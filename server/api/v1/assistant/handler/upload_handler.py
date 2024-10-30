from server.database.db import get_db_connection
from server.utils.vector_db import run_update_database_multi
from server.plugins.jwt_utils import verify_token
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Path, APIRouter, Header
from typing import List
import os, uuid, shutil

CHUNK_PATH = "data"
USER_ID = "test"
DATA_PATH = "data"

router = APIRouter()

@router.post("/{assistant_id}/database/update")
async def update_database(assistant_id: str, files: List[UploadFile] = File(...), authorization: str = Header(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    
    token = authorization.split(" ")[1]
    tenant_id = verify_token(token)

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

@router.post("/{assistant_id}/database/upload")
async def upload_files(
    assistant_id: str,
    files: List[UploadFile] = File(...),
    authorization: str = Header(None)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    
    token = authorization.split(" ")[1]
    tenant_id = verify_token(token)
    cursor.execute(
        """
        SELECT id FROM assistants WHERE id = %s AND tenant_id = %s
        """,
        (assistant_id, tenant_id)
    )
    if cursor.fetchone() is None:
        cursor.close()
        conn.close()
        return {"error": "Assistant ID not found or does not belong to the specified tenant"}

    tenant_folder = os.path.join(DATA_PATH, tenant_id)
    assistant_folder = os.path.join(tenant_folder, assistant_id)
    vector_db_location = os.path.join(assistant_folder, "CHROMA")

    cursor.execute(
        """
        UPDATE assistants
        SET vector_db_location = %s
        WHERE id = %s AND tenant_id = %s
        """,
        (vector_db_location, assistant_id, tenant_id)
    )
    conn.commit()

    cursor.close()
    conn.close()

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