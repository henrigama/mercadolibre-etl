# Modelo de Datos

> *Nota: esta traducción al español fue elaborada con asistencia de
> IA, ya que el español no es mi lengua nativa.*


## Tabla: `etl.products`

Tabla única desnormalizada, elegida deliberadamente en lugar de un
esquema en estrella multi-tabla — ver [`architecture.md`](architecture.md)
sección 6 para el razonamiento.

| Columna | Tipo | Nulable | Descripción |
|---|---|---|---|
| `item_id` | `VARCHAR(20)` | No | ID del artículo en Mercado Libre (ej. `MLA1416598200`). Parte de la clave primaria compuesta. |
| `title` | `VARCHAR(255)` | Sí | Título de la publicación tal como lo devuelve la API. |
| `seller_id` | `BIGINT` | Sí | ID numérico del seller. |
| `seller_nickname` | `VARCHAR(100)` | Sí | Nickname público de la tienda del seller. |
| `condition` | `VARCHAR(20)` | Sí | Siempre `new`; los productos usados se filtran en el momento de la extracción. |
| `price_ars` | `NUMERIC(14,2)` | Sí | Precio original de la publicación en Pesos Argentinos. |
| `price_usd` | `NUMERIC(14,2)` | Sí | Precalculado en la transformación usando la tasa real de `/currency_conversions`. |
| `currency_id` | `VARCHAR(10)` | Sí | Código de moneda de `price_ars` (siempre `ARS` en este dataset). |
| `sold_quantity` | `INTEGER` | Sí | Valor de ventas referencial de la API — no es un conteo de transacciones en tiempo real. Ver `decision.md` §5. |
| `has_warranty` | `BOOLEAN` | Sí | Derivado de `warranty_description`; `false` cuando el texto indica explícitamente ausencia de garantía. |
| `warranty_description` | `VARCHAR(255)` | Sí | Campo de texto libre original de garantía devuelto por la API. |
| `free_shipping` | `BOOLEAN` | Sí | Si la publicación ofrece envío gratis. |
| `logistic_type` | `VARCHAR(30)` | Sí | Uno de `fulfillment`, `drop_off`, `cross_docking`. |
| `data_source` | `VARCHAR(10)` | No | `live` (respuesta real de la API) o `sample` (dataset de fallback). Ver `decision.md` §2. |
| `job_run` | `TIMESTAMP` | No | Timestamp de ejecución, idéntico para todas las filas de una misma corrida del ETL. Parte de la clave primaria compuesta. |

**Clave primaria:** `(item_id, job_run)`
**Índices:** `seller_id`, `job_run` (ver [`ddl/create_tables.sql`](../../ddl/create_tables.sql))

## Notas de Diseño

- **Sin tabla separada de `sellers`.** Los atributos del seller
  (`seller_id`, `seller_nickname`) están desnormalizados directamente
  en `products`. Dado el alcance del desafío — cinco preguntas
  agregadas sobre una sola entidad —, un join agregaría complejidad
  sin beneficio analítico. Si este pipeline creciera para rastrear
  sellers de forma independiente en el tiempo (ej. historial de
  reputación), una tabla de dimensión `sellers` dedicada sería el
  próximo paso natural.
- **Sin tabla separada de `shipping`**, por la misma razón: los
  atributos de envío son 1:1 con una publicación al momento de la
  extracción, no una relación de múltiples valores.
- **`job_run` como parte de la clave primaria, no una tabla de
  auditoría separada.** Esto mantiene los datos de cada corrida
  consultables en el mismo lugar, sin necesitar una tabla de metadata
  `etl_runs` separada para un proyecto de este alcance.