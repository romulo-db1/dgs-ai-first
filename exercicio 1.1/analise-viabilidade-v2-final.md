# Análise de Viabilidade Técnica — Assistente de IA para Atendimento NovaTech
## Exercício 1.1 — Versão 2 (pós-revisão crítica)

**Autor:** Arquiteto de Soluções Sênior  
**Data:** 29/05/2026  
**Projeto:** Assistente RAG para time de atendimento — NovaTech / DB1  
**Status:** Versão final

> **Nota de iteração:** Esta versão incorpora feedback da revisão crítica da v1. As principais mudanças são: (1) estimativa de tokens apresentada em faixas em vez de ponto único, (2) recomendação de chunks variável por tipo de pergunta, (3) desenvolvimento da arquitetura de function calling para planilhas, (4) adição de riscos de latência, alucinação em gaps e governança, e (5) inclusão do risco de metadados de supersessão não aplicados.

---

## 1. Resumo Executivo

A NovaTech enfrenta um problema de acesso a informações: 45 atendentes gastam em média 12 minutos por chamado consultando documentação dispersa em SharePoint, Confluence e planilhas de rede. O objetivo é construir um assistente baseado em RAG (Retrieval-Augmented Generation) que reduza esse tempo para menos de 2 minutos.

**Conclusão:** O projeto é **tecnicamente viável**, mas com riscos que precisam ser gerenciados desde o design — não tratados como dívida técnica. A principal ameaça não é a tecnologia em si: é a qualidade e a consistência da documentação de origem.

A NovaTech possui documentos que se contradizem entre versões (PROC-042 v1 vs v2), fontes com confiabilidade heterogênea (documentos normativos vs. FAQ informal não validado), e tipos de conteúdo — tabelas complexas, fluxogramas como imagem, planilhas com fórmulas — que apresentam desafios reais de extração e representação.

Os riscos não tornam o projeto inviável, mas tornam inviável uma abordagem ingênua de "ingerir tudo e confiar no modelo". A solução requer engenharia cuidadosa em três frentes: **extração**, **chunking** e **gerenciamento de contexto**. Um quarto fator, frequentemente negligenciado, é igualmente crítico: **governança contínua da base de conhecimento**.

---

## 2. Análise por Tipo de Fonte

### 2.1 PDFs com Tabelas Complexas (15+ colunas)

**Contexto NovaTech:** Tabelas de frete com múltiplas colunas são o coração operacional do negócio. Um atendente que pergunta "qual o multiplicador para frete de 800kg para o Nordeste?" espera um valor numérico preciso. Erro aqui tem impacto financeiro direto.

**Desafio técnico:**  
Extratores de PDF tradicionais (PyMuPDF, pdfminer, pypdf) tratam tabelas como texto corrido. Uma tabela com 15 colunas frequentemente é serializada como uma sequência linear de células, perdendo completamente a estrutura de linhas e colunas. O resultado é um bloco de texto como `"Sul 1.2 Sudeste 1.0 Centro-Oeste 1.3..."` sem delimitação de qual valor pertence a qual combinação de linha/coluna.

Quando esse texto vira um chunk e é enviado ao LLM como contexto, o modelo pode associar o multiplicador errado à região errada — especialmente se a tabela for grande e o chunk capturar apenas parte dela.

Tabelas que se estendem por mais de uma página são frequentemente divididas pelo extrator no limite da página, gerando um chunk de "cabeçalho + primeiras linhas" e outro de "linhas restantes sem cabeçalho". O segundo chunk fica ilegível sem o contexto do primeiro.

**Impacto na qualidade das respostas:**  
- Alta probabilidade de valores numéricos errados em respostas sobre frete
- O modelo pode reconstruir incorretamente a estrutura da tabela a partir de texto malformado
- Chunks parciais de tabela criam respostas inconsistentes dependendo de qual chunk foi recuperado

