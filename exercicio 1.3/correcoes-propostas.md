# Problemas Identificados e Propostas de Correção

**Exercício 1.3 — Pipeline de RAG NovaTech**

Os 5 testes evidenciaram que o pipeline atende bem ao caso geral — retrieval semântico recupera os chunks corretos em 4 de 5 perguntas, e o LLM seguindo o prompt v3 produz respostas corretas mesmo quando o retrieval falha parcialmente. Mas dois problemas concretos apareceram nas respostas, e dois outros são limitações arquiteturais conhecidas que ainda não estão materializadas mas vão aparecer em produção. Esta seção lista os quatro com proposta de correção.

---

## Problema 1 — Chunk crítico não recuperado em P2 (multiplicadores regionais)

**Evidência:** P2 perguntou "Quanto custa o frete para 600kg para Manaus?". O chunk `PROC-042-v2-2.1`, que contém a tabela de multiplicadores regionais (onde está "Norte = 1.8"), **não entrou no top 5**. A fórmula geral (`PROC-042-v2-2`) veio em 1º, mas a tabela específica ficou fora.

**Causa raiz provável:** O chunk `PROC-042-v2-2.1` é majoritariamente tabular — texto curto, denso em valores numéricos, com pouca variedade lexical. Para um modelo de embedding, esse tipo de conteúdo gera um vetor menos "rico" semanticamente comparado a chunks de prosa. A pergunta "Quanto custa o frete para 600kg para Manaus?" tem similaridade alta com chunks que falam de "fórmula", "cálculo", "peso" (prosa) e similaridade menor com a tabela em si — mesmo que a tabela seja exatamente o que o atendente precisa.

Este é um caso conhecido na literatura de RAG: **tabelas pequenas têm representação vetorial fraca**. A análise 1.1 §2.1 menciona o problema em outro contexto (extração de tabelas de PDFs), mas o problema vetorial é diferente — não é sobre estrutura preservada, é sobre densidade semântica do embedding.

**Proposta de correção:**

1. **Enriquecer chunks tabulares com contexto descritivo.** No momento da ingestão, prefixar tabelas com uma frase descritiva gerada a partir do título e do contexto da seção. Para o `PROC-042-v2-2.1`, o prefixo seria algo como: "Esta tabela define os multiplicadores regionais usados no cálculo de frete especial para cada região do Brasil — Sul, Sudeste, Centro-Oeste, Nordeste e Norte." Esse prefixo aumenta o vocabulário semântico do chunk sem alterar os valores numéricos.

2. **Boosting por relação semântica entre chunks irmãos.** Quando o retrieval recupera um chunk `§X` (ex: `PROC-042-v2-2` — fórmula), aumentar artificialmente o score do chunk filho `§X.Y` (ex: `PROC-042-v2-2.1` — tabela de multiplicadores) que aparece em top-N candidatos. Essa lógica usa o metadado `section` que já está disponível por chunk. Implementação é uma função pós-retrieval que opera sobre top-20 candidatos antes de reduzir para top-5.

3. **Aumentar top_k para perguntas de cálculo.** A análise 1.1 §4.3 recomenda 4-6 chunks para cálculos. O pipeline atual usa top_k=5 fixo. Implementar a classificação leve de tipo de pergunta proposta (palavras como "quanto custa", "calcule", "valor") e aumentar para 6-8 quando for cálculo, dando mais chance ao chunk de multiplicadores entrar.

**Impacto esperado:** O chunk de multiplicadores entra no contexto em perguntas de frete. A resposta para P2 passa a incluir "Norte = 1.8" e o atendente recebe `Valor = base × 1.8 × 1.0` com apenas o valor base como dado faltante (em vez de dois dados).

**Esforço:** 1 dia de dev para implementar todas as três medidas + testes regressivos.

---

## Problema 2 — Mistura de domínios em P4 (carga danificada vs carga perigosa)

**Evidência:** P4 perguntou "O que acontece quando a carga chega danificada?". O LLM respondeu corretamente sobre o fluxo de sinistros (FAQ-38), mas **incluiu na `[Resposta direta]` uma menção a "carga perigosa ou lacre violado → ramal 4500"**, vinda do `POL-001-3.2`. Carga danificada e carga perigosa são cenários distintos — danificada é problema de transporte; perigosa é categoria de mercadoria.

**Causa raiz:** O retrieval trouxe `POL-001-3.2` em 2º lugar porque o chunk fala sobre exceções a devolução, e essas exceções incluem "lacre violado" — termo que tem proximidade semântica com "danificada". O prompt v3 instrui o LLM a ler todos os chunks e verificar se há chunks que se complementam. O LLM seguiu a instrução, conectou "lacre violado" a "carga danificada" e produziu uma resposta integrada. Em alguns casos essa integração é desejável (P3, onde FAQ e SLA combinaram bem); aqui ela é forçada.

