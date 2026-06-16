# Histórico da conversa (transcrição literal)

Data: 2026-06-16

## Mensagens

### Usuário
Query endpoint — HTTP trigger (Task T1).
Stack: TypeScript strict, Azure Functions v4 (@azure/functions), Zod.

Requisitos:
- Registrar uma function HTTP via `app.http(...)` com:
- methods: ['POST'] apenas (método != POST deve resultar em 405).
- authLevel: 'function'.
- route: 'query'  (resolve para POST /api/query).
- O handler tem assinatura `(request: HttpRequest, context: InvocationContext): Promise<HttpResponseInit>`.
NÃO usar `any` no retorno.
- Fluxo do handler:
1. Ler o corpo como JSON: `const body = await request.json()` (tratar JSON inválido → 400).
2. Validar com `parseQueryInput(body)` do ./validator.
3. Se inválido: retornar status 400 com jsonBody { error: 'Invalid request body', issues: <ZodIssue[]> }.
4. Se válido: retornar status 200 com jsonBody STUB { answer: null, source_document: null, chunks_used: [] }(os serviços de busca/completion são tasks futuras T2–T5 — NÃO implementar aqui).
 - Não usar console.log (logging estruturado vem na T6); por ora, usar context.log apenas se necessário.

Não implementar: embedding, Azure AI Search, GPT-4o, prompt builder.
Esta task é só o setup do endpoint + validação de input.

Gere o conteúdo completo deste arquivo seguindo a especificação acima

### Assistente
Conteúdo completo gerado em [novatech-assistant/src/functions/query/handler.ts](novatech-assistant/src/functions/query/handler.ts):

~~~ts
import {
  app,
  HttpRequest,
  HttpResponseInit,
  InvocationContext,
} from "@azure/functions";
import { parseQueryInput } from "./validator";

type QueryStubResponse = {
  answer: null;
  source_document: null;
  chunks_used: [];
};

export async function queryHandler(
  request: HttpRequest,
  _context: InvocationContext,
): Promise<HttpResponseInit> {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return {
      status: 400,
      jsonBody: {
        error: "Invalid JSON body",
      },
    };
  }

  const parsed = parseQueryInput(body);

  if (!parsed.success) {
    return {
      status: 400,
      jsonBody: {
        error: "Invalid request body",
        issues: parsed.issues,
      },
    };
  }

  const response: QueryStubResponse = {
    answer: null,
    source_document: null,
    chunks_used: [],
  };

  return {
    status: 200,
    jsonBody: response,
  };
}

app.http("query", {
  methods: ["POST"],
  authLevel: "function",
  route: "query",
  handler: queryHandler,
});
~~~

Observação de verificação local: há um diagnóstico no ambiente indicando que o módulo @azure/functions não foi resolvido ([novatech-assistant/src/functions/query/handler.ts#L6](novatech-assistant/src/functions/query/handler.ts#L6)). Isso normalmente é dependência ainda não instalada ou tipos não restaurados no workspace.