**Estratégia de tratamento:**  
1. **Usar extrator especializado em tabelas:** Preferir `pdfplumber` ou `camelot` em vez de extratores genéricos. Ambos reconhecem estrutura tabular e exportam como DataFrame/CSV, preservando alinhamento de células.
2. **Serializar tabelas em Markdown:** Converter cada tabela para Markdown tabular (`| Região | Multiplicador |`) antes de chunkar. Esse formato preserva a estrutura e é nativamente compreendido pelos LLMs.
3. **Tratar tabelas como chunks atômicos:** Uma tabela inteira deve ser um único chunk, mesmo que ultrapasse o tamanho-alvo de tokens. Não dividir tabelas no meio.
4. **Adicionar metadado de tipo:** Marcar chunks de tabela com `content_type: "table"` para que a lógica de retrieval possa priorizar conforme a natureza da pergunta.
5. **Para tabelas com divisão inevitável:** Replicar o cabeçalho em cada chunk, garantindo que linhas nunca sejam enviadas ao LLM sem contexto de cabeçalho.

---

### 2.2 PDFs Escaneados (OCR Necessário)

**Contexto NovaTech:** Documentos históricos, contratos físicos digitalizados ou manuais antigos sem versão digital nativa.

**Desafio técnico:**  
PDFs escaneados são imagens — não há texto extraível diretamente. O pipeline precisa de OCR antes de qualquer extração. O problema é que OCR introduz erros que se propagam para embeddings e para o contexto do LLM.

Erros típicos de OCR em documentos de logística:
- Confusão entre caracteres similares: `0` e `O`, `1` e `l`, `rn` e `m`
- Números com casas decimais corrompidos: `1.5` vira `l.5` ou `15`
- Layout em múltiplas colunas lido como texto contínuo mesclando as colunas

Para documentos onde prazos (`7 dias úteis`), multiplicadores (`1.4`) e códigos de procedimento (`PROC-042`) são críticos, um erro de OCR pode ser devastador: `1.4` virando `l.4` faz o chunk ser recuperado com menor precisão por embedding de similaridade, e o valor errado ir para a resposta — sem nenhum sinal de erro para o atendente.

**Impacto na qualidade das respostas:**  
- Erros silenciosos: o sistema responde com confiança, mas com dados corrompidos
- Degradação de retrieval: embeddings de texto com erros de OCR têm menor similaridade com queries bem escritas
- Impossível rastrear na resposta se o erro veio de OCR ou de lógica do documento original

**Estratégia de tratamento:**  
1. **Inventariar e isolar documentos escaneados** como categoria separada no pipeline.
2. **Usar Azure AI Document Intelligence** (disponível no Azure AI Services já contratado pela NovaTech), que supera Tesseract em documentos de negócio com tabelas e layouts complexos.
3. **Revisão humana obrigatória pós-OCR** para documentos críticos (tabelas de SLA, tabelas de multiplicadores de frete). Implementar workflow de validação antes da ingestão.
4. **Score de confiança de OCR como metadado:** Registrar o score de confiança por página e expô-lo no contexto: `"[AVISO: trecho extraído por OCR com confiança 72%. Verifique o documento original.]"`.
5. **Threshold de qualidade:** Para documentos com OCR abaixo de 85% de confiança em seções críticas, não ingerir automaticamente — escalar para revisão manual.

---

### 2.3 Wiki Confluence com Links Internos e Macros Customizadas

**Contexto NovaTech:** ~400 páginas wiki com procedimentos, decisões de design e conhecimento tácito. Links internos entre páginas são comuns — "consultar PROC-088 para interceptação de carga".

**Desafio técnico:**  
O Confluence usa Storage Format (XML) com macros que renderizam conteúdo dinamicamente: painéis de aviso, tabelas de status, índices automáticos. Quando se exporta uma página para texto, macros viram lixo XML ou desaparecem. Links internos tornam-se referências mortas após extração.

Páginas Confluence frequentemente têm hierarquia (espaço → página pai → subpáginas). Esse contexto hierárquico é perdido quando cada página é tratada como documento isolado. Uma subpágina que só faz sentido dentro do contexto da página pai pode gerar respostas confusas quando recuperada isoladamente.

