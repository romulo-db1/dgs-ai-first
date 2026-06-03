"""
Roda os 5 testes do exercício 1.3 e gera o relatório de resultados.

Para cada pergunta:
1. Executa busca no pipeline (top_k=5).
2. Captura chunks recuperados e scores.
3. Compara com o gabarito do Anexo B.
4. Monta o prompt completo (system_prompt_v3 + chunks + pergunta).
5. Salva o prompt em arquivo para ser colado no Claude (chat).
6. Escreve análise no relatório consolidado.
"""

from pathlib import Path
from rag_pipeline import (
    ingest_all_documents,
    search,
    build_prompt,
    load_system_prompt,
    format_search_results,
)

# ----------------------------------------------------------------------
# Gabarito do Anexo B — chunks esperados por pergunta
# ----------------------------------------------------------------------
# Os IDs do Anexo B usam letras (POL-001-B = seção 3.2). Aqui traduzo
# para os IDs do meu pipeline (POL-001-3.2). Mapeamento manual:
#
# Anexo B → Meu pipeline
# POL-001-A (seção 3.1) → POL-001-3.1
# POL-001-B (seção 3.2) → POL-001-3.2
# POL-001-C (seção 3.3) → POL-001-3.3
# POL-001-D (seção 3.5) → POL-001-3.5
# PROC-042-A (fórmula) → PROC-042-2
# PROC-042-B (multiplicadores) → PROC-042-2.1
# PROC-042v2-A (fórmula v2) → PROC-042-v2-2
# PROC-042v2-B (mult v2) → PROC-042-v2-2.1
# SLA-2024-A (classificação) → SLA-2024-1
# SLA-2024-B/C (SLAs) → SLA-2024-2
# SLA-2024-D (incidente crítico) → SLA-2024-3
# FAQ-03/15/38 → FAQ-Atendimento-Item 3/15/38

TESTS = [
    {
        "id": "T1",
        "question": "Qual o prazo de devolução para carga perigosa?",
        "expected_must_have": ["POL-001-3.2"],
        "expected_nice_to_have": ["POL-001-3.1", "FAQ-Atendimento-Item 3"],
        "armadilha": "Regra geral (7 dias) vs exceção que invalida (carga perigosa não elegível).",
    },
    {
        "id": "T2",
        "question": "Quanto custa o frete para 600kg para Manaus?",
        "expected_must_have": ["PROC-042-v2-2.1", "PROC-042-v2-2"],
        "expected_nice_to_have": ["PROC-042-2.1", "PROC-042-2"],  # versão antiga — risco de contradição
        "armadilha": "Cálculo com duas versões coexistindo. Pipeline pode trazer multiplicadores conflitantes.",
    },
    {
        "id": "T3",
        "question": "Qual o SLA do cliente Platinum?",
        "expected_must_have": ["SLA-2024-1"],  # contém "não existem outros tiers"
        "expected_nice_to_have": ["FAQ-Atendimento-Item 15"],
        "armadilha": "Tier inexistente. Resposta correta: dizer que não existe e que só há Gold/Silver/Standard.",
    },
    {
        "id": "T4",
        "question": "O que acontece quando a carga chega danificada?",
        "expected_must_have": ["FAQ-Atendimento-Item 38"],
        "expected_nice_to_have": [],
        "armadilha": "Única fonte é o FAQ informal. LLM deve sinalizar que a fonte não é validada formalmente.",
    },
    {
        "id": "T5",
        "question": "Quanto custa o frete para 300kg para Salvador?",
        "expected_must_have": [],  # frete padrão < 500kg não está documentado
        "expected_nice_to_have": [],
        "armadilha": "Sem cobertura na base. Pipeline tende a retornar PROC-042 (frete especial > 500kg) por similaridade lexical.",
    },
]


def evaluate_recall(expected: list[str], retrieved: list[str]) -> dict:
    """Compara chunks esperados vs recuperados."""
    found = [c for c in expected if c in retrieved]
    missing = [c for c in expected if c not in retrieved]
    return {"found": found, "missing": missing, "recall_pct": (len(found) / len(expected) * 100) if expected else None}


