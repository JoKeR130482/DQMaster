"""
Проверяет, является ли значение действительным адресом электронной почты.
Правило является настраиваемым.
"""
import re
from typing import Dict, Any, List, Optional

# Описание параметров для UI
PARAMS_SCHEMA = [
    {
        "name": "allow_empty",
        "type": "bool",
        "default": False,
        "label": "Разрешить пустые значения"
    },
    {
        "name": "domain_whitelist",
        "type": "string",
        "default": "",
        "label": "Белый список доменов (через запятую)"
    }
]

# Флаг, указывающий, что правило можно настраивать
IS_CONFIGURABLE = True

# Регулярное выражение для базовой проверки формата email
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def validate(value: Any, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Выполняет валидацию.
    """
    params = params or {}
    allow_empty = params.get("allow_empty", False)
    domain_whitelist_str = params.get("domain_whitelist", "")

    if value is None or (isinstance(value, str) and not value.strip()):
        return {"is_valid": allow_empty, "error": None if allow_empty else "Пустое значение недопустимо"}

    if not isinstance(value, str):
        return {"is_valid": False, "error": "Значение не является строкой"}

    if not EMAIL_REGEX.match(value):
        return {"is_valid": False, "error": "Неверный формат email"}

    if domain_whitelist_str:
        domain = value.split('@')[1]
        whitelist = [d.strip().lower() for d in domain_whitelist_str.split(',') if d.strip()]
        if domain.lower() not in whitelist:
            return {"is_valid": False, "error": f"Домен '{domain}' отсутствует в белом списке"}

    return {"is_valid": True, "error": None}

def format_name(params: Optional[Dict[str, Any]] = None) -> str:
    """
    Форматирует имя правила для отображения в UI на основе его параметров.
    """
    params = params or {}
    allow_empty = params.get("allow_empty", False)
    domain_whitelist_str = params.get("domain_whitelist", "")

    details = []
    if allow_empty:
        details.append("пустые разрешены")

    if domain_whitelist_str:
        # Показываем только первые несколько доменов, если список длинный
        whitelist = [d.strip() for d in domain_whitelist_str.split(',')]
        display_domains = ", ".join(whitelist[:2])
        if len(whitelist) > 2:
            display_domains += "..."
        details.append(f"домены: {display_domains}")

    if not details:
        return "Проверка email (стандартная)"

    return f"Проверка email ({'; '.join(details)})"
