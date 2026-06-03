# Exercício 1.3 — Pipeline de RAG NovaTech

Entrega do Exercício 1.3 (Cenário 1 — Fase de Entendimento e Contexto, papel Desenvolvedor).

## Como navegar

**Para entender o pipeline:**
1. `rag_pipeline.py` — código do pipeline (parser, chunking, ingestão, busca, montagem de prompt). Documentado, com decisões justificadas no docstring inicial. Suporta dois métodos de embedding via constante `EMBEDDING_METHOD`: `"sentence-transformers"` (usado nesta rodada) e `"tfidf"` (fallback offline).
2. `system_prompt_v3.txt` — system prompt vindo do Exercício 1.2, usado pelo `build_prompt()`.
3. `run_tests.py` — script que roda os 5 testes.

**Para entender os resultados:**
4. `resultados-testes.md` — relatório consolidado dos 5 testes, com (a) chunks recuperados, (b) comparação com o gabarito do Anexo B, (c) avaliação da resposta gerada em quatro eixos (correção factual, citação, guardrails, observações críticas).
5. `correcoes-propostas.md` — 4 problemas identificados, com propostas concretas priorizadas (P0/P1).

**Para ver as respostas reais do Claude:**
6. `respostas-claude/output_pergunta_1.md` a `output_pergunta_5.md` — respostas obtidas colando cada prompt montado pelo pipeline no Claude (chat). São o input principal do relatório.

## Stack utilizada

- **Parser:** `markdown-it-py` + parser hierárquico próprio
- **Chunking:** por seção semântica (`##` e `###`), conforme análise 1.1 §5.3
- **Vetorização:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (open-source, multilíngue, adequado para PT-BR)
- **Vector store:** ChromaDB (persistente local)
- **Geração:** Claude (chat) — prompts colados manualmente

## Resumo do que foi exposto pelos testes

| Teste | Recall must-have | Resposta correta? | Observação |
|---|---|---|---|
| P1 (carga perigosa) | 100% | ✓ | Aviso de versões aplicado mecanicamente, mas resposta substantivamente correta |
| P2 (frete 600kg Manaus) | 50% | ✓ (compensou) | Chunk de multiplicadores não recuperado, mas LLM identificou o gap |
| P3 (cliente Platinum) | 100% | ✓ Excelente | Caso modelo de hierarquia oficial > FAQ |
| P4 (carga danificada) | 100% | ~ correta + ruído | Mistura indevida com tópico de carga perigosa |
| P5 (frete 300kg Salvador) | n/a (gap) | ✓ Excelente | LLM recusou aplicar fórmula fora de escopo |

**Recall must-have: 4,5/5 (90%). Geração correta: 5/5, com ressalva em P4.** Os achados são detalhados em `resultados-testes.md` e as correções em `correcoes-propostas.md`.
