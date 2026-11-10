"""Top-k search with embedding-profile and source-integrity validation."""

from terramind.rag.contracts import Chunk, Embedder, KnowledgeStore, unit_vector

RULE_QUERIES = {
    "TM-GCP-001": "Cloud Storage public bucket object read allUsers access prevention review",
    "TM-GCP-002": "Firewall world ingress SSH RDP administrative ports hardening review",
    "TM-GCP-003": "IAM project owner editor basic role least privilege scoped permissions review",
    "TM-GCP-004": "Persistent bucket database deletion replacement backup restore retention review",
    "TM-GCP-005": "Cloud Storage uniform bucket level access disabled object ACL hardening",
    "TM-GCP-006": "Cloud Storage inherited public access prevention organization policy hardening",
    "TM-GCP-007": "Cloud SQL public IPv4 world authorized networks private connectivity hardening",
    "TM-GCP-008": "Cloud SQL SSL TLS unencrypted encrypted only client certificate hardening",
}


class RetrievalUnavailable(RuntimeError):
    """Safe dependency failure, never echo backend content."""


class Retriever:
    def __init__(self, embedder: Embedder, store: KnowledgeStore, top_k: int = 3):
        if not 3 <= top_k <= 5:
            raise ValueError("Retrieval limit must be between three and five")
        self.embedder = embedder
        self.store = store
        self.top_k = top_k

    def search(self, query: str) -> tuple[Chunk, ...]:
        if not query or len(query) > 1000:
            raise ValueError("Retrieval query exceeds its limit")
        vector = unit_vector(self.embedder.embed(query, task="query"))
        records = self.store.nearest(vector, limit=self.top_k)
        if not records or len(records) > self.top_k:
            raise RetrievalUnavailable("Knowledge retrieval unavailable")
        if any(item.embedding_model != self.embedder.model_id for item in records):
            raise RetrievalUnavailable("Knowledge embedding profile mismatch")
        chunks = tuple(record.chunk for record in records)
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise RetrievalUnavailable("Knowledge retrieval returned duplicate sources")
        return chunks
