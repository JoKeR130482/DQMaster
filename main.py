from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
import io
from pathlib import Path

app = FastAPI()

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Mount the 'static' directory to serve static files using an absolute path
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Read the Excel file in memory
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))

        # Get column names
        columns = df.columns.tolist()

        return {"columns": columns}
    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}