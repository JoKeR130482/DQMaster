import os
import json
import uuid
import datetime
from pathlib import Path
from typing import List, Optional
import shutil

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ==============================================================================
# 1. Globals & App Initialization
# ==============================================================================
app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROJECTS_DIR = BASE_DIR / "projects"

# ==============================================================================
# 2. Pydantic Models
# ==============================================================================
class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    created_at: str
    updated_at: str
    files: List[dict] = []
    rules: dict = {}

class ProjectInfo(Project):
    size_kb: float

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

# ==============================================================================
# 3. Helper Functions
# ==============================================================================
def read_project(project_id: str) -> Optional[Project]:
    config_path = PROJECTS_DIR / project_id / "project.json"
    if not config_path.exists(): return None
    try:
        return Project(**json.loads(config_path.read_text(encoding="utf-8")))
    except Exception:
        return None

def write_project(project_id: str, project_data: Project):
    config_path = PROJECTS_DIR / project_id / "project.json"
    project_data.updated_at = datetime.datetime.utcnow().isoformat()
    config_path.write_text(project_data.model_dump_json(indent=2), encoding="utf-8")

# ==============================================================================
# 4. API Endpoints
# ==============================================================================
@app.get("/api/projects", response_model=List[ProjectInfo])
async def get_projects():
    projects = []
    if not PROJECTS_DIR.exists():
        return projects
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            project = read_project(project_dir.name)
            if project:
                total_size = sum(f.stat().st_size for f in project_dir.glob('**/*') if f.is_file())
                project_info = ProjectInfo(**project.model_dump(), size_kb=round(total_size / 1024, 2))
                projects.append(project_info)
    projects.sort(key=lambda p: p.updated_at, reverse=True)
    return projects

@app.post("/api/projects", status_code=201, response_model=Project)
async def create_project(project_data: ProjectCreateRequest):
    project_id = str(uuid.uuid4())
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(exist_ok=True)
    (project_dir / "files").mkdir(exist_ok=True)
    now = datetime.datetime.utcnow().isoformat()
    project = Project(id=project_id, name=project_data.name, description=project_data.description, created_at=now, updated_at=now)
    write_project(project_id, project)
    return project

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

# Minimal routes for now
@app.get("/rules")
async def read_rules_page():
    return FileResponse(STATIC_DIR / "rules.html")

@app.get("/templates")
async def read_templates_page():
    return FileResponse(STATIC_DIR / "templates.html")

# ==============================================================================
# 6. Startup Logic
# ==============================================================================
@app.on_event("startup")
async def startup_event():
    STATIC_DIR.mkdir(exist_ok=True)
    PROJECTS_DIR.mkdir(exist_ok=True)
    print("--- Server is running with a minimal main.py ---")