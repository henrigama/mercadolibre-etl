# Mercado Libre ETL Challenge

> *Nota: esta traducción al español fue elaborada con asistencia de
> IA, ya que el español no es mi lengua nativa.*

Un pipeline ETL en Python que extrae publicaciones de productos
Samsung Galaxy S24 de la API pública de Mercado Libre (Argentina), las
transforma en un modelo relacional normalizado, y las carga en
PostgreSQL para responder cinco preguntas de negocio vía SQL.

> **Nota sobre la fuente de datos:** como se documenta en
> [`decision.md`](decision.md), los endpoints públicos `/search` e
> `/items` de Mercado Libre devuelven `403 Forbidden` incluso con un
> token OAuth válido y correctamente scoped. Esto coincide con un
> problema conocido, reportado públicamente por otros desarrolladores
> desde al menos abril de 2025 (ver `decision.md` §1 para las fuentes)
> — Mercado Libre no publicó un changelog oficial al respecto, así que
> no puedo confirmar una fecha exacta de despliegue, solo que la
> restricción es real, actual, e independiente de esta implementación.
> Este pipeline detecta esa condición automáticamente y recurre a un
> dataset de muestra fiel al esquema real, mientras que
> `/currency_conversions` corre contra la **API real y en vivo** vía
> OAuth Client Credentials. Cada fila en la base de datos está
> etiquetada con `data_source = 'live' | 'sample'`, así que esto es
> totalmente transparente y auditable — no está oculto.

## Arquitectura

Ver [`architecture.md`](architecture.md) para el diseño completo por
capas y un diagrama del pipeline.

src/
├── main.py # Orquesta el pipeline completo
├── config.py # Carga config.yaml + inyecta credenciales OAuth
├── auth.py # Flujo OAuth Client Credentials
├── api.py # Cliente HTTP con manejo de errores 403/401
├── extract.py # Lógica de extracción + fallback
├── sample_data.py # Dataset de fallback fiel al esquema real
├── transform.py # Aplana el JSON crudo en filas listas para la DB
├── database.py # Motor SQLAlchemy a partir de .env
└── load.py # Inserta filas en PostgreSQL

config/
├── config.yaml # Configuración no sensible (endpoints, paginación, query)
└── logging.yaml

ddl/
└── create_tables.sql

sql/
└── question1.sql … question5.sql # Una query por pregunta de negocio

docs/
├── en/
├── es/
└── pt/

tests/
├── conftest.py
└── test_extract.py

## Prerrequisitos

