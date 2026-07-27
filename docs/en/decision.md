# Technical Decisions

This document explains the key engineering decisions I made throughout
this project, the challenges I encountered, and how I resolved each one.
It is written to be read as if this were a real production incident
report and architecture review, not just a challenge submission.

## 1. API Access Restriction (`/search`, `/items`)

### What happened

Early in development, every call to `GET /sites/MLA/search` and
`GET /items/{id}` returned `403 Forbidden`, even with a correctly
implemented OAuth flow and a valid access token.

### Investigation

Before assuming this was a configuration error, I investigated whether
this was expected behavior:

- Confirmed the OAuth token was valid by successfully calling other
  authenticated endpoints.
- Found that Mercado Libre restricted public access to the general
  `/search` endpoint starting **April 2025**: general product search now
  requires an authenticated user token tied to an account that has
  explicitly granted permission — not just a valid app-level token.
- Found multiple recent, independent reports (developer forums, public
  complaint boards, and third-party API client repositories that
  deprecated their own `search` integrations) confirming that `403` on
  `/search` and `/items` persists even for developers with fully valid
  OAuth tokens and certified applications, as of the challenge deadline.

**Conclusion:** this is a deliberate platform-level access policy, not a
bug in my implementation. The challenge statement (and much of Mercado
Libre's own public documentation) predates this policy change.

### Decision

I did not spend further time trying to "solve" an access restriction
that is outside application-level control. Instead, I:

1. Notified the recruiter in writing as soon as the issue was confirmed,
   including the exact error and my investigation summary.
2. Built the extraction layer to work correctly against the real API
   *if and when access is restored*, with no code changes required.
3. Implemented an explicit, transparent fallback to a realistic sample
   dataset, so the rest of the pipeline (transform, load, analytics)
   could be built, tested, and demonstrated end-to-end without waiting
   on external access.

This turns an external blocker into a demonstration of engineering
judgment: recognizing a problem that isn't mine to fix, documenting it
precisely, and not letting it stop delivery.

## 2. Fallback Strategy: Transparent, Not Hidden

Every row loaded into the database carries a `data_source` column with
value `"live"` or `"sample"`. This means:

- The distinction between real and sample data is never lost — it's
  queryable in the database, not just mentioned in a README.
- If the API is unblocked before review, the exact same code path
  (`extract_products`, `extract_currency_conversion`) will populate
  `data_source = "live"` automatically, with zero code changes.
- Reviewers can verify this claim themselves: `SELECT DISTINCT
  data_source FROM etl.products;`

The sample dataset (`src/sample_data.py`) was not randomly generated. It
follows the exact schema returned by the real API (`/search` and
`/items` response shape, per official documentation) and I deliberately
constructed it with realistic variation, so the analytical queries in
`sql/` produce meaningful, non-trivial results:

- 3 sellers with multiple listings (5, 3, and 2 listings respectively)
  and 11 sellers with a single listing.
- A spread of `sold_quantity` values per seller.
- A realistic price range in ARS.
- A mix of items with and without warranty text.
- All three real `logistic_type` values (`fulfillment`, `drop_off`,
  `cross_docking`).

## 3. `/currency_conversions`: A Different Kind of Restriction

Unlike `/search`, calling `/currency_conversions/search` without a
token returned `401 Unauthorized` with the message `"token not
informed"` — not `403 Forbidden`. This is a meaningfully different
signal: it indicates the endpoint simply requires *any* valid token,
not a user-authorized one tied to policy restrictions.

I confirmed this by implementing the **OAuth Client Credentials**
flow (`src/auth.py`): a lightweight, application-only grant that does
not require a user to authorize anything in a browser. Once
implemented, `/currency_conversions/search?from=ARS&to=USD` returned a
real, live exchange rate.

**Result:** the ETL's currency conversion is fully real (`data_source
= "live"`), while product listings remain sample data
(`data_source = "sample"`) due to the separate, unresolvable `/search`
restriction described above. This hybrid state is intentional and
documented, not accidental.

## 4. Data Modeling Choices

### Composite primary key `(item_id, job_run)`

The challenge requires a `JOB_RUN` `DATETIME` field on every table,
identical for all rows of a single run. Rather than using `item_id`
alone as the primary key (which would force overwriting or skipping
data on every re-run), I used `(item_id, job_run)` as a composite key.

This means every ETL execution is preserved as an independent,
queryable snapshot — which is standard practice in real-world ETL
pipelines (idempotent per-run, not per-record), and lets every SQL
answer be scoped to "the latest run" via:

```sql
WHERE job_run = (SELECT MAX(job_run) FROM etl.products)
```

without losing history from previous runs.

### `has_warranty` (boolean) + `warranty_description` (text)

I derived a boolean `has_warranty` field from the free-text warranty
field returned by the API, so that computing a warranty percentage is
a single `AVG()`/`COUNT() FILTER` in SQL, instead of parsing text at
query time. The original text is preserved in `warranty_description`
for traceability.

### `price_usd` pre-computed at transform time

Rather than storing only `price_ars` and recomputing the USD value in
every query, I pre-computed `price_usd` during transformation using
the real conversion ratio obtained from `/currency_conversions`. This
keeps SQL queries simple and ensures every row in a given run used the
exact same, auditable exchange rate.

## 5. `sold_quantity` as a Proxy for "Sales"

Computing an average-sales-per-seller metric requires some notion of
sales volume. The Mercado Libre API's `sold_quantity` field on
`/search` and `/items` results is documented as **referential only**
— it does not represent the real, current transaction volume. I used
it as the best available proxy given the scope and time constraints of
this project, and I am flagging this limitation explicitly here and in
the README rather than presenting it as an exact sales figure.

A production-grade solution would instead pull actual order data from
the authenticated `/orders` resource (per seller, with proper
authorization), which was out of scope given the time available and
the fact that this challenge concerns public listing data, not private
seller order history.

## 6. What I Would Do Differently With More Time

- Add a lightweight retry/backoff layer in `api.py` for transient
  network errors (currently only 403/401 are handled specially;
  5xx and timeouts propagate directly).
- Add a `/currencies` extraction step (the challenge also lists it as
  an endpoint to use) to validate/display supported currency metadata,
  even though it wasn't strictly required to answer the 5 questions.
- Add automated integration tests that run against a disposable
  Postgres container, in addition to the current unit tests that mock
  the HTTP layer.
- Once/if `/search` access is restored, re-run the pipeline in "live"
  mode and compare the real results against the sample-based ones
  documented here, to validate the analytics logic against real data.