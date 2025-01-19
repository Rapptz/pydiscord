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

from typing import List, Literal, Optional, TypedDict
from typing_extensions import NotRequired, Required

from .automod import AutoModerationAction, AutoModerationRuleTriggerType
from .activity import PartialPresenceUpdate
from .sku import Entitlement
from .voice import GuildVoiceState
from .integration import BaseIntegration, IntegrationApplication
from .role import Role
from .channel import ChannelType, StageInstance, VoiceChannelEffect
from .interactions import Interaction
from .invite import InviteTargetType
from .emoji import Emoji, PartialEmoji
from .member import MemberWithUser
from .snowflake import Snowflake
from .message import Message, ReactionType
from .sticker import GuildSticker
from .appinfo import GatewayAppInfo, PartialAppInfo
from .guild import Guild, UnavailableGuild
from .user import User, AvatarDecorationData
from .threads import Thread, ThreadMember
from .scheduled_event import GuildScheduledEvent
from .audit_log import AuditLogEntry
from .soundboard import SoundboardSound
from .subscription import Subscription


class SessionStartLimit(TypedDict):
    total: int
    remaining: int
    reset_after: int
    max_concurrency: int


class Gateway(TypedDict):
    url: str


class GatewayBot(Gateway):
    shards: int
    session_start_limit: SessionStartLimit


class ReadyEvent(TypedDict):
    v: int
    user: User
    guilds: List[UnavailableGuild]
    session_id: str
    resume_gateway_url: str
    shard: List[int]  # shard_id, num_shards
    application: GatewayAppInfo


ResumedEvent = Literal[None]

MessageCreateEvent = Message


class MessageDeleteEvent(TypedDict):
    id: Snowflake
    channel_id: Snowflake
    guild_id: NotRequired[Snowflake]


class MessageDeleteBulkEvent(TypedDict):
    ids: List[Snowflake]
    channel_id: Snowflake
    guild_id: NotRequired[Snowflake]


MessageUpdateEvent = MessageCreateEvent


class MessageReactionAddEvent(TypedDict):
    user_id: Snowflake
    channel_id: Snowflake
    message_id: Snowflake
    emoji: PartialEmoji
    member: NotRequired[MemberWithUser]
    guild_id: NotRequired[Snowflake]
    message_author_id: NotRequired[Snowflake]
    burst: bool
    burst_colors: NotRequired[List[str]]
    type: ReactionType


class MessageReactionRemoveEvent(TypedDict):
    user_id: Snowflake
    channel_id: Snowflake
    message_id: Snowflake
    emoji: PartialEmoji
    guild_id: NotRequired[Snowflake]
    burst: bool
    type: ReactionType


class MessageReactionRemoveAllEvent(TypedDict):
    message_id: Snowflake
    channel_id: Snowflake
    guild_id: NotRequired[Snowflake]


class MessageReactionRemoveEmojiEvent(TypedDict):
    emoji: PartialEmoji
    message_id: Snowflake
    channel_id: Snowflake
    guild_id: NotRequired[Snowflake]


InteractionCreateEvent = Interaction


PresenceUpdateEvent = PartialPresenceUpdate


UserUpdateEvent = User


class InviteCreateEvent(TypedDict):
    channel_id: Snowflake
    code: str
    created_at: str
    max_age: int
    max_uses: int
    temporary: bool
    uses: Literal[0]
    guild_id: NotRequired[Snowflake]
    inviter: NotRequired[User]
    target_type: NotRequired[InviteTargetType]
    target_user: NotRequired[User]
    target_application: NotRequired[PartialAppInfo]


class InviteDeleteEvent(TypedDict):
    channel_id: Snowflake
    code: str
    guild_id: NotRequired[Snowflake]


class _ChannelEvent(TypedDict):
    id: Snowflake
    type: ChannelType


ChannelCreateEvent = ChannelUpdateEvent = ChannelDeleteEvent = _ChannelEvent


class ChannelPinsUpdateEvent(TypedDict):
    channel_id: Snowflake
    guild_id: NotRequired[Snowflake]
    last_pin_timestamp: NotRequired[Optional[str]]


class ThreadCreateEvent(Thread, total=False):
    newly_created: bool
    members: List[ThreadMember]


ThreadUpdateEvent = Thread


