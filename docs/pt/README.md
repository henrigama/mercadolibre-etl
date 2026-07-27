# Mercado Libre ETL Challenge

Um pipeline ETL em Python que extrai publicações de produtos Samsung
Galaxy S24 da API pública do Mercado Livre (Argentina), transforma-as
em um modelo relacional normalizado, e as carrega no PostgreSQL para
responder cinco perguntas de negócio via SQL.

> **Nota sobre a fonte dos dados:** conforme documentado em
> [`decision.md`](decision.md), os endpoints públicos `/search` e
> `/items` do Mercado Livre retornam `403 Forbidden` mesmo com um token
> OAuth válido e corretamente escopado. Isso coincide com um problema
> conhecido, relatado publicamente por outros desenvolvedores desde
> pelo menos abril de 2025 (ver `decision.md` §1 para as fontes) — o
> Mercado Livre não publicou um changelog oficial sobre isso, então não
> consigo confirmar uma data exata de lançamento, só que a restrição é
> real, atual, e independente desta implementação. Este pipeline
> detecta essa condição automaticamente e recorre a um dataset de
> amostra fiel ao esquema real, enquanto `/currency_conversions` roda
> contra a **API real e ao vivo** via OAuth Client Credentials. Cada
> linha no banco de dados é marcada com `data_source = 'live' |
> 'sample'`, então isso é totalmente transparente e auditável — não
> está escondido.

## Arquitetura

Ver [`architecture.md`](architecture.md) para o design completo em
camadas e um diagrama do pipeline.

src/
├── main.py # Orquestra o pipeline completo
├── config.py # Carrega config.yaml + injeta credenciais OAuth
├── auth.py # Fluxo OAuth Client Credentials
├── api.py # Cliente HTTP com tratamento de erros 403/401
├── extract.py # Lógica de extração + fallback
├── sample_data.py # Dataset de fallback fiel ao esquema real
├── transform.py # Achata o JSON bruto em linhas prontas para o banco
├── database.py # Engine SQLAlchemy a partir do .env
└── load.py # Insere linhas no PostgreSQL

config/
├── config.yaml # Configurações não sensíveis (endpoints, paginação, query)
└── logging.yaml

ddl/
└── create_tables.sql

sql/
└── question1.sql … question5.sql # Uma query por pergunta de negócio

docs/
├── en/
├── es/
└── pt/

tests/
├── conftest.py
└── test_extract.py

## Pré-requisitos

