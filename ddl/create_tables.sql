-- Single normalized table for the Mercado Libre ETL Challenge.
-- JOB_RUN is required on every table and represents the unique
-- timestamp of each ETL execution.
--
-- Prerequisite: the target database (e.g. `mercadolibre_etl`) must
-- already exist and this script must be run while connected to it.
-- See README.md, section "Setup", step 4.

CREATE SCHEMA IF NOT EXISTS etl;

CREATE TABLE IF NOT EXISTS etl.products (
    item_id               VARCHAR(20)     NOT NULL,
    title                 VARCHAR(255),
    seller_id             BIGINT,
    seller_nickname       VARCHAR(100),
    condition             VARCHAR(20),
    price_ars             NUMERIC(14,2),
    price_usd             NUMERIC(14,2),
    currency_id           VARCHAR(10),
    sold_quantity         INTEGER,
    has_warranty          BOOLEAN,
    warranty_description  VARCHAR(255),
    free_shipping         BOOLEAN,
    logistic_type         VARCHAR(30),
    data_source           VARCHAR(10)     NOT NULL,  -- 'live' or 'sample'
    job_run                TIMESTAMP       NOT NULL,
    PRIMARY KEY (item_id, job_run)
);

CREATE INDEX IF NOT EXISTS idx_products_seller ON etl.products (seller_id);
CREATE INDEX IF NOT EXISTS idx_products_job_run ON etl.products (job_run);