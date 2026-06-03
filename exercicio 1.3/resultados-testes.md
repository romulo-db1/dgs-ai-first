# Relatório de Testes — Pipeline de RAG NovaTech

**Exercício 1.3 — Construção de pipeline de RAG com ferramentas open-source**
**Autor:** Desenvolvedor sênior — projeto Assistente NovaTech / DB1
**Data:** 03/06/2026
**Insumos:** `analise-viabilidade-v2-final.md` (Ex. 1.1), `exercicio-1.2-final.md` (Ex. 1.2)

---

## 1. Configuração do pipeline

| Camada | Implementação | Justificativa |
|---|---|---|
| Parser de documentos | `markdown-it-py` + parser hierárquico próprio | Preservar estrutura de seções numeradas dos documentos |
| Estratégia de chunking | Por seção semântica (`##` e `###` do markdown) | Análise 1.1 §5.3 — respeita estrutura regra+exceção da documentação normativa |
| Vetorização | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo open-source, multilíngue, treinado para PT-BR. Captura similaridade semântica (não apenas lexical) |
| Vector store | ChromaDB (persistente local) | Stack sugerida pelo enunciado |
| Métricas de retrieval | Cosine similarity, top_k=5 | Padrão de POC |
| Montagem de prompt | System prompt v3 (Ex. 1.2) + chunks + pergunta | Posição privilegiada de atenção (análise 1.1 §4.4) |
| Geração | Claude (chat) — prompt colado manualmente | Conforme alinhado |

### Estratégia de chunking — justificativa

Chunking por seção semântica significa que cada seção numerada do markdown vira um chunk próprio: a POL-001 §3.2 (exceções ao prazo geral) é um chunk independente da §3.1 (prazo geral). Tamanho-alvo de 150-400 tokens, máximo 600. Cabeçalho de localização prefixado em cada chunk para preservar contexto na busca (`[POL-001 > Seção 3.2 — Exceções ao prazo geral]`).

Por que não chunking por tamanho fixo (ex: 512 tokens com overlap): a documentação da NovaTech segue padrão [regra geral] → [exceção que invalida a regra para certas categorias]. A POL-001-3.1 diz "devolução em 7 dias úteis" e a POL-001-3.2 diz "exceto cargas perigosas, refrigeradas e com lacre violado". Se o chunking dividisse essas seções no meio, o retrieval poderia trazer apenas a regra geral para uma pergunta sobre carga perigosa — produzindo resposta plausível mas factualmente errada. Chunking por seção preserva a unidade semântica.

Bug encontrado e corrigido durante a implementação: o parser inicial descartava o conteúdo de `##` quando este tinha filhos `###` (caso de `## 2. Fórmula de cálculo` do PROC-042, que tem a fórmula no corpo E um `### 2.1` com a tabela de multiplicadores). Resultado: a fórmula desaparecia da base. Corrigi para que ambos virem chunks independentes. É exatamente o tipo de falha silenciosa que a análise 1.1 §2.1 antecipa em outro contexto: "estrutura tabular preservada exige tratamento explícito."

### Distribuição de chunks após ingestão

| Documento | Chunks gerados |
|---|---|
| POL-001 | 7 (seções 1, 2, 3.1, 3.2, 3.3, 3.4, 3.5) |
| PROC-042 (v1) | 5 (seções 1, 2, 2.1, 3, 4) |
| PROC-042-v2 | 6 (seções 1, 2, 2.1, 3, 4, 5) |
| SLA-2024 | 5 (seções 1, 2, 3, 4, 5) |
| FAQ-Atendimento | 9 (Itens 3, 8, 15, 22, 27, 32, 38, 41, 45) |
| **Total** | **32** |

---

## 2. Perguntas escolhidas e armadilhas

As 5 perguntas foram selecionadas do mapa de cobertura do Anexo B para cobrir padrões de armadilha distintos:

| # | Pergunta | Padrão de armadilha |
|---|---|---|
| P1 | Qual o prazo de devolução para carga perigosa? | Regra geral vs exceção que invalida |
| P2 | Quanto custa o frete para 600kg para Manaus? | Cálculo com versões coexistindo do PROC-042 |
| P3 | Qual o SLA do cliente Platinum? | Tier inexistente — alucinação se mal-mitigado |
| P4 | O que acontece quando a carga chega danificada? | Única fonte é FAQ informal (gap na documentação oficial) |
| P5 | Quanto custa o frete para 300kg para Salvador? | Sem cobertura na base (frete < 500kg não está documentado) |

