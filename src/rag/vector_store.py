# /opt/auto-wiki/src/rag/vector_store.py
# ベクトルストア管理
# 目的: 記事をベクトル化してChromaDBに保存し、意味検索を提供する

import chromadb
from chromadb.utils import embedding_functions

class WikiVectorDB:
    def __init__(self, persist_path="/app/wiki_vector_db"):
        self.client = chromadb.PersistentClient(path=persist_path)
        
        # 埋め込みモデル（ローカル動作する軽量モデルを使用）
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        self.collection = self.client.get_or_create_collection(
            name="wiki_articles",
            embedding_function=self.ef
        )

    def upsert_article(self, topic: str, content: str):
        """記事をベクトルDBに保存・更新する"""
        try:
            # チャンク分割などは簡易的に今回は省略し、全文（または先頭）を入れる
            # 実運用ではLangChain等でChunking推奨
            short_content = content[:8000] # トークン制限回避のため制限
            
            self.collection.upsert(
                documents=[short_content],
                metadatas=[{"topic": topic}],
                ids=[topic]
            )
            print(f"🧠 Vectorized: {topic}")
        except Exception as e:
            print(f"⚠️ Vector DB Error: {e}")

    def search(self, query: str, n_results: int = 3):
        """関連する記事を検索する"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results