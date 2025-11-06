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
import logging
import logging.handlers
import time
import sqlite3
import database

from fastapi import Depends, FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

# ==============================================================================
# 0. Logging Configuration
# ==============================================================================
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Форматтер для логов
log_formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)d] - %(message)s"
)

# --- Логгер для приложения (уровень INFO) ---
app_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "app.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
)
app_handler.setLevel(logging.INFO)
app_handler.setFormatter(log_formatter)

# --- Логгер для отладки (уровень DEBUG) ---
debug_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "debug.log", maxBytes=10*1024*1024, backupCount=3, encoding="utf-8"
)
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(log_formatter)

# --- Консольный логгер ---
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# --- Настройка корневого логгера ---
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)  # Устанавливаем самый низкий уровень для корневого логгера
root_logger.addHandler(app_handler)
root_logger.addHandler(debug_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. Globals & App Initialization
# ==============================================================================
app = FastAPI()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000
    logger.info(
        f"'{request.method} {request.url.path}' {response.status_code} "
        f"processed in {duration:.2f} ms"
    )
    return response


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

class SheetStatus(BaseModel):
    sheet_name: str
    expected_rows: int
    actual_rows: int
    is_consistent: bool

class DataStatus(BaseModel):
    project_id: str
    overall_status: str # "CONSISTENT", "INCONSISTENT", "NO_DATA"
    checked_at: str
    details: List[SheetStatus]

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
    """Возвращает список всех проектов из основной базы данных."""
    logger.debug("Запрос на получение списка всех проектов.")
    projects = []
    try:
        with database.get_main_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, description, updated_at FROM projects ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            for row in rows:
                project_dir = PROJECTS_DIR / row["id"]
                total_size = 0
                if project_dir.is_dir():
                    total_size = sum(f.stat().st_size for f in project_dir.glob('**/*') if f.is_file())

                projects.append(ProjectInfo(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    updated_at=row["updated_at"].isoformat(),
                    size_kb=round(total_size / 1024, 2)
                ))
        logger.debug(f"Найдено {len(projects)} проектов.")
        return projects
    except sqlite3.Error as e:
        logger.error(f"Не удалось получить список проектов из main.db: {e}")
        raise HTTPException(status_code=500, detail="Не удалось получить список проектов.")

@app.post("/api/projects", status_code=201, response_model=ProjectInfo)
async def create_project(project_data: ProjectCreateRequest):
    """Создает новый проект, инициализирует его БД и регистрирует в основной БД."""
    project_id = str(uuid.uuid4())
    logger.info(f"Запрос на создание нового проекта '{project_data.name}' с ID: {project_id}")

    # 1. Создание БД проекта
    if not database.create_project_db(project_id):
        logger.error(f"[PROJECT_ID: {project_id}] Не удалось создать базу данных проекта.")
        raise HTTPException(status_code=500, detail="Не удалось создать базу данных проекта.")

    # 2. Регистрация проекта в основной БД
    db_path = PROJECTS_DIR / project_id / f"project_{project_id}.db"
    now = datetime.datetime.utcnow()
    try:
        with database.get_main_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO projects (id, name, description, created_at, updated_at, db_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project_id, project_data.name, project_data.description, now, now, str(db_path))
            )
            conn.commit()
            logger.info(f"[PROJECT_ID: {project_id}] Проект успешно зарегистрирован в main.db.")
    except sqlite3.Error as e:
        logger.error(f"[PROJECT_ID: {project_id}] Ошибка при регистрации проекта в main.db: {e}")
        # Попытка очистки - удаляем созданную директорию проекта
        shutil.rmtree(PROJECTS_DIR / project_id, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Ошибка при регистрации проекта.")

    # 3. Возвращаем информацию о созданном проекте
    return ProjectInfo(
        id=project_id,
        name=project_data.name,
        description=project_data.description,
        updated_at=now.isoformat(),
        size_kb=0.0
    )

def _build_project_model_from_db(project_id: str) -> Optional[Project]:
    """
    Собирает полную Pydantic модель проекта из его базы данных.
    Это сложная операция, включающая множество SQL-запросов.
    """
    logger.debug(f"[PROJECT_ID: {project_id}] Сборка модели проекта из БД.")
    project_info = None

    # 1. Получаем базовую информацию о проекте из main.db
    try:
        with database.get_main_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            project_info = cursor.fetchone()
    except sqlite3.Error as e:
        logger.error(f"[PROJECT_ID: {project_id}] Не удалось получить метаданные проекта из main.db: {e}")
        return None

    if not project_info:
        return None

    project_files = []
    # 2. Получаем структуру (файлы, листы, поля, правила) из БД проекта
    try:
        with database.get_project_db_connection(project_id) as conn:
            cursor = conn.cursor()

            # Получаем все файлы
            cursor.execute("SELECT * FROM files ORDER BY upload_time")
            files_rows = cursor.fetchall()
            if not files_rows:
                 # Если файлов нет, возвращаем проект с пустым списком файлов
                 return Project(
                    id=project_info["id"], name=project_info["name"], description=project_info["description"],
                    created_at=project_info["created_at"].isoformat(), updated_at=project_info["updated_at"].isoformat(),
                    files=[]
                )

            for file_row in files_rows:
                # Получаем листы для каждого файла
                cursor.execute("SELECT * FROM sheets WHERE file_id = ? ORDER BY name", (file_row["id"],))
                sheets_rows = cursor.fetchall()
                file_sheets = []

                for sheet_row in sheets_rows:
                    # Получаем поля для каждого листа
                    cursor.execute("SELECT * FROM fields WHERE sheet_id = ? ORDER BY name", (sheet_row["id"],))
                    fields_rows = cursor.fetchall()
                    sheet_fields = []

                    for field_row in fields_rows:
                        # Получаем правила для каждого поля
                        cursor.execute("SELECT * FROM rules WHERE field_id = ? ORDER BY order_num", (field_row["id"],))
                        rules_rows = cursor.fetchall()
                        field_rules = [
                            Rule(
                                id=r["id"],
                                type=r["rule_type"],
                                group_id=r["group_id"],
                                params=json.loads(r["params"]) if r["params"] else None,
                                order=r["order_num"]
                            ) for r in rules_rows
                        ]
                        sheet_fields.append(
                            FieldSchema(id=field_row["id"], name=field_row["name"], is_required=bool(field_row["is_required"]), rules=field_rules)
                        )
                    file_sheets.append(
                        SheetSchema(id=sheet_row["id"], name=sheet_row["name"], is_active=bool(sheet_row["is_active"]), fields=sheet_fields)
                    )
                project_files.append(
                    FileSchema(id=file_row["id"], name=file_row["original_name"], saved_name=file_row["saved_name"], sheets=file_sheets)
                )

        # 3. Собираем итоговую модель
        project_model = Project(
            id=project_info["id"],
            name=project_info["name"],
            description=project_info["description"],
            created_at=project_info["created_at"].isoformat(),
            updated_at=project_info["updated_at"].isoformat(),
            files=project_files
        )
        logger.debug(f"[PROJECT_ID: {project_id}] Модель проекта успешно собрана.")
        return project_model

    except sqlite3.Error as e:
        logger.error(f"[PROJECT_ID: {project_id}] Ошибка при чтении структуры проекта из его БД: {e}", exc_info=True)
        return None
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"[PROJECT_ID: {project_id}] Ошибка валидации Pydantic или парсинга JSON при сборке модели: {e}", exc_info=True)
        return None