**Impacto na qualidade das respostas:**  
- Respostas incompletas quando o LLM recebe um chunk que referencia outro documento sem conseguir acessá-lo
- Contexto hierárquico perdido: chunks de subpáginas sem contexto da página pai são frequentemente ambíguos
- Macros de aviso críticas (ex: "ATENÇÃO: esta regra foi revogada em jan/2024") podem desaparecer na extração, fazendo o sistema citar regras obsoletas com confiança

**Estratégia de tratamento:**  
1. **Usar a API REST do Confluence**, não exportação em lote. A API retorna Storage Format (HTML) que preserva estrutura melhor.
2. **Resolver links internos durante ingestão:** Para cada link interno, registrar metadado de relacionamento `links_to: [page_id_1, page_id_2]` e usar no retrieval para expandir contexto quando necessário.
3. **Incluir breadcrumb hierárquico como prefixo de chunk:** Cada chunk começa com `[Espaço > Página Pai > Página Atual]`.
4. **Tratar macros de aviso como conteúdo crítico:** Macros "Note", "Warning", "Info" devem ser extraídas explicitamente e prefixadas com `[AVISO:]`, `[IMPORTANTE:]`. Nunca descartadas silenciosamente.
5. **Link expansion controlada:** Quando um chunk contém referência explícita a outro documento, incluir automaticamente o chunk mais relevante do referenciado no contexto, marcado como `[contexto expandido]`.

---

### 2.4 Planilhas com Fórmulas Interdependentes

**Contexto NovaTech:** Planilhas de referência atualizadas mensalmente — tabelas de frete-base, prazos por rota, SLAs customizados.

**Desafio técnico:**  
Este é o tipo de fonte **mais problemático para RAG**, e o risco é sistematicamente subestimado.

O problema fundamental: planilhas com fórmulas têm dois tipos de "conteúdo" — os **valores calculados** (o que o usuário vê) e as **fórmulas** (a lógica que gerou os valores). Se a extração captura as fórmulas (`=SE(B2>500;VLOOKUP(C2,TabelaBase,3,0)*1.2;...)`), o LLM recebe expressões matemáticas sem contexto. Se captura apenas os valores, captura um snapshot estático — desatualizado quando a planilha é editada sem o pipeline ser reexecutado.

Planilhas com fórmulas interdependentes são ainda mais críticas: uma célula depende de outra, em outra aba. A "resposta" está distribuída em múltiplas abas com a lógica nos relacionamentos entre elas. Adicionalmente, a semântica visual (células verdes = ativas, vermelhas = descontinuadas, negrito = atenção) desaparece na extração.

**Impacto na qualidade das respostas:**  
- Respostas sobre valores de frete podem estar desatualizadas
- Fórmulas complexas enviadas ao LLM geram respostas confusas ou incorretas
- Semântica visual perdida: o sistema pode recomendar uma tarifa descontinuada que estava marcada em vermelho

**Estratégia de tratamento — dois níveis:**

**Nível 1 — RAG com valores estáticos (para dados de referência estáveis):**
1. Ingerir apenas valores calculados, nunca fórmulas
2. Adicionar timestamp de extração obrigatório como metadado
3. Implementar pipeline de reingesta automática com trigger a cada atualização da pasta de rede
4. Converter tabelas de planilha para Markdown tabular antes de chunkar
5. Alertas de defasagem: chunks com mais de X dias sem atualização recebem aviso no contexto

**Nível 2 — Function Calling para dados dinâmicos (recomendado para frete-base):**  
Para consultas que envolvem cálculos com dados que mudam mensalmente (ex: "qual o frete para 800kg para o Nordeste?"), a abordagem RAG tem limitação estrutural. A alternativa é expor a planilha de frete-base como uma **ferramenta que o LLM pode chamar diretamente**, via function calling:

