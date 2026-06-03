"""
Pipeline de RAG — POC para Assistente NovaTech (Exercício 1.3)
================================================================

Stack:
- ChromaDB como vector store local (com embeddings customizados)
- Vetorização configurável (ver EMBEDDING_METHOD):
    * "tfidf" — TF-IDF lexical (scikit-learn). Funciona offline, sem rede.
    * "sentence-transformers" — embedding semântico multilíngue. Requer acesso
       a huggingface.co (1x na primeira execução para baixar o modelo).
- markdown-it-py para parsing estrutural

COMO ALTERNAR O MÉTODO DE EMBEDDING
-----------------------------------
Mude a constante EMBEDDING_METHOD logo abaixo. Nenhuma outra alteração de código
é necessária — a abstração Embedder isola o resto do pipeline. Quando trocar,
RODE A INGESTÃO NOVAMENTE (run_tests.py ou rag_pipeline.py): vectorizers diferentes
produzem espaços vetoriais incompatíveis; a collection do ChromaDB precisa ser
reconstruída.

NOTA HISTÓRICA SOBRE A ESCOLHA
------------------------------
A escolha original era 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
modelo semântico multilíngue ideal para PT-BR. No ambiente original de execução
desta POC, huggingface.co estava bloqueado, e por isso o TF-IDF foi implementado
como fallback. As implicações de cada método:
  - TF-IDF captura similaridade LEXICAL (palavras compartilhadas), não semântica.
    Sinônimos e paráfrases são tratados como dissimilares.
  - sentence-transformers captura similaridade SEMÂNTICA. "Platinum" e "outros tiers"
    têm similaridade alta porque o modelo entende contexto.
  - Em produção corporativa, recomenda-se o embedding gerenciado da Azure
    (text-embedding-3-large), conforme análise 1.1 §7.

Decisões de design (baseadas na análise 1.1, seção 5.3):
- Chunking por seção numerada (não por tamanho fixo): respeita a estrutura
  semântica regra+exceção da documentação normativa.
- Metadados essenciais: source_document, section, section_title, reliability.
- FAQ marcado como reliability="informal" para que o LLM saiba diferenciar.

Limitações conhecidas (ver correcoes-propostas.md):
- Sem reranking com cross-encoder.
- Sem lógica de supersessão (PROC-042 v1 e v2 coexistem como iguais no vector store).
- Sem orçamento variável de chunks por tipo de pergunta — top_k fixo.
"""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import chromadb
from chromadb.config import Settings
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle

# --------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------

# --------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------

# >>> ESCOLHA O MÉTODO DE EMBEDDING AQUI <<<
# Opções suportadas:
#   "tfidf"                 — lexical, scikit-learn, offline.
#   "sentence-transformers" — semântico, requer huggingface.co liberado.
EMBEDDING_METHOD = "sentence-transformers"

# Modelo usado quando EMBEDDING_METHOD == "sentence-transformers".
# paraphrase-multilingual-MiniLM-L12-v2 é open-source, ~120MB, treinado em 50+
# idiomas incluindo PT-BR. Para qualidade superior, considerar em produção:
# "intfloat/multilingual-e5-large" ou o embedding gerenciado da Azure.
SENTENCE_TRANSFORMER_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

COLLECTION_NAME = "novatech_docs"
CHROMA_PATH = "./chroma_db"
VECTORIZER_PATH = "./tfidf_vectorizer.pkl"
DOCS_PATH = "./docs"

# Mapeamento explícito: arquivo → (id do doc, tipo, reliability)
DOC_REGISTRY = {
    "POL-001-politica-devolucao.md": {
        "doc_id": "POL-001",
        "doc_type": "policy",
        "reliability": "official",
    },
    "PROC-042-frete-especial-v1.md": {
        "doc_id": "PROC-042",
        "doc_type": "procedure",
        "reliability": "official",
        "version": "v1",
    },
    "PROC-042-v2-frete-especial-revisado.md": {
        "doc_id": "PROC-042-v2",
        "doc_type": "procedure",
        "reliability": "official",
        "version": "v2",
    },
    "SLA-2024-tabela-sla-clientes.md": {
        "doc_id": "SLA-2024",
        "doc_type": "sla",
        "reliability": "official",
    },
    "FAQ-atendimento.md": {
        "doc_id": "FAQ-Atendimento",
        "doc_type": "faq",
        "reliability": "informal",
    },
}