@app.get("/api/projects/{project_id}", response_model=Project)
async def get_project_details(project_id: str):
    """Собирает и возвращает полную структуру проекта из его базы данных."""
    project = await asyncio.to_thread(_build_project_model_from_db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден или поврежден.")
    return project

def _update_project_in_db(project_id: str, project_update: FullProjectUpdateRequest) -> Project:
    """Синхронная функция для атомарного обновления всей структуры проекта в БД с использованием UPSERT."""
    logger.info(f"[PROJECT_ID: {project_id}] Начало полного обновления проекта в БД.")
    start_time = time.time()

    # 1. Обновляем метаданные в main.db
    now = datetime.datetime.utcnow()
    try:
        with database.get_main_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET name = ?, description = ?, updated_at = ? WHERE id = ?",
                (project_update.name, project_update.description, now, project_id)
            )
            conn.commit()
            if cursor.rowcount == 0:
                 raise HTTPException(status_code=404, detail="Проект не найден в основной БД.")
    except sqlite3.Error as e:
        logger.error(f"[{project_id}] Ошибка при обновлении метаданных в main.db: {e}")
        raise HTTPException(status_code=500, detail="Ошибка БД при обновлении проекта.")

    # 2. Атомарно обновляем (UPSERT) всю структуру в БД проекта
    conn = None # Объявляем conn здесь для доступа в блоке except
    try:
        conn = database.get_project_db_connection(project_id)
        cursor = conn.cursor()
        cursor.execute("BEGIN;")
        logger.debug(f"[{project_id}] Транзакция для обновления структуры проекта начата.")

        # Проходим по новой структуре и обновляем/вставляем данные
        for file_schema in project_update.files:
            for sheet_schema in file_schema.sheets:
                logger.debug(f"[{project_id}] Обработка листа: {sheet_schema.name} (ID: {sheet_schema.id})")
                cursor.execute(
                    """
                    INSERT INTO sheets (id, file_id, name, is_active) VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        file_id = excluded.file_id,
                        name = excluded.name,
                        is_active = excluded.is_active
                    """,
                    (sheet_schema.id, file_schema.id, sheet_schema.name, sheet_schema.is_active)
                )
                for field_schema in sheet_schema.fields:
                    logger.debug(f"[{project_id}] Обработка поля: {field_schema.name} (ID: {field_schema.id}) для листа {sheet_schema.id}")
                    cursor.execute(
                        """
                        INSERT INTO fields (id, sheet_id, name, is_required) VALUES (?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            sheet_id = excluded.sheet_id,
                            name = excluded.name,
                            is_required = excluded.is_required
                        """,
                        (field_schema.id, sheet_schema.id, field_schema.name, field_schema.is_required)
                    )
                    for rule in field_schema.rules:
                        logger.debug(f"[{project_id}] Обработка правила (ID: {rule.id}) для поля {field_schema.id}")
                        cursor.execute(
                            """
                            INSERT INTO rules (id, field_id, rule_type, group_id, params, order_num)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(id) DO UPDATE SET
                                field_id = excluded.field_id,
                                rule_type = excluded.rule_type,
                                group_id = excluded.group_id,
                                params = excluded.params,
                                order_num = excluded.order_num
                            """,
                            (
                                rule.id, field_schema.id, rule.type, rule.group_id,
                                json.dumps(rule.params, ensure_ascii=False) if rule.params else None,
                                rule.order
                            )
                        )

        conn.commit()
        logger.info(f"[{project_id}] Транзакция для обновления структуры проекта успешно завершена.")

    except sqlite3.Error as e:
        logger.error(f"[{project_id}] Ошибка БД при обновлении структуры проекта: {e}", exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении структуры проекта: {str(e)}")
    finally:
        if conn:
            conn.close()

    duration = (time.time() - start_time) * 1000
    logger.info(f"[PROJECT_ID: {project_id}] Полное обновление проекта завершено за {duration:.2f} мс.")

    project_update.updated_at = now.isoformat()
    return project_update

@app.put("/api/projects/{project_id}", response_model=Project)
async def update_full_project(project_id: str, project_update: FullProjectUpdateRequest):
    """Атомарно обновляет всю структуру проекта (листы, поля, правила) в базе данных."""
    # Убеждаемся, что ID в пути и в теле запроса совпадают
    if project_id != project_update.id:
        raise HTTPException(status_code=400, detail="ID проекта в URL и теле запроса не совпадают.")

    updated_project = await asyncio.to_thread(_update_project_in_db, project_id, project_update)
    return updated_project

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
    """Удаляет проект: его директорию и запись в основной БД."""
    logger.info(f"[PROJECT_ID: {project_id}] Запрос на удаление проекта.")
    project_dir = PROJECTS_DIR / project_id

    # 1. Удаляем запись из main.db
    try:
        with database.get_main_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            if cursor.rowcount == 0:
                logger.warning(f"[PROJECT_ID: {project_id}] Проект не найден в main.db, но папка может существовать.")
                # Не бросаем ошибку, чтобы можно было почистить "осиротевшие" папки
            else:
                logger.info(f"[PROJECT_ID: {project_id}] Запись о проекте успешно удалена из main.db.")
    except sqlite3.Error as e:
        logger.error(f"[PROJECT_ID: {project_id}] Ошибка при удалении проекта из main.db: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных при удалении проекта.")

    # 2. Удаляем директорию проекта
    if project_dir.is_dir():
        try:
            shutil.rmtree(project_dir)
            logger.info(f"[PROJECT_ID: {project_id}] Директория проекта успешно удалена.")
        except OSError as e:
            logger.error(f"[PROJECT_ID: {project_id}] Не удалось удалить директорию проекта: {e}")
            # Возвращаем ошибку, так как проект частично удален, что является проблемой
            raise HTTPException(status_code=500, detail="Не удалось удалить файлы проекта.")
    else:
        logger.warning(f"[PROJECT_ID: {project_id}] Директория проекта не найдена.")

    return

# --- Project File & Validation Operations ---

def _import_excel_to_db(project_id: str, file_id: str, original_filename: str, saved_filename: str, contents: bytes):
    """
    Синхронная функция для выполнения тяжелой работы по импорту Excel в БД.
    Запускается в отдельном потоке через asyncio.to_thread.
    """
    project_dir = PROJECTS_DIR / project_id
    logger.info(f"[PROJECT_ID: {project_id}] Начало импорта файла '{original_filename}'.")
    start_time = time.time()

    try:
        xls = pd.ExcelFile(io.BytesIO(contents))
        sheet_schemas = []
        field_schemas = {} # {sheet_id: [FieldSchema, ...]}

        with database.get_project_db_connection(project_id) as conn:
            cursor = conn.cursor()
            # Начинаем транзакцию
            cursor.execute("BEGIN;")
            logger.debug(f"[PROJECT_ID: {project_id}] Транзакция для импорта начата.")

            # 1. Записываем метаданные файла
            cursor.execute(
                "INSERT INTO files (id, original_name, saved_name, upload_time) VALUES (?, ?, ?, ?)",
                (file_id, original_filename, saved_filename, datetime.datetime.utcnow())
            )

            for sheet_name in xls.sheet_names:
                sheet_id = str(uuid.uuid4())
                logger.debug(f"[PROJECT_ID: {project_id}] Обработка листа: '{sheet_name}' (ID: {sheet_id})")

                # 2. Записываем метаданные листа
                cursor.execute(
                    "INSERT INTO sheets (id, file_id, name, is_active) VALUES (?, ?, ?, ?)",
                    (sheet_id, file_id, sheet_name, True)
                )
                sheet_schemas.append(SheetSchema(id=sheet_id, name=sheet_name, is_active=True, fields=[]))
                field_schemas[sheet_id] = []

                # 3. Читаем данные листа и создаем таблицу для них
                df = pd.read_excel(xls, sheet_name=sheet_name)
                # Приводим все типы колонок к строке, чтобы избежать проблем с типами данных в SQLite
                for col in df.columns:
                    df[col] = df[col].astype(str)

                table_name = f"data_sheet_{database.normalize_name_for_sqlite(sheet_name)}_{sheet_id[:8]}"

                # Обновляем запись листа, добавляя имя таблицы с данными и количество строк
                cursor.execute(
                    "UPDATE sheets SET data_table_name = ?, row_count = ? WHERE id = ?",
                    (table_name, len(df), sheet_id)
                )

                normalized_columns = {col: database.normalize_name_for_sqlite(col) for col in df.columns}
                df.rename(columns=normalized_columns, inplace=True)

                # Создаем CREATE TABLE statement
                cols_with_types = ", ".join(f'"{col_name}" TEXT' for col_name in df.columns)
                create_table_sql = f'CREATE TABLE "{table_name}" (_row_id INTEGER PRIMARY KEY AUTOINCREMENT, {cols_with_types});'
                logger.debug(f"[PROJECT_ID: {project_id}] SQL для создания таблицы данных: {create_table_sql}")
                cursor.execute(create_table_sql)

                # 4. Записываем метаданные полей (колонок)
                for original_col_name in normalized_columns.keys():
                    field_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO fields (id, sheet_id, name, is_required) VALUES (?, ?, ?, ?)",
                        (field_id, sheet_id, original_col_name, False)
                    )
                    field_schemas[sheet_id].append(FieldSchema(id=field_id, name=original_col_name, is_required=False, rules=[]))


                # 5. Вставляем данные в новую таблицу (batch insert)
                if not df.empty:
                    logger.debug(f"[PROJECT_ID: {project_id}] Вставка {len(df)} строк в таблицу '{table_name}'.")
                    df.to_sql(name=table_name, con=conn, if_exists='append', index=False)
                else:
                    logger.warning(f"[PROJECT_ID: {project_id}] Лист '{sheet_name}' пуст, данные не импортированы.")

                # Обновляем структуру Pydantic моделей
                sheet_to_update = next(s for s in sheet_schemas if s.id == sheet_id)
                sheet_to_update.fields = field_schemas[sheet_id]


            # Завершаем транзакцию
            conn.commit()
            logger.info(f"[PROJECT_ID: {project_id}] Транзакция для импорта успешно завершена.")

    except Exception as e:
        logger.error(f"[PROJECT_ID: {project_id}] КРИТИЧЕСКАЯ ОШИБКА во время импорта Excel: {e}", exc_info=True)
        # Откатываем транзакцию в случае ошибки
        if 'conn' in locals() and conn:
            conn.rollback()
            logger.warning(f"[PROJECT_ID: {project_id}] Транзакция отменена из-за ошибки.")
        raise  # Передаем исключение дальше, чтобы API вернул ошибку 500

    finally:
        duration = time.time() - start_time
        logger.info(f"[PROJECT_ID: {project_id}] Импорт файла '{original_filename}' завершен за {duration:.2f} сек.")

    # Создаем итоговую Pydantic модель файла
    final_file_schema = FileSchema(
        id=file_id,
        name=original_filename,
        saved_name=saved_filename,
        sheets=sheet_schemas
    )
    return final_file_schema


