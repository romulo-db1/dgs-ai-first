# Revisão Crítica — `typescript-conventions.md`

## Veredito geral

Aprovado com ajustes menores. O arquivo é concreto e prescritivo; os exemplos são TypeScript real e do domínio correto (`QueryRequest`, `Chunk` com `effectiveDate`, top-5); os anti-padrões refletem erros que o Copilot de fato comete. Os quatro pares DO/DON'T superam o mínimo (3). A fronteira com `error-handling` / `logging` / `testing` está demarcada (regras 11-12). Os dois P1 abaixo deveriam ser corrigidos antes do merge.

## Achados

| # | Severidade | Item | Ação proposta |
|---|-----------|------|---------------|
| 1 | P1 | Indentação com tabs em todos os exemplos; uma Foundation deveria fixar a convenção de formatação (Prettier/ESLint), e os exemplos servem de referência visual | Alinhar à config real do repo + adicionar regra explícita sobre formatação delegada ao Prettier |
| 2 | P1 | `{} as never` aparece num bloco **DO** (seção 4), contradizendo a regra 2 e o 1º anti-padrão (cast cego proibido) | Usar credencial real (`new DefaultAzureCredential()`) ou abstrair atrás de parâmetro tipado |
| 3 | P2 | `SearchClient<unknown>` reforça sensação de tipagem frouxa justamente no exemplo modelo | Tipar o documento do índice (ex.: `SearchClient<Chunk>`) |
| 4 | P2 | Regra 10 (`effectiveDate` / ADR-0003) é regra de domínio, não convenção de TypeScript; mistura níveis numa Foundation | Mover para `rag-prompt-assembly` / `azure-ai-search-integration`; manter aqui só como nota de que o campo existe no tipo `Chunk` |
| 5 | Advisory | Stubs (`executeVectorSearch`, `runSearch` retornando `[]`) sem marcação podem ser copiados como padrão | Adicionar comentário `// stub para exemplo` |

## Prioridade de correção

Os dois P1 são bloqueantes para o merge — em especial o `{} as never`: uma skill que proíbe cast cego e depois usa um no exemplo modelo perde autoridade. Os P2 e o advisory podem entrar num ajuste de follow-up.