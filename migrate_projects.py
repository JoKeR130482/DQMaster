# migrate_projects.py
import os
import sys
import json
import shutil
import sqlite3
import time
from pathlib import Path
from tqdm import tqdm
import pandas as pd
import io
import uuid
from datetime import datetime

# --- Настройка путей для импорта модулей ---
# Добавляем корневую директорию проекта в sys.path, чтобы можно было импортировать database и main
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

import database
from main import Project, FileSchema, SheetSchema, FieldSchema, Rule # Импортируем Pydantic модели

# --- Глобальные переменные ---
PROJECTS_DIR = database.PROJECTS_DIR
logger = database.logger # Используем тот же логгер, что и в основном приложении

def migrate_project_data(project_id: str, project_model: Project, conn: sqlite3.Connection):
    """
    Мигрирует данные из Excel-файлов и структуру из Pydantic модели в БД проекта.
    """
    cursor = conn.cursor()

    # 1. Проходим по файлам из старого project.json
    for file_schema in project_model.files:
        old_file_path = PROJECTS_DIR / project_id / "files" / file_schema.saved_name
        if not old_file_path.exists():
            logger.warning(f"[{project_id}] Файл {file_schema.saved_name} не найден, пропуск.")
            continue

        # Создаем архивную директорию
        archive_dir = PROJECTS_DIR / project_id / "archive"
        archive_dir.mkdir(exist_ok=True)
        new_file_path = archive_dir / file_schema.saved_name

        # Читаем содержимое файла
        contents = old_file_path.read_bytes()

        # 2. Импортируем данные (аналогично _import_excel_to_db в main.py)
        xls = pd.ExcelFile(io.BytesIO(contents))

        cursor.execute(
            "INSERT INTO files (id, original_name, saved_name, upload_time) VALUES (?, ?, ?, ?)",
            (file_schema.id, file_schema.name, file_schema.saved_name, datetime.utcnow())
        )

        for sheet_schema in file_schema.sheets:
            table_name = f"data_sheet_{database.normalize_name_for_sqlite(sheet_schema.name)}_{sheet_schema.id[:8]}"

            cursor.execute(
                "INSERT INTO sheets (id, file_id, name, is_active, data_table_name) VALUES (?, ?, ?, ?, ?)",
                (sheet_schema.id, file_schema.id, sheet_schema.name, sheet_schema.is_active, table_name)
            )

            df = pd.read_excel(xls, sheet_name=sheet_schema.name)
            for col in df.columns:
                df[col] = df[col].astype(str)

            normalized_columns = {col: database.normalize_name_for_sqlite(col) for col in df.columns}
            df.rename(columns=normalized_columns, inplace=True)

            cols_with_types = ", ".join(f'"{col_name}" TEXT' for col_name in df.columns)
            cursor.execute(f'CREATE TABLE "{table_name}" (_row_id INTEGER PRIMARY KEY AUTOINCREMENT, {cols_with_types});')

            if not df.empty:
                df.to_sql(name=table_name, con=conn, if_exists='append', index=False)

            # 3. Мигрируем поля и правила
            for field_schema in sheet_schema.fields:
                cursor.execute(
                    "INSERT INTO fields (id, sheet_id, name, is_required) VALUES (?, ?, ?, ?)",
                    (field_schema.id, sheet_schema.id, field_schema.name, field_schema.is_required)
                )
                for rule in field_schema.rules:
                    cursor.execute(
                        """INSERT INTO rules (id, field_id, rule_type, group_id, params, order_num)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (rule.id, field_schema.id, rule.type, rule.group_id, json.dumps(rule.params) if rule.params else None, rule.order)
                    )

        # 4. Перемещаем файл в архив
        shutil.move(str(old_file_path), str(new_file_path))

    # Удаляем старую директорию 'files'
    old_files_dir = PROJECTS_DIR / project_id / "files"
    if old_files_dir.exists():
        shutil.rmtree(old_files_dir)


def main():
    """
    Основная функция для запуска процесса миграции.
    """
    logger.info("="*50)
    logger.info("Запуск утилиты миграции проектов в архитектуру SQLite.")
    logger.info("="*50)

    # Убедимся, что основная БД существует
    database.setup_main_database()

    # Получаем список всех директорий проектов
    if not PROJECTS_DIR.exists():
        logger.warning("Директория 'projects' не найдена. Нет проектов для миграции.")
        return

    project_dirs = [d for d in PROJECTS_DIR.iterdir() if d.is_dir()]

    # Отфильтровываем проекты, которые уже есть в новой БД
    projects_to_migrate = []
    with database.get_main_db_connection() as conn:
        cursor = conn.cursor()
        for project_dir in project_dirs:
            project_id = project_dir.name
            cursor.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
            if cursor.fetchone():
                logger.info(f"Проект '{project_id}' уже находится в main.db, пропуск.")
                continue

            if not (project_dir / "project.json").exists():
                logger.warning(f"В директории проекта '{project_id}' отсутствует project.json, пропуск.")
                continue

            projects_to_migrate.append(project_dir)

    if not projects_to_migrate:
        logger.info("Все существующие проекты уже мигрированы. Работа завершена.")
        return

    logger.info(f"Найдено {len(projects_to_migrate)} проектов для миграции.")

    # Запускаем процесс миграции с прогресс-баром
    with tqdm(total=len(projects_to_migrate), desc="Миграция проектов") as pbar:
        for project_dir in projects_to_migrate:
            project_id = project_dir.name
            pbar.set_description(f"Миграция {project_id}")

            # 1. Читаем старый project.json
            try:
                project_json_path = project_dir / "project.json"
                project_model = Project(**json.loads(project_json_path.read_text(encoding="utf-8")))
            except Exception as e:
                logger.error(f"Не удалось прочитать или распарсить project.json для '{project_id}': {e}. Пропуск.")
                pbar.update(1)
                continue

            # 2. Создаем новую БД для проекта
            if not database.create_project_db(project_id):
                logger.error(f"Не удалось создать БД для проекта '{project_id}'. Пропуск.")
                pbar.update(1)
                continue

            # 3. Регистрируем проект в main.db
            try:
                with database.get_main_db_connection() as main_conn:
                    db_path = PROJECTS_DIR / project_id / f"project_{project_id}.db"
                    main_conn.execute(
                        "INSERT INTO projects (id, name, description, created_at, updated_at, db_path) VALUES (?, ?, ?, ?, ?, ?)",
                        (project_id, project_model.name, project_model.description, project_model.created_at, project_model.updated_at, str(db_path))
                    )
                    main_conn.commit()
            except Exception as e:
                logger.error(f"Не удалось зарегистрировать проект '{project_id}' в main.db: {e}. Пропуск.")
                # Удаляем частично созданную БД
                shutil.rmtree(project_dir)
                pbar.update(1)
                continue

            # 4. Мигрируем данные и структуру
            try:
                with database.get_project_db_connection(project_id) as proj_conn:
                    proj_conn.execute("BEGIN;")
                    migrate_project_data(project_id, project_model, proj_conn)
                    proj_conn.commit()
            except Exception as e:
                logger.error(f"КРИТИЧЕСКАЯ ОШИБКА при миграции данных проекта '{project_id}': {e}", exc_info=True)
                with database.get_project_db_connection(project_id) as proj_conn:
                    proj_conn.rollback()
                logger.error(f"Откат изменений для '{project_id}'. Проект НЕ мигрирован.")
                pbar.update(1)
                continue

            # 5. Переименовываем project.json для отметки о завершении
            project_json_path.rename(project_json_path.with_suffix(".json.migrated"))

            logger.info(f"Проект '{project_id}' успешно мигрирован.")
            pbar.update(1)

    logger.info("="*50)
    logger.info("Миграция завершена.")
    logger.info("="*50)


if __name__ == "__main__":
    main()
