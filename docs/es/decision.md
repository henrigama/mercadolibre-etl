# Decisiones Técnicas

> *Nota: esta traducción al español fue elaborada con asistencia de
> IA, ya que el español no es mi lengua nativa.*


Este documento explica las decisiones de ingeniería clave que tomé a lo
largo de este proyecto, los desafíos que encontré y cómo resolví cada
uno. Está escrito para leerse como un informe real de revisión de
arquitectura, no solo como una entrega de desafío.

## 1. Restricción de acceso a la API (`/search`, `/items`)

### Qué pasó

Al comienzo del desarrollo, cada llamada a `GET /sites/MLA/search` y
`GET /items/{id}` devolvía `403 Forbidden`, incluso con un flujo OAuth
correctamente implementado y un token de acceso válido.

### Investigación

Antes de asumir que era un error de configuración, investigué si este
era el comportamiento esperado:

- Confirmé que el token OAuth era válido llamando exitosamente a otros
  endpoints autenticados.
- Encontré que Mercado Libre restringió el acceso público al endpoint
  general `/search` a partir de **abril de 2025**: la búsqueda general
  de productos ahora requiere un token de usuario autenticado vinculado
  a una cuenta que haya otorgado permiso explícitamente — no solo un
  token válido a nivel de aplicación.
- Encontré múltiples reportes recientes e independientes (foros de
  desarrolladores, plataformas públicas de reclamos y repositorios de
  clientes de API de terceros que discontinuaron sus propias
  integraciones de `search`) que confirman que el `403` en `/search` y
  `/items` persiste incluso para desarrolladores con tokens OAuth
  completamente válidos y aplicaciones certificadas, hasta la fecha
  límite de este desafío.

**Conclusión:** esta es una política de acceso deliberada a nivel de
plataforma, no un error en mi implementación. El enunciado del desafío
(y gran parte de la documentación pública de Mercado Libre) es anterior
a este cambio de política.

### Decisión

No dediqué más tiempo a intentar "resolver" una restricción de acceso
que está fuera del control de la aplicación. En cambio:

1. Notifiqué al reclutador por escrito apenas confirmé el problema,
   incluyendo el error exacto y el resumen de mi investigación.
2. Construí la capa de extracción para que funcione correctamente
   contra la API real *si y cuando se restablezca el acceso*, sin
   requerir cambios de código.
3. Implementé un fallback explícito y transparente a un dataset de
   muestra realista, para poder construir, probar y demostrar el resto
   del pipeline (transform, load, analítica) de punta a punta sin
   depender del acceso externo.

Esto convierte un bloqueo externo en una demostración de criterio de
ingeniería: reconocer un problema que no me corresponde resolver,
documentarlo con precisión, y no dejar que detenga la entrega.

## 2. Estrategia de Fallback: Transparente, No Oculta

Cada fila cargada en la base de datos lleva una columna `data_source`
con valor `"live"` o `"sample"`. Esto significa:

- La distinción entre datos reales y de muestra nunca se pierde — es
  consultable en la base de datos, no solo mencionada en un README.
- Si la API se desbloquea antes de la revisión, el mismo código
  (`extract_products`, `extract_currency_conversion`) poblará
  `data_source = "live"` automáticamente, sin cambios de código.
- Los evaluadores pueden verificar esto ellos mismos: `SELECT DISTINCT
  data_source FROM etl.products;`

El dataset de muestra (`src/sample_data.py`) no fue generado
aleatoriamente. Sigue exactamente el esquema devuelto por la API real
(estructura de respuesta de `/search` e `/items`, según la
documentación oficial) y lo construí deliberadamente con variación
realista, para que las consultas analíticas en `sql/` produzcan
resultados significativos y no triviales:

- 3 sellers con múltiples publicaciones (5, 3 y 2 publicaciones
  respectivamente) y 11 sellers con una sola publicación.
- Una distribución de valores de `sold_quantity` por seller.
- Un rango de precios realista en ARS.
- Una mezcla de artículos con y sin texto de garantía.
- Los tres valores reales de `logistic_type` (`fulfillment`,
  `drop_off`, `cross_docking`).

## 3. `/currency_conversions`: Un Tipo Diferente de Restricción

