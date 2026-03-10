from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ── Auth ──
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── LLM Model ──
class ModelCreateHuggingFace(BaseModel):
    huggingface_id: str
    precision: str = "fp16"
    context_length: int = 4096
    expected_qps: float = 1.0
    avg_tokens_per_request: int = 512


class ModelCreateCustomUpload(BaseModel):
    name: str
    file_size_bytes: int
    precision: str = "fp16"
    context_length: int = 4096
    parameters_billion: Optional[float] = None
    expected_qps: float = 1.0
    avg_tokens_per_request: int = 512


class ModelResponse(BaseModel):
    id: str
    name: str
    source: str
    huggingface_id: Optional[str]
    file_size_bytes: Optional[int]
    parameters_billion: Optional[float]
    precision: str
    context_length: int
    architecture: Optional[str]
    is_parameters_estimated: bool
    profiled: bool
    peak_vram_gb: Optional[float]
    tokens_per_second: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True
