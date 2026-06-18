# Entregável 2 — Mapeamento de Criação / Consumo

> Exercício 2.3 — Para cada skill: nome, frase-ativação, papel criador, papel + agentes consumidores, frequência estimada.

## Papéis e agentes

- **Papéis:** Tech Lead, Dev Sênior, Dev Pleno, QA, Product Specialist, Delivery Manager.
- **Agentes consumidores:** Copilot (geração de código), Claude Cowork (QA / Product / Delivery), Claude Design (Product Specialist / UI).

## Matriz

| Skill | Nível | Frase-ativação | Cria | Consome (papel + agente) | Frequência |
|-------|-------|----------------|------|--------------------------|-----------|
| typescript-conventions | Foundation | "seguir as convenções TypeScript do projeto" | Dev Sênior | Todos os devs (Copilot) | Sempre |
| error-handling | Foundation | "tratar erros conforme padrão do projeto" | Dev Sênior | Devs (Copilot), QA (Cowork) | Sempre |
| logging | Foundation | "adicionar logging estruturado" | Dev Sênior | Devs (Copilot) | Alta |
| env-config | Foundation | "ler configuração de ambiente" | Tech Lead | Devs (Copilot) | Média |
| project-structure | Foundation | "onde colocar este arquivo / como organizar o módulo" | Tech Lead | Todos (Copilot, Cowork) | Alta |
| azure-functions-endpoint | Domain | "criar um endpoint Azure Functions v4" | Dev Sênior | Devs (Copilot) | Alta |
| azure-ai-search-integration | Domain | "integrar com Azure AI Search / buscar chunks" | Dev Sênior | Devs (Copilot) | Média |
| rag-prompt-assembly | Domain | "montar o prompt RAG respeitando o context budget" | Tech Lead + Dev Sênior | Devs (Copilot) | Média |
| testing-patterns | Domain | "escrever testes no padrão do projeto" | QA + Dev Sênior | Devs (Copilot), QA (Cowork) | Alta |
| react-components | Domain | "criar componente React do painel" | Dev Pleno | Dev Pleno (Copilot), Product Specialist (Claude Design) | Média |
| create-rag-endpoint | Artifact | "gerar um endpoint RAG completo" | Dev Sênior | Devs (Copilot) | Média |
| create-integration-test | Artifact | "gerar teste de integração para o endpoint" | QA | Devs + QA (Copilot, Cowork) | Alta |
| create-react-card | Artifact | "gerar um card de resposta/feedback no painel" | Dev Pleno | Dev Pleno (Copilot), Product Specialist (Claude Design) | Média |
| create-adr | Artifact | "documentar uma decisão arquitetural (ADR)" | Tech Lead | Tech Lead, Dev Sênior (Cowork) | Baixa |
| create-product-spec | Artifact | "escrever a spec de produto (requirements)" | Product Specialist | Product Specialist (Cowork, Claude Design), Tech Lead | Baixa-Média |

## Notas sobre a distribuição

A criação está distribuída por todo o time, não só pelos devs — atendendo ao critério "visão de time":

- **QA** é dono das skills de teste (`testing-patterns`, `create-integration-test`).
- **Product Specialist** é dono da skill de spec de produto (`create-product-spec`).
- **Tech Lead** é dono das decisões transversais (`env-config`, `project-structure`, `create-adr`) e co-dono de `rag-prompt-assembly` por envolver as ADRs.
- **Dev Sênior** concentra a criação das Foundation técnicas e Domain de backend, por serem o padrão que os demais devs seguem.
- **Dev Pleno** cria as skills de frontend (`react-components`, `create-react-card`).

Os agentes consumidores variam conforme o tipo de output: Copilot para código, Claude Cowork para artefatos de QA/Product/Delivery, Claude Design para componentes e UI.