```
Atendente: "Frete para 800kg para o Nordeste?"
LLM → chama ferramenta: get_frete_base(peso=800, regiao="Nordeste", data=hoje)
Ferramenta → consulta planilha via API/Excel → retorna valor_base=R$450
LLM → aplica PROC-042-v2: R$450 × 1.5 (Nordeste) × 1.15 (fator peso 800kg) = R$776,25
LLM → responde com cálculo detalhado e rastreável
```

Isso garante dados sempre atualizados, cálculos corretos e resposta rastreável — o que RAG estático não consegue oferecer para dados que mudam mensalmente. A integração com Microsoft Excel/SharePoint via Microsoft Graph API (disponível com M365 E3 já contratado) é direta.

---

## 3. Estimativa de Tamanho da Base em Tokens

### 3.1 Premissas e faixas de estimativa

Regra fornecida: **1 token ≈ 0,75 palavras**.

Para PDFs, a densidade varia significativamente por tipo de documento. Em vez de um único número, apresentamos faixas:

| Tipo de documento | Palavras/página (pessimista) | Palavras/página (base) | Palavras/página (otimista) |
|---|---|---|---|
| Manual de procedimento (texto denso) | 300 | 350 | 450 |
| Documentos com tabelas/formatação | 150 | 250 | 300 |
| Mix realista (NovaTech) | 200 | 280 | 350 |

Para a estimativa base, usamos **280 palavras/página** para PDFs — ligeiramente abaixo de 300 para refletir que a documentação de logística da NovaTech tem alta densidade de tabelas, listas numeradas e formatação que reduzem a contagem de palavras por página.

Para planilhas, a estimativa varia ainda mais. Planilhas de frete com centenas de rotas podem ter 5.000-10.000 palavras de dados. Usamos **2.000 palavras/planilha** como estimativa base, reconhecendo que há alta incerteza aqui.

### 3.2 Cálculo por fonte (cenário base)

**PDFs do SharePoint:**
- Volume: 800 documentos × 10 páginas/documento = 8.000 páginas
- Palavras: 8.000 × 280 = 2.240.000 palavras
- Tokens: 2.240.000 ÷ 0,75 = **~3.000.000 tokens**

**Wiki Confluence:**
- Volume: 400 páginas × 1.500 palavras = 600.000 palavras
- Tokens: 600.000 ÷ 0,75 = **~800.000 tokens**

**Planilhas:**
- Volume: 50 planilhas × 2.000 palavras = 100.000 palavras
- Tokens: 100.000 ÷ 0,75 = **~133.000 tokens**

### 3.3 Total com faixas

| Fonte | Tokens (pessimista) | Tokens (base) | Tokens (otimista) |
|---|---|---|---|
| PDFs SharePoint | 3.800.000 | 3.000.000 | 2.100.000 |
| Wiki Confluence | 800.000 | 800.000 | 800.000 |
| Planilhas | 250.000 | 133.000 | 67.000 |
| **Total** | **~4.850.000** | **~3.933.000** | **~2.967.000** |

**A base tem aproximadamente 3 a 5 milhões de tokens.** 

Isso confirma que a base **não cabe na janela de contexto de nenhum modelo atual** (GPT-4o: 128K; Claude Sonnet: 200K). Essa não é uma limitação — é a premissa que justifica o RAG. O pipeline precisa selecionar 2.000–5.000 tokens relevantes dentre os ~4 milhões da base. A qualidade desse processo de seleção é o determinante principal da qualidade das respostas.

---

## 4. Análise de Orçamento de Contexto

### 4.1 Anatomia do contexto por query

Com GPT-4o (128K tokens):

| Componente | Tokens estimados | Tipo |
|---|---|---|
| System prompt (identidade, regras, guardrails, instruções de formato) | ~1.500 | Estático |
| Instruções de uso dos chunks (como interpretar, como citar) | ~500 | Estático |
| **Total estático** | **~2.000** | |
| Histórico da conversa (3-5 turnos) | ~1.000–2.500 | Dinâmico |
| Dados do atendente/contexto do chamado (cliente, tier) | ~300–500 | Dinâmico |
| Chunks recuperados | variável | Dinâmico |
| Pergunta atual | ~50–150 | Dinâmico |
| **Margem para resposta do modelo** | ~1.000–2.000 | Saída |

