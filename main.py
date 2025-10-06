import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# --- Globals & App Initialization ---
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# --- API Endpoint ---
@app.post("/api/create-test-folder")
async def create_test_folder():
    try:
        print("--- SERVER: Запрос на /api/create-test-folder получен. ---")
        test_dir_path = BASE_DIR / "TEST"
        print(f"--- SERVER: Создаю директорию: {test_dir_path} ---")

        test_dir_path.mkdir(exist_ok=True)

        if test_dir_path.is_dir():
            print("--- SERVER: Директория TEST успешно создана. ---")
            return {"message": "Папка TEST успешно создана!"}
        else:
            print("--- SERVER: ОШИБКА: Не удалось создать директорию. ---")
            raise HTTPException(status_code=500, detail="Не удалось создать директорию на сервере.")

    except Exception as e:
        print(f"--- SERVER: КРИТИЧЕСКАЯ ОШИБКА: {e} ---")
        raise HTTPException(status_code=500, detail=str(e))

# --- HTML Serving ---
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_root():
    return FileResponse(STATIC_DIR / "index.html")

# --- Startup Logic ---
@app.on_event("startup")
async def startup_event():
    STATIC_DIR.mkdir(exist_ok=True)
    print("--- SERVER: Приложение запущено. Статическая директория готова. ---")