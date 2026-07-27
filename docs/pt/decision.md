# Decisões Técnicas

Este documento explica as principais decisões de engenharia que tomei
ao longo deste projeto, os desafios que encontrei e como resolvi cada
um. Foi escrito para ser lido como um relatório real de revisão de
arquitetura, não apenas como uma entrega de desafio.

## 1. Restrição de acesso à API (`/search`, `/items`)

### O que aconteceu

No início do desenvolvimento, toda chamada a `GET /sites/MLA/search` e
`GET /items/{id}` retornava `403 Forbidden`, mesmo com um fluxo OAuth
corretamente implementado e um token de acesso válido.

### Investigação

Antes de assumir que era um erro de configuração, investiguei se esse
era o comportamento esperado:

- Confirmei que o token OAuth era válido chamando com sucesso outros
  endpoints autenticados.
- Encontrei uma issue aberta no próprio repositório `golang-restclient`
  do Mercado Livre no GitHub (datada de 1º de abril de 2025) relatando
  o mesmo sintoma exato: `403 Forbidden` em `/sites/{SITE_ID}/search`
  com um token que funciona corretamente em outros endpoints como
  `/users/me`. Não encontrei nenhum changelog oficial, post de blog ou
  anúncio no portal de desenvolvedores do Mercado Livre documentando
  essa restrição — essa issue do GitHub é simplesmente o relato público
  mais antigo que encontrei desse sintoma, não uma data de lançamento
  confirmada.
