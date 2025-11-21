import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ValidationStatus:
    """Статус выполнения валидации"""
    is_running: bool = False
    current_file: str = ""
    current_sheet: str = ""
    current_field: str = ""
    current_rule: str = ""
    processed_rows: int = 0
    total_rows: int = 0
    percentage: float = 0.0
    message: str = ""
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class StatusStorage:
    """Потокобезопасное хранилище статусов валидации"""

    def __init__(self):
        self._storage: Dict[str, ValidationStatus] = {}
        self._lock = asyncio.Lock()

    async def get_status(self, project_id: str) -> ValidationStatus:
        """Получение статуса валидации"""
        async with self._lock:
            return self._storage.get(project_id, ValidationStatus())

    async def set_status(self, project_id: str, status: ValidationStatus):
        """Установка статуса валидации"""
        async with self._lock:
            status.updated_at = datetime.utcnow()
            self._storage[project_id] = status

    async def clear_status(self, project_id: str):
        """Очистка статуса валидации"""
        async with self._lock:
            self._storage.pop(project_id, None)

    async def is_running(self, project_id: str) -> bool:
        """Проверка, выполняется ли валидация"""
        status = await self.get_status(project_id)
        return status.is_running

# Глобальный экземпляр хранилища
status_storage = StatusStorage()