A resposta final do LLM para cada uma está em `respostas-claude/output_pergunta_*.md`. Os prompts montados pelo pipeline estão em `prompts/prompt_T*.txt`.

---

## 3. Resultados por teste

Cada teste é avaliado em quatro eixos:
- **Retrieval:** chunks recuperados pelo pipeline e comparação com o gabarito do Anexo B.
- **Geração — correção factual:** a resposta do LLM está correta dado o contexto disponível?
- **Geração — citação de fonte:** todas as afirmações estão fundamentadas em chunks com identificador?
- **Geração — guardrails:** prompt v3 respeitado (formato, hierarquia de fontes, ausência de invenção)?

---

### P1 — "Qual o prazo de devolução para carga perigosa?"

**Chunks recuperados (top 5):**

| # | chunk_id | fonte | confiabilidade |
|---|---|---|---|
| 1 | `POL-001-3.2` | POL-001 §3.2 — Exceções ao prazo geral | oficial |
| 2 | `POL-001-3.5` | POL-001 §3.5 — Custos de devolução | oficial |
| 3 | `PROC-042-3` | PROC-042 §3 — Prazo de entrega para frete especial | oficial (v1) |
| 4 | `PROC-042-v2-3` | PROC-042-v2 §3 — Prazo de entrega para frete especial | oficial (v2) |
| 5 | `FAQ-Atendimento-Item 38` | FAQ Item 38 — Carga danificada | informal |

**Comparação com gabarito (Anexo B → "Posso devolver carga perigosa?"):**

- Must-have: `POL-001-3.2`. **Recuperado em 1º. Recall: 100%.**
- Nice-to-have: `POL-001-3.1`, `FAQ-Atendimento-Item 3`. **Nenhum recuperado.**

**Avaliação da resposta (`output_pergunta_1.md`):**

- **Correção factual:** ✓ A resposta lidera pela exceção, identifica corretamente que carga perigosa não é elegível pelo processo padrão, e cita o procedimento alternativo (ramal 4500 — Gestão de Riscos). É o comportamento esperado pelo prompt v3.
- **Citação de fonte:** ✓ Toda afirmação factual aponta para `POL-001-3.2`. Identificador explícito.
- **Guardrails:** ✓ Formato `[Resposta direta] / [Fundamento] / [Observações]` íntegro. Sem emojis. Sem invenção.

**Observação crítica:** A resposta inclui o aviso obrigatório de versões coexistentes do PROC-042 — porque os dois chunks `PROC-042-3` e `PROC-042-v2-3` aparecem no contexto. Isso é tecnicamente correto pelo prompt v3, mas **operacionalmente ruim**: a pergunta é sobre devolução, não sobre frete. O atendente recebe um aviso irrelevante para o caso dele. Esse é um efeito colateral interessante do retrieval trazer chunks tematicamente próximos (ambos contêm "prazo") mas semanticamente fora do escopo.

A resposta também acrescentou um parágrafo bem-feito em `[Observações]` registrando que os chunks não estabelecem prazo para acionar o ramal 4500 — sinalização explícita de gap, com sugestão de escalar.

---

### P2 — "Quanto custa o frete para 600kg para Manaus?"

**Chunks recuperados (top 5):**

| # | chunk_id | fonte | confiabilidade |
|---|---|---|---|
| 1 | `PROC-042-v2-2` | PROC-042-v2 §2 — Fórmula de cálculo | oficial (v2) |
| 2 | `PROC-042-v2-4` | PROC-042-v2 §4 — Condições especiais | oficial (v2) |
| 3 | `PROC-042-1` | PROC-042 §1 — Objetivo | oficial (v1) |
| 4 | `PROC-042-2` | PROC-042 §2 — Fórmula de cálculo | oficial (v1) |
| 5 | (5º não identificado claramente na resposta — provável `PROC-042-v2-1` ou semelhante) | | |

**Comparação com gabarito (Anexo B → "Frete para 600kg para Manaus?"):**

- Must-have: `PROC-042-v2-2.1` (multiplicadores v2), `PROC-042-v2-2` (fórmula v2). **Recall parcial: 50%.** A fórmula (`PROC-042-v2-2`) foi recuperada em 1º; **a tabela de multiplicadores (`PROC-042-v2-2.1`), que contém o valor "Norte = 1.8", NÃO foi recuperada.**
- Nice-to-have: `PROC-042-B` (versão antiga). 1 chunk da v1 apareceu.

**Avaliação da resposta (`output_pergunta_2.md`):**

