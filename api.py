from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, UploadFile, File, Path
from typing import List
from pydantic import BaseModel
from vector_db import load_documents, split_documents, add_to_chroma, clear_database
from query import query_rag
import os, shutil

CHUNK_PATH = "data"

app = FastAPI()

class QueryRequest(BaseModel):
    query_text: str

class ResetDatabaseRequest(BaseModel):
    reset: bool = False

@app.post("/api/v1/reset-database")
async def reset_database(request: ResetDatabaseRequest):
    if request.reset:
        clear_database()
        return {"message": "Database cleared"}
    return {"message": "Reset flag not set"}

@app.post("/api/v1/update-database")
async def update_database():
    run_update_database()
    return {"message": "Database update initiated"}

def run_update_database():
    try:
        documents = load_documents()
        chunks = split_documents(documents)
        add_to_chroma(chunks)
    except Exception as e:
        print(f"Error updating database: {e}")


@app.post("/api/v1/upload-file")
async def upload_file(file: UploadFile = File(...)):
    file_location = os.path.join(CHUNK_PATH, file.filename)
    
    os.makedirs(CHUNK_PATH, exist_ok=True)
    
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    if file.filename.endswith('.pdf'):
        run_update_database()
        return {"message": "File uploaded and database update initiated"}
    else:
        return {"message": "File uploaded but not processed. Only PDF files are supported."}
    
@app.delete("/api/v1/delete-file/{filename}")
async def delete_file(filename: str = Path(...)):
    file_location = os.path.join(CHUNK_PATH, filename)
    
    if os.path.exists(file_location):
        os.remove(file_location)
        return {"message": f"File {filename} deleted"}
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/v1/list-files", response_model=List[str])
async def list_files():
    files = os.listdir(CHUNK_PATH)
    return files

@app.post("/api/v1/query")
async def query_rag_endpoint(request: QueryRequest):
    result = query_rag(request.query_text)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
