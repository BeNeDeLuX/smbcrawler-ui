from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from .models import AnnotationKind, AnnotationStatus, ScanSource, ScanStatus


class LoginIn(BaseModel):
    password: str


class CredentialIn(BaseModel):
    username: str = " "
    domain: str = "."
    password: str = ""
    nthash: str = ""
    aeskey: str = ""
    dc_ip: str = ""
    use_kerberos: bool = False


class ScanOptions(BaseModel):
    threads: int = Field(1, ge=1, le=64)
    depth: int = Field(1, ge=-1, le=64)
    timeout: int = Field(5, ge=1, le=120)
    check_write_access: bool = False
    disable_autodownload: bool = False
    crawl_printers_and_pipes: bool = False
    max_file_size_kib: int = Field(200, ge=1, le=1_048_576)
    force: bool = False


class ScanCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    targets: list[str] = []
    hostfile_text: str | None = None
    credentials: CredentialIn = CredentialIn()
    options: ScanOptions = ScanOptions()
    extra_profile_yaml: str | None = None
    no_default: bool = False


class ScanOut(BaseModel):
    id: uuid.UUID
    name: str
    source: ScanSource
    status: ScanStatus
    params: dict
    progress: dict
    error: str | None
    created_at: dt.datetime
    started_at: dt.datetime | None
    finished_at: dt.datetime | None

    model_config = ConfigDict(from_attributes=True)


class DryRunIn(BaseModel):
    targets: list[str] = []
    extra_profile_yaml: str | None = None


class FetchIn(BaseModel):
    """Credentials for an on-demand SMB fetch of a single not-downloaded file."""

    username: str = ""
    domain: str = ""
    password: str = ""
    nthash: str = ""
    max_mib: int = Field(50, ge=1, le=500)
    timeout: int = Field(8, ge=1, le=60)


class AnnotationIn(BaseModel):
    kind: AnnotationKind
    ref: str
    status: AnnotationStatus = AnnotationStatus.open
    note: str = ""


class AnnotationOut(BaseModel):
    kind: AnnotationKind
    ref: str
    status: AnnotationStatus
    note: str
    updated_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)
