import jwt
import os
from fastapi import Header, HTTPException
from server.database.db import get_db_connection

SECRET_KEY = os.getenv('SECRET_KEY')

def create_token(tenant_id: str):
    payload = {
        "tenant_id": tenant_id
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        tenant_id = payload["tenant_id"]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tenants WHERE id = %s", (tenant_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        return tenant_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")