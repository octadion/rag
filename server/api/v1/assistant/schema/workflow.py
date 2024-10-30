from pydantic import BaseModel
from typing import List, Dict

class QueryRequest(BaseModel):
    query_text: str

class InputData(BaseModel):
    input: List[Dict[str, str]]