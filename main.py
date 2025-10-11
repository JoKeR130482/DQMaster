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
from pydantic import BaseModel, Field, ValidationError
from rules import spell_check

# ==============================================================================
# 1. Globals & App Initialization
# ==============================================================================
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RULES_DIR = BASE_DIR / "rules"
PROJECTS_DIR = BASE_DIR / "projects"
RULE_REGISTRY = {}

# ==============================================================================
# 2. Pydantic Models (New Hierarchical Structure)
# ==============================================================================

class Rule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    value: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    order: int

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
    name: str # Original filename
    saved_name: str # UUID-based filename on disk
    sheets: List[SheetSchema] = []

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    created_at: str
    updated_at: str
    files: List[FileSchema] = []

# --- API Request/Response Models ---

class ProjectInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    updated_at: str
    size_kb: float

class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""

class ProjectPartialUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class FullProjectUpdateRequest(Project):
    pass

# ==============================================================================
# 3. Helper Functions
# ==============================================================================

def read_project(project_id: str) -> Optional[Project]:
    config_path = PROJECTS_DIR / project_id / "project.json"
    if not config_path.exists():
        return None
    try:
        return Project(**json.loads(config_path.read_text(encoding="utf-8")))
    except (ValidationError, json.JSONDecodeError) as e:
        print(f"WARNING: Corrupted project file for '{project_id}'. Creating a stub. Reason: {e}")
        now = datetime.datetime.utcnow().isoformat()
        return Project(
            id=project_id,
            name=f"Поврежденный проект: {project_id}",
            description="Этот файл проекта поврежден или имеет неверный формат. Рекомендуется удалить его.",
            created_at=now,
            updated_at=now,
            files=[]
        )

def write_project(project_id: str, project_data: Project):
    config_path = PROJECTS_DIR / project_id / "project.json"
    project_data.updated_at = datetime.datetime.utcnow().isoformat()
    config_path.write_text(project_data.model_dump_json(indent=2), encoding="utf-8")

def load_rules():
    RULE_REGISTRY.clear()
    if not RULES_DIR.exists(): return
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
                            "formatter": getattr(module, "format_name", None),
                            "params_schema": getattr(module, "PARAMS_SCHEMA", None)
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
    if not PROJECTS_DIR.exists():
        return projects
    for project_dir in PROJECTS_DIR.iterdir():
        if project_dir.is_dir():
            project = read_project(project_dir.name)
            if project:
                total_size = sum(f.stat().st_size for f in project_dir.glob('**/*') if f.is_file())
                project_info = ProjectInfo(
                    id=project.id,
                    name=project.name,
                    description=project.description,
                    updated_at=project.updated_at,
                    size_kb=round(total_size / 1024, 2)
                )
                projects.append(project_info)
    projects.sort(key=lambda p: p.updated_at, reverse=True)
    return projects

@app.post("/api/projects", status_code=201, response_model=Project)
async def create_project(project_data: ProjectCreateRequest):
    project_id = str(uuid.uuid4())
    project_dir = PROJECTS_DIR / project_id
    # Ensure the base projects directory and the new project directory are created.
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "files").mkdir(exist_ok=True)
    now = datetime.datetime.utcnow().isoformat()
    project = Project(id=project_id, name=project_data.name, description=project_data.description, created_at=now, updated_at=now)
    write_project(project_id, project)
    return project

@app.get("/api/projects/{project_id}", response_model=Project)
async def get_project_details(project_id: str):
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@app.put("/api/projects/{project_id}", response_model=Project)
async def update_full_project(project_id: str, project_update: FullProjectUpdateRequest):
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")

    project_update.id = project_id
    write_project(project_id, project_update)
    return project_update

@app.patch("/api/projects/{project_id}", response_model=Project)
async def partial_update_project(project_id: str, project_update: ProjectPartialUpdateRequest):
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = project_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated_project = project.model_copy(update=update_data)
    write_project(project_id, updated_project)
    return updated_project

@app.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir(): raise HTTPException(status_code=404, detail="Project not found")
    shutil.rmtree(project_dir)

