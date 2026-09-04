"""Domain enums (stored as plain strings for migration-friendly schemas)."""
from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    RSS = "rss"
    AUTHORIZED_FEED = "authorized_feed"
    AGENT_REACH = "agent_reach"
    MANUAL = "manual"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"


class Authorization(StrEnum):
    AUTHORIZED = "authorized"
    NOT_AUTHORIZED = "not_authorized"
    DISABLED = "disabled"


class ContentStatus(StrEnum):
    DETECTED = "detected"
    PROCESSING = "processing"
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    SKIPPED = "skipped"


class MediaType(StrEnum):
    VIDEO = "video"
    IMAGE = "image"
    TEXT = "text"


class VideoStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class BatchStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    RESTING = "resting"
    COMPLETED = "completed"
    ABORTED = "aborted"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    DISABLED = "disabled"


class IntegrationStatus(StrEnum):
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    TOKEN_ERROR = "token_error"


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    CUSTOM = "custom"


class ReportType(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    NETWORK = "network"
    ACCOUNT = "account"


class ReportStatus(StrEnum):
    GENERATED = "generated"
    SENT = "sent"
    FAILED = "failed"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(StrEnum):
    PUBLISH_SUCCESS = "publish_success"
    PUBLISH_FAILED = "publish_failed"
    TREND_DETECTED = "trend_detected"
    MILESTONE = "milestone"
    AUTOMATION_ERROR = "automation_error"
    METRIC = "metric"
