# Exercício 2.1 — Item 1: Mapeamento de necessidades → MCP servers

**Projeto:** NovaTech Assistant
**Autor:** Rômulo — DB1
**Data:** 15/06/2026

## Objetivo

Mapear cada necessidade de acesso do projeto para um *reference server* MCP gratuito e local (`filesystem`, `git`, `memory`, `everything`), definindo, para cada um: o que ele expõe (tools / resources / prompts), quem consome e qual escopo de pasta recebe.

## Mapeamento

| Necessidade do projeto | Server | O que expõe | Quem consome | Escopo / pasta |
|---|---|---|---|---|
| Código, specs e skills (ler **e escrever**) | `fs-workspace` (filesystem) | Tools de leitura **e escrita** (`read_text_file`, `write_file`, `edit_file`, `list_directory`, `search_files`) | Dev e Tech Lead via Copilot / Claude Code | `./src ./specs ./skills` |
| Documentação de negócio da NovaTech (ler) | `fs-knowledge` (filesystem) | Tools de leitura (`read_text_file`, `search_files`, `list_directory`) | Assistente / agentes que precisam de contexto de domínio (guardrails, glossário) | `./docs/novatech` |
| Corpus de chunks para "recuperação" (ler) | `fs-knowledge` (mesma instância) | idem | "Recuperação" de chunk por pergunta do domínio | `./data/retrieval-corpus` |
| Histórico / branches do repositório | `git` | Tools (`git_log`, `git_status`, `git_diff`, `git_show`, branches) | Dev e Tech Lead | repositório `.` |
| Memória persistente (decisões, linguagem ubíqua) | `memory` | Tools de grafo (`create_entities`, `create_relations`, `read_graph`, `search_nodes`) | Todos os papéis | grafo em `./data/memory` |
| *(Explorar primitivas de MCP — aprendizado)* | `everything` | Tools **+ resources + prompts** (server de demonstração das três primitivas) | Time, em fase de aprendizado | — |

## Decisões de design

**Duas instâncias de filesystem.** O acesso de leitura/escrita (`fs-workspace`) é separado do acesso de leitura às fontes de verdade (`fs-knowledge`). Essa separação é o que torna possível tratar a documentação e o corpus como somente-leitura de fato — a justificativa e o mecanismo de enforcement estão no Item 2.

**`everything` fora da config operacional.** O server `everything` é apenas didático (demonstra tools, resources e prompts) e não atende a nenhuma necessidade real do projeto. Por *least privilege*, ele não é carregado no ambiente onde o agente opera sobre dados reais; se houver interesse em explorá-lo, fica num perfil de dev/aprendizado à parte. Incluí-lo "porque o Anexo C lista" seria o oposto de escopo mínimo.

**Recuperação via filesystem é busca por texto, não vetorial.** O `filesystem` server faz busca por arquivo/texto (`search_files` / glob) + leitura — não similaridade de embeddings. A "recuperação" demonstrada no Item 3 é o agente buscando por palavra-chave no corpus e selecionando o chunk; a corretude é julgada contra o mapa de cobertura do Anexo B.
