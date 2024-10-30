from fastapi import APIRouter, Query, Header, HTTPException
from server.database.db import get_db_connection
from server.plugins.jwt_utils import verify_token

router = APIRouter()

@router.get("/{assistant_id}/files")
async def list_files(assistant_id: str, authorization: str = Header(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    
    token = authorization.split(" ")[1]
    tenant_id = verify_token(token)

    cursor.execute("SELECT id, file_name FROM files WHERE tenant_id = %s AND assistant_id = %s", (tenant_id, assistant_id))
    files = cursor.fetchall()

    cursor.close()
    conn.close()

    return [f"{file_id}: {file_name}" for file_id, file_name in files]

@router.get("/")
async def list_assistant_ids(authorization: str = Header(...)):
    conn = get_db_connection()
    cursor = conn.cursor()

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    
    token = authorization.split(" ")[1]
    tenant_id = verify_token(token)
    
    cursor.execute("SELECT DISTINCT assistant_id FROM files WHERE tenant_id = %s", (tenant_id,))
    assistant_ids = cursor.fetchall()

    cursor.close()
    conn.close()

    return [assistant_id[0] for assistant_id in assistant_ids]