# Cenário-Âncora 2 — Fase de Estruturação do Trabalho

## Tópicos cobertos
- MCP (Model Context Protocol)
- Recorte de Domínio e Spec Driven Development (SDD)
- AGENTS.md
- Skills

## Ferramentas disponíveis para os participantes
- **Claude** (chat) — todos os papéis
- **GitHub Copilot** — desenvolvedores e Tech Lead

## Documentos de apoio
- **Anexo A — Documentação Simulada da NovaTech:** Conteúdo completo dos 5 documentos-chave. Usar como referência para guardrails, glossário de domínio, e dados de teste.
- **Anexo B — Chunks de Referência do Pipeline de RAG:** Chunks extraídos e mapa de cobertura. Usar nos exercícios que pedem dados de teste realistas.
- **Anexo C — Estrutura do Repositório:** Mapa de diretórios do `db1/novatech-assistant` no início desta fase, com convenções de organização e exemplo de configuração MCP.

---

## O Cenário (continuação)

O projeto NovaTech foi aprovado. O discovery está concluído e a fase de entendimento produziu artefatos concretos: ADRs com decisões arquiteturais (modelo LLM, estratégia de contexto, tratamento de documentos contraditórios, build vs buy), uma spec de requisitos de produto para o pipeline de RAG, um protótipo funcional de RAG com ferramentas open-source, cenários de falha mapeados pelo QA, e um plano de testes inicial. Agora o time precisa estruturar o ambiente, os padrões e os artefatos que vão governar o desenvolvimento.

### O que foi definido na fase anterior (cenário 1)

- **Modelo LLM:** Azure OpenAI (GPT-4o) — escolhido pela integração com o ecossistema Microsoft da NovaTech e pela janela de 128K tokens (ADR-0001).
- **Pipeline de RAG:** Azure AI Search + Azure OpenAI. O protótipo open-source (ChromaDB + sentence-transformers) validou a abordagem e identificou problemas de chunking em tabelas (ADR-0004).
- **Estratégia de contexto:** Context budget de ~4K tokens para system prompt + ~8K para chunks (5 chunks de ~1.500 tokens) + pergunta + histórico limitado a 3 turnos (ADR-0002).
- **Documentos contraditórios:** Metadado de vigência no pipeline; prompt instrui o modelo a priorizar versão mais recente; documentos obsoletos marcados, não excluídos (ADR-0003).
- **Integração:** Microsoft Teams (bot) + painel web interno.
- **Base documental:** 847 documentos válidos, 63 descartados por obsolescência, 12 com contradições pendentes de resolução pelo Compliance da NovaTech.
- **Arquitetura:** 3 componentes — (1) pipeline de ingestão, (2) API do assistente (Azure Functions + Azure AI Search + Azure OpenAI), (3) interface no Teams via Bot Framework.
- **Stack:** TypeScript (backend e bot), React (painel web), Bicep para infraestrutura como código.
- **Repositório:** `db1/novatech-assistant` no GitHub da DB1.
- **Time:** 1 Tech Lead, 2 Desenvolvedores (1 pleno, 1 sênior), 1 QA, 1 Product Specialist, 1 Delivery Manager.

### O desafio desta fase

Antes de escrever a primeira linha de código de produção, o time precisa:
1. Definir como agentes de IA (Copilot, Claude Code) serão usados no desenvolvimento — regras, limites, padrões.
2. Recortar o domínio do projeto (bounded contexts, linguagem ubíqua) e especificar o que será construído usando Spec Driven Development.
3. Configurar as conexões que os agentes precisam para operar (MCP servers para acessar repositório, docs, Azure).
4. Criar skills reutilizáveis que encapsulam os padrões do projeto para geração consistente de código e artefatos.

---

## Exercícios por Papel

---

### DESENVOLVEDOR

#### Exercício 2.1 — Configuração de MCP servers para o projeto