- Encontrei mais relatos independentes (fóruns de desenvolvedores,
  plataformas públicas de reclamação e repositórios de clientes de API
  de terceiros — incluindo um servidor MCP mantido pela comunidade que
  descontinuou sua própria ferramenta de `search` "devido a mudanças
  nas políticas da API do MercadoLibre") confirmando que o `403` em
  `/search` e `/items` persiste mesmo para desenvolvedores com tokens
  OAuth totalmente válidos e aplicações certificadas, até o prazo final
  deste desafio.

**Conclusão:** a evidência aponta para uma política de acesso
deliberada em nível de plataforma, não um bug na minha implementação —
embora eu queira ser preciso: isso é inferido de relatos de
desenvolvedores, não confirmado por um anúncio oficial do Mercado
Livre. O enunciado do desafio (e boa parte da própria documentação
pública do Mercado Livre) parece ser anterior a essa mudança.

### Decisão

Não gastei mais tempo tentando "resolver" uma restrição de acesso que
está fora do controle da aplicação. Em vez disso:

1. Documentei o erro exato e o resumo da minha investigação nesta
   seção, para comunicar com transparência à recrutadora junto com a
   entrega final (link do repositório e esta apresentação), em vez de
   tratar isso como uma nota escondida.
2. Construí a camada de extração para funcionar corretamente contra a
   API real *se e quando o acesso for restabelecido*, sem exigir
   mudanças de código.
3. Implementei um fallback explícito e transparente para um dataset de
   amostra realista, para poder construir, testar e demonstrar o resto
   do pipeline (transform, load, analítica) de ponta a ponta sem
   depender do acesso externo.

Isso transforma um bloqueio externo em uma demonstração de julgamento
de engenharia: reconhecer um problema que não é meu para resolver,
documentá-lo com precisão, e não deixar que ele impeça a entrega.

## 2. Estratégia de Fallback: Transparente, Não Oculta

Cada linha carregada no banco de dados carrega uma coluna `data_source`
com valor `"live"` ou `"sample"`. Isso significa:

- A distinção entre dados reais e de amostra nunca se perde — é
  consultável no banco de dados, não apenas mencionada em um README.
- Se a API for desbloqueada antes da revisão, o mesmo código
  (`extract_products`, `extract_currency_conversion`) vai popular
  `data_source = "live"` automaticamente, sem mudanças de código.
- Os avaliadores podem verificar isso por conta própria: `SELECT
  DISTINCT data_source FROM etl.products;`

O dataset de amostra (`src/sample_data.py`) não foi gerado
aleatoriamente. Ele segue exatamente o esquema retornado pela API real
(estrutura de resposta de `/search` e `/items`, conforme a
documentação oficial) e eu o construí deliberadamente com variação
realista, para que as consultas analíticas em `sql/` produzam
resultados significativos e não triviais:

- 3 sellers com múltiplas publicações (5, 3 e 2 publicações,
  respectivamente) e 11 sellers com apenas uma publicação.
- Uma distribuição de valores de `sold_quantity` por seller.
- Uma faixa de preços realista em ARS.
- Uma mistura de itens com e sem texto de garantia.
- Os três valores reais de `logistic_type` (`fulfillment`, `drop_off`,
  `cross_docking`).

## 3. `/currency_conversions`: Um Tipo Diferente de Restrição

Diferente do `/search`, chamar `/currency_conversions/search` sem um
token retornou `401 Unauthorized` com a mensagem `"token not
informed"` — não `403 Forbidden`. Esse é um sinal significativamente
diferente: indica que o endpoint simplesmente exige *algum* token
válido, não um autorizado por um usuário vinculado a restrições de
política.

Confirmei isso implementando o fluxo **OAuth Client Credentials**
(`src/auth.py`): um grant leve, apenas de aplicação, que não exige que
um usuário autorize nada em um navegador. Uma vez implementado,
`/currency_conversions/search?from=ARS&to=USD` retornou uma taxa de
câmbio real e ao vivo.

**Resultado:** a conversão de moeda do ETL é totalmente real
(`data_source = "live"`), enquanto as publicações de produtos
continuam sendo dados de amostra (`data_source = "sample"`) por causa
da restrição separada e não resolvível do `/search` descrita acima.
Esse estado híbrido é intencional e está documentado, não é acidental.

## 4. Decisões de Modelagem de Dados

### Chave primária composta `(item_id, job_run)`

O desafio exige um campo `JOB_RUN` do tipo `DATETIME` em cada tabela,
idêntico para todas as linhas de uma mesma execução. Em vez de usar
`item_id` sozinho como chave primária (o que forçaria sobrescrever ou
pular dados a cada nova execução), usei `(item_id, job_run)` como
chave composta.

Isso significa que cada execução do ETL é preservada como uma
"fotografia" independente e consultável — o que é prática padrão em
pipelines ETL do mundo real (idempotente por execução, não por
registro), e permite que cada resposta SQL seja limitada à "última
execução" via:

```sql
WHERE job_run = (SELECT MAX(job_run) FROM etl.products)
```

sem perder o histórico de execuções anteriores.

### `has_warranty` (booleano) + `warranty_description` (texto)

Derivei um campo booleano `has_warranty` a partir do campo de texto
livre de garantia retornado pela API, para que calcular um percentual
de garantia seja um simples `AVG()`/`COUNT() FILTER` em SQL, em vez de
parsing de texto em tempo de consulta. O texto original é preservado
em `warranty_description` para rastreabilidade.

### `price_usd` pré-calculado na transformação

Em vez de armazenar apenas `price_ars` e recalcular o valor em USD em
cada consulta, pré-calculei `price_usd` durante a transformação usando
a taxa de conversão real obtida de `/currency_conversions`. Isso
mantém as consultas SQL simples e garante que cada linha de uma
execução usou exatamente a mesma taxa de câmbio, auditável.

## 5. `sold_quantity` como Proxy de "Vendas"

Calcular uma média de vendas por seller exige alguma noção de volume
de vendas. O campo `sold_quantity` da API do Mercado Livre em
`/search` e `/items` é documentado como **apenas referencial** — não
representa o volume real e atual de transações. Usei-o como o melhor
proxy disponível dado o escopo e as restrições de tempo deste projeto,
e estou sinalizando essa limitação explicitamente aqui e no README, em
vez de apresentá-lo como um número exato de vendas.

Uma solução de nível produtivo consultaria dados reais de pedidos do
recurso autenticado `/orders` (por seller, com a autorização
correspondente), o que ficou fora do escopo dado o tempo disponível e
o fato de que este desafio trata de dados públicos de publicações, não
do histórico privado de pedidos do seller.

## 6. O Que Eu Faria Diferente Com Mais Tempo

- `extract_item()` (em `extract.py`) implementa uma chamada a
  `/items/{id}`, mas o pipeline atual nunca a invoca — os dados de
  produto vêm inteiramente dos resultados de `/search`. Como
  `/search` está bloqueado durante o prazo deste projeto (ver seção
  1), isso nunca foi testado contra a API real, então não posso
  confirmar se campos como `warranty` e `sold_quantity` estão
  realmente presentes nas respostas de `/search` ou só nas respostas
  de detalhe de `/items`. Conectar `extract_item()` ao pipeline (uma
  chamada por publicação, ou um fallback quando um campo estiver
  ausente) fecharia essa lacuna assim que o acesso ao `/search`
  estiver disponível para testar.
- Adicionar uma camada leve de retry/backoff em `api.py` para erros de
  rede transitórios (atualmente só 403/401 têm tratamento especial;
  erros 5xx e timeouts se propagam diretamente).
- Adicionar uma etapa de extração de `/currencies` (o desafio também
  lista como endpoint a ser usado) para validar/exibir metadados de
  moedas suportadas, mesmo não sendo estritamente necessário para
  responder as 5 perguntas.
- Adicionar testes de integração rodando contra um container Postgres
  descartável, além dos testes unitários atuais que fazem mock da
  camada HTTP.
- Assim que o acesso ao `/search` for restabelecido, rodar o pipeline
  novamente em modo "live" e comparar os resultados reais contra os
  baseados em amostra documentados aqui, para validar a lógica
  analítica contra dados reais.