# --- Project File & Validation Operations ---
@app.post("/api/projects/{project_id}/upload", response_model=Project)
async def upload_file_to_project(project_id: str, file: UploadFile = File(...)):
    project = read_project(project_id)
    if not project: raise HTTPException(status_code=404, detail="Project not found")
    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type")

    project_files_dir = PROJECTS_DIR / project_id / "files"
    project_files_dir.mkdir(exist_ok=True)

    contents = await file.read()

    try:
        xls = pd.ExcelFile(io.BytesIO(contents))
        sheets = []
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            fields = [FieldSchema(name=col) for col in df.columns]
            sheets.append(SheetSchema(name=sheet_name, fields=fields))

        saved_filename = f"{uuid.uuid4()}{Path(file.filename).suffix}"
        new_file = FileSchema(name=file.filename, saved_name=saved_filename, sheets=sheets)
        project.files.append(new_file)

        write_project(project_id, project)

        # Save the actual file with a unique name
        (project_files_dir / saved_filename).write_bytes(contents)

        return project

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not process Excel file: {e}")


@app.post("/api/projects/{project_id}/validate")
async def validate_project_data(project_id: str):
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_files_dir = PROJECTS_DIR / project_id / "files"

    project_total_rows = 0
    all_errors = [] # A flat list of all errors from all files/sheets

    # --- Step 1: Gather ALL errors from all files/sheets ---
    for file_schema in project.files:
        file_path = project_files_dir / file_schema.saved_name
        if not file_path.exists():
            continue

        for sheet_schema in file_schema.sheets:
            if not sheet_schema.is_active:
                continue

            try:
                df = pd.read_excel(file_path, sheet_name=sheet_schema.name)
                sheet_total_rows = len(df)
                if sheet_total_rows == 0:
                    continue

                project_total_rows += sheet_total_rows

                for field_schema in sheet_schema.fields:
                    if field_schema.name not in df.columns:
                        continue

                    # Process all configured rules for the current field
                    for rule_config in sorted(field_schema.rules, key=lambda r: r.order):
                        rule_def = RULE_REGISTRY.get(rule_config.type)
                        if not rule_def: continue

                        validator = rule_def["validator"]
                        params = rule_config.params or {}
                        formatter = rule_def.get("formatter")
                        rule_name = formatter(params) if formatter and params else rule_def["name"]

                        for index, value in df[field_schema.name].items():
                            result = validator(value, params=params) if 'params' in inspect.signature(validator).parameters else validator(value)

                            is_valid = False
                            details = None

                            if isinstance(result, bool):
                                is_valid = result
                            elif isinstance(result, dict):
                                is_valid = result.get("is_valid", False)
                                details = result.get("errors")

                            if not is_valid:
                                error_entry = {
                                    "file_name": file_schema.name,
                                    "sheet_name": sheet_schema.name,
                                    "field_name": field_schema.name,
                                    "is_required": field_schema.is_required,
                                    "row": index + 2,
                                    "error_type": rule_name,
                                    "value": str(value) if pd.notna(value) else "ПУСТО"
                                }
                                if details:
                                    error_entry["details"] = details
                                all_errors.append(error_entry)

            except Exception as e:
                print(f"Error processing sheet {sheet_schema.name} in file {file_schema.name}: {e}")
                continue

    # --- Step 2: Post-process the flat list of errors ---

    # 2.1: Calculate main statistic: unique rows with errors in required fields
    required_field_errors = [e for e in all_errors if e["is_required"]]
    unique_error_row_keys = {f"{e['file_name']}-{e['sheet_name']}-{e['row']}" for e in required_field_errors}

    # 2.2: Build per-sheet summaries
    file_results = []
    for file_schema in project.files:
        sheet_summaries = []
        for sheet_schema in file_schema.sheets:
            if not sheet_schema.is_active: continue

            # Get all rule names that *could* apply to this sheet
            all_applicable_rule_names = set()
            for f in sheet_schema.fields:
                for r_conf in f.rules:
                    r_def = RULE_REGISTRY.get(r_conf.type)
                    if r_def:
                        formatter = r_def.get("formatter")
                        rule_name = formatter(r_conf.params) if formatter and r_conf.params else r_def["name"]
                        all_applicable_rule_names.add(rule_name)

            # Group errors for this sheet
            sheet_errors = [e for e in all_errors if e["file_name"] == file_schema.name and e["sheet_name"] == sheet_schema.name]

            summary_list = []
            if all_applicable_rule_names: # Only build summary if there are rules
                df_sheet = pd.read_excel(PROJECTS_DIR / project_id / "files" / file_schema.saved_name, sheet_name=sheet_schema.name)
                sheet_total_rows = len(df_sheet)

                for rule_name in sorted(list(all_applicable_rule_names)):
                    rule_errors = [e for e in sheet_errors if e["error_type"] == rule_name]
                    error_count = len(rule_errors)

                    summary_list.append({
                        "rule_name": rule_name,
                        "error_count": error_count,
                        "error_percentage": round((error_count / sheet_total_rows) * 100, 2) if sheet_total_rows > 0 else 0,
                        "detailed_errors": rule_errors
                    })

                summary_list.sort(key=lambda x: x['error_count'], reverse=True)

            # Calculate sheet-specific error row count and percentage
            sheet_error_row_keys = {e['row'] for e in sheet_errors}
            sheet_error_rows_count = len(sheet_error_row_keys)
            sheet_error_percentage = round((sheet_error_rows_count / sheet_total_rows) * 100, 2) if sheet_total_rows > 0 else 0

            sheet_summaries.append({
                "sheet_name": sheet_schema.name,
                "total_rows": sheet_total_rows,
                "sheet_error_rows_count": sheet_error_rows_count,
                "sheet_error_percentage": sheet_error_percentage,
                "rule_summaries": summary_list
            })

        if sheet_summaries:
            file_results.append({
                "file_name": file_schema.name,
                "sheets": sheet_summaries
            })

    # --- Step 3: Structure the final response ---
    response_data = {
        "total_processed_rows": project_total_rows,
        "required_field_error_rows_count": len(unique_error_row_keys),
        "required_field_errors": required_field_errors,
        "file_results": file_results,
        "validated_at": datetime.datetime.utcnow().isoformat()
    }

    # --- Step 4: Save the results to a file ---
    results_path = PROJECTS_DIR / project_id / "validation_result.json"
    results_path.write_text(json.dumps(response_data, indent=2), encoding="utf-8")

    return response_data

