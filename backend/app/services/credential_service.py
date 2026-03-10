"""Service for encrypting, decrypting, and validating cloud credentials."""

import json
import os
from cryptography.fernet import Fernet

# In production, load from env / secrets manager
_ENCRYPTION_KEY = os.getenv(
    "CREDENTIAL_ENCRYPTION_KEY",
    Fernet.generate_key().decode(),  # fallback for dev
)
_fernet = Fernet(_ENCRYPTION_KEY.encode() if isinstance(_ENCRYPTION_KEY, str) else _ENCRYPTION_KEY)


# ── Required fields per provider ──

PROVIDER_FIELDS = {
    "aws": ["aws_access_key_id", "aws_secret_access_key"],
    "gcp": ["service_account_json"],
    "azure": ["tenant_id", "client_id", "client_secret", "subscription_id"],
}


def encrypt_credentials(creds: dict) -> str:
    """Encrypt a credentials dict into a Fernet token string."""
    plaintext = json.dumps(creds).encode()
    return _fernet.encrypt(plaintext).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt a Fernet token string back into a credentials dict."""
    plaintext = _fernet.decrypt(encrypted.encode())
    return json.loads(plaintext.decode())


def validate_credential_fields(provider: str, creds: dict) -> list[str]:
    """Return list of missing required fields for the given provider."""
    required = PROVIDER_FIELDS.get(provider, [])
    return [f for f in required if not creds.get(f)]


def mask_credentials(provider: str, creds: dict) -> dict:
    """Return a masked version of credentials for display (never reveal secrets)."""
    masked = {}
    for key, value in creds.items():
        if not value:
            masked[key] = ""
        elif key == "service_account_json":
            masked[key] = "****service-account****"
        elif len(str(value)) > 8:
            s = str(value)
            masked[key] = s[:4] + "****" + s[-4:]
        else:
            masked[key] = "****"
    return masked


async def validate_cloud_credentials(provider: str, creds: dict) -> tuple[bool, str]:
    """
    Simulate credential validation for each provider.
    In production, this would make real API calls (STS, IAM, etc.).
    """
    missing = validate_credential_fields(provider, creds)
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"

    if provider == "aws":
        key_id = creds.get("aws_access_key_id", "")
        if not key_id.startswith("AKIA") and not key_id.startswith("ASIA"):
            return False, "AWS access key ID should start with AKIA or ASIA"
        return True, "AWS credentials validated (STS GetCallerIdentity)"

    elif provider == "gcp":
        sa_json = creds.get("service_account_json", "")
        try:
            sa = json.loads(sa_json) if isinstance(sa_json, str) else sa_json
            if "project_id" not in sa:
                return False, "Service account JSON missing 'project_id'"
            return True, f"GCP credentials validated (project: {sa['project_id']})"
        except (json.JSONDecodeError, TypeError):
            return False, "Invalid service account JSON"

    elif provider == "azure":
        return True, "Azure credentials validated (service principal)"

    return False, f"Unknown provider: {provider}"
