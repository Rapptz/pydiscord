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

import copy
import datetime
import unicodedata
from typing import (
    Any,
    AsyncIterator,
    ClassVar,
    Collection,
    Coroutine,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    Sequence,
    Set,
    Literal,
    Optional,
    TYPE_CHECKING,
    Tuple,
    Union,
    overload,
)
import warnings

from . import utils, abc
from .role import Role
from .member import Member, VoiceState
from .emoji import Emoji
from .errors import InvalidData
from .permissions import PermissionOverwrite
from .colour import Colour
from .errors import ClientException
from .channel import *
from .channel import _guild_channel_factory
from .channel import _threaded_guild_channel_factory
from .enums import (
    AuditLogAction,
    VideoQualityMode,
    ChannelType,
    EntityType,
    PrivacyLevel,
    try_enum,
    VerificationLevel,
    ContentFilter,
    NotificationLevel,
    NSFWLevel,
    MFALevel,
    Locale,
    AutoModRuleEventType,
    ForumOrderType,
    ForumLayoutType,
)
from .mixins import Hashable
from .user import User
from .invite import Invite
from .widget import Widget
from .asset import Asset
from .flags import SystemChannelFlags
from .integrations import Integration, PartialIntegration, _integration_factory
from .scheduled_event import ScheduledEvent, ScheduledEventRecurrenceRule
from .stage_instance import StageInstance
from .threads import Thread, ThreadMember
from .sticker import GuildSticker
from .file import File
from .audit_logs import AuditLogEntry
from .object import OLDEST_OBJECT, Object
from .welcome_screen import WelcomeScreen, WelcomeChannel
from .automod import AutoModRule, AutoModTrigger, AutoModRuleAction
from .partial_emoji import _EmojiTag, PartialEmoji
from .soundboard import SoundboardSound
from .presences import RawPresenceUpdateEvent

__all__ = (
    'Guild',
    'GuildPreview',
    'BanEntry',
)

MISSING = utils.MISSING

if TYPE_CHECKING:
    from .abc import Snowflake, SnowflakeTime
    from .types.guild import (
        Ban as BanPayload,
        Guild as GuildPayload,
        GuildPreview as GuildPreviewPayload,
        RolePositionUpdate as RolePositionUpdatePayload,
        GuildFeature,
        IncidentData,
    )
    from .types.threads import (
        Thread as ThreadPayload,
    )
    from .types.voice import GuildVoiceState
    from .permissions import Permissions
    from .channel import VoiceChannel, StageChannel, TextChannel, ForumChannel, CategoryChannel
    from .template import Template
    from .webhook import Webhook
    from .state import ConnectionState
    from .voice_client import VoiceProtocol
    from .types.channel import (
        GuildChannel as GuildChannelPayload,
        TextChannel as TextChannelPayload,
        NewsChannel as NewsChannelPayload,
        VoiceChannel as VoiceChannelPayload,
        CategoryChannel as CategoryChannelPayload,
        StageChannel as StageChannelPayload,
        ForumChannel as ForumChannelPayload,
    )
    from .types.integration import IntegrationType
    from .types.snowflake import SnowflakeList
    from .types.widget import EditWidgetSettings
    from .types.audit_log import AuditLogEvent
    from .message import EmojiInputType

    VocalGuildChannel = Union[VoiceChannel, StageChannel]
    GuildChannel = Union[VocalGuildChannel, ForumChannel, TextChannel, CategoryChannel]
    ByCategoryItem = Tuple[Optional[CategoryChannel], List[GuildChannel]]


class BanEntry(NamedTuple):
    reason: Optional[str]
    user: User


class BulkBanResult(NamedTuple):
    banned: List[Object]
    failed: List[Object]


class _GuildLimit(NamedTuple):
    emoji: int
    stickers: int
    bitrate: float
    filesize: int


