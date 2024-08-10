from langchain_community.embeddings import OllamaEmbeddings
import os

def get_embedding_function():
    embeddings = OllamaEmbeddings(model="all-minilm:l6-v2", base_url=os.getenv('OLLAMA_BASE_URL'))
    return embeddings
