from pydantic import BaseModel, Field, root_validator
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime

class Rule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Optional[str] = None
    group_id: Optional[str] = None
    value: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    order: int

    @root_validator(pre=True)
    def check_type_or_group_id_exists(cls, values):
        if values.get('type') is None and values.get('group_id') is None:
            raise ValueError('Either "type" or "group_id" must be provided.')
        if values.get('type') is not None and values.get('group_id') is not None:
            raise ValueError('Cannot provide both "type" and "group_id".')
        return values

class FieldSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    is_required: bool = False
    rules: List[Rule] = []

class SheetSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    is_active: bool = True
    fields: List[FieldSchema] = []

class FileSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    saved_name: str
    sheets: List[SheetSchema] = []

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

class ProjectPartialUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class ProjectInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    updated_at: str
    size_kb: float

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    created_at: str
    updated_at: str
    files: List[FileSchema] = []
    auto_revalidate: bool = True
