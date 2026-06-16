# Histórico da conversa (transcrição literal)

Data: 2026-06-16

## Mensagens

### Usuário
Query endpoint — input validation (Task T1).
Stack: TypeScript strict, Azure Functions v4, Zod.

Requisitos:
- Exportar um schema Zod `querySchema` que valida o corpo da requisição.
- Campo obrigatório: `question` (string).
- non-empty (min 1, após trim)
- tamanho máximo de 2000 caracteres
- Usar `.strict()` para rejeitar campos não esperados no corpo.
- Exportar o tipo inferido: `export type QueryInput = z.infer<typeof querySchema>`.
- Exportar uma função `parseQueryInput(body: unknown)` que retorna um discriminated union: { success: true; data: QueryInput } | { success: false; issues: z.ZodIssue[] }.
NÃO lançar exceção — usar `safeParse`.


Gere o conteúdo completo deste arquivo seguindo a especificação acima

### Assistente
Conteúdo completo gerado em [src/functions/query/validator.ts](src/functions/query/validator.ts) com:

- `querySchema` em Zod
- `question` obrigatório com:
	- `trim()`
	- `min(1)` após trim
	- `max(2000)`
- `.strict()` para rejeitar campos extras
- `export type QueryInput = z.infer<typeof querySchema>`
- `parseQueryInput(body: unknown)` usando `safeParse` e retornando união discriminada sem lançar exceção

Observação de validação local:
- Existe um erro de compilação em [src/functions/query/validator.ts#L1](src/functions/query/validator.ts#L1): módulo `zod` não encontrado no ambiente atual (dependência aparentemente ausente no projeto).