@app.post("/api/projects/{project_id}/upload", response_model=FileSchema)
async def upload_file_to_project(project_id: str, file: UploadFile = File(...)):
    """
    Загружает файл Excel, сохраняет его в архив, импортирует данные в БД проекта
    и возвращает структуру нового файла.
    """
    # Проверка существования проекта
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Проект не найден.")

    if not file.filename or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Неверный тип файла. Требуется .xlsx или .xls.")

    logger.info(f"[PROJECT_ID: {project_id}] Получен запрос на загрузку файла: {file.filename}")

    contents = await file.read()
    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}{Path(file.filename).suffix}"

    # 1. Сохраняем исходный файл в архив
    archive_dir = project_dir / "archive"
    archive_dir.mkdir(exist_ok=True)
    archive_path = archive_dir / saved_filename
    try:
        with open(archive_path, "wb") as f:
            f.write(contents)
        logger.debug(f"[PROJECT_ID: {project_id}] Файл сохранен в архив: {archive_path}")
    except IOError as e:
        logger.error(f"[PROJECT_ID: {project_id}] Не удалось сохранить файл в архив: {e}")
        raise HTTPException(status_code=500, detail="Не удалось сохранить файл на сервере.")

    # 2. Запускаем импорт в БД в отдельном потоке, чтобы не блокировать event loop
    try:
        file_schema = await asyncio.to_thread(
            _import_excel_to_db,
            project_id,
            file_id,
            file.filename,
            saved_filename,
            contents
        )
    except Exception as e:
        # Если в _import_excel_to_db произошла ошибка, она будет здесь перехвачена
        raise HTTPException(status_code=500, detail=f"Ошибка при импорте данных из Excel: {e}")

    # 3. Обновляем `updated_at` в основной БД
    try:
        with database.get_main_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET updated_at = ? WHERE id = ?",
                (datetime.datetime.utcnow(), project_id)
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.warning(f"[PROJECT_ID: {project_id}] Не удалось обновить 'updated_at' для проекта: {e}")
        # Это не критичная ошибка, поэтому просто логируем ее

    return file_schema

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


