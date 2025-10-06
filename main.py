import os
import importlib.util
from pathlib import Path
import uuid
from typing import Dict, List, Any, Optional
import inspect
import datetime
import shutil
import pandas as pd
import io
import json

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ==============================================================================
# 1. Globals & App Initialization
# ==============================================================================
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RULES_DIR = BASE_DIR / "rules"
PROJECTS_DIR = BASE_DIR / "projects"
TEMPLATES_FILE = BASE_DIR / "templates.json"
RULE_REGISTRY = {}

# ==============================================================================
# 2. Pydantic Models (kept for reference, but not all are used by the simplified endpoint)
# ==============================================================================

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

# ... (other models can remain for now)
class RuleConfig(BaseModel):
    id: str
    params: Optional[Dict[str, Any]] = None

class ColumnConfig(BaseModel):
    is_required: bool = False
    rules: List[RuleConfig] = []

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    created_at: str
    updated_at: str
    files: List[Dict[str, Any]] = []
    rules: Dict[str, ColumnConfig] = {}

class ProjectInfo(Project):
    size_kb: float

class ProjectUpdateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

class SheetSelectRequest(BaseModel):
    fileId: str
    sheetName: str

class ValidationRequest(BaseModel):
    fileId: str
    sheetName: str
    rules: Dict[str, ColumnConfig]

class Template(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    columns: List[str]
    rules: Dict[str, ColumnConfig]

class MatchRequest(BaseModel):
    columns: List[str]

# ==============================================================================
# 4. API Endpoints
# ==============================================================================

# --- Simplified Project Creation for Debugging ---
@app.post("/api/projects", status_code=200)
async def create_project_atomic(project_data: ProjectCreateRequest):
    try:
        print(f"--- SERVER: ATOMIC TEST: Получены данные: {project_data.name} ---")
        project_id = str(uuid.uuid4())

        project_dir = PROJECTS_DIR / project_id
        files_dir = project_dir / "files"

        print(f"--- SERVER: ATOMIC TEST: Создаю директорию: {project_dir} ---")
        project_dir.mkdir(exist_ok=True)

        print(f"--- SERVER: ATOMIC TEST: Создаю поддиректорию: {files_dir} ---")
        files_dir.mkdir(exist_ok=True)

        # For now, just confirm that the folders were created.
        if project_dir.is_dir() and files_dir.is_dir():
            print(f"--- SERVER: ATOMIC TEST: Директории успешно созданы. ---")
            return {"status": "success", "message": f"Проект '{project_data.name}' и папка для файлов созданы.", "project_id": project_id}
        else:
            raise HTTPException(status_code=500, detail="Не удалось создать директории на сервере.")

    except Exception as e:
        print(f"--- SERVER: ATOMIC TEST: КРИТИЧЕСКАЯ ОШИБКА: {e} ---")
        raise HTTPException(status_code=500, detail=str(e))


# --- Other endpoints are temporarily disabled by commenting them out or can be left as is ---
# ... (all other endpoints would be here, but we are focusing on the one above)


# ==============================================================================
# 5. Static Files & HTML Routes
# ==============================================================================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_root():
    return FileResponse(STATIC_DIR / "index.html")

# ==============================================================================
# 6. Startup Logic
# ==============================================================================
@app.on_event("startup")
async def startup_event():
    STATIC_DIR.mkdir(exist_ok=True)
    RULES_DIR.mkdir(exist_ok=True)
    PROJECTS_DIR.mkdir(exist_ok=True)
    if not TEMPLATES_FILE.exists():
        TEMPLATES_FILE.write_text("[]")

    # For this atomic test, we don't need to load rules.
    # load_rules()