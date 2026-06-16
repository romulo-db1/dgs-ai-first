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