# --------------------------------------------------------------------
# Dataclass para Chunk
# --------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str
    text: str                # texto completo do chunk (com prefixo de localização)
    raw_content: str         # apenas o conteúdo, sem prefixo
    source_document: str     # ex: "POL-001"
    section: str             # ex: "3.2"
    section_title: str       # ex: "Exceções ao prazo geral"
    reliability: str         # "official" | "informal"
    doc_type: str            # "policy" | "procedure" | "sla" | "faq"
    version: Optional[str] = None  # ex: "v1", "v2"

    def to_metadata(self) -> dict:
        """Metadados serializáveis para o ChromaDB (sem o texto)."""
        md = {
            "source_document": self.source_document,
            "section": self.section,
            "section_title": self.section_title,
            "reliability": self.reliability,
            "doc_type": self.doc_type,
        }
        if self.version:
            md["version"] = self.version
        return md


# --------------------------------------------------------------------
# 1) INGESTÃO: parser de markdown + chunking semântico
# --------------------------------------------------------------------

def parse_markdown_to_chunks(filepath: Path, registry_entry: dict) -> list[Chunk]:
    """
    Parser que respeita a estrutura hierárquica do markdown.

    Estratégia:
    - Lê o documento linha a linha.
    - Identifica headings (## e ###).
    - Para documentos normativos: cada ### é um chunk; ## sem ### filhos vira chunk próprio.
    - Para FAQ: cada ### Item N — ... é um chunk.
    - O texto de cada chunk inclui um prefixo de localização: "[DOC > Seção X — Título]".

    Retorna lista de Chunks com metadados preenchidos.
    """
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    doc_id = registry_entry["doc_id"]
    is_faq = registry_entry["doc_type"] == "faq"

    chunks: list[Chunk] = []
    current_h2: Optional[tuple[str, str]] = None  # (numero, titulo)
    current_h2_buffer: list[str] = []
    has_h3_under_h2 = False  # marca se o H2 atual já teve H3s — se sim, ignoramos o buffer do H2
    current_h3: Optional[tuple[str, str]] = None
    current_h3_buffer: list[str] = []

    def flush_h3():
        """Fecha o chunk do ### atual."""
        nonlocal current_h3, current_h3_buffer
        if current_h3 is None:
            return
        section_num, section_title = current_h3
        body = "\n".join(current_h3_buffer).strip()
        if not body:
            current_h3 = None
            current_h3_buffer = []
            return
        prefix = f"[{doc_id} > Seção {section_num} — {section_title}]"
        chunk = Chunk(
            chunk_id=f"{doc_id}-{section_num}",
            text=f"{prefix}\n{body}",
            raw_content=body,
            source_document=doc_id,
            section=section_num,
            section_title=section_title,
            reliability=registry_entry["reliability"],
            doc_type=registry_entry["doc_type"],
            version=registry_entry.get("version"),
        )
        chunks.append(chunk)
        current_h3 = None
        current_h3_buffer = []

    def flush_h2_if_orphan():
        """
        Fecha o chunk do ## atual.

        Mantém o chunk do ## se ele tem conteúdo próprio (mesmo que tenha filhos ###).
        Isso é importante para casos como "## 2. Fórmula de cálculo" do PROC-042,
        onde o ## tem a fórmula no corpo E o ### 2.1 tem só a tabela de multiplicadores.
        Sem isso, a fórmula seria perdida.
        """
        nonlocal current_h2, current_h2_buffer, has_h3_under_h2
        if current_h2 is None:
            return
        section_num, section_title = current_h2
        body = "\n".join(current_h2_buffer).strip()
        if not body:
            # H2 sem conteúdo próprio (só serviu de container para ###): descarta
            current_h2 = None
            current_h2_buffer = []
            has_h3_under_h2 = False
            return
        prefix = f"[{doc_id} > Seção {section_num} — {section_title}]"
        chunk = Chunk(
            chunk_id=f"{doc_id}-{section_num}",
            text=f"{prefix}\n{body}",
            raw_content=body,
            source_document=doc_id,
            section=section_num,
            section_title=section_title,
            reliability=registry_entry["reliability"],
            doc_type=registry_entry["doc_type"],
            version=registry_entry.get("version"),
        )
        chunks.append(chunk)
        current_h2 = None
        current_h2_buffer = []
        has_h3_under_h2 = False

    h2_pattern = re.compile(r"^## +(.+)$")
    h3_pattern = re.compile(r"^### +(.+)$")
    # Extrai número da seção quando presente (ex: "3.1." ou "3.1" no início do título)
    section_num_pattern = re.compile(r"^(\d+(?:\.\d+)*)\.?\s*[\-—–:]?\s*(.*)$")

    for line in lines:
        # Pula o H1 (título do documento) — já temos no doc_id
        if line.startswith("# ") and not line.startswith("## "):
            continue

        m3 = h3_pattern.match(line)
        if m3:
            # Novo H3: fecha o H3 anterior; marca H2 atual como tendo filhos
            flush_h3()
            has_h3_under_h2 = True
            title_raw = m3.group(1).strip()
            sm = section_num_pattern.match(title_raw)
            if sm:
                section_num = sm.group(1)
                section_title = sm.group(2).strip() or title_raw
            else:
                # Sem numeração (caso FAQ: "Item 3 — ...")
                section_num = title_raw.split("—")[0].strip() if "—" in title_raw else title_raw
                section_title = title_raw
            current_h3 = (section_num, section_title)
            current_h3_buffer = []
            continue

        m2 = h2_pattern.match(line)
        if m2:
            # Novo H2: fecha o H3 anterior (se houver) e o H2 anterior (se órfão)
            flush_h3()
            flush_h2_if_orphan()
            title_raw = m2.group(1).strip()
            sm = section_num_pattern.match(title_raw)
            if sm:
                section_num = sm.group(1)
                section_title = sm.group(2).strip() or title_raw
            else:
                section_num = title_raw
                section_title = title_raw
            current_h2 = (section_num, section_title)
            current_h2_buffer = []
            has_h3_under_h2 = False
            continue

        # Linha de conteúdo: acumula no buffer apropriado
        if current_h3 is not None:
            current_h3_buffer.append(line)
        elif current_h2 is not None:
            current_h2_buffer.append(line)
        # Linhas antes de qualquer H2 (cabeçalho do doc: versão, responsável, etc.) são descartadas
        # — esses metadados já estão registrados no DOC_REGISTRY

    # Fim do arquivo: fecha tudo
    flush_h3()
    flush_h2_if_orphan()

    return chunks


