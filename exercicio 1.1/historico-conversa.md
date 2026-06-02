# Histórico da Conversa — Exercício 1.1 NovaTech
**Data:** 29/05/2026  
**Projeto:** Assistente RAG para Atendimento — NovaTech / DB1  
**Papel:** Arquiteto de Soluções Sênior

---

## Mensagem 1 — Usuário

**Contexto fornecido:** Documentos do projeto NovaTech carregados na conversa:
- `anexo-a-documentacao-simulada-novatech.md` — documentação simulada da NovaTech (POL-001, PROC-042 v1 e v2, SLA-2024, FAQ-Atendimento)
- `POL-001-politica-devolucao.md`
- `FAQ-atendimento.md`
- `PROC-042-v2-frete-especial-revisado.md`
- `PROC-042-frete-especial-v1.md`
- `SLA-2024-tabela-sla-clientes.md`
- `anexo-b-chunks-referencia-rag.md`
- `exercicio-fase-1-entendimento-dev.md`

**Instrução:**
> Você é um arquiteto de soluções com IA senior.
>
> Sua tarefa é fazer o exercício 1.1, que consta no arquivo exercicio-fase-1-entendimento-dev.md: uma análise da viabilidade técnica de um assistente de IA que permita aos atendentes fazer perguntas em linguagem natural e receber respostas fundamentadas na documentação oficial da empresa, com indicação da fonte.
>
> Comece planejando os passo a passo que você vai seguir para conseguir entregar a análise da viabilidade técnica da melhor forma possível, seguindo todos os critérios e orientações.

---

## Mensagem 2 — Assistente (Planejamento)

Produzido um plano detalhado antes de executar, cobrindo:

### O que o exercício pede
- Tarefa 1: análise técnica em 4 áreas (fontes, tokens, orçamento de contexto, chunking)
- Tarefa 2: revisão iterativa com o Claude + incorporação de feedback

### Critérios mapeados
- [ ] Diferentes tipos de conteúdo → diferentes estratégias
- [ ] Estimativa de tokens razoável
- [ ] Orçamento de contexto como recurso limitado
- [ ] Chunking justificado pelo tipo de pergunta + efeito *lost in the middle*
- [ ] Iteração verificável

### Passo a passo definido
1. Releitura crítica dos inputs
2. Análise por tipo de fonte (4 tipos)
3. Estimativa de tokens
4. Análise de orçamento de contexto
5. Estratégia de chunking
6. Escrever análise v1
7. Iteração com Claude (auto-crítica)
8. Incorporar feedback e produzir v2

### Observações críticas identificadas antes de começar
- Contradição PROC-042 v1 vs v2 é um caso técnico real dentro da base
- FAQ-Atendimento é não controlado e não validado — confiabilidade diferenciada
- Planilhas com fórmulas são o tipo mais difícil para RAG
- Efeito *lost in the middle* é especialmente perigoso para valores numéricos precisos (multiplicadores, prazos, SLAs)

---

## Mensagem 3 — Usuário

> pode executar o plano

---

## Mensagem 4 — Assistente (Execução)

### Passos executados

**Leitura dos arquivos do projeto:**
- `exercicio-fase-1-entendimento-dev.md` — confirmação de todos os requisitos e critérios
- `anexo-a-documentacao-simulada-novatech.md` — detalhes da documentação da NovaTech
- `/mnt/skills/public/docx/SKILL.md` — verificação de skill relevante

**Produção da Análise v1** (`analise-viabilidade-v1.md`):

Estrutura entregue:
1. Resumo Executivo
2. Análise por Tipo de Fonte
   - 2.1 PDFs com Tabelas Complexas
   - 2.2 PDFs Escaneados (OCR)
   - 2.3 Wiki Confluence com Links e Macros
   - 2.4 Planilhas com Fórmulas
3. Estimativa de Tamanho da Base em Tokens (~4M tokens)
4. Análise de Orçamento de Contexto
5. Estratégia de Chunking Recomendada
6. Riscos e Mitigações
7. Conclusão de Viabilidade

**Iteração com Claude — Revisão Crítica da v1:**