**Orçamento disponível para chunks:** 128.000 − 2.000 − 2.500 − 500 − 150 − 2.000 ≈ **~120.850 tokens** em teoria.

### 4.2 Por que não usar todos os tokens disponíveis

Matematicamente, caberiam ~241 chunks de 500 tokens no orçamento. Isso parece generoso — e é exatamente a armadilha.

O problema é o **efeito "lost in the middle"**: LLMs têm atenção não-uniforme ao longo do contexto. Informações no início ou no final do prompt recebem significativamente mais atenção do que informações no meio. Em experimentos com GPT-3.5 e GPT-4 (Liu et al., 2023), a precisão em recuperar informações do meio de contextos longos cai 15-30% em comparação com extremidades.

Para o assistente da NovaTech, isso é especialmente crítico porque as respostas dependem de **valores numéricos precisos** — multiplicadores de frete, prazos em dias, SLAs em horas — que são exatamente o tipo de dado que se perde quando enterrado no meio de 241 chunks. O modelo pode ver o chunk correto, mas não lhe dar atenção suficiente.

### 4.3 Orçamento de chunks recomendado por tipo de pergunta

A v1 desta análise recomendava um número fixo de 5-8 chunks. A revisão crítica identificou que esse número varia pelo tipo de pergunta. A recomendação correta é:

| Tipo de pergunta | Chunks recomendados | Justificativa |
|---|---|---|
| Lookup pontual ("qual o prazo de devolução?") | 2–3 | Uma seção, possivelmente a adjacent para contexto |
| Lookup com condição ("posso devolver carga perigosa?") | 3–4 | Regra geral + seção de exceções + procedimento alternativo |
| Cálculo/composição ("frete para 800kg para o Nordeste") | 4–6 | Fórmula + multiplicadores + fator de peso + condições especiais |
| Multi-domínio ("cliente Gold, carga perigosa, custo de devolução") | 6–10 | Chunks de 3-4 documentos diferentes |

**Limite máximo recomendado:** 10 chunks por query, independente do tipo. Acima disso, a degradação de atenção supera o ganho de cobertura.

### 4.4 Posicionamento estratégico no contexto

A ordem dos chunks no contexto importa. O padrão recomendado:

```
[System Prompt — ~2.000 tokens — POSIÇÃO MAIS PRIVILEGIADA]
[Chunk 1 — mais relevante — beneficia de atenção no início]
[Chunk 2 — segundo mais relevante]
[Chunks 3 a N-1 — relevância decrescente — zona de atenção reduzida]
[Chunk N — segundo mais relevante (repetir para reforçar)]
[Pergunta do atendente — POSIÇÃO FINAL — MÁXIMA ATENÇÃO]
```

O chunk mais relevante deve aparecer tanto no início quanto próximo ao final da lista de chunks. Essa estratégia de "sandwich" mitiga o efeito lost in the middle para a informação mais crítica.

### 4.5 Implicações para estratégia de retrieval

- Retrieval inicial: buscar 20–30 candidatos por similaridade vetorial
- Reranking: usar cross-encoder para reordenar e selecionar os N melhores (N definido pelo tipo de pergunta)
- Deduplicação: remover chunks que são subconjuntos de outros antes de montar o contexto

---

## 5. Estratégia de Chunking Recomendada

### 5.1 Tipologia de perguntas dos atendentes

| Tipo | Exemplo | Características |
|---|---|---|
| **Lookup pontual** | "Qual o prazo de devolução?" | Uma resposta factual de uma seção específica |
| **Lookup com condição** | "Posso devolver carga perigosa?" | Regra com exceção — requer seção de exceções, não só regra geral |
| **Cálculo/composição** | "Frete para 800kg para o Nordeste?" | Múltiplos chunks: fórmula + multiplicador + fator de peso |
| **Multi-domínio** | "Cliente Gold, carga perigosa, prazo e custo de devolução?" | Chunks de múltiplos documentos |

