from server.database.db import get_db_connection
from server.api.v1.user.schema.user import RegisterTenantRequest
import uuid
from fastapi import FastAPI, HTTPException, APIRouter
from server.plugins.jwt_utils import create_token
from datetime import datetime

router = APIRouter()

@router.post("/register")
async def register_tenant(request: RegisterTenantRequest):
    tenant_id = request.tenant_id if request.tenant_id else str(uuid.uuid4())
    created_at = datetime.now()

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO tenants (id, name, created_at)
            VALUES (%s, %s, %s)
            """,
            (tenant_id, request.name, created_at)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to register tenant") from e
    finally:
        cursor.close()
        conn.close()
    token = create_token(tenant_id)
    return {"message": "Tenant registered successfully", "token": token,"tenant_id": tenant_id, "name": request.name, "created_at": created_at}
