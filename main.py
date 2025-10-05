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
from fastapi.responses import FileResponse
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
# 2. Pydantic Models
# ==============================================================================

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

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

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
# 3. Helper Functions
# ==============================================================================

def read_project(project_id: str) -> Optional[Project]:
    config_path = PROJECTS_DIR / project_id / "project.json"
    if not config_path.exists(): return None
    try:
        return Project(**json.loads(config_path.read_text(encoding="utf-8")))
    except Exception as e:
        print(f"Error reading project {project_id}: {e}")
        return None

def write_project(project_id: str, project_data: Project):
    config_path = PROJECTS_DIR / project_id / "project.json"
    project_data.updated_at = datetime.datetime.utcnow().isoformat()
    config_path.write_text(project_data.model_dump_json(indent=2), encoding="utf-8")

def read_templates() -> List[Template]:
    if not TEMPLATES_FILE.exists(): return []
    try:
        raw_data = TEMPLATES_FILE.read_text(encoding="utf-8")
        if not raw_data.strip(): return []
        return [Template(**t) for t in json.loads(raw_data)]
    except Exception as e:
        print(f"Error reading templates: {e}")
        return []

def write_templates(templates: List[Template]):
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump([t.model_dump() for t in templates], f, indent=2, ensure_ascii=False)

def load_rules():
    RULE_REGISTRY.clear()
    for filename in os.listdir(RULES_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            try:
                spec = importlib.util.spec_from_file_location(filename[:-3], RULES_DIR / filename)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "validate") and hasattr(module, "RULE_NAME"):
                        RULE_REGISTRY[filename[:-3]] = {
                            "id": filename[:-3],
                            "name": module.RULE_NAME,
                            "description": getattr(module, "RULE_DESC", ""),
                            "validator": module.validate,
                            "is_configurable": getattr(module, "IS_CONFIGURABLE", False),
                            "formatter": getattr(module, "format_name", None)
                        }
            except Exception as e:
                print(f"Error loading rule from {filename}: {e}")

# ==============================================================================
# 4. API Endpoints
# ==============================================================================

# --- Project Management ---
@app.get("/api/projects", response_model=List[ProjectInfo])
async def get_projects():
    projects = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            project = read_project(project_dir.name)
            if project:
                total_size = sum(f.stat().st_size for f in project_dir.glob('**/*') if f.is_file())
                project_info = ProjectInfo(
                    **project.model_dump(),
                    size_kb=round(total_size / 1024, 2)
                )
                projects.append(project_info)
    projects.sort(key=lambda p: p.updated_at, reverse=True)
    return projects

# NEW, RENAMED ENDPOINT FOR DEBUGGING
@app.post("/api/create_new_project_test", status_code=201, response_model=Project)
async def create_project_test(project_data: ProjectCreateRequest):
    project_id = str(uuid.uuid4())
    (PROJECTS_DIR / project_id).mkdir(exist_ok=True)
    now = datetime.datetime.utcnow().isoformat()
    project = Project(id=project_id, name=project_data.name, description=project_data.description, created_at=now, updated_at=now)
    write_project(project_id, project)
    return project

@app.get("/api/projects/{project_id}", response_model=Project)
async def get_project_details(project_id: str):
    project = read_project(project_id)
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    return project

@app.put("/api/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, project_update: ProjectUpdateRequest):
    project = read_project(project_id)
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    project.name = project_update.name
    project.description = project_update.description
    write_project(project_id, project)
    return project

@app.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir(): raise HTTPException(status_code=404, detail="Project not found")
    shutil.rmtree(project_dir)

# --- Project File & Validation Operations ---
@app.post("/api/projects/{project_id}/upload")
async def upload_file_to_project(project_id: str, file: UploadFile = File(...)):
    project = read_project(project_id)
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    project_files_dir = PROJECTS_DIR / project_id / "files"
    project_files_dir.mkdir(exist_ok=True)

    if project.files:
        for old_file in project.files:
            old_file_path = project_files_dir / old_file['saved_name']
            if old_file_path.exists(): old_file_path.unlink()

    contents = await file.read()
    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}{Path(file.filename).suffix}"
    (project_files_dir / saved_filename).write_bytes(contents)

    file_info = {
        "id": file_id, "original_name": file.filename, "saved_name": saved_filename,
        "sheets": pd.ExcelFile(io.BytesIO(contents)).sheet_names
    }
    project.files = [file_info]
    project.rules = {}
    write_project(project_id, project)
    return file_info

@app.post("/api/projects/{project_id}/select-sheet")
async def select_project_sheet(project_id: str, request: SheetSelectRequest):
    project = read_project(project_id)
    if not project or not project.files: raise HTTPException(status_code=404, detail="Project or file not found")

    file_info = next((f for f in project.files if f['id'] == request.fileId), None)
    if not file_info: raise HTTPException(status_code=404, detail="File ID not found in project")

    file_path = PROJECTS_DIR / project_id / "files" / file_info['saved_name']
    if not file_path.exists(): raise HTTPException(status_code=404, detail="File data not found on disk")

    df = pd.read_excel(file_path, sheet_name=request.sheetName)
    return {"columns": df.columns.tolist()}