async def _run_validation_async(project_id: str):
    """
    Асинхронная функция для выполнения валидации, читающая данные ИСКЛЮЧИТЕЛЬНО из БД.
    Поддерживает два типа правил: построчные и требующие доступ ко всему столбцу.
    """
    logger.info(f"[{project_id}] Запуск процесса валидации.")

    project = await asyncio.to_thread(_build_project_model_from_db, project_id)
    if not project:
        logger.error(f"[{project_id}] Валидация прервана: не удалось собрать модель проекта.")
        VALIDATION_STATUS[project_id].update({"is_running": False, "message": "Ошибка: проект не найден."})
        return

    # --- 1. Расчет общего количества операций ---
    total_operations = 0
    try:
        with database.get_project_db_connection(project_id) as conn:
            cursor = conn.cursor()
            for file_schema in project.files:
                for sheet_schema in file_schema.sheets:
                    if not sheet_schema.is_active: continue
                    cursor.execute("SELECT row_count FROM sheets WHERE id = ?", (sheet_schema.id,))
                    row_count_res = cursor.fetchone()
                    if not row_count_res: continue
                    row_count = row_count_res[0]
                    num_rules = sum(len(field.rules) for field in sheet_schema.fields)
                    total_operations += row_count * num_rules
    except sqlite3.Error as e:
        logger.error(f"[{project_id}] Ошибка при расчете общего числа операций: {e}", exc_info=True)
        VALIDATION_STATUS[project_id].update({"is_running": False, "message": "Ошибка: не удалось рассчитать объем работы."})
        return

    VALIDATION_STATUS[project_id].update({
        "total_rows": total_operations,
        "message": f"Начинаем проверку {len(project.files)} файлов..."
    })

    # --- 2. Выполнение валидации ---
    all_errors = []
    processed_ops_count = 0

    try:
        with database.get_project_db_connection(project_id) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO validation_results DEFAULT VALUES;")
            result_id = cursor.lastrowid
            conn.commit()

            for file_schema in project.files:
                VALIDATION_STATUS[project_id]["current_file"] = file_schema.name
                for sheet_schema in file_schema.sheets:
                    if not sheet_schema.is_active:
                        logger.debug(f"[{project_id}] Лист '{sheet_schema.name}' неактивен, пропуск.")
                        continue

                    try:
                        VALIDATION_STATUS[project_id]["current_sheet"] = sheet_schema.name
                        logger.debug(f"[{project_id}] Начало обработки листа: '{file_schema.name}' -> '{sheet_schema.name}'.")

                        cursor.execute("SELECT data_table_name FROM sheets WHERE id = ?", (sheet_schema.id,))
                        sheet_info = cursor.fetchone()
                        if not sheet_info or not sheet_info["data_table_name"]:
                            logger.warning(f"[{project_id}] Не найдена таблица данных для листа '{sheet_schema.name}' (ID: {sheet_schema.id}). Пропуск.")
                            continue
                        table_name = sheet_info["data_table_name"]

                        for field_schema in sheet_schema.fields:
                            normalized_col_name = database.normalize_name_for_sqlite(field_schema.name)
                            VALIDATION_STATUS[project_id]["current_field"] = field_schema.name

                            cursor.execute(f"PRAGMA table_info('{table_name}')")
                            if normalized_col_name not in [col['name'] for col in cursor.fetchall()]:
                                logger.warning(f"[{project_id}] Колонка '{normalized_col_name}' (оригинал: '{field_schema.name}') не найдена в таблице '{table_name}'. Пропуск поля.")
                                continue

                            # Разделяем правила на построчные и постолбцовые
                            column_rules, row_rules = [], []
                            for rc in sorted(field_schema.rules, key=lambda r: r.order):
                                if rc.type and RULE_REGISTRY.get(rc.type, {}).get('needs_column_access'):
                                    column_rules.append((rc, RULE_REGISTRY[rc.type]))
                                else:
                                    row_rules.append(rc)

                            # --- 2.1 Обработка правил, требующих доступ к столбцу ---
                            if column_rules:
                                logger.debug(f"[{project_id}] Загрузка столбца '{field_schema.name}' для спец. правил.")
                                query = f'SELECT _row_id, "{normalized_col_name}" FROM "{table_name}" ORDER BY _row_id'
                                df = pd.read_sql_query(query, conn, index_col='_row_id')
                                column_series = df[normalized_col_name]

                                for rule_config, rule_def in column_rules:
                                    rule_name = rule_def['name']
                                    VALIDATION_STATUS[project_id]['current_rule'] = rule_name
                                    try:
                                        res = rule_def["validator"](column_series, params=rule_config.params or {})
                                        is_valid_mask, errors_series = res["is_valid"], res.get("errors")
                                        invalid_rows = column_series[~is_valid_mask]
                                        for row_id, value in invalid_rows.items():
                                            all_errors.append({
                                                "file_name": file_schema.name, "sheet_name": sheet_schema.name,
                                                "field_name": field_schema.name, "is_required": field_schema.is_required,
                                                "row": row_id, "error_type": rule_name,
                                                "value": str(value) if pd.notna(value) else "ПУСТО",
                                                "details": errors_series.loc[row_id] if errors_series is not None else None
                                            })
                                    except Exception as e:
                                        logger.error(f"[{project_id}] Ошибка в правиле '{rule_name}' для столбца '{field_schema.name}': {e}", exc_info=True)

                                    processed_ops_count += len(column_series)
                                    VALIDATION_STATUS[project_id].update({
                                        "processed_rows": processed_ops_count,
                                        "percentage": (processed_ops_count / total_operations) * 100 if total_operations > 0 else 0
                                    })

                            # --- 2.2 Обработка обычных (построчных) правил ---
                            if row_rules:
                                query = f'SELECT _row_id, "{normalized_col_name}" FROM "{table_name}" ORDER BY _row_id'
                                data_cursor = conn.cursor()
                                data_cursor.execute(query)

                                while chunk := data_cursor.fetchmany(1000):
                                    for row_id, value in chunk:
                                        for rule_config in row_rules:
                                            rule_name = "Неизвестное правило"
                                            is_valid, details = True, None

                                            try: # Обертываем логику одного правила в try-except
                                                if rule_config.group_id:
                                                    group = RULE_GROUPS_REGISTRY.get(rule_config.group_id)
                                                    if group:
                                                        rule_name = f"Группа: {group.name}"
                                                        result = _validate_group(value, group)
                                                        if not result["is_valid"]:
                                                            is_valid = False
                                                            details = result["errors"]
                                                elif rule_config.type:
                                                    rule_def = RULE_REGISTRY.get(rule_config.type)
                                                    if rule_def:
                                                        formatter = rule_def.get("formatter")
                                                        rule_name = formatter(rule_config.params) if formatter and rule_config.params else rule_def["name"]
                                                        res = rule_def["validator"](value, params=rule_config.params or {})
                                                        is_valid = res if isinstance(res, bool) else res.get("is_valid", False)
                                                        details = None if isinstance(res, bool) else res.get("errors")
                                                else:
                                                    logger.warning(f"[{project_id}] Пропущено некорректное правило: {rule_config.id} (нет type и group_id)")
                                                    continue # Пропускаем это правило

                                                if not is_valid:
                                                    all_errors.append({
                                                        "file_name": file_schema.name, "sheet_name": sheet_schema.name,
                                                        "field_name": field_schema.name, "is_required": field_schema.is_required,
                                                        "row": row_id, "error_type": rule_name,
                                                        "value": str(value) if pd.notna(value) else "ПУСТО", "details": details
                                                    })

                                            except Exception as e:
                                                logger.error(f"[{project_id}] Ошибка при выполнении правила '{rule_name}' (ID: {rule_config.id}) для поля '{field_schema.name}' в строке {row_id}. Значение: '{str(value)[:50]}...'. Ошибка: {e}", exc_info=True)
                                                # Не прерываем валидацию, просто логируем ошибку для конкретного правила

                                            processed_ops_count += 1

                                        VALIDATION_STATUS[project_id].update({
                                            "processed_rows": processed_ops_count,
                                            "current_rule": rule_name,
                                            "percentage": (processed_ops_count / total_operations) * 100 if total_operations > 0 else 0
                                        })

                        logger.debug(f"[{project_id}] Завершение обработки листа: '{sheet_schema.name}'.")

                    except Exception as e:
                        logger.error(f"[{project_id}] Не удалось обработать лист '{sheet_schema.name}' из-за ошибки: {e}", exc_info=True)
                        # Продолжаем со следующим листом, чтобы не прерывать всю валидацию
                        continue

            # --- 3. Сохранение результатов в БД ---
            if all_errors:
                error_tuples = [
                    (result_id, e["file_name"], e["sheet_name"], e["field_name"], e["row"], e["error_type"], e["value"], json.dumps(e["details"], ensure_ascii=False) if e["details"] else None, e["is_required"])
                    for e in all_errors
                ]
                cursor.executemany("INSERT INTO validation_errors (result_id, file_name, sheet_name, field_name, row_number, error_type, value, details, is_required) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", error_tuples)

            required_field_errors = [e for e in all_errors if e["is_required"]]
            unique_error_row_keys = {f"{e['file_name']}-{e['sheet_name']}-{e['row']}" for e in required_field_errors}

            cursor.execute("UPDATE validation_results SET total_rows = ?, error_rows = ? WHERE id = ?", (total_operations, len(unique_error_row_keys), result_id))
            conn.commit()
            logger.info(f"[{project_id}] Результаты валидации (ID: {result_id}) сохранены. Найдено ошибок: {len(all_errors)}.")

    except Exception as e:
        logger.error(f"[{project_id}] Критическая ошибка во время валидации: {e}", exc_info=True)
        VALIDATION_STATUS[project_id].update({"is_running": False, "message": "Критическая ошибка во время проверки."})
        return

    VALIDATION_STATUS[project_id].update({"is_running": False, "message": "Проверка завершена.", "percentage": 100.0})
    logger.info(f"[{project_id}] Валидация успешно завершена.")


