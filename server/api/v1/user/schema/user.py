from pydantic import BaseModel
from typing import Optional

class RegisterTenantRequest(BaseModel):
    tenant_id: Optional[str] = None 
    name: str