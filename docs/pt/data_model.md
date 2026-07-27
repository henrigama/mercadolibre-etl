# Modelo de Dados

## Tabela: `etl.products`

Tabela única desnormalizada, escolhida deliberadamente em vez de um
esquema estrela com múltiplas tabelas — ver [`architecture.md`](architecture.md)
seção 6 para o raciocínio.

| Coluna | Tipo | Nulável | Descrição |
|---|---|---|---|
| `item_id` | `VARCHAR(20)` | Não | ID do item no Mercado Livre (ex. `MLA1416598200`). Parte da chave primária composta. |
| `title` | `VARCHAR(255)` | Sim | Título da publicação conforme retornado pela API. |
| `seller_id` | `BIGINT` | Sim | ID numérico do seller. |
| `seller_nickname` | `VARCHAR(100)` | Sim | Nickname público da loja do seller. |
| `condition` | `VARCHAR(20)` | Sim | Sempre `new`; produtos usados são filtrados no momento da extração. |
| `price_ars` | `NUMERIC(14,2)` | Sim | Preço original da publicação em Pesos Argentinos. |
| `price_usd` | `NUMERIC(14,2)` | Sim | Pré-calculado na transformação usando a taxa real de `/currency_conversions`. |
| `currency_id` | `VARCHAR(10)` | Sim | Código de moeda de `price_ars` (sempre `ARS` neste dataset). |
| `sold_quantity` | `INTEGER` | Sim | Valor de vendas referencial da API — não é uma contagem de transações em tempo real. Ver `decision.md` §5. |
| `has_warranty` | `BOOLEAN` | Sim | Derivado de `warranty_description`; `false` quando o texto indica explicitamente ausência de garantia. |
| `warranty_description` | `VARCHAR(255)` | Sim | Campo de texto livre original de garantia retornado pela API. |
| `free_shipping` | `BOOLEAN` | Sim | Se a publicação oferece frete grátis. |
| `logistic_type` | `VARCHAR(30)` | Sim | Um de `fulfillment`, `drop_off`, `cross_docking`. |
| `data_source` | `VARCHAR(10)` | Não | `live` (resposta real da API) ou `sample` (dataset de fallback). Ver `decision.md` §2. |
| `job_run` | `TIMESTAMP` | Não | Timestamp de execução, idêntico para todas as linhas de uma mesma execução do ETL. Parte da chave primária composta. |

**Chave primária:** `(item_id, job_run)`
**Índices:** `seller_id`, `job_run` (ver [`ddl/create_tables.sql`](../../ddl/create_tables.sql))

## Notas de Design

- **Sem tabela separada de `sellers`.** Os atributos do seller
  (`seller_id`, `seller_nickname`) estão desnormalizados diretamente
  em `products`. Dado o escopo do desafio — cinco perguntas agregadas
  sobre uma única entidade —, um join adicionaria complexidade sem
  benefício analítico. Se este pipeline crescesse para rastrear
  sellers de forma independente ao longo do tempo (ex. histórico de
  reputação), uma tabela de dimensão `sellers` dedicada seria o
  próximo passo natural.
- **Sem tabela separada de `shipping`**, pelo mesmo motivo: os
  atributos de frete são 1:1 com uma publicação no momento da
  extração, não uma relação de múltiplos valores.
- **`job_run` como parte da chave primária, não uma tabela de
  auditoria separada.** Isso mantém os dados de cada execução
  consultáveis no mesmo lugar, sem precisar de uma tabela de metadados
  `etl_runs` separada para um projeto deste escopo.