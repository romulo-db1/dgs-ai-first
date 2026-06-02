# Análise de Viabilidade Técnica — Assistente de IA para Atendimento NovaTech
## Exercício 1.1 — Versão 1 (antes da revisão crítica)

**Autor:** Arquiteto de Soluções Sênior  
**Data:** 29/05/2026  
**Projeto:** Assistente RAG para time de atendimento — NovaTech / DB1  
**Status:** Rascunho para revisão

---

## 1. Resumo Executivo

A NovaTech enfrenta um problema de acesso a informações: 45 atendentes gastam em média 12 minutos por chamado consultando documentação dispersa em SharePoint, Confluence e planilhas de rede. O objetivo é construir um assistente baseado em RAG (Retrieval-Augmented Generation) que reduza esse tempo para menos de 2 minutos.

**Conclusão antecipada:** O projeto é **tecnicamente viável**, mas com riscos significativos que precisam ser gerenciados desde o design. A principal ameaça não é a tecnologia em si — é a qualidade e a consistência da documentação de origem. A NovaTech possui documentos que se contradizem entre versões, fontes com confiabilidade heterogênea, e tipos de conteúdo (tabelas complexas, fluxogramas como imagem, planilhas com fórmulas) que apresentam desafios reais de extração e representação em um pipeline de RAG.

Os riscos não tornam o projeto inviável, mas tornam inviável uma abordagem ingênua de "ingerir tudo e confiar no modelo". A solução requer engenharia cuidadosa em três frentes: extração, chunking e gerenciamento de contexto.

---

## 2. Análise por Tipo de Fonte

### 2.1 PDFs com Tabelas Complexas (15+ colunas)

**Contexto NovaTech:** Tabelas de frete com múltiplas colunas são o coração operacional do negócio. Um atendente que pergunta "qual o multiplicador para frete de 800kg para o Nordeste?" espera um valor numérico preciso. Erro aqui tem impacto financeiro direto.

**Desafio técnico:**  
Extratores de PDF tradicionais (PyMuPDF, pdfminer, pypdf) tratam tabelas como texto corrido. Uma tabela com 15 colunas frequentemente é serializada como uma sequência linear de células, perdendo completamente a estrutura de linhas e colunas. O resultado é texto como `"Sul 1.2 Sudeste 1.0 Centro-Oeste 1.3..."` sem delimitação clara de qual valor pertence a qual combinação de linha/coluna.

Quando esse texto vira um chunk e é enviado ao LLM como contexto, o modelo pode associar o multiplicador errado à região errada — especialmente se a tabela for grande e o chunk capturar apenas parte dela.

Um segundo problema: tabelas que se estendem por mais de uma página são frequentemente divididas pelo extrator no limite da página, gerando um chunk de "cabeçalho + primeiras linhas" e outro de "linhas restantes sem cabeçalho". O segundo chunk fica ilegível sem o contexto do primeiro.

**Impacto na qualidade das respostas:**  
- Alta probabilidade de valores numéricos errados em respostas sobre frete
- O modelo pode "alucinar" a estrutura da tabela ao tentar reconstruí-la a partir de texto malformado
- Chunks parciais de tabela criam respostas inconsistentes dependendo de qual chunk foi recuperado

**Estratégia de tratamento:**  
1. **Usar extrator especializado em tabelas:** Preferir `pdfplumber` ou `camelot` em vez de extratores genéricos. Ambos reconhecem estrutura tabular e exportam como DataFrame/CSV, preservando alinhamento de células.
2. **Serializar tabelas em Markdown ou JSON:** Converter cada tabela para Markdown tabular (`| Região | Multiplicador |`) antes de chunkar. Esse formato preserva a estrutura e é nativamente compreendido pelos LLMs.
3. **Tratar tabelas como chunks atômicos:** Uma tabela inteira deve ser um único chunk, mesmo que ultrapasse o tamanho-alvo de tokens. Não dividir tabelas no meio.
4. **Adicionar metadado de tipo:** Marcar chunks de tabela com `content_type: "table"` para que a lógica de retrieval possa priorizar ou filtrar conforme a natureza da pergunta.
5. **Para tabelas acima de ~300 tokens:** Replicar o cabeçalho em cada chunk se a divisão for inevitável, garantindo que linhas sem contexto de cabeçalho nunca sejam enviadas isoladas ao LLM.

---

### 2.2 PDFs Escaneados (OCR Necessário)

