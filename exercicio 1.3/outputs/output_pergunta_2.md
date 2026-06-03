# Consulta NovaTech Assistente

**Data:** 03/06/2026  
**Sistema:** NovaTech Assistente — Atendimento Interno  

---

## Pergunta do Atendente

> Quanto custa o frete para 600kg para Manaus?

---

## Resposta

### [Resposta direta]

Não é possível calcular o valor final do frete. A fórmula está disponível nos chunks, mas o Multiplicador Regional para Manaus não consta na documentação recuperada.

### [Fundamento]

Conforme PROC-042-v2, Seção 2 (chunk PROC-042-v2-2), a fórmula é:

```
Valor do frete = Valor base × Multiplicador regional × Fator de peso
```

Para uma carga de 600kg, o Fator de peso é **1.0** (faixa de 500kg a 1.000kg, conforme PROC-042-v2, Seção 2). O Valor base deve ser consultado na tabela mensal de fretes vigente. O Multiplicador regional para Manaus está definido na Seção 2.1 do PROC-042-v2, que não foi recuperada nos chunks disponíveis.

### [Observações]

Existem duas versões do PROC-042 no contexto. Apliquei a v2 (mais recente). Se o contrato do cliente é anterior a 12/2023, valide com o Comercial.

A diferença relevante entre as versões está nos fatores de peso:

| Faixa de peso         | PROC-042 (versão anterior) | PROC-042-v2 (versão atual) |
|-----------------------|----------------------------|----------------------------|
| 500kg a 1.000kg       | 1.0                        | 1.0                        |
| 1.001kg a 3.000kg     | 1.2                        | 1.15                       |
| Acima de 3.000kg      | 1.5                        | 1.4                        |

Para a carga em questão (600kg), ambas as versões coincidem no fator 1.0, portanto a divergência não afeta este cálculo específico.

**Para concluir o cálculo**, consulte:
- Seção 2.1 do PROC-042-v2 → Multiplicador Regional de Manaus
- Tabela mensal de fretes vigente → Valor base

---

*Registro gerado pelo NovaTech Assistente — uso interno.*
