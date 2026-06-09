# Anexo C — Estrutura do Repositório NovaTech Assistant

> **Nota para o participante:** A estrutura abaixo representa o repositório `db1/novatech-assistant` no início da fase de estruturação. O repositório foi criado pelo Tech Lead com a estrutura base. As pastas existem, mas a maioria dos arquivos ainda precisa ser criada — essa é a tarefa desta fase.

---

## Estrutura de diretórios

```
db1/novatech-assistant/
│
├── AGENTS.md                          # Constitution do projeto (a ser escrito nesta fase)
├── README.md                          # Visão geral do projeto
├── package.json                       # Dependências do projeto (TypeScript, Azure Functions)
├── tsconfig.json                      # Configuração TypeScript (strict: true)
├── vitest.config.ts                   # Configuração de testes
├── .github/
│   └── workflows/
│       ├── ci.yml                     # Pipeline de CI (lint, test, build)
│       └── cd.yml                     # Pipeline de CD (deploy para staging/produção)
│
├── .mcp/
│   └── mcp.json                       # Configuração dos MCP servers do projeto (a ser criado)
│
├── docs/
│   ├── adr/                           # Architecture Decision Records
│   │   └── template.md                # Template para novos ADRs
│   ├── runbooks/                      # Runbooks operacionais
│   └── onboarding.md                  # Guia de onboarding para novos membros
│
├── specs/                             # Specs SDD (requirements, plans, tasks)
│   ├── pipeline-ingestao/
│   │   ├── requirements.md            # (a ser escrito pelo Product Specialist)
│   │   ├── plan.md                    # (a ser escrito pelo Tech Lead)
│   │   └── tasks.md                   # (a ser gerado pelo Dev com apoio de IA)
│   ├── query-endpoint/
│   │   ├── requirements.md
│   │   ├── plan.md
│   │   └── tasks.md
│   ├── feedback-api/
│   │   ├── requirements.md
│   │   ├── plan.md
│   │   └── tasks.md
│   ├── teams-bot/
│   │   ├── requirements.md
│   │   ├── plan.md
│   │   └── tasks.md
│   └── painel-web/
│       ├── requirements.md
│       ├── plan.md
│       └── tasks.md
│
├── prompts/                           # System prompts versionados
│   ├── system-prompt.md               # Prompt principal do assistente (versionado aqui)
│   ├── prompt-changelog.md            # Registro de mudanças no prompt
│   └── eval/                          # Dados para avaliação de prompts
│       ├── golden-queries.json        # Perguntas de referência + respostas esperadas
│       └── eval-results/              # Resultados das rodadas de avaliação
│
├── skills/                            # Skills do projeto (hierarquia Foundation → Domain → Artifact)
│   ├── foundation/
│   │   ├── typescript-conventions.md
│   │   ├── error-handling.md
│   │   └── project-structure.md
│   ├── domain/
│   │   ├── azure-functions-endpoint.md
│   │   ├── azure-ai-search-integration.md
│   │   ├── react-components.md
│   │   └── testing-patterns.md
│   └── artifact/
│       ├── create-rag-endpoint.md
│       ├── create-integration-test.md
│       └── create-react-card.md
│
├── src/                               # Código-fonte
│   ├── functions/                     # Azure Functions (endpoints)
│   │   ├── query/
│   │   │   ├── handler.ts             # HTTP trigger do query endpoint
│   │   │   ├── validator.ts           # Validação de input (Zod)
│   │   │   └── response-builder.ts    # Montagem da resposta com fonte
│   │   ├── feedback/
│   │   │   ├── handler.ts
│   │   │   └── validator.ts
│   │   └── health/
│   │       └── handler.ts             # Health check endpoint
│   │
│   ├── services/                      # Lógica de negócio
│   │   ├── search.ts                  # Integração com Azure AI Search
│   │   ├── completion.ts              # Integração com Azure OpenAI
│   │   ├── prompt-builder.ts          # Montagem do prompt com chunks + system prompt
│   │   └── response-validator.ts      # Validação determinística de respostas (harness)
│   │
│   ├── pipeline/                      # Pipeline de ingestão de documentos
│   │   ├── extractor.ts               # Extração de texto de PDFs/DOCX/HTML
│   │   ├── chunker.ts                 # Divisão em chunks com overlap
│   │   ├── embedder.ts                # Geração de embeddings
│   │   └── indexer.ts                 # Indexação no Azure AI Search
│   │
│   ├── bot/                           # Bot do Teams
│   │   ├── bot.ts                     # Lógica principal do bot
│   │   └── cards/                     # Adaptive Cards para respostas no Teams
│   │       ├── response-card.ts
│   │       └── feedback-card.ts
│   │
│   ├── web/                           # Painel web (React)
│   │   ├── src/
│   │   │   ├── components/
│   │   │   ├── pages/
│   │   │   └── App.tsx
│   │   └── package.json
│   │
│   └── shared/                        # Código compartilhado
│       ├── types.ts                   # Tipos TypeScript do domínio
│       ├── config.ts                  # Configuração de ambiente
│       ├── logger.ts                  # Logger (pino)
│       └── errors.ts                  # Custom errors
│
├── tests/                             # Testes
│   ├── unit/                          # Testes unitários
│   ├── integration/                   # Testes de integração
│   ├── e2e/                           # Testes end-to-end
│   └── fixtures/                      # Dados de teste compartilhados
│       ├── chunks.ts                  # Chunks simulados para testes
│       ├── queries.ts                 # Perguntas de teste
│       └── expected-responses.ts      # Respostas esperadas
│
└── infra/                             # Infraestrutura como código
    ├── main.bicep                     # Definição principal (Azure)
    ├── modules/
    │   ├── ai-search.bicep
    │   ├── openai.bicep
    │   ├── functions.bicep
    │   └── cosmos.bicep
    └── parameters/
        ├── dev.bicepparam
        ├── staging.bicepparam
        └── prod.bicepparam
```

