# Skill Foundation: TypeScript Conventions

> Entregável 3 do exercício 2.3 — gerado pelo GitHub Copilot (Agent mode) a partir do prompt-guia. Revisão crítica em `03b-revisao-critica-skill.md`.

- Nível: Foundation
- Slug: typescript-conventions
- Frase-ativação: seguir as convenções TypeScript do projeto
- Consumida por: todas as skills (foundation, domain, artifact) e todos os devs via Copilot

## Contexto
Esta skill define o baseline obrigatório de TypeScript para todo o `novatech-assistant` (RAG de atendimento com Azure Functions v4, Zod e pino). Onde não houver instrução explícita em skill superior, estas convenções prevalecem para reduzir drift entre tipos, manter segurança de `strict: true`, padronizar integração entre camadas e evitar regressões comuns de geração automática de código.

## Regras prescritivas
1. `strict: true` é inegociável: não desativar checagens por arquivo e não usar `@ts-ignore` ou `@ts-nocheck`.
2. `any` é proibido. Em fronteiras externas (HTTP, fila, SDK), usar `unknown` e estreitar com Zod ou type guard explícito.
3. Toda validação de entrada/saída em fronteiras deve usar Zod; o tipo de domínio deve ser inferido com `z.infer<typeof Schema>` e nunca duplicado em interface/type paralelo.
4. Tipos de domínio compartilhados devem viver em `src/shared/types.ts`; não redeclarar localmente em handler, service ou pipeline.
5. Erros devem usar custom errors de `src/shared/errors.ts`; não lançar `throw new Error("...")` para regras de domínio.
6. Para falhas esperadas de fluxo (ex.: chunk não encontrado), preferir retorno por discriminated union; usar `throw` apenas para falhas excepcionais.
7. Imutabilidade por padrão: usar `const` sempre que possível, `readonly` em contratos e coleções imutáveis; `let` somente com reatribuição real.
8. Convenções de nome: tipos e schemas em `PascalCase`, valores/funções em `camelCase`, variáveis de ambiente em `SCREAMING_SNAKE_CASE`; preferir named exports.
9. Não introduzir side effects no top-level de módulo: clientes Azure e integrações externas devem ser criados via factory ou lazy init.
10. Em conflitos de conteúdo entre chunks de políticas/procedimentos, respeitar metadado de vigência (`effectiveDate`) conforme ADR-0003.
11. Logging deve usar pino (nunca `console.log`); detalhes de estratégia de logs pertencem à skill de logging.
12. Regras detalhadas de error handling, endpoint e testes devem ser consultadas nas skills específicas; esta skill define apenas baseline de convenções TypeScript.

## Exemplos DO / DON'T

### 1) Fronteira HTTP com Zod + `z.infer` (QueryRequest)

DO:
```ts
import { z } from "zod";

export const QueryRequestSchema = z.object({
	question: z.string().min(1),
	conversationId: z.string().uuid().optional(),
});

export type QueryRequest = z.infer<typeof QueryRequestSchema>;

export function parseQueryRequest(input: unknown): QueryRequest {
	return QueryRequestSchema.parse(input);
}
```

DON'T:
```ts
import { z } from "zod";

// ERRADO: schema e interface duplicam a mesma entidade (drift futuro).
const QueryRequestSchema = z.object({
	question: z.string(),
	conversationId: z.string().optional(),
});

interface QueryRequest {
	question: string;
	conversationId?: string;
}

// ERRADO: cast cego ignora validação real.
export function parseQueryRequest(input: unknown): QueryRequest {
	return input as any;
}
```

### 2) Falha esperada com discriminated union (chunk não encontrado)

DO:
```ts
import type { Chunk } from "../../shared/types";

export type GetChunkResult =
	| { kind: "found"; chunk: Chunk }
	| { kind: "not_found"; chunkId: string };

export function getChunkById(chunks: readonly Chunk[], chunkId: string): GetChunkResult {
	const chunk = chunks.find((item) => item.id === chunkId);
	if (!chunk) {
		return { kind: "not_found", chunkId };
	}
	return { kind: "found", chunk };
}
```

DON'T:
```ts
import type { Chunk } from "../../shared/types";

export function getChunkById(chunks: Chunk[], chunkId: string): Chunk {
	const chunk = chunks.find((item) => item.id === chunkId);
	if (!chunk) {
		// ERRADO: falha esperada tratada com throw genérico.
		throw new Error("chunk não encontrado");
	}
	return chunk;
}
```

### 3) Tipo compartilhado em `src/shared/types.ts` vs redeclaração local

DO:
```ts
// src/services/search/searchChunks.ts
import type { Chunk } from "../../shared/types";

export async function searchChunks(question: string): Promise<readonly Chunk[]> {
	// Retorna top-5 chunks mais relevantes.
	const top5: Chunk[] = await executeVectorSearch(question, 5);
	return top5;
}

async function executeVectorSearch(_question: string, _top: number): Promise<Chunk[]> {
	return [];
}
```

DON'T:
```ts
// src/services/search/searchChunks.ts
// ERRADO: tipo de domínio redeclarado localmente (pode divergir de src/shared/types.ts).
type Chunk = {
	id: string;
	documentId: string;
	content: string;
	effectiveDate: string;
};

export async function searchChunks(question: string): Promise<Chunk[]> {
	return runSearch(question);
}

async function runSearch(_question: string): Promise<Chunk[]> {
	return [];
}
```

### 4) Side effects, logging e erros customizados

DO:
```ts
import { SearchClient } from "@azure/search-documents";
import { InvalidQueryError } from "../../shared/errors";
import { logger } from "../../shared/logger";

let cachedClient: SearchClient<unknown> | undefined;

function getSearchClient(): SearchClient<unknown> {
	if (!cachedClient) {
		const endpoint = process.env.AZURE_SEARCH_ENDPOINT;
		const indexName = process.env.AZURE_SEARCH_INDEX_NAME;
		if (!endpoint || !indexName) {
			throw new InvalidQueryError("Configuração de busca ausente");
		}
		cachedClient = new SearchClient(endpoint, indexName, {} as never);
	}
	return cachedClient;
}

export async function runSearch(question: string): Promise<void> {
	logger.info({ question }, "Executando busca");
	const client = getSearchClient();
	void client;
}
```

DON'T:
```ts
import { SearchClient } from "@azure/search-documents";

// ERRADO: side effect no top-level.
const client = new SearchClient(
	process.env.AZURE_SEARCH_ENDPOINT as string,
	process.env.AZURE_SEARCH_INDEX_NAME as string,
	{} as never,
);

export async function runSearch(question: string): Promise<void> {
	// ERRADO: logging fora do padrão do projeto.
	console.log("Executando busca", question);

	if (!question) {
		// ERRADO: erro genérico em vez de custom error.
		throw new Error("question obrigatória");
	}

	void client;
}
```

## Anti-padrões
- Usar `as any` ou cast cego para "fazer o strict passar" sem validação real.
- Definir schema Zod e também interface/type manual para a mesma entidade (`QueryRequest`, `Chunk`), criando drift.
- Declarar tipo de domínio dentro de handler/service em vez de importar de `src/shared/types.ts`.
- Usar `console.log` para debug em fluxo de produção, ignorando pino.
- Instanciar cliente Azure no top-level do módulo, gerando side effect e dificultando teste/configuração.
- Introduzir `@ts-ignore` para contornar erro de modelagem em vez de corrigir contrato/tipo.