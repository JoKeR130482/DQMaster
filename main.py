from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# --- Globals & App Initialization ---
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PROJECTS_DIR = BASE_DIR / "projects" # We'll create this, but not use it yet

# --- API Endpoint ---
@app.post("/api/create-test-folder")
async def create_test_folder():
    """
    This is the simplest possible endpoint. It only creates one folder.
    """
    try:
        test_dir_path = BASE_DIR / "TEST"
        test_dir_path.mkdir(exist_ok=True)

        if test_dir_path.is_dir():
            return {"message": "Папка TEST успешно создана!"}
        else:
            raise HTTPException(status_code=500, detail="Не удалось создать директорию на сервере.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- HTML Serving ---
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_root():
    # Serve the index.html from the static directory
    return FileResponse(STATIC_DIR / "index.html")

# --- Startup Logic ---
@app.on_event("startup")
async def startup_event():
    # Ensure the static and projects directories exist when the app starts
    STATIC_DIR.mkdir(exist_ok=True)
    PROJECTS_DIR.mkdir(exist_ok=True)
    print("--- Server is running with a minimal 'Clean Slate' main.py ---")