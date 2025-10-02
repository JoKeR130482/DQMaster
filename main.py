import os
import importlib.util
from pathlib import Path
import uuid
from typing import Dict, List
from pydantic import BaseModel, Field
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
                    if hasattr(module, "validate") and hasattr(module, "RULE_NAME") and hasattr(module, "RULE_DESC"):
                        RULE_REGISTRY[rule_id] = {
                            "id": rule_id,
                            "name": module.RULE_NAME,
                            "description": module.RULE_DESC,
                            "validator": module.validate
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

# --- Pydantic Models ---

class ValidationRequest(BaseModel):
    fileId: str
    rules: Dict[str, List[str]]

class Template(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    columns: List[str]
    rules: Dict[str, List[str]]

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
    serializable_rules = {
        rule_id: {"id": data["id"], "name": data["name"], "description": data["description"]}
        for rule_id, data in RULE_REGISTRY.items()
    }
    return JSONResponse(content=list(serializable_rules.values()))

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    """
    Saves the uploaded Excel file to a temporary location and returns a unique
    file ID along with the column headers.
    """
    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an Excel file.")

    try:
        contents = await file.read()

        # Generate a unique ID for the file
        file_id = f"{uuid.uuid4()}_{file.filename}"
        file_path = UPLOADS_DIR / file_id

        with open(file_path, "wb") as f:
            f.write(contents)

        # Read columns without keeping the whole file in memory
        df = pd.read_excel(io.BytesIO(contents))
        columns = df.columns.tolist()

        return {"fileId": file_id, "columns": columns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@app.post("/api/validate")
async def validate_data(request: ValidationRequest):
    """
    Validates the cached data file against the provided rules.
    """
    file_path = UPLOADS_DIR / request.fileId
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found. It may have expired or never existed.")

    try:
        df = pd.read_excel(file_path)
        errors = []

        for col_name, rule_ids in request.rules.items():
            if col_name not in df.columns:
                continue # Skip if column from request is not in the file

            for rule_id in rule_ids:
                rule = RULE_REGISTRY.get(rule_id)
                if not rule:
                    continue # Skip if rule_id is invalid

                validator = rule["validator"]
                for index, value in df[col_name].items():
                    # Skip validation for empty cells
                    if pd.isna(value):
                        continue

                    if not validator(value):
                        errors.append({
                            "row": index + 2, # Adding 2 for 1-based indexing + header
                            "column": col_name,
                            "value": str(value),
                            "rule_name": rule["name"],
                            "error": f"Value '{value}' failed validation for rule '{rule['name']}'"
                        })
        return {"errors": errors}
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