- Python 3.11+
- PostgreSQL 16+ (local ou remoto)
- Uma aplicação Mercado Livre Developer ([developers.mercadolibre.com](https://developers.mercadolibre.com)) configurada com o fluxo OAuth **Client Credentials**

## Configuração

### 1. Clonar e criar um ambiente virtual

```bash
git clone <this-repo-url>
cd mercadolibre-etl
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

Copie o arquivo de exemplo e preencha com seus próprios valores —
**nunca suba o `.env`**:

```bash
cp .env.example .env
```

| Variável | Descrição |
|---|---|
| `ML_CLIENT_ID` | Client ID da sua aplicação Mercado Livre |
| `ML_CLIENT_SECRET` | Client Secret da sua aplicação Mercado Livre |
| `DB_HOST` | Host do PostgreSQL (ex. `localhost`) |
| `DB_PORT` | Porta do PostgreSQL (padrão `5432`) |
| `DB_NAME` | Nome do banco de dados |
| `DB_USER` | Usuário do banco de dados |
| `DB_PASSWORD` | Senha do banco de dados |
| `DB_SCHEMA` | Schema a ser usado (este projeto usa `etl`) |

### 4. Criar o banco de dados e o schema

```sql
CREATE DATABASE mercadolibre_etl;
```

Depois, conectado a esse banco, rode:

```bash
psql -U <user> -d mercadolibre_etl -f ../../ddl/create_tables.sql
```

(ou execute `ddl/create_tables.sql` diretamente pelo DBeaver/pgAdmin).

### 5. Rodar o pipeline

```bash
python src/main.py
```

Você deve ver logs estruturados mostrando a extração (real ou fallback
de amostra), a taxa de câmbio real, e a quantidade de linhas
carregadas em `etl.products`.

## Modelo de Dados

Ver [`data_model.md`](data_model.md) para a referência completa do
esquema. Resumo:

**Tabela `etl.products`**

| Coluna | Tipo | Notas |
|---|---|---|
| `item_id` | VARCHAR(20) | Parte da PK composta |
| `title` | VARCHAR(255) | |
| `seller_id` | BIGINT | |
| `seller_nickname` | VARCHAR(100) | |
| `condition` | VARCHAR(20) | Sempre `new`; produtos usados são filtrados no momento da extração |
| `price_ars` | NUMERIC(14,2) | |
| `price_usd` | NUMERIC(14,2) | Pré-calculado com a taxa real de conversão |
| `currency_id` | VARCHAR(10) | |
| `sold_quantity` | INTEGER | Valor referencial — ver `decision.md` §5 |
| `has_warranty` | BOOLEAN | Derivado de `warranty_description` |
| `warranty_description` | VARCHAR(255) | Texto original da API |
| `free_shipping` | BOOLEAN | |
| `logistic_type` | VARCHAR(30) | `fulfillment` / `drop_off` / `cross_docking` |
| `data_source` | VARCHAR(10) | `live` ou `sample` — ver nota acima |
| `job_run` | TIMESTAMP | Parte da PK composta; igual para todas as linhas de uma execução |

Chave primária: `(item_id, job_run)` — ver [`decision.md`](decision.md)
§4 para o porquê.

## Perguntas de Negócio e Respostas

Cada pergunta é respondida por um arquivo SQL independente em
[`sql/`](../../sql/), sempre limitado à execução mais recente do ETL.
Os resultados abaixo são do dataset de amostra atual (21 publicações)
combinado com uma taxa de câmbio **real**.

> Nota: os aliases das colunas SQL abaixo permanecem em espanhol,
> seguindo o idioma original do enunciado do desafio e de suas
> perguntas (`total_publicaciones`, `con_garantia`, etc.) — ver
> [`sql/`](../../sql/) para as queries reais.

### 1. Há algum seller com múltiplas publicações? Quantas?

[`sql/question1.sql`](../../sql/question1.sql)

| seller_id | seller_nickname | total_publicaciones |
|---|---|---|
| 205417396 | TIENDA_SAMSUNG_OFICIAL | 5 |
| 118820033 | MOVISTAR_TIENDA_OFICIAL | 3 |
| 300112244 | CELULARES_DEL_SUR | 2 |

### 2. Média de vendas por seller

[`sql/question2.sql`](../../sql/question2.sql)

> `sold_quantity` é um valor referencial da API pública, não uma
> contagem de vendas em tempo real — ver [`decision.md`](decision.md) §5.

| seller_id | seller_nickname | total_publicaciones | promedio_sold_quantity |
|---|---|---|---|
| 302990011 | CELUMANIA_TUCUMAN | 1 | 203.00 |
| 205417396 | TIENDA_SAMSUNG_OFICIAL | 5 | 170.20 |
| … | … | … | … |
| 300998877 | IMPORT_PHONES_AR | 1 | 12.00 |

Ranking completo entre os 14 sellers distintos em [`sql/question2.sql`](../../sql/question2.sql).

### 3. Preço médio em dólares

[`sql/question3.sql`](../../sql/question3.sql)

| precio_promedio_usd | total_publicaciones | precio_minimo_usd | precio_maximo_usd |
|---|---|---|---|
| **724.62** | 21 | 454.24 | 1135.60 |

### 4. Percentual de itens com garantia

[`sql/question4.sql`](../../sql/question4.sql)

| con_garantia | sin_garantia | porcentaje_con_garantia |
|---|---|---|
| 16 | 5 | **76.2** |

### 5. Métodos de shipping oferecidos

[`sql/question5.sql`](../../sql/question5.sql)

| logistic_type | total_publicaciones | con_envio_gratis | porcentaje |
|---|---|---|---|
| fulfillment | 10 | 10 | 47.6 |
| drop_off | 7 | 3 | 33.3 |
| cross_docking | 4 | 3 | 19.0 |

## Testes

```bash
python -m pytest tests/
```

Os testes unitários fazem mock da camada HTTP para verificar tanto o
caminho de fallback (ativado por `403`) quanto o caminho de dados
reais, sem exigir acesso à internet nem credenciais reais.

## Documentação

- [`architecture.md`](architecture.md) — design em camadas, diagrama, filosofia de tratamento de erros
- [`decision.md`](decision.md) — desafios encontrados e o raciocínio por trás de cada decisão importante
- [`data_model.md`](data_model.md) — referência completa do esquema da tabela

## Melhorias Futuras

Ver [`decision.md`](decision.md) §6 para a lista completa. Destaques:

- Retry/backoff para erros de rede transitórios
- Integração do endpoint `/currencies` para metadados de moedas
- Testes de integração contra um container Postgres descartável
- Revalidar a analítica contra dados reais do `/search` assim que o acesso for restabelecido