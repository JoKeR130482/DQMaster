from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class RuleConfig(BaseModel):
    is_configurable: bool = False
    params_schema: Optional[List[Dict[str, Any]]] = None
    description: str = ""
    needs_column_access: bool = False

class RuleMetadata(BaseModel):
    id: str
    name: str
    description: str
    is_configurable: bool
    params_schema: Optional[List[Dict[str, Any]]] = None