**Proposta de correção:**

1. **Reranking com cross-encoder.** Esta é a correção principal. Um cross-encoder (ex: `BAAI/bge-reranker-v2-m3`, open-source e multilíngue) avalia a relevância de cada chunk em relação à pergunta de forma muito mais precisa que cosine similarity. Para P4, o reranker provavelmente posicionaria `POL-001-3.2` em uma posição muito abaixo, ou o eliminaria do top 5 — porque ele "entende" que a pergunta é sobre carga danificada, não sobre categorias de carga em geral. Implementação: top-20 por similaridade vetorial → reranking → top-N final.

2. **Instrução adicional no prompt sobre integração de chunks.** Reforçar no prompt v3 que chunks de tópicos relacionados mas não diretamente cobertos pela pergunta devem ser mencionados em `[Observações]` separadamente, não integrados na `[Resposta direta]`. Hoje a instrução é "leia todos os chunks e veja se se complementam", o que abre espaço para integração indevida.

**Impacto esperado:** Respostas mais focadas na pergunta exata, sem ruído de tópicos próximos. O atendente sob pressão de tempo não precisa filtrar.

**Esforço:** 1 dia para integrar o cross-encoder; algumas horas para ajustar o prompt.

---

## Problema 3 — Pipeline não tem lógica de supersessão de versões (PROC-042 v1 e v2 coexistem)

**Evidência:** Em P1, P2 e P5, chunks de ambas as versões do PROC-042 apareceram no top 5 simultaneamente. O prompt v3 mitiga via aviso obrigatório de versões coexistentes, mas isso depende inteiramente do LLM perceber pelo padrão dos identificadores (`PROC-042-N` vs `PROC-042-v2-N`).

Em P1 (devolução de carga perigosa), o aviso de versões apareceu na resposta — mesmo sendo **irrelevante para a pergunta**, já que a pergunta é sobre POL-001, não PROC-042. O LLM disparou o aviso porque os dois chunks de PROC-042 estavam no contexto, ainda que como ruído.

**Causa raiz:** O pipeline atual armazena `version: "v1"` e `version: "v2"` como metadado, mas não tem **lógica de supersessão**. Este é exatamente o cenário previsto na análise 1.1 §5.4: "Esta estratégia requer que alguém adicione manualmente os metadados de supersessão na ingestão. Se esse processo não for executado, os dois documentos entrarão no vector store como equivalentes."

**Proposta de correção:**

1. **Estender o `DOC_REGISTRY`** com relações de supersessão explícitas:
   ```python
   "PROC-042-frete-especial-v1.md": {
       "doc_id": "PROC-042",
       "version": "v1",
       "superseded_by": "PROC-042-v2",   # NOVO
   },
   "PROC-042-v2-frete-especial-revisado.md": {
       "doc_id": "PROC-042-v2",
       "version": "v2",
       "supersedes": "PROC-042",   # NOVO
   },
   ```

2. **Filtrar no retrieval.** Modificar a função `search()` para que, após obter o top_k inicial, remova chunks cujo `superseded_by` aponta para um documento que **também está** entre os resultados. Apenas quando a v2 não estiver presente é que a v1 é mantida (cenário de fallback raro).

3. **Avisar o LLM via metadado no prompt.** Quando o pipeline detectar versões coexistentes (mesmo após filtro), injetar no contexto: `"[AVISO DO PIPELINE: detectadas múltiplas versões do PROC-042. Apliquei filtro de supersessão; apenas v2 está presente abaixo.]"` Isso é mais robusto do que confiar no LLM perceber pelos identificadores.

**Impacto esperado:** Em P1 (pergunta sobre devolução), os chunks de PROC-042 v1 não chegam ao contexto — eliminam-se ruído e aviso irrelevante. Em P2 e P5 (perguntas sobre frete), só a v2 chega, e o LLM trabalha com uma única tabela.

