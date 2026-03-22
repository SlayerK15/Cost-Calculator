from pydantic import BaseModel
from typing import Optional


class WorkflowRunCreate(BaseModel):
    domain: str
    use_case: str
    base_model: Optional[str] = None


class WorkflowRunResponse(BaseModel):
    id: str
    status: str
    domain: str
    use_case: str
    base_model: Optional[str] = None
    n8n_execution_id: Optional[str] = None
    config_snapshot: Optional[dict] = None
    result_snapshot: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


class WorkflowCallbackPayload(BaseModel):
    status: str
    n8n_execution_id: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
