# Tasks — Query Endpoint

> Derivado de `specs/query-endpoint/plan.md`. Decisões herdadas: ADR-0002 (context budget ~4K system + ~8K chunks, top-5 de ~1.500 tokens), ADR-0003 (documentos contraditórios via metadado de vigência), stack TypeScript + Azure Functions v4 + Zod + pino. Organização de diretórios conforme Anexo C (`src/functions/query/`, `src/services/`).
>
> Estimativas: **P** (≤ meio dia) · **M** (~1 dia) · **G** (> 1 dia).

---

## T1 — Setup do endpoint HTTP com validação de input

**Descrição:** Criar o HTTP trigger `POST /api/query` em Azure Functions v4 (`src/functions/query/handler.ts`) e o schema de validação de input em `src/functions/query/validator.ts` usando Zod. O endpoint recebe a pergunta do atendente, valida o corpo da requisição e retorna estrutura de resposta provisória (stub) enquanto os serviços de busca e completon não existem.

**Critérios de aceite:**
- `POST /api/query` com corpo `{ "question": "Qual o prazo de devolução?" }` retorna HTTP 200.
- Corpo sem o campo `question` retorna HTTP 400 com payload `{ "error": "...", "issues": [...] }` derivado do `ZodError`.
- `question` vazia (`""`) ou com mais de 2.000 caracteres retorna HTTP 400.
- Campos não esperados no corpo são rejeitados ou ignorados de forma explícita (schema com `.strict()` ou `.passthrough()` documentado).
- Método diferente de POST retorna HTTP 405.
- O handler retorna `HttpResponseInit` tipado (contrato Azure Functions v4), não `any`.

**Dependências:** nenhuma.
**Estimativa:** P.

---

## T2 — Serviço de embedding da pergunta (Azure OpenAI)

**Descrição:** Implementar `src/services/completion.ts` (ou módulo dedicado) que converte a pergunta validada em embedding via Azure OpenAI, com retry e exponential backoff para falhas transitórias.

**Critérios de aceite:**
- Função recebe `string` e retorna `number[]` (vetor de embedding) ou erro tipado.
- Retry com no mínimo 3 tentativas e backoff exponencial em erros 429/5xx; erros 4xx (exceto 429) não são repetidos.
- Configuração (endpoint, deployment, API version) lida de `src/shared/config.ts`, nunca hardcoded.
- Teste unitário com mock da chamada Azure cobre: sucesso, retry após 429, e falha definitiva.

**Dependências:** T1.
**Estimativa:** M.

---

## T3 — Serviço de busca top-5 no Azure AI Search

**Descrição:** Implementar `src/services/search.ts` que recebe o embedding e recupera os top-5 chunks por similaridade no Azure AI Search, retornando o conteúdo e os metadados (incluindo vigência, conforme ADR-0003).

**Critérios de aceite:**
- Função recebe `number[]` e retorna lista de no máximo 5 chunks, cada um com `content`, `source_document` e `metadata` (incl. campo de vigência).
- Quando a busca não retorna resultados, devolve lista vazia sem lançar exceção.
- Retry/backoff aplicado a falhas transitórias do Azure AI Search.
- Teste unitário com mock cobre: 5 resultados, 0 resultados, e erro do serviço.

**Dependências:** T1.
**Estimativa:** M.

---

## T4 — Prompt builder com context budget

**Descrição:** Implementar `src/services/prompt-builder.ts` que monta o prompt final combinando system prompt (`/prompts/system-prompt.md`), os chunks recuperados e a pergunta, respeitando o context budget da ADR-0002.

**Critérios de aceite:**
- System prompt carregado de `/prompts/system-prompt.md` (não duplicado em código).
- Total de tokens dos chunks truncado para não exceder ~8K; system prompt ~4K. O builder rejeita ou trunca de forma determinística quando o orçamento estoura, registrando em log.
- Em caso de chunks de versões contraditórias (ADR-0003), o de vigência mais recente é priorizado na ordem do contexto.
- Teste unitário verifica: montagem dentro do orçamento, truncamento quando excede, e priorização por vigência.

**Dependências:** T2, T3.
**Estimativa:** M.

---

## T5 — Chamada ao GPT-4o e resposta com source_document

**Descrição:** Implementar a chamada de completion ao GPT-4o em `src/services/completion.ts` e a montagem da resposta final em `src/functions/query/response-builder.ts`, incluindo o(s) documento(s) de origem.

**Critérios de aceite:**
- Resposta HTTP 200 com payload `{ "answer": "...", "source_document": "...", "chunks_used": [...] }`.
- Quando nenhum chunk relevante é recuperado, a resposta indica explicitamente ausência de fonte (não inventa resposta).
- Retry/backoff aplicado à chamada de completion.
- Teste de integração (com mocks) cobre o fluxo completo: pergunta → embedding → busca → prompt → resposta.

**Dependências:** T4.
**Estimativa:** M.

---

## T6 — Logging estruturado e tratamento de erros transversal

**Descrição:** Configurar `src/shared/logger.ts` (pino) e padronizar o tratamento de erros em todo o fluxo do endpoint, usando os custom errors de `src/shared/errors.ts`.

**Critérios de aceite:**
- Toda requisição gera log estruturado com `correlationId`, latência e status final.
- Erros de validação, de serviços externos e inesperados são mapeados para códigos HTTP e mensagens distintas.
- Nenhum `console.log` no código de produção.
- Dados sensíveis (pergunta completa, conteúdo de chunks) não são logados em nível `info` por padrão.

**Dependências:** T1.
**Estimativa:** P.

---

## Ordem de execução sugerida

T1 → (T2 ∥ T3 ∥ T6) → T4 → T5

A primeira task a implementar é a **T1**.