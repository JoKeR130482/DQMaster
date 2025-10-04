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
TEMPLATES_FILE = BASE_DIR / "templates.json"
RULE_REGISTRY = {}

# --- Ensure core directories exist ---
STATIC_DIR.mkdir(exist_ok=True)
RULES_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
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
    if not TEMPLATES_FILE.exists():
        return []
    return [Template(**t) for t in json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))]

def write_templates(templates: List[Template]):
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump([t.dict() for t in templates], f, indent=2, ensure_ascii=False)


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

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    """
    Saves the uploaded Excel file and returns a file ID and a list of sheet names.
    """
    UPLOADS_DIR.mkdir(exist_ok=True)
    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file.")

    try:
        contents = await file.read()

        file_id = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOADS_DIR / file_id

        with open(file_path, "wb") as f:
            f.write(contents)

        # Use ExcelFile to get sheet names without loading the whole file
        xls = pd.ExcelFile(io.BytesIO(contents))
        sheet_names = xls.sheet_names

        return {"fileId": file_id, "sheets": sheet_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@app.post("/api/select-sheet")
async def select_sheet(request: SheetSelectRequest):
    """
    Reads a specific sheet from a saved Excel file and returns its columns.
    """
    file_path = UPLOADS_DIR / request.fileId
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        df = pd.read_excel(file_path, sheet_name=request.sheetName)
        columns = df.columns.tolist()
        return {"columns": columns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read sheet: {str(e)}")

@app.post("/api/validate")
async def validate_data(request: ValidationRequest):
    """
    Validates a specific sheet, supporting required fields and returning row-based error stats.
    """
    UPLOADS_DIR.mkdir(exist_ok=True)
    file_path = UPLOADS_DIR / request.fileId
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        df = pd.read_excel(file_path, sheet_name=request.sheetName)
        errors = []
        total_rows = len(df)

        for col_name, col_config in request.rules.items():
            if col_name not in df.columns:
                continue

            for index, value in df[col_name].items():
                # Check for required field violation first
                if col_config.is_required and (pd.isna(value) or (isinstance(value, str) and not value.strip())):
                    errors.append({
                        "row": index + 2, "column": col_name, "value": "ПУСТО",
                        "rule_name": "Обязательное поле",
                        "error": "Поле не должно быть пустым"
                    })
                    # We still check other rules for this row, as it might have other errors.

                # Apply other rules regardless of the required check
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

        # Calculate unique rows with errors
        error_rows_set = {e["row"] for e in errors}

        return {
            "total_rows": total_rows,
            "error_rows_count": len(error_rows_set),
            "errors": errors
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

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
