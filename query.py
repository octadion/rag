from langchain.vectorstores.chroma import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOllama
from embedding import get_embedding_function
from dotenv import load_dotenv
from fastapi import HTTPException
import os, psycopg2
def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT")
    )
load_dotenv()

CHROMA_PATH = "chroma"
PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Answer the question based on the above context: {question}
"""

def query_rag(query_text: str, vector_db_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vector_db_location FROM files WHERE vector_db_id = %s", (vector_db_id,))
    vector_db_location = cursor.fetchone()

    if vector_db_location is None:
        raise HTTPException(status_code=404, detail="Vector DB location not found")

    embedding_function = get_embedding_function()
    db = Chroma(persist_directory=vector_db_location[0], embedding_function=embedding_function)
    results = db.similarity_search_with_score(query_text, k=5)

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)
    model = ChatOllama(model="llama3.1:latest", temperature=0, base_url=os.getenv('OLLAMA_BASE_URL'))
    response_text = model.invoke(prompt)
    sources = [doc.metadata.get("id", None) for doc, _score in results]

    cursor.close()
    conn.close()
    
    return {"response": response_text, "sources": sources}