- Python 3.11+
- PostgreSQL 16+ (local o remoto)
- Una aplicación de Mercado Libre Developer ([developers.mercadolibre.com](https://developers.mercadolibre.com)) configurada con el flujo OAuth **Client Credentials**

## Configuración

### 1. Clonar y crear un entorno virtual

```bash
git clone <this-repo-url>
cd mercadolibre-etl
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Copiá el archivo de ejemplo y completá tus propios valores — **nunca
subas `.env` al repositorio**:

```bash
cp .env.example .env
```

| Variable | Descripción |
|---|---|
| `ML_CLIENT_ID` | Client ID de tu aplicación de Mercado Libre |
| `ML_CLIENT_SECRET` | Client Secret de tu aplicación de Mercado Libre |
| `DB_HOST` | Host de PostgreSQL (ej. `localhost`) |
| `DB_PORT` | Puerto de PostgreSQL (default `5432`) |
| `DB_NAME` | Nombre de la base de datos |
| `DB_USER` | Usuario de la base de datos |
| `DB_PASSWORD` | Contraseña de la base de datos |
| `DB_SCHEMA` | Schema a utilizar (este proyecto usa `etl`) |

### 4. Crear la base de datos y el schema

```sql
CREATE DATABASE mercadolibre_etl;
```

Luego, conectado a esa base de datos, ejecutá:

```bash
psql -U <user> -d mercadolibre_etl -f ../../ddl/create_tables.sql
```

(o ejecutá `ddl/create_tables.sql` directamente desde DBeaver/pgAdmin).

### 5. Correr el pipeline

```bash
python src/main.py
```

Deberías ver logs estructurados mostrando la extracción (real o
fallback de muestra), la tasa de cambio real, y la cantidad de filas
cargadas en `etl.products`.

## Modelo de Datos

Ver [`data_model.md`](data_model.md) para la referencia completa del
esquema. Resumen:

**Tabla `etl.products`**

| Columna | Tipo | Notas |
|---|---|---|
| `item_id` | VARCHAR(20) | Parte de la PK compuesta |
| `title` | VARCHAR(255) | |
| `seller_id` | BIGINT | |
| `seller_nickname` | VARCHAR(100) | |
| `condition` | VARCHAR(20) | Siempre `new`; los productos usados se filtran en el momento de la extracción |
| `price_ars` | NUMERIC(14,2) | |
| `price_usd` | NUMERIC(14,2) | Precalculado con la tasa real de conversión |
| `currency_id` | VARCHAR(10) | |
| `sold_quantity` | INTEGER | Valor referencial — ver `decision.md` §5 |
| `has_warranty` | BOOLEAN | Derivado de `warranty_description` |
| `warranty_description` | VARCHAR(255) | Texto original de la API |
| `free_shipping` | BOOLEAN | |
| `logistic_type` | VARCHAR(30) | `fulfillment` / `drop_off` / `cross_docking` |
| `data_source` | VARCHAR(10) | `live` o `sample` — ver nota arriba |
| `job_run` | TIMESTAMP | Parte de la PK compuesta; igual para todas las filas de una corrida |

Clave primaria: `(item_id, job_run)` — ver [`decision.md`](decision.md)
§4 para el porqué.

## Preguntas de Negocio y Respuestas

Cada pregunta se responde con un archivo SQL independiente en
[`sql/`](../../sql/), siempre limitado a la corrida más reciente del
ETL. Los resultados abajo son del dataset de muestra actual (21
publicaciones) combinado con una tasa de cambio **real**.

### 1. ¿Hay algún vendedor con múltiples publicaciones? ¿Con cuántas?

[`sql/question1.sql`](../../sql/question1.sql)

| seller_id | seller_nickname | total_publicaciones |
|---|---|---|
| 205417396 | TIENDA_SAMSUNG_OFICIAL | 5 |
| 118820033 | MOVISTAR_TIENDA_OFICIAL | 3 |
| 300112244 | CELULARES_DEL_SUR | 2 |

### 2. Promedio de ventas por seller

[`sql/question2.sql`](../../sql/question2.sql)

> `sold_quantity` es un valor referencial de la API pública, no un
> conteo de ventas en tiempo real — ver [`decision.md`](decision.md) §5.

| seller_id | seller_nickname | total_publicaciones | promedio_sold_quantity |
|---|---|---|---|
| 302990011 | CELUMANIA_TUCUMAN | 1 | 203.00 |
| 205417396 | TIENDA_SAMSUNG_OFICIAL | 5 | 170.20 |
| … | … | … | … |
| 300998877 | IMPORT_PHONES_AR | 1 | 12.00 |

Ranking completo entre los 14 sellers distintos en [`sql/question2.sql`](../../sql/question2.sql).

### 3. Precio promedio en dólares

[`sql/question3.sql`](../../sql/question3.sql)

| precio_promedio_usd | total_publicaciones | precio_minimo_usd | precio_maximo_usd |
|---|---|---|---|
| **724.62** | 21 | 454.24 | 1135.60 |

### 4. Porcentaje de artículos con garantía

[`sql/question4.sql`](../../sql/question4.sql)

| con_garantia | sin_garantia | porcentaje_con_garantia |
|---|---|---|
| 16 | 5 | **76.2** |

### 5. Métodos de shipping que ofrecen

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

Los tests unitarios mockean la capa HTTP para verificar tanto el
camino de fallback (activado por `403`) como el camino de datos
reales, sin requerir acceso a internet ni credenciales reales.

## Documentación

- [`architecture.md`](architecture.md) — diseño por capas, diagrama, filosofía de manejo de errores
- [`decision.md`](decision.md) — desafíos encontrados y el razonamiento detrás de cada decisión importante
- [`data_model.md`](data_model.md) — referencia completa del esquema de la tabla

## Mejoras Futuras

Ver [`decision.md`](decision.md) §6 para la lista completa. Destacados:

- Retry/backoff para errores de red transitorios
- Integración del endpoint `/currencies` para metadata de monedas
- Tests de integración contra un contenedor Postgres descartable
- Re-validar la analítica contra datos reales de `/search` una vez que se restablezca el acceso