import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Text, JSON,
    ForeignKey, Enum as SAEnum, BigInteger,
)
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


def utcnow():
    return datetime.now(timezone.utc)


def generate_uuid():
    return str(uuid.uuid4())


class CloudProvider(str, enum.Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class ModelSource(str, enum.Enum):
    HUGGINGFACE = "huggingface"
    CUSTOM_UPLOAD = "custom_upload"
    COMPOSED = "composed"


class UserTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class QuantizationMethod(str, enum.Enum):
    NONE = "none"
    GPTQ = "gptq"
    AWQ = "awq"
    BNB_INT8 = "bnb_int8"
    BNB_INT4 = "bnb_int4"


class MergeMethod(str, enum.Enum):
    LINEAR = "linear"
    SLERP = "slerp"
    TIES = "ties"
    DARE = "dare"


class Precision(str, enum.Enum):
    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"


class DeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    TERMINATED = "terminated"


class ManagedDeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    VALIDATING_CREDENTIALS = "validating_credentials"
    PROVISIONING_INFRA = "provisioning_infra"
    BUILDING_IMAGE = "building_image"
    DEPLOYING_MODEL = "deploying_model"
    RUNNING = "running"
    SCALING = "scaling"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"
    TEARING_DOWN = "tearing_down"
    TERMINATED = "terminated"


class CredentialStatus(str, enum.Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    tier = Column(SAEnum(UserTier), default=UserTier.FREE)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    stripe_customer_id = Column(String, nullable=True, unique=True, index=True)
    stripe_subscription_id = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    models = relationship("LLMModel", back_populates="owner")
    deployments = relationship("Deployment", back_populates="owner")
    cost_estimates = relationship("CostEstimate", back_populates="owner")
    model_configs = relationship("ModelConfig", back_populates="owner")


class LLMModel(Base):
    __tablename__ = "llm_models"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    source = Column(SAEnum(ModelSource), nullable=False)
    huggingface_id = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)

    # Model specs
    parameters_billion = Column(Float, nullable=True)
    precision = Column(SAEnum(Precision), default=Precision.FP16)
    context_length = Column(Integer, default=4096)
    architecture = Column(String, nullable=True)
    is_parameters_estimated = Column(Boolean, default=False)

    # Profiling results
    profiled = Column(Boolean, default=False)
    peak_vram_gb = Column(Float, nullable=True)
    tokens_per_second = Column(Float, nullable=True)
    load_latency_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)

    owner = relationship("User", back_populates="models")
    cost_estimates = relationship("CostEstimate", back_populates="model")
    deployments = relationship("Deployment", back_populates="model")