**Contexto NovaTech:** Documentos históricos, contratos físicos digitalizados, ou manuais antigos que não existem em formato digital nativo.

**Desafio técnico:**  
PDFs escaneados são imagens — não há texto extraível diretamente. O pipeline precisa de uma etapa de OCR (Optical Character Recognition) antes de qualquer extração de conteúdo. O problema é que OCR introduz erros que se propagam para os embeddings e para o contexto do LLM.

Erros típicos de OCR:
- Confusão entre caracteres similares: `0` e `O`, `1` e `l`, `rn` e `m`
- Palavras compostas quebradas: "frete-especial" vira "frete -especial"
- Números com casas decimais corrompidos: `1.5` vira `l.5` ou `15`
- Layout em múltiplas colunas lido como texto contínuo mesclando as colunas

Para documentos de logística, onde prazos em dias (`7 dias úteis`), multiplicadores (`1.4`) e códigos de procedimento (`PROC-042`) são críticos, um erro de OCR pode ser devastador: `1.4` virando `l.4` faz o chunk ser recuperado incorretamente por embedding de similaridade, e o valor errado ir para a resposta.

**Impacto na qualidade das respostas:**  
- Erros silenciosos: o sistema responde com confiança, mas com dados corrompidos
- Degradação de retrieval: embeddings de texto com erros de OCR têm menor similaridade com queries bem escritas
- Impossível rastrear na resposta final se o erro veio de OCR ou de lógica

**Estratégia de tratamento:**  
1. **Inventariar e isolar documentos escaneados** como categoria separada no pipeline de ingestão.
2. **Usar OCR de alta qualidade:** Azure AI Document Intelligence (disponível no Azure AI Services já contratado pela NovaTech) supera soluções open-source como Tesseract em documentos de negócio, especialmente para tabelas e layouts complexos.
3. **Revisão humana obrigatória pós-OCR** para documentos críticos (política de devolução, tabelas de SLA, tabelas de multiplicadores de frete). Implementar um workflow de validação antes da ingestão.
4. **Score de confiança de OCR como metadado:** Registrar o score de confiança do OCR por página e expô-lo no contexto enviado ao LLM — `"[AVISO: este trecho foi extraído por OCR com confiança 72%. Verifique o documento original.]"`.
5. **Estratégia de fallback:** Para documentos com OCR abaixo de threshold definido (ex: < 85% de confiança), não ingerir automaticamente. Escalar para revisão manual.

---

### 2.3 Wiki Confluence com Links Internos e Macros Customizadas

**Contexto NovaTech:** ~400 páginas wiki que podem conter procedimentos detalhados, decisões de design e conhecimento tácito do time. Links internos entre páginas são comuns (ex: "consultar PROC-088 para interceptação de carga").

**Desafio técnico:**  
O Confluence usa uma linguagem de marcação própria (Confluence Wiki Markup / Storage Format em XML) e suporta macros que renderizam conteúdo dinamicamente: painéis coloridos de aviso, tabelas de status, índices automáticos, abas. Quando se exporta uma página Confluence para texto, macros viram lixo XML ou desaparecem completamente.

Links internos (`[Consultar PROC-088|PROC-088]`) tornam-se referências mortas após extração. O chunk que diz "consulte o documento X para mais detalhes" não tem como levar o LLM até o documento X — a menos que o pipeline tenha resolvido essa referência durante a ingestão.

Outro problema: páginas Confluence frequentemente têm hierarquia de espaço → página pai → subpáginas. Esse contexto hierárquico é perdido quando cada página é tratada como documento isolado. Um procedimento que só faz sentido dentro do contexto da sua página pai pode gerar respostas confusas quando recuperado isoladamente.

**Impacto na qualidade das respostas:**  
- Respostas incompletas quando o LLM recebe um chunk que referencia outro documento sem conseguir acessá-lo
- Contexto hierárquico perdido: chunks de subpáginas sem o contexto da página pai são frequentemente ambíguos
- Macros de aviso importantes (ex: "ATENÇÃO: esta regra foi revogada em jan/2024") podem desaparecer na extração, fazendo o sistema citar regras obsoletas com confiança

