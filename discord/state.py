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

import asyncio
from collections import deque, OrderedDict
import copy
import logging
from typing import (
    Dict,
    Optional,
    TYPE_CHECKING,
    Type,
    Union,
    Callable,
    Any,
    List,
    TypeVar,
    Coroutine,
    Sequence,
    Generic,
    Tuple,
    Deque,
    Literal,
    overload,
)
import weakref
import inspect

import os

from .guild import Guild
from .activity import BaseActivity
from .sku import Entitlement
from .user import User, ClientUser
from .emoji import Emoji
from .mentions import AllowedMentions
from .partial_emoji import PartialEmoji
from .message import Message
from .channel import *
from .channel import _channel_factory
from .raw_models import *
from .member import Member
from .role import Role
from .enums import ChannelType, try_enum, Status
from . import utils
from .flags import ApplicationFlags, Intents, MemberCacheFlags
from .invite import Invite
from .integrations import _integration_factory
from .interactions import Interaction
from .ui.view import ViewStore, View
from .scheduled_event import ScheduledEvent
from .stage_instance import StageInstance
from .threads import Thread, ThreadMember
from .sticker import GuildSticker
from .automod import AutoModRule, AutoModAction
from .audit_logs import AuditLogEntry
from ._types import ClientT
from .soundboard import SoundboardSound
from .subscription import Subscription


if TYPE_CHECKING:
    from .abc import PrivateChannel
    from .message import MessageableChannel
    from .guild import GuildChannel
    from .http import HTTPClient
    from .voice_client import VoiceProtocol
    from .gateway import DiscordWebSocket
    from .ui.item import Item
    from .ui.dynamic import DynamicItem
    from .app_commands import CommandTree, Translator
    from .poll import Poll

    from .types.automod import AutoModerationRule, AutoModerationActionExecution
    from .types.snowflake import Snowflake
    from .types.activity import Activity as ActivityPayload
    from .types.channel import DMChannel as DMChannelPayload
    from .types.user import User as UserPayload, PartialUser as PartialUserPayload
    from .types.emoji import Emoji as EmojiPayload, PartialEmoji as PartialEmojiPayload
    from .types.sticker import GuildSticker as GuildStickerPayload
    from .types.guild import Guild as GuildPayload
    from .types.message import Message as MessagePayload, PartialMessage as PartialMessagePayload
    from .types import gateway as gw
    from .types.command import GuildApplicationCommandPermissions as GuildApplicationCommandPermissionsPayload

    T = TypeVar('T')
    Channel = Union[GuildChannel, PrivateChannel, PartialMessageable]


class ChunkRequest:
    def __init__(
        self,
        guild_id: int,
        shard_id: int,
        loop: asyncio.AbstractEventLoop,
        resolver: Callable[[int], Any],
        *,
        cache: bool = True,
    ) -> None:
        self.guild_id: int = guild_id
        self.shard_id: int = shard_id
        self.resolver: Callable[[int], Any] = resolver
        self.loop: asyncio.AbstractEventLoop = loop
        self.cache: bool = cache
        self.nonce: str = os.urandom(16).hex()
        self.buffer: List[Member] = []
        self.waiters: List[asyncio.Future[List[Member]]] = []

    def add_members(self, members: List[Member]) -> None:
        self.buffer.extend(members)
        if self.cache:
            guild = self.resolver(self.guild_id)
            if guild is None:
                return

            for member in members:
                existing = guild.get_member(member.id)
                if existing is None or existing.joined_at is None:
                    guild._add_member(member)

    async def wait(self) -> List[Member]:
        future = self.loop.create_future()
        self.waiters.append(future)
        try:
            return await future
        finally:
            self.waiters.remove(future)

    def get_future(self) -> asyncio.Future[List[Member]]:
        future = self.loop.create_future()
        self.waiters.append(future)
        return future

    def done(self) -> None:
        for future in self.waiters:
            if not future.done():
                future.set_result(self.buffer)


_log = logging.getLogger(__name__)


async def logging_coroutine(coroutine: Coroutine[Any, Any, T], *, info: str) -> Optional[T]:
    try:
        await coroutine
    except Exception:
        _log.exception('Exception occurred during %s', info)