@app.post("/api/projects/{project_id}/validate")
async def validate_project_data(project_id: str):
    """Запускает валидацию данных проекта из его БД."""
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Проект не найден.")

    initial_status = {
        "is_running": True, "current_file": "", "current_sheet": "",
        "current_field": "", "current_rule": "", "processed_rows": 0,
        "total_rows": 0, "percentage": 0.0, "message": "Запуск проверки..."
    }
    VALIDATION_STATUS[project_id] = initial_status
    asyncio.create_task(_run_validation_async(project_id))
    return {"status": "started", "project_id": project_id, "initial_status": initial_status}


@app.get("/api/projects/{project_id}/validation-status", response_model=ValidationStatus)
async def get_validation_status(project_id: str):
    """Возвращает текущее состояние проверки."""
    return VALIDATION_STATUS.get(project_id, {"is_running": False, "message": "Проверка не запущена."})


@app.get("/api/projects/{project_id}/results")
async def get_validation_results(project_id: str):
    """
    Возвращает последний результат валидации из БД, форматируя его
    в JSON-структуру, совместимую с фронтендом.
    """
    logger.debug(f"[PROJECT_ID: {project_id}] Запрос на получение последнего результата валидации.")
    try:
        with database.get_project_db_connection(project_id) as conn:
            cursor = conn.cursor()

            # Находим ID последнего результата
            cursor.execute("SELECT id, validated_at, total_rows, error_rows FROM validation_results ORDER BY validated_at DESC LIMIT 1")
            last_result = cursor.fetchone()
            if not last_result:
                raise HTTPException(status_code=404, detail="Результаты валидации для этого проекта не найдены.")

            result_id = last_result["id"]
            logger.debug(f"[{project_id}] Загружены результаты валидации ID: {result_id}")

            # Получаем все ошибки для этого результата
            cursor.execute("SELECT * FROM validation_errors WHERE result_id = ?", (result_id,))
            errors_rows = cursor.fetchall()

            all_errors = [dict(row) for row in errors_rows]

            from collections import Counter
            error_distribution = Counter(e['error_type'] for e in all_errors)
            logger.debug(f"[{project_id}] Количество найденных ошибок: {len(all_errors)}")
            logger.debug(f"[{project_id}] Распределение ошибок по типам: {error_distribution}")

            for e in all_errors: # Десериализуем JSON
                if e.get('details'): e['details'] = json.loads(e['details'])
                e['row'] = e.pop('row_number') # Переименовываем для совместимости

    except sqlite3.Error as e:
        logger.error(f"[PROJECT_ID: {project_id}] Ошибка БД при получении результатов валидации: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка БД при получении результатов.")

    # --- Собираем JSON-ответ, аналогичный старому формату ---
    project = await asyncio.to_thread(_build_project_model_from_db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Не удалось загрузить структуру проекта для построения отчета.")

    required_field_errors = [e for e in all_errors if e["is_required"]]
    unique_error_row_keys = {f"{e['file_name']}-{e['sheet_name']}-{e['row']}" for e in required_field_errors}

    file_results = []
    for file_schema in project.files:
        sheet_summaries = []
        for sheet_schema in file_schema.sheets:
            if not sheet_schema.is_active: continue

            with database.get_project_db_connection(project_id) as conn:
                 cursor = conn.cursor()
                 cursor.execute("SELECT data_table_name, row_count FROM sheets WHERE id=?", (sheet_schema.id,))
                 sheet_info = cursor.fetchone()
                 table_name = sheet_info['data_table_name'] if sheet_info else None
                 sheet_total_rows = sheet_info['row_count'] if sheet_info else 0


            sheet_errors = [e for e in all_errors if e["file_name"] == file_schema.name and e["sheet_name"] == sheet_schema.name]

            # Собираем все уникальные имена правил для этого листа
            all_applicable_rule_names = set()
            for f in sheet_schema.fields:
                for r_conf in f.rules:
                    if r_conf.type and r_conf.type in RULE_REGISTRY:
                        rule_def = RULE_REGISTRY[r_conf.type]
                        formatter = rule_def.get("formatter")
                        rule_name = formatter(r_conf.params) if formatter and r_conf.params else rule_def.get("name", "Unnamed Rule")
                        all_applicable_rule_names.add(rule_name)
                    elif r_conf.group_id and r_conf.group_id in RULE_GROUPS_REGISTRY:
                        group = RULE_GROUPS_REGISTRY[r_conf.group_id]
                        all_applicable_rule_names.add(f"Группа: {group.name}")

            summary_list = []
            for rule_name in sorted(list(all_applicable_rule_names)):
                 rule_errors = [e for e in sheet_errors if e["error_type"] == rule_name]
                 error_count = len(rule_errors)
                 summary_list.append({
                     "rule_name": rule_name, "error_count": error_count,
                     "error_percentage": round((error_count / sheet_total_rows) * 100, 2) if sheet_total_rows > 0 else 0,
                     "detailed_errors": rule_errors
                 })

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
        "total_processed_rows": last_result["total_rows"],
        "required_field_error_rows_count": len(unique_error_row_keys),
        "required_field_errors": required_field_errors,
        "file_results": file_results,
        "validated_at": last_result["validated_at"].isoformat()
    }
    return response_data


