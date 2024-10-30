from pydantic import BaseModel
from typing import Optional

class AssistantCreateRequest(BaseModel):
    tenant_id: str
    vector_db_location: Optional[str] = None
    llm_model: Optional[str] = None
    llm_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    type: Optional[str] = None

class SourceInput(BaseModel):
    url: str
    type: str
