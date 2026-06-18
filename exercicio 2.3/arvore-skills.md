# Entregável 1 — Árvore de Skills do Projeto

> Exercício 2.3 — Definição de estratégia de skills do `novatech-assistant`.
> Hierarquia Foundation → Domain → Artifact, conforme Anexo C.

## Restrições que toda skill deve respeitar

Decisões herdadas do cenário 1 e do exercício 2.2 que governam todas as skills:

- TypeScript `strict: true` + Azure Functions v4.
- Validação de input/output com Zod (tipo de domínio inferido com `z.infer`).
- Logging estruturado com pino.
- Custom errors em `src/shared/errors.ts`.
- Tipos de domínio compartilhados em `src/shared/types.ts`.
- Context budget da ADR-0002 (~4K system + ~8K chunks, top-5 de ~1.500 tokens).
- Contraditórios resolvidos por metadado de vigência — `effectiveDate` (ADR-0003).
- System prompt versionado em `/prompts/`.

## Árvore

```
skills/
├── foundation/        # convenções globais — base de TUDO
│   ├── typescript-conventions.md   ★ (a mais importante)
│   ├── error-handling.md
│   ├── logging.md
│   ├── env-config.md
│   └── project-structure.md
│
├── domain/            # padrões por camada
│   ├── azure-functions-endpoint.md
│   ├── azure-ai-search-integration.md
│   ├── rag-prompt-assembly.md
│   ├── testing-patterns.md
│   └── react-components.md
│
└── artifact/          # receitas de geração end-to-end
    ├── create-rag-endpoint.md
    ├── create-integration-test.md
    ├── create-react-card.md
    ├── create-adr.md
    └── create-product-spec.md
```

## Rationale por nível

### Foundation — convenções globais
Invariantes que qualquer artefato herda. Sem elas, cada skill superior repetiria as mesmas regras.

- **`typescript-conventions`** ★ — raiz da árvore. `error-handling`, `logging` e todo endpoint dependem das suas decisões de tipagem (strict, sem `any`, discriminated unions, tipos em `shared/types.ts`).
- **`error-handling`** — uso uniforme dos custom errors de `src/shared/errors.ts`.
- **`logging`** — padrão pino (campos, níveis, correlação de request).
- **`env-config`** — leitura tipada e validada de variáveis de ambiente.
- **`project-structure`** — onde cada arquivo vive (convenção Anexo C), o que vai em `shared/`.

### Domain — padrões por camada
Encapsula o "como esta camada é feita aqui".

- **`azure-functions-endpoint`** — estrutura de um HTTP trigger v4 (handler/validator/response-builder), status codes corretos (lição do 404/405 do T1).
- **`azure-ai-search-integration`** — como buscar chunks (top-5), tipagem do índice.
- **`rag-prompt-assembly`** — montagem do prompt respeitando o context budget (ADR-0002) e a regra de vigência (ADR-0003). Skill própria porque essa lógica é reusada por todo endpoint RAG, não só pelo query endpoint.
- **`testing-patterns`** — organização unit/integration/e2e, uso de mocks (msw), fixtures.
- **`react-components`** — organização e padrões dos componentes do painel web.

### Artifact — receitas de geração end-to-end
Compõem Foundation + Domain num output pronto. Cada uma corresponde direto a um item da lista de artefatos repetitivos do exercício; nenhuma é supérflua.

- **`create-rag-endpoint`** — gera um endpoint RAG completo (endpoints Azure Functions com padrão RAG).
- **`create-integration-test`** — gera teste de integração para endpoint (mesmo padrão para todos).
- **`create-react-card`** — gera card de resposta/feedback no painel (componentes React).
- **`create-adr`** — gera um ADR no template do projeto (documentação técnica).
- **`create-product-spec`** — gera spec de produto no template SDD (specs de produto).