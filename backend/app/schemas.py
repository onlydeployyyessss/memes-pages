"""Pydantic request schemas (responses are serialized ORM rows)."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = __import__("re").compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _check_email(v: str) -> str:
    v = (v or "").strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("invalid email address")
    return v


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return _check_email(v)


class AdminCreateIn(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=200)
    full_name: str = ""
    role: str = "admin"  # owner|admin|viewer

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return _check_email(v)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    platform: str = "instagram"
    username: str = ""
    external_id: str = ""
    notes: str = ""


class AccountPatchIn(BaseModel):
    name: str | None = None
    platform: str | None = None
    username: str | None = None
    external_id: str | None = None
    status: str | None = None
    automation_enabled: bool | None = None
    default_caption_id: int | None = None
    caption_template_id: int | None = None
    reel_cover_id: int | None = None
    notes: str | None = None


class CredentialsIn(BaseModel):
    credentials: dict = Field(default_factory=dict)


class AccountSettingsIn(BaseModel):
    caption_settings: dict | None = None
    cover_settings: dict | None = None
    schedule_settings: dict | None = None
    posting_limits: dict | None = None
    distribution: dict | None = None


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    source_type: str = "rss"
    url: str = ""
    authorization: str = "not_authorized"
    enabled: bool = True
    categories: list[str] = []
    priority: int = 5
    check_interval_minutes: int = 15
    config: dict = {}
    notes: str = ""


class SourcePatchIn(BaseModel):
    name: str | None = None
    url: str | None = None
    authorization: str | None = None
    enabled: bool | None = None
    categories: list[str] | None = None
    priority: int | None = None
    check_interval_minutes: int | None = None
    config: dict | None = None
    notes: str | None = None


class FeedIn(BaseModel):
    feed_name: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=8)
    category: str = "memes"
    priority: int = 5
    enabled: bool = True
    check_interval_minutes: int = 15
    authorization: str = "authorized"  # feeds are usually authorized by owner


class CaptionIn(BaseModel):
    name: str
    text: str = ""
    hashtags: list[str] = []
    is_default: bool = False
    language: str = "en"


class CaptionTemplateIn(BaseModel):
    name: str
    template_text: str = ""
    placeholder_keys: list[str] = []
    weight: int = 1
    enabled: bool = True


class AssignIn(BaseModel):
    account_id: int
