from server.database.db import get_db_connection
from fastapi import HTTPException
from server.utils.embedding import get_embedding_function
from langchain.vectorstores.chroma import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOllama
from server.utils.embedding import get_embedding_function
from server.utils.prompts import PROMPT_TEMPLATE
from fastapi import HTTPException
import os

def query_rag(query_text: str, assistant_id: str, thread_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT vector_db_location FROM files WHERE assistant_id = %s", (assistant_id,))
    vector_db_location = cursor.fetchone()

    if vector_db_location is None:
        raise HTTPException(status_code=404, detail="Vector DB location not found")

    cursor.execute("""
        SELECT message_text 
        FROM messages 
        WHERE thread_id = %s 
        ORDER BY created_at DESC 
        LIMIT 4
    """, (thread_id,))
    
    previous_messages = cursor.fetchall()

    previous_messages.reverse()

    previous_context = "\n".join([msg[0] for msg in previous_messages])

    combined_context = f"{previous_context}\nUser: {query_text}"

    embedding_function = get_embedding_function()
    db = Chroma(persist_directory=vector_db_location[0], embedding_function=embedding_function)

    results = db.similarity_search_with_score(query_text, k=5)

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=combined_context)

    model = ChatOllama(model="llama3.1:latest", temperature=0, base_url=os.getenv('OLLAMA_BASE_URL'))
    response_text = model.invoke(prompt)

    sources = [doc.metadata.get("id", None) for doc, _score in results]

    cursor.close()
    conn.close()
    
    return {
        "response": response_text,
        "sources": sources
    }