@app.post("/api/projects/{project_id}/validate")
async def validate_project_data(project_id: str, request: ValidationRequest):
    project = read_project(project_id)
    if not project or not project.files: raise HTTPException(status_code=404, detail="Project or file not found")

    project.rules = request.rules
    write_project(project_id, project)

    file_info = next((f for f in project.files if f['id'] == request.fileId), None)
    if not file_info: raise HTTPException(status_code=404, detail="File not found in project")

    file_path = PROJECTS_DIR / project_id / "files" / file_info['saved_name']
    if not file_path.exists(): raise HTTPException(status_code=404, detail="File data not found on disk")

    df = pd.read_excel(file_path, sheet_name=request.sheetName)
    errors = []
    for col_name, col_config in request.rules.items():
        if col_name not in df.columns: continue
        for index, value in df[col_name].items():
            if col_config.is_required and (pd.isna(value) or str(value).strip() == ""):
                errors.append({"row": index + 2, "column": col_name, "value": "ПУСТО", "rule_name": "Обязательное поле", "error": "Поле не должно быть пустым"})
            for config in col_config.rules:
                rule = RULE_REGISTRY.get(config.id)
                if not rule: continue
                validator = rule["validator"]
                is_valid = validator(value, params=config.params) if 'params' in inspect.signature(validator).parameters else validator(value)
                if not is_valid:
                    formatter = rule.get("formatter")
                    rule_name_for_error = formatter(config.params) if formatter and config.params else rule["name"]
                    errors.append({"row": index + 2, "column": col_name, "value": str(value), "rule_name": rule_name_for_error, "error": f"Validation failed"})

    return {"total_rows": len(df), "error_rows_count": len({e["row"] for e in errors}), "errors": errors}

# --- Rule & Template Library ---
@app.get("/api/rules")
async def get_all_rules():
    return [{"id": data["id"], "name": data["name"], "description": data["description"], "is_configurable": data["is_configurable"]} for data in RULE_REGISTRY.values()]

@app.get("/api/templates", response_model=List[Template])
async def get_templates():
    return read_templates()

@app.post("/api/templates", response_model=Template, status_code=201)
async def create_template(template: Template):
    templates = read_templates()
    if any(t.name.lower() == template.name.lower() for t in templates):
        raise HTTPException(status_code=400, detail=f"Template name '{template.name}' already exists.")
    templates.append(template)
    write_templates(templates)
    return template

@app.put("/api/templates/{template_id}", response_model=Template)
async def update_template(template_id: str, template_update: Template):
    templates = read_templates()
    template_index = next((i for i, t in enumerate(templates) if t.id == template_id), -1)
    if template_index == -1: raise HTTPException(status_code=404, detail="Template not found.")
    if any(t.name.lower() == template_update.name.lower() and t.id != template_id for t in templates):
        raise HTTPException(status_code=400, detail=f"Template name '{template_update.name}' already exists.")
    template_update.id = template_id
    templates[template_index] = template_update
    write_templates(templates)
    return template_update

@app.delete("/api/templates/{template_id}", status_code=204)
async def delete_template(template_id: str):
    templates = read_templates()
    if not any(t.id == template_id for t in templates):
        raise HTTPException(status_code=404, detail="Template not found.")
    write_templates([t for t in templates if t.id != template_id])

@app.post("/api/templates/find-matches", response_model=List[Template])
async def find_matching_templates(request: MatchRequest):
    templates = read_templates()
    request_columns_set = set(request.columns)
    return [t for t in templates if set(t.columns) == request_columns_set]

# ==============================================================================
# 5. Static Files & HTML Routes
# ==============================================================================
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/projects/{project_id}")
async def read_project_page(project_id: str):
    if not (PROJECTS_DIR / project_id).is_dir():
        raise HTTPException(status_code=404, detail="Project not found")
    return FileResponse(STATIC_DIR / "project.html")

@app.get("/rules")
async def read_rules_page():
    return FileResponse(STATIC_DIR / "rules.html")

@app.get("/templates")
async def read_templates_page():
    return FileResponse(STATIC_DIR / "templates.html")

@app.get("/templates/edit/{template_id}")
async def read_edit_template_page(template_id: str):
    return FileResponse(STATIC_DIR / "edit_template.html")

# ==============================================================================
# 6. Startup Logic
# ==============================================================================
def setup_default_rule():
    default_rule_path = RULES_DIR / "starts_with_capital.py"
    if not default_rule_path.exists():
        content = """
import re
RULE_NAME = "Начинается с заглавной"
RULE_DESC = "Проверяет, что значение является строкой и начинается с заглавной буквы."
def validate(value):
    if not isinstance(value, str): return False
    return re.match(r'^[A-ZА-Я]', value) is not None
"""
        default_rule_path.write_text(content.strip(), encoding="utf-8")
        print("Created default rule file: starts_with_capital.py")

@app.on_event("startup")
async def startup_event():
    STATIC_DIR.mkdir(exist_ok=True)
    RULES_DIR.mkdir(exist_ok=True)
    PROJECTS_DIR.mkdir(exist_ok=True)
    if not TEMPLATES_FILE.exists():
        TEMPLATES_FILE.write_text("[]")

    setup_default_rule()
    load_rules()