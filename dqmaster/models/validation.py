from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid

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

class RuleInGroup(BaseModel):
    id: str
    params: Optional[Dict[str, Any]] = None

class RuleGroup(BaseModel):
    id: str = Field(default_factory=lambda: f"grp_{uuid.uuid4()}")
    name: str
    logic: str  # "AND" or "OR"
    rules: List[RuleInGroup] = []

class ValidationError(BaseModel):
    file_name: str
    sheet_name: str
    field_name: str
    is_required: bool
    row: int
    error_type: str
    value: str
    details: Optional[Union[str, list]] = None

class RuleSummary(BaseModel):
    rule_name: str
    error_count: int
    error_percentage: float
    detailed_errors: List[ValidationError] = []

class SheetSummary(BaseModel):
    sheet_name: str
    total_rows: int
    sheet_error_rows_count: int
    sheet_error_percentage: float
    rule_summaries: List[RuleSummary]

class FileSummary(BaseModel):
    file_name: str
    sheets: List[SheetSummary]

class ValidationResults(BaseModel):
    total_processed_rows: int
    required_field_error_rows_count: int
    required_field_errors: List[ValidationError]
    file_results: List[FileSummary]
    validated_at: str