**Estratégia de tratamento:**  
1. **Usar a API REST do Confluence** (não exportação em lote) para extrair páginas com controle de qualidade. A API retorna Storage Format (HTML), que pode ser parsado com BeautifulSoup preservando estrutura melhor que exportação PDF.
2. **Resolver links internos durante ingestão:** Para cada link interno encontrado, buscar o documento referenciado e criar um metadado de relacionamento `links_to: [page_id_1, page_id_2]`. Usar isso no retrieval para expandir o contexto quando necessário.
3. **Incluir breadcrumb hierárquico como prefixo de chunk:** Cada chunk começa com `[Espaço > Página Pai > Página Atual]` para garantir contexto de navegação mesmo quando o chunk é recuperado isoladamente.
4. **Tratar macros de aviso/alerta como conteúdo crítico:** Macros do tipo "Note", "Warning", "Info" devem ser extraídas explicitamente e prefixadas no chunk com `[AVISO:]`, `[IMPORTANTE:]` etc. Nunca silenciosamente descartadas.
5. **Estratégia de link expansion controlada:** Quando um chunk recuperado contém referência explícita a outro documento (ex: "consultar PROC-088"), incluir automaticamente o chunk mais relevante do documento referenciado no contexto, marcado como `[contexto expandido]`.

---

### 2.4 Planilhas com Fórmulas Interdependentes

**Contexto NovaTech:** Planilhas de referência atualizadas mensalmente — provavelmente tabelas de frete-base (valor base para os cálculos de PROC-042), tabelas de prazo por rota, ou tabelas de SLA customizadas.

**Desafio técnico:**  
Este é o tipo de fonte **mais problemático para RAG**, e o risco é sistematicamente subestimado.

O problema fundamental: planilhas com fórmulas têm dois tipos de "conteúdo" — os **valores** (o que o usuário vê na célula após o cálculo) e as **fórmulas** (a lógica que gerou esses valores). Um pipeline de RAG ingere texto. Se a extração captura as fórmulas (`=SE(B2>500;VLOOKUP(C2,TabelaBase,3,0)*1.2;...)`), o LLM recebe um conjunto de expressões matemáticas sem contexto. Se captura apenas os valores calculados, captura um snapshot estático — que fica desatualizado quando a planilha é editada mas o pipeline não é reexecutado.

Planilhas com fórmulas interdependentes são ainda mais críticas: uma célula depende de outra, que depende de uma terceira em outra aba. A "resposta" para uma pergunta pode estar distribuída em múltiplas abas e linhas, com a lógica nos relacionamentos entre elas, não em nenhuma célula específica.

Adicionalmente, planilhas frequentemente usam formatação visual como semântica: células verdes = ativas, células vermelhas = descontinuadas, negrito = atenção. Toda essa semântica desaparece na extração de texto.

**Impacto na qualidade das respostas:**  
- Respostas sobre valores de frete podem estar desatualizadas se a planilha foi atualizada mas o pipeline não reprocessou
- Fórmulas complexas enviadas como texto ao LLM geram respostas confusas ou incorretas
- Semântica visual perdida: o sistema pode recomendar uma tarifa descontinuada que estava marcada em vermelho na planilha

**Estratégia de tratamento:**  
1. **Não ingerir fórmulas — ingerir apenas valores calculados**, com timestamp de extração como metadado obrigatório: `"extração_em: 2024-01-15T08:00:00"`.
2. **Converter tabelas de planilha para Markdown tabular** antes de chunkar — o mesmo tratamento das tabelas em PDF.
3. **Implementar pipeline de reingesta automática:** Toda vez que uma planilha for atualizada na pasta de rede, disparar automaticamente o reprocessamento e atualização dos chunks correspondentes. A atualização mensal das planilhas de frete exige que esse pipeline seja confiável.
4. **Para lógica de cálculo complexa:** Não tentar extrair a lógica das fórmulas para o RAG. Em vez disso, documentar em texto a lógica relevante (ex: "o valor base é o resultado da célula C15 da aba 'Frete-Base' da planilha mensal") e enriquecer o chunk com essa descrição.
5. **Criar alertas de defasagem:** Se um chunk derivado de planilha tem mais de X dias sem atualização, adicionar aviso no contexto enviado ao LLM: `"[DADO POSSIVELMENTE DESATUALIZADO: última extração há 35 dias. Verificar planilha original.]"`.
6. **Considerar uma alternativa ao RAG para dados tabulares dinâmicos:** Para consultas que envolvem cálculo (ex: "qual o frete para 800kg para o Nordeste?"), avaliar a viabilidade de uma ferramenta de consulta direta à planilha (via API, não RAG) que o LLM chame como function call. Esse approach garante dados sempre atualizados e cálculos corretos.