- **Correção factual:** ✓ A resposta correta dado o contexto. Identifica que (a) a fórmula é conhecida, (b) o fator de peso é 1.0 para 600kg, e (c) o multiplicador regional para Manaus não consta nos chunks. **Não inventa** o valor — comportamento ideal do prompt v3.
- **Citação de fonte:** ✓ Cita `PROC-042-v2-2` e identifica corretamente que `Seção 2.1 não foi recuperada`.
- **Guardrails:** ✓ Formato íntegro. Aviso obrigatório de versões coexistentes presente (e aqui faz total sentido — é uma pergunta sobre PROC-042). A tabela comparativa de fatores de peso em `[Observações]` é uma adição útil — mostra ao atendente que para 600kg as duas versões coincidem, removendo ambiguidade.

**Observação crítica:** Este é o caso mais interessante do conjunto. **O retrieval falhou parcialmente** (não trouxe o chunk com o multiplicador), **mas o LLM compensou perfeitamente** seguindo o prompt v3: identificou exatamente o que estava faltando e onde consultar (Seção 2.1 do PROC-042-v2 + tabela mensal de fretes). A resposta é mais útil para o atendente do que uma resposta calculada com valor inventado seria — porque ele agora sabe o que buscar manualmente.

A síntese da diferença entre v1 e v2 nos fatores de peso, em `[Observações]`, mostra que o LLM consegue raciocinar sobre versões coexistentes quando os chunks de ambas estão no contexto.

---

### P3 — "Qual o SLA do cliente Platinum?"

**Chunks recuperados (top 5):**

| # | chunk_id | fonte | confiabilidade |
|---|---|---|---|
| 1 | `FAQ-Atendimento-Item 15` | FAQ Item 15 — Tier Platinum | informal |
| 2 | `SLA-2024-1` | SLA-2024 §1 — Classificação de clientes | oficial |
| 3 | `FAQ-Atendimento-Item 41` | FAQ Item 41 — Diferença SLA resposta/resolução | informal |
| 4 | `POL-001-2` | POL-001 §2 — Escopo | oficial |
| 5 | `SLA-2024-5` | SLA-2024 §5 — Medição e reportes | oficial |

**Comparação com gabarito (Anexo B → "Qual o SLA do cliente Platinum?"):**

- Must-have: `SLA-2024-1` (contém "não existem outros tiers"). **Recuperado em 2º. Recall: 100%.**
- Nice-to-have: `FAQ-Atendimento-Item 15`. **Recuperado em 1º.**

**Avaliação da resposta (`output_pergunta_3.md`):**

- **Correção factual:** ✓ Excelente. Lidera afirmando que Platinum não existe, cita os três tiers reais (Gold, Silver, Standard), e indica a ação correta para o atendente (solicitar número de contrato).
- **Citação de fonte:** ✓ Distinção exemplar entre `SLA-2024-1` (oficial — usado como fundamento principal) e `FAQ-15` (informal — usado como contexto histórico explicativo, marcado como "fonte interna não validada formalmente").
- **Guardrails:** ✓ Formato íntegro. Hierarquia de fontes respeitada: oficial primeiro, informal como complemento.

**Observação crítica:** Este é o resultado mais sólido do conjunto. O retrieval semântico recuperou tanto o chunk oficial (que tem a informação com autoridade formal) quanto o chunk informal (que tem o contexto histórico sobre por que o cliente pode estar confuso — programa de fidelidade descontinuado em 2022). A resposta combina os dois com hierarquia correta. É exatamente o comportamento desejado em produção.

A observação final, sugerindo encaminhar ao Comercial para análise de viabilidade de SLA diferenciado, é construtiva — não é apenas "não" para o cliente, é um caminho de saída.

---

### P4 — "O que acontece quando a carga chega danificada?"

**Chunks recuperados (top 5):**

| # | chunk_id | fonte | confiabilidade |
|---|---|---|---|
| 1 | `FAQ-Atendimento-Item 38` | FAQ Item 38 — Carga danificada em trânsito | informal |
| 2 | `POL-001-3.2` | POL-001 §3.2 — Exceções ao prazo geral | oficial |
| 3 | `POL-001-3.4` | POL-001 §3.4 — Devoluções parciais | oficial |
| 4 | `POL-001-3.5` | POL-001 §3.5 — Custos de devolução | oficial |
| 5 | `SLA-2024-3` | SLA-2024 §3 — Definição de incidente crítico | oficial |

**Comparação com gabarito (Anexo B → "O que acontece com carga danificada?"):**

