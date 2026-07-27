# Data Model

## Table: `etl.products`

Single denormalized table, chosen deliberately over a multi-table star
schema — see [`architecture.md`](architecture.md) §6 for the reasoning.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `item_id` | `VARCHAR(20)` | No | Mercado Libre item ID (e.g. `MLA1416598200`). Part of composite primary key. |
| `title` | `VARCHAR(255)` | Yes | Listing title as returned by the API. |
| `seller_id` | `BIGINT` | Yes | Numeric seller ID. |
| `seller_nickname` | `VARCHAR(100)` | Yes | Seller's public store nickname. |
| `condition` | `VARCHAR(20)` | Yes | Always `new`; used products are filtered out at extraction time. |
| `price_ars` | `NUMERIC(14,2)` | Yes | Original listing price in Argentine Pesos. |
| `price_usd` | `NUMERIC(14,2)` | Yes | Pre-computed at transform time using the live rate from `/currency_conversions`. |
| `currency_id` | `VARCHAR(10)` | Yes | Currency code of `price_ars` (always `ARS` for this dataset). |
| `sold_quantity` | `INTEGER` | Yes | Referential sales figure from the API — not a real-time transaction count. See `decision.md` §5. |
| `has_warranty` | `BOOLEAN` | Yes | Derived from `warranty_description`; `false` when the text explicitly indicates no warranty. |
| `warranty_description` | `VARCHAR(255)` | Yes | Original free-text warranty field from the API. |
| `free_shipping` | `BOOLEAN` | Yes | Whether the listing offers free shipping. |
| `logistic_type` | `VARCHAR(30)` | Yes | One of `fulfillment`, `drop_off`, `cross_docking`. |
| `data_source` | `VARCHAR(10)` | No | `live` (real API response) or `sample` (fallback dataset). See `decision.md` §2. |
| `job_run` | `TIMESTAMP` | No | Execution timestamp, identical for every row of a single ETL run. Part of composite primary key. |

**Primary key:** `(item_id, job_run)`
**Indexes:** `seller_id`, `job_run` (see [`ddl/create_tables.sql`](../../ddl/create_tables.sql))

## Design Notes

- **No separate `sellers` table.** Seller attributes (`seller_id`,
  `seller_nickname`) are denormalized directly into `products`. Given
  the challenge's scope — five aggregate questions over one entity — a
  join would add complexity with no analytical benefit. If this
  pipeline grew to track sellers independently over time (e.g.
  reputation history), a dedicated `sellers` dimension table would be
  the natural next step.
- **No separate `shipping` table**, for the same reason: shipping
  attributes are 1:1 with a listing at extraction time, not a
  many-valued relationship.
- **`job_run` as part of the primary key, not a separate audit table.**
  This keeps every run's data queryable in place, without needing a
  separate `etl_runs` metadata table for a project of this scope.