class GuildPreview(Hashable):
    """Represents a preview of a Discord guild.

        .. versionadded:: 2.5

    .. container:: operations

        .. describe:: x == y

            Checks if two guild previews are equal.

        .. describe:: x != y

            Checks if two guild previews are not equal.

        .. describe:: hash(x)

            Returns the guild's hash.

        .. describe:: str(x)

            Returns the guild's name.

    Attributes
    ----------
    name: :class:`str`
        The guild preview's name.
    id: :class:`int`
        The guild preview's ID.
    features: List[:class:`str`]
        A list of features the guild has. See :attr:`Guild.features` for more information.
    description: Optional[:class:`str`]
        The guild preview's description.
    emojis: Tuple[:class:`Emoji`, ...]
        All emojis that the guild owns.
    stickers: Tuple[:class:`GuildSticker`, ...]
        All stickers that the guild owns.
    approximate_member_count: :class:`int`
        The approximate number of members in the guild.
    approximate_presence_count: :class:`int`
        The approximate number of members currently active in in the guild. Offline members are excluded.
    """

    __slots__ = (
        '_state',
        '_icon',
        '_splash',
        '_discovery_splash',
        'id',
        'name',
        'emojis',
        'stickers',
        'features',
        'description',
        "approximate_member_count",
        "approximate_presence_count",
    )

    def __init__(self, *, data: GuildPreviewPayload, state: ConnectionState) -> None:
        self._state: ConnectionState = state
        self.id = int(data['id'])
        self.name: str = data['name']
        self._icon: Optional[str] = data.get('icon')
        self._splash: Optional[str] = data.get('splash')
        self._discovery_splash: Optional[str] = data.get('discovery_splash')
        self.emojis: Tuple[Emoji, ...] = tuple(
            map(
                lambda d: Emoji(guild=state._get_or_create_unavailable_guild(self.id), state=state, data=d),
                data.get('emojis', []),
            )
        )
        self.stickers: Tuple[GuildSticker, ...] = tuple(
            map(lambda d: GuildSticker(state=state, data=d), data.get('stickers', []))
        )
        self.features: List[GuildFeature] = data.get('features', [])
        self.description: Optional[str] = data.get('description')
        self.approximate_member_count: int = data.get('approximate_member_count')
        self.approximate_presence_count: int = data.get('approximate_presence_count')

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return (
            f'<{self.__class__.__name__} id={self.id} name={self.name!r} description={self.description!r} '
            f'features={self.features}>'
        )

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the guild's creation time in UTC."""
        return utils.snowflake_time(self.id)

    @property
    def icon(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's icon asset, if available."""
        if self._icon is None:
            return None
        return Asset._from_guild_icon(self._state, self.id, self._icon)

    @property
    def splash(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's invite splash asset, if available."""
        if self._splash is None:
            return None
        return Asset._from_guild_image(self._state, self.id, self._splash, path='splashes')

    @property
    def discovery_splash(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's discovery splash asset, if available."""
        if self._discovery_splash is None:
            return None
        return Asset._from_guild_image(self._state, self.id, self._discovery_splash, path='discovery-splashes')


class Guild(Hashable):
    """Represents a Discord guild.

    This is referred to as a "server" in the official Discord UI.

    .. container:: operations

        .. describe:: x == y

            Checks if two guilds are equal.

        .. describe:: x != y

            Checks if two guilds are not equal.

        .. describe:: hash(x)

            Returns the guild's hash.

        .. describe:: str(x)

            Returns the guild's name.

    Attributes
    ----------
    name: :class:`str`
        The guild name.
    emojis: Tuple[:class:`Emoji`, ...]
        All emojis that the guild owns.
    stickers: Tuple[:class:`GuildSticker`, ...]
        All stickers that the guild owns.

        .. versionadded:: 2.0
    afk_timeout: :class:`int`
        The number of seconds until someone is moved to the AFK channel.
    id: :class:`int`
        The guild's ID.
    owner_id: :class:`int`
        The guild owner's ID. Use :attr:`Guild.owner` instead.
    unavailable: :class:`bool`
        Indicates if the guild is unavailable. If this is ``True`` then the
        reliability of other attributes outside of :attr:`Guild.id` is slim and they might
        all be ``None``. It is best to not do anything with the guild if it is unavailable.

        Check the :func:`on_guild_unavailable` and :func:`on_guild_available` events.
    max_presences: Optional[:class:`int`]
        The maximum amount of presences for the guild.
    max_members: Optional[:class:`int`]
        The maximum amount of members for the guild.

        .. note::

            This attribute is only available via :meth:`.Client.fetch_guild`.
    max_video_channel_users: Optional[:class:`int`]
        The maximum amount of users in a video channel.

        .. versionadded:: 1.4
    description: Optional[:class:`str`]
        The guild's description.
    verification_level: :class:`VerificationLevel`
        The guild's verification level.
    vanity_url_code: Optional[:class:`str`]
        The guild's vanity url code, if any

        .. versionadded:: 2.0
    explicit_content_filter: :class:`ContentFilter`
        The guild's explicit content filter.
    default_notifications: :class:`NotificationLevel`
        The guild's notification settings.
    features: List[:class:`str`]
        A list of features that the guild has. The features that a guild can have are
        subject to arbitrary change by Discord. A list of guild features can be found
        in :ddocs:`the Discord documentation <resources/guild#guild-object-guild-features>`.

    premium_tier: :class:`int`
        The premium tier for this guild. Corresponds to "Nitro Server" in the official UI.
        The number goes from 0 to 3 inclusive.
    premium_subscription_count: :class:`int`
        The number of "boosts" this guild currently has.
    preferred_locale: :class:`Locale`
        The preferred locale for the guild. Used when filtering Server Discovery
        results to a specific language.

        .. versionchanged:: 2.0
            This field is now an enum instead of a :class:`str`.
    nsfw_level: :class:`NSFWLevel`
        The guild's NSFW level.

        .. versionadded:: 2.0
    mfa_level: :class:`MFALevel`
        The guild's Multi-Factor Authentication requirement level.

        .. versionchanged:: 2.0
            This field is now an enum instead of an :class:`int`.

    approximate_member_count: Optional[:class:`int`]
        The approximate number of members in the guild. This is ``None`` unless the guild is obtained
        using :meth:`Client.fetch_guild` or :meth:`Client.fetch_guilds` with ``with_counts=True``.

        .. versionadded:: 2.0
    approximate_presence_count: Optional[:class:`int`]
        The approximate number of members currently active in the guild.
        Offline members are excluded. This is ``None`` unless the guild is obtained using
        :meth:`Client.fetch_guild` or :meth:`Client.fetch_guilds` with ``with_counts=True``.

        .. versionchanged:: 2.0
    premium_progress_bar_enabled: :class:`bool`
        Indicates if the guild has premium AKA server boost level progress bar enabled.

        .. versionadded:: 2.0
    widget_enabled: :class:`bool`
        Indicates if the guild has widget enabled.

        .. versionadded:: 2.0
    max_stage_video_users: Optional[:class:`int`]
        The maximum amount of users in a stage video channel.

        .. versionadded:: 2.3
    """

    __slots__ = (
        'afk_timeout',
        'name',
        'id',
        'unavailable',
        'owner_id',
        'emojis',
        'stickers',
        'features',
        'verification_level',
        'explicit_content_filter',
        'default_notifications',
        'description',
        'max_presences',
        'max_members',
        'max_video_channel_users',
        'premium_tier',
        'premium_subscription_count',
        'preferred_locale',
        'nsfw_level',
        'mfa_level',
        'vanity_url_code',
        'widget_enabled',
        '_widget_channel_id',
        '_afk_channel_id',
        '_members',
        '_channels',
        '_icon',
        '_banner',
        '_state',
        '_roles',
        '_member_count',
        '_large',
        '_splash',
        '_voice_states',
        '_system_channel_id',
        '_system_channel_flags',
        '_discovery_splash',
        '_rules_channel_id',
        '_public_updates_channel_id',
        '_stage_instances',
        '_scheduled_events',
        '_threads',
        'approximate_member_count',
        'approximate_presence_count',
        'premium_progress_bar_enabled',
        '_safety_alerts_channel_id',
        'max_stage_video_users',
        '_incidents_data',
        '_soundboard_sounds',
    )

    _PREMIUM_GUILD_LIMITS: ClassVar[Dict[Optional[int], _GuildLimit]] = {
        None: _GuildLimit(emoji=50, stickers=5, bitrate=96e3, filesize=utils.DEFAULT_FILE_SIZE_LIMIT_BYTES),
        0: _GuildLimit(emoji=50, stickers=5, bitrate=96e3, filesize=utils.DEFAULT_FILE_SIZE_LIMIT_BYTES),
        1: _GuildLimit(emoji=100, stickers=15, bitrate=128e3, filesize=utils.DEFAULT_FILE_SIZE_LIMIT_BYTES),
        2: _GuildLimit(emoji=150, stickers=30, bitrate=256e3, filesize=52428800),
        3: _GuildLimit(emoji=250, stickers=60, bitrate=384e3, filesize=104857600),
    }

    def __init__(self, *, data: GuildPayload, state: ConnectionState) -> None:
        self._channels: Dict[int, GuildChannel] = {}
        self._members: Dict[int, Member] = {}
        self._voice_states: Dict[int, VoiceState] = {}
        self._threads: Dict[int, Thread] = {}
        self._stage_instances: Dict[int, StageInstance] = {}
        self._scheduled_events: Dict[int, ScheduledEvent] = {}
        self._soundboard_sounds: Dict[int, SoundboardSound] = {}
        self._state: ConnectionState = state
        self._member_count: Optional[int] = None
        self._from_data(data)

    def _add_channel(self, channel: GuildChannel, /) -> None:
        self._channels[channel.id] = channel

    def _remove_channel(self, channel: Snowflake, /) -> None:
        self._channels.pop(channel.id, None)

    def _voice_state_for(self, user_id: int, /) -> Optional[VoiceState]:
        return self._voice_states.get(user_id)

    def _add_member(self, member: Member, /) -> None:
        self._members[member.id] = member

    def _store_thread(self, payload: ThreadPayload, /) -> Thread:
        thread = Thread(guild=self, state=self._state, data=payload)
        self._threads[thread.id] = thread
        return thread

    def _remove_member(self, member: Snowflake, /) -> None:
        self._members.pop(member.id, None)

    def _add_thread(self, thread: Thread, /) -> None:
        self._threads[thread.id] = thread

    def _remove_thread(self, thread: Snowflake, /) -> None:
        self._threads.pop(thread.id, None)

    def _clear_threads(self) -> None:
        self._threads.clear()

    def _remove_threads_by_channel(self, channel_id: int) -> List[Thread]:
        to_remove = [t for t in self._threads.values() if t.parent_id == channel_id]
        for thread in to_remove:
            del self._threads[thread.id]
        return to_remove

    def _filter_threads(self, channel_ids: Set[int]) -> Dict[int, Thread]:
        to_remove: Dict[int, Thread] = {k: t for k, t in self._threads.items() if t.parent_id in channel_ids}
        for k in to_remove:
            del self._threads[k]
        return to_remove

    def _add_soundboard_sound(self, sound: SoundboardSound, /) -> None:
        self._soundboard_sounds[sound.id] = sound

    def _remove_soundboard_sound(self, sound: SoundboardSound, /) -> None:
        self._soundboard_sounds.pop(sound.id, None)

    def __str__(self) -> str:
        return self.name or ''

    def __repr__(self) -> str:
        attrs = (
            ('id', self.id),
            ('name', self.name),
            ('shard_id', self.shard_id),
            ('chunked', self.chunked),
            ('member_count', self._member_count),
        )
        inner = ' '.join('%s=%r' % t for t in attrs)
        return f'<Guild {inner}>'

    def _update_voice_state(self, data: GuildVoiceState, channel_id: int) -> Tuple[Optional[Member], VoiceState, VoiceState]:
        user_id = int(data['user_id'])
        channel: Optional[VocalGuildChannel] = self.get_channel(channel_id)  # type: ignore # this will always be a voice channel
        try:
            # check if we should remove the voice state from cache
            if channel is None:
                after = self._voice_states.pop(user_id)
            else:
                after = self._voice_states[user_id]

            before = copy.copy(after)
            after._update(data, channel)
        except KeyError:
            # if we're here then we're getting added into the cache
            after = VoiceState(data=data, channel=channel)
            before = VoiceState(data=data, channel=None)
            self._voice_states[user_id] = after

        member = self.get_member(user_id)
        if member is None:
            try:
                member = Member(data=data['member'], state=self._state, guild=self)
            except KeyError:
                member = None

        return member, before, after

    def _add_role(self, role: Role, /) -> None:
        self._roles[role.id] = role

    def _remove_role(self, role_id: int, /) -> Role:
        # this raises KeyError if it fails..
        return self._roles.pop(role_id)

    @classmethod
    def _create_unavailable(cls, *, state: ConnectionState, guild_id: int, data: Optional[Dict[str, Any]]) -> Guild:
        if data is None:
            data = {'unavailable': True}
        data.update(id=guild_id)
        return cls(state=state, data=data)  # type: ignore

    def _from_data(self, guild: GuildPayload) -> None:
        try:
            self._member_count = guild['member_count']
        except KeyError:
            pass

        self.name: str = guild.get('name', '')
        self.verification_level: VerificationLevel = try_enum(VerificationLevel, guild.get('verification_level'))
        self.default_notifications: NotificationLevel = try_enum(
            NotificationLevel, guild.get('default_message_notifications')
        )
        self.explicit_content_filter: ContentFilter = try_enum(ContentFilter, guild.get('explicit_content_filter', 0))
        self.afk_timeout: int = guild.get('afk_timeout', 0)
        self._icon: Optional[str] = guild.get('icon')
        self._banner: Optional[str] = guild.get('banner')
        self.unavailable: bool = guild.get('unavailable', False)
        self.id: int = int(guild['id'])
        self._roles: Dict[int, Role] = {}
        state = self._state  # speed up attribute access
        for r in guild.get('roles', []):
            role = Role(guild=self, data=r, state=state)
            self._roles[role.id] = role

        self.emojis: Tuple[Emoji, ...] = (
            tuple(map(lambda d: state.store_emoji(self, d), guild.get('emojis', [])))
            if state.cache_guild_expressions
            else ()
        )
        self.stickers: Tuple[GuildSticker, ...] = (
            tuple(map(lambda d: state.store_sticker(self, d), guild.get('stickers', [])))
            if state.cache_guild_expressions
            else ()
        )
        self.features: List[GuildFeature] = guild.get('features', [])
        self._splash: Optional[str] = guild.get('splash')
        self._system_channel_id: Optional[int] = utils._get_as_snowflake(guild, 'system_channel_id')
        self.description: Optional[str] = guild.get('description')
        self.max_presences: Optional[int] = guild.get('max_presences')
        self.max_members: Optional[int] = guild.get('max_members')
        self.max_video_channel_users: Optional[int] = guild.get('max_video_channel_users')
        self.max_stage_video_users: Optional[int] = guild.get('max_stage_video_channel_users')
        self.premium_tier: int = guild.get('premium_tier', 0)
        self.premium_subscription_count: int = guild.get('premium_subscription_count') or 0
        self.vanity_url_code: Optional[str] = guild.get('vanity_url_code')
        self.widget_enabled: bool = guild.get('widget_enabled', False)
        self._widget_channel_id: Optional[int] = utils._get_as_snowflake(guild, 'widget_channel_id')
        self._system_channel_flags: int = guild.get('system_channel_flags', 0)
        self.preferred_locale: Locale = try_enum(Locale, guild.get('preferred_locale', 'en-US'))
        self._discovery_splash: Optional[str] = guild.get('discovery_splash')
        self._rules_channel_id: Optional[int] = utils._get_as_snowflake(guild, 'rules_channel_id')
        self._public_updates_channel_id: Optional[int] = utils._get_as_snowflake(guild, 'public_updates_channel_id')
        self._safety_alerts_channel_id: Optional[int] = utils._get_as_snowflake(guild, 'safety_alerts_channel_id')
        self.nsfw_level: NSFWLevel = try_enum(NSFWLevel, guild.get('nsfw_level', 0))
        self.mfa_level: MFALevel = try_enum(MFALevel, guild.get('mfa_level', 0))
        self.approximate_presence_count: Optional[int] = guild.get('approximate_presence_count')
        self.approximate_member_count: Optional[int] = guild.get('approximate_member_count')
        self.premium_progress_bar_enabled: bool = guild.get('premium_progress_bar_enabled', False)
        self.owner_id: Optional[int] = utils._get_as_snowflake(guild, 'owner_id')
        self._large: Optional[bool] = None if self._member_count is None else self._member_count >= 250
        self._afk_channel_id: Optional[int] = utils._get_as_snowflake(guild, 'afk_channel_id')
        self._incidents_data: Optional[IncidentData] = guild.get('incidents_data')

        if 'channels' in guild:
            channels = guild['channels']
            for c in channels:
                factory, ch_type = _guild_channel_factory(c['type'])
                if factory:
                    self._add_channel(factory(guild=self, data=c, state=self._state))  # type: ignore

        for obj in guild.get('voice_states', []):
            self._update_voice_state(obj, int(obj['channel_id']))

        cache_joined = self._state.member_cache_flags.joined
        cache_voice = self._state.member_cache_flags.voice
        self_id = self._state.self_id
        for mdata in guild.get('members', []):
            member = Member(data=mdata, guild=self, state=self._state)  # type: ignore # Members will have the 'user' key in this scenario
            if cache_joined or member.id == self_id or (cache_voice and member.id in self._voice_states):
                self._add_member(member)

        empty_tuple = ()
        for presence in guild.get('presences', []):
            raw_presence = RawPresenceUpdateEvent(data=presence, state=self._state)
            member = self.get_member(raw_presence.user_id)

            if member is not None:
                member._presence_update(raw_presence, empty_tuple)  # type: ignore

        if 'threads' in guild:
            threads = guild['threads']
            for thread in threads:
                self._add_thread(Thread(guild=self, state=self._state, data=thread))

        if 'stage_instances' in guild:
            for s in guild['stage_instances']:
                stage_instance = StageInstance(guild=self, data=s, state=self._state)
                self._stage_instances[stage_instance.id] = stage_instance

        if 'guild_scheduled_events' in guild:
            for s in guild['guild_scheduled_events']:
                scheduled_event = ScheduledEvent(data=s, state=self._state)
                self._scheduled_events[scheduled_event.id] = scheduled_event

        if 'soundboard_sounds' in guild:
            for s in guild['soundboard_sounds']:
                soundboard_sound = SoundboardSound(guild=self, data=s, state=self._state)
                self._add_soundboard_sound(soundboard_sound)

    @property
    def channels(self) -> Sequence[GuildChannel]:
        """Sequence[:class:`abc.GuildChannel`]: A list of channels that belongs to this guild."""
        return utils.SequenceProxy(self._channels.values())

    @property
    def threads(self) -> Sequence[Thread]:
        """Sequence[:class:`Thread`]: A list of threads that you have permission to view.

        .. versionadded:: 2.0
        """
        return utils.SequenceProxy(self._threads.values())

    @property
    def large(self) -> bool:
        """:class:`bool`: Indicates if the guild is a 'large' guild.

        A large guild is defined as having more than ``large_threshold`` count
        members, which for this library is set to the maximum of 250.
        """
        if self._large is None:
            if self._member_count is not None:
                return self._member_count >= 250
            return len(self._members) >= 250
        return self._large

    @property
    def voice_channels(self) -> List[VoiceChannel]:
        """List[:class:`VoiceChannel`]: A list of voice channels that belongs to this guild.

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, VoiceChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def stage_channels(self) -> List[StageChannel]:
        """List[:class:`StageChannel`]: A list of stage channels that belongs to this guild.

        .. versionadded:: 1.7

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, StageChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def me(self) -> Member:
        """:class:`Member`: Similar to :attr:`Client.user` except an instance of :class:`Member`.
        This is essentially used to get the member version of yourself.
        """
        self_id = self._state.user.id  # type: ignore # state.user won't be None if we're logged in
        # The self member is *always* cached
        return self.get_member(self_id)  # type: ignore

    @property
    def voice_client(self) -> Optional[VoiceProtocol]:
        """Optional[:class:`VoiceProtocol`]: Returns the :class:`VoiceProtocol` associated with this guild, if any."""
        return self._state._get_voice_client(self.id)

    @property
    def text_channels(self) -> List[TextChannel]:
        """List[:class:`TextChannel`]: A list of text channels that belongs to this guild.

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, TextChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def categories(self) -> List[CategoryChannel]:
        """List[:class:`CategoryChannel`]: A list of categories that belongs to this guild.

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, CategoryChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    @property
    def forums(self) -> List[ForumChannel]:
        """List[:class:`ForumChannel`]: A list of forum channels that belongs to this guild.

        This is sorted by the position and are in UI order from top to bottom.
        """
        r = [ch for ch in self._channels.values() if isinstance(ch, ForumChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    def by_category(self) -> List[ByCategoryItem]:
        """Returns every :class:`CategoryChannel` and their associated channels.

        These channels and categories are sorted in the official Discord UI order.

        If the channels do not have a category, then the first element of the tuple is
        ``None``.

        Returns
        --------
        List[Tuple[Optional[:class:`CategoryChannel`], List[:class:`abc.GuildChannel`]]]:
            The categories and their associated channels.
        """
        grouped: Dict[Optional[int], List[GuildChannel]] = {}
        for channel in self._channels.values():
            if isinstance(channel, CategoryChannel):
                grouped.setdefault(channel.id, [])
                continue

            try:
                grouped[channel.category_id].append(channel)
            except KeyError:
                grouped[channel.category_id] = [channel]

        def key(t: ByCategoryItem) -> Tuple[Tuple[int, int], List[GuildChannel]]:
            k, v = t
            return ((k.position, k.id) if k else (-1, -1), v)

        _get = self._channels.get
        as_list: List[ByCategoryItem] = [(_get(k), v) for k, v in grouped.items()]  # type: ignore
        as_list.sort(key=key)
        for _, channels in as_list:
            channels.sort(key=lambda c: (c._sorting_bucket, c.position, c.id))
        return as_list

    def _resolve_channel(self, id: Optional[int], /) -> Optional[Union[GuildChannel, Thread]]:
        if id is None:
            return

        return self._channels.get(id) or self._threads.get(id)

    def get_channel_or_thread(self, channel_id: int, /) -> Optional[Union[Thread, GuildChannel]]:
        """Returns a channel or thread with the given ID.

        .. versionadded:: 2.0

        Parameters
        -----------
        channel_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[Union[:class:`Thread`, :class:`.abc.GuildChannel`]]
            The returned channel or thread or ``None`` if not found.
        """
        return self._channels.get(channel_id) or self._threads.get(channel_id)

    def get_channel(self, channel_id: int, /) -> Optional[GuildChannel]:
        """Returns a channel with the given ID.

        .. note::

            This does *not* search for threads.

        .. versionchanged:: 2.0

            ``channel_id`` parameter is now positional-only.

        Parameters
        -----------
        channel_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`.abc.GuildChannel`]
            The returned channel or ``None`` if not found.
        """
        return self._channels.get(channel_id)

    def get_thread(self, thread_id: int, /) -> Optional[Thread]:
        """Returns a thread with the given ID.

        .. note::

            This does not always retrieve archived threads, as they are not retained in the internal
            cache. Use :func:`fetch_channel` instead.

        .. versionadded:: 2.0

        Parameters
        -----------
        thread_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`Thread`]
            The returned thread or ``None`` if not found.
        """
        return self._threads.get(thread_id)

    def get_emoji(self, emoji_id: int, /) -> Optional[Emoji]:
        """Returns an emoji with the given ID.

        .. versionadded:: 2.3

        Parameters
        ----------
        emoji_id: int
            The ID to search for.

        Returns
        --------
        Optional[:class:`Emoji`]
            The returned Emoji or ``None`` if not found.
        """
        emoji = self._state.get_emoji(emoji_id)
        if emoji and emoji.guild == self:
            return emoji
        return None

    @property
    def afk_channel(self) -> Optional[VocalGuildChannel]:
        """Optional[Union[:class:`VoiceChannel`, :class:`StageChannel`]]: The channel that denotes the AFK channel.

        If no channel is set, then this returns ``None``.
        """
        return self.get_channel(self._afk_channel_id)  # type: ignore

    @property
    def system_channel(self) -> Optional[TextChannel]:
        """Optional[:class:`TextChannel`]: Returns the guild's channel used for system messages.

        If no channel is set, then this returns ``None``.
        """
        channel_id = self._system_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def system_channel_flags(self) -> SystemChannelFlags:
        """:class:`SystemChannelFlags`: Returns the guild's system channel settings."""
        return SystemChannelFlags._from_value(self._system_channel_flags)

    @property
    def rules_channel(self) -> Optional[TextChannel]:
        """Optional[:class:`TextChannel`]: Return's the guild's channel used for the rules.
        The guild must be a Community guild.

        If no channel is set, then this returns ``None``.

        .. versionadded:: 1.3
        """
        channel_id = self._rules_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def public_updates_channel(self) -> Optional[TextChannel]:
        """Optional[:class:`TextChannel`]: Return's the guild's channel where admins and
        moderators of the guilds receive notices from Discord. The guild must be a
        Community guild.

        If no channel is set, then this returns ``None``.

        .. versionadded:: 1.4
        """
        channel_id = self._public_updates_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def safety_alerts_channel(self) -> Optional[TextChannel]:
        """Optional[:class:`TextChannel`]: Return's the guild's channel used for safety alerts, if set.

        For example, this is used for the raid protection setting. The guild must have the ``COMMUNITY`` feature.

        .. versionadded:: 2.3
        """
        channel_id = self._safety_alerts_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def widget_channel(self) -> Optional[Union[TextChannel, ForumChannel, VoiceChannel, StageChannel]]:
        """Optional[Union[:class:`TextChannel`, :class:`ForumChannel`, :class:`VoiceChannel`, :class:`StageChannel`]]: Returns
        the widget channel of the guild.

        If no channel is set, then this returns ``None``.

        .. versionadded:: 2.3
        """
        channel_id = self._widget_channel_id
        return channel_id and self._channels.get(channel_id)  # type: ignore

    @property
    def emoji_limit(self) -> int:
        """:class:`int`: The maximum number of emoji slots this guild has."""
        more_emoji = 200 if 'MORE_EMOJI' in self.features else 50
        return max(more_emoji, self._PREMIUM_GUILD_LIMITS[self.premium_tier].emoji)

    @property
    def sticker_limit(self) -> int:
        """:class:`int`: The maximum number of sticker slots this guild has.

        .. versionadded:: 2.0
        """
        more_stickers = 60 if 'MORE_STICKERS' in self.features else 0
        return max(more_stickers, self._PREMIUM_GUILD_LIMITS[self.premium_tier].stickers)

    @property
    def bitrate_limit(self) -> float:
        """:class:`float`: The maximum bitrate for voice channels this guild can have."""
        vip_guild = self._PREMIUM_GUILD_LIMITS[1].bitrate if 'VIP_REGIONS' in self.features else 96e3
        return max(vip_guild, self._PREMIUM_GUILD_LIMITS[self.premium_tier].bitrate)

    @property
    def filesize_limit(self) -> int:
        """:class:`int`: The maximum number of bytes files can have when uploaded to this guild."""
        return self._PREMIUM_GUILD_LIMITS[self.premium_tier].filesize

    @property
    def members(self) -> Sequence[Member]:
        """Sequence[:class:`Member`]: A list of members that belong to this guild."""
        return utils.SequenceProxy(self._members.values())

    def get_member(self, user_id: int, /) -> Optional[Member]:
        """Returns a member with the given ID.

        .. versionchanged:: 2.0

            ``user_id`` parameter is now positional-only.

        Parameters
        -----------
        user_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`Member`]
            The member or ``None`` if not found.
        """
        return self._members.get(user_id)

    @property
    def premium_subscribers(self) -> List[Member]:
        """List[:class:`Member`]: A list of members who have "boosted" this guild."""
        return [member for member in self.members if member.premium_since is not None]

    @property
    def roles(self) -> Sequence[Role]:
        """Sequence[:class:`Role`]: Returns a sequence of the guild's roles in hierarchy order.

        The first element of this sequence will be the lowest role in the
        hierarchy.
        """
        return utils.SequenceProxy(self._roles.values(), sorted=True)

    def get_role(self, role_id: int, /) -> Optional[Role]:
        """Returns a role with the given ID.

        .. versionchanged:: 2.0

            ``role_id`` parameter is now positional-only.

        Parameters
        -----------
        role_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`Role`]
            The role or ``None`` if not found.
        """
        return self._roles.get(role_id)

    @property
    def default_role(self) -> Role:
        """:class:`Role`: Gets the @everyone role that all members have by default."""
        # The @everyone role is *always* given
        return self.get_role(self.id)  # type: ignore

    @property
    def premium_subscriber_role(self) -> Optional[Role]:
        """Optional[:class:`Role`]: Gets the premium subscriber role, AKA "boost" role, in this guild.

        .. versionadded:: 1.6
        """
        for role in self._roles.values():
            if role.is_premium_subscriber():
                return role
        return None

    @property
    def self_role(self) -> Optional[Role]:
        """Optional[:class:`Role`]: Gets the role associated with this client's user, if any.

        .. versionadded:: 1.6
        """
        self_id = self._state.self_id
        for role in self._roles.values():
            tags = role.tags
            if tags and tags.bot_id == self_id:
                return role
        return None

    @property
    def stage_instances(self) -> Sequence[StageInstance]:
        """Sequence[:class:`StageInstance`]: Returns a sequence of the guild's stage instances that
        are currently running.

        .. versionadded:: 2.0
        """
        return utils.SequenceProxy(self._stage_instances.values())

    def get_stage_instance(self, stage_instance_id: int, /) -> Optional[StageInstance]:
        """Returns a stage instance with the given ID.

        .. versionadded:: 2.0

        Parameters
        -----------
        stage_instance_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`StageInstance`]
            The stage instance or ``None`` if not found.
        """
        return self._stage_instances.get(stage_instance_id)

    @property
    def scheduled_events(self) -> Sequence[ScheduledEvent]:
        """Sequence[:class:`ScheduledEvent`]: Returns a sequence of the guild's scheduled events.

        .. versionadded:: 2.0
        """
        return utils.SequenceProxy(self._scheduled_events.values())

    def get_scheduled_event(self, scheduled_event_id: int, /) -> Optional[ScheduledEvent]:
        """Returns a scheduled event with the given ID.

        .. versionadded:: 2.0

        Parameters
        -----------
        scheduled_event_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`ScheduledEvent`]
            The scheduled event or ``None`` if not found.
        """
        return self._scheduled_events.get(scheduled_event_id)

    @property
    def soundboard_sounds(self) -> Sequence[SoundboardSound]:
        """Sequence[:class:`SoundboardSound`]: Returns a sequence of the guild's soundboard sounds.

        .. versionadded:: 2.5
        """
        return utils.SequenceProxy(self._soundboard_sounds.values())

    def get_soundboard_sound(self, sound_id: int, /) -> Optional[SoundboardSound]:
        """Returns a soundboard sound with the given ID.

        .. versionadded:: 2.5

        Parameters
        -----------
        sound_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`SoundboardSound`]
            The soundboard sound or ``None`` if not found.
        """
        return self._soundboard_sounds.get(sound_id)

    def _resolve_soundboard_sound(self, id: Optional[int], /) -> Optional[SoundboardSound]:
        if id is None:
            return

        return self._soundboard_sounds.get(id)

    @property
    def owner(self) -> Optional[Member]:
        """Optional[:class:`Member`]: The member that owns the guild."""
        return self.get_member(self.owner_id)  # type: ignore

    @property
    def icon(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's icon asset, if available."""
        if self._icon is None:
            return None
        return Asset._from_guild_icon(self._state, self.id, self._icon)

    @property
    def banner(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's banner asset, if available."""
        if self._banner is None:
            return None
        return Asset._from_guild_image(self._state, self.id, self._banner, path='banners')

    @property
    def splash(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's invite splash asset, if available."""
        if self._splash is None:
            return None
        return Asset._from_guild_image(self._state, self.id, self._splash, path='splashes')

    @property
    def discovery_splash(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's discovery splash asset, if available."""
        if self._discovery_splash is None:
            return None
        return Asset._from_guild_image(self._state, self.id, self._discovery_splash, path='discovery-splashes')

    @property
    def member_count(self) -> Optional[int]:
        """Optional[:class:`int`]: Returns the member count if available.

        .. warning::

            Due to a Discord limitation, in order for this attribute to remain up-to-date and
            accurate, it requires :attr:`Intents.members` to be specified.

        .. versionchanged:: 2.0

            Now returns an ``Optional[int]``.
        """
        return self._member_count

    @property
    def chunked(self) -> bool:
        """:class:`bool`: Returns a boolean indicating if the guild is "chunked".

        A chunked guild means that :attr:`member_count` is equal to the
        number of members stored in the internal :attr:`members` cache.

        If this value returns ``False``, then you should request for
        offline members.
        """
        count = self._member_count
        if count is None:
            return False
        return count == len(self._members)

    @property
    def shard_id(self) -> int:
        """:class:`int`: Returns the shard ID for this guild if applicable."""
        count = self._state.shard_count
        if count is None:
            return 0
        return (self.id >> 22) % count

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the guild's creation time in UTC."""
        return utils.snowflake_time(self.id)

    def get_member_named(self, name: str, /) -> Optional[Member]:
        """Returns the first member found that matches the name provided.

        The name is looked up in the following order:

        - Username#Discriminator (deprecated)
        - Username#0 (deprecated, only gets users that migrated from their discriminator)
        - Nickname
        - Global name
        - Username

        If no member is found, ``None`` is returned.

        .. versionchanged:: 2.0

            ``name`` parameter is now positional-only.

        .. deprecated:: 2.3

            Looking up users via discriminator due to Discord API change.

        Parameters
        -----------
        name: :class:`str`
            The name of the member to lookup.

        Returns
        --------
        Optional[:class:`Member`]
            The member in this guild with the associated name. If not found
            then ``None`` is returned.
        """

        members = self.members

        username, _, discriminator = name.rpartition('#')

        # If # isn't found then "discriminator" actually has the username
        if not username:
            discriminator, username = username, discriminator

        if discriminator == '0' or (len(discriminator) == 4 and discriminator.isdigit()):
            return utils.find(lambda m: m.name == username and m.discriminator == discriminator, members)

        def pred(m: Member) -> bool:
            return m.nick == name or m.global_name == name or m.name == name

        return utils.find(pred, members)

    @overload
    def _create_channel(
        self,
        name: str,
        channel_type: Literal[ChannelType.text],
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = ...,
        category: Optional[Snowflake] = ...,
        **options: Any,
    ) -> Coroutine[Any, Any, TextChannelPayload]:
        ...

    @overload
    def _create_channel(
        self,
        name: str,
        channel_type: Literal[ChannelType.voice],
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = ...,
        category: Optional[Snowflake] = ...,
        **options: Any,
    ) -> Coroutine[Any, Any, VoiceChannelPayload]:
        ...

    @overload
    def _create_channel(
        self,
        name: str,
        channel_type: Literal[ChannelType.stage_voice],
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = ...,
        category: Optional[Snowflake] = ...,
        **options: Any,
    ) -> Coroutine[Any, Any, StageChannelPayload]:
        ...

    @overload
    def _create_channel(
        self,
        name: str,
        channel_type: Literal[ChannelType.category],
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = ...,
        category: Optional[Snowflake] = ...,
        **options: Any,
    ) -> Coroutine[Any, Any, CategoryChannelPayload]:
        ...

    @overload
    def _create_channel(
        self,
        name: str,
        channel_type: Literal[ChannelType.news],
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = ...,
        category: Optional[Snowflake] = ...,
        **options: Any,
    ) -> Coroutine[Any, Any, NewsChannelPayload]:
        ...

    @overload
    def _create_channel(
        self,
        name: str,
        channel_type: Literal[ChannelType.news, ChannelType.text],
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = ...,
        category: Optional[Snowflake] = ...,
        **options: Any,
    ) -> Coroutine[Any, Any, Union[TextChannelPayload, NewsChannelPayload]]:
        ...

    @overload
    def _create_channel(
        self,
        name: str,
        channel_type: Literal[ChannelType.forum],
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = ...,
        category: Optional[Snowflake] = ...,
        **options: Any,
    ) -> Coroutine[Any, Any, ForumChannelPayload]:
        ...

    @overload
    def _create_channel(
        self,
        name: str,
        channel_type: ChannelType,
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = ...,
        category: Optional[Snowflake] = ...,
        **options: Any,
    ) -> Coroutine[Any, Any, GuildChannelPayload]:
        ...

    def _create_channel(
        self,
        name: str,
        channel_type: ChannelType,
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = MISSING,
        category: Optional[Snowflake] = None,
        **options: Any,
    ) -> Coroutine[Any, Any, GuildChannelPayload]:
        if overwrites is MISSING:
            overwrites = {}
        elif not isinstance(overwrites, Mapping):
            raise TypeError('overwrites parameter expects a dict.')

        perms = []
        for target, perm in overwrites.items():
            if not isinstance(perm, PermissionOverwrite):
                raise TypeError(f'Expected PermissionOverwrite received {perm.__class__.__name__}')

            allow, deny = perm.pair()
            payload = {'allow': allow.value, 'deny': deny.value, 'id': target.id}

            if isinstance(target, Role):
                payload['type'] = abc._Overwrites.ROLE
            else:
                payload['type'] = abc._Overwrites.MEMBER

            perms.append(payload)

        parent_id = category.id if category else None
        return self._state.http.create_channel(
            self.id, channel_type.value, name=name, parent_id=parent_id, permission_overwrites=perms, **options
        )

    async def create_text_channel(
        self,
        name: str,
        *,
        reason: Optional[str] = None,
        category: Optional[CategoryChannel] = None,
        news: bool = False,
        position: int = MISSING,
        topic: str = MISSING,
        slowmode_delay: int = MISSING,
        nsfw: bool = MISSING,
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = MISSING,
        default_auto_archive_duration: int = MISSING,
        default_thread_slowmode_delay: int = MISSING,
    ) -> TextChannel:
        """|coro|

        Creates a :class:`TextChannel` for the guild.

        Note that you must have :attr:`~Permissions.manage_channels` to create the channel.

        The ``overwrites`` parameter can be used to create a 'secret'
        channel upon creation. This parameter expects a :class:`dict` of
        overwrites with the target (either a :class:`Member` or a :class:`Role`)
        as the key and a :class:`PermissionOverwrite` as the value.

        .. note::

            Creating a channel of a specified position will not update the position of
            other channels to follow suit. A follow-up call to :meth:`~TextChannel.edit`
            will be required to update the position of the channel in the channel list.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Examples
        ----------

        Creating a basic channel:

        .. code-block:: python3

            channel = await guild.create_text_channel('cool-channel')

        Creating a "secret" channel:

        .. code-block:: python3

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }

            channel = await guild.create_text_channel('secret', overwrites=overwrites)

        Parameters
        -----------
        name: :class:`str`
            The channel's name.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        category: Optional[:class:`CategoryChannel`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        topic: :class:`str`
            The new channel's topic.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for user in this channel, in seconds.
            The maximum value possible is ``21600``.
        nsfw: :class:`bool`
            To mark the channel as NSFW or not.
        news: :class:`bool`
            Whether to create the text channel as a news channel.

            .. versionadded:: 2.0
        default_auto_archive_duration: :class:`int`
            The default auto archive duration for threads created in the text channel (in minutes).
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.

            .. versionadded:: 2.0
        default_thread_slowmode_delay: :class:`int`
            The default slowmode delay in seconds for threads created in the text channel.

            .. versionadded:: 2.3
        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`TextChannel`
            The channel that was just created.
        """

        options = {}
        if position is not MISSING:
            options['position'] = position

        if topic is not MISSING:
            options['topic'] = topic

        if slowmode_delay is not MISSING:
            options['rate_limit_per_user'] = slowmode_delay

        if nsfw is not MISSING:
            options['nsfw'] = nsfw

        if default_auto_archive_duration is not MISSING:
            options['default_auto_archive_duration'] = default_auto_archive_duration

        if default_thread_slowmode_delay is not MISSING:
            options['default_thread_rate_limit_per_user'] = default_thread_slowmode_delay

        data = await self._create_channel(
            name,
            overwrites=overwrites,
            channel_type=ChannelType.news if news else ChannelType.text,
            category=category,
            reason=reason,
            **options,
        )
        channel = TextChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_voice_channel(
        self,
        name: str,
        *,
        reason: Optional[str] = None,
        category: Optional[CategoryChannel] = None,
        position: int = MISSING,
        bitrate: int = MISSING,
        user_limit: int = MISSING,
        rtc_region: Optional[str] = MISSING,
        video_quality_mode: VideoQualityMode = MISSING,
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = MISSING,
    ) -> VoiceChannel:
        """|coro|

        This is similar to :meth:`create_text_channel` except makes a :class:`VoiceChannel` instead.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        -----------
        name: :class:`str`
            The channel's name.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        category: Optional[:class:`CategoryChannel`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        bitrate: :class:`int`
            The channel's preferred audio bitrate in bits per second.
        user_limit: :class:`int`
            The channel's limit for number of members that can be in a voice channel.
        rtc_region: Optional[:class:`str`]
            The region for the voice channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.

            .. versionadded:: 1.7
        video_quality_mode: :class:`VideoQualityMode`
            The camera video quality for the voice channel's participants.

            .. versionadded:: 2.0
        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`VoiceChannel`
            The channel that was just created.
        """
        options = {}
        if position is not MISSING:
            options['position'] = position

        if bitrate is not MISSING:
            options['bitrate'] = bitrate

        if user_limit is not MISSING:
            options['user_limit'] = user_limit

        if rtc_region is not MISSING:
            options['rtc_region'] = None if rtc_region is None else rtc_region

        if video_quality_mode is not MISSING:
            if not isinstance(video_quality_mode, VideoQualityMode):
                raise TypeError('video_quality_mode must be of type VideoQualityMode')
            options['video_quality_mode'] = video_quality_mode.value

        data = await self._create_channel(
            name, overwrites=overwrites, channel_type=ChannelType.voice, category=category, reason=reason, **options
        )
        channel = VoiceChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_stage_channel(
        self,
        name: str,
        *,
        reason: Optional[str] = None,
        category: Optional[CategoryChannel] = None,
        position: int = MISSING,
        bitrate: int = MISSING,
        user_limit: int = MISSING,
        rtc_region: Optional[str] = MISSING,
        video_quality_mode: VideoQualityMode = MISSING,
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = MISSING,
    ) -> StageChannel:
        """|coro|

        This is similar to :meth:`create_text_channel` except makes a :class:`StageChannel` instead.

        .. versionadded:: 1.7

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        -----------
        name: :class:`str`
            The channel's name.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        category: Optional[:class:`CategoryChannel`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        bitrate: :class:`int`
            The channel's preferred audio bitrate in bits per second.

            .. versionadded:: 2.2
        user_limit: :class:`int`
            The channel's limit for number of members that can be in a voice channel.

            .. versionadded:: 2.2
        rtc_region: Optional[:class:`str`]
            The region for the voice channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.

            .. versionadded:: 2.2
        video_quality_mode: :class:`VideoQualityMode`
            The camera video quality for the voice channel's participants.

            .. versionadded:: 2.2
        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`StageChannel`
            The channel that was just created.
        """

        options = {}
        if position is not MISSING:
            options['position'] = position

        if bitrate is not MISSING:
            options['bitrate'] = bitrate

        if user_limit is not MISSING:
            options['user_limit'] = user_limit

        if rtc_region is not MISSING:
            options['rtc_region'] = None if rtc_region is None else rtc_region

        if video_quality_mode is not MISSING:
            if not isinstance(video_quality_mode, VideoQualityMode):
                raise TypeError('video_quality_mode must be of type VideoQualityMode')
            options['video_quality_mode'] = video_quality_mode.value

        data = await self._create_channel(
            name, overwrites=overwrites, channel_type=ChannelType.stage_voice, category=category, reason=reason, **options
        )
        channel = StageChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def create_category(
        self,
        name: str,
        *,
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = MISSING,
        reason: Optional[str] = None,
        position: int = MISSING,
    ) -> CategoryChannel:
        """|coro|

        Same as :meth:`create_text_channel` except makes a :class:`CategoryChannel` instead.

        .. note::

            The ``category`` parameter is not supported in this function since categories
            cannot have categories.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Raises
        ------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`CategoryChannel`
            The channel that was just created.
        """
        options: Dict[str, Any] = {}
        if position is not MISSING:
            options['position'] = position

        data = await self._create_channel(
            name, overwrites=overwrites, channel_type=ChannelType.category, reason=reason, **options
        )
        channel = CategoryChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    create_category_channel = create_category

    async def create_forum(
        self,
        name: str,
        *,
        topic: str = MISSING,
        position: int = MISSING,
        category: Optional[CategoryChannel] = None,
        slowmode_delay: int = MISSING,
        nsfw: bool = MISSING,
        overwrites: Mapping[Union[Role, Member, Object], PermissionOverwrite] = MISSING,
        reason: Optional[str] = None,
        default_auto_archive_duration: int = MISSING,
        default_thread_slowmode_delay: int = MISSING,
        default_sort_order: ForumOrderType = MISSING,
        default_reaction_emoji: EmojiInputType = MISSING,
        default_layout: ForumLayoutType = MISSING,
        available_tags: Sequence[ForumTag] = MISSING,
    ) -> ForumChannel:
        """|coro|

        Similar to :meth:`create_text_channel` except makes a :class:`ForumChannel` instead.

        The ``overwrites`` parameter can be used to create a 'secret'
        channel upon creation. This parameter expects a :class:`dict` of
        overwrites with the target (either a :class:`Member` or a :class:`Role`)
        as the key and a :class:`PermissionOverwrite` as the value.

        .. versionadded:: 2.0

        Parameters
        -----------
        name: :class:`str`
            The channel's name.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`], :class:`PermissionOverwrite`]
            A :class:`dict` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply upon creation of a channel.
            Useful for creating secret channels.
        topic: :class:`str`
            The channel's topic.
        category: Optional[:class:`CategoryChannel`]
            The category to place the newly created channel under.
            The permissions will be automatically synced to category if no
            overwrites are provided.
        position: :class:`int`
            The position in the channel list. This is a number that starts
            at 0. e.g. the top channel is position 0.
        nsfw: :class:`bool`
            To mark the channel as NSFW or not.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for users in this channel, in seconds.
            The maximum possible value is ``21600``.
        reason: Optional[:class:`str`]
            The reason for creating this channel. Shows up in the audit log.
        default_auto_archive_duration: :class:`int`
            The default auto archive duration for threads created in the forum channel (in minutes).
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.
        default_thread_slowmode_delay: :class:`int`
            The default slowmode delay in seconds for threads created in this forum.

            .. versionadded:: 2.1
        default_sort_order: :class:`ForumOrderType`
            The default sort order for posts in this forum channel.

            .. versionadded:: 2.3
        default_reaction_emoji: Union[:class:`Emoji`, :class:`PartialEmoji`, :class:`str`]
            The default reaction emoji for threads created in this forum to show in the
            add reaction button.

            .. versionadded:: 2.3
        default_layout: :class:`ForumLayoutType`
            The default layout for posts in this forum.

            .. versionadded:: 2.3
        available_tags: Sequence[:class:`ForumTag`]
            The available tags for this forum channel.

            .. versionadded:: 2.1

        Raises
        -------
        Forbidden
            You do not have the proper permissions to create this channel.
        HTTPException
            Creating the channel failed.
        TypeError
            The permission overwrite information is not in proper form.

        Returns
        -------
        :class:`ForumChannel`
            The channel that was just created.
        """
        options = {}

        if position is not MISSING:
            options['position'] = position

        if topic is not MISSING:
            options['topic'] = topic

        if slowmode_delay is not MISSING:
            options['rate_limit_per_user'] = slowmode_delay

        if nsfw is not MISSING:
            options['nsfw'] = nsfw

        if default_auto_archive_duration is not MISSING:
            options['default_auto_archive_duration'] = default_auto_archive_duration

        if default_thread_slowmode_delay is not MISSING:
            options['default_thread_rate_limit_per_user'] = default_thread_slowmode_delay

        if default_sort_order is not MISSING:
            if not isinstance(default_sort_order, ForumOrderType):
                raise TypeError(
                    f'default_sort_order parameter must be a ForumOrderType not {default_sort_order.__class__.__name__}'
                )

            options['default_sort_order'] = default_sort_order.value

        if default_reaction_emoji is not MISSING:
            if isinstance(default_reaction_emoji, _EmojiTag):
                options['default_reaction_emoji'] = default_reaction_emoji._to_partial()._to_forum_tag_payload()
            elif isinstance(default_reaction_emoji, str):
                options['default_reaction_emoji'] = PartialEmoji.from_str(default_reaction_emoji)._to_forum_tag_payload()
            else:
                raise ValueError(f'default_reaction_emoji parameter must be either Emoji, PartialEmoji, or str')

        if default_layout is not MISSING:
            if not isinstance(default_layout, ForumLayoutType):
                raise TypeError(
                    f'default_layout parameter must be a ForumLayoutType not {default_layout.__class__.__name__}'
                )

            options['default_forum_layout'] = default_layout.value

        if available_tags is not MISSING:
            options['available_tags'] = [t.to_dict() for t in available_tags]

        data = await self._create_channel(
            name=name, overwrites=overwrites, channel_type=ChannelType.forum, category=category, reason=reason, **options
        )

        channel = ForumChannel(state=self._state, guild=self, data=data)

        # temporarily add to the cache
        self._channels[channel.id] = channel
        return channel

    async def leave(self) -> None:
        """|coro|

        Leaves the guild.

        .. note::

            You cannot leave the guild that you own, you must delete it instead
            via :meth:`delete`.

        Raises
        --------
        HTTPException
            Leaving the guild failed.
        """
        await self._state.http.leave_guild(self.id)

    async def delete(self) -> None:
        """|coro|

        Deletes the guild. You must be the guild owner to delete the
        guild.

        Raises
        --------
        HTTPException
            Deleting the guild failed.
        Forbidden
            You do not have permissions to delete the guild.
        """

        await self._state.http.delete_guild(self.id)

    async def edit(
        self,
        *,
        reason: Optional[str] = MISSING,
        name: str = MISSING,
        description: Optional[str] = MISSING,
        icon: Optional[bytes] = MISSING,
        banner: Optional[bytes] = MISSING,
        splash: Optional[bytes] = MISSING,
        discovery_splash: Optional[bytes] = MISSING,
        community: bool = MISSING,
        afk_channel: Optional[VoiceChannel] = MISSING,
        owner: Snowflake = MISSING,
        afk_timeout: int = MISSING,
        default_notifications: NotificationLevel = MISSING,
        verification_level: VerificationLevel = MISSING,
        explicit_content_filter: ContentFilter = MISSING,
        vanity_code: str = MISSING,
        system_channel: Optional[TextChannel] = MISSING,
        system_channel_flags: SystemChannelFlags = MISSING,
        preferred_locale: Locale = MISSING,
        rules_channel: Optional[TextChannel] = MISSING,
        public_updates_channel: Optional[TextChannel] = MISSING,
        premium_progress_bar_enabled: bool = MISSING,
        discoverable: bool = MISSING,
        invites_disabled: bool = MISSING,
        widget_enabled: bool = MISSING,
        widget_channel: Optional[Snowflake] = MISSING,
        mfa_level: MFALevel = MISSING,
        raid_alerts_disabled: bool = MISSING,
        safety_alerts_channel: TextChannel = MISSING,
        invites_disabled_until: datetime.datetime = MISSING,
        dms_disabled_until: datetime.datetime = MISSING,
    ) -> Guild:
        r"""|coro|

        Edits the guild.

        You must have :attr:`~Permissions.manage_guild` to edit the guild.

        .. versionchanged:: 2.0
            The newly updated guild is returned.

        .. versionchanged:: 2.0
            The ``region`` keyword parameter has been removed.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` or
            :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The new name of the guild.
        description: Optional[:class:`str`]
            The new description of the guild. Could be ``None`` for no description.
            This is only available to guilds that contain ``COMMUNITY`` in :attr:`Guild.features`.
        icon: :class:`bytes`
            A :term:`py:bytes-like object` representing the icon. Only PNG/JPEG is supported.
            GIF is only available to guilds that contain ``ANIMATED_ICON`` in :attr:`Guild.features`.
            Could be ``None`` to denote removal of the icon.
        banner: :class:`bytes`
            A :term:`py:bytes-like object` representing the banner.
            Could be ``None`` to denote removal of the banner. This is only available to guilds that contain
            ``BANNER`` in :attr:`Guild.features`.
        splash: :class:`bytes`
            A :term:`py:bytes-like object` representing the invite splash.
            Only PNG/JPEG supported. Could be ``None`` to denote removing the
            splash. This is only available to guilds that contain ``INVITE_SPLASH``
            in :attr:`Guild.features`.
        discovery_splash: :class:`bytes`
            A :term:`py:bytes-like object` representing the discovery splash.
            Only PNG/JPEG supported. Could be ``None`` to denote removing the
            splash. This is only available to guilds that contain ``DISCOVERABLE``
            in :attr:`Guild.features`.

            .. versionadded:: 2.0
        community: :class:`bool`
            Whether the guild should be a Community guild. If set to ``True``\, both ``rules_channel``
            and ``public_updates_channel`` parameters are required.

            .. versionadded:: 2.0
        afk_channel: Optional[:class:`VoiceChannel`]
            The new channel that is the AFK channel. Could be ``None`` for no AFK channel.
        afk_timeout: :class:`int`
            The number of seconds until someone is moved to the AFK channel.
        owner: :class:`Member`
            The new owner of the guild to transfer ownership to. Note that you must
            be owner of the guild to do this.
        verification_level: :class:`VerificationLevel`
            The new verification level for the guild.
        default_notifications: :class:`NotificationLevel`
            The new default notification level for the guild.
        explicit_content_filter: :class:`ContentFilter`
            The new explicit content filter for the guild.
        vanity_code: :class:`str`
            The new vanity code for the guild.
        system_channel: Optional[:class:`TextChannel`]
            The new channel that is used for the system channel. Could be ``None`` for no system channel.
        system_channel_flags: :class:`SystemChannelFlags`
            The new system channel settings to use with the new system channel.
        preferred_locale: :class:`Locale`
            The new preferred locale for the guild. Used as the primary language in the guild.

            .. versionchanged:: 2.0

                Now accepts an enum instead of :class:`str`.
        rules_channel: Optional[:class:`TextChannel`]
            The new channel that is used for rules. This is only available to
            guilds that contain ``COMMUNITY`` in :attr:`Guild.features`. Could be ``None`` for no rules
            channel.

            .. versionadded:: 1.4
        public_updates_channel: Optional[:class:`TextChannel`]
            The new channel that is used for public updates from Discord. This is only available to
            guilds that contain ``COMMUNITY`` in :attr:`Guild.features`. Could be ``None`` for no
            public updates channel.

            .. versionadded:: 1.4
        premium_progress_bar_enabled: :class:`bool`
            Whether the premium AKA server boost level progress bar should be enabled for the guild.

            .. versionadded:: 2.0
        discoverable: :class:`bool`
            Whether server discovery is enabled for this guild.

            .. versionadded:: 2.1
        invites_disabled: :class:`bool`
            Whether joining via invites should be disabled for the guild.

            .. versionadded:: 2.1
        widget_enabled: :class:`bool`
            Whether to enable the widget for the guild.

            .. versionadded:: 2.3
        widget_channel: Optional[:class:`abc.Snowflake`]
             The new widget channel. ``None`` removes the widget channel.

            .. versionadded:: 2.3
        mfa_level: :class:`MFALevel`
            The new guild's Multi-Factor Authentication requirement level.
            Note that you must be owner of the guild to do this.

            .. versionadded:: 2.3
        reason: Optional[:class:`str`]
            The reason for editing this guild. Shows up on the audit log.

        raid_alerts_disabled: :class:`bool`
            Whether the alerts for raid protection should be disabled for the guild.

            .. versionadded:: 2.3

        safety_alerts_channel: Optional[:class:`TextChannel`]
            The new channel that is used for safety alerts. This is only available to
            guilds that contain ``COMMUNITY`` in :attr:`Guild.features`. Could be ``None`` for no
            safety alerts channel.

            .. versionadded:: 2.3

        invites_disabled_until: Optional[:class:`datetime.datetime`]
            The time when invites should be enabled again, or ``None`` to disable the action.
            This must be a timezone-aware datetime object. Consider using :func:`utils.utcnow`.

            .. versionadded:: 2.4

        dms_disabled_until: Optional[:class:`datetime.datetime`]
            The time when direct messages should be allowed again, or ``None`` to disable the action.
            This must be a timezone-aware datetime object. Consider using :func:`utils.utcnow`.

            .. versionadded:: 2.4

        Raises
        -------
        Forbidden
            You do not have permissions to edit the guild.
        HTTPException
            Editing the guild failed.
        ValueError
            The image format passed in to ``icon`` is invalid. It must be
            PNG or JPG. This is also raised if you are not the owner of the
            guild and request an ownership transfer.
        TypeError
            The type passed to the ``default_notifications``, ``rules_channel``, ``public_updates_channel``,
            ``safety_alerts_channel`` ``verification_level``, ``explicit_content_filter``,
            ``system_channel_flags``, or ``mfa_level`` parameter was of the incorrect type.

        Returns
        --------
        :class:`Guild`
            The newly updated guild. Note that this has the same limitations as
            mentioned in :meth:`Client.fetch_guild` and may not have full data.
        """

        http = self._state.http

        if vanity_code is not MISSING:
            await http.change_vanity_code(self.id, vanity_code, reason=reason)

        fields: Dict[str, Any] = {}
        if name is not MISSING:
            fields['name'] = name

        if description is not MISSING:
            fields['description'] = description

        if preferred_locale is not MISSING:
            fields['preferred_locale'] = str(preferred_locale)

        if afk_timeout is not MISSING:
            fields['afk_timeout'] = afk_timeout

        if icon is not MISSING:
            if icon is None:
                fields['icon'] = icon
            else:
                fields['icon'] = utils._bytes_to_base64_data(icon)

        if banner is not MISSING:
            if banner is None:
                fields['banner'] = banner
            else:
                fields['banner'] = utils._bytes_to_base64_data(banner)

        if splash is not MISSING:
            if splash is None:
                fields['splash'] = splash
            else:
                fields['splash'] = utils._bytes_to_base64_data(splash)

        if discovery_splash is not MISSING:
            if discovery_splash is None:
                fields['discovery_splash'] = discovery_splash
            else:
                fields['discovery_splash'] = utils._bytes_to_base64_data(discovery_splash)

        if default_notifications is not MISSING:
            if not isinstance(default_notifications, NotificationLevel):
                raise TypeError('default_notifications field must be of type NotificationLevel')
            fields['default_message_notifications'] = default_notifications.value

        if afk_channel is not MISSING:
            if afk_channel is None:
                fields['afk_channel_id'] = afk_channel
            else:
                fields['afk_channel_id'] = afk_channel.id

        if system_channel is not MISSING:
            if system_channel is None:
                fields['system_channel_id'] = system_channel
            else:
                fields['system_channel_id'] = system_channel.id

        if rules_channel is not MISSING:
            if rules_channel is None:
                fields['rules_channel_id'] = rules_channel
            else:
                if not isinstance(rules_channel, TextChannel):
                    raise TypeError(f'rules_channel must be of type TextChannel not {rules_channel.__class__.__name__}')

                fields['rules_channel_id'] = rules_channel.id

        if public_updates_channel is not MISSING:
            if public_updates_channel is None:
                fields['public_updates_channel_id'] = public_updates_channel
            else:
                if not isinstance(public_updates_channel, TextChannel):
                    raise TypeError(
                        f'public_updates_channel must be of type TextChannel not {public_updates_channel.__class__.__name__}'
                    )

                fields['public_updates_channel_id'] = public_updates_channel.id

        if safety_alerts_channel is not MISSING:
            if safety_alerts_channel is None:
                fields['safety_alerts_channel_id'] = safety_alerts_channel
            else:
                if not isinstance(safety_alerts_channel, TextChannel):
                    raise TypeError(
                        f'safety_alerts_channel must be of type TextChannel not {safety_alerts_channel.__class__.__name__}'
                    )

            fields['safety_alerts_channel_id'] = safety_alerts_channel.id

        if owner is not MISSING:
            if self.owner_id != self._state.self_id:
                raise ValueError('To transfer ownership you must be the owner of the guild.')

            fields['owner_id'] = owner.id

        if verification_level is not MISSING:
            if not isinstance(verification_level, VerificationLevel):
                raise TypeError('verification_level field must be of type VerificationLevel')

            fields['verification_level'] = verification_level.value

        if explicit_content_filter is not MISSING:
            if not isinstance(explicit_content_filter, ContentFilter):
                raise TypeError('explicit_content_filter field must be of type ContentFilter')

            fields['explicit_content_filter'] = explicit_content_filter.value

        if system_channel_flags is not MISSING:
            if not isinstance(system_channel_flags, SystemChannelFlags):
                raise TypeError('system_channel_flags field must be of type SystemChannelFlags')

            fields['system_channel_flags'] = system_channel_flags.value

        if any(feat is not MISSING for feat in (community, discoverable, invites_disabled, raid_alerts_disabled)):
            features = set(self.features)

            if community is not MISSING:
                if community:
                    if 'rules_channel_id' in fields and 'public_updates_channel_id' in fields:
                        features.add('COMMUNITY')
                    else:
                        raise ValueError(
                            'community field requires both rules_channel and public_updates_channel fields to be provided'
                        )
                else:
                    features.discard('COMMUNITY')

            if discoverable is not MISSING:
                if discoverable:
                    features.add('DISCOVERABLE')
                else:
                    features.discard('DISCOVERABLE')

            if invites_disabled is not MISSING:
                if invites_disabled:
                    features.add('INVITES_DISABLED')
                else:
                    features.discard('INVITES_DISABLED')

            if raid_alerts_disabled is not MISSING:
                if raid_alerts_disabled:
                    features.add('RAID_ALERTS_DISABLED')
                else:
                    features.discard('RAID_ALERTS_DISABLED')

            fields['features'] = list(features)

        if premium_progress_bar_enabled is not MISSING:
            fields['premium_progress_bar_enabled'] = premium_progress_bar_enabled

        widget_payload: EditWidgetSettings = {}
        if widget_channel is not MISSING:
            widget_payload['channel_id'] = None if widget_channel is None else widget_channel.id
        if widget_enabled is not MISSING:
            widget_payload['enabled'] = widget_enabled

        if widget_payload:
            await self._state.http.edit_widget(self.id, payload=widget_payload, reason=reason)

        if mfa_level is not MISSING:
            if not isinstance(mfa_level, MFALevel):
                raise TypeError(f'mfa_level must be of type MFALevel not {mfa_level.__class__.__name__}')

            await http.edit_guild_mfa_level(self.id, mfa_level=mfa_level.value)

        incident_actions_payload: IncidentData = {}
        if invites_disabled_until is not MISSING:
            if invites_disabled_until is None:
                incident_actions_payload['invites_disabled_until'] = None
            else:
                if invites_disabled_until.tzinfo is None:
                    raise TypeError(
                        'invites_disabled_until must be an aware datetime. Consider using discord.utils.utcnow() or datetime.datetime.now().astimezone() for local time.'
                    )
                incident_actions_payload['invites_disabled_until'] = invites_disabled_until.isoformat()

        if dms_disabled_until is not MISSING:
            if dms_disabled_until is None:
                incident_actions_payload['dms_disabled_until'] = None
            else:
                if dms_disabled_until.tzinfo is None:
                    raise TypeError(
                        'dms_disabled_until must be an aware datetime. Consider using discord.utils.utcnow() or datetime.datetime.now().astimezone() for local time.'
                    )
                incident_actions_payload['dms_disabled_until'] = dms_disabled_until.isoformat()

        if incident_actions_payload:
            await http.edit_incident_actions(self.id, payload=incident_actions_payload)

        data = await http.edit_guild(self.id, reason=reason, **fields)
        return Guild(data=data, state=self._state)

    async def fetch_channels(self) -> Sequence[GuildChannel]:
        """|coro|

        Retrieves all :class:`abc.GuildChannel` that the guild has.

        .. note::

            This method is an API call. For general usage, consider :attr:`channels` instead.

        .. versionadded:: 1.2

        Raises
        -------
        InvalidData
            An unknown channel type was received from Discord.
        HTTPException
            Retrieving the channels failed.

        Returns
        -------
        Sequence[:class:`abc.GuildChannel`]
            All channels in the guild.
        """
        data = await self._state.http.get_all_guild_channels(self.id)

        def convert(d):
            factory, ch_type = _guild_channel_factory(d['type'])
            if factory is None:
                raise InvalidData('Unknown channel type {type} for channel ID {id}.'.format_map(d))

            channel = factory(guild=self, state=self._state, data=d)
            return channel

        return [convert(d) for d in data]

    async def active_threads(self) -> List[Thread]:
        """|coro|

        Returns a list of active :class:`Thread` that the client can access.

        This includes both private and public threads.

        .. versionadded:: 2.0

        Raises
        ------
        HTTPException
            The request to get the active threads failed.

        Returns
        --------
        List[:class:`Thread`]
            The active threads
        """
        data = await self._state.http.get_active_threads(self.id)
        threads = [Thread(guild=self, state=self._state, data=d) for d in data.get('threads', [])]
        thread_lookup: Dict[int, Thread] = {thread.id: thread for thread in threads}
        for member in data.get('members', []):
            thread = thread_lookup.get(int(member['id']))
            if thread is not None:
                thread._add_member(ThreadMember(parent=thread, data=member))

        return threads

    async def fetch_members(self, *, limit: Optional[int] = 1000, after: SnowflakeTime = MISSING) -> AsyncIterator[Member]:
        """Retrieves an :term:`asynchronous iterator` that enables receiving the guild's members. In order to use this,
        :meth:`Intents.members` must be enabled.

        .. note::

            This method is an API call. For general usage, consider :attr:`members` instead.

        .. versionadded:: 1.3

        All parameters are optional.

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of members to retrieve. Defaults to 1000.
            Pass ``None`` to fetch all members. Note that this is potentially slow.
        after: Optional[Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve members after this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.

        Raises
        ------
        ClientException
            The members intent is not enabled.
        HTTPException
            Getting the members failed.

        Yields
        ------
        :class:`.Member`
            The member with the member data parsed.

        Examples
        --------

        Usage ::

            async for member in guild.fetch_members(limit=150):
                print(member.name)
        """

        if not self._state._intents.members:
            raise ClientException('Intents.members must be enabled to use this.')

        while True:
            retrieve = 1000 if limit is None else min(limit, 1000)
            if retrieve < 1:
                return

            if isinstance(after, datetime.datetime):
                after = Object(id=utils.time_snowflake(after, high=True))

            after = after or OLDEST_OBJECT
            after_id = after.id if after else None
            state = self._state

            data = await state.http.get_members(self.id, retrieve, after_id)
            if not data:
                return

            # Terminate loop on next iteration; there's no data left after this
            if len(data) < 1000:
                limit = 0

            after = Object(id=int(data[-1]['user']['id']))

            for raw_member in reversed(data):
                yield Member(data=raw_member, guild=self, state=state)

    async def fetch_member(self, member_id: int, /) -> Member:
        """|coro|

        Retrieves a :class:`Member` from a guild ID, and a member ID.

        .. note::

            This method is an API call. If you have :attr:`Intents.members` and member cache enabled, consider :meth:`get_member` instead.

        .. versionchanged:: 2.0

            ``member_id`` parameter is now positional-only.

        Parameters
        -----------
        member_id: :class:`int`
            The member's ID to fetch from.

        Raises
        -------
        Forbidden
            You do not have access to the guild.
        HTTPException
            Fetching the member failed.
        NotFound
            The member could not be found.

        Returns
        --------
        :class:`Member`
            The member from the member ID.
        """
        data = await self._state.http.get_member(self.id, member_id)
        return Member(data=data, state=self._state, guild=self)

    async def fetch_ban(self, user: Snowflake) -> BanEntry:
        """|coro|

        Retrieves the :class:`BanEntry` for a user.

        You must have :attr:`~Permissions.ban_members` to get this information.

        Parameters
        -----------
        user: :class:`abc.Snowflake`
            The user to get ban information from.

        Raises
        ------
        Forbidden
            You do not have proper permissions to get the information.
        NotFound
            This user is not banned.
        HTTPException
            An error occurred while fetching the information.

        Returns
        -------
        :class:`BanEntry`
            The :class:`BanEntry` object for the specified user.
        """
        data: BanPayload = await self._state.http.get_ban(user.id, self.id)
        return BanEntry(user=User(state=self._state, data=data['user']), reason=data['reason'])

    async def fetch_channel(self, channel_id: int, /) -> Union[GuildChannel, Thread]:
        """|coro|

        Retrieves a :class:`.abc.GuildChannel` or :class:`.Thread` with the specified ID.

        .. note::

            This method is an API call. For general usage, consider :meth:`get_channel_or_thread` instead.

        .. versionadded:: 2.0

        Raises
        -------
        InvalidData
            An unknown channel type was received from Discord
            or the guild the channel belongs to is not the same
            as the one in this object points to.
        HTTPException
            Retrieving the channel failed.
        NotFound
            Invalid Channel ID.
        Forbidden
            You do not have permission to fetch this channel.

        Returns
        --------
        Union[:class:`.abc.GuildChannel`, :class:`.Thread`]
            The channel from the ID.
        """
        data = await self._state.http.get_channel(channel_id)

        factory, ch_type = _threaded_guild_channel_factory(data['type'])
        if factory is None:
            raise InvalidData('Unknown channel type {type} for channel ID {id}.'.format_map(data))

        if ch_type in (ChannelType.group, ChannelType.private):
            raise InvalidData('Channel ID resolved to a private channel')

        guild_id = int(data['guild_id'])  # type: ignore # channel won't be a private channel
        if self.id != guild_id:
            raise InvalidData('Guild ID resolved to a different guild')

        channel: GuildChannel = factory(guild=self, state=self._state, data=data)  # type: ignore # channel won't be a private channel
        return channel

    async def bans(
        self,
        *,
        limit: Optional[int] = 1000,
        before: Snowflake = MISSING,
        after: Snowflake = MISSING,
    ) -> AsyncIterator[BanEntry]:
        """Retrieves an :term:`asynchronous iterator` of the users that are banned from the guild as a :class:`BanEntry`.

        You must have :attr:`~Permissions.ban_members` to get this information.

        .. versionchanged:: 2.0
            Due to a breaking change in Discord's API, this now returns a paginated iterator instead of a list.

        Examples
        ---------

        Usage ::

            async for entry in guild.bans(limit=150):
                print(entry.user, entry.reason)

        Flattening into a list ::

            bans = [entry async for entry in guild.bans(limit=2000)]
            # bans is now a list of BanEntry...

        All parameters are optional.

        Parameters
        -----------
        limit: Optional[:class:`int`]
            The number of bans to retrieve. If ``None``, it retrieves every ban in
            the guild. Note, however, that this would make it a slow operation.
            Defaults to ``1000``.
        before: :class:`.abc.Snowflake`
            Retrieves bans before this user.
        after: :class:`.abc.Snowflake`
            Retrieve bans after this user.

        Raises
        -------
        Forbidden
            You do not have proper permissions to get the information.
        HTTPException
            An error occurred while fetching the information.
        TypeError
            Both ``after`` and ``before`` were provided, as Discord does not
            support this type of pagination.

        Yields
        --------
        :class:`BanEntry`
            The ban entry of the banned user.
        """

        if before is not MISSING and after is not MISSING:
            raise TypeError('bans pagination does not support both before and after')

        # This endpoint paginates in ascending order.
        endpoint = self._state.http.get_bans

        async def _before_strategy(retrieve: int, before: Optional[Snowflake], limit: Optional[int]):
            before_id = before.id if before else None
            data = await endpoint(self.id, limit=retrieve, before=before_id)

            if data:
                if limit is not None:
                    limit -= len(data)

                before = Object(id=int(data[0]['user']['id']))

            return data, before, limit

        async def _after_strategy(retrieve: int, after: Optional[Snowflake], limit: Optional[int]):
            after_id = after.id if after else None
            data = await endpoint(self.id, limit=retrieve, after=after_id)

            if data:
                if limit is not None:
                    limit -= len(data)

                after = Object(id=int(data[-1]['user']['id']))

            return data, after, limit

        if before:
            strategy, state = _before_strategy, before
        else:
            strategy, state = _after_strategy, after

        while True:
            retrieve = 1000 if limit is None else min(limit, 1000)
            if retrieve < 1:
                return

            data, state, limit = await strategy(retrieve, state, limit)

            # Terminate loop on next iteration; there's no data left after this
            if len(data) < 1000:
                limit = 0

            for e in data:
                yield BanEntry(user=User(state=self._state, data=e['user']), reason=e['reason'])

    async def prune_members(
        self,
        *,
        days: int,
        compute_prune_count: bool = True,
        roles: Collection[Snowflake] = MISSING,
        reason: Optional[str] = None,
    ) -> Optional[int]:
        r"""|coro|

        Prunes the guild from its inactive members.

        The inactive members are denoted if they have not logged on in
        ``days`` number of days and they have no roles.

        You must have both :attr:`~Permissions.kick_members` and :attr:`~Permissions.manage_guild` to do this.

        To check how many members you would prune without actually pruning,
        see the :meth:`estimate_pruned_members` function.

        To prune members that have specific roles see the ``roles`` parameter.

        .. versionchanged:: 1.4
            The ``roles`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        -----------
        days: :class:`int`
            The number of days before counting as inactive.
        reason: Optional[:class:`str`]
            The reason for doing this action. Shows up on the audit log.
        compute_prune_count: :class:`bool`
            Whether to compute the prune count. This defaults to ``True``
            which makes it prone to timeouts in very large guilds. In order
            to prevent timeouts, you must set this to ``False``. If this is
            set to ``False``\, then this function will always return ``None``.
        roles: List[:class:`abc.Snowflake`]
            A list of :class:`abc.Snowflake` that represent roles to include in the pruning process. If a member
            has a role that is not specified, they'll be excluded.

        Raises
        -------
        Forbidden
            You do not have permissions to prune members.
        HTTPException
            An error occurred while pruning members.
        TypeError
            An integer was not passed for ``days``.

        Returns
        ---------
        Optional[:class:`int`]
            The number of members pruned. If ``compute_prune_count`` is ``False``
            then this returns ``None``.
        """

        if not isinstance(days, int):
            raise TypeError(f'Expected int for ``days``, received {days.__class__.__name__} instead.')

        if roles:
            role_ids = [str(role.id) for role in roles]
        else:
            role_ids = []

        data = await self._state.http.prune_members(
            self.id, days, compute_prune_count=compute_prune_count, roles=role_ids, reason=reason
        )
        return data['pruned']

    async def templates(self) -> List[Template]:
        """|coro|

        Gets the list of templates from this guild.

        You must have :attr:`~.Permissions.manage_guild` to do this.

        .. versionadded:: 1.7

        Raises
        -------
        Forbidden
            You don't have permissions to get the templates.

        Returns
        --------
        List[:class:`Template`]
            The templates for this guild.
        """
        from .template import Template

        data = await self._state.http.guild_templates(self.id)
        return [Template(data=d, state=self._state) for d in data]

    async def webhooks(self) -> List[Webhook]:
        """|coro|

        Gets the list of webhooks from this guild.

        You must have :attr:`~.Permissions.manage_webhooks` to do this.

        Raises
        -------
        Forbidden
            You don't have permissions to get the webhooks.

        Returns
        --------
        List[:class:`Webhook`]
            The webhooks for this guild.
        """

        from .webhook import Webhook

        data = await self._state.http.guild_webhooks(self.id)
        return [Webhook.from_state(d, state=self._state) for d in data]

    async def estimate_pruned_members(self, *, days: int, roles: Collection[Snowflake] = MISSING) -> Optional[int]:
        """|coro|

        Similar to :meth:`prune_members` except instead of actually
        pruning members, it returns how many members it would prune
        from the guild had it been called.

        .. versionchanged:: 2.0
            The returned value can be ``None``.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        -----------
        days: :class:`int`
            The number of days before counting as inactive.
        roles: List[:class:`abc.Snowflake`]
            A list of :class:`abc.Snowflake` that represent roles to include in the estimate. If a member
            has a role that is not specified, they'll be excluded.

            .. versionadded:: 1.7

        Raises
        -------
        Forbidden
            You do not have permissions to prune members.
        HTTPException
            An error occurred while fetching the prune members estimate.
        TypeError
            An integer was not passed for ``days``.

        Returns
        ---------
        Optional[:class:`int`]
            The number of members estimated to be pruned.
        """

        if not isinstance(days, int):
            raise TypeError(f'Expected int for ``days``, received {days.__class__.__name__} instead.')

        if roles:
            role_ids = [str(role.id) for role in roles]
        else:
            role_ids = []

        data = await self._state.http.estimate_pruned_members(self.id, days, role_ids)
        return data['pruned']

    async def invites(self) -> List[Invite]:
        """|coro|

        Returns a list of all active instant invites from the guild.

        You must have :attr:`~Permissions.manage_guild` to get this information.

        Raises
        -------
        Forbidden
            You do not have proper permissions to get the information.
        HTTPException
            An error occurred while fetching the information.

        Returns
        -------
        List[:class:`Invite`]
            The list of invites that are currently active.
        """

        data = await self._state.http.invites_from(self.id)
        result = []
        for invite in data:
            channel = self.get_channel(int(invite['channel']['id']))
            result.append(Invite(state=self._state, data=invite, guild=self, channel=channel))

        return result

    async def create_template(self, *, name: str, description: str = MISSING) -> Template:
        """|coro|

        Creates a template for the guild.

        You must have :attr:`~Permissions.manage_guild` to do this.

        .. versionadded:: 1.7

        Parameters
        -----------
        name: :class:`str`
            The name of the template.
        description: :class:`str`
            The description of the template.
        """
        from .template import Template

        payload = {'name': name}

        if description:
            payload['description'] = description

        data = await self._state.http.create_template(self.id, payload)

        return Template(state=self._state, data=data)

    async def create_integration(self, *, type: IntegrationType, id: int) -> None:
        """|coro|

        Attaches an integration to the guild.

        You must have :attr:`~Permissions.manage_guild` to do this.

        .. versionadded:: 1.4

        Parameters
        -----------
        type: :class:`str`
            The integration type (e.g. Twitch).
        id: :class:`int`
            The integration ID.

        Raises
        -------
        Forbidden
            You do not have permission to create the integration.
        HTTPException
            The account could not be found.
        """
        await self._state.http.create_integration(self.id, type, id)

    async def integrations(self) -> List[Integration]:
        """|coro|

        Returns a list of all integrations attached to the guild.

        You must have :attr:`~Permissions.manage_guild` to do this.

        .. versionadded:: 1.4

        Raises
        -------
        Forbidden
            You do not have permission to create the integration.
        HTTPException
            Fetching the integrations failed.

        Returns
        --------
        List[:class:`Integration`]
            The list of integrations that are attached to the guild.
        """
        data = await self._state.http.get_all_integrations(self.id)

        def convert(d):
            factory, _ = _integration_factory(d['type'])
            if factory is None:
                raise InvalidData('Unknown integration type {type!r} for integration ID {id}'.format_map(d))
            return factory(guild=self, data=d)

        return [convert(d) for d in data]

    async def fetch_stickers(self) -> List[GuildSticker]:
        r"""|coro|

        Retrieves a list of all :class:`Sticker`\s for the guild.

        .. versionadded:: 2.0

        .. note::

            This method is an API call. For general usage, consider :attr:`stickers` instead.

        Raises
        ---------
        HTTPException
            An error occurred fetching the stickers.

        Returns
        --------
        List[:class:`GuildSticker`]
            The retrieved stickers.
        """
        data = await self._state.http.get_all_guild_stickers(self.id)
        return [GuildSticker(state=self._state, data=d) for d in data]

    async def fetch_sticker(self, sticker_id: int, /) -> GuildSticker:
        """|coro|

        Retrieves a custom :class:`Sticker` from the guild.

        .. versionadded:: 2.0

        .. note::

            This method is an API call.
            For general usage, consider iterating over :attr:`stickers` instead.

        Parameters
        -------------
        sticker_id: :class:`int`
            The sticker's ID.

        Raises
        ---------
        NotFound
            The sticker requested could not be found.
        HTTPException
            An error occurred fetching the sticker.

        Returns
        --------
        :class:`GuildSticker`
            The retrieved sticker.
        """
        data = await self._state.http.get_guild_sticker(self.id, sticker_id)
        return GuildSticker(state=self._state, data=data)

    async def create_sticker(
        self,
        *,
        name: str,
        description: str,
        emoji: str,
        file: File,
        reason: Optional[str] = None,
    ) -> GuildSticker:
        """|coro|

        Creates a :class:`Sticker` for the guild.

        You must have :attr:`~Permissions.manage_emojis_and_stickers` to do this.

        .. versionadded:: 2.0

        Parameters
        -----------
        name: :class:`str`
            The sticker name. Must be at least 2 characters.
        description: :class:`str`
            The sticker's description.
        emoji: :class:`str`
            The name of a unicode emoji that represents the sticker's expression.
        file: :class:`File`
            The file of the sticker to upload.
        reason: :class:`str`
            The reason for creating this sticker. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You are not allowed to create stickers.
        HTTPException
            An error occurred creating a sticker.

        Returns
        --------
        :class:`GuildSticker`
            The created sticker.
        """
        payload = {
            'name': name,
        }

        payload['description'] = description

        try:
            emoji = unicodedata.name(emoji)
        except TypeError:
            pass
        else:
            emoji = emoji.replace(' ', '_')

        payload['tags'] = emoji

        data = await self._state.http.create_guild_sticker(self.id, payload, file, reason)
        if self._state.cache_guild_expressions:
            return self._state.store_sticker(self, data)
        else:
            return GuildSticker(state=self._state, data=data)

    async def delete_sticker(self, sticker: Snowflake, /, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the custom :class:`Sticker` from the guild.

        You must have :attr:`~Permissions.manage_emojis_and_stickers` to do this.

        .. versionadded:: 2.0

        Parameters
        -----------
        sticker: :class:`abc.Snowflake`
            The sticker you are deleting.
        reason: Optional[:class:`str`]
            The reason for deleting this sticker. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You are not allowed to delete stickers.
        HTTPException
            An error occurred deleting the sticker.
        """
        await self._state.http.delete_guild_sticker(self.id, sticker.id, reason)

    async def fetch_scheduled_events(self, *, with_counts: bool = True) -> List[ScheduledEvent]:
        """|coro|

        Retrieves a list of all scheduled events for the guild.

        .. versionadded:: 2.0

        Parameters
        ------------
        with_counts: :class:`bool`
            Whether to include the number of users that are subscribed to the event.
            Defaults to ``True``.

        Raises
        -------
        HTTPException
            Retrieving the scheduled events failed.

        Returns
        --------
        List[:class:`ScheduledEvent`]
            The scheduled events.
        """
        data = await self._state.http.get_scheduled_events(self.id, with_counts)
        return [ScheduledEvent(state=self._state, data=d) for d in data]

    async def fetch_scheduled_event(self, scheduled_event_id: int, /, *, with_counts: bool = True) -> ScheduledEvent:
        """|coro|

        Retrieves a scheduled event from the guild.

        .. versionadded:: 2.0

        Parameters
        ------------
        scheduled_event_id: :class:`int`
            The scheduled event ID.
        with_counts: :class:`bool`
            Whether to include the number of users that are subscribed to the event.
            Defaults to ``True``.

        Raises
        -------
        NotFound
            The scheduled event was not found.
        HTTPException
            Retrieving the scheduled event failed.

        Returns
        --------
        :class:`ScheduledEvent`
            The scheduled event.
        """
        data = await self._state.http.get_scheduled_event(self.id, scheduled_event_id, with_counts)
        return ScheduledEvent(state=self._state, data=data)

    @overload
    async def create_scheduled_event(
        self,
        *,
        name: str,
        start_time: datetime.datetime,
        entity_type: Literal[EntityType.external] = ...,
        privacy_level: PrivacyLevel = ...,
        location: str = ...,
        end_time: datetime.datetime = ...,
        description: str = ...,
        image: bytes = ...,
        reason: Optional[str] = ...,
        recurrence_rule: Optional[ScheduledEventRecurrenceRule] = ...,
    ) -> ScheduledEvent:
        ...

    @overload
    async def create_scheduled_event(
        self,
        *,
        name: str,
        start_time: datetime.datetime,
        entity_type: Literal[EntityType.stage_instance, EntityType.voice] = ...,
        privacy_level: PrivacyLevel = ...,
        channel: Snowflake = ...,
        end_time: datetime.datetime = ...,
        description: str = ...,
        image: bytes = ...,
        reason: Optional[str] = ...,
        recurrence_rule: Optional[ScheduledEventRecurrenceRule] = ...,
    ) -> ScheduledEvent:
        ...

    @overload
    async def create_scheduled_event(
        self,
        *,
        name: str,
        start_time: datetime.datetime,
        privacy_level: PrivacyLevel = ...,
        location: str = ...,
        end_time: datetime.datetime = ...,
        description: str = ...,
        image: bytes = ...,
        reason: Optional[str] = ...,
        recurrence_rule: Optional[ScheduledEventRecurrenceRule] = ...,
    ) -> ScheduledEvent:
        ...

    @overload
    async def create_scheduled_event(
        self,
        *,
        name: str,
        start_time: datetime.datetime,
        privacy_level: PrivacyLevel = ...,
        channel: Union[VoiceChannel, StageChannel] = ...,
        end_time: datetime.datetime = ...,
        description: str = ...,
        image: bytes = ...,
        reason: Optional[str] = ...,
        recurrence_rule: Optional[ScheduledEventRecurrenceRule] = ...,
    ) -> ScheduledEvent:
        ...

    async def create_scheduled_event(
        self,
        *,
        name: str,
        start_time: datetime.datetime,
        entity_type: EntityType = MISSING,
        privacy_level: PrivacyLevel = MISSING,
        channel: Optional[Snowflake] = MISSING,
        location: str = MISSING,
        end_time: datetime.datetime = MISSING,
        description: str = MISSING,
        image: bytes = MISSING,
        reason: Optional[str] = None,
        recurrence_rule: Optional[ScheduledEventRecurrenceRule] = MISSING,
    ) -> ScheduledEvent:
        r"""|coro|

        Creates a scheduled event for the guild.

        You must have :attr:`~Permissions.manage_events` to do this.

        .. versionadded:: 2.0

        Parameters
        ------------
        name: :class:`str`
            The name of the scheduled event.
        description: :class:`str`
            The description of the scheduled event.
        channel: Optional[:class:`abc.Snowflake`]
            The channel to send the scheduled event to. If the channel is
            a :class:`StageInstance` or :class:`VoiceChannel` then
            it automatically sets the entity type.

            Required if ``entity_type`` is either :attr:`EntityType.voice` or
            :attr:`EntityType.stage_instance`.
        start_time: :class:`datetime.datetime`
            The scheduled start time of the scheduled event. This must be a timezone-aware
            datetime object. Consider using :func:`utils.utcnow`.
        end_time: :class:`datetime.datetime`
            The scheduled end time of the scheduled event. This must be a timezone-aware
            datetime object. Consider using :func:`utils.utcnow`.

            Required if the entity type is :attr:`EntityType.external`.
        privacy_level: :class:`PrivacyLevel`
            The privacy level of the scheduled event.
        entity_type: :class:`EntityType`
            The entity type of the scheduled event. If the channel is a
            :class:`StageInstance` or :class:`VoiceChannel` then this is
            automatically set to the appropriate entity type. If no channel
            is passed then the entity type is assumed to be
            :attr:`EntityType.external`
        image: :class:`bytes`
            The image of the scheduled event.
        location: :class:`str`
            The location of the scheduled event.

            Required if the ``entity_type`` is :attr:`EntityType.external`.
        reason: Optional[:class:`str`]
            The reason for creating this scheduled event. Shows up on the audit log.
        recurrence_rule: Optional[:class:`ScheduledEventRecurrenceRule`]
            The recurrence rule this event will follow. If this is ``None`` then this is
            a one-time event.

        Raises
        -------
        TypeError
            ``image`` was not a :term:`py:bytes-like object`, or ``privacy_level``
            was not a :class:`PrivacyLevel`, or ``entity_type`` was not an
            :class:`EntityType`, ``status`` was not an :class:`EventStatus`,
            or an argument was provided that was incompatible with the provided
            ``entity_type``.
        ValueError
            ``start_time`` or ``end_time`` was not a timezone-aware datetime object.
        Forbidden
            You are not allowed to create scheduled events.
        HTTPException
            Creating the scheduled event failed.

        Returns
        --------
        :class:`ScheduledEvent`
            The created scheduled event.
        """
        payload = {}
        metadata = {}

        payload['name'] = name

        if start_time is not MISSING:
            if start_time.tzinfo is None:
                raise ValueError(
                    'start_time must be an aware datetime. Consider using discord.utils.utcnow() or datetime.datetime.now().astimezone() for local time.'
                )
            payload['scheduled_start_time'] = start_time.isoformat()

        entity_type = entity_type or getattr(channel, '_scheduled_event_entity_type', MISSING)
        if entity_type is MISSING:
            if channel and isinstance(channel, Object):
                if channel.type is VoiceChannel:
                    entity_type = EntityType.voice
                elif channel.type is StageChannel:
                    entity_type = EntityType.stage_instance

            elif location not in (MISSING, None):
                entity_type = EntityType.external
        else:
            if not isinstance(entity_type, EntityType):
                raise TypeError('entity_type must be of type EntityType')

            payload['entity_type'] = entity_type.value

        if entity_type is None:
            raise TypeError(
                'invalid GuildChannel type passed, must be VoiceChannel or StageChannel ' f'not {channel.__class__.__name__}'
            )

        if privacy_level is not MISSING:
            if not isinstance(privacy_level, PrivacyLevel):
                raise TypeError('privacy_level must be of type PrivacyLevel.')

            payload['privacy_level'] = privacy_level.value

        if description is not MISSING:
            payload['description'] = description

        if image is not MISSING:
            image_as_str: str = utils._bytes_to_base64_data(image)
            payload['image'] = image_as_str

        if entity_type in (EntityType.stage_instance, EntityType.voice):
            if channel in (MISSING, None):
                raise TypeError('channel must be set when entity_type is voice or stage_instance')

            payload['channel_id'] = channel.id

            if location is not MISSING:
                raise TypeError('location cannot be set when entity_type is voice or stage_instance')
        else:
            if channel is not MISSING:
                raise TypeError('channel cannot be set when entity_type is external')

            if location is MISSING or location is None:
                raise TypeError('location must be set when entity_type is external')

            metadata['location'] = location

            if end_time in (MISSING, None):
                raise TypeError('end_time must be set when entity_type is external')

        if end_time not in (MISSING, None):
            if end_time.tzinfo is None:
                raise ValueError(
                    'end_time must be an aware datetime. Consider using discord.utils.utcnow() or datetime.datetime.now().astimezone() for local time.'
                )
            payload['scheduled_end_time'] = end_time.isoformat()

        if recurrence_rule is not MISSING:
            if recurrence_rule is not None:
                payload['recurrence_rule'] = recurrence_rule.to_dict()
            else:
                payload['recurrence_rule'] = None

        if metadata:
            payload['entity_metadata'] = metadata

        data = await self._state.http.create_guild_scheduled_event(self.id, **payload, reason=reason)
        return ScheduledEvent(state=self._state, data=data)

    async def fetch_emojis(self) -> List[Emoji]:
        r"""|coro|

        Retrieves all custom :class:`Emoji`\s from the guild.

        .. note::

            This method is an API call. For general usage, consider :attr:`emojis` instead.

        Raises
        ---------
        HTTPException
            An error occurred fetching the emojis.

        Returns
        --------
        List[:class:`Emoji`]
            The retrieved emojis.
        """
        data = await self._state.http.get_all_custom_emojis(self.id)
        return [Emoji(guild=self, state=self._state, data=d) for d in data]

    async def fetch_emoji(self, emoji_id: int, /) -> Emoji:
        """|coro|

        Retrieves a custom :class:`Emoji` from the guild.

        .. note::

            This method is an API call.
            For general usage, consider iterating over :attr:`emojis` instead.

        .. versionchanged:: 2.0

            ``emoji_id`` parameter is now positional-only.

        Parameters
        -------------
        emoji_id: :class:`int`
            The emoji's ID.

        Raises
        ---------
        NotFound
            The emoji requested could not be found.
        HTTPException
            An error occurred fetching the emoji.

        Returns
        --------
        :class:`Emoji`
            The retrieved emoji.
        """
        data = await self._state.http.get_custom_emoji(self.id, emoji_id)
        return Emoji(guild=self, state=self._state, data=data)

    async def create_custom_emoji(
        self,
        *,
        name: str,
        image: bytes,
        roles: Collection[Role] = MISSING,
        reason: Optional[str] = None,
    ) -> Emoji:
        r"""|coro|

        Creates a custom :class:`Emoji` for the guild.

        There is currently a limit of 50 static and animated emojis respectively per guild,
        unless the guild has the ``MORE_EMOJI`` feature which extends the limit to 200.

        You must have :attr:`~Permissions.manage_emojis` to do this.

        Parameters
        -----------
        name: :class:`str`
            The emoji name. Must be at least 2 characters.
        image: :class:`bytes`
            The :term:`py:bytes-like object` representing the image data to use.
            Only JPG, PNG and GIF images are supported.
        roles: List[:class:`Role`]
            A :class:`list` of :class:`Role`\s that can use this emoji. Leave empty to make it available to everyone.
        reason: Optional[:class:`str`]
            The reason for creating this emoji. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You are not allowed to create emojis.
        HTTPException
            An error occurred creating an emoji.

        Returns
        --------
        :class:`Emoji`
            The created emoji.
        """

        img = utils._bytes_to_base64_data(image)
        if roles:
            role_ids: SnowflakeList = [role.id for role in roles]
        else:
            role_ids = []

        data = await self._state.http.create_custom_emoji(self.id, name, img, roles=role_ids, reason=reason)
        if self._state.cache_guild_expressions:
            return self._state.store_emoji(self, data)
        else:
            return Emoji(guild=self, state=self._state, data=data)

    async def delete_emoji(self, emoji: Snowflake, /, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the custom :class:`Emoji` from the guild.

        You must have :attr:`~Permissions.manage_emojis` to do this.

        .. versionchanged:: 2.0

            ``emoji`` parameter is now positional-only.

        Parameters
        -----------
        emoji: :class:`abc.Snowflake`
            The emoji you are deleting.
        reason: Optional[:class:`str`]
            The reason for deleting this emoji. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You are not allowed to delete emojis.
        HTTPException
            An error occurred deleting the emoji.
        """

        await self._state.http.delete_custom_emoji(self.id, emoji.id, reason=reason)

    async def fetch_roles(self) -> List[Role]:
        """|coro|

        Retrieves all :class:`Role` that the guild has.

        .. note::

            This method is an API call. For general usage, consider :attr:`roles` instead.

        .. versionadded:: 1.3

        Raises
        -------
        HTTPException
            Retrieving the roles failed.

        Returns
        -------
        List[:class:`Role`]
            All roles in the guild.
        """
        data = await self._state.http.get_roles(self.id)
        return [Role(guild=self, state=self._state, data=d) for d in data]

    async def fetch_role(self, role_id: int, /) -> Role:
        """|coro|

        Retrieves a :class:`Role` with the specified ID.

        .. versionadded:: 2.5

        .. note::

            This method is an API call. For general usage, consider :attr:`get_role` instead.

        Parameters
        ----------
        role_id: :class:`int`
            The role's ID.

        Raises
        -------
        NotFound
            The role requested could not be found.
        HTTPException
            An error occurred fetching the role.

        Returns
        -------
        :class:`Role`
            The retrieved role.
        """
        data = await self._state.http.get_role(self.id, role_id)
        return Role(guild=self, state=self._state, data=data)

    @overload
    async def create_role(
        self,
        *,
        reason: Optional[str] = ...,
        name: str = ...,
        permissions: Permissions = ...,
        colour: Union[Colour, int] = ...,
        hoist: bool = ...,
        display_icon: Union[bytes, str] = MISSING,
        mentionable: bool = ...,
    ) -> Role:
        ...

    @overload
    async def create_role(
        self,
        *,
        reason: Optional[str] = ...,
        name: str = ...,
        permissions: Permissions = ...,
        color: Union[Colour, int] = ...,
        hoist: bool = ...,
        display_icon: Union[bytes, str] = MISSING,
        mentionable: bool = ...,
    ) -> Role:
        ...

    async def create_role(
        self,
        *,
        name: str = MISSING,
        permissions: Permissions = MISSING,
        color: Union[Colour, int] = MISSING,
        colour: Union[Colour, int] = MISSING,
        hoist: bool = MISSING,
        display_icon: Union[bytes, str] = MISSING,
        mentionable: bool = MISSING,
        reason: Optional[str] = None,
    ) -> Role:
        """|coro|

        Creates a :class:`Role` for the guild.

        All fields are optional.

        You must have :attr:`~Permissions.manage_roles` to do this.

        .. versionchanged:: 1.6
            Can now pass ``int`` to ``colour`` keyword-only parameter.

        .. versionadded:: 2.0
            The ``display_icon`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        -----------
        name: :class:`str`
            The role name. Defaults to 'new role'.
        permissions: :class:`Permissions`
            The permissions to have. Defaults to no permissions.
        colour: Union[:class:`Colour`, :class:`int`]
            The colour for the role. Defaults to :meth:`Colour.default`.
            This is aliased to ``color`` as well.
        hoist: :class:`bool`
            Indicates if the role should be shown separately in the member list.
            Defaults to ``False``.
        display_icon: Union[:class:`bytes`, :class:`str`]
            A :term:`py:bytes-like object` representing the icon
            or :class:`str` representing unicode emoji that should be used as a role icon.
            Only PNG/JPEG is supported.
            This is only available to guilds that contain ``ROLE_ICONS`` in :attr:`features`.
        mentionable: :class:`bool`
            Indicates if the role should be mentionable by others.
            Defaults to ``False``.
        reason: Optional[:class:`str`]
            The reason for creating this role. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permissions to create the role.
        HTTPException
            Creating the role failed.
        TypeError
            An invalid keyword argument was given.

        Returns
        --------
        :class:`Role`
            The newly created role.
        """
        fields: Dict[str, Any] = {}
        if permissions is not MISSING:
            fields['permissions'] = str(permissions.value)
        else:
            fields['permissions'] = '0'

        actual_colour = colour or color or Colour.default()
        if isinstance(actual_colour, int):
            fields['color'] = actual_colour
        else:
            fields['color'] = actual_colour.value

        if hoist is not MISSING:
            fields['hoist'] = hoist

        if display_icon is not MISSING:
            if isinstance(display_icon, bytes):
                fields['icon'] = utils._bytes_to_base64_data(display_icon)
            else:
                fields['unicode_emoji'] = display_icon

        if mentionable is not MISSING:
            fields['mentionable'] = mentionable

        if name is not MISSING:
            fields['name'] = name

        data = await self._state.http.create_role(self.id, reason=reason, **fields)
        role = Role(guild=self, data=data, state=self._state)

        return role

    async def edit_role_positions(self, positions: Mapping[Snowflake, int], *, reason: Optional[str] = None) -> List[Role]:
        """|coro|

        Bulk edits a list of :class:`Role` in the guild.

        You must have :attr:`~Permissions.manage_roles` to do this.

        .. versionadded:: 1.4

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Example
        ----------

        .. code-block:: python3

            positions = {
                bots_role: 1, # penultimate role
                tester_role: 2,
                admin_role: 6
            }

            await guild.edit_role_positions(positions=positions)

        Parameters
        -----------
        positions
            A :class:`dict` of :class:`Role` to :class:`int` to change the positions
            of each given role.
        reason: Optional[:class:`str`]
            The reason for editing the role positions. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permissions to move the roles.
        HTTPException
            Moving the roles failed.
        TypeError
            An invalid keyword argument was given.

        Returns
        --------
        List[:class:`Role`]
            A list of all the roles in the guild.
        """
        if not isinstance(positions, Mapping):
            raise TypeError('positions parameter expects a dict.')

        role_positions = []
        for role, position in positions.items():
            payload: RolePositionUpdatePayload = {'id': role.id, 'position': position}

            role_positions.append(payload)

        data = await self._state.http.move_role_position(self.id, role_positions, reason=reason)
        roles: List[Role] = []
        for d in data:
            role = Role(guild=self, data=d, state=self._state)
            roles.append(role)
            self._roles[role.id] = role

        return roles

    async def welcome_screen(self) -> WelcomeScreen:
        """|coro|

        Returns the guild's welcome screen.

        The guild must have ``COMMUNITY`` in :attr:`~Guild.features`.

        You must have :attr:`~Permissions.manage_guild` to do this.as well.

        .. versionadded:: 2.0

        Raises
        -------
        Forbidden
            You do not have the proper permissions to get this.
        HTTPException
            Retrieving the welcome screen failed.

        Returns
        --------
        :class:`WelcomeScreen`
            The welcome screen.
        """
        data = await self._state.http.get_welcome_screen(self.id)
        return WelcomeScreen(data=data, guild=self)

    async def edit_welcome_screen(
        self,
        *,
        description: str = MISSING,
        welcome_channels: List[WelcomeChannel] = MISSING,
        enabled: bool = MISSING,
        reason: Optional[str] = None,
    ) -> WelcomeScreen:
        """|coro|

        A shorthand method of :attr:`WelcomeScreen.edit` without needing
        to fetch the welcome screen beforehand.

        The guild must have ``COMMUNITY`` in :attr:`~Guild.features`.

        You must have :attr:`~Permissions.manage_guild` to do this as well.

        .. versionadded:: 2.0

        Returns
        --------
        :class:`WelcomeScreen`
            The edited welcome screen.
        """
        fields = {}

        if welcome_channels is not MISSING:
            welcome_channels_serialised = []
            for wc in welcome_channels:
                if not isinstance(wc, WelcomeChannel):
                    raise TypeError('welcome_channels parameter must be a list of WelcomeChannel')
                welcome_channels_serialised.append(wc.to_dict())
            fields['welcome_channels'] = welcome_channels_serialised

        if description is not MISSING:
            fields['description'] = description

        if enabled is not MISSING:
            fields['enabled'] = enabled

        data = await self._state.http.edit_welcome_screen(self.id, reason=reason, **fields)
        return WelcomeScreen(data=data, guild=self)

    async def kick(self, user: Snowflake, *, reason: Optional[str] = None) -> None:
        """|coro|

        Kicks a user from the guild.

        The user must meet the :class:`abc.Snowflake` abc.

        You must have :attr:`~Permissions.kick_members` to do this.

        Parameters
        -----------
        user: :class:`abc.Snowflake`
            The user to kick from the guild.
        reason: Optional[:class:`str`]
            The reason the user got kicked.

        Raises
        -------
        Forbidden
            You do not have the proper permissions to kick.
        HTTPException
            Kicking failed.
        """
        await self._state.http.kick(user.id, self.id, reason=reason)

    async def ban(
        self,
        user: Snowflake,
        *,
        reason: Optional[str] = None,
        delete_message_days: int = MISSING,
        delete_message_seconds: int = MISSING,
    ) -> None:
        """|coro|

        Bans a user from the guild.

        The user must meet the :class:`abc.Snowflake` abc.

        You must have :attr:`~Permissions.ban_members` to do this.

        Parameters
        -----------
        user: :class:`abc.Snowflake`
            The user to ban from the guild.
        delete_message_days: :class:`int`
            The number of days worth of messages to delete from the user
            in the guild. The minimum is 0 and the maximum is 7.
            Defaults to 1 day if neither ``delete_message_days`` nor
            ``delete_message_seconds`` are passed.

            .. deprecated:: 2.1
        delete_message_seconds: :class:`int`
            The number of seconds worth of messages to delete from the user
            in the guild. The minimum is 0 and the maximum is 604800 (7 days).
            Defaults to 1 day if neither ``delete_message_days`` nor
            ``delete_message_seconds`` are passed.

            .. versionadded:: 2.1
        reason: Optional[:class:`str`]
            The reason the user got banned.

        Raises
        -------
        NotFound
            The requested user was not found.
        Forbidden
            You do not have the proper permissions to ban.
        HTTPException
            Banning failed.
        TypeError
            You specified both ``delete_message_days`` and ``delete_message_seconds``.
        """
        if delete_message_days is not MISSING and delete_message_seconds is not MISSING:
            raise TypeError('Cannot mix delete_message_days and delete_message_seconds keyword arguments.')

        if delete_message_days is not MISSING:
            msg = 'delete_message_days is deprecated, use delete_message_seconds instead'
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            delete_message_seconds = delete_message_days * 86400  # one day

        if delete_message_seconds is MISSING:
            delete_message_seconds = 86400  # one day

        await self._state.http.ban(user.id, self.id, delete_message_seconds, reason=reason)

    async def unban(self, user: Snowflake, *, reason: Optional[str] = None) -> None:
        """|coro|

        Unbans a user from the guild.

        The user must meet the :class:`abc.Snowflake` abc.

        You must have :attr:`~Permissions.ban_members` to do this.

        Parameters
        -----------
        user: :class:`abc.Snowflake`
            The user to unban.
        reason: Optional[:class:`str`]
            The reason for doing this action. Shows up on the audit log.

        Raises
        -------
        NotFound
            The requested unban was not found.
        Forbidden
            You do not have the proper permissions to unban.
        HTTPException
            Unbanning failed.
        """
        await self._state.http.unban(user.id, self.id, reason=reason)

    async def bulk_ban(
        self,
        users: Iterable[Snowflake],
        *,
        reason: Optional[str] = None,
        delete_message_seconds: int = 86400,
    ) -> BulkBanResult:
        """|coro|

        Bans multiple users from the guild.

        The users must meet the :class:`abc.Snowflake` abc.

        You must have :attr:`~Permissions.ban_members` and :attr:`~Permissions.manage_guild` to do this.

        .. versionadded:: 2.4

        Parameters
        -----------
        users: Iterable[:class:`abc.Snowflake`]
            The users to ban from the guild, up to 200 users.
        delete_message_seconds: :class:`int`
            The number of seconds worth of messages to delete from the user
            in the guild. The minimum is 0 and the maximum is 604800 (7 days).
            Defaults to 1 day.
        reason: Optional[:class:`str`]
            The reason the users got banned.

        Raises
        -------
        Forbidden
            You do not have the proper permissions to ban.
        HTTPException
            Banning failed.

        Returns
        --------
        :class:`BulkBanResult`
            The result of the bulk ban operation.
        """

        response = await self._state.http.bulk_ban(
            self.id,
            user_ids=[u.id for u in users],
            delete_message_seconds=delete_message_seconds,
            reason=reason,
        )
        return BulkBanResult(
            banned=[Object(id=int(user_id), type=User) for user_id in response.get('banned_users', []) or []],
            failed=[Object(id=int(user_id), type=User) for user_id in response.get('failed_users', []) or []],
        )

    @property
    def vanity_url(self) -> Optional[str]:
        """Optional[:class:`str`]: The Discord vanity invite URL for this guild, if available.

        .. versionadded:: 2.0
        """
        if self.vanity_url_code is None:
            return None
        return f'{Invite.BASE}/{self.vanity_url_code}'

    async def vanity_invite(self) -> Optional[Invite]:
        """|coro|

        Returns the guild's special vanity invite.

        The guild must have ``VANITY_URL`` in :attr:`~Guild.features`.

        You must have :attr:`~Permissions.manage_guild` to do this as well.

        Raises
        -------
        Forbidden
            You do not have the proper permissions to get this.
        HTTPException
            Retrieving the vanity invite failed.

        Returns
        --------
        Optional[:class:`Invite`]
            The special vanity invite. If ``None`` then the guild does not
            have a vanity invite set.
        """

        # we start with { code: abc }
        payload = await self._state.http.get_vanity_code(self.id)
        if not payload['code']:
            return None

        # get the vanity URL channel since default channels aren't
        # reliable or a thing anymore
        data = await self._state.http.get_invite(payload['code'])

        channel = self.get_channel(int(data['channel']['id']))
        payload['revoked'] = False
        payload['temporary'] = False
        payload['max_uses'] = 0
        payload['max_age'] = 0
        payload['uses'] = payload.get('uses', 0)
        return Invite(state=self._state, data=payload, guild=self, channel=channel)  # type: ignore # we're faking a payload here

    async def audit_logs(
        self,
        *,
        limit: Optional[int] = 100,
        before: SnowflakeTime = MISSING,
        after: SnowflakeTime = MISSING,
        oldest_first: bool = MISSING,
        user: Snowflake = MISSING,
        action: AuditLogAction = MISSING,
    ) -> AsyncIterator[AuditLogEntry]:
        """Returns an :term:`asynchronous iterator` that enables receiving the guild's audit logs.

        You must have :attr:`~Permissions.view_audit_log` to do this.

        Examples
        ----------

        Getting the first 100 entries: ::

            async for entry in guild.audit_logs(limit=100):
                print(f'{entry.user} did {entry.action} to {entry.target}')

        Getting entries for a specific action: ::

            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                print(f'{entry.user} banned {entry.target}')

        Getting entries made by a specific user: ::

            entries = [entry async for entry in guild.audit_logs(limit=None, user=guild.me)]
            await channel.send(f'I made {len(entries)} moderation actions.')

        Parameters
        -----------
        limit: Optional[:class:`int`]
            The number of entries to retrieve. If ``None`` retrieve all entries.
        before: Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]
            Retrieve entries before this date or entry.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        after: Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]
            Retrieve entries after this date or entry.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        oldest_first: :class:`bool`
            If set to ``True``, return entries in oldest->newest order. Defaults to ``True`` if
            ``after`` is specified, otherwise ``False``.
        user: :class:`abc.Snowflake`
            The moderator to filter entries from.
        action: :class:`AuditLogAction`
            The action to filter with.

        Raises
        -------
        Forbidden
            You are not allowed to fetch audit logs
        HTTPException
            An error occurred while fetching the audit logs.

        Yields
        --------
        :class:`AuditLogEntry`
            The audit log entry.
        """

        async def _before_strategy(retrieve: int, before: Optional[Snowflake], limit: Optional[int]):
            before_id = before.id if before else None
            data = await self._state.http.get_audit_logs(
                self.id, limit=retrieve, user_id=user_id, action_type=action_type, before=before_id
            )

            entries = data.get('audit_log_entries', [])

            if data and entries:
                if limit is not None:
                    limit -= len(entries)

                before = Object(id=int(entries[-1]['id']))

            return data, entries, before, limit

        async def _after_strategy(retrieve: int, after: Optional[Snowflake], limit: Optional[int]):
            after_id = after.id if after else None
            data = await self._state.http.get_audit_logs(
                self.id, limit=retrieve, user_id=user_id, action_type=action_type, after=after_id
            )

            entries = data.get('audit_log_entries', [])

            if data and entries:
                if limit is not None:
                    limit -= len(entries)

                after = Object(id=int(entries[-1]['id']))

            return data, entries, after, limit

        if user is not MISSING:
            user_id = user.id
        else:
            user_id = None

        if action is not MISSING:
            action_type: Optional[AuditLogEvent] = action.value
        else:
            action_type = None

        if isinstance(before, datetime.datetime):
            before = Object(id=utils.time_snowflake(before, high=False))
        if isinstance(after, datetime.datetime):
            after = Object(id=utils.time_snowflake(after, high=True))

        if oldest_first:
            if after is MISSING:
                after = OLDEST_OBJECT

        predicate = None

        if oldest_first:
            strategy, state = _after_strategy, after
            if before:
                predicate = lambda m: int(m['id']) < before.id
        else:
            strategy, state = _before_strategy, before
            if after:
                predicate = lambda m: int(m['id']) > after.id

        # avoid circular import
        from .app_commands import AppCommand
        from .webhook import Webhook

        while True:
            retrieve = 100 if limit is None else min(limit, 100)
            if retrieve < 1:
                return

            data, raw_entries, state, limit = await strategy(retrieve, state, limit)

            if predicate:
                raw_entries = filter(predicate, raw_entries)

            users = (User(data=raw_user, state=self._state) for raw_user in data.get('users', []))
            user_map = {user.id: user for user in users}

            integrations = (PartialIntegration(data=raw_i, guild=self) for raw_i in data.get('integrations', []))
            integration_map = {integration.id: integration for integration in integrations}

            app_commands = (AppCommand(data=raw_cmd, state=self._state) for raw_cmd in data.get('application_commands', []))
            app_command_map = {app_command.id: app_command for app_command in app_commands}

            automod_rules = (
                AutoModRule(data=raw_rule, guild=self, state=self._state)
                for raw_rule in data.get('auto_moderation_rules', [])
            )
            automod_rule_map = {rule.id: rule for rule in automod_rules}

            webhooks = (Webhook.from_state(data=raw_webhook, state=self._state) for raw_webhook in data.get('webhooks', []))
            webhook_map = {webhook.id: webhook for webhook in webhooks}

            count = 0

            for count, raw_entry in enumerate(raw_entries, 1):
                # Weird Discord quirk
                if raw_entry['action_type'] is None:
                    continue

                yield AuditLogEntry(
                    data=raw_entry,
                    users=user_map,
                    integrations=integration_map,
                    app_commands=app_command_map,
                    automod_rules=automod_rule_map,
                    webhooks=webhook_map,
                    guild=self,
                )

            if count < 100:
                # There's no data left after this
                break

    async def widget(self) -> Widget:
        """|coro|

        Returns the widget of the guild.

        .. note::

            The guild must have the widget enabled to get this information.

        Raises
        -------
        Forbidden
            The widget for this guild is disabled.
        HTTPException
            Retrieving the widget failed.

        Returns
        --------
        :class:`Widget`
            The guild's widget.
        """
        data = await self._state.http.get_widget(self.id)

        return Widget(state=self._state, data=data)

    async def edit_widget(
        self,
        *,
        enabled: bool = MISSING,
        channel: Optional[Snowflake] = MISSING,
        reason: Optional[str] = None,
    ) -> None:
        """|coro|

        Edits the widget of the guild. This can also be done with :attr:`~Guild.edit`.

        You must have :attr:`~Permissions.manage_guild` to do this.

        .. versionadded:: 2.0

        Parameters
        -----------
        enabled: :class:`bool`
            Whether to enable the widget for the guild.
        channel: Optional[:class:`~discord.abc.Snowflake`]
            The new widget channel. ``None`` removes the widget channel.
        reason: Optional[:class:`str`]
            The reason for editing this widget. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permission to edit the widget.
        HTTPException
            Editing the widget failed.
        """
        payload: EditWidgetSettings = {}
        if channel is not MISSING:
            payload['channel_id'] = None if channel is None else channel.id
        if enabled is not MISSING:
            payload['enabled'] = enabled

        if payload:
            await self._state.http.edit_widget(self.id, payload=payload, reason=reason)

    async def chunk(self, *, cache: bool = True) -> List[Member]:
        """|coro|

        Requests all members that belong to this guild. In order to use this,
        :meth:`Intents.members` must be enabled.

        This is a websocket operation and can be slow.

        .. versionadded:: 1.5

        Parameters
        -----------
        cache: :class:`bool`
            Whether to cache the members as well.

        Raises
        -------
        ClientException
            The members intent is not enabled.

        Returns
        --------
        List[:class:`Member`]
            The list of members in the guild.
        """

        if not self._state._intents.members:
            raise ClientException('Intents.members must be enabled to use this.')

        if not self._state.is_guild_evicted(self):
            return await self._state.chunk_guild(self, cache=cache)

        return []

    async def query_members(
        self,
        query: Optional[str] = None,
        *,
        limit: int = 5,
        user_ids: Optional[List[int]] = None,
        presences: bool = False,
        cache: bool = True,
    ) -> List[Member]:
        """|coro|

        Request members of this guild whose username or nickname starts with the given query.
        This is a websocket operation.

        .. versionadded:: 1.3

        Parameters
        -----------
        query: Optional[:class:`str`]
            The string that the username or nickname should start with.
        limit: :class:`int`
            The maximum number of members to send back. This must be
            a number between 5 and 100.
        presences: :class:`bool`
            Whether to request for presences to be provided. This defaults
            to ``False``.

            .. versionadded:: 1.6

        cache: :class:`bool`
            Whether to cache the members internally. This makes operations
            such as :meth:`get_member` work for those that matched.
        user_ids: Optional[List[:class:`int`]]
            List of user IDs to search for. If the user ID is not in the guild then it won't be returned.

            .. versionadded:: 1.4


        Raises
        -------
        asyncio.TimeoutError
            The query timed out waiting for the members.
        ValueError
            Invalid parameters were passed to the function
        ClientException
            The presences intent is not enabled.

        Returns
        --------
        List[:class:`Member`]
            The list of members that have matched the query.
        """

        if presences and not self._state._intents.presences:
            raise ClientException('Intents.presences must be enabled to use this.')

        if query == '':
            raise ValueError('Cannot pass empty query string.')

        if query is None and user_ids is None:
            raise ValueError('Must pass either query or user_ids')

        if user_ids is not None and query is not None:
            raise ValueError('Cannot pass both query and user_ids')

        if user_ids is not None and not user_ids:
            raise ValueError('user_ids must contain at least 1 value')

        limit = min(100, limit or 5)
        return await self._state.query_members(
            self, query=query, limit=limit, user_ids=user_ids, presences=presences, cache=cache
        )

    async def change_voice_state(
        self, *, channel: Optional[abc.Snowflake], self_mute: bool = False, self_deaf: bool = False
    ) -> None:
        """|coro|

        Changes client's voice state in the guild.

        .. versionadded:: 1.4

        Parameters
        -----------
        channel: Optional[:class:`abc.Snowflake`]
            Channel the client wants to join. Use ``None`` to disconnect.
        self_mute: :class:`bool`
            Indicates if the client should be self-muted.
        self_deaf: :class:`bool`
            Indicates if the client should be self-deafened.
        """
        ws = self._state._get_websocket(self.id)
        channel_id = channel.id if channel else None
        await ws.voice_state(self.id, channel_id, self_mute, self_deaf)

    async def fetch_automod_rule(self, automod_rule_id: int, /) -> AutoModRule:
        """|coro|

        Fetches an active automod rule from the guild.

        You must have :attr:`Permissions.manage_guild` to do this.

        .. versionadded:: 2.0

        Parameters
        -----------
        automod_rule_id: :class:`int`
            The ID of the automod rule to fetch.

        Raises
        -------
        Forbidden
            You do not have permission to view the automod rule.
        NotFound
            The automod rule does not exist within this guild.

        Returns
        --------
        :class:`AutoModRule`
            The automod rule that was fetched.
        """

        data = await self._state.http.get_auto_moderation_rule(self.id, automod_rule_id)

        return AutoModRule(data=data, guild=self, state=self._state)

    async def fetch_automod_rules(self) -> List[AutoModRule]:
        """|coro|

        Fetches all automod rules from the guild.

        You must have :attr:`Permissions.manage_guild` to do this.

        .. versionadded:: 2.0

        Raises
        -------
        Forbidden
            You do not have permission to view the automod rule.
        NotFound
            There are no automod rules within this guild.

        Returns
        --------
        List[:class:`AutoModRule`]
            The automod rules that were fetched.
        """
        data = await self._state.http.get_auto_moderation_rules(self.id)

        return [AutoModRule(data=d, guild=self, state=self._state) for d in data]

    async def create_automod_rule(
        self,
        *,
        name: str,
        event_type: AutoModRuleEventType,
        trigger: AutoModTrigger,
        actions: List[AutoModRuleAction],
        enabled: bool = False,
        exempt_roles: Sequence[Snowflake] = MISSING,
        exempt_channels: Sequence[Snowflake] = MISSING,
        reason: str = MISSING,
    ) -> AutoModRule:
        """|coro|

        Create an automod rule.

        You must have :attr:`Permissions.manage_guild` to do this.

        .. versionadded:: 2.0

        Parameters
        -----------
        name: :class:`str`
            The name of the automod rule.
        event_type: :class:`AutoModRuleEventType`
            The type of event that the automod rule will trigger on.
        trigger: :class:`AutoModTrigger`
            The trigger that will trigger the automod rule.
        actions: List[:class:`AutoModRuleAction`]
            The actions that will be taken when the automod rule is triggered.
        enabled: :class:`bool`
            Whether the automod rule is enabled.
            Defaults to ``False``.
        exempt_roles: Sequence[:class:`abc.Snowflake`]
            A list of roles that will be exempt from the automod rule.
        exempt_channels: Sequence[:class:`abc.Snowflake`]
            A list of channels that will be exempt from the automod rule.
        reason: :class:`str`
            The reason for creating this automod rule. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permissions to create an automod rule.
        HTTPException
            Creating the automod rule failed.

        Returns
        --------
        :class:`AutoModRule`
            The automod rule that was created.
        """
        data = await self._state.http.create_auto_moderation_rule(
            self.id,
            name=name,
            event_type=event_type.value,
            trigger_type=trigger.type.value,
            trigger_metadata=trigger.to_metadata_dict() or None,
            actions=[a.to_dict() for a in actions],
            enabled=enabled,
            exempt_roles=[str(r.id) for r in exempt_roles] if exempt_roles else None,
            exempt_channels=[str(c.id) for c in exempt_channels] if exempt_channels else None,
            reason=reason,
        )

        return AutoModRule(data=data, guild=self, state=self._state)

    @property
    def invites_paused_until(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: If invites are paused, returns when
        invites will get enabled in UTC, otherwise returns None.

        .. versionadded:: 2.4
        """
        if not self._incidents_data:
            return None

        return utils.parse_time(self._incidents_data.get('invites_disabled_until'))

    @property
    def dms_paused_until(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: If DMs are paused, returns when DMs
        will get enabled in UTC, otherwise returns None.

        .. versionadded:: 2.4
        """
        if not self._incidents_data:
            return None

        return utils.parse_time(self._incidents_data.get('dms_disabled_until'))

    @property
    def dm_spam_detected_at(self) -> Optional[datetime.datetime]:
        """:class:`datetime.datetime`: Returns the time when DM spam was detected in the guild.

        .. versionadded:: 2.5
        """
        if not self._incidents_data:
            return None

        return utils.parse_time(self._incidents_data.get('dm_spam_detected_at'))

    @property
    def raid_detected_at(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: Returns the time when a raid was detected in the guild.

        .. versionadded:: 2.5
        """
        if not self._incidents_data:
            return None

        return utils.parse_time(self._incidents_data.get('raid_detected_at'))

    def invites_paused(self) -> bool:
        """:class:`bool`: Whether invites are paused in the guild.

        .. versionadded:: 2.4
        """
        if not self.invites_paused_until:
            return 'INVITES_DISABLED' in self.features

        return self.invites_paused_until > utils.utcnow()

    def dms_paused(self) -> bool:
        """:class:`bool`: Whether DMs are paused in the guild.

        .. versionadded:: 2.4
        """
        if not self.dms_paused_until:
            return False

        return self.dms_paused_until > utils.utcnow()

    def is_dm_spam_detected(self) -> bool:
        """:class:`bool`: Whether DM spam was detected in the guild.

        .. versionadded:: 2.5
        """
        if not self.dm_spam_detected_at:
            return False

        return self.dm_spam_detected_at > utils.utcnow()

    def is_raid_detected(self) -> bool:
        """:class:`bool`: Whether a raid was detected in the guild.

        .. versionadded:: 2.5
        """
        if not self.raid_detected_at:
            return False

        return self.raid_detected_at > utils.utcnow()

    async def fetch_soundboard_sound(self, sound_id: int, /) -> SoundboardSound:
        """|coro|

        Retrieves a :class:`SoundboardSound` with the specified ID.

        .. versionadded:: 2.5

        .. note::

            Using this, in order to receive :attr:`SoundboardSound.user`, you must have :attr:`~Permissions.create_expressions`
            or :attr:`~Permissions.manage_expressions`.

        .. note::

            This method is an API call. For general usage, consider :attr:`get_soundboard_sound` instead.

        Raises
        -------
        NotFound
            The sound requested could not be found.
        HTTPException
            Retrieving the sound failed.

        Returns
        --------
        :class:`SoundboardSound`
            The retrieved sound.
        """
        data = await self._state.http.get_soundboard_sound(self.id, sound_id)
        return SoundboardSound(guild=self, state=self._state, data=data)

    async def fetch_soundboard_sounds(self) -> List[SoundboardSound]:
        """|coro|

        Retrieves a list of all soundboard sounds for the guild.

        .. versionadded:: 2.5

        .. note::

            Using this, in order to receive :attr:`SoundboardSound.user`, you must have :attr:`~Permissions.create_expressions`
            or :attr:`~Permissions.manage_expressions`.

        .. note::

            This method is an API call. For general usage, consider :attr:`soundboard_sounds` instead.

        Raises
        -------
        HTTPException
            Retrieving the sounds failed.

        Returns
        --------
        List[:class:`SoundboardSound`]
            The retrieved soundboard sounds.
        """
        data = await self._state.http.get_soundboard_sounds(self.id)
        return [SoundboardSound(guild=self, state=self._state, data=sound) for sound in data['items']]

    async def create_soundboard_sound(
        self,
        *,
        name: str,
        sound: bytes,
        volume: float = 1,
        emoji: Optional[EmojiInputType] = None,
        reason: Optional[str] = None,
    ) -> SoundboardSound:
        """|coro|

        Creates a :class:`SoundboardSound` for the guild.
        You must have :attr:`Permissions.create_expressions` to do this.

        .. versionadded:: 2.5

        Parameters
        ----------
        name: :class:`str`
            The name of the sound. Must be between 2 and 32 characters.
        sound: :class:`bytes`
            The :term:`py:bytes-like object` representing the sound data.
            Only MP3 and OGG sound files that don't exceed the duration of 5.2s are supported.
        volume: :class:`float`
            The volume of the sound. Must be between 0 and 1. Defaults to ``1``.
        emoji: Optional[Union[:class:`Emoji`, :class:`PartialEmoji`, :class:`str`]]
            The emoji of the sound.
        reason: Optional[:class:`str`]
            The reason for creating the sound. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permissions to create a soundboard sound.
        HTTPException
            Creating the soundboard sound failed.

        Returns
        -------
        :class:`SoundboardSound`
            The newly created soundboard sound.
        """
        payload: Dict[str, Any] = {
            'name': name,
            'sound': utils._bytes_to_base64_data(sound, audio=True),
            'volume': volume,
            'emoji_id': None,
            'emoji_name': None,
        }

        if emoji is not None:
            if isinstance(emoji, _EmojiTag):
                partial_emoji = emoji._to_partial()
            elif isinstance(emoji, str):
                partial_emoji = PartialEmoji.from_str(emoji)
            else:
                partial_emoji = None

            if partial_emoji is not None:
                if partial_emoji.id is None:
                    payload['emoji_name'] = partial_emoji.name
                else:
                    payload['emoji_id'] = partial_emoji.id

        data = await self._state.http.create_soundboard_sound(self.id, reason=reason, **payload)
        return SoundboardSound(guild=self, state=self._state, data=data)
