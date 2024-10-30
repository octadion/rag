from server.database.db import get_db_connection
from server.plugins.jwt_utils import verify_token
from server.api.v1.assistant.schema.assistant import AssistantCreateRequest, SourceInput
import uuid
from datetime import datetime, timezone
from server.utils.vector_db import run_update_database_multi, run_update_database_webbase
from fastapi import FastAPI, HTTPException, Query, Header, APIRouter
import os, uuid
from langchain_community.document_loaders import WebBaseLoader
router = APIRouter()

CHUNK_PATH = "data"
USER_ID = "test"
DATA_PATH = "data"
@router.post("/")
async def create_assistant(request: AssistantCreateRequest):
    assistant_id = str(uuid.uuid4())

    conn = get_db_connection()
    cursor = conn.cursor()

    created_at = datetime.now(timezone.utc)


    cursor.execute(
        """
        INSERT INTO assistants (id, tenant_id, vector_db_location, created_at, llm_model, llm_provider, embedding_model, embedding_provider, type)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (assistant_id, request.tenant_id, None, created_at, 
         request.llm_model, request.llm_provider, request.embedding_model, 
         request.embedding_provider, request.type)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {"assistant_id": assistant_id, "message": "Assistant created successfully"}

@router.post("/{assistant_id}/database/add_source")
async def add_source(
    assistant_id: str,
    source: SourceInput,
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

    if source.type == "website-url":
        source_id = str(uuid.uuid4())
        file_name = source.url
        file_folder = os.path.join(assistant_folder, source_id)
        file_location = os.path.join(file_folder, file_name)

        os.makedirs(file_folder, exist_ok=True)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO files (id, file_name, file_location, assistant_id, vector_db_location, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (source_id, file_name, file_location, assistant_id, vector_db_location, tenant_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        run_update_database_webbase(source.url, assistant_id, vector_db_location)

        return {
            "message": "Website source added and database updated",
            "tenant_id": tenant_id,
            "assistant_id": assistant_id,
        }
    else:
        raise HTTPException(status_code=400, detail="Unsupported source type")