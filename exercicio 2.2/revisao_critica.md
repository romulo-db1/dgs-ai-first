# Revisão Crítica — Task T1 (Query Endpoint)

> Revisão do código gerado com o GitHub Copilot para a Task T1 (setup do endpoint `POST /api/query` + validação de input).
> Arquivos revisados: `src/functions/query/validator.ts`, `src/functions/query/handler.ts`.
> Objetivo: identificar ajustes necessários antes de um code review real, separando defeitos de código de ruído de ambiente.

---

## Avaliação geral

O código gerado é funcional e fiel à especificação da T1. Atende corretamente:

- Tratamento de JSON malformado com `try/catch`, retornando 400 em vez de deixar estourar 500.
- Retorno `HttpResponseInit` tipado, sem uso de `any`.
- União discriminada no `parseQueryInput` usando `safeParse`, sem lançar exceção.
- Validação Zod com `trim()`, `min(1)`, `max(2000)` e `.strict()` para rejeitar campos extras.
- Escopo respeitado: não implementa embedding, busca, prompt builder nem GPT-4o (tasks T2–T5).

Os pontos abaixo são os ajustes recomendados antes da aprovação.

---

## Ruído de ambiente (não são defeitos de código)

Os diagnósticos de módulo não resolvido em `validator.ts` (`zod`) e `handler.ts` (`@azure/functions`) são **dependências não instaladas no workspace**, não defeitos do código. Os imports estão corretos. Resolução:

```
npm install zod @azure/functions
```

Ambos os pacotes já trazem suas declarações de tipo (`.d.ts`), dispensando `@types/*`. Estes itens não contam como achados de revisão.

---

## Achados de revisão

### Achado 1 (P0) — O critério de aceite do 405 não é satisfeito

**Onde:** `handler.ts`, registro `app.http(...)`.

**Problema:** O critério de aceite da T1 exige que "método diferente de POST retorne HTTP 405". Com `methods: ["POST"]`, o Azure Functions v4 **não** devolve 405 para um GET em `/api/query` — a rota simplesmente não casa e o runtime responde **404**. O comportamento gerado diverge do critério de aceite, ainda que de forma silenciosa.

**Ações possíveis (decisão consciente necessária):**
- **Opção A:** registrar os demais métodos e tratá-los explicitamente no handler, retornando 405 com `Allow: POST`.
- **Opção B:** aceitar o 404 como comportamento padrão do runtime e **ajustar o critério de aceite** no `tasks.md` para refletir isso.

Qualquer das duas é defensável, mas a escolha deve ser registrada — não pode ficar implícita. Em um code review real, este seria um comentário bloqueante.

### Achado 2 (P1) — Contrato de resposta deveria viver em `shared/types.ts`

**Onde:** `handler.ts`, tipo `QueryStubResponse`.

**Problema:** O tipo do stub fixa `answer: null`, `source_document: null` e `chunks_used: []` como tipos literais, local ao handler. Está correto para o stub, mas quando a T5 preencher a resposta de verdade, esse tipo será descartado e reescrito, gerando retrabalho duas tasks à frente.

**Sugestão:** definir o contrato de resposta em `src/shared/types.ts` (arquivo já previsto no Anexo C) como, por exemplo, `QueryResponse` com campos anuláveis/opcionais, e tratar o stub como uma instância desse contrato. Assim T5 apenas preenche os campos, sem alterar a forma.

### Achado 3 (P2) — Formato do erro de campo extra não está alinhado com os consumidores

**Onde:** `validator.ts` (`.strict()`) e `handler.ts` (repasse de `issues`).

**Problema:** O `.strict()` rejeita campos não esperados (comportamento correto), mas o `ZodIssue` de `unrecognized_keys` é repassado cru no array `issues`. Como o endpoint atende dois consumidores (bot do Teams e painel web), vale confirmar se ambos conseguem interpretar esse formato de erro.

**Sugestão:** não é defeito, é dívida de contrato. Alinhar com quem consome a API se o payload de erro (`{ error, issues }`) atende, ou se é necessário um formato mais amigável/normalizado.

### Achado 4 (P2) — Logging ausente e `context` descartado (dívida esperada)

**Onde:** `handler.ts`, parâmetro `_context`.

**Problema:** O handler ignora o `InvocationContext`. Está correto para a T1, pois logging estruturado é a T6. O ponto é não tratar isto como "concluído" — é uma dependência futura explícita (T6), não um esquecimento. Registrar para garantir que a T6 cubra correlação de requisição, latência e status.

---

## Os dois ajustes prioritários antes da aprovação

1. **Achado 1 (405 vs 404):** decidir entre implementar o 405 ou ajustar o critério de aceite — e registrar a decisão.
2. **Achado 2 (contrato em `shared/types.ts`):** mover a forma da resposta para o tipo compartilhado, evitando retrabalho na T5.

Os achados 3 e 4 são dívidas conhecidas, encaminháveis sem bloquear o merge da T1.