import os
from dataclasses import dataclass
from pathlib import Path


def _flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class Settings:
    dev_mode: bool
    service_name: str
    storage_account: str
    batch_endpoint: str
    head_pool_id: str
    worker_pool_id: str
    runtime_image: str
    head_identity_client_id: str
    allowed_roles: tuple[str, ...]
    builtin_pipelines_dir: Path
    data_dir: Path
    max_upload_bytes: int
    public_url: str
    auth_client_id: str
    auth_client_secret: str
    auth_authority: str
    session_secret: str

    @property
    def blob_endpoint(self) -> str:
        return f"https://{self.storage_account}.blob.core.windows.net"


def load_settings() -> Settings:
    app_dir = Path(__file__).resolve().parent.parent
    roles = os.environ.get("NF_ALLOWED_ROLES", "WorkspaceOwner,WorkspaceResearcher")
    return Settings(
        dev_mode=_flag("NF_DEV_MODE"),
        service_name=os.environ.get("NF_SERVICE_NAME", "Nextflow"),
        storage_account=os.environ.get("NF_STORAGE_ACCOUNT", ""),
        batch_endpoint=os.environ.get("NF_BATCH_ENDPOINT", ""),
        head_pool_id=os.environ.get("NF_HEAD_POOL_ID", "nf-head"),
        worker_pool_id=os.environ.get("NF_WORKER_POOL_ID", "nf-worker"),
        runtime_image=os.environ.get("NF_RUNTIME_IMAGE", ""),
        head_identity_client_id=os.environ.get("NF_HEAD_IDENTITY_CLIENT_ID", ""),
        allowed_roles=tuple(r.strip() for r in roles.split(",") if r.strip()),
        builtin_pipelines_dir=Path(os.environ.get("NF_BUILTIN_PIPELINES_DIR", app_dir / "pipelines")),
        data_dir=Path(os.environ.get("NF_DATA_DIR", app_dir / ".devdata")),
        max_upload_bytes=int(os.environ.get("NF_MAX_UPLOAD_MB", "1024")) * 1024 * 1024,
        public_url=os.environ.get("NF_PUBLIC_URL", "").rstrip("/"),
        auth_client_id=os.environ.get("NF_AUTH_CLIENT_ID", ""),
        auth_client_secret=os.environ.get("NF_AUTH_CLIENT_SECRET", ""),
        auth_authority=os.environ.get("NF_AUTH_AUTHORITY", ""),
        session_secret=os.environ.get("NF_SESSION_SECRET", ""),
    )
