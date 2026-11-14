"""CPU-only, pinned local models. Downloads are an explicit setup operation."""
from pathlib import Path

from backend.document_store import RetrievalError


ROOT = Path(__file__).resolve().parents[1]
MODEL_CACHE = ROOT / ".cache" / "models"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
RERANK_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
EMBEDDING_KEY = f"{EMBEDDING_MODEL}@{EMBEDDING_REVISION}"


def model_path(model, revision, cache_dir=MODEL_CACHE, download=False):
    try:
        from huggingface_hub import snapshot_download

        return snapshot_download(
            model, revision=revision, cache_dir=str(cache_dir), token=False,
            local_files_only=not download,
            allow_patterns=["*.json", "*.txt", "*.safetensors"],
            ignore_patterns=["onnx/*", "openvino/*"],
        )
    except (ImportError, OSError, RuntimeError) as error:
        raise RetrievalError(
            f"Local model {model} is unavailable. Install requirements-rag.txt and run "
            "python -m scripts.retrieve download-models once with network access."
        ) from error


def download_models(cache_dir=MODEL_CACHE):
    return [model_path(model, revision, cache_dir, download=True) for model, revision in
            [(EMBEDDING_MODEL, EMBEDDING_REVISION), (RERANK_MODEL, RERANK_REVISION)]]


class LocalModels:
    embedding_key = EMBEDDING_KEY

    def __init__(self, cache_dir=MODEL_CACHE):
        self.cache_dir = Path(cache_dir)
        self.encoder = None
        self.reranker = None

    def _load(self, rerank=False):
        try:
            import torch
            from sentence_transformers import CrossEncoder, SentenceTransformer

            # Small CPU batches are slower with all hardware threads competing.
            torch.set_num_threads(2)
            if rerank and self.reranker is None:
                path = model_path(RERANK_MODEL, RERANK_REVISION, self.cache_dir)
                self.reranker = CrossEncoder(
                    path, device="cpu", local_files_only=True, trust_remote_code=False,
                    activation_fn=torch.nn.Identity(), model_kwargs={"use_safetensors": True},
                )
            elif not rerank and self.encoder is None:
                path = model_path(EMBEDDING_MODEL, EMBEDDING_REVISION, self.cache_dir)
                self.encoder = SentenceTransformer(
                    path, device="cpu", local_files_only=True, trust_remote_code=False,
                    model_kwargs={"use_safetensors": True},
                )
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise RetrievalError("Could not load local retrieval model. Check requirements-rag.txt and the model cache.") from error

    def embed(self, texts):
        self._load()
        return self.encoder.encode(texts, normalize_embeddings=True, convert_to_numpy=True,
                                   show_progress_bar=False, batch_size=16).astype("float32")

    def rerank(self, query, passages):
        self._load(rerank=True)
        return self.reranker.predict([(query, text) for text in passages],
                                     show_progress_bar=False, batch_size=16).astype("float32")
