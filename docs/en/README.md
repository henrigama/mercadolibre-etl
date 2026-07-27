# Mercado Libre ETL Challenge

A Python ETL pipeline that extracts Samsung Galaxy S24 product listings
from the Mercado Libre public API (Argentina), transforms them into a
normalized relational model, and loads them into PostgreSQL to answer
five business questions via SQL.

> **Note on data source:** as documented in [`decision.md`](decision.md),
> Mercado Libre's `/search` and `/items` public endpoints have been
> restricted by platform policy since April 2025 and return `403
> Forbidden` even with a valid, correctly-scoped OAuth token — a known,
> widely reported issue independent of this implementation. This
> pipeline detects that condition automatically and falls back to a
> schema-accurate sample dataset, while `/currency_conversions` runs
> against the **real, live API** via OAuth Client Credentials. Every row
> in the database is tagged with `data_source = 'live' | 'sample'`, so
> this is fully transparent and auditable — not hidden.

## Architecture

See [`architecture.md`](architecture.md) for the full layered design
and a diagram of the pipeline.

src/
├── main.py # Orchestrates the full pipeline
├── config.py # Loads config.yaml + injects OAuth credentials
├── auth.py # OAuth Client Credentials flow
├── api.py # HTTP client with 403/401-aware error handling
├── extract.py # Extraction + fallback logic
├── sample_data.py # Schema-accurate fallback dataset
├── transform.py # Flattens raw JSON into DB-ready rows
├── database.py # SQLAlchemy engine from .env
└── load.py # Inserts rows into PostgreSQL

config/
├── config.yaml # Non-sensitive settings (endpoints, pagination, query)
└── logging.yaml

ddl/
└── create_tables.sql

sql/
└── question1.sql … question5.sql # One query per business question

docs/
├── en/
├── es/
└── pt/

tests/
├── conftest.py
└── test_extract.py

## Prerequisites

- Python 3.11+
- PostgreSQL 16+ (local or remote)
- A Mercado Libre Developer application ([developers.mercadolibre.com](https://developers.mercadolibre.com)) configured with the **Client Credentials** OAuth flow

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <this-repo-url>
cd mercadolibre-etl
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and fill in your own values — **never commit `.env`**:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `ML_CLIENT_ID` | Client ID of your Mercado Libre application |
| `ML_CLIENT_SECRET` | Client Secret of your Mercado Libre application |
| `DB_HOST` | PostgreSQL host (e.g. `localhost`) |
| `DB_PORT` | PostgreSQL port (default `5432`) |
| `DB_NAME` | Database name |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `DB_SCHEMA` | Schema to use (this project uses `etl`) |

### 4. Create the database and schema

```sql
CREATE DATABASE mercadolibre_etl;
```

Then, connected to that database, run:

```bash
psql -U <user> -d mercadolibre_etl -f ddl/create_tables.sql
```

(or execute `ddl/create_tables.sql` directly from DBeaver/pgAdmin).

### 5. Run the pipeline

```bash
python src/main.py
```

You should see structured logs showing extraction (live or sample
fallback), the live currency conversion rate, and the number of rows
loaded into `etl.products`.

## Data Model

See [`data_model.md`](data_model.md) for the full schema reference. Summary:

**Table `etl.products`**

| Column | Type | Notes |
|---|---|---|
| `item_id` | VARCHAR(20) | Part of composite PK |
| `title` | VARCHAR(255) | |
| `seller_id` | BIGINT | |
| `seller_nickname` | VARCHAR(100) | |
| `condition` | VARCHAR(20) | Always `new`; used products are filtered out at extraction time |
| `price_ars` | NUMERIC(14,2) | |
| `price_usd` | NUMERIC(14,2) | Pre-computed using live conversion rate |
| `currency_id` | VARCHAR(10) | |
| `sold_quantity` | INTEGER | Referential value — see `decision.md` §5 |
| `has_warranty` | BOOLEAN | Derived from `warranty_description` |
| `warranty_description` | VARCHAR(255) | Original API text |
| `free_shipping` | BOOLEAN | |
| `logistic_type` | VARCHAR(30) | `fulfillment` / `drop_off` / `cross_docking` |
| `data_source` | VARCHAR(10) | `live` or `sample` — see note above |
| `job_run` | TIMESTAMP | Part of composite PK; same for every row of one run |

Primary key: `(item_id, job_run)` — see [`decision.md`](decision.md) §4 for why.

## Business Questions & Answers

Each question is answered by a standalone SQL file in [`sql/`](../../sql/),
always scoped to the most recent ETL run. Results below are from the
current fallback sample dataset (21 listings) combined with a **live**
currency conversion rate.

> Note: SQL column aliases below are kept in Spanish, matching the
> original language of the challenge statement and its questions
> (`total_publicaciones`, `con_garantia`, etc.) — see [`sql/`](../../sql/)
> for the actual queries.

### 1. Is there a seller with multiple listings? How many?

[`sql/question1.sql`](../../sql/question1.sql)

| seller_id | seller_nickname | total_publicaciones |
|---|---|---|
| 205417396 | TIENDA_SAMSUNG_OFICIAL | 5 |
| 118820033 | MOVISTAR_TIENDA_OFICIAL | 3 |
| 300112244 | CELULARES_DEL_SUR | 2 |

### 2. Average sales per seller

[`sql/question2.sql`](../../sql/question2.sql)

> `sold_quantity` is a referential value from the public API, not a
> real-time sales count — see [`decision.md`](decision.md) §5.

| seller_id | seller_nickname | total_publicaciones | promedio_sold_quantity |
|---|---|---|---|
| 302990011 | CELUMANIA_TUCUMAN | 1 | 203.00 |
| 205417396 | TIENDA_SAMSUNG_OFICIAL | 5 | 170.20 |
| … | … | … | … |
| 300998877 | IMPORT_PHONES_AR | 1 | 12.00 |

Full ranking across all 14 distinct sellers in [`sql/question2.sql`](../../sql/question2.sql).

### 3. Average price in USD

[`sql/question3.sql`](../../sql/question3.sql)

| precio_promedio_usd | total_publicaciones | precio_minimo_usd | precio_maximo_usd |
|---|---|---|---|
| **724.62** | 21 | 454.24 | 1135.60 |

### 4. Percentage of items with warranty

[`sql/question4.sql`](../../sql/question4.sql)

| con_garantia | sin_garantia | porcentaje_con_garantia |
|---|---|---|
| 16 | 5 | **76.2** |

### 5. Shipping methods offered

[`sql/question5.sql`](../../sql/question5.sql)

| logistic_type | total_publicaciones | con_envio_gratis | porcentaje |
|---|---|---|---|
| fulfillment | 10 | 10 | 47.6 |
| drop_off | 7 | 3 | 33.3 |
| cross_docking | 4 | 3 | 19.0 |

## Testing

```bash
python -m pytest tests/
```

Unit tests mock the HTTP layer to verify both the `403`-triggered
fallback path and the live-data path, without requiring network
access or real credentials.

## Documentation

- [`architecture.md`](architecture.md) — layered design, diagram, error-handling philosophy
- [`decision.md`](decision.md) — challenges encountered and the reasoning behind every major decision
- [`data_model.md`](data_model.md) — full table schema reference

## Future Improvements

See [`decision.md`](decision.md) §6 for a full list. Highlights:

- Retry/backoff for transient network errors
- `/currencies` endpoint integration for currency metadata
- Integration tests against a disposable Postgres container
- Re-validating analytics against live `/search` data once/if access is restored