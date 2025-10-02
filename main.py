import os
import importlib.util
from pathlib import Path
import uuid
from typing import Dict, List
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import io

# --- Globals & Setup ---

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RULES_DIR = BASE_DIR / "rules"
UPLOADS_DIR = BASE_DIR / "uploads"
RULE_REGISTRY = {}

# --- Ensure core directories exist ---
STATIC_DIR.mkdir(exist_ok=True)
RULES_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

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

# --- Pydantic Models ---

class ValidationRequest(BaseModel):
    fileId: str
    rules: Dict[str, List[str]] # e.g., {"ColumnName": ["rule_id_1", "rule_id_2"]}

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