---

## 3. Estimativa de Tamanho da Base em Tokens

### 3.1 Premissas de cálculo

Regra fornecida: **1 token ≈ 0,75 palavras** (ou, equivalentemente, 1 palavra ≈ 1,33 tokens).

Para PDFs, usa-se a estimativa padrão de **300 palavras por página** para documentos de negócio com tabelas e formatação (documentos densos de texto chegam a 400-500; documentos com muitas tabelas/imagens ficam em 200-250; 300 é uma média conservadora e razoável).

### 3.2 Cálculo por fonte

**PDFs do SharePoint:**
- Volume: 800 documentos × 10 páginas/documento = 8.000 páginas
- Palavras: 8.000 páginas × 300 palavras/página = 2.400.000 palavras
- Tokens: 2.400.000 ÷ 0,75 = **3.200.000 tokens** (~3,2M tokens)

**Wiki Confluence:**
- Volume: 400 páginas × 1.500 palavras/página = 600.000 palavras
- Tokens: 600.000 ÷ 0,75 = **800.000 tokens** (~800K tokens)

**Planilhas de rede:**
- Volume: 50 planilhas. Premissa: planilhas de referência de logística tipicamente têm 2-5 abas com tabelas de 50-200 linhas. Estimando 1.000 palavras por planilha (valores de células + cabeçalhos + metadados descritivos adicionados na extração).
- Palavras: 50 × 1.000 = 50.000 palavras
- Tokens: 50.000 ÷ 0,75 = **~67.000 tokens** (~67K tokens)

### 3.3 Total e implicações

| Fonte | Documentos/Páginas | Palavras estimadas | Tokens estimados |
|---|---|---|---|
| PDFs SharePoint | 800 docs / 8.000 páginas | 2.400.000 | 3.200.000 |
| Wiki Confluence | 400 páginas | 600.000 | 800.000 |
| Planilhas | 50 arquivos | 50.000 | 67.000 |
| **Total** | | **3.050.000** | **~4.067.000** |

**A base total tem aproximadamente 4 milhões de tokens.**

Isso significa que a base **não cabe integralmente na janela de contexto de nenhum modelo atual** (GPT-4o tem 128K tokens, Claude tem até 200K). Isso não é um problema — é a premissa fundamental que justifica o uso de RAG em vez de "colocar tudo no contexto". O RAG existe exatamente para selecionar os ~2.000-5.000 tokens relevantes dentre os 4 milhões da base.

A implicação prática é que a **qualidade do retrieval é o determinante principal da qualidade das respostas** — mais do que o modelo de geração em si. Um modelo de geração mediano com retrieval excelente supera um modelo de geração excelente com retrieval ruim.

---

## 4. Análise de Orçamento de Contexto

### 4.1 Anatomia do contexto por query

Com GPT-4o (128K tokens de janela), o orçamento de contexto por query tem a seguinte estrutura:

| Componente | Tokens estimados | Tipo |
|---|---|---|
| System prompt (identidade, regras, guardrails, instruções de formato) | ~1.500 | Estático |
| Instruções de uso dos chunks (como interpretar, como citar) | ~500 | Estático |
| **Total estático** | **~2.000** | |
| Histórico da conversa (3-5 turnos anteriores) | ~1.000–2.500 | Dinâmico |
| Dados do atendente/contexto do chamado (cliente, tier, histórico) | ~300–500 | Dinâmico |
| Chunks recuperados | variável | Dinâmico |
| Pergunta atual do atendente | ~50–150 | Dinâmico |
| **Margem para resposta do modelo** | ~1.000–2.000 | Saída |

**Orçamento disponível para chunks:** 128.000 − 2.000 (estático) − 2.000 (histórico + contexto) − 100 (pergunta) − 1.500 (margem de resposta) ≈ **~122.000 tokens** em teoria.

### 4.2 Por que não usar todos os 122K tokens para chunks

Matematicamente, caberiam **~244 chunks de 500 tokens** no orçamento disponível. Isso parece muito espaço, e é uma armadilha clássica.

O problema é o **efeito "lost in the middle"** (Shi et al., 2023; Liu et al., 2023): LLMs têm uma atenção não-uniforme ao longo do contexto. Informações posicionadas no início ou no final do contexto recebem muito mais atenção do modelo do que informações no meio. Em experimentos, a precisão de modelos em responder perguntas sobre informações no meio de um contexto longo cai 15-30% em comparação com informações nas extremidades.

