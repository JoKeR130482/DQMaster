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
import asyncio

from fastapi import Depends, FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

# ==============================================================================
# 1. Globals & App Initialization
# ==============================================================================
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RULES_DIR = BASE_DIR / "rules"
PROJECTS_DIR = BASE_DIR / "projects"
RULE_GROUPS_PATH = BASE_DIR / "rule_groups.json"
RULE_REGISTRY = {}
RULE_GROUPS_REGISTRY = {}
VALIDATION_STATUS = {}

# ==============================================================================
# 2. Pydantic Models (New Hierarchical Structure)
# ==============================================================================

from pydantic import root_validator

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
    name: str # Original filename
    saved_name: str # UUID-based filename on disk
    sheets: List[SheetSchema] = []

class RuleInGroup(BaseModel):
    id: str # Rule ID, e.g., "is_empty"
    params: Optional[Dict[str, Any]] = None

class RuleGroup(BaseModel):
    id: str = Field(default_factory=lambda: f"grp_{uuid.uuid4()}")
    name: str
    logic: str # "AND" or "OR"
    rules: List[RuleInGroup] = []

class Project(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    created_at: str
    updated_at: str
    files: List[FileSchema] = []
    auto_revalidate: bool = True

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

class ValidationStatus(BaseModel):
    is_running: bool
    current_file: str = ""
    current_sheet: str = ""
    current_field: str = ""
    current_rule: str = ""
    processed_rows: int = 0
    total_rows: int = 0
    percentage: float = 0.0
    message: str = ""

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
                            "params_schema": getattr(module, "PARAMS_SCHEMA", None),
                            "needs_column_access": getattr(module, "NEEDS_COLUMN_ACCESS", False),
                            "module": module
                        }
            except Exception as e:
                print(f"Error loading rule from {filename}: {e}")

def read_rule_groups():
    """Loads rule groups from the JSON file into the registry."""
    if not RULE_GROUPS_PATH.exists():
        return
    try:
        groups_data = json.loads(RULE_GROUPS_PATH.read_text(encoding="utf-8"))
        RULE_GROUPS_REGISTRY.clear()
        for group_dict in groups_data:
            group = RuleGroup(**group_dict)
            RULE_GROUPS_REGISTRY[group.id] = group
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"Error reading or parsing rule_groups.json: {e}")

def write_rule_groups():
    """Saves the current state of the rule groups registry to the JSON file."""
    try:
        if not RULE_GROUPS_PATH.exists():
            RULE_GROUPS_PATH.touch()
        groups_list = [group.model_dump() for group in RULE_GROUPS_REGISTRY.values()]
        RULE_GROUPS_PATH.write_text(json.dumps(groups_list, indent=2, ensure_ascii=False), encoding="utf-8")
    except IOError as e:
        print(f"Error writing to rule_groups.json: {e}")


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
        (project_files_dir / saved_filename).write_bytes(contents)
        return project
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not process Excel file: {e}")

def _validate_group(value: Any, group: RuleGroup) -> dict:
    """Helper to validate a single value against a rule group."""
    results = []
    for rule_ref in group.rules:
        rule_def = RULE_REGISTRY.get(rule_ref.id)
        if not rule_def:
            continue

        validator = rule_def["validator"]
        params = rule_ref.params or {}

        result = validator(value, params=params) if 'params' in inspect.signature(validator).parameters else validator(value)

        is_valid = result if isinstance(result, bool) else result.get("is_valid", False)
        results.append(is_valid)

    if group.logic == "AND":
        # Error if ALL rules are broken (all are invalid)
        is_error = all(not r for r in results)
    else:  # OR
        # Error if ANY rule is broken (at least one is invalid)
        is_error = any(not r for r in results)

    return {
        "is_valid": not is_error,
        "errors": group.name if is_error else None
    }