### 5.2 Por que chunking por tamanho fixo é insuficiente

Chunking por tamanho fixo (ex: 512 tokens com overlap) não respeita a estrutura semântica. Uma regra que ocupa 3 parágrafos (enunciado, exceção, procedimento) pode ser dividida ao meio.

Este risco é concreto na documentação da NovaTech: a POL-001 tem uma regra geral na seção 3.1 (prazo de 7 dias) e suas exceções na seção 3.2 (cargas perigosas não elegíveis). Se o chunking por tamanho dividir essas seções e apenas a 3.1 for recuperada para a pergunta "qual o prazo de devolução para carga perigosa?", a resposta "7 dias úteis" será plausível, rastreável para o documento — e completamente errada para o caso.

### 5.3 Estratégia: Chunking Hierárquico com Metadados Semânticos

**Princípio:** Seguir a estrutura semântica do documento, não limites arbitrários de tamanho.

**Para documentos normativos (POL, PROC, SLA):**
- Chunk por seção numerada (ex: 3.1, 3.2, 3.3)
- Seções estreitamente relacionadas (regra + exceção imediata) mantidas no mesmo chunk
- Tamanho-alvo: 150–400 tokens; máximo absoluto de 600 tokens
- Prefixo de localização em cada chunk: `[POL-001 v3.1 > Seção 3 > 3.2 — Exceções ao prazo geral]`

**Para tabelas:**
- Uma tabela = um chunk atômico
- Serialização em Markdown tabular com legenda descritiva
- Legenda: `"Multiplicadores regionais para cálculo de frete especial — PROC-042-v2, nov/2023"`

**Para o FAQ:**
- Um item = um chunk
- Prefixo obrigatório: `"[FAQ-Atendimento — conhecimento prático, não validado formalmente por Compliance]"`

**Metadados obrigatórios por chunk:**
```json
{
  "chunk_id": "POL-001-3.2-a",
  "source_document": "POL-001",
  "document_version": "3.1",
  "document_date": "2024-01-15",
  "section": "3.2",
  "section_title": "Exceções ao prazo geral",
  "content_type": "rule_with_exception",
  "reliability": "official",
  "related_chunks": ["POL-001-3.1", "POL-001-3.3"],
  "supersedes": null,
  "superseded_by": null
}
```

### 5.4 Tratamento especial: documentos com versões conflitantes (PROC-042)

Este é o caso mais crítico na documentação da NovaTech. Os multiplicadores regionais da v1 e v2 são diferentes; ambas as versões coexistem no SharePoint sem hierarquia clara. O retrieval retornará chunks de ambas as versões para a mesma pergunta sobre frete.

**Estratégia técnica:**
1. Adicionar metadado `superseded_by: "PROC-042-v2"` em todos os chunks da v1
2. Adicionar metadado `supersedes: "PROC-042-v1"` em todos os chunks da v2
3. Configurar o retrieval para, ao encontrar um chunk com `superseded_by`, substituir pelo chunk equivalente da versão mais recente
4. Expor no contexto do LLM: `"[ATENÇÃO: existe versão anterior (PROC-042 v1) com valores diferentes. Os valores abaixo são da versão atual (v2, nov/2023).]"`

**Dependência crítica desta estratégia:** Ela requer que alguém adicione manualmente os metadados de supersessão na ingestão. Se esse processo não for executado, os dois documentos entrarão no vector store como equivalentes e o retrieval continuará retornando chunks conflitantes. O processo de marcação de metadados precisa ser parte do workflow de ingestão, não uma etapa opcional.

### 5.5 Tratamento do FAQ como fonte de confiabilidade diferenciada

O FAQ-Atendimento é classificado no próprio documento como "não validado por Compliance ou Operações". O sistema não pode tratá-lo como equivalente a um documento normativo.