**Contexto:** Antes de começar a codar, você precisa configurar os MCP servers que vão permitir aos agentes de IA acessar o repositório, a documentação do Azure e as APIs do projeto.

**Ferramentas a utilizar:** Claude (chat) + GitHub Copilot

**Inputs fornecidos:**
- O cenário completo.
- A estrutura do repositório e o exemplo mínimo de configuração MCP (ver **Anexo C**, seção "Exemplo mínimo de configuração MCP").
- A lista de ferramentas e serviços que o time usa:
  - GitHub (`db1/novatech-assistant`) — repositório do projeto.
  - Azure AI Search — base vetorial de documentos.
  - Azure OpenAI — modelo de geração.
  - Azure DevOps — boards e tracking.
  - Confluence da NovaTech — documentação de negócio (read-only).
- Conceito de MCP: *"MCP (Model Context Protocol) é o protocolo que padroniza como modelos de IA se conectam a ferramentas externas. Um MCP server expõe Tools (ações que o modelo pode executar), Resources (dados read-only que o modelo pode consultar), e Prompts (templates reutilizáveis)."*

**Tarefa:**
1. Usando o **Claude**, mapeie quais MCP servers o projeto precisa. Para cada server, defina: o que expõe (tools, resources, prompts), quem consome (quais papéis/ferramentas), e se já existe como server público ou precisaria ser construído.

2. Para cada MCP server, defina as permissões mínimas necessárias (princípio de least privilege).

3. Usando o **GitHub Copilot**, crie o arquivo de configuração MCP (`.mcp.json` ou equivalente) para o projeto, listando os servers mapeados com suas configurações.

4. Identifique ao menos 2 riscos de segurança no uso de MCP servers neste projeto e proponha mitigações.

**Entregável:** O mapeamento de MCP servers, o arquivo de configuração gerado com o Copilot, e a análise de riscos de segurança.

**Critérios de avaliação:**
- A arquitetura MCP é pragmática (usa servers existentes onde possível, customiza só onde necessário).
- As permissões seguem princípio de least privilege.
- Os riscos de segurança são específicos ao contexto (ex: "o MCP server do Confluence expõe documentação do cliente — se um agente local do dev acessar via MCP e enviar a um modelo cloud, dados sensíveis podem vazar").
- O arquivo de configuração é sintaticamente válido e demonstra uso correto do Copilot.

---

#### Exercício 2.2 — Implementação de spec com Spec Driven Development

**Contexto:** O Product Specialist escreveu o requirements.md do query endpoint. O Tech Lead converteu em plan.md. Agora você precisa converter o plan em tasks.md e implementar a primeira task. Lembre-se de que na fase anterior você construiu um protótipo de RAG com ferramentas open-source — agora o código é de produção, com Azure e padrões do projeto.

**Ferramentas a utilizar:** Claude (chat) + GitHub Copilot

**Inputs fornecidos:**
- O cenário completo.
- A estrutura do repositório (ver **Anexo C**) — o código deve seguir a organização de diretórios definida.
- O plan.md simulado do query endpoint:
  ```markdown
  # Plan — Query Endpoint
  
  ## Approach
  Azure Function HTTP trigger que:
  1. Recebe pergunta do atendente via POST /api/query
  2. Converte pergunta em embedding via Azure OpenAI
  3. Busca top-5 chunks no Azure AI Search
  4. Monta prompt com chunks + system prompt + pergunta
     (respeitando context budget: ~2K system + ~8K chunks + pergunta)
  5. Envia ao GPT-4o e retorna resposta com source_document
  
  ## Technical Decisions
  - TypeScript com Azure Functions v4
  - Zod para validação de input/output
  - Retry com exponential backoff para chamadas Azure
  - Structured logging com pino
  
  ## Prior Decisions (do cenário 1)
  - Context budget definido na ADR-0002: ~4K system + ~8K chunks
  - Documentos contraditórios tratados com metadado de vigência (ADR-0003)
  - System prompt versionado em /prompts/system-prompt.md
  
  ## Dependencies
  - Azure AI Search index must be populated (pipeline de ingestão)
  - System prompt must be finalized (ver /prompts/system-prompt.md)
  ```