# Вспомогательная функция, определенная где-то в вашем файле
def get_rule_name_from_config(rule_config):
    if rule_config.group_id:
        group = RULE_GROUPS_REGISTRY.get(rule_config.group_id)
        return f"Группа: {group.name}" if group else "Неизвестная группа"

    rule_def = RULE_REGISTRY.get(rule_config.type)
    if not rule_def:
        return "Неизвестное правило"

    formatter = rule_def.get("formatter")
    return formatter(rule_config.params) if formatter and rule_config.params else rule_def["name"]


async def _calculate_total_operations(project_id: str, project: Project) -> int:
    """Асинхронный расчет общего количества операций для прогресса."""
    total_ops = 0
    project_files_dir = PROJECTS_DIR / project.id / "files"
    loop = asyncio.get_running_loop()
    try:
        for file_schema in project.files:
            file_path = project_files_dir / file_schema.saved_name
            if not file_path.exists():
                continue

            xls_content = await loop.run_in_executor(None, file_path.read_bytes)
            xls = pd.ExcelFile(io.BytesIO(xls_content))

            for sheet_schema in file_schema.sheets:
                if not sheet_schema.is_active:
                    continue
                try:
                    df = await loop.run_in_executor(None, pd.read_excel, xls, sheet_schema.name)
                    row_count = len(df)
                    rule_count = sum(len(field.rules) for field in sheet_schema.fields)
                    total_ops += row_count * rule_count
                except Exception as e:
                    # logger.warning(f"[{project_id}] Could not calculate ops for sheet {sheet_schema.name}: {e}")
                    continue
    except Exception as e:
        # logger.error(f"[{project_id}] Ошибка при расчете общего числа операций: {e}", exc_info=True)
        return 100 # Возвращаем значение по умолчанию при серьезной ошибке

    if total_ops <= 0:
        # logger.warning(f"[{project_id}] Общее количество операций равно 0. Установлено в 100 для отображения прогресса.")
        return 100

    return total_ops