def run_all_tests():
    # Garante ingestão fresca
    print("=" * 70)
    print("INGESTÃO")
    print("=" * 70)
    ingest_all_documents(reset=True)

    print("\n" + "=" * 70)
    print("EXECUÇÃO DOS TESTES")
    print("=" * 70)

    system_prompt = load_system_prompt()
    output_dir = Path("./outputs")
    output_dir.mkdir(exist_ok=True)

    report_sections = []
    report_sections.append("# Relatório de Testes — Pipeline de RAG NovaTech\n")
    report_sections.append("**Exercício 1.3 — Construção de pipeline de RAG com ferramentas open-source**\n")
    report_sections.append(
        "**Configuração:** TF-IDF (scikit-learn) + ChromaDB. top_k=5 fixo. "
        "Ver `rag_pipeline.py` para o detalhe da decisão de usar TF-IDF como fallback "
        "do `sentence-transformers` (huggingface.co bloqueado no ambiente de execução).\n"
    )
    report_sections.append(
        "**Como ler:** cada teste mostra (a) chunks recuperados com score, (b) comparação com gabarito do Anexo B, "
        "(c) análise do que o LLM consegue/não consegue fazer com esse contexto, (d) caminho para o prompt montado.\n"
    )

    for test in TESTS:
        print(f"\n--- {test['id']}: {test['question']} ---")
        results = search(test["question"], top_k=5)
        print(format_search_results(results))

        retrieved_ids = [r.chunk_id for r in results]
        must_have_eval = evaluate_recall(test["expected_must_have"], retrieved_ids)
        nice_eval = evaluate_recall(test["expected_nice_to_have"], retrieved_ids)

        # Monta o prompt e salva
        prompt = build_prompt(test["question"], results, system_prompt)
        prompt_file = output_dir / f"prompt_{test['id']}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")

        # Seção do relatório
        section = []
        section.append(f"\n## {test['id']} — \"{test['question']}\"\n")
        section.append(f"**Armadilha embutida:** {test['armadilha']}\n")
        section.append("### Chunks recuperados (top 5)\n")
        section.append("| # | chunk_id | similaridade | fonte | confiabilidade |")
        section.append("|---|---|---|---|---|")
        for i, r in enumerate(results, 1):
            section.append(
                f"| {i} | `{r.chunk_id}` | {r.similarity:.3f} | "
                f"{r.metadata['source_document']} §{r.metadata['section']} | "
                f"{r.metadata['reliability']} |"
            )
        section.append("")

        # Comparação com gabarito
        section.append("### Comparação com o gabarito do Anexo B\n")
        if test["expected_must_have"]:
            section.append(f"**Esperados (must-have):** {test['expected_must_have']}")
            section.append(
                f"- Encontrados: {must_have_eval['found']}"
                + (" ✓" if not must_have_eval['missing'] else "")
            )
            if must_have_eval["missing"]:
                section.append(f"- **Faltando: {must_have_eval['missing']} ✗**")
            section.append(f"- Recall must-have: {must_have_eval['recall_pct']:.0f}%")
        else:
            section.append("**Esperados (must-have):** nenhum — esta pergunta NÃO tem cobertura na base.")
            chunks_relevantes = [c for c in retrieved_ids if "frete" in c.lower() or "PROC-042" in c]
            if chunks_relevantes:
                section.append(
                    f"- Pipeline retornou chunks tematicamente relacionados mas tecnicamente fora de escopo: "
                    f"`{chunks_relevantes}`. Estes não cobrem a pergunta — risco de o LLM gerar resposta inadequada."
                )

        if test["expected_nice_to_have"]:
            section.append(f"\n**Nice-to-have (complementares):** {test['expected_nice_to_have']}")
            section.append(f"- Encontrados: {nice_eval['found']}")
            if nice_eval["missing"]:
                section.append(f"- Faltando: {nice_eval['missing']}")

        section.append("")
        section.append(f"### Prompt montado")
        section.append(f"Salvo em: `outputs_test/prompt_{test['id']}.txt`")
        section.append(
            f"Total de chunks no contexto: {len(results)}. "
            f"Para gerar a resposta, cole o conteúdo desse arquivo no chat do Claude."
        )

        report_sections.extend(section)

    report = "\n".join(report_sections)
    report_path = output_dir / "resultados-testes.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n\nRelatório salvo em: {report_path}")
    print(f"Prompts salvos em: {output_dir}/prompt_T*.txt")


if __name__ == "__main__":
    run_all_tests()
