# 04 — Revisão Crítica do Código (Exercício 3.1)

**Artefatos revisados:** schema Zod (Etapa 1) + `response-validator.ts` (Etapa 2)
**Método:** checklist do `03-guia-revisao-critica-3.1.md`, prioridades P0/P1/P2.

---

## Veredito resumido

O schema está correto e robusto (`.strict()`, `.min(1)`, range `[0,1]`). O validator acerta a estrutura geral — separa formato de conteúdo, nunca encaminha resposta inválida, usa pino e imports estáticos. **Porém há 1 problema P0 lógico e 2 problemas P1** que comprometem o guardrail de carga perigosa. São problemas reais, não cosméticos.

---

## Schema (Etapa 1) — aprovado

| Check | Resultado |
|-------|-----------|
| S1 — campos extras rejeitados | OK — usa `.strict()` |
| S2 — `confidence_score` com range | OK — `.min(0).max(1)` |
| S3 — strings não-vazias | OK — `.trim().min(1)` |

Nenhuma correção necessária no schema. Observação menor (P2): `.trim()` muda o valor de saída (faz coerção, não só validação) — aceitável aqui, mas vale saber que o `data` retornado vem aparado.

---

## Validator (Etapa 2) — 3 problemas a corrigir

### P0 — Brecha lógica: afirmação proibida sem palavra-gatilho passa direto

**Onde:** bloco `if (mentionsDangerousCargoAndReturn(answerText))`.

A lógica atual é:

1. Se contém negativa → aprova.
2. Senão, se contém afirmação positiva → bloqueia.
3. Senão (nem negativa nem positiva detectada) → bloqueia.

O problema está na **interação entre os passos 1 e 2 com regexes que se sobrepõem**. `AFFIRMATIVE_RETURN_PATTERN` casa `\bpode\b` e `poss[ií]vel`, e `NEGATIVE_RETURN_PATTERN` casa `não pode` / `não é possível`. Como o passo 1 é avaliado primeiro e usa `.test()` sobre a frase inteira, uma resposta que contenha **as duas coisas** — uma negativa em algum lugar e uma afirmação proibida em outro — é **aprovada** pela mera presença da negativa.

Exemplo que passa indevidamente:

> "A devolução de carga perigosa não é permitida para itens refrigerados, mas para carga perigosa comum a devolução é possível em 7 dias."

`containsRequiredNegative` retorna `true` ("não é permitida") → aprova, apesar de a frase afirmar que a devolução é possível. A negativa e a afirmação coexistem; a checagem por presença não consegue distinguir a qual sujeito cada uma se refere.

**Impacto:** o guardrail mais sensível do exercício (POL-001 §3.2) pode ser contornado. É exatamente a "inversão de regra" listada como armadilha no Anexo B.

**Correção pragmática (sem NLP):** inverter a precedência — a presença de uma **afirmação proibida** deve bloquear independentemente de haver também uma negativa. Só aprovar quando há negativa **e não há** afirmação positiva de devolução. Quando ambas aparecem, o caminho seguro é bloquear (a resposta está ambígua/contraditória e não deve chegar ao atendente).

```typescript
if (mentionsDangerousCargoAndReturn(answerText)) {
    const hasNegative = containsRequiredNegative(answerText);
    const hasPositive = containsPositiveReturnAssertion(answerText);

    // Bloqueia se afirma possibilidade — mesmo que também contenha uma negativa
    // em outra parte da frase (resposta ambígua/contraditória não é segura).
    if (hasPositive) {
        return rejectStructuredAnswer(
            "content-guardrail",
            "Structured answer rejected: response asserts a standard return is possible for dangerous cargo.",
            { source_document: structuredAnswer.source_document },
        );
    }

    // Só aprova quando há a negativa e nenhuma afirmação positiva.
    if (hasNegative) {
        return { status: "approved", response: structuredAnswer };
    }

    // Coocorrência sem negativa explícita → bloqueia (negativa obrigatória ausente).
    return rejectStructuredAnswer(
        "content-guardrail",
        "Structured answer rejected: dangerous cargo and return mentioned, required negative policy statement missing.",
        { source_document: structuredAnswer.source_document },
    );
}
```

---

### P1 — `AFFIRMATIVE_RETURN_PATTERN` casa fragmentos dentro da negativa

**Onde:** definição dos regexes de afirmação/negação.