Prompt submetido:
> "Você é um arquiteto de soluções sênior revisando a análise de um colega para um projeto de assistente RAG. Identifique: (1) pontos fracos de argumentação, (2) estimativas otimistas demais, (3) riscos não considerados, (4) inconsistências internas."

Feedback recebido (6 pontos):

| # | Tipo | Problema identificado |
|---|---|---|
| 1 | Ponto fraco | Estimativa de tokens usa premissa não justificada (300 palavras/página como ponto único, sem faixa) |
| 2 | Ponto fraco | Recomendação de "5-8 chunks por query" não é variável pelo tipo de pergunta |
| 3 | Ponto fraco | Function calling para planilhas mencionado mas não desenvolvido como arquitetura |
| 4 | Risco não considerado | Latência de resposta não analisada (pipeline completo pode chegar a 3-8s) |
| 5 | Risco não considerado | Alucinação em perguntas sem cobertura na base (retrieval retorna chunks parcialmente relevantes e LLM constrói resposta errada com aparência de confiança) |
| 6 | Risco não considerado | Ausência de processo de governança/curadoria humana da base |
| 7 | Inconsistência | Estratégia de metadados de supersessão descrita na seção 5 mas risco de não ser aplicada não listado na seção 6 |

**Produção da Análise v2 Final** (`analise-viabilidade-v2-final.md`):

Mudanças incorporadas:

| Seção | Mudança | Motivação |
|---|---|---|
| Seção 3 — Tokens | Estimativa de ponto único → faixas (pessimista/base/otimista) com premissas justificadas | Premissa de 300 palavras/página sem justificativa; planilhas têm alta variabilidade |
| Seção 4.3 — Chunks | Número fixo (5-8) → tabela variável por tipo de pergunta | Perguntas multi-domínio precisam de mais chunks; lookups simples precisam de menos |
| Seção 2.4 — Planilhas | Adicionada subseção completa de Function Calling como Nível 2 | Melhor abordagem para dados dinâmicos estava enterrada sem desenvolvimento |
| Seção 5.4 | Adicionado parágrafo sobre dependência crítica dos metadados de supersessão | A v1 descrevia a estratégia mas não o risco de ela não ser executada |
| Seção 6 | Adicionados riscos de latência, alucinação em gaps e ausência de governança | Riscos identificados na revisão crítica |
| Seção 6.1 e 6.2 | Detalhamentos de latência e alucinação em seções próprias | Os dois riscos mais perigosos merecem tratamento específico |
| Seção 7 | Adicionada visão geral de arquitetura | Facilita comunicação com Tech Lead e stakeholders |

**Arquivos entregues:**
- `analise-viabilidade-v1.md` — rascunho original
- `analise-viabilidade-v2-final.md` — versão final com revisão incorporada

### Como cada critério de avaliação foi atendido

| Critério | Status | Como foi atendido |
|---|---|---|
| Diferentes tipos de conteúdo → diferentes estratégias | ✅ | Seção 2 com 4 subseções independentes, cada uma com desafio, impacto e estratégia próprios |
| Estimativa de tokens razoável e justificada | ✅ | Seção 3 com faixas pessimista/base/otimista e premissas explicitadas |
| Orçamento de contexto como recurso limitado | ✅ | Seção 4 explica efeito *lost in the middle*, propõe orçamento variável e posicionamento em "sandwich" |
| Chunking justificado pelo tipo de pergunta | ✅ | Seção 5 mapeia 4 tipos de perguntas e conecta cada um à estratégia de chunking |
| Iteração verificável com o Claude | ✅ | Revisão crítica com 6 problemas identificados; apêndice com tabela de mudanças da v1 para v2 |

---

## Mensagem 5 — Usuário

> gere um arquivo markdown com o histórico da nossa conversa

---

## Mensagem 6 — Assistente

Geração deste arquivo: `historico-conversa.md`

---

## Artefatos Produzidos na Conversa

| Arquivo | Descrição |
|---|---|
| `analise-viabilidade-v1.md` | Análise de viabilidade técnica — versão inicial (rascunho) |
| `analise-viabilidade-v2-final.md` | Análise de viabilidade técnica — versão final pós-revisão crítica |
| `historico-conversa.md` | Este arquivo — registro completo da conversa |