# --------------------------------------------------------------------
# Camada de abstração: Embedder
# --------------------------------------------------------------------
# Interface comum para os dois métodos de vetorização suportados.
# Adicionar um novo método (ex: Azure OpenAI embeddings) requer apenas implementar
# essa interface e estender create_embedder().

class Embedder(ABC):
    """Interface abstrata para qualquer método de vetorização."""

    name: str  # nome legível para logs

    @abstractmethod
    def fit(self, texts: list[str]) -> None:
        """
        Treina o embedder no corpus, se aplicável.
        Para sentence-transformers (modelo pré-treinado): no-op.
        Para TF-IDF: constrói o vocabulário com base no corpus.
        """
        ...

    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:
        """Retorna matriz numpy (n_texts, dim) com embeddings L2-normalizados."""
        ...

    @abstractmethod
    def save(self) -> None:
        """Persiste estado para ser carregado depois pela busca, se necessário."""
        ...

    @classmethod
    @abstractmethod
    def load(cls) -> "Embedder":
        """Carrega estado persistido (usado pela função search)."""
        ...


class TfidfEmbedder(Embedder):
    """TF-IDF (scikit-learn). Funciona offline. Captura similaridade lexical."""

    name = "TF-IDF (scikit-learn, ngram 1-2)"

    def __init__(self, vectorizer: Optional[TfidfVectorizer] = None):
        # ngram_range=(1,2) capta bigramas (ex: "carga perigosa"); min_df=1 para
        # base pequena (POC); sem remoção de acentos para preservar PT-BR.
        self.vectorizer = vectorizer or TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            sublinear_tf=True,
        )
        self._fitted = vectorizer is not None

    def fit(self, texts: list[str]) -> None:
        self.vectorizer.fit(texts)
        self._fitted = True

    def encode(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("TfidfEmbedder.encode() chamado antes de fit()")
        matrix = self.vectorizer.transform(texts).toarray()
        # Normalização L2 para que produto interno = cosine similarity
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def save(self) -> None:
        with open(VECTORIZER_PATH, "wb") as f:
            pickle.dump(self.vectorizer, f)
        print(f"[Embedder] Vocabulário TF-IDF salvo em {VECTORIZER_PATH}")

    @classmethod
    def load(cls) -> "TfidfEmbedder":
        with open(VECTORIZER_PATH, "rb") as f:
            vectorizer = pickle.load(f)
        return cls(vectorizer=vectorizer)


class SentenceTransformerEmbedder(Embedder):
    """
    sentence-transformers (HuggingFace). Captura similaridade semântica.
    REQUER acesso a huggingface.co na primeira execução para baixar o modelo
    (~120MB cacheado em ~/.cache/huggingface/). Execuções seguintes funcionam
    offline com o cache.
    """

    name = f"sentence-transformers ({SENTENCE_TRANSFORMER_MODEL})"

    def __init__(self):
        # Import tardio: só carrega a biblioteca se este método for selecionado.
        # Evita exigir a dependência quando o usuário só quer TF-IDF.
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers não está instalado. "
                "Instale com: pip install sentence-transformers"
            ) from e
        self.model = SentenceTransformer(SENTENCE_TRANSFORMER_MODEL)

    def fit(self, texts: list[str]) -> None:
        # Modelo pré-treinado: nada a fazer.
        pass

    def encode(self, texts: list[str]) -> np.ndarray:
        # normalize_embeddings=True faz a normalização L2 internamente.
        return self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def save(self) -> None:
        # Modelo já está cacheado pelo HuggingFace; nada para persistir manualmente.
        pass

    @classmethod
    def load(cls) -> "SentenceTransformerEmbedder":
        return cls()