`AFFIRMATIVE_RETURN_PATTERN` inclui `\bpode\b` e `poss[ií]vel`. Esses fragmentos estão **contidos** nas formas negativas "não **pode**" e "não é **possível**". Como os dois regexes rodam de forma independente sobre o texto, a frase "não é possível devolver carga perigosa" faz **ambos** retornarem `true`:

- `NEGATIVE_RETURN_PATTERN` → `true` (casa "não é possível")
- `AFFIRMATIVE_RETURN_PATTERN` → `true` (casa "possível" isoladamente)

Com a correção P0 acima (que prioriza o positivo), isso passaria a **bloquear uma resposta correta** — um falso positivo que inverte o problema.

**Correção:** a checagem de afirmação precisa excluir os casos em que o "possível/pode" está precedido de negação. Opções:

- Tornar a afirmação sensível à negação imediata, ex.: casar afirmação **não** precedida de "não " num raio curto. JS não tem lookbehind variável simples; alternativa robusta é **remover/neutralizar as ocorrências negadas antes** de testar a afirmação:

```typescript
function containsPositiveReturnAssertion(answer: string): boolean {
    // Remove construções negadas para não confundir "não é possível" com "é possível".
    const withoutNegations = answer.replace(
        /\bn[aã]o\s+(?:é\s+)?(?:poss[ií]vel|pode|permitid[oa]s?|autorizad[oa]s?|aceit[oa]s?)\b/gi,
        " ",
    );
    return AFFIRMATIVE_RETURN_PATTERN.test(withoutNegations);
}
```

Isso garante que "não é possível" não dispare a afirmação, enquanto "a devolução é possível" continua disparando.

---

### P1 — Cobertura de variações do gatilho é parcial (acento/ASCII e "estorno")

**Onde:** `DANGEROUS_CARGO_PATTERN` e `RETURN_PATTERN`.

Dois pontos de fragilidade prática:

1. **Texto sem acento.** Saídas de LLM e logs às vezes vêm sem acento ("devolucao", "nao e possivel"). `RETURN_PATTERN` cobre `devolu[cç][aã]o` (bom), mas `NEGATIVE_RETURN_PATTERN` exige `não` acentuado e não casa "nao". Recomenda-se **normalizar o texto** (lowercase + remoção de diacríticos) uma única vez no início e rodar todos os regexes sobre a versão normalizada, simplificando os próprios padrões:

```typescript
function normalize(text: string): string {
    return text
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "") // remove acentos
        .toLowerCase();
}
```

Com isso, `não`/`nao` e `devolução`/`devolucao` convergem, e os regexes podem dispensar as alternâncias de acento.

2. **Sinônimo de devolução.** O domínio NovaTech usa "reembolso", "frete reverso", "coleta reversa", "crédito" (POL-001 §3.3 e §3.5). Se o objetivo é só "devolução", a cobertura atual basta; se a intenção é capturar a política de reverter a entrega de carga perigosa de forma ampla, falta pelo menos "reverso/reversa". Decisão de escopo a confirmar com o Tech Lead — sinalizado, não corrigido unilateralmente.

---

## Itens verificados que estão OK (não geram correção)

- **V1 (loga mas não bloqueia):** correto — `rejectStructuredAnswer` sempre retorna `SAFE_STRUCTURED_ANSWER` com `status: "rejected"`. Bloqueia de fato.
- **V4 (JSON inválido):** tratado — `parseRawModelOutput` envolve `JSON.parse` em try/catch e retorna `undefined`, que vira rejeição `invalid-json`.
- **V5 (console.log):** OK — usa `logger.warn` (pino).
- **V6 (require dinâmico):** OK — imports estáticos no topo.
- **V7 (dado sensível em log):** OK — loga apenas `source_document` e o resumo de issues do Zod; nada de PII.
- **V8 (tipo de retorno):** OK — union discriminada `approved | rejected` com `reason`.

---

## Resumo das correções

| ID | Prioridade | Ação |
|----|-----------|------|
| P0 | Bloqueante | Inverter precedência: afirmação positiva bloqueia mesmo com negativa presente |
| P1a | Alta | Neutralizar construções negadas antes de testar afirmação positiva |
| P1b | Alta | Normalizar texto (lowercase + sem acento); avaliar sinônimos de devolução com o Tech Lead |

A distinção do exercício fica evidente: o **schema/validator é determinístico** (sempre bloqueia o que viola formato ou política), complementando o **prompt, que é probabilístico** (pode emitir uma resposta bem-formada que ainda assim afirma algo proibido). Os 3 achados acima são justamente onde a verificação determinística precisava ser endurecida para cumprir esse papel.