async def _run_validation_async(project_id: str):
    """Асинхронная функция для выполнения валидации с корректным отображением прогресса."""
    VALIDATION_STATUS[project_id].update({
        "is_running": True, "percentage": 0.0, "processed_rows": 0, "message": "Подготовка к валидации..."
    })
    await asyncio.sleep(0.1)

    project = await asyncio.to_thread(read_project, project_id)
    if not project:
        VALIDATION_STATUS[project_id].update({"is_running": False, "message": "Ошибка: проект не найден."})
        return

    total_operations = await _calculate_total_operations(project_id, project)
    VALIDATION_STATUS[project_id].update({
        "total_rows": int(total_operations), "message": f"Начинаем проверку...", "percentage": 1.0
    })
    await asyncio.sleep(0.1)

    processed_ops_count = 0
    all_errors = []
    project_files_dir = PROJECTS_DIR / project.id / "files"
    loop = asyncio.get_running_loop()

    for file_schema in project.files:
        VALIDATION_STATUS[project_id]["current_file"] = file_schema.name
        file_path = project_files_dir / file_schema.saved_name
        if not file_path.exists(): continue

        for sheet_schema in file_schema.sheets:
            if not sheet_schema.is_active: continue

            VALIDATION_STATUS[project_id]["current_sheet"] = sheet_schema.name
            try:
                df = await loop.run_in_executor(None, pd.read_excel, file_path, sheet_name=sheet_schema.name)
                if df.empty: continue

                for field_schema in sheet_schema.fields:
                    if field_schema.name not in df.columns: continue

                    for rule_config in sorted(field_schema.rules, key=lambda r: r.order):
                        rule_name = get_rule_name_from_config(rule_config)
                        VALIDATION_STATUS[project_id].update({
                            "current_field": field_schema.name,
                            "current_rule": rule_name,
                            "message": f"Проверка: {field_schema.name} / {rule_name}"
                        })

                        # --- Реальная логика валидации ---
                        if rule_config.group_id:
                            group = RULE_GROUPS_REGISTRY.get(rule_config.group_id)
                            if not group:
                                processed_ops_count += len(df)
                                continue
                            for index, value in df[field_schema.name].items():
                                result = _validate_group(value, group)
                                if not result["is_valid"]:
                                     all_errors.append({
                                        "file_name": file_schema.name, "sheet_name": sheet_schema.name,
                                        "field_name": field_schema.name, "is_required": field_schema.is_required,
                                        "row": index + 2, "error_type": result["errors"],
                                        "value": str(value) if pd.notna(value) else "ПУСТО",
                                        "details": None
                                    })
                                processed_ops_count += 1
                        else:
                            rule_def = RULE_REGISTRY.get(rule_config.type)
                            if not rule_def:
                                processed_ops_count += len(df)
                                continue
                            validator = rule_def["validator"]
                            params = rule_config.params or {}
                            for index, value in df[field_schema.name].items():
                                result = validator(value, params=params) if 'params' in inspect.signature(validator).parameters else validator(value)
                                is_valid = result if isinstance(result, bool) else result.get("is_valid", False)
                                if not is_valid:
                                    details = result.get("errors") if isinstance(result, dict) else None
                                    all_errors.append({
                                        "file_name": file_schema.name, "sheet_name": sheet_schema.name,
                                        "field_name": field_schema.name, "is_required": field_schema.is_required,
                                        "row": index + 2, "error_type": rule_name,
                                        "value": str(value) if pd.notna(value) else "ПУСТО",
                                        "details": details
                                    })
                                processed_ops_count += 1

                        # --- Периодическое обновление статуса ---
                        if processed_ops_count % 100 == 0:
                            percentage = min(99.0, (processed_ops_count / total_operations) * 100) if total_operations > 0 else 0
                            VALIDATION_STATUS[project_id].update({
                                "processed_rows": processed_ops_count,
                                "percentage": percentage,
                            })
                            await asyncio.sleep(0.001)

            except Exception as e:
                continue

    # --- Сохранение результатов (ПОЛНАЯ ЛОГИКА) ---
    required_field_errors = [e for e in all_errors if e["is_required"]]
    unique_error_row_keys = {f"{e['file_name']}-{e['sheet_name']}-{e['row']}" for e in required_field_errors}
    file_results = []
    for file_schema in project.files:
        sheet_summaries = []
        for sheet_schema in file_schema.sheets:
            if not sheet_schema.is_active: continue
            try:
                df_sheet = pd.read_excel(PROJECTS_DIR / project.id / "files" / file_schema.saved_name, sheet_name=sheet_schema.name)
                sheet_total_rows = len(df_sheet)
            except Exception:
                sheet_total_rows = 0

            all_applicable_rule_names = {get_rule_name_from_config(r_conf) for f in sheet_schema.fields for r_conf in f.rules}
            sheet_errors = [e for e in all_errors if e["file_name"] == file_schema.name and e["sheet_name"] == sheet_schema.name]
            summary_list = []
            for rule_name in sorted(list(all_applicable_rule_names)):
                rule_errors = [e for e in sheet_errors if e["error_type"] == rule_name]
                error_count = len(rule_errors)
                summary_list.append({
                    "rule_name": rule_name, "error_count": error_count,
                    "error_percentage": round((error_count / sheet_total_rows) * 100, 2) if sheet_total_rows > 0 else 0,
                    "detailed_errors": rule_errors
                })
            summary_list.sort(key=lambda x: x['error_count'], reverse=True)
            sheet_error_row_keys = {e['row'] for e in sheet_errors}
            sheet_summaries.append({
                "sheet_name": sheet_schema.name, "total_rows": sheet_total_rows,
                "sheet_error_rows_count": len(sheet_error_row_keys),
                "sheet_error_percentage": round((len(sheet_error_row_keys) / sheet_total_rows) * 100, 2) if sheet_total_rows > 0 else 0,
                "rule_summaries": summary_list
            })
        if sheet_summaries:
            file_results.append({"file_name": file_schema.name, "sheets": sheet_summaries})

    response_data = {
        "total_processed_rows": total_operations,
        "required_field_error_rows_count": len(unique_error_row_keys),
        "required_field_errors": required_field_errors,
        "file_results": file_results,
        "validated_at": datetime.datetime.utcnow().isoformat()
    }
    results_path = PROJECTS_DIR / project_id / "validation_result.json"
    try:
        results_path.write_text(json.dumps(response_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except IOError as e:
        pass # logger.error(...)

    VALIDATION_STATUS[project_id].update({
        "is_running": False, "percentage": 100.0,
        "processed_rows": total_operations, "message": "Проверка завершена."
    })


@app.post("/api/projects/{project_id}/validate")
async def validate_project_data(project_id: str):
    """
    Запускает валидацию и сразу возвращает ID задачи или начальное состояние.
    """
    project = read_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # --- НАЧАЛО ИЗМЕНЕНИЙ ---
    # Явно инициализируем статус ПЕРЕД запуском фоновой задачи
    initial_status = {
        "is_running": True,
        "current_file": "",
        "current_sheet": "",
        "current_field": "",
        "current_rule": "",
        "processed_rows": 0,
        "total_rows": 0,
        "percentage": 0.0,
        "message": "Запуск проверки..."
    }

    # Присваиваем статус напрямую, чтобы он был доступен немедленно
    VALIDATION_STATUS[project_id] = initial_status

    # Запускаем проверку в фоновом режиме
    asyncio.create_task(_run_validation_async(project_id))

    # Возвращаем начальный статус клиенту
    return {"status": "started", "project_id": project_id, "initial_status": initial_status}


@app.get("/api/projects/{project_id}/validation-status", response_model=ValidationStatus)
async def get_validation_status(project_id: str):
    """Возвращает текущее состояние проверки."""
    status = VALIDATION_STATUS.get(project_id, {
        "is_running": False, "message": "Проверка не запущена."
    })
    return status

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
    return sorted([word for word in words if word and not word.startswith('#')])

class AddWordRequest(BaseModel):
    word: str

@app.post("/api/dictionary", status_code=201)
async def add_word_to_dictionary(request: AddWordRequest, current_words: List[str] = Depends(get_dictionary)):
    new_word = request.word.strip().lower()
    if not new_word:
        raise HTTPException(status_code=400, detail="Word cannot be empty.")
    if new_word in set(current_words):
        raise HTTPException(status_code=400, detail="Word already exists in the dictionary.")
    with CUSTOM_DICT_PATH.open("a", encoding="utf-8") as f:
        f.write(f"\n{new_word}")
    if "spell_check" in RULE_REGISTRY:
        RULE_REGISTRY["spell_check"]["module"].reload_custom_dictionary()
    return {"message": "Word added successfully."}

class EditWordRequest(BaseModel):
    new_word: str

@app.put("/api/dictionary/{old_word}", status_code=200)
async def edit_word_in_dictionary(old_word: str, request: EditWordRequest):
    old_word_clean = old_word.strip()
    new_word_clean = request.new_word.strip()
    if not old_word_clean or not new_word_clean:
        raise HTTPException(status_code=400, detail="Words cannot be empty.")

    # Read the raw lines to preserve comments and original casing
    if not CUSTOM_DICT_PATH.exists():
        raise HTTPException(status_code=404, detail="Dictionary file not found.")

    raw_lines = CUSTOM_DICT_PATH.read_text(encoding="utf-8").split("\n")

    # Find the word to edit using case-insensitive comparison
    word_to_edit_found = any(line.strip().lower() == old_word_clean.lower() for line in raw_lines)
    if not word_to_edit_found:
        raise HTTPException(status_code=404, detail="Word to edit not found in the dictionary.")

    # Check for conflicts with the new word (case-insensitive)
    existing_words_lower = {line.strip().lower() for line in raw_lines if line.strip() and not line.strip().startswith('#')}
    if new_word_clean.lower() in existing_words_lower and new_word_clean.lower() != old_word_clean.lower():
        raise HTTPException(status_code=400, detail="New word already exists in the dictionary.")

    # Rebuild the list, replacing the old word with the new one, preserving original case for others
    updated_lines = []
    for line in raw_lines:
        if line.strip().lower() == old_word_clean.lower():
            updated_lines.append(new_word_clean)
        else:
            updated_lines.append(line)

    CUSTOM_DICT_PATH.write_text("\n".join(updated_lines), encoding="utf-8")

    if "spell_check" in RULE_REGISTRY:
        RULE_REGISTRY["spell_check"]["module"].reload_custom_dictionary()

    return {"message": "Word updated successfully."}

@app.delete("/api/dictionary/{word}", status_code=200)
async def remove_word_from_dictionary(word: str, current_words: List[str] = Depends(get_dictionary)):
    word_to_delete = word.strip().lower()
    if not word_to_delete:
        raise HTTPException(status_code=400, detail="Word cannot be empty.")
    if word_to_delete not in current_words:
        raise HTTPException(status_code=404, detail="Word not found in the dictionary.")
    updated_words = [w for w in current_words if w.lower() != word_to_delete]
    CUSTOM_DICT_PATH.write_text("\n".join(updated_words), encoding="utf-8")
    if "spell_check" in RULE_REGISTRY:
        RULE_REGISTRY["spell_check"]["module"].reload_custom_dictionary()
    return {"message": "Word removed successfully."}

# --- Rule Groups ---
@app.get("/api/rule-groups", response_model=List[RuleGroup])
async def get_rule_groups():
    return list(RULE_GROUPS_REGISTRY.values())

@app.post("/api/rule-groups", response_model=RuleGroup, status_code=201)
async def create_rule_group(group: RuleGroup):
    if group.id in RULE_GROUPS_REGISTRY:
        raise HTTPException(status_code=409, detail="Rule group with this ID already exists.")
    RULE_GROUPS_REGISTRY[group.id] = group
    write_rule_groups()
    return group

@app.put("/api/rule-groups/{group_id}", response_model=RuleGroup)
async def update_rule_group(group_id: str, group_update: RuleGroup):
    if group_id not in RULE_GROUPS_REGISTRY:
        raise HTTPException(status_code=404, detail="Rule group not found.")
    group_update.id = group_id # Ensure ID is not changed
    RULE_GROUPS_REGISTRY[group_id] = group_update
    write_rule_groups()
    return group_update

@app.delete("/api/rule-groups/{group_id}", status_code=204)
async def delete_rule_group(group_id: str):
    if group_id not in RULE_GROUPS_REGISTRY:
        raise HTTPException(status_code=404, detail="Rule group not found.")
    del RULE_GROUPS_REGISTRY[group_id]
    write_rule_groups()
    return

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
            "params_schema": data.get("params_schema")
        })
    return rules_list

