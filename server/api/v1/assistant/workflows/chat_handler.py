from fastapi import Query, APIRouter, HTTPException, Header
from server.database.db import get_db_connection
from server.plugins.jwt_utils import verify_token
from server.api.v1.assistant.schema.workflow import QueryRequest
from server.api.v1.assistant.workflows.rag_handler import query_rag
from server.api.v1.assistant.workflows.classification_handler import classification_workflow
from langchain_core.messages import AIMessage
import uuid, json

router = APIRouter()

@router.post("/{assistant_id}/thread")
async def create_thread(assistant_id: str, authorization: str = Header(None)):
    thread_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    
    token = authorization.split(" ")[1]
    tenant_id = verify_token(token)

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

@router.post("/{assistant_id}/query/{thread_id}")
async def query_rag_endpoint(request: QueryRequest, assistant_id: str, thread_id: str = None, authorization: str = Header(None)):
    if not assistant_id:
        raise HTTPException(status_code=400, detail="Assistant ID must be provided")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    
    token = authorization.split(" ")[1]
    tenant_id = verify_token(token)
    
    cursor.execute("SELECT type FROM assistants WHERE id = %s AND tenant_id = %s", (assistant_id, tenant_id))
    assistant_type_result = cursor.fetchone()
    
    if not assistant_type_result:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Assistant ID not found")

    assistant_type = assistant_type_result[0]

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

    if assistant_type == "rag":
        workflow_result = query_rag(request.query_text, assistant_id, thread_id)
    elif assistant_type == "classification":
        workflow_result = classification_workflow(request.query_text, assistant_id, thread_id)
    else:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Unsupported assistant type: {assistant_type}")
    
    assistant_response = workflow_result["response"].content if isinstance(workflow_result["response"], AIMessage) else workflow_result["response"]

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
    print(workflow_result)
    return {
        "message": "Query executed",
        "result": workflow_result,
        "thread_id": thread_id
    }