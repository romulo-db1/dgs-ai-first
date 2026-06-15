# Exercício 2.1 — Item 2: `.mcp/mcp.json` final e justificativa de least privilege

**Projeto:** NovaTech Assistant
**Autor:** Rômulo — DB1
**Data:** 15/06/2026

## Configuração canônica do projeto — `.mcp/mcp.json`

Formato do projeto (Anexo C), com a chave `mcpServers`:

```json
{
  "mcpServers": {
    "fs-workspace": {
      "command": "npx",
      "args": [
        "-y", "@modelcontextprotocol/server-filesystem",
        "./src", "./specs", "./skills"
      ]
    },
    "fs-knowledge": {
      "command": "npx",
      "args": [
        "-y", "@modelcontextprotocol/server-filesystem",
        "./docs/novatech", "./data/retrieval-corpus"
      ]
    },
    "git": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "."]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": { "MEMORY_FILE_PATH": "./data/memory/memory.json" }
    }
  }
}
```

## Cópia para execução no VS Code — `.vscode/mcp.json`

O VS Code usa a chave `servers` (não `mcpServers`) e exige o campo `type: "stdio"` para servers locais. Esta cópia é a que o Copilot lê em agent mode:

```json
{
  "servers": {
    "fs-workspace": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem",
               "${workspaceFolder}/src", "${workspaceFolder}/specs", "${workspaceFolder}/skills"]
    },
    "fs-knowledge": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem",
               "${workspaceFolder}/docs/novatech", "${workspaceFolder}/data/retrieval-corpus"]
    },
    "git": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "${workspaceFolder}"]
    },
    "memory": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": { "MEMORY_FILE_PATH": "${workspaceFolder}/data/memory/memory.json" }
    }
  }
}
```

## Justificativa de escopo mínimo (least privilege), por server

**`fs-workspace` → só `./src ./specs ./skills`.** São as únicas pastas que o agente legitimamente edita. Deixar a raiz do repositório de fora é deliberado: evita expor `.env`, `.git/` e principalmente `infra/parameters/*.bicepparam`, que costumam carregar parâmetros e segredos de ambiente.

**`fs-knowledge` separada e somente-leitura → `./docs/novatech ./data/retrieval-corpus`.** São fonte de verdade do domínio; o agente nunca deve alterá-las. Como o filesystem server via `npx` concede escrita a toda pasta passada como argumento (não existe flag de read-only na invocação), o read-only de fato é garantido em nível de sistema operacional:

```bash
# macOS/Linux — remove permissão de escrita das fontes de verdade
chmod -R a-w docs/novatech data/retrieval-corpus

# reverter quando precisar atualizar o corpus:
# chmod -R u+w docs/novatech data/retrieval-corpus
```

No Windows, remove-se a permissão de escrita via aba Segurança / `icacls`. Alternativa equivalente: rodar essa instância pela imagem Docker do filesystem com mount `ro` (read-only no nível do SO). A separação em duas instâncias é o que viabiliza isso: `fs-workspace` continua read-write, `fs-knowledge` fica imutável.

**`git` escopado ao repositório `.`, sem credenciais.** A necessidade é histórico/branches (leitura). Fica registrado que o server também expõe operações de escrita (commit/checkout); como não há flag read-only, a mitigação é processual — gate de revisão/PR antes de qualquer commit do agente (ver Item 4).

**`memory` com `MEMORY_FILE_PATH` explícito.** Evita persistir o grafo num local default desconhecido; aponta para `./data/memory/`, mantendo a memória auditável, versionável e fora de pastas sensíveis.

**`everything` ausente.** Por *least privilege*, não é carregado no ambiente operacional — não atende a nenhuma necessidade real do projeto.

> Nota de manutenção: os nomes de pacote e comandos (`@modelcontextprotocol/server-...`, `mcp-server-git`) evoluem. Confirmar contra o README oficial de `modelcontextprotocol/servers` antes de configurar, conforme orienta o Anexo C.
