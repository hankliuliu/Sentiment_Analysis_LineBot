"""
embedder.py — 文章向量化模組

使用 intfloat/multilingual-e5-large 模型。
此模型要求輸入加上前綴：
  - 文章段落：「passage: 」
  - 使用者查詢：「query: 」
"""

from sentence_transformers import SentenceTransformer

_model = None

def get_model() -> SentenceTransformer:
    """Lazy 載入模型（只在第一次呼叫時下載/載入，之後重用）。"""
    global _model
    if _model is None:
        print("[Embedder] 載入 multilingual-e5-large 模型...\n")  # （首次需下載約 1.3GB）
        _model = SentenceTransformer("intfloat/multilingual-e5-large")
        print("\n[Embedder] 模型載入完成")
    return _model


def embed_passages(texts: list[str]) -> list[list[float]]:
    """將文章內容向量化（用於存入向量 DB）。"""
    model = get_model()
    prefixed = [f"passage: {t}" for t in texts]
    embeddings = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(text: str) -> list[float]:
    """將使用者問題向量化（用於搜尋相似文章）。"""
    model = get_model()
    embedding = model.encode(f"query: {text}", normalize_embeddings=True)
    return embedding.tolist()
