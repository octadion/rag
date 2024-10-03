from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, UploadFile, File, Path
from typing import List
from pydantic import BaseModel
from langchain_core.messages import AIMessage
from vector_db import load_documents, split_documents, add_to_chroma, clear_database
from query import query_rag
from dotenv import load_dotenv
import json
import os, shutil, psycopg2, uuid

load_dotenv()

CHUNK_PATH = "data"
USER_ID = "test"
DATA_PATH = "data"

app = FastAPI()

def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("POSTGRES_DBNAME"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT")
    )
class QueryRequest(BaseModel):
    query_text: str

class ResetDatabaseRequest(BaseModel):
    reset: bool = False


@app.post("/api/v1/update-database")
async def update_database(tenant_id: str = Query(...), assistant_id: str = Query(...), files: List[UploadFile] = File(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT vector_db_location FROM files WHERE tenant_id = %s AND assistant_id = %s LIMIT 1", (tenant_id, assistant_id))
    result = cursor.fetchone()
    
    if not result:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Assistant ID not found for the given tenant")

    vector_db_location = result[0]

    tenant_folder = os.path.join(DATA_PATH, tenant_id)
    assistant_folder = os.path.join(tenant_folder, assistant_id)

    file_ids = []
    for file in files:
        file_id = str(uuid.uuid4())
        file_ids.append(file_id)

        file_folder = os.path.join(assistant_folder, file_id)
        file_location = os.path.join(file_folder, file.filename)

        os.makedirs(file_folder, exist_ok=True)
        
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)

        cursor.execute(
            """
            INSERT INTO files (id, file_name, file_location, assistant_id, vector_db_location, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (file_id, file.filename, file_location, assistant_id, vector_db_location, tenant_id)
        )
        conn.commit()

    cursor.close()
    conn.close()

    all_file_locations = [os.path.join(assistant_folder, file_id, file.filename) for file_id, file in zip(file_ids, files)]
    run_update_database_multi(all_file_locations, assistant_id, vector_db_location)

    return {"message": "Files uploaded and database update initiated", "tenant_id": tenant_id, "assistant_id": assistant_id}

def run_update_database(file_name, file_id, file_location, vector_db_id, vector_db_location):
    try:
        folder = os.path.dirname(file_location)
        documents = load_documents(folder)
        chunks = split_documents(documents)
        add_to_chroma(chunks, vector_db_location)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO files (id, file_name, file_location, vector_db_id, vector_db_location) VALUES (%s, %s, %s, %s, %s)",
            (file_id, file_name, file_location, vector_db_id, vector_db_location)
        )

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error updating database: {e}")
    
@app.post("/api/v1/upload-files")
async def upload_files(tenant_id: str = Query(...), files: List[UploadFile] = File(...)):

    conn = get_db_connection()
    cursor = conn.cursor()

    assistant_id = str(uuid.uuid4())

    cursor.execute(
        """
        INSERT INTO assistants (id, tenant_id)
        VALUES (%s, %s)
        """, 
        (assistant_id, tenant_id)
    )
    conn.commit()

    cursor.close()
    conn.close()

    tenant_folder = os.path.join(DATA_PATH, tenant_id)
    assistant_folder = os.path.join(tenant_folder, assistant_id)
    vector_db_location = os.path.join(assistant_folder, "CHROMA")
    
    os.makedirs(vector_db_location, exist_ok=True)

    file_ids = []
    for file in files:
        file_id = str(uuid.uuid4())
        file_ids.append(file_id)

        file_folder = os.path.join(assistant_folder, file_id)
        file_location = os.path.join(file_folder, file.filename)

        os.makedirs(file_folder, exist_ok=True)
        
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO files (id, file_name, file_location, assistant_id, vector_db_location, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (file_id, file.filename, file_location, assistant_id, vector_db_location, tenant_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

    all_file_locations = [os.path.join(assistant_folder, file_id, file.filename) for file_id, file in zip(file_ids, files)]
    run_update_database_multi(all_file_locations, assistant_id, vector_db_location)

    return {"message": "Files uploaded and database update initiated", "tenant_id": tenant_id, "assistant_id": assistant_id}

def run_update_database_multi(file_locations, assistant_id, vector_db_location):
    try:
        all_documents = []
        for file_location in file_locations:
            folder = os.path.dirname(file_location)
            documents = load_documents(folder)
            all_documents.extend(documents)

        chunks = split_documents(all_documents)
        add_to_chroma(chunks, vector_db_location)
    except Exception as e:
        print(f"Error updating database: {e}")
    
@app.delete("/api/v1/delete-file/{file_id}")
async def delete_file(file_id: str = Path(...), tenant_id: str = Query(...), assistant_id: str = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_location, vector_db_location FROM files WHERE id = %s AND tenant_id = %s AND assistant_id = %s",
        (file_id, tenant_id, assistant_id)
    )
    result = cursor.fetchone()

    if result is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="File not found or mismatch in tenant_id or assistant_id")

    file_location, vector_db_location = result

    if os.path.exists(file_location):
        os.remove(file_location)

    file_id_folder = os.path.dirname(file_location)
    if os.path.isdir(file_id_folder):
        shutil.rmtree(file_id_folder)

    cursor.execute("DELETE FROM files WHERE id = %s AND tenant_id = %s AND assistant_id = %s", (file_id, tenant_id, assistant_id))
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": f"File {file_id} and its associated folder deleted successfully"}

@app.get("/api/v1/list-files")
async def list_files(tenant_id: str = Query(...), assistant_id: str = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, file_name FROM files WHERE tenant_id = %s AND assistant_id = %s", (tenant_id, assistant_id))
    files = cursor.fetchall()

    cursor.close()
    conn.close()

    return [f"{file_id}: {file_name}" for file_id, file_name in files]

@app.get("/api/v1/list-assistant-ids")
async def list_assistant_ids(tenant_id: str = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT assistant_id FROM files WHERE tenant_id = %s", (tenant_id,))
    assistant_ids = cursor.fetchall()

    cursor.close()
    conn.close()

    return [assistant_id[0] for assistant_id in assistant_ids]

@app.post("/api/v1/create-thread")
async def create_thread(tenant_id: str = Query(...), assistant_id: str = Query(...)):
    thread_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO threads (id, assistant_id, tenant_id)
        VALUES (%s, %s, %s)
        """,
        (thread_id, assistant_id, tenant_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Thread created", "tenant_id": tenant_id, "assistant_id": assistant_id, "thread_id": thread_id}

@app.post("/api/v1/query")
async def query_rag_endpoint(request: QueryRequest, tenant_id: str = Query(...), assistant_id: str = Query(...), thread_id: str = Query(None)):
    if not assistant_id:
        raise HTTPException(status_code=400, detail="Assistant ID must be provided")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT vector_db_location FROM files WHERE tenant_id = %s AND assistant_id = %s LIMIT 1", (tenant_id, assistant_id))
    vector_db_result = cursor.fetchone()
    
    if not vector_db_result:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Assistant ID not found")
    
    vector_db_location = vector_db_result[0]

    if not thread_id:
        thread_id = str(uuid.uuid4())

        cursor.execute(
            """
            INSERT INTO threads (id, assistant_id, tenant_id, created_at)
            VALUES (%s, %s, %s, NOW())
            """,
            (thread_id, assistant_id, tenant_id)
        )
        conn.commit()

    result = query_rag(request.query_text, assistant_id, thread_id)
    assistant_response = result["response"].content if isinstance(result["response"], AIMessage) else result["response"]

    combined_message = [
        {"content": request.query_text, "role": "user"},
        {"content": assistant_response, "role": "assistant"}
    ]

    message_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO messages (id, thread_id, assistant_id, tenant_id, message_text, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        """,
        (message_id, thread_id, assistant_id, tenant_id, json.dumps(combined_message))
    )
    conn.commit()

    cursor.close()
    conn.close()

    return {
        "message": "Query executed",
        "result": result,
        "thread_id": thread_id
    }

@app.delete("/api/v1/delete-assistant/{assistant_id}")
async def delete_assistant(assistant_id: str = Path(...), tenant_id: str = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT vector_db_location FROM files WHERE tenant_id = %s AND assistant_id = %s LIMIT 1", (tenant_id, assistant_id))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Assistant ID not found for the given tenant")

    vector_db_location = result[0]

    cursor.execute("SELECT file_location FROM files WHERE tenant_id = %s AND assistant_id = %s", (tenant_id, assistant_id))
    file_results = cursor.fetchall()

    for file_result in file_results:
        file_location = file_result[0]
        if os.path.exists(file_location):
            os.remove(file_location)

        file_id_folder = os.path.dirname(file_location)
        if os.path.isdir(file_id_folder):
            shutil.rmtree(file_id_folder)

    if os.path.isdir(vector_db_location):
        shutil.rmtree(vector_db_location)

    cursor.execute("DELETE FROM files WHERE tenant_id = %s AND assistant_id = %s", (tenant_id, assistant_id))
    conn.commit()

    cursor.execute("DELETE FROM assistants WHERE tenant_id = %s AND id = %s", (tenant_id, assistant_id))
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": f"Assistant {assistant_id} and all related data deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
