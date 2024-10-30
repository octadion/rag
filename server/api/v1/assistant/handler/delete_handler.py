from fastapi import APIRouter, Path, Query, HTTPException, Header
from server.plugins.jwt_utils import verify_token
from server.database.db import get_db_connection
import os, shutil

router = APIRouter()

@router.delete("/{assistant_id}/file/{file_id}")
async def delete_file(assistant_id: str, file_id: str = Path(...), authorization: str = Header(None)):
    conn = get_db_connection()
    cursor = conn.cursor()
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    
    token = authorization.split(" ")[1]
    tenant_id = verify_token(token)
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

@router.delete("/{assistant_id}")
async def delete_assistant(assistant_id: str, authorization: str = Header(None)):
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