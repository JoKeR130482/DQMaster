import json
import importlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from core.config import settings
from core.exceptions import SecurityError
from models.rules import RuleConfig, RuleMetadata

logger = logging.getLogger("dqmaster")

class RuleService:
    """Сервис для управления правилами валидации"""

    def __init__(self):
        self.rule_registry: Dict[str, Dict[str, Any]] = {}
        self.load_rules()

    def load_rules(self):
        """Загрузка правил из директории"""
        self.rule_registry.clear()

        # Безопасная загрузка правил - только из доверенных источников
        trusted_rules = [
            "is_empty", "is_email", "length_check", "spell_check",
            "no_leading_trailing_spaces", "unique_value", "starts_with_capital",
            "date_format_check", "no_special_chars", "contains_digit",
            "contains_letter", "in_list_check", "is_number", "substring_check"
        ]

        for rule_name in trusted_rules:
            try:
                module = importlib.import_module(f"rules.{rule_name}")
                if hasattr(module, "validate") and hasattr(module, "RULE_NAME"):
                    self.rule_registry[rule_name] = {
                        "id": rule_name,
                        "name": module.RULE_NAME,
                        "description": getattr(module, "RULE_DESC", ""),
                        "validator": module.validate,
                        "is_configurable": getattr(module, "IS_CONFIGURABLE", False),
                        "formatter": getattr(module, "format_name", None),
                        "params_schema": getattr(module, "PARAMS_SCHEMA", None),
                        "needs_column_access": getattr(module, "NEEDS_COLUMN_ACCESS", False),
                        "module": module
                    }
                    logger.info(f"Loaded rule: {rule_name}")
            except (ImportError, AttributeError) as e:
                logger.warning(f"Could not load rule {rule_name}: {e}")

    def get_all_rules(self) -> List[RuleMetadata]:
        """Получение списка всех правил"""
        return [
            RuleMetadata(
                id=rule_data["id"],
                name=rule_data["name"],
                description=rule_data["description"],
                is_configurable=rule_data["is_configurable"],
                params_schema=rule_data["params_schema"]
            )
            for rule_data in self.rule_registry.values()
        ]

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Получение правила по ID"""
        return self.rule_registry.get(rule_id)
