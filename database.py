# database.py
import sqlite3
import logging
from pathlib import Path
from datetime import datetime

# Настройка основного логгера
logger = logging.getLogger(__name__)

# --- Адаптеры типов для работы с datetime ---
def adapt_datetime_iso(val):
    """Адаптирует datetime.datetime в наивный ISO 8601 формат."""
    return val.isoformat()

def convert_timestamp(val):
    """Конвертирует строку ISO 8601 обратно в объект datetime.datetime."""
    return datetime.fromisoformat(val.decode('utf-8'))

sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("TIMESTAMP", convert_timestamp)


MAIN_DB_PATH = Path("main.db")
PROJECTS_DIR = Path("projects")

def get_main_db_connection():
    """Возвращает соединение с основной БД."""
    try:
        conn = sqlite3.connect(MAIN_DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Ошибка подключения к основной БД: {e}")
        return None

def get_project_db_connection(project_id: str):
    """Возвращает соединение с БД проекта."""
    db_path = PROJECTS_DIR / project_id / f"project_{project_id}.db"
    try:
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"[PROJECT_ID: {project_id}] Ошибка подключения к БД проекта: {e}")
        return None

def setup_main_database():
    """
    Создает основную БД, если ее нет, и выполняет миграцию схемы,
    добавляя недостающие столбцы.
    """
    is_new_db = not MAIN_DB_PATH.exists()

    try:
        with get_main_db_connection() as conn:
            cursor = conn.cursor()

            if is_new_db:
                logger.info("Создание основной базы данных 'main.db'...")
                cursor.execute("""
                    CREATE TABLE projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        db_path TEXT NOT NULL,
                        size_kb REAL DEFAULT 0,
                        auto_revalidate BOOLEAN DEFAULT 0 NOT NULL
                    );
                """)
                logger.info("Таблица 'projects' успешно создана в 'main.db'.")
            else:
                logger.info("Основная база данных уже существует. Проверка схемы...")
                # --- Миграция: Добавляем столбец auto_revalidate, если его нет ---
                cursor.execute("PRAGMA table_info(projects)")
                columns = [column['name'] for column in cursor.fetchall()]
                if 'auto_revalidate' not in columns:
                    logger.info("Миграция: Добавление столбца 'auto_revalidate' в таблицу 'projects'.")
                    # Добавляем столбец с NOT NULL и DEFAULT 0, чтобы избежать проблем с существующими записями
                    cursor.execute("ALTER TABLE projects ADD COLUMN auto_revalidate BOOLEAN DEFAULT 0 NOT NULL;")
                    logger.info("Столбец 'auto_revalidate' успешно добавлен.")

            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при настройке или миграции основной базы данных: {e}", exc_info=True)


def create_project_db(project_id: str):
    """Создает и инициализирует базу данных для нового проекта."""
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    db_path = project_dir / f"project_{project_id}.db"

    if db_path.exists():
        logger.warning(f"[PROJECT_ID: {project_id}] База данных для проекта уже существует.")
        return True

    logger.debug(f"[PROJECT_ID: {project_id}] Создание базы данных проекта по пути: {db_path}")

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            # 1. project_metadata
            cursor.execute("""
                CREATE TABLE project_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            # 2. files
            cursor.execute("""
                CREATE TABLE files (
                    id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    saved_name TEXT NOT NULL,
                    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 3. sheets
            cursor.execute("""
                CREATE TABLE sheets (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    data_table_name TEXT,
                    row_count INTEGER DEFAULT 0, -- Количество импортированных строк
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
                );
            """)
            # 4. fields
            cursor.execute("""
                CREATE TABLE fields (
                    id TEXT PRIMARY KEY,
                    sheet_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    is_required BOOLEAN DEFAULT 0,
                    FOREIGN KEY (sheet_id) REFERENCES sheets(id) ON DELETE CASCADE
                );
            """)
            # 5. rules
            cursor.execute("""
                CREATE TABLE rules (
                    id TEXT PRIMARY KEY,
                    field_id TEXT NOT NULL,
                    rule_type TEXT,
                    group_id TEXT,
                    params TEXT,
                    order_num INTEGER DEFAULT 1,
                    FOREIGN KEY (field_id) REFERENCES fields(id) ON DELETE CASCADE
                );
            """)
            # 6. rule_groups
            cursor.execute("""
                CREATE TABLE rule_groups (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    logic TEXT CHECK(logic IN ('AND', 'OR')) NOT NULL
                );
            """)
            # 7. rule_group_items
            cursor.execute("""
                CREATE TABLE rule_group_items (
                    id TEXT PRIMARY KEY,
                    group_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES rule_groups(id) ON DELETE CASCADE,
                    FOREIGN KEY (rule_id) REFERENCES rules(id) ON DELETE CASCADE
                );
            """)
            # 8. validation_results
            cursor.execute("""
                CREATE TABLE validation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_rows INTEGER DEFAULT 0,
                    error_rows INTEGER DEFAULT 0
                );
            """)
            # 9. validation_errors
            cursor.execute("""
                CREATE TABLE validation_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_id INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    sheet_name TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    error_type TEXT NOT NULL,
                    value TEXT,
                    details TEXT,
                    is_required BOOLEAN DEFAULT 0,
                    FOREIGN KEY (result_id) REFERENCES validation_results(id) ON DELETE CASCADE
                );
            """)

            # --- 10. Создание индексов для ускорения запросов ---
            logger.debug(f"[PROJECT_ID: {project_id}] Создание индексов в БД проекта...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sheets_file_id ON sheets(file_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fields_sheet_id ON fields(sheet_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_field_id ON rules(field_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rule_group_items_group_id ON rule_group_items(group_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_validation_errors_result_id ON validation_errors(result_id);")

            # 11. Raw data tables for sheets will be created dynamically
            conn.commit()
            logger.info(f"[PROJECT_ID: {project_id}] Все таблицы успешно созданы в БД проекта.")
            return True
    except sqlite3.Error as e:
        logger.error(f"[PROJECT_ID: {project_id}] Не удалось создать БД проекта: {e}")
        # Попытка удалить неполностью созданный файл БД
        if db_path.exists():
            db_path.unlink()
        return False

def normalize_name_for_sqlite(name: str) -> str:
    """
    Приводит имя (таблицы, колонки) к безопасному для SQLite формату.
    - Заменяет пробелы и неалфавитно-цифровые символы на '_'
    - Приводит к нижнему регистру
    - Убирает последовательные '_'
    """
    import re
    # Удаляем любые символы, не являющиеся буквами, цифрами или '_'
    name = re.sub(r'[^\w]', '_', name)
    # Заменяем множественные подчеркивания на одно
    name = re.sub(r'__+', '_', name)
    # Удаляем подчеркивания в начале/конце
    name = name.strip('_')
    return name.lower()