Para o assistente da NovaTech, isso é especialmente crítico porque as respostas dependem de **valores numéricos precisos** (multiplicadores de frete, prazos em dias, valores de SLA) que são exatamente o tipo de conteúdo que se perde quando enterrado no meio de 244 chunks.

### 4.3 Orçamento recomendado na prática

O recomendado pela literatura e experiência prática é trabalhar com **5 a 8 chunks por query**, posicionados estrategicamente:

```
[System Prompt - 2.000 tokens]
[Chunk mais relevante — posição 1 — início do contexto]
[Chunk 2]
[Chunk 3]
[Chunks 4-6 — posição menos privilegiada]
[Chunk 7-8 — posição de relativa atenção]
[Pergunta do atendente — posição final — MÁXIMA atenção]
```

Com chunks de 500 tokens, isso representa 2.500–4.000 tokens de documentação por query — uma fração mínima do orçamento disponível, mas suficiente para manter a qualidade de atenção alta.

O orçamento não usado não é desperdício: é a garantia de que o modelo processa os chunks com alta qualidade de atenção.

### 4.4 Implicações para estratégia de chunking e retrieval

- **Chunks menores e mais focados** são preferíveis a chunks grandes que "garantem que tudo está lá": um chunk de 200 tokens com a informação exata é melhor que um de 1.000 tokens onde a informação é um parágrafo no meio.
- **Retrieval preciso** é mais importante que retrieval amplo: recuperar 5 chunks certos é melhor que recuperar 20 chunks dos quais 5 são corretos.
- **Reranking** (pós-retrieval) é recomendado: recuperar 20 candidatos por similaridade vetorial, depois usar um cross-encoder para reordenar e selecionar os 5-8 melhores, posicionando os mais relevantes no início e no final do contexto.

---

## 5. Estratégia de Chunking Recomendada

### 5.1 Tipologia de perguntas dos atendentes

Antes de definir chunking, é preciso entender o que os atendentes perguntam. Com base no cenário e nos documentos da NovaTech, as perguntas se encaixam em 4 tipos:

| Tipo | Exemplo | Características |
|---|---|---|
| **Lookup pontual** | "Qual o prazo de devolução?" | Uma resposta numérica/factual de uma seção específica |
| **Lookup com condição** | "Posso devolver carga perigosa?" | Regra com exceção — requer ler a seção de exceções, não só a regra geral |
| **Cálculo/composição** | "Frete para 800kg para o Nordeste?" | Requer múltiplos chunks (fórmula + multiplicador + fator de peso) |
| **Multi-domínio** | "Cliente Gold, carga perigosa, prazo e custo de devolução?" | Requer chunks de múltiplos documentos |

### 5.2 Problemas com abordagens simples

**Chunking por tamanho fixo (ex: 512 tokens com overlap):**  
Não respeita a estrutura semântica dos documentos. Uma regra que ocupa 3 parágrafos (enunciado, exceção, procedimento) pode ser dividida ao meio. Um atendente que pergunta sobre a exceção pode receber o chunk que contém apenas a regra geral — sem a exceção que invalida a regra para o caso específico.

Este é exatamente o risco identificado na documentação da NovaTech: a POL-001 tem uma regra geral na seção 3.1 e suas exceções na seção 3.2. Se esses forem chunks separados e apenas a seção 3.1 for recuperada para a pergunta "qual o prazo de devolução para carga perigosa?", a resposta "7 dias úteis" estará tecnicamente presente no documento — mas será completamente errada para o caso perguntado.

### 5.3 Estratégia recomendada: Chunking Hierárquico com Metadados Semânticos

**Princípio geral:** Seguir a estrutura semântica do documento, não limites arbitrários de tamanho.

**Para documentos normativos (POL, PROC, SLA):**
- Chunk por seção numerada (ex: seção 3.1, seção 3.2, seção 3.3)
- Se uma seção tiver subseções estreitamente relacionadas (ex: "regra geral" + "exceções à regra geral"), mantê-las no mesmo chunk
- Tamanho-alvo: 150–400 tokens por chunk; máximo absoluto de 600 tokens
- Incluir no chunk: título da seção, conteúdo, e contexto de localização `[POL-001 > Seção 3 > 3.2]`

