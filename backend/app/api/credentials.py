from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.models import CloudCredential, CredentialStatus, UserTier
from app.api.subscription import require_tier
from app.services.credential_service import (
    encrypt_credentials,
    decrypt_credentials,
    validate_credential_fields,
    validate_cloud_credentials,
    mask_credentials,
    PROVIDER_FIELDS,
)

router = APIRouter(prefix="/credentials", tags=["credentials"])


# ── Schemas ──

class CredentialCreate(BaseModel):
    provider: str  # aws, gcp, azure
    label: str
    credentials: dict  # raw credential fields


class CredentialResponse(BaseModel):
    id: str
    provider: str
    label: str
    status: str
    masked_credentials: dict
    validated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CredentialFieldsResponse(BaseModel):
    provider: str
    required_fields: list[str]


# ── Endpoints ──

@router.get("/providers")
async def list_provider_fields():
    """List required credential fields per cloud provider."""
    return [
        CredentialFieldsResponse(provider=p, required_fields=f)
        for p, f in PROVIDER_FIELDS.items()
    ]


@router.post("/create", response_model=CredentialResponse)
async def create_credential(
    data: CredentialCreate,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Store encrypted cloud credentials."""
    if data.provider not in PROVIDER_FIELDS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {data.provider}")

    missing = validate_credential_fields(data.provider, data.credentials)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")

    encrypted = encrypt_credentials(data.credentials)

    cred = CloudCredential(
        user_id=user.id,
        provider=data.provider,
        label=data.label,
        encrypted_credentials=encrypted,
        status=CredentialStatus.PENDING,
    )
    db.add(cred)
    await db.flush()
    await db.refresh(cred)

    return CredentialResponse(
        id=cred.id,
        provider=cred.provider.value,
        label=cred.label,
        status=cred.status.value,
        masked_credentials=mask_credentials(data.provider, data.credentials),
        validated_at=cred.validated_at,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


@router.get("/list", response_model=list[CredentialResponse])
async def list_credentials(
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """List all credentials for the current user (masked)."""
    result = await db.execute(
        select(CloudCredential)
        .where(CloudCredential.user_id == user.id)
        .order_by(CloudCredential.created_at.desc())
    )
    creds = result.scalars().all()
    responses = []
    for c in creds:
        try:
            raw = decrypt_credentials(c.encrypted_credentials)
            masked = mask_credentials(c.provider.value, raw)
        except Exception:
            masked = {"error": "Unable to decrypt"}
        responses.append(CredentialResponse(
            id=c.id,
            provider=c.provider.value,
            label=c.label,
            status=c.status.value,
            masked_credentials=masked,
            validated_at=c.validated_at,
            created_at=c.created_at,
            updated_at=c.updated_at,
        ))
    return responses


@router.post("/{credential_id}/validate")
async def validate_credential(
    credential_id: str,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Validate stored credentials against the cloud provider."""
    result = await db.execute(
        select(CloudCredential).where(
            CloudCredential.id == credential_id,
            CloudCredential.user_id == user.id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    raw = decrypt_credentials(cred.encrypted_credentials)
    is_valid, message = await validate_cloud_credentials(cred.provider.value, raw)

    cred.status = CredentialStatus.VALID if is_valid else CredentialStatus.INVALID
    if is_valid:
        cred.validated_at = datetime.now(timezone.utc)
    await db.flush()

    return {"valid": is_valid, "message": message, "status": cred.status.value}


@router.delete("/{credential_id}")
async def delete_credential(
    credential_id: str,
    user=Depends(require_tier(UserTier.ENTERPRISE)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a stored credential."""
    result = await db.execute(
        select(CloudCredential).where(
            CloudCredential.id == credential_id,
            CloudCredential.user_id == user.id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    await db.delete(cred)
    await db.flush()
    return {"message": "Credential deleted"}
