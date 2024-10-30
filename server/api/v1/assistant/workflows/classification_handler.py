from server.api.v1.assistant.schema.workflow import InputData
from server.database.db import get_db_connection
from fastapi import HTTPException
from server.utils.prompts import prompt
from langchain_community.chat_models import ChatOllama
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import os

load_dotenv()

classification_llm = ChatOllama(model='llama3:8b-maxchat', temperature=0, base_url=os.getenv('OLLAMA_BASE_URL'))

output_parser = StrOutputParser()

def generate_response(data: InputData):
    try:
        formatted_input = "\n".join([f'{key}: {value}' for message in data.input for key, value in message.items()])
        
        chain = prompt | classification_llm | output_parser
        response = chain.invoke({"input": formatted_input})
        
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
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