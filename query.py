from langchain.vectorstores.chroma import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOllama
from embedding import get_embedding_function
from dotenv import load_dotenv
from fastapi import HTTPException
import os, psycopg2
from typing import List, Dict
from pydantic import BaseModel
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

class InputData(BaseModel):
    input: List[Dict[str, str]]

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

Answer the question based on the above context and previous question: {question}
"""
classification_llm = ChatOllama(model='llama3:8b-maxchat', temperature=0, base_url=os.getenv('OLLAMA_BASE_URL'))

prompt = PromptTemplate.from_template(
    """Analisa teks percakapan berikut ke dalam format di bawah serta klasifikasikanlah ke dalam salah satu label:

    Konteks Percakapan: 
    {{konteks_percakapan}}

    Keyword Extraction: 
    {{keyword_extraction}}

    Intent Recognition: 
    {{intent_recognition}}

    Kualifikasi Lead: 
    {{kualifikasi_lead}}

    Label: [L1-Qualified, S_JUNK, Qualified, L1-Junk]

    {input}
    """
)

output_parser = StrOutputParser()
class InputData(BaseModel):
    input: List[Dict[str, str]]

def generate_response(data: InputData):
    try:
        formatted_input = "\n".join([f'{key}: {value}' for message in data.input for key, value in message.items()])
        
        chain = prompt | classification_llm | output_parser
        response = chain.invoke({"input": formatted_input})
        
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
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

def classification_workflow(query_text: str, assistant_id: str, thread_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT message_text 
        FROM messages 
        WHERE thread_id = %s 
        ORDER BY created_at DESC 
        LIMIT 6
        """, 
        (thread_id,)
    )

    previous_messages = cursor.fetchall()

    if len(previous_messages) >= 10:
        previous_messages.reverse()
        formatted_input = [{"content": f"{msg[0]}", "role": "user"} for msg in previous_messages]
        formatted_input.append({"content": query_text, "role": "user"})

        input_data = InputData(input=formatted_input)
        classification_response = generate_response(input_data)

        cursor.close()
        conn.close()

        return {
            "response": classification_response,
            "classification": "Classification Response Generated"
        }
    else:
        regular_llm = ChatOllama(model="llama3.1:latest", temperature=0, base_url=os.getenv('OLLAMA_BASE_URL'))
        
        regular_prompt = PromptTemplate.from_template(
            """Anda adalah assistant AI dari Maxchat, Maxchat merupakan WhatsApp Business Solutions Provider (BSP WA) untuk penyedia layanan WhatsApp API Official dan Omnichannel, jika ada pertanyaan, jawab sebaik mungkin sebagai Assistant AI Maxchat, jika ada pertanyaan terkait produk atau hal spesifik, berikan kontak maxchat: 0812-3451-1449 dan halo@maxchat.id
            {input}"""
        )

        formatted_input = "\n".join([f'{msg[0]}' for msg in previous_messages])
        formatted_input += f"\n{query_text}"
        
        chain = regular_prompt | regular_llm | output_parser
        regular_response = chain.invoke({"input": formatted_input})

        cursor.close()
        conn.close()

        return {
            "response": regular_response,
            "classification": "Regular Response Generated"
        }