**Tarefa:**
1. Usando o **Claude**, converta o plan.md em um `tasks.md` com tasks atômicas. Cada task deve ter: ID, descrição, critérios de aceite, dependências (quais tasks precisam estar prontas antes), e estimativa (P/M/G).

2. Usando o **GitHub Copilot**, implemente a primeira task da lista — tipicamente o setup do endpoint com validação de input. O código deve seguir os padrões definidos no plan (TypeScript, Zod, Azure Functions v4).

3. Revise criticamente o código gerado pelo Copilot: identifique ao menos 2 pontos que precisariam de ajuste antes de um code review real.

**Entregável:** O tasks.md, o código implementado com o Copilot, e a revisão crítica com os ajustes propostos.

**Critérios de avaliação:**
- As tasks são realmente atômicas (cada uma pode ser implementada e testada independentemente).
- Os critérios de aceite são verificáveis (não são vagos como "funcionar corretamente").
- O código gerado pelo Copilot é funcional e segue os padrões do plan.
- A revisão crítica identifica problemas reais (não inventa problemas para cumprir a tarefa).

---

#### Exercício 2.3 — Definição de estratégia de skills do projeto

**Contexto:** Você precisa definir quais skills o projeto precisa, quem as cria, e como são mantidas.

**Ferramentas a utilizar:** Claude (chat) + GitHub Copilot

**Inputs fornecidos:**
- O cenário completo.
- A estrutura do repositório (ver **Anexo C**) — as skills devem seguir a organização em `/skills/foundation/`, `/skills/domain/`, `/skills/artifact/`.
- A lista de artefatos que serão produzidos repetidamente no projeto:
  - Endpoints Azure Functions com padrão RAG (vários ao longo do projeto).
  - Testes de integração para endpoints (mesmo padrão para todos).
  - Componentes React para o painel web (cards de resposta, formulários de feedback).
  - Documentação técnica de endpoints (ADRs, README de módulos).
  - Specs de produto (seguindo template SDD).
- Conceito de skills: *"Skills são artefatos estruturados (tipicamente arquivos .md) que encapsulam como gerar tipos específicos de outputs. A hierarquia é Foundation (convenções globais) → Domain (padrões por camada) → Artifact (receitas de geração)."*

**Tarefa:**
1. Usando o **Claude**, defina a árvore de skills do projeto seguindo a hierarquia Foundation → Domain → Artifact:
   - Foundation: convenções globais (ex: error handling, logging, env config, TypeScript conventions).
   - Domain: padrões por camada (ex: como endpoints são estruturados, como testes são escritos, como componentes React são organizados).
   - Artifact: receitas de geração específicas (ex: skill para criar endpoint RAG, skill para criar teste de integração).

2. Para cada skill, defina: nome, descrição (frase-ativação que um agente reconheceria), quem cria (qual papel), quem consome (qual papel + quais agentes), e frequência de uso estimada.

3. Usando o **GitHub Copilot**, crie o SKILL.md da skill Foundation mais importante (a que será usada por todas as outras como base). O arquivo deve conter: contexto, regras prescritivas, exemplos concretos (DO/DON'T com código), e anti-padrões.

**Entregável:** A árvore de skills, o mapeamento de criação/consumo, e o SKILL.md Foundation gerado com o Copilot.

**Critérios de avaliação:**
- A árvore de skills é coerente com o projeto (não tem skills que ninguém usaria).
- A atribuição de criação e consumo por papel demonstra visão de time (não é só para devs).
- O SKILL.md Foundation é concreto e prescritivo (contém exemplos de código reais, não abstrações).
- Os anti-padrões são úteis (coisas que o Copilot realmente geraria de errado sem guidance).

---