A diferencia de `/search`, llamar a `/currency_conversions/search` sin
un token devolvió `401 Unauthorized` con el mensaje `"token not
informed"` — no `403 Forbidden`. Esta es una señal significativamente
diferente: indica que el endpoint simplemente requiere *algún* token
válido, no uno autorizado por un usuario vinculado a restricciones de
política.

Confirmé esto implementando el flujo **OAuth Client Credentials**
(`src/auth.py`): un grant liviano, solo de aplicación, que no requiere
que un usuario autorice nada en un navegador. Una vez implementado,
`/currency_conversions/search?from=ARS&to=USD` devolvió una tasa de
cambio real y en vivo.

**Resultado:** la conversión de moneda del ETL es completamente real
(`data_source = "live"`), mientras que las publicaciones de productos
siguen siendo datos de muestra (`data_source = "sample"`) debido a la
restricción separada e irresoluble de `/search` descrita arriba. Este
estado híbrido es intencional y está documentado, no es accidental.

## 4. Decisiones de Modelado de Datos

### Clave primaria compuesta `(item_id, job_run)`

El desafío exige un campo `JOB_RUN` de tipo `DATETIME` en cada tabla,
idéntico para todas las filas de una misma corrida. En lugar de usar
`item_id` solo como clave primaria (lo que forzaría sobrescribir u
omitir datos en cada re-ejecución), usé `(item_id, job_run)` como clave
compuesta.

Esto significa que cada ejecución del ETL se preserva como una
instantánea independiente y consultable — lo cual es una práctica
estándar en pipelines ETL del mundo real (idempotente por corrida, no
por registro), y permite que cada respuesta SQL se limite a "la última
corrida" mediante:

```sql
WHERE job_run = (SELECT MAX(job_run) FROM etl.products)
```

sin perder el historial de corridas anteriores.

### `has_warranty` (booleano) + `warranty_description` (texto)

Deriví un campo booleano `has_warranty` a partir del campo de texto
libre de garantía devuelto por la API, para que calcular un porcentaje
de garantía sea un simple `AVG()`/`COUNT() FILTER` en SQL, en lugar de
parsear texto en tiempo de consulta. El texto original se conserva en
`warranty_description` para trazabilidad.

### `price_usd` precalculado en la transformación

En lugar de almacenar solo `price_ars` y recalcular el valor en USD en
cada consulta, precalculé `price_usd` durante la transformación usando
la tasa de conversión real obtenida de `/currency_conversions`. Esto
mantiene las consultas SQL simples y garantiza que cada fila de una
corrida dada usó exactamente la misma tasa de cambio, auditable.

## 5. `sold_quantity` como Proxy de "Ventas"

Calcular un promedio de ventas por seller requiere alguna noción de
volumen de ventas. El campo `sold_quantity` de la API de Mercado Libre
en `/search` e `/items` está documentado como **solo referencial** —
no representa el volumen real y actual de transacciones. Lo usé como
el mejor proxy disponible dado el alcance y las restricciones de
tiempo de este proyecto, y estoy señalando esta limitación
explícitamente aquí y en el README, en lugar de presentarlo como una
cifra exacta de ventas.

Una solución de nivel productivo consultaría en cambio datos reales de
órdenes desde el recurso autenticado `/orders` (por seller, con la
autorización correspondiente), lo cual quedó fuera de alcance dado el
tiempo disponible y el hecho de que este desafío trata sobre datos
públicos de publicaciones, no sobre historial privado de órdenes del
seller.

## 6. Qué Haría Diferente Con Más Tiempo

- Agregar una capa liviana de retry/backoff en `api.py` para errores de
  red transitorios (actualmente solo 403/401 tienen manejo especial;
  errores 5xx y timeouts se propagan directamente).
- Agregar un paso de extracción de `/currencies` (el desafío también lo
  lista como endpoint a utilizar) para validar/mostrar metadata de
  monedas soportadas, aunque no era estrictamente necesario para
  responder las 5 preguntas.
- Agregar tests de integración que corran contra un contenedor Postgres
  descartable, además de los tests unitarios actuales que mockean la
  capa HTTP.
- Una vez que se restablezca el acceso a `/search`, volver a correr el
  pipeline en modo "live" y comparar los resultados reales contra los
  basados en muestra documentados aquí, para validar la lógica
  analítica contra datos reales.