class CostEstimate(Base):
    __tablename__ = "cost_estimates"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    model_id = Column(String, ForeignKey("llm_models.id"), nullable=False)

    cloud_provider = Column(SAEnum(CloudProvider), nullable=False)
    gpu_type = Column(String, nullable=False)
    gpu_count = Column(Integer, default=1)
    instance_type = Column(String, nullable=False)

    # Cost breakdown
    vram_required_gb = Column(Float, nullable=False)
    compute_cost_monthly = Column(Float, nullable=False)
    storage_cost_monthly = Column(Float, nullable=False)
    bandwidth_cost_monthly = Column(Float, nullable=False)
    idle_cost_monthly = Column(Float, nullable=False)
    total_cost_monthly = Column(Float, nullable=False)

    # Configuration
    expected_qps = Column(Float, default=1.0)
    avg_tokens_per_request = Column(Integer, default=512)
    hours_per_day = Column(Integer, default=24)
    autoscaling_enabled = Column(Boolean, default=False)
    min_replicas = Column(Integer, default=1)
    max_replicas = Column(Integer, default=1)

    cost_breakdown_json = Column(JSON, nullable=True)
    recommendation = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)

    owner = relationship("User", back_populates="cost_estimates")
    model = relationship("LLMModel", back_populates="cost_estimates")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    model_id = Column(String, ForeignKey("llm_models.id"), nullable=True)

    cloud_provider = Column(SAEnum(CloudProvider), nullable=False)
    status = Column(SAEnum(DeploymentStatus), default=DeploymentStatus.PENDING)
    instance_type = Column(String, nullable=False)
    gpu_type = Column(String, nullable=False)
    gpu_count = Column(Integer, default=1)
    region = Column(String, default="us-east-1")

    endpoint_url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)

    # Generated configs
    dockerfile = Column(Text, nullable=True)
    kubernetes_yaml = Column(Text, nullable=True)
    terraform_config = Column(Text, nullable=True)

    # Monitoring
    total_requests = Column(BigInteger, default=0)
    total_tokens_generated = Column(BigInteger, default=0)
    total_cost_incurred = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner = relationship("User", back_populates="deployments")
    model = relationship("LLMModel", back_populates="deployments")
    chat_sessions = relationship("ChatSession", back_populates="deployment")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    deployment_id = Column(String, ForeignKey("deployments.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    messages_json = Column(JSON, default=list)
    total_tokens_used = Column(BigInteger, default=0)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    deployment = relationship("Deployment", back_populates="chat_sessions")


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    deployment_id = Column(String, ForeignKey("deployments.id"), nullable=False)

    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    latency_ms = Column(Float, nullable=True)
    cost_usd = Column(Float, default=0.0)
    timestamp = Column(DateTime(timezone=True), default=utcnow)


class ModelConfig(Base):
    """A user-composed model configuration from the no-code builder."""
    __tablename__ = "model_configs"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, default=1)

    # Base model reference
    base_model_id = Column(String, ForeignKey("llm_models.id"), nullable=True)
    base_model_hf_id = Column(String, nullable=True)

    # LoRA adapter
    adapter_hf_id = Column(String, nullable=True)
    adapter_file_path = Column(String, nullable=True)

    # Merge config
    is_merge = Column(Boolean, default=False)
    merge_method = Column(SAEnum(MergeMethod), nullable=True)
    merge_models_json = Column(JSON, nullable=True)

    # Quantization
    quantization_method = Column(SAEnum(QuantizationMethod), default=QuantizationMethod.NONE)

    # Inference params
    system_prompt = Column(Text, nullable=True)
    default_temperature = Column(Float, default=0.7)
    default_top_p = Column(Float, default=0.9)
    default_max_tokens = Column(Integer, default=512)

    # Computed specs
    effective_parameters_billion = Column(Float, nullable=True)
    effective_precision = Column(String, nullable=True)
    effective_context_length = Column(Integer, nullable=True)
    estimated_vram_gb = Column(Float, nullable=True)

    # Visual builder state
    pipeline_json = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner = relationship("User", back_populates="model_configs")
    base_model = relationship("LLMModel", foreign_keys=[base_model_id])
    versions = relationship("ModelConfigVersion", back_populates="config", order_by="ModelConfigVersion.version.desc()")


class ModelConfigVersion(Base):
    """Version history for model configurations."""
    __tablename__ = "model_config_versions"

    id = Column(String, primary_key=True, default=generate_uuid)
    config_id = Column(String, ForeignKey("model_configs.id"), nullable=False)
    version = Column(Integer, nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    change_summary = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    config = relationship("ModelConfig", back_populates="versions")


class LiveGPUPrice(Base):
    """GPU instance pricing fetched by n8n workflows."""
    __tablename__ = "live_gpu_prices"

    id = Column(String, primary_key=True, default=generate_uuid)
    provider = Column(String, nullable=False, index=True)  # aws, gcp, azure
    instance_type = Column(String, nullable=False)
    gpu_type = Column(String, nullable=False)
    gpu_count = Column(Integer, nullable=False)
    vram_per_gpu_gb = Column(Float, nullable=False)
    total_vram_gb = Column(Float, nullable=False)
    cost_per_hour = Column(Float, nullable=False)
    spot_price_per_hour = Column(Float, nullable=True)
    region = Column(String, default="us-east-1")
    storage_cost_per_gb_month = Column(Float, default=0.08)
    bandwidth_cost_per_gb = Column(Float, default=0.09)
    vcpus = Column(Integer, default=0)
    ram_gb = Column(Float, default=0)
    source = Column(String, default="n8n")  # n8n, manual, api
    fetched_at = Column(DateTime(timezone=True), default=utcnow)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class LiveAPIPrice(Base):
    """API provider pricing fetched by n8n workflows."""
    __tablename__ = "live_api_prices"

    id = Column(String, primary_key=True, default=generate_uuid)
    provider = Column(String, nullable=False, index=True)  # OpenAI, Anthropic, etc.
    model = Column(String, nullable=False)
    input_cost_per_million = Column(Float, nullable=False)
    output_cost_per_million = Column(Float, nullable=False)
    source = Column(String, default="n8n")
    fetched_at = Column(DateTime(timezone=True), default=utcnow)
    created_at = Column(DateTime(timezone=True), default=utcnow)


# ── Phase 3: Managed Cloud Deployment ──


class CloudCredential(Base):
    """Encrypted cloud provider credentials for managed deployment."""
    __tablename__ = "cloud_credentials"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    provider = Column(SAEnum(CloudProvider), nullable=False)
    label = Column(String, nullable=False)  # user-friendly name
    status = Column(SAEnum(CredentialStatus), default=CredentialStatus.PENDING)

    # Encrypted credential blob (Fernet)
    encrypted_credentials = Column(Text, nullable=False)

    validated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner = relationship("User", backref="cloud_credentials")


class ManagedDeployment(Base):
    """A fully managed cloud deployment (ENTERPRISE tier)."""
    __tablename__ = "managed_deployments"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    deployment_id = Column(String, ForeignKey("deployments.id"), nullable=True)
    credential_id = Column(String, ForeignKey("cloud_credentials.id"), nullable=False)

    status = Column(SAEnum(ManagedDeploymentStatus), default=ManagedDeploymentStatus.PENDING)
    cloud_provider = Column(SAEnum(CloudProvider), nullable=False)
    region = Column(String, default="us-east-1")
    instance_type = Column(String, nullable=False)
    gpu_type = Column(String, nullable=False)
    gpu_count = Column(Integer, default=1)

    # Provisioning
    cluster_endpoint = Column(String, nullable=True)
    terraform_state_ref = Column(String, nullable=True)
    provision_log = Column(Text, nullable=True)

    # Auto-scaling
    autoscaling_enabled = Column(Boolean, default=False)
    min_replicas = Column(Integer, default=1)
    max_replicas = Column(Integer, default=3)
    target_gpu_utilization = Column(Float, default=0.7)

    # Health
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String, default="unknown")
    uptime_seconds = Column(BigInteger, default=0)

    # Cost tracking
    estimated_hourly_cost = Column(Float, default=0.0)
    total_cost_incurred = Column(Float, default=0.0)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner = relationship("User", backref="managed_deployments")
    credential = relationship("CloudCredential")
    base_deployment = relationship("Deployment")
    metrics = relationship("DeploymentMetric", back_populates="managed_deployment",
                          order_by="DeploymentMetric.timestamp.desc()")


class DeploymentMetric(Base):
    """Time-series metrics for managed deployments."""
    __tablename__ = "deployment_metrics"

    id = Column(String, primary_key=True, default=generate_uuid)
    managed_deployment_id = Column(String, ForeignKey("managed_deployments.id"), nullable=False)

    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)
    requests_count = Column(Integer, default=0)
    avg_latency_ms = Column(Float, default=0.0)
    p99_latency_ms = Column(Float, default=0.0)
    tokens_generated = Column(BigInteger, default=0)
    gpu_utilization = Column(Float, default=0.0)  # 0-1
    vram_used_gb = Column(Float, default=0.0)
    cpu_utilization = Column(Float, default=0.0)  # 0-1
    active_replicas = Column(Integer, default=1)
    cost_usd = Column(Float, default=0.0)

    managed_deployment = relationship("ManagedDeployment", back_populates="metrics")


class CostAlert(Base):
    """Cost budget alerts for managed deployments."""
    __tablename__ = "cost_alerts"

    id = Column(String, primary_key=True, default=generate_uuid)
    managed_deployment_id = Column(String, ForeignKey("managed_deployments.id"), nullable=False)

    monthly_budget_usd = Column(Float, nullable=False)
    alert_threshold_pct = Column(Float, default=80.0)  # Alert at this % of budget
    alert_triggered = Column(Boolean, default=False)
    alert_triggered_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    managed_deployment = relationship("ManagedDeployment", backref="cost_alerts")
