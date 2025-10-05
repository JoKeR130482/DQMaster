import os
import importlib.util
from pathlib import Path
import uuid
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
import inspect
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import io
import json

# --- Globals & Setup ---

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RULES_DIR = BASE_DIR / "rules"
UPLOADS_DIR = BASE_DIR / "uploads"
PROJECTS_DIR = BASE_DIR / "projects"
TEMPLATES_FILE = BASE_DIR / "templates.json"
RULE_REGISTRY = {}

# --- Ensure core directories exist ---
STATIC_DIR.mkdir(exist_ok=True)
RULES_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)
if not TEMPLATES_FILE.exists():
    TEMPLATES_FILE.write_text("[]")

# --- Rule Discovery and Loading ---

def load_rules():
    """
    Discovers and loads validation rules from the 'rules' directory.
    Also checks for configurable rules and their formatters.
    """
    RULE_REGISTRY.clear()
    for filename in os.listdir(RULES_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            rule_id = filename[:-3]
            module_path = RULES_DIR / filename
            try:
                spec = importlib.util.spec_from_file_location(rule_id, module_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    if hasattr(module, "validate") and hasattr(module, "RULE_NAME"):
                        RULE_REGISTRY[rule_id] = {
                            "id": rule_id,
                            "name": module.RULE_NAME,
                            "description": getattr(module, "RULE_DESC", ""),
                            "validator": module.validate,
                            "is_configurable": getattr(module, "IS_CONFIGURABLE", False),
                            "formatter": getattr(module, "format_name", None)
                        }
            except Exception as e:
                print(f"Error loading rule from {filename}: {e}")

def setup_default_rule():
    """
    Creates the default 'starts_with_capital' rule if it doesn't exist.
    """
    default_rule_path = RULES_DIR / "starts_with_capital.py"
    if not default_rule_path.exists():
        content = """
import re

RULE_NAME = "Начинается с заглавной"
RULE_DESC = "Проверяет, что значение является строкой и начинается с заглавной буквы (кириллица или латиница)."

def validate(value):
    if not isinstance(value, str):
        return False
    pattern = r'^[A-ZА-Я]'
    return re.match(pattern, value) is not None
"""
        with open(default_rule_path, "w", encoding="utf-8") as f:
            f.write(content.strip())
        print("Created default rule file: starts_with_capital.py")

@app.on_event("startup")
async def startup_event():
    """
    On application startup, set up directories and load rules.
    """
    setup_default_rule()
    load_rules()

# --- Static Files & HTML Routes ---

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/projects/{project_id}")
async def read_project_page(project_id: str):
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir():
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

# --- Pydantic Models ---

class RuleConfig(BaseModel):
    id: str
    params: Optional[Dict[str, Any]] = None

class SheetSelectRequest(BaseModel):
    fileId: str
    sheetName: str

class ColumnConfig(BaseModel):
    is_required: bool = False
    rules: List[RuleConfig] = []

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

# --- Template Helper Functions ---

def read_templates() -> List[Template]:
    """
    Reads templates from the JSON file.
    Includes migration logic to handle a legacy format where column rules were a
    direct list instead of an object containing 'is_required' and 'rules'.
    """
    if not TEMPLATES_FILE.exists():
        return []

    try:
        raw_data = TEMPLATES_FILE.read_text(encoding="utf-8")
        # Handle case where file is empty
        if not raw_data.strip():
            return []
        templates_data = json.loads(raw_data)
    except (json.JSONDecodeError, FileNotFoundError):
        # Return empty list if file is corrupt or doesn't exist
        return []

    needs_rewrite = False
    for template_dict in templates_data:
        # Ensure rules is a dict before iterating
        if "rules" in template_dict and isinstance(template_dict["rules"], dict):
            rules = template_dict["rules"]
            for col_name, col_config in rules.items():
                # Check if the value is a list (old format)
                if isinstance(col_config, list):
                    # Convert to new format
                    rules[col_name] = {"is_required": False, "rules": col_config}
                    needs_rewrite = True

    # Now, validate and create Pydantic objects
    try:
        validated_templates = [Template(**t) for t in templates_data]
    except Exception as e:
        print(f"Pydantic validation failed after migration attempt: {e}")
        return []

    # If we made changes, write them back to the file
    if needs_rewrite:
        write_templates(validated_templates)

    return validated_templates

def write_templates(templates: List[Template]):
    """Saves a list of Template objects to the JSON file."""
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        # For Pydantic v2, model_dump() is used to get a dictionary.
        json_data = [t.model_dump() for t in templates]
        json.dump(json_data, f, indent=2, ensure_ascii=False)


# --- API Endpoints ---

@app.get("/api/rules")
async def get_all_rules():
    """
    Returns a list of all available validation rules, excluding the validator function.
    """
    serializable_rules = [
        {"id": data["id"], "name": data["name"], "description": data["description"], "is_configurable": data["is_configurable"]}
        for data in RULE_REGISTRY.values()
    ]
    return JSONResponse(content=serializable_rules)

@app.post("/api/projects/{project_id}/upload")
async def upload_file_to_project(project_id: str, file: UploadFile = File(...)):
    """
    Saves an uploaded file to a specific project, updates project.json,
    and returns the file info and sheet names.
    """
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file.")

    project_files_dir = PROJECTS_DIR / project_id / "files"
    project_files_dir.mkdir(exist_ok=True)

    try:
        contents = await file.read()

        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        saved_filename = f"{file_id}{file_extension}"
        file_path = project_files_dir / saved_filename

        with open(file_path, "wb") as f:
            f.write(contents)

        xls = pd.ExcelFile(io.BytesIO(contents))
        sheet_names = xls.sheet_names

        # If a file already exists, remove it. This simplifies the UI to one file per project.
        if project.files:
            for old_file in project.files:
                old_file_path = project_files_dir / old_file['saved_name']
                if old_file_path.exists():
                    old_file_path.unlink()

        file_info = {
            "id": file_id,
            "original_name": file.filename,
            "saved_name": saved_filename,
            "sheets": sheet_names
        }
        project.files = [file_info]
        project.rules = {} # Reset rules on new file upload

        write_project(project_id, project)

        return file_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@app.post("/api/projects/{project_id}/select-sheet")
async def select_project_sheet(project_id: str, request: SheetSelectRequest):
    """
    Reads a specific sheet from a file within a project and returns its columns.
    """
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    file_info = next((f for f in project.files if f['id'] == request.fileId), None)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found in project")

    file_path = PROJECTS_DIR / project_id / "files" / file_info['saved_name']
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File data not found on disk.")

    try:
        df = pd.read_excel(file_path, sheet_name=request.sheetName)
        columns = df.columns.tolist()
        return {"columns": columns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read sheet: {str(e)}")

@app.post("/api/projects/{project_id}/validate")
async def validate_project_data(project_id: str, request: ValidationRequest):
    """
    Validates data from a file in a project, saves the applied rule configuration,
    and returns validation results.
    """
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Save the rule configuration to the project
    project.rules = request.rules
    write_project(project_id, project)

    file_info = next((f for f in project.files if f['id'] == request.fileId), None)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found in project")

    file_path = PROJECTS_DIR / project_id / "files" / file_info['saved_name']
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File data not found on disk.")

    try:
        df = pd.read_excel(file_path, sheet_name=request.sheetName)
        errors = []
        total_rows = len(df)

        for col_name, col_config in request.rules.items():
            if col_name not in df.columns:
                continue

            for index, value in df[col_name].items():
                if col_config.is_required and (pd.isna(value) or (isinstance(value, str) and not value.strip())):
                    errors.append({
                        "row": index + 2, "column": col_name, "value": "ПУСТО",
                        "rule_name": "Обязательное поле",
                        "error": "Поле не должно быть пустым"
                    })

                for config in col_config.rules:
                    rule = RULE_REGISTRY.get(config.id)
                    if not rule: continue

                    validator = rule["validator"]
                    sig = inspect.signature(validator)
                    is_valid = validator(value, params=config.params) if 'params' in sig.parameters else validator(value)

                    if not is_valid:
                        formatter = rule.get("formatter")
                        rule_name_for_error = formatter(config.params) if formatter and config.params else rule["name"]
                        errors.append({
                            "row": index + 2, "column": col_name, "value": str(value),
                            "rule_name": rule_name_for_error,
                            "error": f"Значение '{value}' не прошло проверку '{rule_name_for_error}'"
                        })

        error_rows_set = {e["row"] for e in errors}

        return {
            "total_rows": total_rows,
            "error_rows_count": len(error_rows_set),
            "errors": errors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

# --- Project Management Models ---

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    created_at: str
    updated_at: str
    files: List[Dict[str, Any]] = []
    rules: Dict[str, ColumnConfig] = {}

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

# --- Project Helper Functions ---

def read_project(project_id: str) -> Optional[Project]:
    config_path = PROJECTS_DIR / project_id / "project.json"
    if not config_path.exists():
        return None
    try:
        # Pydantic will validate the data upon instantiation
        return Project(**json.loads(config_path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"Error reading or validating project {project_id}: {e}")
        return None

def write_project(project_id: str, project_data: Project):
    import datetime
    config_path = PROJECTS_DIR / project_id / "project.json"
    project_data.updated_at = datetime.datetime.utcnow().isoformat()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(project_data.model_dump(), f, indent=2, ensure_ascii=False)


# --- Project API Endpoints ---

@app.post("/api/projects", status_code=201, response_model=Project)
async def create_project(project_data: ProjectCreateRequest):
    import datetime

    project_id = str(uuid.uuid4())
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(exist_ok=True)

    now = datetime.datetime.utcnow().isoformat()

    project_info = Project(
        id=project_id,
        name=project_data.name,
        description=project_data.description,
        created_at=now,
        updated_at=now,
    )

    write_project(project_id, project_info)
    return project_info

@app.get("/api/projects")
async def get_projects():
    projects = []
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            project = read_project(project_dir.name)
            if project:
                total_size = sum(f.stat().st_size for f in project_dir.glob('**/*') if f.is_file())
                project_dict = project.model_dump()
                project_dict["size_kb"] = round(total_size / 1024, 2)
                projects.append(project_dict)

    projects.sort(key=lambda p: p['updated_at'], reverse=True)
    return projects

@app.get("/api/projects/{project_id}", response_model=Project)
async def get_project_details(project_id: str):
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    import shutil
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        shutil.rmtree(project_dir)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Error deleting project directory: {e}")

class ProjectUpdateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

@app.put("/api/projects/{project_id}", response_model=Project)
async def update_project(project_id: str, project_update: ProjectUpdateRequest):
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.name = project_update.name
    project.description = project_update.description

    write_project(project_id, project)

    return project


# --- Template API Endpoints ---

@app.get("/api/templates", response_model=List[Template])
async def get_templates():
    """Returns a list of all saved validation templates."""
    return read_templates()

@app.post("/api/templates", response_model=Template, status_code=201)
async def create_template(template: Template):
    """Saves a new validation template."""
    templates = read_templates()
    if any(t.name.lower() == template.name.lower() for t in templates):
        raise HTTPException(status_code=400, detail=f"A template with the name '{template.name}' already exists.")
    templates.append(template)
    write_templates(templates)
    return template

@app.put("/api/templates/{template_id}", response_model=Template)
async def update_template(template_id: str, template_update: Template):
    """Updates an existing template."""
    templates = read_templates()

    template_index = -1
    for i, t in enumerate(templates):
        if t.id == template_id:
            template_index = i
            break

    if template_index == -1:
        raise HTTPException(status_code=404, detail="Template not found.")

    # Check if the new name is already used by another template
    if any(t.name.lower() == template_update.name.lower() and t.id != template_id for t in templates):
        raise HTTPException(status_code=400, detail=f"A template with the name '{template_update.name}' already exists.")

    # Update the template in the list
    template_update.id = template_id # Ensure the ID from the path is used
    templates[template_index] = template_update

    write_templates(templates)
    return template_update

@app.delete("/api/templates/{template_id}", status_code=204)
async def delete_template(template_id: str):
    """Deletes a validation template by its ID."""
    templates = read_templates()
    initial_len = len(templates)
    templates = [t for t in templates if t.id != template_id]
    if len(templates) == initial_len:
        raise HTTPException(status_code=404, detail="Template not found.")
    write_templates(templates)
    return

@app.post("/api/templates/find-matches", response_model=List[Template])
async def find_matching_templates(request: MatchRequest):
    """Finds templates that have the same set of columns as the input."""
    templates = read_templates()
    # Using sets for order-insensitive comparison
    request_columns_set = set(request.columns)
    matching_templates = [
        t for t in templates if set(t.columns) == request_columns_set
    ]
    return matching_templates