class ConnectionState(Generic[ClientT]):
    if TYPE_CHECKING:
        _get_websocket: Callable[..., DiscordWebSocket]
        _get_client: Callable[..., ClientT]
        _parsers: Dict[str, Callable[[Dict[str, Any]], None]]

    def __init__(
        self,
        *,
        dispatch: Callable[..., Any],
        handlers: Dict[str, Callable[..., Any]],
        hooks: Dict[str, Callable[..., Coroutine[Any, Any, Any]]],
        http: HTTPClient,
        **options: Any,
    ) -> None:
        # Set later, after Client.login
        self.loop: asyncio.AbstractEventLoop = utils.MISSING
        self.http: HTTPClient = http
        self.max_messages: Optional[int] = options.get('max_messages', 1000)
        if self.max_messages is not None and self.max_messages <= 0:
            self.max_messages = 1000

        self.dispatch: Callable[..., Any] = dispatch
        self.handlers: Dict[str, Callable[..., Any]] = handlers
        self.hooks: Dict[str, Callable[..., Coroutine[Any, Any, Any]]] = hooks
        self.shard_count: Optional[int] = None
        self._ready_task: Optional[asyncio.Task] = None
        self.application_id: Optional[int] = utils._get_as_snowflake(options, 'application_id')
        self.application_flags: ApplicationFlags = utils.MISSING
        self.heartbeat_timeout: float = options.get('heartbeat_timeout', 60.0)
        self.guild_ready_timeout: float = options.get('guild_ready_timeout', 2.0)
        if self.guild_ready_timeout < 0:
            raise ValueError('guild_ready_timeout cannot be negative')

        allowed_mentions = options.get('allowed_mentions')

        if allowed_mentions is not None and not isinstance(allowed_mentions, AllowedMentions):
            raise TypeError('allowed_mentions parameter must be AllowedMentions')

        self.allowed_mentions: Optional[AllowedMentions] = allowed_mentions
        self._chunk_requests: Dict[Union[int, str], ChunkRequest] = {}

        activity = options.get('activity', None)
        if activity:
            if not isinstance(activity, BaseActivity):
                raise TypeError('activity parameter must derive from BaseActivity.')

            activity = activity.to_dict()

        status = options.get('status', None)
        if status:
            if status is Status.offline:
                status = 'invisible'
            else:
                status = str(status)

        intents = options.get('intents', None)
        if intents is not None:
            if not isinstance(intents, Intents):
                raise TypeError(f'intents parameter must be Intent not {type(intents)!r}')
        else:
            intents = Intents.default()

        if not intents.guilds:
            _log.warning('Guilds intent seems to be disabled. This may cause state related issues.')

        self._chunk_guilds: bool = options.get('chunk_guilds_at_startup', intents.members)

        # Ensure these two are set properly
        if not intents.members and self._chunk_guilds:
            raise ValueError('Intents.members must be enabled to chunk guilds at startup.')

        cache_flags = options.get('member_cache_flags', None)
        if cache_flags is None:
            cache_flags = MemberCacheFlags.from_intents(intents)
        else:
            if not isinstance(cache_flags, MemberCacheFlags):
                raise TypeError(f'member_cache_flags parameter must be MemberCacheFlags not {type(cache_flags)!r}')

            cache_flags._verify_intents(intents)

        self.member_cache_flags: MemberCacheFlags = cache_flags
        self._activity: Optional[ActivityPayload] = activity
        self._status: Optional[str] = status
        self._intents: Intents = intents
        self._command_tree: Optional[CommandTree] = None
        self._translator: Optional[Translator] = None

        if not intents.members or cache_flags._empty:
            self.store_user = self.store_user_no_intents

        self.parsers: Dict[str, Callable[[Any], None]]
        self.parsers = parsers = {}
        for attr, func in inspect.getmembers(self):
            if attr.startswith('parse_'):
                parsers[attr[6:].upper()] = func

        self.clear()

    # For some reason Discord still sends emoji/sticker data in payloads
    # This makes it hard to actually swap out the appropriate store methods
    # So this is checked instead, it's a small penalty to pay
    @property
    def cache_guild_expressions(self) -> bool:
        return self._intents.emojis_and_stickers

    async def close(self) -> None:
        for voice in self.voice_clients:
            try:
                await voice.disconnect(force=True)
            except Exception:
                # if an error happens during disconnects, disregard it.
                pass

        if self._translator:
            await self._translator.unload()

        # Purposefully don't call `clear` because users rely on cache being available post-close

    def clear(self, *, views: bool = True) -> None:
        self.user: Optional[ClientUser] = None
        self._users: weakref.WeakValueDictionary[int, User] = weakref.WeakValueDictionary()
        self._emojis: Dict[int, Emoji] = {}
        self._stickers: Dict[int, GuildSticker] = {}
        self._guilds: Dict[int, Guild] = {}
        if views:
            self._view_store: ViewStore = ViewStore(self)

        self._voice_clients: Dict[int, VoiceProtocol] = {}

        # LRU of max size 128
        self._private_channels: OrderedDict[int, PrivateChannel] = OrderedDict()
        # extra dict to look up private channels by user id
        self._private_channels_by_user: Dict[int, DMChannel] = {}
        if self.max_messages is not None:
            self._messages: Optional[Deque[Message]] = deque(maxlen=self.max_messages)
        else:
            self._messages: Optional[Deque[Message]] = None

    def process_chunk_requests(self, guild_id: int, nonce: Optional[str], members: List[Member], complete: bool) -> None:
        removed = []
        for key, request in self._chunk_requests.items():
            if request.guild_id == guild_id and request.nonce == nonce:
                request.add_members(members)
                if complete:
                    request.done()
                    removed.append(key)

        for key in removed:
            del self._chunk_requests[key]

    def clear_chunk_requests(self, shard_id: int | None) -> None:
        removed = []
        for key, request in self._chunk_requests.items():
            if shard_id is None or request.shard_id == shard_id:
                request.done()
                removed.append(key)

        for key in removed:
            del self._chunk_requests[key]

    def call_handlers(self, key: str, *args: Any, **kwargs: Any) -> None:
        try:
            func = self.handlers[key]
        except KeyError:
            pass
        else:
            func(*args, **kwargs)

    async def call_hooks(self, key: str, *args: Any, **kwargs: Any) -> None:
        try:
            coro = self.hooks[key]
        except KeyError:
            pass
        else:
            await coro(*args, **kwargs)

    @property
    def self_id(self) -> Optional[int]:
        u = self.user
        return u.id if u else None

    @property
    def intents(self) -> Intents:
        ret = Intents.none()
        ret.value = self._intents.value
        return ret

    @property
    def voice_clients(self) -> List[VoiceProtocol]:
        return list(self._voice_clients.values())

    def _get_voice_client(self, guild_id: Optional[int]) -> Optional[VoiceProtocol]:
        # the keys of self._voice_clients are ints
        return self._voice_clients.get(guild_id)  # type: ignore

    def _add_voice_client(self, guild_id: int, voice: VoiceProtocol) -> None:
        self._voice_clients[guild_id] = voice

    def _remove_voice_client(self, guild_id: int) -> None:
        self._voice_clients.pop(guild_id, None)

    def _update_references(self, ws: DiscordWebSocket) -> None:
        for vc in self.voice_clients:
            vc.main_ws = ws  # type: ignore # Silencing the unknown attribute (ok at runtime).

    def store_user(self, data: Union[UserPayload, PartialUserPayload], *, cache: bool = True) -> User:
        # this way is 300% faster than `dict.setdefault`.
        user_id = int(data['id'])
        try:
            return self._users[user_id]
        except KeyError:
            user = User(state=self, data=data)
            if cache:
                self._users[user_id] = user
            return user

    def store_user_no_intents(self, data: Union[UserPayload, PartialUserPayload], *, cache: bool = True) -> User:
        return User(state=self, data=data)

    def create_user(self, data: Union[UserPayload, PartialUserPayload]) -> User:
        return User(state=self, data=data)

    def get_user(self, id: int) -> Optional[User]:
        return self._users.get(id)

    def store_emoji(self, guild: Guild, data: EmojiPayload) -> Emoji:
        # the id will be present here
        emoji_id = int(data['id'])  # type: ignore
        self._emojis[emoji_id] = emoji = Emoji(guild=guild, state=self, data=data)
        return emoji

    def store_sticker(self, guild: Guild, data: GuildStickerPayload) -> GuildSticker:
        sticker_id = int(data['id'])
        self._stickers[sticker_id] = sticker = GuildSticker(state=self, data=data)
        return sticker

    def store_view(self, view: View, message_id: Optional[int] = None, interaction_id: Optional[int] = None) -> None:
        if interaction_id is not None:
            self._view_store.remove_interaction_mapping(interaction_id)
        self._view_store.add_view(view, message_id)

    def prevent_view_updates_for(self, message_id: int) -> Optional[View]:
        return self._view_store.remove_message_tracking(message_id)

    def store_dynamic_items(self, *items: Type[DynamicItem[Item[Any]]]) -> None:
        self._view_store.add_dynamic_items(*items)

    def remove_dynamic_items(self, *items: Type[DynamicItem[Item[Any]]]) -> None:
        self._view_store.remove_dynamic_items(*items)

    @property
    def persistent_views(self) -> Sequence[View]:
        return self._view_store.persistent_views

    @property
    def guilds(self) -> Sequence[Guild]:
        return utils.SequenceProxy(self._guilds.values())

    def _get_guild(self, guild_id: Optional[int]) -> Optional[Guild]:
        # the keys of self._guilds are ints
        return self._guilds.get(guild_id)  # type: ignore

    def _get_or_create_unavailable_guild(self, guild_id: int, *, data: Optional[Dict[str, Any]] = None) -> Guild:
        return self._guilds.get(guild_id) or Guild._create_unavailable(state=self, guild_id=guild_id, data=data)

    def _add_guild(self, guild: Guild) -> None:
        self._guilds[guild.id] = guild

    def _remove_guild(self, guild: Guild) -> None:
        self._guilds.pop(guild.id, None)

        for emoji in guild.emojis:
            self._emojis.pop(emoji.id, None)

        for sticker in guild.stickers:
            self._stickers.pop(sticker.id, None)

        del guild

    @property
    def emojis(self) -> Sequence[Emoji]:
        return utils.SequenceProxy(self._emojis.values())

    @property
    def stickers(self) -> Sequence[GuildSticker]:
        return utils.SequenceProxy(self._stickers.values())

    @property
    def soundboard_sounds(self) -> List[SoundboardSound]:
        all_sounds = []
        for guild in self.guilds:
            all_sounds.extend(guild.soundboard_sounds)

        return all_sounds

    def get_emoji(self, emoji_id: Optional[int]) -> Optional[Emoji]:
        # the keys of self._emojis are ints
        return self._emojis.get(emoji_id)  # type: ignore

    def get_sticker(self, sticker_id: Optional[int]) -> Optional[GuildSticker]:
        # the keys of self._stickers are ints
        return self._stickers.get(sticker_id)  # type: ignore

    @property
    def private_channels(self) -> Sequence[PrivateChannel]:
        return utils.SequenceProxy(self._private_channels.values())

    def _get_private_channel(self, channel_id: Optional[int]) -> Optional[PrivateChannel]:
        try:
            # the keys of self._private_channels are ints
            value = self._private_channels[channel_id]  # type: ignore
        except KeyError:
            return None
        else:
            # Type narrowing can't figure out that channel_id isn't None here
            self._private_channels.move_to_end(channel_id)  # type: ignore
            return value

    def _get_private_channel_by_user(self, user_id: Optional[int]) -> Optional[DMChannel]:
        # the keys of self._private_channels are ints
        return self._private_channels_by_user.get(user_id)  # type: ignore

    def _add_private_channel(self, channel: PrivateChannel) -> None:
        channel_id = channel.id
        self._private_channels[channel_id] = channel

        if len(self._private_channels) > 128:
            _, to_remove = self._private_channels.popitem(last=False)
            if isinstance(to_remove, DMChannel) and to_remove.recipient:
                self._private_channels_by_user.pop(to_remove.recipient.id, None)

        if isinstance(channel, DMChannel) and channel.recipient:
            self._private_channels_by_user[channel.recipient.id] = channel

    def add_dm_channel(self, data: DMChannelPayload) -> DMChannel:
        # self.user is *always* cached when this is called
        channel = DMChannel(me=self.user, state=self, data=data)  # type: ignore
        self._add_private_channel(channel)
        return channel

    def _remove_private_channel(self, channel: PrivateChannel) -> None:
        self._private_channels.pop(channel.id, None)
        if isinstance(channel, DMChannel):
            recipient = channel.recipient
            if recipient is not None:
                self._private_channels_by_user.pop(recipient.id, None)

    def _get_message(self, msg_id: Optional[int]) -> Optional[Message]:
        return utils.find(lambda m: m.id == msg_id, reversed(self._messages)) if self._messages else None

    def _add_guild_from_data(self, data: GuildPayload) -> Guild:
        guild = Guild(data=data, state=self)
        self._add_guild(guild)
        return guild

    def _guild_needs_chunking(self, guild: Guild) -> bool:
        # If presences are enabled then we get back the old guild.large behaviour
        return self._chunk_guilds and not guild.chunked and not (self._intents.presences and not guild.large)

    def _get_guild_channel(
        self, data: PartialMessagePayload, guild_id: Optional[int] = None
    ) -> Tuple[Union[Channel, Thread], Optional[Guild]]:
        channel_id = int(data['channel_id'])
        try:
            guild_id = guild_id or int(data['guild_id'])
            guild = self._get_guild(guild_id)
        except KeyError:
            channel = DMChannel._from_message(self, channel_id)
            guild = None
        else:
            channel = guild and guild._resolve_channel(channel_id)

        return channel or PartialMessageable(state=self, guild_id=guild_id, id=channel_id), guild

    def _update_poll_counts(self, message: Message, answer_id: int, added: bool, self_voted: bool = False) -> Optional[Poll]:
        poll = message.poll
        if not poll:
            return
        poll._handle_vote(answer_id, added, self_voted)
        return poll

    def _update_poll_results(self, from_: Message, to: Union[Message, int]) -> None:
        if isinstance(to, Message):
            cached = self._get_message(to.id)
        elif isinstance(to, int):
            cached = self._get_message(to)

            if cached is None:
                return

            to = cached
        else:
            return

        if to.poll is None:
            return

        to.poll._update_results_from_message(from_)

        if cached is not None and cached.poll:
            cached.poll._update_results_from_message(from_)

    async def chunker(
        self, guild_id: int, query: str = '', limit: int = 0, presences: bool = False, *, nonce: Optional[str] = None
    ) -> None:
        ws = self._get_websocket(guild_id)  # This is ignored upstream
        await ws.request_chunks(guild_id, query=query, limit=limit, presences=presences, nonce=nonce)

    async def query_members(
        self, guild: Guild, query: Optional[str], limit: int, user_ids: Optional[List[int]], cache: bool, presences: bool
    ) -> List[Member]:
        guild_id = guild.id
        ws = self._get_websocket(guild_id)
        if ws is None:
            raise RuntimeError('Somehow do not have a websocket for this guild_id')

        request = ChunkRequest(guild.id, guild.shard_id, self.loop, self._get_guild, cache=cache)
        self._chunk_requests[request.nonce] = request

        try:
            # start the query operation
            await ws.request_chunks(
                guild_id, query=query, limit=limit, user_ids=user_ids, presences=presences, nonce=request.nonce
            )
            return await asyncio.wait_for(request.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            _log.warning('Timed out waiting for chunks with query %r and limit %d for guild_id %d', query, limit, guild_id)
            raise

    async def _delay_ready(self) -> None:
        try:
            states = []
            while True:
                # this snippet of code is basically waiting N seconds
                # until the last GUILD_CREATE was sent
                try:
                    guild = await asyncio.wait_for(self._ready_state.get(), timeout=self.guild_ready_timeout)
                except asyncio.TimeoutError:
                    break
                else:
                    if self._guild_needs_chunking(guild):
                        future = await self.chunk_guild(guild, wait=False)
                        states.append((guild, future))
                    else:
                        if guild.unavailable is False:
                            self.dispatch('guild_available', guild)
                        else:
                            self.dispatch('guild_join', guild)

            for guild, future in states:
                timeout = self._chunk_timeout(guild)

                try:
                    await asyncio.wait_for(future, timeout=timeout)
                except asyncio.TimeoutError:
                    _log.warning('Shard ID %s timed out waiting for chunks for guild_id %s.', guild.shard_id, guild.id)

                if guild.unavailable is False:
                    self.dispatch('guild_available', guild)
                else:
                    self.dispatch('guild_join', guild)

            # remove the state
            try:
                del self._ready_state
            except AttributeError:
                pass  # already been deleted somehow

        except asyncio.CancelledError:
            pass
        else:
            # dispatch the event
            self.call_handlers('ready')
            self.dispatch('ready')
        finally:
            self._ready_task = None

    def parse_ready(self, data: gw.ReadyEvent) -> None:
        if self._ready_task is not None:
            self._ready_task.cancel()

        self._ready_state: asyncio.Queue[Guild] = asyncio.Queue()
        self.clear(views=False)
        self.clear_chunk_requests(None)
        self.user = user = ClientUser(state=self, data=data['user'])
        self._users[user.id] = user  # type: ignore

        if self.application_id is None:
            try:
                application = data['application']
            except KeyError:
                pass
            else:
                self.application_id = utils._get_as_snowflake(application, 'id')
                self.application_flags: ApplicationFlags = ApplicationFlags._from_value(application['flags'])

        for guild_data in data['guilds']:
            self._add_guild_from_data(guild_data)  # type: ignore

        self.dispatch('connect')
        self._ready_task = asyncio.create_task(self._delay_ready())

    def parse_resumed(self, data: gw.ResumedEvent) -> None:
        self.dispatch('resumed')

    def parse_message_create(self, data: gw.MessageCreateEvent) -> None:
        channel, _ = self._get_guild_channel(data)
        # channel would be the correct type here
        message = Message(channel=channel, data=data, state=self)  # type: ignore
        self.dispatch('message', message)
        if self._messages is not None:
            self._messages.append(message)
        # we ensure that the channel is either a TextChannel, VoiceChannel, or Thread
        if channel and channel.__class__ in (TextChannel, VoiceChannel, Thread, StageChannel):
            channel.last_message_id = message.id  # type: ignore

    def parse_message_delete(self, data: gw.MessageDeleteEvent) -> None:
        raw = RawMessageDeleteEvent(data)
        found = self._get_message(raw.message_id)
        raw.cached_message = found
        self.dispatch('raw_message_delete', raw)
        if self._messages is not None and found is not None:
            self.dispatch('message_delete', found)
            self._messages.remove(found)

    def parse_message_delete_bulk(self, data: gw.MessageDeleteBulkEvent) -> None:
        raw = RawBulkMessageDeleteEvent(data)
        if self._messages:
            found_messages = [message for message in self._messages if message.id in raw.message_ids]
        else:
            found_messages = []
        raw.cached_messages = found_messages
        self.dispatch('raw_bulk_message_delete', raw)
        if found_messages:
            self.dispatch('bulk_message_delete', found_messages)
            for msg in found_messages:
                # self._messages won't be None here
                self._messages.remove(msg)  # type: ignore

    def parse_message_update(self, data: gw.MessageUpdateEvent) -> None:
        channel, _ = self._get_guild_channel(data)
        # channel would be the correct type here
        updated_message = Message(channel=channel, data=data, state=self)  # type: ignore

        raw = RawMessageUpdateEvent(data=data, message=updated_message)
        cached_message = self._get_message(updated_message.id)
        if cached_message is not None:
            older_message = copy.copy(cached_message)
            raw.cached_message = older_message
            self.dispatch('raw_message_edit', raw)
            cached_message._update(data)
            # Coerce the `after` parameter to take the new updated Member
            # ref: #5999
            older_message.author = updated_message.author
            self.dispatch('message_edit', older_message, updated_message)
        else:
            self.dispatch('raw_message_edit', raw)

        if 'components' in data:
            try:
                entity_id = int(data['interaction']['id'])
            except (KeyError, ValueError):
                entity_id = raw.message_id

            if self._view_store.is_message_tracked(entity_id):
                self._view_store.update_from_message(entity_id, data['components'])

    def parse_message_reaction_add(self, data: gw.MessageReactionAddEvent) -> None:
        emoji = PartialEmoji.from_dict(data['emoji'])
        emoji._state = self
        raw = RawReactionActionEvent(data, emoji, 'REACTION_ADD')

        member_data = data.get('member')
        if member_data:
            guild = self._get_guild(raw.guild_id)
            if guild is not None:
                raw.member = Member(data=member_data, guild=guild, state=self)
            else:
                raw.member = None
        else:
            raw.member = None
        self.dispatch('raw_reaction_add', raw)

        # rich interface here
        message = self._get_message(raw.message_id)
        if message is not None:
            emoji = self._upgrade_partial_emoji(emoji)
            reaction = message._add_reaction(data, emoji, raw.user_id)
            user = raw.member or self._get_reaction_user(message.channel, raw.user_id)

            if user:
                self.dispatch('reaction_add', reaction, user)

    def parse_message_reaction_remove_all(self, data: gw.MessageReactionRemoveAllEvent) -> None:
        raw = RawReactionClearEvent(data)
        self.dispatch('raw_reaction_clear', raw)

        message = self._get_message(raw.message_id)
        if message is not None:
            old_reactions = message.reactions.copy()
            message.reactions.clear()
            self.dispatch('reaction_clear', message, old_reactions)

    def parse_message_reaction_remove(self, data: gw.MessageReactionRemoveEvent) -> None:
        emoji = PartialEmoji.from_dict(data['emoji'])
        emoji._state = self
        raw = RawReactionActionEvent(data, emoji, 'REACTION_REMOVE')
        self.dispatch('raw_reaction_remove', raw)

        message = self._get_message(raw.message_id)
        if message is not None:
            emoji = self._upgrade_partial_emoji(emoji)
            try:
                reaction = message._remove_reaction(data, emoji, raw.user_id)
            except (AttributeError, ValueError):  # eventual consistency lol
                pass
            else:
                user = self._get_reaction_user(message.channel, raw.user_id)
                if user:
                    self.dispatch('reaction_remove', reaction, user)

    def parse_message_reaction_remove_emoji(self, data: gw.MessageReactionRemoveEmojiEvent) -> None:
        emoji = PartialEmoji.from_dict(data['emoji'])
        emoji._state = self
        raw = RawReactionClearEmojiEvent(data, emoji)
        self.dispatch('raw_reaction_clear_emoji', raw)

        message = self._get_message(raw.message_id)
        if message is not None:
            try:
                reaction = message._clear_emoji(emoji)
            except (AttributeError, ValueError):  # eventual consistency lol
                pass
            else:
                if reaction:
                    self.dispatch('reaction_clear_emoji', reaction)

    def parse_interaction_create(self, data: gw.InteractionCreateEvent) -> None:
        interaction = Interaction(data=data, state=self)
        if data['type'] in (2, 4) and self._command_tree:  # application command and auto complete
            self._command_tree._from_interaction(interaction)
        elif data['type'] == 3:  # interaction component
            # These keys are always there for this interaction type
            inner_data = data['data']
            custom_id = inner_data['custom_id']
            component_type = inner_data['component_type']
            self._view_store.dispatch_view(component_type, custom_id, interaction)
        elif data['type'] == 5:  # modal submit
            # These keys are always there for this interaction type
            inner_data = data['data']
            custom_id = inner_data['custom_id']
            components = inner_data['components']
            self._view_store.dispatch_modal(custom_id, interaction, components)
        self.dispatch('interaction', interaction)

    def parse_presence_update(self, data: gw.PresenceUpdateEvent) -> None:
        guild_id = utils._get_as_snowflake(data, 'guild_id')
        # guild_id won't be None here
        guild = self._get_guild(guild_id)
        if guild is None:
            _log.debug('PRESENCE_UPDATE referencing an unknown guild ID: %s. Discarding.', guild_id)
            return

        user = data['user']
        member_id = int(user['id'])
        member = guild.get_member(member_id)
        if member is None:
            _log.debug('PRESENCE_UPDATE referencing an unknown member ID: %s. Discarding', member_id)
            return

        old_member = Member._copy(member)
        user_update = member._presence_update(data=data, user=user)
        if user_update:
            self.dispatch('user_update', user_update[0], user_update[1])

        self.dispatch('presence_update', old_member, member)

    def parse_user_update(self, data: gw.UserUpdateEvent) -> None:
        if self.user:
            self.user._update(data)

    def parse_invite_create(self, data: gw.InviteCreateEvent) -> None:
        invite = Invite.from_gateway(state=self, data=data)
        self.dispatch('invite_create', invite)

    def parse_invite_delete(self, data: gw.InviteDeleteEvent) -> None:
        invite = Invite.from_gateway(state=self, data=data)
        self.dispatch('invite_delete', invite)

    def parse_channel_delete(self, data: gw.ChannelDeleteEvent) -> None:
        guild = self._get_guild(utils._get_as_snowflake(data, 'guild_id'))
        channel_id = int(data['id'])
        if guild is not None:
            channel = guild.get_channel(channel_id)
            if channel is not None:
                guild._remove_channel(channel)
                self.dispatch('guild_channel_delete', channel)

                if channel.type in (ChannelType.voice, ChannelType.stage_voice):
                    for s in guild.scheduled_events:
                        if s.channel_id == channel.id:
                            guild._scheduled_events.pop(s.id)
                            self.dispatch('scheduled_event_delete', s)

                threads = guild._remove_threads_by_channel(channel_id)

                for thread in threads:
                    self.dispatch('thread_delete', thread)
                    self.dispatch('raw_thread_delete', RawThreadDeleteEvent._from_thread(thread))

    def parse_channel_update(self, data: gw.ChannelUpdateEvent) -> None:
        channel_type = try_enum(ChannelType, data.get('type'))
        channel_id = int(data['id'])
        if channel_type is ChannelType.group:
            channel = self._get_private_channel(channel_id)
            if channel is not None:
                old_channel = copy.copy(channel)
                # the channel is a GroupChannel rather than PrivateChannel
                channel._update_group(data)  # type: ignore
                self.dispatch('private_channel_update', old_channel, channel)
                return
            else:
                _log.debug('CHANNEL_UPDATE referencing an unknown channel ID: %s. Discarding.', channel_id)

        guild_id = utils._get_as_snowflake(data, 'guild_id')
        guild = self._get_guild(guild_id)
        if guild is not None:
            channel = guild.get_channel(channel_id)
            if channel is not None:
                old_channel = copy.copy(channel)
                channel._update(guild, data)  # type: ignore # the data payload varies based on the channel type.
                self.dispatch('guild_channel_update', old_channel, channel)
            else:
                _log.debug('CHANNEL_UPDATE referencing an unknown channel ID: %s. Discarding.', channel_id)
        else:
            _log.debug('CHANNEL_UPDATE referencing an unknown guild ID: %s. Discarding.', guild_id)

    def parse_channel_create(self, data: gw.ChannelCreateEvent) -> None:
        factory, ch_type = _channel_factory(data['type'])
        if factory is None:
            _log.debug('CHANNEL_CREATE referencing an unknown channel type %s. Discarding.', data['type'])
            return

        guild_id = utils._get_as_snowflake(data, 'guild_id')
        guild = self._get_guild(guild_id)
        if guild is not None:
            # the factory can't be a DMChannel or GroupChannel here
            channel = factory(guild=guild, state=self, data=data)  # type: ignore
            guild._add_channel(channel)  # type: ignore
            self.dispatch('guild_channel_create', channel)
        else:
            _log.debug('CHANNEL_CREATE referencing an unknown guild ID: %s. Discarding.', guild_id)
            return

    def parse_channel_pins_update(self, data: gw.ChannelPinsUpdateEvent) -> None:
        channel_id = int(data['channel_id'])
        try:
            guild = self._get_guild(int(data['guild_id']))
        except KeyError:
            guild = None
            channel = self._get_private_channel(channel_id)
        else:
            channel = guild and guild._resolve_channel(channel_id)

        if channel is None:
            _log.debug('CHANNEL_PINS_UPDATE referencing an unknown channel ID: %s. Discarding.', channel_id)
            return

        last_pin = utils.parse_time(data.get('last_pin_timestamp'))

        if guild is None:
            self.dispatch('private_channel_pins_update', channel, last_pin)
        else:
            self.dispatch('guild_channel_pins_update', channel, last_pin)

    def parse_thread_create(self, data: gw.ThreadCreateEvent) -> None:
        guild_id = int(data['guild_id'])
        guild: Optional[Guild] = self._get_guild(guild_id)
        if guild is None:
            _log.debug('THREAD_CREATE referencing an unknown guild ID: %s. Discarding', guild_id)
            return

        thread = Thread(guild=guild, state=guild._state, data=data)
        has_thread = guild.get_thread(thread.id)
        guild._add_thread(thread)
        if not has_thread:
            if data.get('newly_created'):
                if thread.parent.__class__ is ForumChannel:
                    thread.parent.last_message_id = thread.id  # type: ignore

                self.dispatch('thread_create', thread)
            else:
                self.dispatch('thread_join', thread)

    def parse_thread_update(self, data: gw.ThreadUpdateEvent) -> None:
        guild_id = int(data['guild_id'])
        guild = self._get_guild(guild_id)
        if guild is None:
            _log.debug('THREAD_UPDATE referencing an unknown guild ID: %s. Discarding', guild_id)
            return

        raw = RawThreadUpdateEvent(data)
        raw.thread = thread = guild.get_thread(raw.thread_id)
        self.dispatch('raw_thread_update', raw)
        if thread is not None:
            old = copy.copy(thread)
            thread._update(data)
            if thread.archived:
                guild._remove_thread(thread)
            self.dispatch('thread_update', old, thread)
        else:
            thread = Thread(guild=guild, state=guild._state, data=data)
            if not thread.archived:
                guild._add_thread(thread)
            self.dispatch('thread_join', thread)

    def parse_thread_delete(self, data: gw.ThreadDeleteEvent) -> None:
        guild_id = int(data['guild_id'])
        guild = self._get_guild(guild_id)
        if guild is None:
            _log.debug('THREAD_DELETE referencing an unknown guild ID: %s. Discarding', guild_id)
            return

        raw = RawThreadDeleteEvent(data)
        raw.thread = thread = guild.get_thread(raw.thread_id)
        self.dispatch('raw_thread_delete', raw)

        if thread is not None:
            guild._remove_thread(thread)
            self.dispatch('thread_delete', thread)

    def parse_thread_list_sync(self, data: gw.ThreadListSyncEvent) -> None:
        guild_id = int(data['guild_id'])
        guild: Optional[Guild] = self._get_guild(guild_id)
        if guild is None:
            _log.debug('THREAD_LIST_SYNC referencing an unknown guild ID: %s. Discarding', guild_id)
            return

        try:
            channel_ids = {int(i) for i in data['channel_ids']}
        except KeyError:
            # If not provided, then the entire guild is being synced
            # So all previous thread data should be overwritten
            previous_threads = guild._threads.copy()
            guild._clear_threads()
        else:
            previous_threads = guild._filter_threads(channel_ids)

        threads = {d['id']: guild._store_thread(d) for d in data.get('threads', [])}

        for member in data.get('members', []):
            try:
                # note: member['id'] is the thread_id
                thread = threads[member['id']]
            except KeyError:
                continue
            else:
                thread._add_member(ThreadMember(thread, member))

        for thread in threads.values():
            old = previous_threads.pop(thread.id, None)
            if old is None:
                self.dispatch('thread_join', thread)

        for thread in previous_threads.values():
            self.dispatch('thread_remove', thread)

    def parse_thread_member_update(self, data: gw.ThreadMemberUpdate) -> None:
        guild_id = int(data['guild_id'])
        guild: Optional[Guild] = self._get_guild(guild_id)
        if guild is None:
            _log.debug('THREAD_MEMBER_UPDATE referencing an unknown guild ID: %s. Discarding', guild_id)
            return

        thread_id = int(data['id'])
        thread: Optional[Thread] = guild.get_thread(thread_id)
        if thread is None:
            _log.debug('THREAD_MEMBER_UPDATE referencing an unknown thread ID: %s. Discarding', thread_id)
            return

        member = ThreadMember(thread, data)
        thread.me = member

    def parse_thread_members_update(self, data: gw.ThreadMembersUpdate) -> None:
        guild_id = int(data['guild_id'])
        guild: Optional[Guild] = self._get_guild(guild_id)
        if guild is None:
            _log.debug('THREAD_MEMBERS_UPDATE referencing an unknown guild ID: %s. Discarding', guild_id)
            return

        thread_id = int(data['id'])
        thread: Optional[Thread] = guild.get_thread(thread_id)
        raw = RawThreadMembersUpdate(data)
        if thread is None:
            _log.debug('THREAD_MEMBERS_UPDATE referencing an unknown thread ID: %s. Discarding', thread_id)
            return

        added_members = [ThreadMember(thread, d) for d in data.get('added_members', [])]
        removed_member_ids = [int(x) for x in data.get('removed_member_ids', [])]
        self_id = self.self_id
        for member in added_members:
            if member.id != self_id:
                thread._add_member(member)
                self.dispatch('thread_member_join', member)
            else:
                thread.me = member
                self.dispatch('thread_join', thread)

        for member_id in removed_member_ids:
            if member_id != self_id:
                member = thread._pop_member(member_id)
                self.dispatch('raw_thread_member_remove', raw)
                if member is not None:
                    self.dispatch('thread_member_remove', member)
            else:
                self.dispatch('thread_remove', thread)

    def parse_guild_member_add(self, data: gw.GuildMemberAddEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('GUILD_MEMBER_ADD referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        member = Member(guild=guild, data=data, state=self)
        if self.member_cache_flags.joined:
            guild._add_member(member)

        if guild._member_count is not None:
            guild._member_count += 1

        self.dispatch('member_join', member)

    def parse_guild_member_remove(self, data: gw.GuildMemberRemoveEvent) -> None:
        user = self.store_user(data['user'])
        raw = RawMemberRemoveEvent(data, user)

        guild = self._get_guild(raw.guild_id)
        if guild is not None:
            if guild._member_count is not None:
                guild._member_count -= 1

            member = guild.get_member(user.id)
            if member is not None:
                raw.user = member
                guild._remove_member(member)
                self.dispatch('member_remove', member)
        else:
            _log.debug('GUILD_MEMBER_REMOVE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])

        self.dispatch('raw_member_remove', raw)

    def parse_guild_member_update(self, data: gw.GuildMemberUpdateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        user = data['user']
        user_id = int(user['id'])
        if guild is None:
            _log.debug('GUILD_MEMBER_UPDATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        member = guild.get_member(user_id)
        if member is not None:
            old_member = Member._copy(member)
            member._update(data)
            user_update = member._update_inner_user(user)
            if user_update:
                self.dispatch('user_update', user_update[0], user_update[1])

            self.dispatch('member_update', old_member, member)
        else:
            if self.member_cache_flags.joined:
                member = Member(data=data, guild=guild, state=self)  # type: ignore # the data is not complete, contains a delta of values

                # Force an update on the inner user if necessary
                user_update = member._update_inner_user(user)
                if user_update:
                    self.dispatch('user_update', user_update[0], user_update[1])

                guild._add_member(member)
            _log.debug('GUILD_MEMBER_UPDATE referencing an unknown member ID: %s. Discarding.', user_id)

    def parse_guild_emojis_update(self, data: gw.GuildEmojisUpdateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('GUILD_EMOJIS_UPDATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        before_emojis = guild.emojis
        for emoji in before_emojis:
            self._emojis.pop(emoji.id, None)
        # guild won't be None here
        guild.emojis = tuple(map(lambda d: self.store_emoji(guild, d), data['emojis']))
        self.dispatch('guild_emojis_update', guild, before_emojis, guild.emojis)

    def parse_guild_stickers_update(self, data: gw.GuildStickersUpdateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('GUILD_STICKERS_UPDATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        before_stickers = guild.stickers
        for emoji in before_stickers:
            self._stickers.pop(emoji.id, None)

        guild.stickers = tuple(map(lambda d: self.store_sticker(guild, d), data['stickers']))
        self.dispatch('guild_stickers_update', guild, before_stickers, guild.stickers)

    def parse_guild_audit_log_entry_create(self, data: gw.GuildAuditLogEntryCreate) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('GUILD_AUDIT_LOG_ENTRY_CREATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        entry = AuditLogEntry(
            users=self._users,
            integrations={},
            app_commands={},
            automod_rules={},
            webhooks={},
            data=data,
            guild=guild,
        )

        self.dispatch('audit_log_entry_create', entry)

    def parse_auto_moderation_rule_create(self, data: AutoModerationRule) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('AUTO_MODERATION_RULE_CREATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        rule = AutoModRule(data=data, guild=guild, state=self)

        self.dispatch('automod_rule_create', rule)

    def parse_auto_moderation_rule_update(self, data: AutoModerationRule) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('AUTO_MODERATION_RULE_UPDATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        rule = AutoModRule(data=data, guild=guild, state=self)

        self.dispatch('automod_rule_update', rule)

    def parse_auto_moderation_rule_delete(self, data: AutoModerationRule) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('AUTO_MODERATION_RULE_DELETE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        rule = AutoModRule(data=data, guild=guild, state=self)

        self.dispatch('automod_rule_delete', rule)

    def parse_auto_moderation_action_execution(self, data: AutoModerationActionExecution) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('AUTO_MODERATION_ACTION_EXECUTION referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        execution = AutoModAction(data=data, state=self)

        self.dispatch('automod_action', execution)

    def _get_create_guild(self, data: gw.GuildCreateEvent) -> Guild:
        if data.get('unavailable') is False:
            # GUILD_CREATE with unavailable in the response
            # usually means that the guild has become available
            # and is therefore in the cache
            guild = self._get_guild(int(data['id']))
            if guild is not None:
                guild.unavailable = False
                guild._from_data(data)
                return guild

        return self._add_guild_from_data(data)

    def is_guild_evicted(self, guild: Guild) -> bool:
        return guild.id not in self._guilds

    @overload
    async def chunk_guild(self, guild: Guild, *, wait: Literal[True] = ..., cache: Optional[bool] = ...) -> List[Member]:
        ...

    @overload
    async def chunk_guild(
        self, guild: Guild, *, wait: Literal[False] = ..., cache: Optional[bool] = ...
    ) -> asyncio.Future[List[Member]]:
        ...

    async def chunk_guild(
        self, guild: Guild, *, wait: bool = True, cache: Optional[bool] = None
    ) -> Union[List[Member], asyncio.Future[List[Member]]]:
        cache = cache or self.member_cache_flags.joined
        request = self._chunk_requests.get(guild.id)
        if request is None:
            self._chunk_requests[guild.id] = request = ChunkRequest(
                guild.id, guild.shard_id, self.loop, self._get_guild, cache=cache
            )
            await self.chunker(guild.id, nonce=request.nonce)

        if wait:
            return await request.wait()
        return request.get_future()

    def _chunk_timeout(self, guild: Guild) -> float:
        return max(5.0, (guild.member_count or 0) / 10000)

    async def _chunk_and_dispatch(self, guild, unavailable):
        timeout = self._chunk_timeout(guild)

        try:
            await asyncio.wait_for(self.chunk_guild(guild), timeout=timeout)
        except asyncio.TimeoutError:
            _log.warning('Somehow timed out waiting for chunks for guild ID %s.', guild.id)

        if unavailable is False:
            self.dispatch('guild_available', guild)
        else:
            self.dispatch('guild_join', guild)

    def _add_ready_state(self, guild: Guild) -> bool:
        try:
            # Notify the on_ready state, if any, that this guild is complete.
            self._ready_state.put_nowait(guild)
        except AttributeError:
            return False
        else:
            return True

    def parse_guild_create(self, data: gw.GuildCreateEvent) -> None:
        unavailable = data.get('unavailable')
        if unavailable is True:
            # joined a guild with unavailable == True so..
            return

        guild = self._get_create_guild(data)

        if self._add_ready_state(guild):
            return  # We're waiting for the ready event, put the rest on hold

        # check if it requires chunking
        if self._guild_needs_chunking(guild):
            asyncio.create_task(self._chunk_and_dispatch(guild, unavailable))
            return

        # Dispatch available if newly available
        if unavailable is False:
            self.dispatch('guild_available', guild)
        else:
            self.dispatch('guild_join', guild)

    def parse_guild_update(self, data: gw.GuildUpdateEvent) -> None:
        guild = self._get_guild(int(data['id']))
        if guild is not None:
            old_guild = copy.copy(guild)
            guild._from_data(data)
            self.dispatch('guild_update', old_guild, guild)
        else:
            _log.debug('GUILD_UPDATE referencing an unknown guild ID: %s. Discarding.', data['id'])

    def parse_guild_delete(self, data: gw.GuildDeleteEvent) -> None:
        guild = self._get_guild(int(data['id']))
        if guild is None:
            _log.debug('GUILD_DELETE referencing an unknown guild ID: %s. Discarding.', data['id'])
            return

        if data.get('unavailable', False):
            # GUILD_DELETE with unavailable being True means that the
            # guild that was available is now currently unavailable
            guild.unavailable = True
            self.dispatch('guild_unavailable', guild)
            return

        # do a cleanup of the messages cache
        if self._messages is not None:
            self._messages: Optional[Deque[Message]] = deque(
                (msg for msg in self._messages if msg.guild != guild), maxlen=self.max_messages
            )

        self._remove_guild(guild)
        self.dispatch('guild_remove', guild)

    def parse_guild_ban_add(self, data: gw.GuildBanAddEvent) -> None:
        # we make the assumption that GUILD_BAN_ADD is done
        # before GUILD_MEMBER_REMOVE is called
        # hence we don't remove it from cache or do anything
        # strange with it, the main purpose of this event
        # is mainly to dispatch to another event worth listening to for logging
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            try:
                user = User(data=data['user'], state=self)
            except KeyError:
                pass
            else:
                member = guild.get_member(user.id) or user
                self.dispatch('member_ban', guild, member)

    def parse_guild_ban_remove(self, data: gw.GuildBanRemoveEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None and 'user' in data:
            user = self.store_user(data['user'])
            self.dispatch('member_unban', guild, user)

    def parse_guild_role_create(self, data: gw.GuildRoleCreateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('GUILD_ROLE_CREATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])
            return

        role_data = data['role']
        role = Role(guild=guild, data=role_data, state=self)
        guild._add_role(role)
        self.dispatch('guild_role_create', role)

    def parse_guild_role_delete(self, data: gw.GuildRoleDeleteEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            role_id = int(data['role_id'])
            try:
                role = guild._remove_role(role_id)
            except KeyError:
                return
            else:
                self.dispatch('guild_role_delete', role)
        else:
            _log.debug('GUILD_ROLE_DELETE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_guild_role_update(self, data: gw.GuildRoleUpdateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            role_data = data['role']
            role_id = int(role_data['id'])
            role = guild.get_role(role_id)
            if role is not None:
                old_role = copy.copy(role)
                role._update(role_data)
                self.dispatch('guild_role_update', old_role, role)
        else:
            _log.debug('GUILD_ROLE_UPDATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_guild_members_chunk(self, data: gw.GuildMembersChunkEvent) -> None:
        guild_id = int(data['guild_id'])
        guild = self._get_guild(guild_id)
        presences = data.get('presences', [])

        if guild is None:
            return

        members = [Member(guild=guild, data=member, state=self) for member in data.get('members', [])]
        _log.debug('Processed a chunk for %s members in guild ID %s.', len(members), guild_id)

        if presences:
            member_dict: Dict[Snowflake, Member] = {str(member.id): member for member in members}
            for presence in presences:
                user = presence['user']
                member_id = user['id']
                member = member_dict.get(member_id)
                if member is not None:
                    member._presence_update(presence, user)

        complete = data.get('chunk_index', 0) + 1 == data.get('chunk_count')
        self.process_chunk_requests(guild_id, data.get('nonce'), members, complete)

    def parse_guild_integrations_update(self, data: gw.GuildIntegrationsUpdateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            self.dispatch('guild_integrations_update', guild)
        else:
            _log.debug('GUILD_INTEGRATIONS_UPDATE referencing an unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_integration_create(self, data: gw.IntegrationCreateEvent) -> None:
        guild_id = int(data['guild_id'])
        guild = self._get_guild(guild_id)
        if guild is not None:
            cls, _ = _integration_factory(data['type'])
            integration = cls(data=data, guild=guild)
            self.dispatch('integration_create', integration)
        else:
            _log.debug('INTEGRATION_CREATE referencing an unknown guild ID: %s. Discarding.', guild_id)

    def parse_integration_update(self, data: gw.IntegrationUpdateEvent) -> None:
        guild_id = int(data['guild_id'])
        guild = self._get_guild(guild_id)
        if guild is not None:
            cls, _ = _integration_factory(data['type'])
            integration = cls(data=data, guild=guild)
            self.dispatch('integration_update', integration)
        else:
            _log.debug('INTEGRATION_UPDATE referencing an unknown guild ID: %s. Discarding.', guild_id)

    def parse_integration_delete(self, data: gw.IntegrationDeleteEvent) -> None:
        guild_id = int(data['guild_id'])
        guild = self._get_guild(guild_id)
        if guild is not None:
            raw = RawIntegrationDeleteEvent(data)
            self.dispatch('raw_integration_delete', raw)
        else:
            _log.debug('INTEGRATION_DELETE referencing an unknown guild ID: %s. Discarding.', guild_id)

    def parse_webhooks_update(self, data: gw.WebhooksUpdateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is None:
            _log.debug('WEBHOOKS_UPDATE referencing an unknown guild ID: %s. Discarding', data['guild_id'])
            return

        channel_id = utils._get_as_snowflake(data, 'channel_id')
        channel = guild.get_channel(channel_id)  # type: ignore # None is okay here
        if channel is not None:
            self.dispatch('webhooks_update', channel)
        else:
            _log.debug('WEBHOOKS_UPDATE referencing an unknown channel ID: %s. Discarding.', data['channel_id'])

    def parse_stage_instance_create(self, data: gw.StageInstanceCreateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            stage_instance = StageInstance(guild=guild, state=self, data=data)
            guild._stage_instances[stage_instance.id] = stage_instance
            self.dispatch('stage_instance_create', stage_instance)
        else:
            _log.debug('STAGE_INSTANCE_CREATE referencing unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_stage_instance_update(self, data: gw.StageInstanceUpdateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            stage_instance = guild._stage_instances.get(int(data['id']))
            if stage_instance is not None:
                old_stage_instance = copy.copy(stage_instance)
                stage_instance._update(data)
                self.dispatch('stage_instance_update', old_stage_instance, stage_instance)
            else:
                _log.debug('STAGE_INSTANCE_UPDATE referencing unknown stage instance ID: %s. Discarding.', data['id'])
        else:
            _log.debug('STAGE_INSTANCE_UPDATE referencing unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_stage_instance_delete(self, data: gw.StageInstanceDeleteEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            try:
                stage_instance = guild._stage_instances.pop(int(data['id']))
            except KeyError:
                pass
            else:
                self.dispatch('stage_instance_delete', stage_instance)
        else:
            _log.debug('STAGE_INSTANCE_DELETE referencing unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_guild_scheduled_event_create(self, data: gw.GuildScheduledEventCreateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            scheduled_event = ScheduledEvent(state=self, data=data)
            guild._scheduled_events[scheduled_event.id] = scheduled_event
            self.dispatch('scheduled_event_create', scheduled_event)
        else:
            _log.debug('SCHEDULED_EVENT_CREATE referencing unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_guild_scheduled_event_update(self, data: gw.GuildScheduledEventUpdateEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            scheduled_event = guild._scheduled_events.get(int(data['id']))
            if scheduled_event is not None:
                old_scheduled_event = copy.copy(scheduled_event)
                scheduled_event._update(data)
                self.dispatch('scheduled_event_update', old_scheduled_event, scheduled_event)
            else:
                _log.debug('SCHEDULED_EVENT_UPDATE referencing unknown scheduled event ID: %s. Discarding.', data['id'])
        else:
            _log.debug('SCHEDULED_EVENT_UPDATE referencing unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_guild_scheduled_event_delete(self, data: gw.GuildScheduledEventDeleteEvent) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            try:
                scheduled_event = guild._scheduled_events.pop(int(data['id']))
            except KeyError:
                pass
            else:
                self.dispatch('scheduled_event_delete', scheduled_event)
        else:
            _log.debug('SCHEDULED_EVENT_DELETE referencing unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_guild_scheduled_event_user_add(self, data: gw.GuildScheduledEventUserAdd) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            scheduled_event = guild._scheduled_events.get(int(data['guild_scheduled_event_id']))
            if scheduled_event is not None:
                user = self.get_user(int(data['user_id']))
                if user is not None:
                    scheduled_event._add_user(user)
                    self.dispatch('scheduled_event_user_add', scheduled_event, user)
                else:
                    _log.debug('SCHEDULED_EVENT_USER_ADD referencing unknown user ID: %s. Discarding.', data['user_id'])
            else:
                _log.debug(
                    'SCHEDULED_EVENT_USER_ADD referencing unknown scheduled event ID: %s. Discarding.',
                    data['guild_scheduled_event_id'],
                )
        else:
            _log.debug('SCHEDULED_EVENT_USER_ADD referencing unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_guild_scheduled_event_user_remove(self, data: gw.GuildScheduledEventUserRemove) -> None:
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            scheduled_event = guild._scheduled_events.get(int(data['guild_scheduled_event_id']))
            if scheduled_event is not None:
                user = self.get_user(int(data['user_id']))
                if user is not None:
                    scheduled_event._pop_user(user.id)
                    self.dispatch('scheduled_event_user_remove', scheduled_event, user)
                else:
                    _log.debug('SCHEDULED_EVENT_USER_REMOVE referencing unknown user ID: %s. Discarding.', data['user_id'])
            else:
                _log.debug(
                    'SCHEDULED_EVENT_USER_REMOVE referencing unknown scheduled event ID: %s. Discarding.',
                    data['guild_scheduled_event_id'],
                )
        else:
            _log.debug('SCHEDULED_EVENT_USER_REMOVE referencing unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_guild_soundboard_sound_create(self, data: gw.GuildSoundBoardSoundCreateEvent) -> None:
        guild_id = int(data['guild_id'])  # type: ignore # can't be None here
        guild = self._get_guild(guild_id)
        if guild is not None:
            sound = SoundboardSound(guild=guild, state=self, data=data)
            guild._add_soundboard_sound(sound)
            self.dispatch('soundboard_sound_create', sound)
        else:
            _log.debug('GUILD_SOUNDBOARD_SOUND_CREATE referencing unknown guild ID: %s. Discarding.', guild_id)

    def _update_and_dispatch_sound_update(self, sound: SoundboardSound, data: gw.GuildSoundBoardSoundUpdateEvent):
        old_sound = copy.copy(sound)
        sound._update(data)
        self.dispatch('soundboard_sound_update', old_sound, sound)

    def parse_guild_soundboard_sound_update(self, data: gw.GuildSoundBoardSoundUpdateEvent) -> None:
        guild_id = int(data['guild_id'])  # type: ignore # can't be None here
        guild = self._get_guild(guild_id)
        if guild is not None:
            sound_id = int(data['sound_id'])
            sound = guild.get_soundboard_sound(sound_id)
            if sound is not None:
                self._update_and_dispatch_sound_update(sound, data)
            else:
                _log.warning('GUILD_SOUNDBOARD_SOUND_UPDATE referencing unknown sound ID: %s. Discarding.', sound_id)
        else:
            _log.debug('GUILD_SOUNDBOARD_SOUND_UPDATE referencing unknown guild ID: %s. Discarding.', guild_id)

    def parse_guild_soundboard_sound_delete(self, data: gw.GuildSoundBoardSoundDeleteEvent) -> None:
        guild_id = int(data['guild_id'])
        guild = self._get_guild(guild_id)
        if guild is not None:
            sound_id = int(data['sound_id'])
            sound = guild.get_soundboard_sound(sound_id)
            if sound is not None:
                guild._remove_soundboard_sound(sound)
                self.dispatch('soundboard_sound_delete', sound)
            else:
                _log.warning('GUILD_SOUNDBOARD_SOUND_DELETE referencing unknown sound ID: %s. Discarding.', sound_id)
        else:
            _log.debug('GUILD_SOUNDBOARD_SOUND_DELETE referencing unknown guild ID: %s. Discarding.', guild_id)

    def parse_guild_soundboard_sounds_update(self, data: gw.GuildSoundBoardSoundsUpdateEvent) -> None:
        guild_id = int(data['guild_id'])
        guild = self._get_guild(guild_id)
        if guild is None:
            _log.debug('GUILD_SOUNDBOARD_SOUNDS_UPDATE referencing unknown guild ID: %s. Discarding.', guild_id)
            return

        for raw_sound in data['soundboard_sounds']:
            sound_id = int(raw_sound['sound_id'])
            sound = guild.get_soundboard_sound(sound_id)
            if sound is not None:
                self._update_and_dispatch_sound_update(sound, raw_sound)
            else:
                _log.warning('GUILD_SOUNDBOARD_SOUNDS_UPDATE referencing unknown sound ID: %s. Discarding.', sound_id)

    def parse_application_command_permissions_update(self, data: GuildApplicationCommandPermissionsPayload):
        raw = RawAppCommandPermissionsUpdateEvent(data=data, state=self)
        self.dispatch('raw_app_command_permissions_update', raw)

    def parse_voice_state_update(self, data: gw.VoiceStateUpdateEvent) -> None:
        guild = self._get_guild(utils._get_as_snowflake(data, 'guild_id'))
        channel_id = utils._get_as_snowflake(data, 'channel_id')
        flags = self.member_cache_flags
        # self.user is *always* cached when this is called
        self_id = self.user.id  # type: ignore
        if guild is not None:
            if int(data['user_id']) == self_id:
                voice = self._get_voice_client(guild.id)
                if voice is not None:
                    coro = voice.on_voice_state_update(data)
                    asyncio.create_task(logging_coroutine(coro, info='Voice Protocol voice state update handler'))

            member, before, after = guild._update_voice_state(data, channel_id)  # type: ignore
            if member is not None:
                if flags.voice:
                    if channel_id is None and flags._voice_only and member.id != self_id:
                        # Only remove from cache if we only have the voice flag enabled
                        guild._remove_member(member)
                    elif channel_id is not None:
                        guild._add_member(member)

                self.dispatch('voice_state_update', member, before, after)
            else:
                _log.debug('VOICE_STATE_UPDATE referencing an unknown member ID: %s. Discarding.', data['user_id'])

    def parse_voice_channel_effect_send(self, data: gw.VoiceChannelEffectSendEvent):
        guild = self._get_guild(int(data['guild_id']))
        if guild is not None:
            effect = VoiceChannelEffect(state=self, data=data, guild=guild)
            self.dispatch('voice_channel_effect', effect)
        else:
            _log.debug('VOICE_CHANNEL_EFFECT_SEND referencing an unknown guild ID: %s. Discarding.', data['guild_id'])

    def parse_voice_server_update(self, data: gw.VoiceServerUpdateEvent) -> None:
        key_id = int(data['guild_id'])

        vc = self._get_voice_client(key_id)
        if vc is not None:
            coro = vc.on_voice_server_update(data)
            asyncio.create_task(logging_coroutine(coro, info='Voice Protocol voice server update handler'))

    def parse_typing_start(self, data: gw.TypingStartEvent) -> None:
        raw = RawTypingEvent(data)
        raw.user = self.get_user(raw.user_id)
        channel, guild = self._get_guild_channel(data)

        if channel is not None:
            if isinstance(channel, DMChannel):
                if raw.user is not None and raw.user not in channel.recipients:
                    channel.recipients.append(raw.user)
            elif guild is not None:
                raw.user = guild.get_member(raw.user_id)

                if raw.user is None:
                    member_data = data.get('member')
                    if member_data:
                        raw.user = Member(data=member_data, state=self, guild=guild)

            if raw.user is not None:
                self.dispatch('typing', channel, raw.user, raw.timestamp)

        self.dispatch('raw_typing', raw)

    def parse_voice_channel_status_update(self, data: gw.VoiceChannelStatusUpdate) -> None:
        raw = RawVoiceChannelStatusUpdateEvent(data)
        guild = self._get_guild(raw.guild_id)
        if guild is not None:
            channel = guild.get_channel(raw.channel_id)
            if channel is not None:
                raw.cached_status = channel.status  # type: ignore # must be a voice channel
                channel.status = raw.status  # type: ignore # must be a voice channel

        self.dispatch('raw_voice_channel_status_update', raw)

    def parse_entitlement_create(self, data: gw.EntitlementCreateEvent) -> None:
        entitlement = Entitlement(data=data, state=self)
        self.dispatch('entitlement_create', entitlement)

    def parse_entitlement_update(self, data: gw.EntitlementUpdateEvent) -> None:
        entitlement = Entitlement(data=data, state=self)
        self.dispatch('entitlement_update', entitlement)

    def parse_entitlement_delete(self, data: gw.EntitlementDeleteEvent) -> None:
        entitlement = Entitlement(data=data, state=self)
        self.dispatch('entitlement_delete', entitlement)

    def parse_message_poll_vote_add(self, data: gw.PollVoteActionEvent) -> None:
        raw = RawPollVoteActionEvent(data)

        self.dispatch('raw_poll_vote_add', raw)

        message = self._get_message(raw.message_id)
        guild = self._get_guild(raw.guild_id)

        if guild:
            user = guild.get_member(raw.user_id)
        else:
            user = self.get_user(raw.user_id)

        if message and user:
            poll = self._update_poll_counts(message, raw.answer_id, True, raw.user_id == self.self_id)
            if poll:
                self.dispatch('poll_vote_add', user, poll.get_answer(raw.answer_id))

    def parse_message_poll_vote_remove(self, data: gw.PollVoteActionEvent) -> None:
        raw = RawPollVoteActionEvent(data)

        self.dispatch('raw_poll_vote_remove', raw)

        message = self._get_message(raw.message_id)
        guild = self._get_guild(raw.guild_id)

        if guild:
            user = guild.get_member(raw.user_id)
        else:
            user = self.get_user(raw.user_id)

        if message and user:
            poll = self._update_poll_counts(message, raw.answer_id, False, raw.user_id == self.self_id)
            if poll:
                self.dispatch('poll_vote_remove', user, poll.get_answer(raw.answer_id))

    def parse_subscription_create(self, data: gw.SubscriptionCreateEvent) -> None:
        subscription = Subscription(data=data, state=self)
        self.dispatch('subscription_create', subscription)

    def parse_subscription_update(self, data: gw.SubscriptionUpdateEvent) -> None:
        subscription = Subscription(data=data, state=self)
        self.dispatch('subscription_update', subscription)

    def parse_subscription_delete(self, data: gw.SubscriptionDeleteEvent) -> None:
        subscription = Subscription(data=data, state=self)
        self.dispatch('subscription_delete', subscription)

    def _get_reaction_user(self, channel: MessageableChannel, user_id: int) -> Optional[Union[User, Member]]:
        if isinstance(channel, (TextChannel, Thread, VoiceChannel)):
            return channel.guild.get_member(user_id)
        return self.get_user(user_id)

    def get_reaction_emoji(self, data: PartialEmojiPayload) -> Union[Emoji, PartialEmoji, str]:
        emoji_id = utils._get_as_snowflake(data, 'id')

        if not emoji_id:
            # the name key will be a str
            return data['name']  # type: ignore

        try:
            return self._emojis[emoji_id]
        except KeyError:
            return PartialEmoji.with_state(
                self, animated=data.get('animated', False), id=emoji_id, name=data['name']  # type: ignore
            )

    def _upgrade_partial_emoji(self, emoji: PartialEmoji) -> Union[Emoji, PartialEmoji, str]:
        emoji_id = emoji.id
        if not emoji_id:
            return emoji.name
        try:
            return self._emojis[emoji_id]
        except KeyError:
            return emoji

    def get_channel(self, id: Optional[int]) -> Optional[Union[Channel, Thread]]:
        if id is None:
            return None

        pm = self._get_private_channel(id)
        if pm is not None:
            return pm

        for guild in self.guilds:
            channel = guild._resolve_channel(id)
            if channel is not None:
                return channel

    def create_message(self, *, channel: MessageableChannel, data: MessagePayload) -> Message:
        return Message(state=self, channel=channel, data=data)

    def get_soundboard_sound(self, id: Optional[int]) -> Optional[SoundboardSound]:
        if id is None:
            return

        for guild in self.guilds:
            sound = guild._resolve_soundboard_sound(id)
            if sound is not None:
                return sound


class AutoShardedConnectionState(ConnectionState[ClientT]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.shard_ids: Union[List[int], range] = []

        self._ready_tasks: Dict[int, asyncio.Task[None]] = {}
        self._ready_states: Dict[int, asyncio.Queue[Guild]] = {}

    def _update_message_references(self) -> None:
        # self._messages won't be None when this is called
        for msg in self._messages:  # type: ignore
            if not msg.guild:
                continue

            new_guild = self._get_guild(msg.guild.id)
            if new_guild is not None and new_guild is not msg.guild:
                channel_id = msg.channel.id
                channel = new_guild._resolve_channel(channel_id) or PartialMessageable(
                    state=self, id=channel_id, guild_id=new_guild.id
                )
                msg._rebind_cached_references(new_guild, channel)

    async def chunker(
        self,
        guild_id: int,
        query: str = '',
        limit: int = 0,
        presences: bool = False,
        *,
        shard_id: Optional[int] = None,
        nonce: Optional[str] = None,
    ) -> None:
        ws = self._get_websocket(guild_id, shard_id=shard_id)
        await ws.request_chunks(guild_id, query=query, limit=limit, presences=presences, nonce=nonce)

    def _add_ready_state(self, guild: Guild) -> bool:
        try:
            # Notify the on_ready state, if any, that this guild is complete.
            self._ready_states[guild.shard_id].put_nowait(guild)
        except KeyError:
            return False
        else:
            return True

    async def _delay_ready(self) -> None:
        await asyncio.gather(*self._ready_tasks.values())

        # clear the current tasks
        self._ready_task = None
        self._ready_tasks = {}

        # dispatch the event
        self.call_handlers('ready')
        self.dispatch('ready')

    async def _delay_shard_ready(self, shard_id: int) -> None:
        try:
            states = []
            while True:
                # this snippet of code is basically waiting N seconds
                # until the last GUILD_CREATE was sent
                try:
                    guild = await asyncio.wait_for(self._ready_states[shard_id].get(), timeout=self.guild_ready_timeout)
                except asyncio.TimeoutError:
                    break
                else:
                    if self._guild_needs_chunking(guild):
                        future = await self.chunk_guild(guild, wait=False)
                        states.append((guild, future))
                    else:
                        if guild.unavailable is False:
                            self.dispatch('guild_available', guild)
                        else:
                            self.dispatch('guild_join', guild)

            for guild, future in states:
                timeout = self._chunk_timeout(guild)

                try:
                    await asyncio.wait_for(future, timeout=timeout)
                except asyncio.TimeoutError:
                    _log.warning('Shard ID %s timed out waiting for chunks for guild_id %s.', guild.shard_id, guild.id)

                if guild.unavailable is False:
                    self.dispatch('guild_available', guild)
                else:
                    self.dispatch('guild_join', guild)

            # remove the state
            try:
                del self._ready_states[shard_id]
            except KeyError:
                pass  # already been deleted somehow

        except asyncio.CancelledError:
            pass
        else:
            # dispatch the event
            self.dispatch('shard_ready', shard_id)

    def parse_ready(self, data: gw.ReadyEvent) -> None:
        if self._ready_task is not None:
            self._ready_task.cancel()

        shard_id = data['shard'][0]  # shard_id, num_shards

        if shard_id in self._ready_tasks:
            self._ready_tasks[shard_id].cancel()
            self.clear_chunk_requests(shard_id)

        if shard_id not in self._ready_states:
            self._ready_states[shard_id] = asyncio.Queue()

        self.user: Optional[ClientUser]
        self.user = user = ClientUser(state=self, data=data['user'])
        # self._users is a list of Users, we're setting a ClientUser
        self._users[user.id] = user  # type: ignore

        if self.application_id is None:
            try:
                application = data['application']
            except KeyError:
                pass
            else:
                self.application_id: Optional[int] = utils._get_as_snowflake(application, 'id')
                self.application_flags: ApplicationFlags = ApplicationFlags._from_value(application['flags'])

        for guild_data in data['guilds']:
            self._add_guild_from_data(guild_data)  # type: ignore # _add_guild_from_data requires a complete Guild payload

        if self._messages:
            self._update_message_references()

        self.dispatch('connect')
        self.dispatch('shard_connect', shard_id)

        self._ready_tasks[shard_id] = asyncio.create_task(self._delay_shard_ready(shard_id))

        # The delay task for every shard has been started
        if len(self._ready_tasks) == len(self.shard_ids):
            self._ready_task = asyncio.create_task(self._delay_ready())

    def parse_resumed(self, data: gw.ResumedEvent) -> None:
        self.dispatch('resumed')
        self.dispatch('shard_resumed', data['__shard_id__'])  # type: ignore # This is an internal discord.py key