- Must-have: `FAQ-Atendimento-Item 38`. **Recuperado em 1º. Recall: 100%.**
- Nice-to-have: nenhum (nenhum documento formal cobre o tema).

**Avaliação da resposta (`output_pergunta_4.md`):**

- **Correção factual:** ~ Correta no essencial (registrar em 48h, enviar para `sinistros@novatech.com.br`, FAQ marcado como informal), mas **introduz ruído**.
- **Citação de fonte:** ✓ Todas as afirmações citam fonte.
- **Guardrails:** ✓ Formato íntegro. FAQ marcado explicitamente como informal.

**Observação crítica — ponto delicado:** O LLM **misturou domínios** ao incluir, no `[Resposta direta]`, a menção a "carga perigosa ou lacre violado → Gestão de Riscos". A pergunta foi sobre carga **danificada** (problema do transporte em si), não sobre carga perigosa (categoria especial de mercadoria). Tecnicamente, o POL-001-3.2 fala de exceções à devolução padrão para essas categorias, mas isso é **um cenário diferente** do que o atendente perguntou.

O motivo da mistura é claro pelo retrieval: como `POL-001-3.2` foi recuperado em 2º (provavelmente por compartilhar vocabulário com "carga"), o LLM tentou integrá-lo à resposta. O prompt v3 instrui o modelo a "ler TODOS os chunks fornecidos" e "verificar se há chunks que se complementam" — neste caso, o LLM aplicou essa regra e produziu uma resposta que cobre dois cenários, mas a integração é forçada.

Em produção, isso é um risco moderado: o atendente que está sob pressão de tempo pode confundir os dois fluxos e mandar o cliente para o ramal 4500 quando o caminho correto seria `sinistros@novatech.com.br`. A boa notícia é que o LLM separou claramente os dois fluxos em `[Observações]` — então um atendente atento percebe a distinção. Mas é uma falha de retrieval que se materializou no output.

---

### P5 — "Quanto custa o frete para 300kg para Salvador?"

**Chunks recuperados (top 5):**

| # | chunk_id | fonte | confiabilidade |
|---|---|---|---|
| 1 | `PROC-042-v2-1` | PROC-042-v2 §1 — Objetivo | oficial (v2) |
| 2 | `PROC-042-v2-2` | PROC-042-v2 §2 — Fórmula de cálculo | oficial (v2) |
| 3 | `PROC-042-v2-4` | PROC-042-v2 §4 — Condições especiais | oficial (v2) |
| 4 | `PROC-042-1` | PROC-042 §1 — Objetivo | oficial (v1) |
| 5 | `PROC-042-2` | PROC-042 §2 — Fórmula de cálculo | oficial (v1) |

**Comparação com gabarito (Anexo B → "Frete para 300kg para Salvador?"):**

- Must-have: **nenhum** — pergunta NÃO tem cobertura na base. A PROC-042 só trata cargas acima de 500kg.
- Pipeline retornou 5 chunks tematicamente relacionados (todos sobre frete especial > 500kg) — exatamente o tipo de ruído esperado.

**Avaliação da resposta (`output_pergunta_5.md`):**

- **Correção factual:** ✓ Excelente. O LLM **leu o conteúdo dos chunks com atenção** e identificou que o limite mínimo da PROC-042-v2 é 500kg. Recusou-se a aplicar a fórmula a uma carga de 300kg e sugeriu escalar.
- **Citação de fonte:** ✓ Cita `PROC-042-v2-1` e `PROC-042-v2-2` como base para identificar o limite.
- **Guardrails:** ✓ Formato íntegro. Aviso de versões coexistentes presente. Recomendação de escalar quando há gap explícito.

**Observação crítica:** Este é o teste decisivo do prompt v3. O risco previsto na análise 1.1 §6.2 era exatamente este — o LLM receber chunks tematicamente relacionados (PROC-042 fala de frete) e construir uma resposta calculada usando a fórmula, ignorando que 300kg está fora do escopo. **O LLM não caiu na armadilha.** Detectou o limite de 500kg e recusou calcular.

Esse comportamento é o que justifica o investimento em prompt engineering do exercício 1.2 — sem o protocolo de leitura e a instrução explícita sobre cálculos com dados faltantes, o modelo provavelmente aplicaria a fórmula a 300kg.

---

## 4. Síntese

### 4.1 Taxa de acerto por etapa