@app.get("/api/projects/{project_id}/data-status", response_model=DataStatus)
async def get_data_consistency_status(project_id: str):
    """
    Проверяет целостность данных: сравнивает ожидаемое и фактическое количество строк.
    """
    logger.debug(f"[PROJECT_ID: {project_id}] Запрос на проверку целостности данных.")
    sheet_statuses = []
    is_overall_consistent = True

    try:
        with database.get_project_db_connection(project_id) as conn:
            cursor = conn.cursor()
            # Получаем все листы с их ожидаемым количеством строк и именами таблиц
            cursor.execute("SELECT name, row_count, data_table_name FROM sheets WHERE is_active = 1")
            sheets_to_check = cursor.fetchall()

            if not sheets_to_check:
                return DataStatus(
                    project_id=project_id,
                    overall_status="NO_DATA",
                    checked_at=datetime.datetime.utcnow().isoformat(),
                    details=[]
                )

            for sheet in sheets_to_check:
                expected = sheet["row_count"]
                actual = 0
                is_consistent = False

                if sheet["data_table_name"]:
                    try:
                        # Считаем фактическое количество строк в таблице данных
                        cursor.execute(f'SELECT COUNT(*) FROM "{sheet["data_table_name"]}"')
                        actual = cursor.fetchone()[0]
                        is_consistent = (expected == actual)
                    except sqlite3.OperationalError:
                        # Таблица не найдена, что является несоответствием
                        is_consistent = False

                if not is_consistent:
                    is_overall_consistent = False

                sheet_statuses.append(SheetStatus(
                    sheet_name=sheet["name"],
                    expected_rows=expected,
                    actual_rows=actual,
                    is_consistent=is_consistent
                ))

    except sqlite3.Error as e:
        logger.error(f"[PROJECT_ID: {project_id}] Ошибка БД при проверке целостности данных: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка БД при проверке данных.")

    return DataStatus(
        project_id=project_id,
        overall_status="CONSISTENT" if is_overall_consistent else "INCONSISTENT",
        checked_at=datetime.datetime.utcnow().isoformat(),
        details=sheet_statuses
    )

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

@app.get("/rule-groups")
async def read_rule_groups_page():
    return FileResponse(STATIC_DIR / "rule_groups.html")

# ==============================================================================
# 6. Startup Logic
# ==============================================================================
@app.on_event("startup")
async def startup_event():
    logger.info("Приложение запускается...")
    STATIC_DIR.mkdir(exist_ok=True)
    RULES_DIR.mkdir(exist_ok=True)
    PROJECTS_DIR.mkdir(exist_ok=True)

    # Инициализация основной базы данных
    database.setup_main_database()

    load_rules()
    read_rule_groups()
    logger.info("Приложение успешно запущено.")