Configurações recomendadas:
1. Todos os chunks do FAQ: `reliability: "informal"`
2. Instrução no system prompt para citar explicitamente quando a fonte é FAQ vs. documento oficial
3. Para perguntas com cobertura em documento oficial, boosting no ranking para que documentos oficiais apareçam acima do FAQ
4. Para perguntas sem cobertura oficial (ex: carga danificada, frete expresso com carga perigosa), o FAQ é a única fonte disponível — o LLM deve citar isso explicitamente ao responder

---

## 6. Riscos e Mitigações

| # | Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|---|
| 1 | Retrieval retorna chunks de PROC-042 v1 e v2 simultaneamente | Alta | Alto | Metadados de supersessão + lógica de deduplicação por versão no retrieval |
| 2 | Metadados de supersessão não são aplicados na ingestão | Alta | Alto | Tornar a marcação de versão parte obrigatória do workflow de ingestão; validação automatizada antes de publicar na base |
| 3 | OCR com erros silenciosos em documentos críticos | Média | Alto | Threshold de confiança + revisão humana para docs críticos |
| 4 | Planilha de frete atualizada sem reingesta da base | Alta | Alto | Pipeline de reingesta automática com trigger de atualização; alertas de defasagem |
| 5 | FAQ citado como fonte autoritativa | Alta | Médio | Marcação de confiabilidade + instrução no system prompt |
| 6 | Chunking dividindo regra e sua exceção em chunks separados | Média | Alto | Chunking por seção semântica, nunca por tamanho fixo |
| 7 | Latência de resposta inaceitável para uso em ligação ativa | Média | Alto | Benchmark de latência end-to-end na POC; cache de respostas para perguntas recorrentes; monitorar P95 < 3s |
| 8 | Alucinação em perguntas sem cobertura na base | Alta | Alto | Instrução explícita no system prompt: ausência de chunk relevante deve gerar "não encontrei" explícito, não geração baseada em conhecimento geral |
| 9 | Ausência de processo de curadoria da base | Alta | Alto | Definir responsável por curadoria + workflow de revisão mensal alinhado ao ciclo de atualização da documentação |
| 10 | Pergunta sobre frete < 500kg (não coberto na base) | Alta | Médio | Instrução ao LLM: quando não há cobertura, dizer explicitamente e escalar para supervisor |

### 6.1 Risco de latência — detalhamento

O pipeline completo (embedding da query → busca vetorial → reranking → montagem de prompt → geração) pode ter latência de 2-8 segundos dependendo das escolhas de implementação. Para atendentes em ligação ativa, latência acima de 3 segundos reduz a adoção da ferramenta.

Estratégias de mitigação:
- **Cache de embeddings de queries recorrentes:** As perguntas sobre prazo de devolução, SLA do cliente Gold e multiplicadores de frete serão feitas centenas de vezes por dia. Cache de resultados de retrieval elimina a busca vetorial para queries repetidas.
- **Retrieval assíncrono:** Iniciar o retrieval enquanto o atendente ainda está digitando a pergunta (streaming de texto com "pesquisando...").
- **Benchmark obrigatório na POC:** Medir latência P50 e P95 antes de ir para produção.

### 6.2 Risco de alucinação em gaps — detalhamento

Este é o risco mais perigoso e mais subestimado. Quando o pipeline não encontra chunks relevantes para uma pergunta, ele frequentemente retorna chunks parcialmente relacionados (alta similaridade semântica, mas não específicos para o caso). O LLM, recebendo esses chunks como contexto, pode construir uma resposta plausível usando informações do chunk genérico mais conhecimento geral do modelo.

Exemplo concreto da NovaTech: pergunta sobre "frete para 300kg para Salvador" (frete padrão, não coberto na base). O retrieval pode retornar chunks de PROC-042-v2 (frete especial, acima de 500kg) por similaridade semântica com "frete". Um LLM sem instrução explícita pode aplicar os multiplicadores de frete especial para uma carga de 300kg, gerando uma resposta calculada, citada com fonte — e completamente errada. Isso é pior do que "não sei".

A instrução no system prompt deve ser explícita: **se nenhum chunk no contexto trata diretamente da pergunta, responder "Não encontrei informação específica sobre isso na documentação disponível. Escale para o supervisor."**

