"""All ORM models — import this module to register everything on Base."""
from memes_shared.models.enums import (
    AccountStatus,
    Authorization,
    BatchStatus,
    ContentStatus,
    EventType,
    IntegrationStatus,
    JobStatus,
    MediaType,
    Platform,
    ReportStatus,
    ReportType,
    Severity,
    SourceType,
    VideoStatus,
)
from memes_shared.models.users import AdminUser, User
from memes_shared.models.accounts import (
    AccountMetrics,
    AccountSettings,
    DailyMetric,
    DestinationAccount,
)
from memes_shared.models.sources import ContentSource, RssFeed
from memes_shared.models.content import DiscoveredContent, Video, VideoHash
from memes_shared.models.trends import TrendHistory, TrendScore
from memes_shared.models.captions import Caption, CaptionTemplate
from memes_shared.models.covers import ReelCover
from memes_shared.models.publishing import (
    PublishingBatch,
    PublishingHistory,
    PublishingJob,
    Schedule,
)
from memes_shared.models.analytics import AnalyticsEvent, Report
from memes_shared.models.logs import (
    AppSetting,
    AuditLog,
    AutomationLog,
    ErrorLog,
)

__all__ = [
    # enums
    "AccountStatus", "Authorization", "BatchStatus", "ContentStatus", "EventType",
    "IntegrationStatus", "JobStatus", "MediaType", "Platform", "ReportStatus",
    "ReportType", "Severity", "SourceType", "VideoStatus",
    # models
    "AdminUser", "User",
    "AccountMetrics", "AccountSettings", "DailyMetric", "DestinationAccount",
    "ContentSource", "RssFeed",
    "DiscoveredContent", "Video", "VideoHash",
    "TrendHistory", "TrendScore",
    "Caption", "CaptionTemplate", "ReelCover",
    "PublishingBatch", "PublishingHistory", "PublishingJob", "Schedule",
    "AnalyticsEvent", "Report",
    "AppSetting", "AuditLog", "AutomationLog", "ErrorLog",
]