**Limitação a aceitar:** Esta correção depende de o registro estar correto. Se a NovaTech publicar uma `v3` e ninguém atualizar o registro, a v2 vira "atual" indevidamente. Isso conecta com o problema de **governança da base** levantado na análise 1.1 §6.1 (risco #9). O pipeline pode automatizar o filtro, mas não pode descobrir sozinho qual é a versão correta.

**Esforço:** Meio dia de dev.

---

## Problema 4 — top_k fixo em 5 ignora a recomendação de orçamento variável por tipo de pergunta

**Evidência:** A análise 1.1 §4.3 recomenda 2-3 chunks para lookup pontual, 4-6 para cálculo, 6-10 para multi-domínio. O pipeline atual usa `top_k=5` em todos os casos.

Em P4 (lookup pontual sobre carga danificada), 5 chunks foram demais — o FAQ-Item 38 estava claramente sozinho à frente e os outros 4 viraram ruído que contribuíram para a mistura de domínios (Problema 2). Em P2 (cálculo de frete), 5 chunks foi pouco — o chunk de multiplicadores (`PROC-042-v2-2.1`) ficou fora.

**Causa raiz:** Falta de classificação do tipo de pergunta antes do retrieval.

**Proposta de correção:**

Implementar um **classificador leve de tipo de pergunta** antes da busca. Pode ser heurística por palavras-chave:

```python
def classify_question(question: str) -> tuple[str, int]:
    """Retorna (tipo, top_k_recomendado)."""
    q = question.lower()
    if any(w in q for w in ["quanto custa", "valor", "calcule", "calcular", "preço", "frete para"]):
        return ("calculation", 7)
    if " e " in q or q.count("?") > 1 or len(q.split()) > 25:
        return ("multi-domain", 8)
    return ("lookup", 3)
```

Heurística simples já cobre bem para POC. Em produção, evolui para classificador treinado com perguntas reais.

**Impacto esperado:**
- P1, P3, P4 com `top_k=3`: contexto mais limpo, menos ruído lateral.
- P2 e P5 com `top_k=7`: chance maior de capturar chunks de seções vizinhas (multiplicadores, condições especiais) sem aumentar muito o ruído.

**Esforço:** Poucas horas de dev. A heurística é trivial e o pipeline já aceita `top_k` como parâmetro.

**Limitação:** A heurística por keywords pode classificar errado. Vale instrumentar telemetria em produção (qual `top_k` foi escolhido, qual era a pergunta) para iterar.

---

## Síntese — priorização das correções

| # | Problema | Manifestou-se em | Esforço | Impacto | Prioridade |
|---|---|---|---|---|---|
| 1 | Chunk tabular não recuperado | P2 | 1 dia | Alto — destrava cálculo end-to-end | **P0** |
| 2 | Mistura de domínios via chunks tematicamente próximos | P4 (e P1 em menor grau) | 1 dia | Alto — reduz ruído sistemático | **P0** |
| 3 | Sem lógica de supersessão | P1, P2, P5 | Meio dia | Médio — limpa contexto de versões obsoletas | P1 |
| 4 | top_k fixo | P2, P4 | Poucas horas | Médio — refina sem mudar fundamentos | P1 |

O caminho recomendado é P0 primeiro. As duas correções de P0 são complementares e juntas atacam a fragilidade central do retrieval atual: chunks recuperados ou por proximidade lexical superficial (P4 — "lacre violado" próximo de "danificada") ou por densidade vetorial baixa de tabelas (P2 — multiplicadores não recuperados). Reranking com cross-encoder resolve P4; enriquecimento descritivo de tabelas + boosting por seção-irmã resolve P2.

Depois de aplicar P0 e P1, vale rodar a bateria de 20-30 perguntas-gabarito recomendada no Ex. 1.2 §6.3, com métricas regressivas (recall must-have, taxa de invenção, taxa de citação correta, taxa de mistura de domínios).

---

## O que esta POC não resolve (e nem deveria, por design)

Vale demarcar o que **fica fora do escopo** desta camada do projeto, em linha com a análise 1.1:

- **OCR de documentos escaneados** (análise 1.1 §2.2): premissa: documentos chegam em texto. POCs com docs escaneados exigem Azure Document Intelligence.
- **Tabelas complexas com 15+ colunas em PDFs** (análise 1.1 §2.1): a documentação da NovaTech usada aqui já estava em markdown limpo. Em produção, extração de PDF com tabelas exige pdfplumber/camelot.
- **Dados dinâmicos** (planilhas de frete-base atualizadas mensalmente — análise 1.1 §2.4): tratados via function calling, não RAG estático. Fora do escopo desta POC.
- **Latência sob carga** (análise 1.1 §6.1): nenhum benchmark de latência foi feito; pipeline rodou sequencialmente para fins de teste. Antes do go-live, medir P50 e P95 com carga simulada.
- **Curadoria contínua da base** (análise 1.1 §6.1, risco #9): este é um problema humano, não técnico. O pipeline pode automatizar reingesta, mas não pode determinar sozinho qual versão está correta.

Esses limites não são falhas do pipeline — são frentes complementares de trabalho que a arquitetura final precisa cobrir.
