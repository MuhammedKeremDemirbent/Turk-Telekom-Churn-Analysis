from functools import lru_cache
import os

from django.conf import settings
from dotenv import load_dotenv
from openai import OpenAI

from src.rag import Embedder, FaissStore, RAGChatbot


@lru_cache(maxsize=1)
def get_rag_runtime() -> tuple[OpenAI, FaissStore, str]:
    load_dotenv(settings.BASE_DIR / ".env")

    api_key = os.getenv("API_KEY")

    if not api_key:
        raise RuntimeError(".env dosyasında API_KEY bulunamadı.")

    base_url = os.getenv(
        "DEEPINFRA_BASE_URL",
        "https://api.deepinfra.com/v1/openai",
    )

    embedding_model = os.getenv(
        "EMBEDDING_MODEL",
        "BAAI/bge-m3",
    )

    chat_model = os.getenv(
        "CHAT_MODEL",
        "Qwen/Qwen3.6-35B-A3B",
    )

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    embedder = Embedder(
        client=client,
        model=embedding_model,
    )

    index_path = settings.BASE_DIR / "data" / "rag_index"

    store = FaissStore.load(
        directory=index_path,
        embedder=embedder,
    )

    return client, store, chat_model


def create_chatbot() -> RAGChatbot:
    client, store, chat_model = get_rag_runtime()

    return RAGChatbot(
        client=client,
        store=store,
        chat_model=chat_model,
        top_k=3,
        min_score=0.35,
        score_margin=0.08,
    )