---

## Convenções de organização

### Specs (`/specs/`)
Cada módulo do projeto tem sua própria pasta com os 3 artefatos SDD:
- `requirements.md` — escrito pelo Product Specialist, aprovado pelo Tech Lead
- `plan.md` — escrito pelo Tech Lead, aprovado pelo Product Specialist e Dev Sênior
- `tasks.md` — gerado pelo Dev com apoio do Copilot, aprovado pelo Tech Lead

Nomenclatura: o nome da pasta é o slug do módulo (ex: `query-endpoint`, `pipeline-ingestao`).

### Skills (`/skills/`)
Organizadas em 3 níveis seguindo a hierarquia Foundation → Domain → Artifact. Cada skill é um arquivo `.md` independente. O nome do arquivo é o slug da skill (ex: `error-handling.md`).

### Prompts (`/prompts/`)
O system prompt principal vive em `/prompts/system-prompt.md` e é versionado via Git. Toda mudança no prompt deve ser registrada em `/prompts/prompt-changelog.md` com: data, autor, motivo da mudança, e resultado esperado.

### ADRs (`/docs/adr/`)
Nomenclatura: `NNNN-titulo-da-decisao.md` (ex: `0001-escolha-azure-openai.md`). Formato: Contexto, Decisão, Consequências, Alternativas Consideradas.

### Testes (`/tests/`)
- `unit/` — testes que não fazem chamadas externas (mocks para tudo)
- `integration/` — testes que usam mocks para APIs externas (msw) mas testam integração entre módulos internos
- `e2e/` — testes que exercitam o fluxo completo (usados com cautela — consomem tokens)
- `fixtures/` — dados compartilhados entre testes (chunks, queries, respostas esperadas)

---

## Estado atual do repositório (início da fase de estruturação)

| Artefato | Status |
|----------|--------|
| AGENTS.md | Vazio (a ser escrito) |
| Specs (5 módulos) | Pastas criadas, arquivos vazios |
| Skills | Pastas criadas, arquivos vazios |
| System prompt | Versão 1 básica do cenário 1 (a ser evoluída) |
| MCP config | Não criado |
| Código-fonte | Scaffold básico (Azure Functions configurado, nenhuma lógica implementada) |
| Testes | Nenhum |
| Infraestrutura | Bicep com recursos provisionados em dev (AI Search, OpenAI, Functions, Cosmos) |
| CI/CD | Pipeline básico (lint + build) |

---

## Exemplo mínimo de configuração MCP (`.mcp/mcp.json`)

> Para referência nos exercícios que pedem configuração de MCP servers. Este é o formato esperado — o participante deve completar com os servers necessários.

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./src", "./specs", "./skills"]
    }
  }
}
```

**Nota:** O exemplo acima mostra apenas 2 servers (GitHub e filesystem). O projeto NovaTech precisa de servers adicionais para Azure AI Search, Azure OpenAI, Azure DevOps e Confluence. O participante deve mapear e configurar os que faltam.