def create_embedder() -> Embedder:
    """Factory que cria o embedder configurado em EMBEDDING_METHOD."""
    if EMBEDDING_METHOD == "tfidf":
        return TfidfEmbedder()
    elif EMBEDDING_METHOD == "sentence-transformers":
        return SentenceTransformerEmbedder()
    else:
        raise ValueError(
            f"EMBEDDING_METHOD desconhecido: {EMBEDDING_METHOD!r}. "
            f"Use 'tfidf' ou 'sentence-transformers'."
        )


def load_embedder() -> Embedder:
    """Carrega o embedder previamente persistido (usado pela busca)."""
    if EMBEDDING_METHOD == "tfidf":
        return TfidfEmbedder.load()
    elif EMBEDDING_METHOD == "sentence-transformers":
        return SentenceTransformerEmbedder.load()
    else:
        raise ValueError(f"EMBEDDING_METHOD desconhecido: {EMBEDDING_METHOD!r}")


# --------------------------------------------------------------------
# Ingestão
# --------------------------------------------------------------------

def ingest_all_documents(reset: bool = True) -> list[Chunk]:
    """Lê os 5 documentos da NovaTech, gera chunks e indexa no ChromaDB."""
    print(f"[Ingestão] Inicializando ChromaDB em {CHROMA_PATH}")
    client = chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False),
    )

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"[Ingestão] Collection anterior removida")
        except Exception:
            pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    all_chunks: list[Chunk] = []
    for filename, registry_entry in DOC_REGISTRY.items():
        filepath = Path(DOCS_PATH) / filename
        if not filepath.exists():
            print(f"[Ingestão] AVISO: arquivo não encontrado: {filepath}")
            continue
        chunks = parse_markdown_to_chunks(filepath, registry_entry)
        print(f"[Ingestão] {filename}: {len(chunks)} chunks extraídos")
        all_chunks.extend(chunks)

    if not all_chunks:
        raise RuntimeError("Nenhum chunk foi extraído. Verifique os caminhos dos documentos.")

    # === ABSTRAÇÃO: cria o embedder conforme EMBEDDING_METHOD ===
    embedder = create_embedder()
    print(f"[Ingestão] Método de vetorização: {embedder.name}")
    print(f"[Ingestão] Total: {len(all_chunks)} chunks. Gerando embeddings...")

    texts = [c.text for c in all_chunks]
    embedder.fit(texts)  # no-op para sentence-transformers; treina vocabulário para TF-IDF
    embeddings_matrix = embedder.encode(texts)
    embeddings = embeddings_matrix.tolist()
    embedder.save()  # persiste estado se necessário (TF-IDF salva vocabulário; SBERT é no-op)

    collection.add(
        ids=[c.chunk_id for c in all_chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[c.to_metadata() for c in all_chunks],
    )
    print(f"[Ingestão] {len(all_chunks)} chunks indexados na collection '{COLLECTION_NAME}'\n")
    return all_chunks


# --------------------------------------------------------------------
# 2) BUSCA: similaridade vetorial + score
# --------------------------------------------------------------------

@dataclass
class SearchResult:
    chunk_id: str
    text: str
    metadata: dict
    distance: float          # distância (menor = mais similar)
    similarity: float        # 1 - distance (maior = mais similar)


_search_embedder_cache: Optional[Embedder] = None
_search_collection_cache = None


def _get_search_resources():
    global _search_embedder_cache, _search_collection_cache
    if _search_embedder_cache is None:
        _search_embedder_cache = load_embedder()
    if _search_collection_cache is None:
        client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        _search_collection_cache = client.get_collection(COLLECTION_NAME)
    return _search_embedder_cache, _search_collection_cache


def search(question: str, top_k: int = 5) -> list[SearchResult]:
    """Busca os top_k chunks mais similares à pergunta."""
    embedder, collection = _get_search_resources()
    query_vec = embedder.encode([question])
    results = collection.query(
        query_embeddings=query_vec.tolist(),
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    out: list[SearchResult] = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        # ChromaDB com vetores normalizados retorna distância = 1 - cos_sim (default L2 ao quadrado).
        # Para apresentar similaridade no intervalo [0, 1] de forma intuitiva:
        # ChromaDB usa L2 squared por default, então distância = 2 - 2*cos_sim para vetores normalizados.
        # → cos_sim = 1 - distance/2
        similarity = max(0.0, 1.0 - distance / 2.0)
        out.append(SearchResult(
            chunk_id=results["ids"][0][i],
            text=results["documents"][0][i],
            metadata=results["metadatas"][0][i],
            distance=distance,
            similarity=similarity,
        ))
    return out


# --------------------------------------------------------------------
# 3) MONTAGEM DE PROMPT: junta system prompt v3 + chunks + pergunta
# --------------------------------------------------------------------

def load_system_prompt(path: str = "./system_prompt_v3.txt") -> str:
    """Carrega o system prompt v3 produzido no exercício 1.2."""
    return Path(path).read_text(encoding="utf-8")


def build_prompt(question: str, results: list[SearchResult], system_prompt: str) -> str:
    """
    Monta o prompt completo seguindo o padrão recomendado na análise 1.1, seção 4.4:
    - System prompt no início (posição privilegiada de atenção).
    - Chunks no meio, com identificador explícito.
    - Pergunta do atendente no final (máxima atenção).
    """
    chunks_block = "\n\n".join([
        f"--- Chunk {r.chunk_id} (fonte: {r.metadata['source_document']}, "
        f"confiabilidade: {r.metadata['reliability']}) ---\n{r.text}"
        for r in results
    ])
    prompt = f"""{system_prompt}

# CHUNKS RECUPERADOS DO PIPELINE DE RAG

{chunks_block}

# PERGUNTA DO ATENDENTE

{question}
"""
    return prompt


# --------------------------------------------------------------------
# Util: imprimir resultado de busca para inspeção
# --------------------------------------------------------------------

def format_search_results(results: list[SearchResult]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. [{r.chunk_id}] sim={r.similarity:.3f} "
            f"({r.metadata['source_document']}, "
            f"§{r.metadata['section']}, "
            f"{r.metadata['reliability']})"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    # Smoke test
    chunks = ingest_all_documents(reset=True)
    print(f"Ingestão concluída: {len(chunks)} chunks\n")
    print("--- Amostra de 3 chunks ---")
    for c in chunks[:3]:
        print(f"\n[{c.chunk_id}] {c.section_title}")
        print(c.text[:200] + "..." if len(c.text) > 200 else c.text)