---

## 7. Arquitetura Recomendada (visão geral)

```
[Fontes]
  SharePoint PDFs ──→ pdfplumber/Azure Doc Intelligence
  Confluence Wiki ──→ REST API + Storage Format parser
  Planilhas Rede  ──→ Microsoft Graph API (valores calculados)

[Pipeline de Ingestão]
  Extração por tipo de fonte
  → Chunking hierárquico semântico
  → Marcação de metadados (versão, confiabilidade, supersessão)
  → Geração de embeddings (text-embedding-3-large ou equivalente)
  → Armazenamento em Azure AI Search (vector store)

[Pipeline de Query]
  Pergunta do atendente
  → Embedding da query
  → Busca vetorial (top-20 candidatos)
  → Reranking com cross-encoder (selecionar top-N por tipo de pergunta)
  → Montagem de contexto (system prompt + chunks ordenados)
  → Geração (GPT-4o)
  → Resposta com citação de fonte

[Ferramentas auxiliares]
  get_frete_base() ──→ Microsoft Graph API → planilha de frete-base (para cálculos dinâmicos)
```

---

## 8. Conclusão de Viabilidade

O assistente RAG para a NovaTech é **viável dentro do orçamento de 3 meses**, com as seguintes condições inegociáveis:

1. **Tratamento diferenciado por tipo de fonte.** Tipos diferentes de conteúdo exigem pipelines de extração diferentes. Uma estratégia de "converter para texto e chunkar em N tokens fixos" é insuficiente.

2. **Resolução do problema de versões conflitantes antes do go-live.** O caso PROC-042 v1 vs v2 representa um problema sistêmico — a NovaTech atualiza documentos sem processo formal de obsolescência. O sistema precisa de metadados de versão e lógica de supersessão, e esses metadados precisam ser aplicados na ingestão de forma obrigatória, não opcional.

3. **Instrução explícita para ausência de cobertura.** O LLM deve ser instruído a responder "não encontrei" quando não há chunk específico para a pergunta — não construir respostas usando informação parcialmente relevante.

4. **Benchmark de latência na POC.** A meta de negócio (menos de 2 minutos por chamado) só é atingida se a ferramenta for rápida o suficiente para uso em ligação ativa. Latência de resposta é critério de viabilidade, não detalhe de implementação.

5. **Governança contínua da base de conhecimento.** O pipeline técnico de reingesta não resolve o problema de documentação inconsistente. É necessário um processo humano de curadoria — uma pessoa ou time responsável por garantir que a base reflita a versão atual e correta da documentação, alinhado ao ciclo mensal de atualização.

---

## Apêndice — Histórico de Iteração

### Mudanças da v1 para a v2

| Seção | Mudança | Motivação |
|---|---|---|
| Seção 3 — Estimativa de tokens | Substituída estimativa de ponto único por faixas (pessimista/base/otimista) | A premissa de 300 palavras/página não estava justificada; planilhas têm alta variabilidade |
| Seção 4.3 — Chunks por query | Substituído número fixo (5-8) por tabela variável por tipo de pergunta | Perguntas multi-domínio precisam de mais chunks; lookups simples precisam de menos |
| Seção 2.4 — Planilhas | Adicionada subseção de Function Calling para dados dinâmicos | A recomendação estava enterrada no final da seção sem desenvolvimento; é a melhor abordagem para frete-base |
| Seção 5.4 — Versões conflitantes | Adicionado parágrafo sobre dependência crítica dos metadados de supersessão | A v1 descrevia a estratégia mas não o risco de ela não ser executada |
| Seção 6 | Adicionados riscos de latência, alucinação em gaps e ausência de governança | Riscos não considerados identificados na revisão crítica |
| Seção 6.1 e 6.2 | Adicionados detalhametos de latência e alucinação | Os dois riscos mais perigosos merecem tratamento específico |
| Seção 7 | Adicionada visão geral de arquitetura | Facilita comunicação com o Tech Lead e stakeholders não-técnicos |