@app.get("/api/projects/{project_id}/results")
async def get_validation_results(project_id: str):
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")

    results_path = project_dir / "validation_result.json"
    if not results_path.exists():
        raise HTTPException(status_code=404, detail="No validation results found for this project.")

    return FileResponse(results_path)

# --- Dictionary Management ---
CUSTOM_DICT_PATH = Path(__file__).resolve().parent / "custom_dictionary.txt"

@app.get("/api/dictionary", response_model=List[str])
async def get_dictionary():
    if not CUSTOM_DICT_PATH.exists():
        return []
    words = CUSTOM_DICT_PATH.read_text(encoding="utf-8").strip().split("\n")
    return sorted([word for word in words if word]) # Return sorted, non-empty words

class AddWordRequest(BaseModel):
    word: str

@app.post("/api/dictionary", status_code=201)
async def add_word_to_dictionary(request: AddWordRequest):
    new_word = request.word.strip().lower()
    if not new_word:
        raise HTTPException(status_code=400, detail="Word cannot be empty.")

    current_words = set(get_dictionary.__wrapped__())
    if new_word in current_words:
        raise HTTPException(status_code=400, detail="Word already exists in the dictionary.")

    with CUSTOM_DICT_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\n{new_word}")

    spell_check.reload_custom_dictionary() # Hot-reload the dictionary
    return {"message": "Word added successfully."}

@app.delete("/api/dictionary/{word}", status_code=200)
async def remove_word_from_dictionary(word: str):
    word_to_delete = word.strip().lower()
    if not word_to_delete:
        raise HTTPException(status_code=400, detail="Word cannot be empty.")

    current_words = get_dictionary.__wrapped__()
    if word_to_delete not in current_words:
        raise HTTPException(status_code=404, detail="Word not found in the dictionary.")

    updated_words = [w for w in current_words if w.lower() != word_to_delete]
    CUSTOM_DICT_PATH.write_text("\n".join(updated_words), encoding="utf-8")

    spell_check.reload_custom_dictionary() # Hot-reload the dictionary
    return {"message": "Word removed successfully."}


# --- Rule Library ---
@app.get("/api/rules")
async def get_all_rules():
    rules_list = []
    for data in RULE_REGISTRY.values():
        rules_list.append({
            "id": data["id"],
            "name": data["name"],
            "description": data["description"],
            "is_configurable": data["is_configurable"],
            "params_schema": data.get("params_schema") # Use .get for safety, might be None
        })
    return rules_list

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

@app.get("/dictionary")
async def read_dictionary_page():
    return FileResponse(STATIC_DIR / "dictionary.html")

# ==============================================================================
# 6. Startup Logic
# ==============================================================================
@app.on_event("startup")
async def startup_event():
    STATIC_DIR.mkdir(exist_ok=True)
    RULES_DIR.mkdir(exist_ok=True)
    PROJECTS_DIR.mkdir(exist_ok=True)
    load_rules()