"""
The MIT License (MIT)

Copyright (c) 2015-present Rapptz

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict, Union
from typing_extensions import NotRequired

from .webhook import Webhook
from .guild import MFALevel, VerificationLevel, ExplicitContentFilterLevel, DefaultMessageNotificationLevel
from .integration import IntegrationExpireBehavior, PartialIntegration
from .user import User
from .scheduled_event import EntityType, EventStatus, GuildScheduledEvent
from .snowflake import Snowflake
from .role import Role
from .channel import ChannelType, DefaultReaction, PrivacyLevel, VideoQualityMode, PermissionOverwrite, ForumTag
from .threads import Thread
from .command import ApplicationCommand, ApplicationCommandPermissions
from .automod import AutoModerationTriggerMetadata

AuditLogEvent = Literal[
    1,
    10,
    11,
    12,
    13,
    14,
    15,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    30,
    31,
    32,
    40,
    41,
    42,
    50,
    51,
    52,
    60,
    61,
    62,
    72,
    73,
    74,
    75,
    80,
    81,
    82,
    83,
    84,
    85,
    90,
    91,
    92,
    100,
    101,
    102,
    110,
    111,
    112,
    121,
    130,
    131,
    132,
    140,
    141,
    142,
    143,
    144,
    145,
    150,
    151,
    192,
    193,
]


class _AuditLogChange_Str(TypedDict):
    key: Literal[
        'name',
        'description',
        'preferred_locale',
        'vanity_url_code',
        'topic',
        'code',
        'allow',
        'deny',
        'permissions',
        'tags',
        'unicode_emoji',
        'emoji_name',
    ]
    new_value: str
    old_value: str


class _AuditLogChange_AssetHash(TypedDict):
    key: Literal['icon_hash', 'splash_hash', 'discovery_splash_hash', 'banner_hash', 'avatar_hash', 'asset']
    new_value: str
    old_value: str


class _AuditLogChange_Snowflake(TypedDict):
    key: Literal[
        'id',
        'owner_id',
        'afk_channel_id',
        'rules_channel_id',
        'public_updates_channel_id',
        'widget_channel_id',
        'system_channel_id',
        'application_id',
        'channel_id',
        'inviter_id',
        'guild_id',
        'user_id',
        'sound_id',
    ]
    new_value: Snowflake
    old_value: Snowflake


class _AuditLogChange_Bool(TypedDict):
    key: Literal[
        'widget_enabled',
        'nsfw',
        'hoist',
        'mentionable',
        'temporary',
        'deaf',
        'mute',
        'nick',
        'enabled_emoticons',
        'region',
        'rtc_region',
        'available',
        'archived',
        'locked',
    ]
    new_value: bool
    old_value: bool


class _AuditLogChange_Int(TypedDict):
    key: Literal[
        'afk_timeout',
        'prune_delete_days',
        'position',
        'bitrate',
        'rate_limit_per_user',
        'color',
        'max_uses',
        'max_age',
        'user_limit',
        'auto_archive_duration',
        'default_auto_archive_duration',
        'default_thread_rate_limit_per_user',
        'communication_disabled_until',
        'flags',
    ]
    new_value: int
    old_value: int


class _AuditLogChange_Float(TypedDict):
    key: Literal['volume']
    new_value: float
    old_value: float


class _AuditLogChange_ListRole(TypedDict):
    key: Literal['$add', '$remove']
    new_value: List[Role]
    old_value: List[Role]


class _AuditLogChange_MFALevel(TypedDict):
    key: Literal['mfa_level']
    new_value: MFALevel
    old_value: MFALevel


class _AuditLogChange_VerificationLevel(TypedDict):
    key: Literal['verification_level']
    new_value: VerificationLevel
    old_value: VerificationLevel


class _AuditLogChange_ExplicitContentFilter(TypedDict):
    key: Literal['explicit_content_filter']
    new_value: ExplicitContentFilterLevel
    old_value: ExplicitContentFilterLevel


class _AuditLogChange_DefaultMessageNotificationLevel(TypedDict):
    key: Literal['default_message_notifications']
    new_value: DefaultMessageNotificationLevel
    old_value: DefaultMessageNotificationLevel


class _AuditLogChange_ChannelType(TypedDict):
    key: Literal['type']
    new_value: ChannelType
    old_value: ChannelType


class _AuditLogChange_IntegrationExpireBehaviour(TypedDict):
    key: Literal['expire_behavior']
    new_value: IntegrationExpireBehavior
    old_value: IntegrationExpireBehavior


class _AuditLogChange_VideoQualityMode(TypedDict):
    key: Literal['video_quality_mode']
    new_value: VideoQualityMode
    old_value: VideoQualityMode


class _AuditLogChange_Overwrites(TypedDict):
    key: Literal['permission_overwrites']
    new_value: List[PermissionOverwrite]
    old_value: List[PermissionOverwrite]


class _AuditLogChange_PrivacyLevel(TypedDict):
    key: Literal['privacy_level']
    new_value: PrivacyLevel
    old_value: PrivacyLevel


class _AuditLogChange_Status(TypedDict):
    key: Literal['status']
    new_value: EventStatus
    old_value: EventStatus


class _AuditLogChange_EntityType(TypedDict):
    key: Literal['entity_type']
    new_value: EntityType
    old_value: EntityType


class _AuditLogChange_AppCommandPermissions(TypedDict):
    key: str
    new_value: ApplicationCommandPermissions
    old_value: ApplicationCommandPermissions


class _AuditLogChange_AppliedTags(TypedDict):
    key: Literal['applied_tags']
    new_value: List[Snowflake]
    old_value: List[Snowflake]


class _AuditLogChange_AvailableTags(TypedDict):
    key: Literal['available_tags']
    new_value: List[ForumTag]
    old_value: List[ForumTag]


class _AuditLogChange_DefaultReactionEmoji(TypedDict):
    key: Literal['default_reaction_emoji']
    new_value: Optional[DefaultReaction]
    old_value: Optional[DefaultReaction]


class _AuditLogChange_TriggerMetadata(TypedDict):
    key: Literal['trigger_metadata']
    new_value: Optional[AutoModerationTriggerMetadata]
    old_value: Optional[AutoModerationTriggerMetadata]


AuditLogChange = Union[
    _AuditLogChange_Str,
    _AuditLogChange_AssetHash,
    _AuditLogChange_Snowflake,
    _AuditLogChange_Int,
    _AuditLogChange_Float,
    _AuditLogChange_Bool,
    _AuditLogChange_ListRole,
    _AuditLogChange_MFALevel,
    _AuditLogChange_VerificationLevel,
    _AuditLogChange_ExplicitContentFilter,
    _AuditLogChange_DefaultMessageNotificationLevel,
    _AuditLogChange_ChannelType,
    _AuditLogChange_IntegrationExpireBehaviour,
    _AuditLogChange_VideoQualityMode,
    _AuditLogChange_Overwrites,
    _AuditLogChange_PrivacyLevel,
    _AuditLogChange_Status,
    _AuditLogChange_EntityType,
    _AuditLogChange_AppCommandPermissions,
    _AuditLogChange_AppliedTags,
    _AuditLogChange_AvailableTags,
    _AuditLogChange_DefaultReactionEmoji,
    _AuditLogChange_TriggerMetadata,
]


class AuditEntryInfo(TypedDict):
    delete_member_days: str
    members_removed: str
    channel_id: Snowflake
    message_id: Snowflake
    count: str
    id: Snowflake
    type: Literal['0', '1']
    role_name: str
    application_id: Snowflake
    guild_id: Snowflake
    auto_moderation_rule_name: str
    auto_moderation_rule_trigger_type: str
    integration_type: str


class AuditLogEntry(TypedDict):
    target_id: Optional[str]
    user_id: Optional[Snowflake]
    id: Snowflake
    action_type: AuditLogEvent
    changes: NotRequired[List[AuditLogChange]]
    options: NotRequired[AuditEntryInfo]
    reason: NotRequired[str]


class AuditLog(TypedDict):
    webhooks: List[Webhook]
    users: List[User]
    audit_log_entries: List[AuditLogEntry]
    integrations: List[PartialIntegration]
    threads: List[Thread]
    guild_scheduled_events: List[GuildScheduledEvent]
    application_commands: List[ApplicationCommand]