# ==============================================================================
# 5. Static Files & HTML Routes
# ==============================================================================

@app.get("/")
async def read_root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/projects/{project_id}")
async def read_project_page(project_id: str):
    # Упрощаем маршрут: он всегда должен возвращать HTML-файл.
    # Фронтенд сам обработает ошибку, если API вернет 404 при запросе данных.
    # Это решает проблему с состоянием гонки, когда Playwright запрашивает
    # страницу до того, как директория проекта физически создана.
    project_html_path = STATIC_DIR / "project.html"
    if not project_html_path.exists():
         raise HTTPException(status_code=500, detail="Файл project.html не найден на сервере.")
    return FileResponse(project_html_path)

@app.get("/rules")
async def read_rules_page():
    return FileResponse(STATIC_DIR / "rules.html")

@app.get("/dictionary")
async def read_dictionary_page():
    return FileResponse(STATIC_DIR / "dictionary.html")

@app.get("/rule-groups")
async def read_rule_groups_page():
    return FileResponse(STATIC_DIR / "rule_groups.html")

# ==============================================================================
# 6. Startup Logic
# ==============================================================================
@app.on_event("startup")
async def startup_event():
    STATIC_DIR.mkdir(exist_ok=True)
    RULES_DIR.mkdir(exist_ok=True)
    PROJECTS_DIR.mkdir(exist_ok=True)
    load_rules()
    read_rule_groups()

# Mount static files at the end to avoid conflicts with specific routes
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