class ThreadDeleteEvent(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    parent_id: Snowflake
    type: ChannelType


class ThreadListSyncEvent(TypedDict):
    guild_id: Snowflake
    threads: List[Thread]
    members: List[ThreadMember]
    channel_ids: NotRequired[List[Snowflake]]


class ThreadMemberUpdate(ThreadMember):
    guild_id: Snowflake


class ThreadMembersUpdate(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    member_count: int
    added_members: NotRequired[List[ThreadMember]]
    removed_member_ids: NotRequired[List[Snowflake]]


class GuildMemberAddEvent(MemberWithUser):
    guild_id: Snowflake


class GuildMemberRemoveEvent(TypedDict):
    guild_id: Snowflake
    user: User


class GuildMemberUpdateEvent(TypedDict):
    guild_id: Snowflake
    roles: List[Snowflake]
    user: User
    avatar: Optional[str]
    joined_at: Optional[str]
    flags: int
    nick: NotRequired[str]
    premium_since: NotRequired[Optional[str]]
    deaf: NotRequired[bool]
    mute: NotRequired[bool]
    pending: NotRequired[bool]
    communication_disabled_until: NotRequired[str]
    avatar_decoration_data: NotRequired[AvatarDecorationData]


class GuildEmojisUpdateEvent(TypedDict):
    guild_id: Snowflake
    emojis: List[Emoji]


class GuildStickersUpdateEvent(TypedDict):
    guild_id: Snowflake
    stickers: List[GuildSticker]


GuildCreateEvent = GuildUpdateEvent = Guild
GuildDeleteEvent = UnavailableGuild


class _GuildBanEvent(TypedDict):
    guild_id: Snowflake
    user: User


GuildBanAddEvent = GuildBanRemoveEvent = _GuildBanEvent


class _GuildRoleEvent(TypedDict):
    guild_id: Snowflake
    role: Role


class GuildRoleDeleteEvent(TypedDict):
    guild_id: Snowflake
    role_id: Snowflake


GuildRoleCreateEvent = GuildRoleUpdateEvent = _GuildRoleEvent


class GuildMembersChunkEvent(TypedDict):
    guild_id: Snowflake
    members: List[MemberWithUser]
    chunk_index: int
    chunk_count: int
    not_found: NotRequired[List[Snowflake]]
    presences: NotRequired[List[PresenceUpdateEvent]]
    nonce: NotRequired[str]


class GuildIntegrationsUpdateEvent(TypedDict):
    guild_id: Snowflake


class _IntegrationEvent(BaseIntegration, total=False):
    guild_id: Required[Snowflake]
    role_id: Optional[Snowflake]
    enable_emoticons: bool
    subscriber_count: int
    revoked: bool
    application: IntegrationApplication


IntegrationCreateEvent = IntegrationUpdateEvent = _IntegrationEvent


class IntegrationDeleteEvent(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    application_id: NotRequired[Snowflake]


class WebhooksUpdateEvent(TypedDict):
    guild_id: Snowflake
    channel_id: Snowflake


StageInstanceCreateEvent = StageInstanceUpdateEvent = StageInstanceDeleteEvent = StageInstance

GuildScheduledEventCreateEvent = GuildScheduledEventUpdateEvent = GuildScheduledEventDeleteEvent = GuildScheduledEvent


class _GuildScheduledEventUsersEvent(TypedDict):
    guild_scheduled_event_id: Snowflake
    user_id: Snowflake
    guild_id: Snowflake


GuildScheduledEventUserAdd = GuildScheduledEventUserRemove = _GuildScheduledEventUsersEvent

VoiceStateUpdateEvent = GuildVoiceState
VoiceChannelEffectSendEvent = VoiceChannelEffect

GuildSoundBoardSoundCreateEvent = GuildSoundBoardSoundUpdateEvent = SoundboardSound


class GuildSoundBoardSoundsUpdateEvent(TypedDict):
    guild_id: Snowflake
    soundboard_sounds: List[SoundboardSound]


class GuildSoundBoardSoundDeleteEvent(TypedDict):
    sound_id: Snowflake
    guild_id: Snowflake


class VoiceServerUpdateEvent(TypedDict):
    token: str
    guild_id: Snowflake
    endpoint: Optional[str]


class TypingStartEvent(TypedDict):
    channel_id: Snowflake
    user_id: Snowflake
    timestamp: int
    guild_id: NotRequired[Snowflake]
    member: NotRequired[MemberWithUser]


class AutoModerationActionExecution(TypedDict):
    guild_id: Snowflake
    action: AutoModerationAction
    rule_id: Snowflake
    rule_trigger_type: AutoModerationRuleTriggerType
    user_id: Snowflake
    channel_id: NotRequired[Snowflake]
    message_id: NotRequired[Snowflake]
    alert_system_message_id: NotRequired[Snowflake]
    content: str
    matched_keyword: Optional[str]
    matched_content: Optional[str]


class GuildAuditLogEntryCreate(AuditLogEntry):
    guild_id: Snowflake


class VoiceChannelStatusUpdate(TypedDict):
    id: Snowflake
    guild_id: Snowflake
    status: Optional[str]


EntitlementCreateEvent = EntitlementUpdateEvent = EntitlementDeleteEvent = Entitlement


class PollVoteActionEvent(TypedDict):
    user_id: Snowflake
    channel_id: Snowflake
    message_id: Snowflake
    guild_id: NotRequired[Snowflake]
    answer_id: int


SubscriptionCreateEvent = SubscriptionUpdateEvent = SubscriptionDeleteEvent = Subscription