**Para tabelas:**
- Uma tabela = um chunk atômico, independente do tamanho
- Serializar em Markdown tabular
- Adicionar legenda descritiva antes da tabela: `"Multiplicadores regionais para cálculo de frete especial (PROC-042-v2, atualizado novembro/2023)"`

**Para o FAQ:**
- Um item de FAQ = um chunk
- Prefixar com indicador de fonte informal: `"[FAQ-Atendimento — conhecimento prático não validado formalmente]"`

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

**Tratamento especial para documentos com versões conflitantes (PROC-042 v1 vs v2):**

Este é o caso mais crítico na documentação da NovaTech. Ambas as versões do PROC-042 coexistem sem hierarquia clara. O pipeline **não pode** tratar isso como dois documentos equivalentes — caso contrário, o retrieval vai retornar chunks de ambas as versões para a mesma pergunta, e o LLM vai mixar multiplicadores antigos e novos.

Estratégia recomendada:
1. Adicionar metadado `superseded_by: "PROC-042-v2"` em todos os chunks da v1
2. Adicionar metadado `supersedes: "PROC-042-v1"` em todos os chunks da v2
3. Configurar o retrieval para, quando encontrar um chunk marcado como `superseded_by`, automaticamente substituir pelo chunk equivalente na versão mais recente
4. Expor explicitamente no contexto do LLM: `"[ATENÇÃO: existe uma versão anterior deste documento (PROC-042 v1) com valores diferentes. Os valores abaixo são da versão atual (v2, nov/2023).]"`

**Tratamento especial para o FAQ:**
O FAQ-Atendimento é classificado no próprio documento como "não validado por Compliance ou Operações". O pipeline deve:
1. Marcar todos os chunks do FAQ com `reliability: "informal"`
2. Configurar o LLM para citar explicitamente quando a fonte é o FAQ vs. um documento oficial
3. Para perguntas onde existe documento oficial, priorizar o documento oficial no ranking de chunks — o FAQ deve aparecer apenas como fonte complementar ou quando não há cobertura oficial

---

## 6. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Pipeline retorna chunks de versões conflitantes (PROC-042 v1 e v2) | Alta | Alto | Metadados de versão + lógica de supersessão no retrieval |
| OCR com erros silenciosos em documentos críticos | Média | Alto | Threshold de confiança + revisão humana para docs críticos |
| Planilha de frete atualizada sem reingesta | Alta | Alto | Pipeline de reingesta automática com trigger de atualização |
| FAQ citado como fonte autoritativa | Alta | Médio | Marcação de confiabilidade + instrução no system prompt |
| Chunking dividindo regra e sua exceção | Média | Alto | Chunking por seção semântica, não por tamanho |
| Pergunta sobre frete < 500kg (não coberta na base) | Alta | Médio | Instrução ao LLM: quando não há cobertura, dizer explicitamente |
| Fluxogramas embutidos como imagens (sem extração) | Alta | Baixo-Médio | Identificar e documentar gaps; não ingerir imagens na v1 |

---

## 7. Conclusão de Viabilidade

O assistente RAG para a NovaTech é **viável** dentro do orçamento de 3 meses, com as seguintes condições:

1. **Não tratar todos os documentos como iguais.** Tipos diferentes de conteúdo exigem pipelines de extração diferentes. Uma estratégia única de "converter para texto e chunkar em N tokens" é insuficiente e produzirá resultados não-confiáveis.

2. **Resolver o problema de versões conflitantes antes do go-live.** O caso PROC-042 v1 vs v2 não é um edge case — é representativo de um problema sistêmico (documentação atualizada sem processo de obsolescência). O assistente precisa de uma estratégia explícita para lidar com contradições, ou se tornará uma fonte de inconsistências ainda maior do que o processo atual.

3. **O sucesso do projeto é mais dependente de engenharia de dados do que de escolha de modelo.** A seleção entre GPT-4o, Claude 3.5, ou qualquer outro modelo de geração terá impacto menor do que a qualidade do pipeline de extração, chunking e retrieval. Alocar mais tempo de desenvolvimento nas etapas anteriores à geração.

4. **Planejar um ciclo contínuo de manutenção.** Com 3 áreas atualizando documentação mensalmente sem processo unificado, o pipeline de ingestão não é um projeto de uma vez — é uma operação contínua. O go-live sem um processo de manutenção sustentável garante degradação progressiva da qualidade das respostas.

---
*Fim da Análise v1 — Próximo passo: revisão crítica com Claude para identificar pontos fracos*
