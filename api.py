from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, UploadFile, File, Path
from typing import List
from pydantic import BaseModel
from vector_db import load_documents, split_documents, add_to_chroma, clear_database
from query import query_rag
from dotenv import load_dotenv
import os, shutil, psycopg2, uuid

load_dotenv()

CHUNK_PATH = "data"
USER_ID = "test"

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
    
@app.post("/api/v1/reset-database")
async def reset_database(request: ResetDatabaseRequest, rag_id: str = Query(...)):
    if request.reset:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT vector_db_id FROM files WHERE rag_id = %s", (rag_id,))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="RAG ID not found")

        vector_db_id = result[0]
        
        cursor.close()
        conn.close()

        clear_database(vector_db_id)
        return {"message": f"Database cleared for rag_id {rag_id}", "vector_db_id": vector_db_id}

    return {"message": "Reset flag not set", "rag_id": rag_id}

@app.post("/api/v1/update-database")
async def update_database(rag_id: str = Query(...), files: List[UploadFile] = File(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT user_id, vector_db_id, vector_db_location FROM files WHERE rag_id = %s", (rag_id,))
    result = cursor.fetchone()
    if not result:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="RAG ID not found")

    user_id, vector_db_id, vector_db_location = result
    
    rag_folder = os.path.join(user_id, rag_id)
    
    file_ids = []
    for file in files:
        file_id = str(uuid.uuid4())
        file_ids.append(file_id)
        
        file_id_folder = os.path.join(rag_folder, file_id)
        
        file_location = os.path.join(file_id_folder, file.filename)
        
        os.makedirs(file_id_folder, exist_ok=True)
        
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)

        cursor.execute(
            """
            INSERT INTO files (id, file_name, file_location, vector_db_id, vector_db_location, rag_id, user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (file_id, file.filename, file_location, vector_db_id, vector_db_location, rag_id, user_id)
        )
        conn.commit()

    cursor.close()
    conn.close()

    all_file_locations = [os.path.join(rag_folder, file_id, file.filename) for file_id, file in zip(file_ids, files)]
    run_update_database_multi(all_file_locations, vector_db_id, vector_db_location)

    return {"message": "Files uploaded and database update initiated", "rag_id": rag_id, "vector_db_id": vector_db_id}

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

# @app.post("/api/v1/upload-file")
# async def upload_file(file: UploadFile = File(...)):
#     file_id = str(uuid.uuid4())
#     vector_db_id = str(uuid.uuid4())

#     file_folder = os.path.join(CHUNK_PATH, file_id)
#     vector_db_folder = os.path.join(CHUNK_PATH, vector_db_id)
    
#     file_location = os.path.join(file_folder, file.filename)
#     vector_db_location = os.path.join(vector_db_folder, "CHROMA")

#     os.makedirs(file_folder, exist_ok=True)
#     os.makedirs(vector_db_folder, exist_ok=True)

#     with open(file_location, "wb") as f:
#         shutil.copyfileobj(file.file, f)
    
#     if file.filename.endswith('.pdf'):
#         run_update_database(file.filename, file_id, file_location, vector_db_id, vector_db_location)
#         return {"message": "File uploaded and database update initiated"}
#     else:
#         return {"message": "File uploaded but not processed. Only PDF files are supported."}
    
@app.post("/api/v1/upload-files")
async def upload_files(files: List[UploadFile] = File(...)):
    rag_id = str(uuid.uuid4())
    
    rag_folder = os.path.join(USER_ID, rag_id)
    
    os.makedirs(rag_folder, exist_ok=True)
    
    vector_db_id = str(uuid.uuid4())
    vector_db_folder = os.path.join(rag_folder, vector_db_id)
    vector_db_location = os.path.join(vector_db_folder, "CHROMA")
    
    os.makedirs(vector_db_folder, exist_ok=True)

    file_ids = []
    for file in files:
        file_id = str(uuid.uuid4())
        file_ids.append(file_id)

        file_folder = os.path.join(rag_folder, file_id)
        file_location = os.path.join(file_folder, file.filename)

        os.makedirs(file_folder, exist_ok=True)
        
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO files (id, file_name, file_location, vector_db_id, vector_db_location, user_id, rag_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (file_id, file.filename, file_location, vector_db_id, vector_db_location, USER_ID, rag_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

    all_file_locations = [os.path.join(rag_folder, file_id, file.filename) for file_id, file in zip(file_ids, files)]
    run_update_database_multi(all_file_locations, vector_db_id, vector_db_location)

    return {"message": "Files uploaded and database update initiated", "user_id": USER_ID, "rag_id": rag_id, "vector_db_id": vector_db_id}

def run_update_database_multi(file_locations, vector_db_id, vector_db_location):
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
async def delete_file(file_id: str = Path(...), rag_id: str = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_location, vector_db_location FROM files WHERE id = %s AND rag_id = %s",
        (file_id, rag_id)
    )
    result = cursor.fetchone()

    if result is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="File not found or rag_id mismatch")

    file_location, vector_db_location = result

    if os.path.exists(file_location):
        os.remove(file_location)

    file_id_folder = os.path.dirname(file_location)
    if os.path.isdir(file_id_folder):
        shutil.rmtree(file_id_folder)

    cursor.execute("DELETE FROM files WHERE id = %s AND rag_id = %s", (file_id, rag_id))
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": f"File and associated folder {file_id} deleted successfully"}

@app.get("/api/v1/list-files", response_model=List[str])
async def list_files():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, file_name FROM files")
    files = cursor.fetchall()

    cursor.close()
    conn.close()

    return [f"{file_id}: {file_name}" for file_id, file_name in files]

@app.get("/api/v1/list-vector-db-ids", response_model=List[str])
async def list_vector_db_ids():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT vector_db_id FROM files")
    vector_db_ids = cursor.fetchall()

    cursor.close()
    conn.close()

    return [vector_db_id[0] for vector_db_id in vector_db_ids]

@app.get("/api/v1/list-rag-ids", response_model=List[str])
async def list_rag_ids():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT rag_id FROM files")
    rag_ids = cursor.fetchall()

    cursor.close()
    conn.close()

    return [rag_id[0] for rag_id in rag_ids]

@app.post("/api/v1/query")
async def query_rag_endpoint(request: QueryRequest, rag_id: str = Query(...)):
    if not rag_id:
        raise HTTPException(status_code=400, detail="RAG ID must be provided")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT vector_db_id FROM files WHERE rag_id = %s LIMIT 1", (rag_id,))
    vector_db_result = cursor.fetchone()
    
    if not vector_db_result:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="RAG ID not found")
    
    vector_db_id = vector_db_result[0]

    cursor.execute("SELECT vector_db_location FROM files WHERE vector_db_id = %s LIMIT 1", (vector_db_id,))
    vector_db_location = cursor.fetchone()
    cursor.close()
    conn.close()

    if not vector_db_location:
        raise HTTPException(status_code=404, detail="Vector DB ID not found for the given RAG ID")
    
    result = query_rag(request.query_text, vector_db_id)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