| Teste | Retrieval (recall must-have) | Resposta correta? | Citação de fonte? | Guardrails? |
|---|---|---|---|---|
| P1 (carga perigosa) | 100% (1/1) | ✓ | ✓ | ✓ |
| P2 (frete 600kg Manaus) | 50% (1/2) | ✓ (compensou via prompt) | ✓ | ✓ |
| P3 (Platinum) | 100% (1/1) | ✓ Excelente | ✓ Hierarquia exemplar | ✓ |
| P4 (carga danificada) | 100% (1/1) | ~ Correta + ruído | ✓ | ✓ |
| P5 (frete 300kg) | n/a (gap correto) | ✓ Excelente | ✓ | ✓ |

**Recall must-have:** 4,5 / 5 = 90%. **Geração correta:** 5 / 5, com a ressalva de P4 que introduziu ruído controlado.

### 4.2 Onde o pipeline funcionou bem

- **Retrieval semântico cobre paráfrases.** P3 é o exemplo claro: o chunk oficial `SLA-2024-1` diz "Não existem outros tiers além dos três listados" — sem mencionar a palavra "Platinum". O modelo semântico entendeu a equivalência e recuperou. Um retrieval por similaridade lexical (tipo TF-IDF) provavelmente teria errado isso.
- **Hierarquia de fontes respeitada.** Em P3, com FAQ-Item 15 e SLA-2024-1 ambos no contexto, o LLM usou o oficial como fundamento principal e o FAQ como contexto histórico — exatamente o comportamento que o prompt v3 instrui.
- **Recusa de calcular em gaps.** P5 é o caso mais sensível, e o LLM não caiu na armadilha de aplicar a fórmula PROC-042 a uma carga de 300kg.
- **Compensação via prompt em falhas de retrieval.** P2 mostra que mesmo quando o retrieval falha parcialmente (chunk de multiplicadores não recuperado), o LLM seguindo o prompt v3 produz uma resposta útil — identifica exatamente o dado faltante e onde buscá-lo.

### 4.3 Onde o pipeline mostrou limitação

- **P2 — chunk crítico não recuperado.** A tabela de multiplicadores da v2 (`PROC-042-v2-2.1`) ficou de fora do top 5. A fórmula veio, mas o valor de "Norte = 1.8" não. Em produção, atendentes não querem precisar fazer o passo manual de buscar o multiplicador.
- **P1 — ruído por retrieval tematicamente próximo.** Os chunks de PROC-042 §3 (prazo de frete especial) foram trazidos para uma pergunta sobre devolução. Não atrapalharam a resposta principal, mas forçaram o LLM a aplicar o aviso de versões coexistentes em um caso onde ele é irrelevante.
- **P4 — mistura de domínios.** Carga danificada e carga perigosa/lacre violado são cenários diferentes, e o LLM tentou integrá-los na mesma resposta porque ambos chunks foram recuperados. O atendente atento separa; o atendente sob pressão pode confundir.

### 4.4 Validação dos pontos da análise 1.1

| Ponto da análise | Status nos testes |
|---|---|
| Chunking semântico preserva regra+exceção (§5.3) | ✓ Confirmado em P1 — POL-001-3.2 recuperado intacto |
| Embedding multilíngue captura paráfrases (§7) | ✓ Confirmado em P3 — recuperou chunk sem o termo literal "Platinum" |
| Versões coexistentes sem supersessão são problema (§5.4) | ✓ Confirmado em P1, P2, P5 — v1 e v2 sempre no contexto juntas |
| Alucinação em gaps deve ser explicitamente prevenida (§6.2) | ✓ Confirmado em P5 — recusou calcular fora do escopo |
| FAQ não deve dominar sobre fonte oficial (§5.5) | ✓ Confirmado em P3 — oficial usado como fundamento, FAQ como contexto |

A análise 1.1 antecipou corretamente as áreas de risco. O pipeline implementado materializa as decisões da análise e os resultados confirmam tanto o que funciona quanto as áreas onde melhorias são necessárias (ver `correcoes-propostas.md`).

---

## 5. Apêndice — Arquivos referenciados neste relatório

- `respostas-claude/output_pergunta_1.md` a `output_pergunta_5.md` — respostas reais do Claude obtidas colando os prompts montados pelo pipeline.
- `prompts/prompt_T1.txt` a `prompt_T5.txt` — prompts completos montados pelo pipeline (system prompt v3 + chunks recuperados + pergunta).
- `rag_pipeline.py` — implementação do pipeline.
- `run_tests.py` — script de execução dos testes.
- `system_prompt_v3.txt` — system prompt vindo do Exercício 1.2.
