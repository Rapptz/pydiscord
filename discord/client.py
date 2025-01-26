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
import datetime
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    Generator,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

import aiohttp

from .sku import SKU, Entitlement
from .user import User, ClientUser
from .invite import Invite
from .template import Template
from .widget import Widget
from .guild import Guild, GuildPreview
from .emoji import Emoji
from .channel import _threaded_channel_factory, PartialMessageable
from .enums import ChannelType, EntitlementOwnerType
from .mentions import AllowedMentions
from .errors import *
from .enums import Status
from .flags import ApplicationFlags, Intents
from .gateway import *
from .activity import ActivityTypes, BaseActivity, create_activity
from .voice_client import VoiceClient
from .http import HTTPClient
from .state import ConnectionState
from . import utils
from .utils import MISSING, time_snowflake
from .object import Object
from .backoff import ExponentialBackoff
from .webhook import Webhook
from .appinfo import AppInfo
from .ui.view import View
from .ui.dynamic import DynamicItem
from .stage_instance import StageInstance
from .threads import Thread
from .sticker import GuildSticker, StandardSticker, StickerPack, _sticker_factory
from .soundboard import SoundboardDefaultSound, SoundboardSound

if TYPE_CHECKING:
    from types import TracebackType

    from typing_extensions import Self

    from .abc import Messageable, PrivateChannel, Snowflake, SnowflakeTime
    from .app_commands import Command, ContextMenu
    from .automod import AutoModAction, AutoModRule
    from .channel import DMChannel, GroupChannel
    from .ext.commands import AutoShardedBot, Bot, Context, CommandError
    from .guild import GuildChannel
    from .integrations import Integration
    from .interactions import Interaction
    from .member import Member, VoiceState
    from .message import Message
    from .raw_models import (
        RawAppCommandPermissionsUpdateEvent,
        RawBulkMessageDeleteEvent,
        RawIntegrationDeleteEvent,
        RawMemberRemoveEvent,
        RawMessageDeleteEvent,
        RawMessageUpdateEvent,
        RawReactionActionEvent,
        RawReactionClearEmojiEvent,
        RawReactionClearEvent,
        RawThreadDeleteEvent,
        RawThreadMembersUpdate,
        RawThreadUpdateEvent,
        RawTypingEvent,
        RawPollVoteActionEvent,
    )
    from .reaction import Reaction
    from .role import Role
    from .scheduled_event import ScheduledEvent
    from .threads import ThreadMember
    from .types.guild import Guild as GuildPayload
    from .ui.item import Item
    from .voice_client import VoiceProtocol
    from .audit_logs import AuditLogEntry
    from .poll import PollAnswer
    from .subscription import Subscription


# fmt: off
__all__ = (
    'Client',
)
# fmt: on

T = TypeVar('T')
Coro = Coroutine[Any, Any, T]
CoroT = TypeVar('CoroT', bound=Callable[..., Coro[Any]])

_log = logging.getLogger(__name__)


class _LoopSentinel:
    __slots__ = ()

    def __getattr__(self, attr: str) -> None:
        msg = (
            'loop attribute cannot be accessed in non-async contexts. '
            'Consider using either an asynchronous main function and passing it to asyncio.run or '
            'using asynchronous initialisation hooks such as Client.setup_hook'
        )
        raise AttributeError(msg)


_loop: Any = _LoopSentinel()


class Client:
    r"""Represents a client connection that connects to Discord.
    This class is used to interact with the Discord WebSocket and API.

    .. container:: operations

        .. describe:: async with x

            Asynchronously initialises the client and automatically cleans up.

            .. versionadded:: 2.0

    A number of options can be passed to the :class:`Client`.

    Parameters
    -----------
    max_messages: Optional[:class:`int`]
        The maximum number of messages to store in the internal message cache.
        This defaults to ``1000``. Passing in ``None`` disables the message cache.

        .. versionchanged:: 1.3
            Allow disabling the message cache and change the default size to ``1000``.
    proxy: Optional[:class:`str`]
        Proxy URL.
    proxy_auth: Optional[:class:`aiohttp.BasicAuth`]
        An object that represents proxy HTTP Basic Authorization.
    shard_id: Optional[:class:`int`]
        Integer starting at ``0`` and less than :attr:`.shard_count`.
    shard_count: Optional[:class:`int`]
        The total number of shards.
    application_id: :class:`int`
        The client's application ID.
    intents: :class:`Intents`
        The intents that you want to enable for the session. This is a way of
        disabling and enabling certain gateway events from triggering and being sent.

        .. versionadded:: 1.5

        .. versionchanged:: 2.0
            Parameter is now required.
    member_cache_flags: :class:`MemberCacheFlags`
        Allows for finer control over how the library caches members.
        If not given, defaults to cache as much as possible with the
        currently selected intents.

        .. versionadded:: 1.5
    chunk_guilds_at_startup: :class:`bool`
        Indicates if :func:`.on_ready` should be delayed to chunk all guilds
        at start-up if necessary. This operation is incredibly slow for large
        amounts of guilds. The default is ``True`` if :attr:`Intents.members`
        is ``True``.

        .. versionadded:: 1.5
    status: Optional[:class:`.Status`]
        A status to start your presence with upon logging on to Discord.
    activity: Optional[:class:`.BaseActivity`]
        An activity to start your presence with upon logging on to Discord.
    allowed_mentions: Optional[:class:`AllowedMentions`]
        Control how the client handles mentions by default on every message sent.

        .. versionadded:: 1.4
    heartbeat_timeout: :class:`float`
        The maximum numbers of seconds before timing out and restarting the
        WebSocket in the case of not receiving a HEARTBEAT_ACK. Useful if
        processing the initial packets take too long to the point of disconnecting
        you. The default timeout is 60 seconds.
    guild_ready_timeout: :class:`float`
        The maximum number of seconds to wait for the GUILD_CREATE stream to end before
        preparing the member cache and firing READY. The default timeout is 2 seconds.

        .. versionadded:: 1.4
    assume_unsync_clock: :class:`bool`
        Whether to assume the system clock is unsynced. This applies to the ratelimit handling
        code. If this is set to ``True``, the default, then the library uses the time to reset
        a rate limit bucket given by Discord. If this is ``False`` then your system clock is
        used to calculate how long to sleep for. If this is set to ``False`` it is recommended to
        sync your system clock to Google's NTP server.

        .. versionadded:: 1.3
    enable_debug_events: :class:`bool`
        Whether to enable events that are useful only for debugging gateway related information.

        Right now this involves :func:`on_socket_raw_receive` and :func:`on_socket_raw_send`. If
        this is ``False`` then those events will not be dispatched (due to performance considerations).
        To enable these events, this must be set to ``True``. Defaults to ``False``.

        .. versionadded:: 2.0
    enable_raw_presences: :class:`bool`
        Whether to manually enable or disable the :func:`on_raw_presence_update` event.

        Setting this flag to ``True`` requires :attr:`Intents.presences` to be enabled.

        By default, this flag is set to ``True`` only when :attr:`Intents.presences` is enabled and :attr:`Intents.members`
        is disabled, otherwise it's set to ``False``.

        .. versionadded:: 2.5
    http_trace: :class:`aiohttp.TraceConfig`
        The trace configuration to use for tracking HTTP requests the library does using ``aiohttp``.
        This allows you to check requests the library is using. For more information, check the
        `aiohttp documentation <https://docs.aiohttp.org/en/stable/client_advanced.html#client-tracing>`_.

        .. versionadded:: 2.0
    max_ratelimit_timeout: Optional[:class:`float`]
        The maximum number of seconds to wait when a non-global rate limit is encountered.
        If a request requires sleeping for more than the seconds passed in, then
        :exc:`~discord.RateLimited` will be raised. By default, there is no timeout limit.
        In order to prevent misuse and unnecessary bans, the minimum value this can be
        set to is ``30.0`` seconds.

        .. versionadded:: 2.0
    connector: Optional[:class:`aiohttp.BaseConnector`]
        The aiohttp connector to use for this client. This can be used to control underlying aiohttp
        behavior, such as setting a dns resolver or sslcontext.

        .. versionadded:: 2.5

    Attributes
    -----------
    ws
        The websocket gateway the client is currently connected to. Could be ``None``.
    """

    def __init__(self, *, intents: Intents, **options: Any) -> None:
        self.loop: asyncio.AbstractEventLoop = _loop
        # self.ws is set in the connect method
        self.ws: DiscordWebSocket = None  # type: ignore
        self._listeners: Dict[str, List[Tuple[asyncio.Future, Callable[..., bool]]]] = {}
        self.shard_id: Optional[int] = options.get('shard_id')
        self.shard_count: Optional[int] = options.get('shard_count')

        connector: Optional[aiohttp.BaseConnector] = options.get('connector', None)
        proxy: Optional[str] = options.pop('proxy', None)
        proxy_auth: Optional[aiohttp.BasicAuth] = options.pop('proxy_auth', None)
        unsync_clock: bool = options.pop('assume_unsync_clock', True)
        http_trace: Optional[aiohttp.TraceConfig] = options.pop('http_trace', None)
        max_ratelimit_timeout: Optional[float] = options.pop('max_ratelimit_timeout', None)
        self.http: HTTPClient = HTTPClient(
            self.loop,
            connector,
            proxy=proxy,
            proxy_auth=proxy_auth,
            unsync_clock=unsync_clock,
            http_trace=http_trace,
            max_ratelimit_timeout=max_ratelimit_timeout,
        )

        self._handlers: Dict[str, Callable[..., None]] = {
            'ready': self._handle_ready,
        }

        self._hooks: Dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {
            'before_identify': self._call_before_identify_hook,
        }

        self._enable_debug_events: bool = options.pop('enable_debug_events', False)
        self._connection: ConnectionState[Self] = self._get_state(intents=intents, **options)
        self._connection.shard_count = self.shard_count
        self._closing_task: Optional[asyncio.Task[None]] = None
        self._ready: asyncio.Event = MISSING
        self._application: Optional[AppInfo] = None
        self._connection._get_websocket = self._get_websocket
        self._connection._get_client = lambda: self

        if VoiceClient.warn_nacl:
            VoiceClient.warn_nacl = False
            _log.warning("PyNaCl is not installed, voice will NOT be supported")

    async def __aenter__(self) -> Self:
        await self._async_setup_hook()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        # This avoids double-calling a user-provided .close()
        if self._closing_task:
            await self._closing_task
        else:
            await self.close()

    # internals

    def _get_websocket(self, guild_id: Optional[int] = None, *, shard_id: Optional[int] = None) -> DiscordWebSocket:
        return self.ws

    def _get_state(self, **options: Any) -> ConnectionState[Self]:
        return ConnectionState(dispatch=self.dispatch, handlers=self._handlers, hooks=self._hooks, http=self.http, **options)

    def _handle_ready(self) -> None:
        self._ready.set()

    @property
    def latency(self) -> float:
        """:class:`float`: Measures latency between a HEARTBEAT and a HEARTBEAT_ACK in seconds.

        This could be referred to as the Discord WebSocket protocol latency.
        """
        ws = self.ws
        return float('nan') if not ws else ws.latency

    def is_ws_ratelimited(self) -> bool:
        """:class:`bool`: Whether the websocket is currently rate limited.

        This can be useful to know when deciding whether you should query members
        using HTTP or via the gateway.

        .. versionadded:: 1.6
        """
        if self.ws:
            return self.ws.is_ratelimited()
        return False

    @property
    def user(self) -> Optional[ClientUser]:
        """Optional[:class:`.ClientUser`]: Represents the connected client. ``None`` if not logged in."""
        return self._connection.user

    @property
    def guilds(self) -> Sequence[Guild]:
        """Sequence[:class:`.Guild`]: The guilds that the connected client is a member of."""
        return self._connection.guilds

    @property
    def emojis(self) -> Sequence[Emoji]:
        """Sequence[:class:`.Emoji`]: The emojis that the connected client has.

        .. note::

            This not include the emojis that are owned by the application.
            Use :meth:`.fetch_application_emoji` to get those.
        """
        return self._connection.emojis

    @property
    def stickers(self) -> Sequence[GuildSticker]:
        """Sequence[:class:`.GuildSticker`]: The stickers that the connected client has.

        .. versionadded:: 2.0
        """
        return self._connection.stickers

    @property
    def soundboard_sounds(self) -> List[SoundboardSound]:
        """List[:class:`.SoundboardSound`]: The soundboard sounds that the connected client has.

        .. versionadded:: 2.5
        """
        return self._connection.soundboard_sounds

    @property
    def cached_messages(self) -> Sequence[Message]:
        """Sequence[:class:`.Message`]: Read-only list of messages the connected client has cached.

        .. versionadded:: 1.1
        """
        return utils.SequenceProxy(self._connection._messages or [])

    @property
    def private_channels(self) -> Sequence[PrivateChannel]:
        """Sequence[:class:`.abc.PrivateChannel`]: The private channels that the connected client is participating on.

        .. note::

            This returns only up to 128 most recent private channels due to an internal working
            on how Discord deals with private channels.
        """
        return self._connection.private_channels

    @property
    def voice_clients(self) -> List[VoiceProtocol]:
        """List[:class:`.VoiceProtocol`]: Represents a list of voice connections.

        These are usually :class:`.VoiceClient` instances.
        """
        return self._connection.voice_clients

    @property
    def application_id(self) -> Optional[int]:
        """Optional[:class:`int`]: The client's application ID.

        If this is not passed via ``__init__`` then this is retrieved
        through the gateway when an event contains the data or after a call
        to :meth:`~discord.Client.login`. Usually after :func:`~discord.on_connect`
        is called.

        .. versionadded:: 2.0
        """
        return self._connection.application_id

    @property
    def application_flags(self) -> ApplicationFlags:
        """:class:`~discord.ApplicationFlags`: The client's application flags.

        .. versionadded:: 2.0
        """
        return self._connection.application_flags

    @property
    def application(self) -> Optional[AppInfo]:
        """Optional[:class:`~discord.AppInfo`]: The client's application info.

        This is retrieved on :meth:`~discord.Client.login` and is not updated
        afterwards. This allows populating the application_id without requiring a
        gateway connection.

        This is ``None`` if accessed before :meth:`~discord.Client.login` is called.

        .. seealso:: The :meth:`~discord.Client.application_info` API call

        .. versionadded:: 2.0
        """
        return self._application

    def is_ready(self) -> bool:
        """:class:`bool`: Specifies if the client's internal cache is ready for use."""
        return self._ready is not MISSING and self._ready.is_set()

    async def _run_event(
        self,
        coro: Callable[..., Coroutine[Any, Any, Any]],
        event_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        try:
            await coro(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except Exception:
            try:
                await self.on_error(event_name, *args, **kwargs)
            except asyncio.CancelledError:
                pass

    def _schedule_event(
        self,
        coro: Callable[..., Coroutine[Any, Any, Any]],
        event_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> asyncio.Task:
        wrapped = self._run_event(coro, event_name, *args, **kwargs)
        # Schedules the task
        return self.loop.create_task(wrapped, name=f'discord.py: {event_name}')

    def dispatch(self, event: str, /, *args: Any, **kwargs: Any) -> None:
        _log.debug('Dispatching event %s', event)
        method = 'on_' + event

        listeners = self._listeners.get(event)
        if listeners:
            removed = []
            for i, (future, condition) in enumerate(listeners):
                if future.cancelled():
                    removed.append(i)
                    continue

                try:
                    result = condition(*args)
                except Exception as exc:
                    future.set_exception(exc)
                    removed.append(i)
                else:
                    if result:
                        if len(args) == 0:
                            future.set_result(None)
                        elif len(args) == 1:
                            future.set_result(args[0])
                        else:
                            future.set_result(args)
                        removed.append(i)

            if len(removed) == len(listeners):
                self._listeners.pop(event)
            else:
                for idx in reversed(removed):
                    del listeners[idx]

        try:
            coro = getattr(self, method)
        except AttributeError:
            pass
        else:
            self._schedule_event(coro, method, *args, **kwargs)

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        """|coro|

        The default error handler provided by the client.

        By default this logs to the library logger however it could be
        overridden to have a different implementation.
        Check :func:`~discord.on_error` for more details.

        .. versionchanged:: 2.0

            ``event_method`` parameter is now positional-only
            and instead of writing to ``sys.stderr`` it logs instead.
        """
        _log.exception('Ignoring exception in %s', event_method)

    # hooks

    async def _call_before_identify_hook(self, shard_id: Optional[int], *, initial: bool = False) -> None:
        # This hook is an internal hook that actually calls the public one.
        # It allows the library to have its own hook without stepping on the
        # toes of those who need to override their own hook.
        await self.before_identify_hook(shard_id, initial=initial)

    async def before_identify_hook(self, shard_id: Optional[int], *, initial: bool = False) -> None:
        """|coro|

        A hook that is called before IDENTIFYing a session. This is useful
        if you wish to have more control over the synchronization of multiple
        IDENTIFYing clients.

        The default implementation sleeps for 5 seconds.

        .. versionadded:: 1.4

        Parameters
        ------------
        shard_id: :class:`int`
            The shard ID that requested being IDENTIFY'd
        initial: :class:`bool`
            Whether this IDENTIFY is the first initial IDENTIFY.
        """

        if not initial:
            await asyncio.sleep(5.0)

    async def _async_setup_hook(self) -> None:
        # Called whenever the client needs to initialise asyncio objects with a running loop
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.http.loop = loop
        self._connection.loop = loop

        self._ready = asyncio.Event()

    async def setup_hook(self) -> None:
        """|coro|

        A coroutine to be called to setup the bot, by default this is blank.

        To perform asynchronous setup after the bot is logged in but before
        it has connected to the Websocket, overwrite this coroutine.

        This is only called once, in :meth:`login`, and will be called before
        any events are dispatched, making it a better solution than doing such
        setup in the :func:`~discord.on_ready` event.

        .. warning::

            Since this is called *before* the websocket connection is made therefore
            anything that waits for the websocket will deadlock, this includes things
            like :meth:`wait_for` and :meth:`wait_until_ready`.

        .. versionadded:: 2.0
        """
        pass

    # login state management

    async def login(self, token: str) -> None:
        """|coro|

        Logs in the client with the specified credentials and
        calls the :meth:`setup_hook`.


        Parameters
        -----------
        token: :class:`str`
            The authentication token. Do not prefix this token with
            anything as the library will do it for you.

        Raises
        ------
        LoginFailure
            The wrong credentials are passed.
        HTTPException
            An unknown HTTP related error occurred,
            usually when it isn't 200 or the known incorrect credentials
            passing status code.
        """

        _log.info('logging in using static token')

        if self.loop is _loop:
            await self._async_setup_hook()

        if not isinstance(token, str):
            raise TypeError(f'expected token to be a str, received {token.__class__.__name__} instead')
        token = token.strip()

        data = await self.http.static_login(token)
        self._connection.user = ClientUser(state=self._connection, data=data)
        self._application = await self.application_info()
        if self._connection.application_id is None:
            self._connection.application_id = self._application.id

        if self._application.interactions_endpoint_url is not None:
            _log.warning(
                'Application has an interaction endpoint URL set, this means registered components and app commands will not be received by the library.'
            )

        if not self._connection.application_flags:
            self._connection.application_flags = self._application.flags

        await self.setup_hook()

    async def connect(self, *, reconnect: bool = True) -> None:
        """|coro|

        Creates a websocket connection and lets the websocket listen
        to messages from Discord. This is a loop that runs the entire
        event system and miscellaneous aspects of the library. Control
        is not resumed until the WebSocket connection is terminated.

        Parameters
        -----------
        reconnect: :class:`bool`
            If we should attempt reconnecting, either due to internet
            failure or a specific failure on Discord's part. Certain
            disconnects that lead to bad state will not be handled (such as
            invalid sharding payloads or bad tokens).

        Raises
        -------
        GatewayNotFound
            If the gateway to connect to Discord is not found. Usually if this
            is thrown then there is a Discord API outage.
        ConnectionClosed
            The websocket connection has been terminated.
        """

        backoff = ExponentialBackoff()
        ws_params = {
            'initial': True,
            'shard_id': self.shard_id,
        }
        while not self.is_closed():
            try:
                coro = DiscordWebSocket.from_client(self, **ws_params)
                self.ws = await asyncio.wait_for(coro, timeout=60.0)
                ws_params['initial'] = False
                while True:
                    await self.ws.poll_event()
            except ReconnectWebSocket as e:
                _log.debug('Got a request to %s the websocket.', e.op)
                self.dispatch('disconnect')
                ws_params.update(sequence=self.ws.sequence, resume=e.resume, session=self.ws.session_id)
                if e.resume:
                    ws_params['gateway'] = self.ws.gateway
                continue
            except (
                OSError,
                HTTPException,
                GatewayNotFound,
                ConnectionClosed,
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as exc:
                self.dispatch('disconnect')
                if not reconnect:
                    await self.close()
                    if isinstance(exc, ConnectionClosed) and exc.code == 1000:
                        # clean close, don't re-raise this
                        return
                    raise

                if self.is_closed():
                    return

                # If we get connection reset by peer then try to RESUME
                if isinstance(exc, OSError) and exc.errno in (54, 10054):
                    ws_params.update(
                        sequence=self.ws.sequence,
                        gateway=self.ws.gateway,
                        initial=False,
                        resume=True,
                        session=self.ws.session_id,
                    )
                    continue

                # We should only get this when an unhandled close code happens,
                # such as a clean disconnect (1000) or a bad state (bad token, no sharding, etc)
                # sometimes, discord sends us 1000 for unknown reasons so we should reconnect
                # regardless and rely on is_closed instead
                if isinstance(exc, ConnectionClosed):
                    if exc.code == 4014:
                        raise PrivilegedIntentsRequired(exc.shard_id) from None
                    if exc.code != 1000:
                        await self.close()
                        raise

                retry = backoff.delay()
                _log.exception("Attempting a reconnect in %.2fs", retry)
                await asyncio.sleep(retry)
                # Always try to RESUME the connection
                # If the connection is not RESUME-able then the gateway will invalidate the session.
                # This is apparently what the official Discord client does.
                ws_params.update(
                    sequence=self.ws.sequence,
                    gateway=self.ws.gateway,
                    resume=True,
                    session=self.ws.session_id,
                )

    async def close(self) -> None:
        """|coro|

        Closes the connection to Discord.
        """
        if self._closing_task:
            return await self._closing_task

        async def _close():
            await self._connection.close()

            if self.ws is not None and self.ws.open:
                await self.ws.close(code=1000)

            await self.http.close()

            if self._ready is not MISSING:
                self._ready.clear()

            self.loop = MISSING

        self._closing_task = asyncio.create_task(_close())
        await self._closing_task

    def clear(self) -> None:
        """Clears the internal state of the bot.

        After this, the bot can be considered "re-opened", i.e. :meth:`is_closed`
        and :meth:`is_ready` both return ``False`` along with the bot's internal
        cache cleared.
        """
        self._closing_task = None
        self._ready.clear()
        self._connection.clear()
        self.http.clear()

    async def start(self, token: str, *, reconnect: bool = True) -> None:
        """|coro|

        A shorthand coroutine for :meth:`login` + :meth:`connect`.

        Parameters
        -----------
        token: :class:`str`
            The authentication token. Do not prefix this token with
            anything as the library will do it for you.
        reconnect: :class:`bool`
            If we should attempt reconnecting, either due to internet
            failure or a specific failure on Discord's part. Certain
            disconnects that lead to bad state will not be handled (such as
            invalid sharding payloads or bad tokens).

        Raises
        -------
        TypeError
            An unexpected keyword argument was received.
        """
        await self.login(token)
        await self.connect(reconnect=reconnect)

    def run(
        self,
        token: str,
        *,
        reconnect: bool = True,
        log_handler: Optional[logging.Handler] = MISSING,
        log_formatter: logging.Formatter = MISSING,
        log_level: int = MISSING,
        root_logger: bool = False,
    ) -> None:
        """A blocking call that abstracts away the event loop
        initialisation from you.

        If you want more control over the event loop then this
        function should not be used. Use :meth:`start` coroutine
        or :meth:`connect` + :meth:`login`.

        This function also sets up the logging library to make it easier
        for beginners to know what is going on with the library. For more
        advanced users, this can be disabled by passing ``None`` to
        the ``log_handler`` parameter.

        .. warning::

            This function must be the last function to call due to the fact that it
            is blocking. That means that registration of events or anything being
            called after this function call will not execute until it returns.

        Parameters
        -----------
        token: :class:`str`
            The authentication token. Do not prefix this token with
            anything as the library will do it for you.
        reconnect: :class:`bool`
            If we should attempt reconnecting, either due to internet
            failure or a specific failure on Discord's part. Certain
            disconnects that lead to bad state will not be handled (such as
            invalid sharding payloads or bad tokens).
        log_handler: Optional[:class:`logging.Handler`]
            The log handler to use for the library's logger. If this is ``None``
            then the library will not set up anything logging related. Logging
            will still work if ``None`` is passed, though it is your responsibility
            to set it up.

            The default log handler if not provided is :class:`logging.StreamHandler`.

            .. versionadded:: 2.0
        log_formatter: :class:`logging.Formatter`
            The formatter to use with the given log handler. If not provided then it
            defaults to a colour based logging formatter (if available).

            .. versionadded:: 2.0
        log_level: :class:`int`
            The default log level for the library's logger. This is only applied if the
            ``log_handler`` parameter is not ``None``. Defaults to ``logging.INFO``.

            .. versionadded:: 2.0
        root_logger: :class:`bool`
            Whether to set up the root logger rather than the library logger.
            By default, only the library logger (``'discord'``) is set up. If this
            is set to ``True`` then the root logger is set up as well.

            Defaults to ``False``.

            .. versionadded:: 2.0
        """

        async def runner():
            async with self:
                await self.start(token, reconnect=reconnect)

        if log_handler is not None:
            utils.setup_logging(
                handler=log_handler,
                formatter=log_formatter,
                level=log_level,
                root=root_logger,
            )

        try:
            asyncio.run(runner())
        except KeyboardInterrupt:
            # nothing to do here
            # `asyncio.run` handles the loop cleanup
            # and `self.start` closes all sockets and the HTTPClient instance.
            return

    # properties

    def is_closed(self) -> bool:
        """:class:`bool`: Indicates if the websocket connection is closed."""
        return self._closing_task is not None

    @property
    def activity(self) -> Optional[ActivityTypes]:
        """Optional[:class:`.BaseActivity`]: The activity being used upon
        logging in.
        """
        return create_activity(self._connection._activity, self._connection)

    @activity.setter
    def activity(self, value: Optional[ActivityTypes]) -> None:
        if value is None:
            self._connection._activity = None
        elif isinstance(value, BaseActivity):
            # ConnectionState._activity is typehinted as ActivityPayload, we're passing Dict[str, Any]
            self._connection._activity = value.to_dict()  # type: ignore
        else:
            raise TypeError('activity must derive from BaseActivity.')

    @property
    def status(self) -> Status:
        """:class:`.Status`:
        The status being used upon logging on to Discord.

        .. versionadded: 2.0
        """
        if self._connection._status in set(state.value for state in Status):
            return Status(self._connection._status)
        return Status.online

    @status.setter
    def status(self, value: Status) -> None:
        if value is Status.offline:
            self._connection._status = 'invisible'
        elif isinstance(value, Status):
            self._connection._status = str(value)
        else:
            raise TypeError('status must derive from Status.')

    @property
    def allowed_mentions(self) -> Optional[AllowedMentions]:
        """Optional[:class:`~discord.AllowedMentions`]: The allowed mention configuration.

        .. versionadded:: 1.4
        """
        return self._connection.allowed_mentions

    @allowed_mentions.setter
    def allowed_mentions(self, value: Optional[AllowedMentions]) -> None:
        if value is None or isinstance(value, AllowedMentions):
            self._connection.allowed_mentions = value
        else:
            raise TypeError(f'allowed_mentions must be AllowedMentions not {value.__class__.__name__}')

    @property
    def intents(self) -> Intents:
        """:class:`~discord.Intents`: The intents configured for this connection.

        .. versionadded:: 1.5
        """
        return self._connection.intents

    # helpers/getters

    @property
    def users(self) -> List[User]:
        """List[:class:`~discord.User`]: Returns a list of all the users the bot can see."""
        return list(self._connection._users.values())

    def get_channel(self, id: int, /) -> Optional[Union[GuildChannel, Thread, PrivateChannel]]:
        """Returns a channel or thread with the given ID.

        .. versionchanged:: 2.0

            ``id`` parameter is now positional-only.

        Parameters
        -----------
        id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[Union[:class:`.abc.GuildChannel`, :class:`.Thread`, :class:`.abc.PrivateChannel`]]
            The returned channel or ``None`` if not found.
        """
        return self._connection.get_channel(id)  # type: ignore # The cache contains all channel types

    def get_partial_messageable(
        self, id: int, *, guild_id: Optional[int] = None, type: Optional[ChannelType] = None
    ) -> PartialMessageable:
        """Returns a partial messageable with the given channel ID.

        This is useful if you have a channel_id but don't want to do an API call
        to send messages to it.

        .. versionadded:: 2.0

        Parameters
        -----------
        id: :class:`int`
            The channel ID to create a partial messageable for.
        guild_id: Optional[:class:`int`]
            The optional guild ID to create a partial messageable for.

            This is not required to actually send messages, but it does allow the
            :meth:`~discord.PartialMessageable.jump_url` and
            :attr:`~discord.PartialMessageable.guild` properties to function properly.
        type: Optional[:class:`.ChannelType`]
            The underlying channel type for the partial messageable.

        Returns
        --------
        :class:`.PartialMessageable`
            The partial messageable
        """
        return PartialMessageable(state=self._connection, id=id, guild_id=guild_id, type=type)

    def get_stage_instance(self, id: int, /) -> Optional[StageInstance]:
        """Returns a stage instance with the given stage channel ID.

        .. versionadded:: 2.0

        Parameters
        -----------
        id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`.StageInstance`]
            The stage instance or ``None`` if not found.
        """
        from .channel import StageChannel

        channel = self._connection.get_channel(id)

        if isinstance(channel, StageChannel):
            return channel.instance

    def get_guild(self, id: int, /) -> Optional[Guild]:
        """Returns a guild with the given ID.

        .. versionchanged:: 2.0

            ``id`` parameter is now positional-only.

        Parameters
        -----------
        id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`.Guild`]
            The guild or ``None`` if not found.
        """
        return self._connection._get_guild(id)

    def get_user(self, id: int, /) -> Optional[User]:
        """Returns a user with the given ID.

        .. versionchanged:: 2.0

            ``id`` parameter is now positional-only.

        Parameters
        -----------
        id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`~discord.User`]
            The user or ``None`` if not found.
        """
        return self._connection.get_user(id)

    def get_emoji(self, id: int, /) -> Optional[Emoji]:
        """Returns an emoji with the given ID.

        .. versionchanged:: 2.0

            ``id`` parameter is now positional-only.

        Parameters
        -----------
        id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`.Emoji`]
            The custom emoji or ``None`` if not found.
        """
        return self._connection.get_emoji(id)

    def get_sticker(self, id: int, /) -> Optional[GuildSticker]:
        """Returns a guild sticker with the given ID.

        .. versionadded:: 2.0

        .. note::

            To retrieve standard stickers, use :meth:`.fetch_sticker`.
            or :meth:`.fetch_premium_sticker_packs`.

        Returns
        --------
        Optional[:class:`.GuildSticker`]
            The sticker or ``None`` if not found.
        """
        return self._connection.get_sticker(id)

    def get_soundboard_sound(self, id: int, /) -> Optional[SoundboardSound]:
        """Returns a soundboard sound with the given ID.

        .. versionadded:: 2.5

        Parameters
        ----------
        id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`.SoundboardSound`]
            The soundboard sound or ``None`` if not found.
        """
        return self._connection.get_soundboard_sound(id)

    def get_all_channels(self) -> Generator[GuildChannel, None, None]:
        """A generator that retrieves every :class:`.abc.GuildChannel` the client can 'access'.

        This is equivalent to: ::

            for guild in client.guilds:
                for channel in guild.channels:
                    yield channel

        .. note::

            Just because you receive a :class:`.abc.GuildChannel` does not mean that
            you can communicate in said channel. :meth:`.abc.GuildChannel.permissions_for` should
            be used for that.

        Yields
        ------
        :class:`.abc.GuildChannel`
            A channel the client can 'access'.
        """

        for guild in self.guilds:
            yield from guild.channels

    def get_all_members(self) -> Generator[Member, None, None]:
        """Returns a generator with every :class:`.Member` the client can see.

        This is equivalent to: ::

            for guild in client.guilds:
                for member in guild.members:
                    yield member

        Yields
        ------
        :class:`.Member`
            A member the client can see.
        """
        for guild in self.guilds:
            yield from guild.members

    # listeners/waiters

    async def wait_until_ready(self) -> None:
        """|coro|

        Waits until the client's internal cache is all ready.

        .. warning::

            Calling this inside :meth:`setup_hook` can lead to a deadlock.
        """
        if self._ready is not MISSING:
            await self._ready.wait()
        else:
            raise RuntimeError(
                'Client has not been properly initialised. '
                'Please use the login method or asynchronous context manager before calling this method'
            )

    # App Commands

    @overload
    async def wait_for(
        self,
        event: Literal['raw_app_command_permissions_update'],
        /,
        *,
        check: Optional[Callable[[RawAppCommandPermissionsUpdateEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawAppCommandPermissionsUpdateEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['app_command_completion'],
        /,
        *,
        check: Optional[Callable[[Interaction[Self], Union[Command[Any, ..., Any], ContextMenu]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Interaction[Self], Union[Command[Any, ..., Any], ContextMenu]]:
        ...

    # AutoMod

    @overload
    async def wait_for(
        self,
        event: Literal['automod_rule_create', 'automod_rule_update', 'automod_rule_delete'],
        /,
        *,
        check: Optional[Callable[[AutoModRule], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> AutoModRule:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['automod_action'],
        /,
        *,
        check: Optional[Callable[[AutoModAction], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> AutoModAction:
        ...

    # Channels

    @overload
    async def wait_for(
        self,
        event: Literal['private_channel_update'],
        /,
        *,
        check: Optional[Callable[[GroupChannel, GroupChannel], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[GroupChannel, GroupChannel]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['private_channel_pins_update'],
        /,
        *,
        check: Optional[Callable[[PrivateChannel, datetime.datetime], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[PrivateChannel, datetime.datetime]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['guild_channel_delete', 'guild_channel_create'],
        /,
        *,
        check: Optional[Callable[[GuildChannel], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> GuildChannel:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['guild_channel_update'],
        /,
        *,
        check: Optional[Callable[[GuildChannel, GuildChannel], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[GuildChannel, GuildChannel]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['guild_channel_pins_update'],
        /,
        *,
        check: Optional[
            Callable[
                [Union[GuildChannel, Thread], Optional[datetime.datetime]],
                bool,
            ]
        ],
        timeout: Optional[float] = ...,
    ) -> Tuple[Union[GuildChannel, Thread], Optional[datetime.datetime]]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['typing'],
        /,
        *,
        check: Optional[Callable[[Messageable, Union[User, Member], datetime.datetime], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Messageable, Union[User, Member], datetime.datetime]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_typing'],
        /,
        *,
        check: Optional[Callable[[RawTypingEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawTypingEvent:
        ...

    # Debug & Gateway events

    @overload
    async def wait_for(
        self,
        event: Literal['connect', 'disconnect', 'ready', 'resumed'],
        /,
        *,
        check: Optional[Callable[[], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> None:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['shard_connect', 'shard_disconnect', 'shard_ready', 'shard_resumed'],
        /,
        *,
        check: Optional[Callable[[int], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> int:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['socket_event_type', 'socket_raw_receive'],
        /,
        *,
        check: Optional[Callable[[str], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> str:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['socket_raw_send'],
        /,
        *,
        check: Optional[Callable[[Union[str, bytes]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Union[str, bytes]:
        ...

    # Entitlements
    @overload
    async def wait_for(
        self,
        event: Literal['entitlement_create', 'entitlement_update', 'entitlement_delete'],
        /,
        *,
        check: Optional[Callable[[Entitlement], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Entitlement:
        ...

    # Guilds

    @overload
    async def wait_for(
        self,
        event: Literal[
            'guild_available',
            'guild_unavailable',
            'guild_join',
            'guild_remove',
        ],
        /,
        *,
        check: Optional[Callable[[Guild], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Guild:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['guild_update'],
        /,
        *,
        check: Optional[Callable[[Guild, Guild], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Guild, Guild]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['guild_emojis_update'],
        /,
        *,
        check: Optional[Callable[[Guild, Sequence[Emoji], Sequence[Emoji]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Guild, Sequence[Emoji], Sequence[Emoji]]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['guild_stickers_update'],
        /,
        *,
        check: Optional[Callable[[Guild, Sequence[GuildSticker], Sequence[GuildSticker]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Guild, Sequence[GuildSticker], Sequence[GuildSticker]]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['invite_create', 'invite_delete'],
        /,
        *,
        check: Optional[Callable[[Invite], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Invite:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['audit_log_entry_create'],
        /,
        *,
        check: Optional[Callable[[AuditLogEntry], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> AuditLogEntry:
        ...

    # Integrations

    @overload
    async def wait_for(
        self,
        event: Literal['integration_create', 'integration_update'],
        /,
        *,
        check: Optional[Callable[[Integration], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Integration:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['guild_integrations_update'],
        /,
        *,
        check: Optional[Callable[[Guild], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Guild:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['webhooks_update'],
        /,
        *,
        check: Optional[Callable[[GuildChannel], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> GuildChannel:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_integration_delete'],
        /,
        *,
        check: Optional[Callable[[RawIntegrationDeleteEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawIntegrationDeleteEvent:
        ...

    # Interactions

    @overload
    async def wait_for(
        self,
        event: Literal['interaction'],
        /,
        *,
        check: Optional[Callable[[Interaction[Self]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Interaction[Self]:
        ...

    # Members

    @overload
    async def wait_for(
        self,
        event: Literal['member_join', 'member_remove'],
        /,
        *,
        check: Optional[Callable[[Member], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Member:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_member_remove'],
        /,
        *,
        check: Optional[Callable[[RawMemberRemoveEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawMemberRemoveEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['member_update', 'presence_update'],
        /,
        *,
        check: Optional[Callable[[Member, Member], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Member, Member]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['user_update'],
        /,
        *,
        check: Optional[Callable[[User, User], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[User, User]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['member_ban'],
        /,
        *,
        check: Optional[Callable[[Guild, Union[User, Member]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Guild, Union[User, Member]]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['member_unban'],
        /,
        *,
        check: Optional[Callable[[Guild, User], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Guild, User]:
        ...

    # Messages

    @overload
    async def wait_for(
        self,
        event: Literal['message', 'message_delete'],
        /,
        *,
        check: Optional[Callable[[Message], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Message:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['message_edit'],
        /,
        *,
        check: Optional[Callable[[Message, Message], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Message, Message]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['bulk_message_delete'],
        /,
        *,
        check: Optional[Callable[[List[Message]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> List[Message]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_message_edit'],
        /,
        *,
        check: Optional[Callable[[RawMessageUpdateEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawMessageUpdateEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_message_delete'],
        /,
        *,
        check: Optional[Callable[[RawMessageDeleteEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawMessageDeleteEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_bulk_message_delete'],
        /,
        *,
        check: Optional[Callable[[RawBulkMessageDeleteEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawBulkMessageDeleteEvent:
        ...

    # Reactions

    @overload
    async def wait_for(
        self,
        event: Literal['reaction_add', 'reaction_remove'],
        /,
        *,
        check: Optional[Callable[[Reaction, Union[Member, User]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Reaction, Union[Member, User]]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['reaction_clear'],
        /,
        *,
        check: Optional[Callable[[Message, List[Reaction]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Message, List[Reaction]]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['reaction_clear_emoji'],
        /,
        *,
        check: Optional[Callable[[Reaction], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Reaction:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_reaction_add', 'raw_reaction_remove'],
        /,
        *,
        check: Optional[Callable[[RawReactionActionEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawReactionActionEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_reaction_clear'],
        /,
        *,
        check: Optional[Callable[[RawReactionClearEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawReactionClearEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_reaction_clear_emoji'],
        /,
        *,
        check: Optional[Callable[[RawReactionClearEmojiEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawReactionClearEmojiEvent:
        ...

    # Roles

    @overload
    async def wait_for(
        self,
        event: Literal['guild_role_create', 'guild_role_delete'],
        /,
        *,
        check: Optional[Callable[[Role], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Role:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['guild_role_update'],
        /,
        *,
        check: Optional[Callable[[Role, Role], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Role, Role]:
        ...

    # Scheduled Events

    @overload
    async def wait_for(
        self,
        event: Literal['scheduled_event_create', 'scheduled_event_delete'],
        /,
        *,
        check: Optional[Callable[[ScheduledEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> ScheduledEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['scheduled_event_user_add', 'scheduled_event_user_remove'],
        /,
        *,
        check: Optional[Callable[[ScheduledEvent, User], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[ScheduledEvent, User]:
        ...

    # Stages

    @overload
    async def wait_for(
        self,
        event: Literal['stage_instance_create', 'stage_instance_delete'],
        /,
        *,
        check: Optional[Callable[[StageInstance], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> StageInstance:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['stage_instance_update'],
        /,
        *,
        check: Optional[Callable[[StageInstance, StageInstance], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Coroutine[Any, Any, Tuple[StageInstance, StageInstance]]:
        ...

    # Subscriptions
    @overload
    async def wait_for(
        self,
        event: Literal['subscription_create', 'subscription_update', 'subscription_delete'],
        /,
        *,
        check: Optional[Callable[[Subscription], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Subscription:
        ...

    # Threads
    @overload
    async def wait_for(
        self,
        event: Literal['thread_create', 'thread_join', 'thread_remove', 'thread_delete'],
        /,
        *,
        check: Optional[Callable[[Thread], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Thread:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['thread_update'],
        /,
        *,
        check: Optional[Callable[[Thread, Thread], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Thread, Thread]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_thread_update'],
        /,
        *,
        check: Optional[Callable[[RawThreadUpdateEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawThreadUpdateEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_thread_delete'],
        /,
        *,
        check: Optional[Callable[[RawThreadDeleteEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawThreadDeleteEvent:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['thread_member_join', 'thread_member_remove'],
        /,
        *,
        check: Optional[Callable[[ThreadMember], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> ThreadMember:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_thread_member_remove'],
        /,
        *,
        check: Optional[Callable[[RawThreadMembersUpdate], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawThreadMembersUpdate:
        ...

    # Voice

    @overload
    async def wait_for(
        self,
        event: Literal['voice_state_update'],
        /,
        *,
        check: Optional[Callable[[Member, VoiceState, VoiceState], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Member, VoiceState, VoiceState]:
        ...

    # Polls

    @overload
    async def wait_for(
        self,
        event: Literal['poll_vote_add', 'poll_vote_remove'],
        /,
        *,
        check: Optional[Callable[[Union[User, Member], PollAnswer], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Union[User, Member], PollAnswer]:
        ...

    @overload
    async def wait_for(
        self,
        event: Literal['raw_poll_vote_add', 'raw_poll_vote_remove'],
        /,
        *,
        check: Optional[Callable[[RawPollVoteActionEvent], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> RawPollVoteActionEvent:
        ...

    # Commands

    @overload
    async def wait_for(
        self: Union[Bot, AutoShardedBot],
        event: Literal["command", "command_completion"],
        /,
        *,
        check: Optional[Callable[[Context[Any]], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Context[Any]:
        ...

    @overload
    async def wait_for(
        self: Union[Bot, AutoShardedBot],
        event: Literal["command_error"],
        /,
        *,
        check: Optional[Callable[[Context[Any], CommandError], bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Tuple[Context[Any], CommandError]:
        ...

    @overload
    async def wait_for(
        self,
        event: str,
        /,
        *,
        check: Optional[Callable[..., bool]] = ...,
        timeout: Optional[float] = ...,
    ) -> Any:
        ...

    def wait_for(
        self,
        event: str,
        /,
        *,
        check: Optional[Callable[..., bool]] = None,
        timeout: Optional[float] = None,
    ) -> Coro[Any]:
        """|coro|

        Waits for a WebSocket event to be dispatched.

        This could be used to wait for a user to reply to a message,
        or to react to a message, or to edit a message in a self-contained
        way.

        The ``timeout`` parameter is passed onto :func:`asyncio.wait_for`. By default,
        it does not timeout. Note that this does propagate the
        :exc:`asyncio.TimeoutError` for you in case of timeout and is provided for
        ease of use.

        In case the event returns multiple arguments, a :class:`tuple` containing those
        arguments is returned instead. Please check the
        :ref:`documentation <discord-api-events>` for a list of events and their
        parameters.

        This function returns the **first event that meets the requirements**.

        Examples
        ---------

        Waiting for a user reply: ::

            @client.event
            async def on_message(message):
                if message.content.startswith('$greet'):
                    channel = message.channel
                    await channel.send('Say hello!')

                    def check(m):
                        return m.content == 'hello' and m.channel == channel

                    msg = await client.wait_for('message', check=check)
                    await channel.send(f'Hello {msg.author}!')

        Waiting for a thumbs up reaction from the message author: ::

            @client.event
            async def on_message(message):
                if message.content.startswith('$thumb'):
                    channel = message.channel
                    await channel.send('Send me that \N{THUMBS UP SIGN} reaction, mate')

                    def check(reaction, user):
                        return user == message.author and str(reaction.emoji) == '\N{THUMBS UP SIGN}'

                    try:
                        reaction, user = await client.wait_for('reaction_add', timeout=60.0, check=check)
                    except asyncio.TimeoutError:
                        await channel.send('\N{THUMBS DOWN SIGN}')
                    else:
                        await channel.send('\N{THUMBS UP SIGN}')

        .. versionchanged:: 2.0

            ``event`` parameter is now positional-only.


        Parameters
        ------------
        event: :class:`str`
            The event name, similar to the :ref:`event reference <discord-api-events>`,
            but without the ``on_`` prefix, to wait for.
        check: Optional[Callable[..., :class:`bool`]]
            A predicate to check what to wait for. The arguments must meet the
            parameters of the event being waited for.
        timeout: Optional[:class:`float`]
            The number of seconds to wait before timing out and raising
            :exc:`asyncio.TimeoutError`.

        Raises
        -------
        asyncio.TimeoutError
            If a timeout is provided and it was reached.

        Returns
        --------
        Any
            Returns no arguments, a single argument, or a :class:`tuple` of multiple
            arguments that mirrors the parameters passed in the
            :ref:`event reference <discord-api-events>`.
        """

        future = self.loop.create_future()
        if check is None:

            def _check(*args):
                return True

            check = _check

        ev = event.lower()
        try:
            listeners = self._listeners[ev]
        except KeyError:
            listeners = []
            self._listeners[ev] = listeners

        listeners.append((future, check))
        return asyncio.wait_for(future, timeout)

    # event registration

    def event(self, coro: CoroT, /) -> CoroT:
        """A decorator that registers an event to listen to.

        You can find more info about the events on the :ref:`documentation below <discord-api-events>`.

        The events must be a :ref:`coroutine <coroutine>`, if not, :exc:`TypeError` is raised.

        Example
        ---------

        .. code-block:: python3

            @client.event
            async def on_ready():
                print('Ready!')

        .. versionchanged:: 2.0

            ``coro`` parameter is now positional-only.

        Raises
        --------
        TypeError
            The coroutine passed is not actually a coroutine.
        """

        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('event registered must be a coroutine function')

        setattr(self, coro.__name__, coro)
        _log.debug('%s has successfully been registered as an event', coro.__name__)
        return coro

    async def change_presence(
        self,
        *,
        activity: Optional[BaseActivity] = None,
        status: Optional[Status] = None,
    ) -> None:
        """|coro|

        Changes the client's presence.

        Example
        ---------

        .. code-block:: python3

            game = discord.Game("with the API")
            await client.change_presence(status=discord.Status.idle, activity=game)

        .. versionchanged:: 2.0
            Removed the ``afk`` keyword-only parameter.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        ----------
        activity: Optional[:class:`.BaseActivity`]
            The activity being done. ``None`` if no currently active activity is done.
        status: Optional[:class:`.Status`]
            Indicates what status to change to. If ``None``, then
            :attr:`.Status.online` is used.

        Raises
        ------
        TypeError
            If the ``activity`` parameter is not the proper type.
        """

        if status is None:
            status_str = 'online'
            status = Status.online
        elif status is Status.offline:
            status_str = 'invisible'
            status = Status.offline
        else:
            status_str = str(status)

        await self.ws.change_presence(activity=activity, status=status_str)

        for guild in self._connection.guilds:
            me = guild.me
            if me is None:
                continue

            if activity is not None:
                me.activities = (activity,)  # type: ignore # Type checker does not understand the downcast here
            else:
                me.activities = ()

            me.status = status

    # Guild stuff

    async def fetch_guilds(
        self,
        *,
        limit: Optional[int] = 200,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
        with_counts: bool = True,
    ) -> AsyncIterator[Guild]:
        """Retrieves an :term:`asynchronous iterator` that enables receiving your guilds.

        .. note::

            Using this, you will only receive :attr:`.Guild.owner`, :attr:`.Guild.icon`,
            :attr:`.Guild.id`, :attr:`.Guild.name`, :attr:`.Guild.approximate_member_count`,
            and :attr:`.Guild.approximate_presence_count` per :class:`.Guild`.

        .. note::

            This method is an API call. For general usage, consider :attr:`guilds` instead.

        Examples
        ---------

        Usage ::

            async for guild in client.fetch_guilds(limit=150):
                print(guild.name)

        Flattening into a list ::

            guilds = [guild async for guild in client.fetch_guilds(limit=150)]
            # guilds is now a list of Guild...

        All parameters are optional.

        Parameters
        -----------
        limit: Optional[:class:`int`]
            The number of guilds to retrieve.
            If ``None``, it retrieves every guild you have access to. Note, however,
            that this would make it a slow operation.
            Defaults to ``200``.

            .. versionchanged:: 2.0

                The default has been changed to 200.

        before: Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]
            Retrieves guilds before this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        after: Union[:class:`.abc.Snowflake`, :class:`datetime.datetime`]
            Retrieve guilds after this date or object.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        with_counts: :class:`bool`
            Whether to include count information in the guilds. This fills the
            :attr:`.Guild.approximate_member_count` and :attr:`.Guild.approximate_presence_count`
            attributes without needing any privileged intents. Defaults to ``True``.

            .. versionadded:: 2.3

        Raises
        ------
        HTTPException
            Getting the guilds failed.

        Yields
        --------
        :class:`.Guild`
            The guild with the guild data parsed.
        """

        async def _before_strategy(retrieve: int, before: Optional[Snowflake], limit: Optional[int]):
            before_id = before.id if before else None
            data = await self.http.get_guilds(retrieve, before=before_id, with_counts=with_counts)

            if data:
                if limit is not None:
                    limit -= len(data)

                before = Object(id=int(data[0]['id']))

            return data, before, limit

        async def _after_strategy(retrieve: int, after: Optional[Snowflake], limit: Optional[int]):
            after_id = after.id if after else None
            data = await self.http.get_guilds(retrieve, after=after_id, with_counts=with_counts)

            if data:
                if limit is not None:
                    limit -= len(data)

                after = Object(id=int(data[-1]['id']))

            return data, after, limit

        if isinstance(before, datetime.datetime):
            before = Object(id=time_snowflake(before, high=False))
        if isinstance(after, datetime.datetime):
            after = Object(id=time_snowflake(after, high=True))

        predicate: Optional[Callable[[GuildPayload], bool]] = None
        strategy, state = _after_strategy, after

        if before:
            strategy, state = _before_strategy, before

        if before and after:
            predicate = lambda m: int(m['id']) > after.id

        while True:
            retrieve = 200 if limit is None else min(limit, 200)
            if retrieve < 1:
                return

            data, state, limit = await strategy(retrieve, state, limit)

            if predicate:
                data = filter(predicate, data)

            count = 0

            for count, raw_guild in enumerate(data, 1):
                yield Guild(state=self._connection, data=raw_guild)

            if count < 200:
                # There's no data left after this
                break

    async def fetch_template(self, code: Union[Template, str]) -> Template:
        """|coro|

        Gets a :class:`.Template` from a discord.new URL or code.

        Parameters
        -----------
        code: Union[:class:`.Template`, :class:`str`]
            The Discord Template Code or URL (must be a discord.new URL).

        Raises
        -------
        NotFound
            The template is invalid.
        HTTPException
            Getting the template failed.

        Returns
        --------
        :class:`.Template`
            The template from the URL/code.
        """
        code = utils.resolve_template(code)
        data = await self.http.get_template(code)
        return Template(data=data, state=self._connection)

    async def fetch_guild(self, guild_id: int, /, *, with_counts: bool = True) -> Guild:
        """|coro|

        Retrieves a :class:`.Guild` from an ID.

        .. note::

            Using this, you will **not** receive :attr:`.Guild.channels`, :attr:`.Guild.members`,
            :attr:`.Member.activity` and :attr:`.Member.voice` per :class:`.Member`.

        .. note::

            This method is an API call. For general usage, consider :meth:`get_guild` instead.

        .. versionchanged:: 2.0

            ``guild_id`` parameter is now positional-only.


        Parameters
        -----------
        guild_id: :class:`int`
            The guild's ID to fetch from.
        with_counts: :class:`bool`
            Whether to include count information in the guild. This fills the
            :attr:`.Guild.approximate_member_count` and :attr:`.Guild.approximate_presence_count`
            attributes without needing any privileged intents. Defaults to ``True``.

            .. versionadded:: 2.0

        Raises
        ------
        NotFound
            The guild doesn't exist or you got no access to it.
        HTTPException
            Getting the guild failed.

        Returns
        --------
        :class:`.Guild`
            The guild from the ID.
        """
        data = await self.http.get_guild(guild_id, with_counts=with_counts)
        return Guild(data=data, state=self._connection)

    async def fetch_guild_preview(self, guild_id: int) -> GuildPreview:
        """|coro|

        Retrieves a preview of a :class:`.Guild` from an ID. If the guild is discoverable,
        you don't have to be a member of it.

        .. versionadded:: 2.5

        Raises
        ------
        NotFound
            The guild doesn't exist, or is not discoverable and you are not in it.
        HTTPException
            Getting the guild failed.

        Returns
        --------
        :class:`.GuildPreview`
            The guild preview from the ID.
        """
        data = await self.http.get_guild_preview(guild_id)
        return GuildPreview(data=data, state=self._connection)

    async def create_guild(
        self,
        *,
        name: str,
        icon: bytes = MISSING,
        code: str = MISSING,
    ) -> Guild:
        """|coro|

        Creates a :class:`.Guild`.

        Bot accounts in more than 10 guilds are not allowed to create guilds.

        .. versionchanged:: 2.0
            ``name`` and ``icon`` parameters are now keyword-only. The ``region`` parameter has been removed.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The name of the guild.
        icon: Optional[:class:`bytes`]
            The :term:`py:bytes-like object` representing the icon. See :meth:`.ClientUser.edit`
            for more details on what is expected.
        code: :class:`str`
            The code for a template to create the guild with.

            .. versionadded:: 1.4

        Raises
        ------
        HTTPException
            Guild creation failed.
        ValueError
            Invalid icon image format given. Must be PNG or JPG.

        Returns
        -------
        :class:`.Guild`
            The guild created. This is not the same guild that is
            added to cache.
        """
        if icon is not MISSING:
            icon_base64 = utils._bytes_to_base64_data(icon)
        else:
            icon_base64 = None

        if code:
            data = await self.http.create_from_template(code, name, icon_base64)
        else:
            data = await self.http.create_guild(name, icon_base64)
        return Guild(data=data, state=self._connection)

    async def fetch_stage_instance(self, channel_id: int, /) -> StageInstance:
        """|coro|

        Gets a :class:`.StageInstance` for a stage channel id.

        .. versionadded:: 2.0

        Parameters
        -----------
        channel_id: :class:`int`
            The stage channel ID.

        Raises
        -------
        NotFound
            The stage instance or channel could not be found.
        HTTPException
            Getting the stage instance failed.

        Returns
        --------
        :class:`.StageInstance`
            The stage instance from the stage channel ID.
        """
        data = await self.http.get_stage_instance(channel_id)
        guild = self.get_guild(int(data['guild_id']))
        # Guild can technically be None here but this is being explicitly silenced right now.
        return StageInstance(guild=guild, state=self._connection, data=data)  # type: ignore

    # Invite management

    async def fetch_invite(
        self,
        url: Union[Invite, str],
        *,
        with_counts: bool = True,
        with_expiration: bool = True,
        scheduled_event_id: Optional[int] = None,
    ) -> Invite:
        """|coro|

        Gets an :class:`.Invite` from a discord.gg URL or ID.

        .. note::

            If the invite is for a guild you have not joined, the guild and channel
            attributes of the returned :class:`.Invite` will be :class:`.PartialInviteGuild` and
            :class:`.PartialInviteChannel` respectively.

        Parameters
        -----------
        url: Union[:class:`.Invite`, :class:`str`]
            The Discord invite ID or URL (must be a discord.gg URL).
        with_counts: :class:`bool`
            Whether to include count information in the invite. This fills the
            :attr:`.Invite.approximate_member_count` and :attr:`.Invite.approximate_presence_count`
            fields.
        with_expiration: :class:`bool`
            Whether to include the expiration date of the invite. This fills the
            :attr:`.Invite.expires_at` field.

            .. versionadded:: 2.0
        scheduled_event_id: Optional[:class:`int`]
            The ID of the scheduled event this invite is for.

            .. note::

                It is not possible to provide a url that contains an ``event_id`` parameter
                when using this parameter.

            .. versionadded:: 2.0

        Raises
        -------
        ValueError
            The url contains an ``event_id``, but ``scheduled_event_id`` has also been provided.
        NotFound
            The invite has expired or is invalid.
        HTTPException
            Getting the invite failed.

        Returns
        --------
        :class:`.Invite`
            The invite from the URL/ID.
        """

        resolved = utils.resolve_invite(url)

        if scheduled_event_id and resolved.event:
            raise ValueError('Cannot specify scheduled_event_id and contain an event_id in the url.')

        scheduled_event_id = scheduled_event_id or resolved.event

        data = await self.http.get_invite(
            resolved.code,
            with_counts=with_counts,
            with_expiration=with_expiration,
            guild_scheduled_event_id=scheduled_event_id,
        )
        return Invite.from_incomplete(state=self._connection, data=data)

    async def delete_invite(self, invite: Union[Invite, str], /) -> None:
        """|coro|

        Revokes an :class:`.Invite`, URL, or ID to an invite.

        You must have :attr:`~.Permissions.manage_channels` in
        the associated guild to do this.

        .. versionchanged:: 2.0

            ``invite`` parameter is now positional-only.

        Parameters
        ----------
        invite: Union[:class:`.Invite`, :class:`str`]
            The invite to revoke.

        Raises
        -------
        Forbidden
            You do not have permissions to revoke invites.
        NotFound
            The invite is invalid or expired.
        HTTPException
            Revoking the invite failed.
        """

        resolved = utils.resolve_invite(invite)
        await self.http.delete_invite(resolved.code)

    # Miscellaneous stuff

    async def fetch_widget(self, guild_id: int, /) -> Widget:
        """|coro|

        Gets a :class:`.Widget` from a guild ID.

        .. note::

            The guild must have the widget enabled to get this information.

        .. versionchanged:: 2.0

            ``guild_id`` parameter is now positional-only.

        Parameters
        -----------
        guild_id: :class:`int`
            The ID of the guild.

        Raises
        -------
        Forbidden
            The widget for this guild is disabled.
        HTTPException
            Retrieving the widget failed.

        Returns
        --------
        :class:`.Widget`
            The guild's widget.
        """
        data = await self.http.get_widget(guild_id)

        return Widget(state=self._connection, data=data)

    async def application_info(self) -> AppInfo:
        """|coro|

        Retrieves the bot's application information.

        Raises
        -------
        HTTPException
            Retrieving the information failed somehow.

        Returns
        --------
        :class:`.AppInfo`
            The bot's application information.
        """
        data = await self.http.application_info()
        return AppInfo(self._connection, data)

    async def fetch_user(self, user_id: int, /) -> User:
        """|coro|

        Retrieves a :class:`~discord.User` based on their ID.
        You do not have to share any guilds with the user to get this information,
        however many operations do require that you do.

        .. note::

            This method is an API call. If you have :attr:`discord.Intents.members` and member cache enabled, consider :meth:`get_user` instead.

        .. versionchanged:: 2.0

            ``user_id`` parameter is now positional-only.

        Parameters
        -----------
        user_id: :class:`int`
            The user's ID to fetch from.

        Raises
        -------
        NotFound
            A user with this ID does not exist.
        HTTPException
            Fetching the user failed.

        Returns
        --------
        :class:`~discord.User`
            The user you requested.
        """
        data = await self.http.get_user(user_id)
        return User(state=self._connection, data=data)

    async def fetch_channel(self, channel_id: int, /) -> Union[GuildChannel, PrivateChannel, Thread]:
        """|coro|

        Retrieves a :class:`.abc.GuildChannel`, :class:`.abc.PrivateChannel`, or :class:`.Thread` with the specified ID.

        .. note::

            This method is an API call. For general usage, consider :meth:`get_channel` instead.

        .. versionadded:: 1.2

        .. versionchanged:: 2.0

            ``channel_id`` parameter is now positional-only.

        Raises
        -------
        InvalidData
            An unknown channel type was received from Discord.
        HTTPException
            Retrieving the channel failed.
        NotFound
            Invalid Channel ID.
        Forbidden
            You do not have permission to fetch this channel.

        Returns
        --------
        Union[:class:`.abc.GuildChannel`, :class:`.abc.PrivateChannel`, :class:`.Thread`]
            The channel from the ID.
        """
        data = await self.http.get_channel(channel_id)

        factory, ch_type = _threaded_channel_factory(data['type'])
        if factory is None:
            raise InvalidData('Unknown channel type {type} for channel ID {id}.'.format_map(data))

        if ch_type in (ChannelType.group, ChannelType.private):
            # the factory will be a DMChannel or GroupChannel here
            channel = factory(me=self.user, data=data, state=self._connection)  # type: ignore
        else:
            # the factory can't be a DMChannel or GroupChannel here
            guild_id = int(data['guild_id'])  # type: ignore
            guild = self._connection._get_or_create_unavailable_guild(guild_id)
            # the factory should be a GuildChannel or Thread
            channel = factory(guild=guild, state=self._connection, data=data)  # type: ignore

        return channel

    async def fetch_webhook(self, webhook_id: int, /) -> Webhook:
        """|coro|

        Retrieves a :class:`.Webhook` with the specified ID.

        .. versionchanged:: 2.0

            ``webhook_id`` parameter is now positional-only.

        Raises
        --------
        HTTPException
            Retrieving the webhook failed.
        NotFound
            Invalid webhook ID.
        Forbidden
            You do not have permission to fetch this webhook.

        Returns
        ---------
        :class:`.Webhook`
            The webhook you requested.
        """
        data = await self.http.get_webhook(webhook_id)
        return Webhook.from_state(data, state=self._connection)

    async def fetch_sticker(self, sticker_id: int, /) -> Union[StandardSticker, GuildSticker]:
        """|coro|

        Retrieves a :class:`.Sticker` with the specified ID.

        .. versionadded:: 2.0

        Raises
        --------
        HTTPException
            Retrieving the sticker failed.
        NotFound
            Invalid sticker ID.

        Returns
        --------
        Union[:class:`.StandardSticker`, :class:`.GuildSticker`]
            The sticker you requested.
        """
        data = await self.http.get_sticker(sticker_id)
        cls, _ = _sticker_factory(data['type'])
        # The type checker is not smart enough to figure out the constructor is correct
        return cls(state=self._connection, data=data)  # type: ignore

    async def fetch_skus(self) -> List[SKU]:
        """|coro|

        Retrieves the bot's available SKUs.

        .. versionadded:: 2.4

        Raises
        -------
        MissingApplicationID
            The application ID could not be found.
        HTTPException
            Retrieving the SKUs failed.

        Returns
        --------
        List[:class:`.SKU`]
            The bot's available SKUs.
        """

        if self.application_id is None:
            raise MissingApplicationID

        data = await self.http.get_skus(self.application_id)
        return [SKU(state=self._connection, data=sku) for sku in data]

    async def fetch_entitlement(self, entitlement_id: int, /) -> Entitlement:
        """|coro|

        Retrieves a :class:`.Entitlement` with the specified ID.

        .. versionadded:: 2.4

        Parameters
        -----------
        entitlement_id: :class:`int`
            The entitlement's ID to fetch from.

        Raises
        -------
        NotFound
            An entitlement with this ID does not exist.
        MissingApplicationID
            The application ID could not be found.
        HTTPException
            Fetching the entitlement failed.

        Returns
        --------
        :class:`.Entitlement`
            The entitlement you requested.
        """

        if self.application_id is None:
            raise MissingApplicationID

        data = await self.http.get_entitlement(self.application_id, entitlement_id)
        return Entitlement(state=self._connection, data=data)

    async def entitlements(
        self,
        *,
        limit: Optional[int] = 100,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
        skus: Optional[Sequence[Snowflake]] = None,
        user: Optional[Snowflake] = None,
        guild: Optional[Snowflake] = None,
        exclude_ended: bool = False,
        exclude_deleted: bool = True,
    ) -> AsyncIterator[Entitlement]:
        """Retrieves an :term:`asynchronous iterator` of the :class:`.Entitlement` that applications has.

        .. versionadded:: 2.4

        Examples
        ---------

        Usage ::

            async for entitlement in client.entitlements(limit=100):
                print(entitlement.user_id, entitlement.ends_at)

        Flattening into a list ::

            entitlements = [entitlement async for entitlement in client.entitlements(limit=100)]
            # entitlements is now a list of Entitlement...

        All parameters are optional.

        Parameters
        -----------
        limit: Optional[:class:`int`]
            The number of entitlements to retrieve. If ``None``, it retrieves every entitlement for this application.
            Note, however, that this would make it a slow operation. Defaults to ``100``.
        before: Optional[Union[:class:`~discord.abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve entitlements before this date or entitlement.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        after: Optional[Union[:class:`~discord.abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve entitlements after this date or entitlement.
            If a datetime is provided, it is recommended to use a UTC aware datetime.
            If the datetime is naive, it is assumed to be local time.
        skus: Optional[Sequence[:class:`~discord.abc.Snowflake`]]
            A list of SKUs to filter by.
        user: Optional[:class:`~discord.abc.Snowflake`]
            The user to filter by.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to filter by.
        exclude_ended: :class:`bool`
            Whether to exclude ended entitlements. Defaults to ``False``.
        exclude_deleted: :class:`bool`
            Whether to exclude deleted entitlements. Defaults to ``True``.

            .. versionadded:: 2.5

        Raises
        -------
        MissingApplicationID
            The application ID could not be found.
        HTTPException
            Fetching the entitlements failed.
        TypeError
            Both ``after`` and ``before`` were provided, as Discord does not
            support this type of pagination.

        Yields
        --------
        :class:`.Entitlement`
            The entitlement with the application.
        """

        if self.application_id is None:
            raise MissingApplicationID

        if before is not None and after is not None:
            raise TypeError('entitlements pagination does not support both before and after')

        # This endpoint paginates in ascending order.
        endpoint = self.http.get_entitlements

        async def _before_strategy(retrieve: int, before: Optional[Snowflake], limit: Optional[int]):
            before_id = before.id if before else None
            data = await endpoint(
                self.application_id,  # type: ignore  # We already check for None above
                limit=retrieve,
                before=before_id,
                sku_ids=[sku.id for sku in skus] if skus else None,
                user_id=user.id if user else None,
                guild_id=guild.id if guild else None,
                exclude_ended=exclude_ended,
                exclude_deleted=exclude_deleted,
            )

            if data:
                if limit is not None:
                    limit -= len(data)

                before = Object(id=int(data[0]['id']))

            return data, before, limit

        async def _after_strategy(retrieve: int, after: Optional[Snowflake], limit: Optional[int]):
            after_id = after.id if after else None
            data = await endpoint(
                self.application_id,  # type: ignore  # We already check for None above
                limit=retrieve,
                after=after_id,
                sku_ids=[sku.id for sku in skus] if skus else None,
                user_id=user.id if user else None,
                guild_id=guild.id if guild else None,
                exclude_ended=exclude_ended,
            )

            if data:
                if limit is not None:
                    limit -= len(data)

                after = Object(id=int(data[-1]['id']))

            return data, after, limit

        if isinstance(before, datetime.datetime):
            before = Object(id=utils.time_snowflake(before, high=False))
        if isinstance(after, datetime.datetime):
            after = Object(id=utils.time_snowflake(after, high=True))

        if before:
            strategy, state = _before_strategy, before
        else:
            strategy, state = _after_strategy, after

        while True:
            retrieve = 100 if limit is None else min(limit, 100)
            if retrieve < 1:
                return

            data, state, limit = await strategy(retrieve, state, limit)

            # Terminate loop on next iteration; there's no data left after this
            if len(data) < 100:
                limit = 0

            for e in data:
                yield Entitlement(self._connection, e)

    async def create_entitlement(
        self,
        sku: Snowflake,
        owner: Snowflake,
        owner_type: EntitlementOwnerType,
    ) -> None:
        """|coro|

        Creates a test :class:`.Entitlement` for the application.

        .. versionadded:: 2.4

        Parameters
        -----------
        sku: :class:`~discord.abc.Snowflake`
            The SKU to create the entitlement for.
        owner: :class:`~discord.abc.Snowflake`
            The ID of the owner.
        owner_type: :class:`.EntitlementOwnerType`
            The type of the owner.

        Raises
        -------
        MissingApplicationID
            The application ID could not be found.
        NotFound
            The SKU or owner could not be found.
        HTTPException
            Creating the entitlement failed.
        """

        if self.application_id is None:
            raise MissingApplicationID

        await self.http.create_entitlement(self.application_id, sku.id, owner.id, owner_type.value)

    async def fetch_premium_sticker_packs(self) -> List[StickerPack]:
        """|coro|

        Retrieves all available premium sticker packs.

        .. versionadded:: 2.0

        Raises
        -------
        HTTPException
            Retrieving the sticker packs failed.

        Returns
        ---------
        List[:class:`.StickerPack`]
            All available premium sticker packs.
        """
        data = await self.http.list_premium_sticker_packs()
        return [StickerPack(state=self._connection, data=pack) for pack in data['sticker_packs']]

    async def fetch_premium_sticker_pack(self, sticker_pack_id: int, /) -> StickerPack:
        """|coro|

        Retrieves a premium sticker pack with the specified ID.

        .. versionadded:: 2.5

        Parameters
        ----------
        sticker_pack_id: :class:`int`
            The sticker pack's ID to fetch from.

        Raises
        -------
        NotFound
            A sticker pack with this ID does not exist.
        HTTPException
            Retrieving the sticker pack failed.

        Returns
        -------
        :class:`.StickerPack`
            The retrieved premium sticker pack.
        """
        data = await self.http.get_sticker_pack(sticker_pack_id)
        return StickerPack(state=self._connection, data=data)

    async def fetch_soundboard_default_sounds(self) -> List[SoundboardDefaultSound]:
        """|coro|

        Retrieves all default soundboard sounds.

        .. versionadded:: 2.5

        Raises
        -------
        HTTPException
            Retrieving the default soundboard sounds failed.

        Returns
        ---------
        List[:class:`.SoundboardDefaultSound`]
            All default soundboard sounds.
        """
        data = await self.http.get_soundboard_default_sounds()
        return [SoundboardDefaultSound(state=self._connection, data=sound) for sound in data]

    async def create_dm(self, user: Snowflake) -> DMChannel:
        """|coro|

        Creates a :class:`.DMChannel` with this user.

        This should be rarely called, as this is done transparently for most
        people.

        .. versionadded:: 2.0

        Parameters
        -----------
        user: :class:`~discord.abc.Snowflake`
            The user to create a DM with.

        Returns
        -------
        :class:`.DMChannel`
            The channel that was created.
        """
        state = self._connection
        found = state._get_private_channel_by_user(user.id)
        if found:
            return found

        data = await state.http.start_private_message(user.id)
        return state.add_dm_channel(data)

    def add_dynamic_items(self, *items: Type[DynamicItem[Item[Any]]]) -> None:
        r"""Registers :class:`~discord.ui.DynamicItem` classes for persistent listening.

        This method accepts *class types* rather than instances.

        .. versionadded:: 2.4

        Parameters
        -----------
        \*items: Type[:class:`~discord.ui.DynamicItem`]
            The classes of dynamic items to add.

        Raises
        -------
        TypeError
            A class is not a subclass of :class:`~discord.ui.DynamicItem`.
        """

        for item in items:
            if not issubclass(item, DynamicItem):
                raise TypeError(f'expected subclass of DynamicItem not {item.__name__}')

        self._connection.store_dynamic_items(*items)

    def remove_dynamic_items(self, *items: Type[DynamicItem[Item[Any]]]) -> None:
        r"""Removes :class:`~discord.ui.DynamicItem` classes from persistent listening.

        This method accepts *class types* rather than instances.

        .. versionadded:: 2.4

        Parameters
        -----------
        \*items: Type[:class:`~discord.ui.DynamicItem`]
            The classes of dynamic items to remove.

        Raises
        -------
        TypeError
            A class is not a subclass of :class:`~discord.ui.DynamicItem`.
        """

        for item in items:
            if not issubclass(item, DynamicItem):
                raise TypeError(f'expected subclass of DynamicItem not {item.__name__}')

        self._connection.remove_dynamic_items(*items)

    def add_view(self, view: View, *, message_id: Optional[int] = None) -> None:
        """Registers a :class:`~discord.ui.View` for persistent listening.

        This method should be used for when a view is comprised of components
        that last longer than the lifecycle of the program.

        .. versionadded:: 2.0

        Parameters
        ------------
        view: :class:`discord.ui.View`
            The view to register for dispatching.
        message_id: Optional[:class:`int`]
            The message ID that the view is attached to. This is currently used to
            refresh the view's state during message update events. If not given
            then message update events are not propagated for the view.

        Raises
        -------
        TypeError
            A view was not passed.
        ValueError
            The view is not persistent or is already finished. A persistent view has no timeout
            and all their components have an explicitly provided custom_id.
        """

        if not isinstance(view, View):
            raise TypeError(f'expected an instance of View not {view.__class__.__name__}')

        if not view.is_persistent():
            raise ValueError('View is not persistent. Items need to have a custom_id set and View must have no timeout')

        if view.is_finished():
            raise ValueError('View is already finished.')

        self._connection.store_view(view, message_id)

    @property
    def persistent_views(self) -> Sequence[View]:
        """Sequence[:class:`.View`]: A sequence of persistent views added to the client.

        .. versionadded:: 2.0
        """
        return self._connection.persistent_views

    async def create_application_emoji(
        self,
        *,
        name: str,
        image: bytes,
    ) -> Emoji:
        """|coro|

        Create an emoji for the current application.

        .. versionadded:: 2.5

        Parameters
        ----------
        name: :class:`str`
            The emoji name. Must be between 2 and 32 characters long.
        image: :class:`bytes`
            The :term:`py:bytes-like object` representing the image data to use.
            Only JPG, PNG and GIF images are supported.

        Raises
        ------
        MissingApplicationID
            The application ID could not be found.
        HTTPException
            Creating the emoji failed.

        Returns
        -------
        :class:`.Emoji`
            The emoji that was created.
        """
        if self.application_id is None:
            raise MissingApplicationID

        img = utils._bytes_to_base64_data(image)
        data = await self.http.create_application_emoji(self.application_id, name, img)
        return Emoji(guild=Object(0), state=self._connection, data=data)

    async def fetch_application_emoji(self, emoji_id: int, /) -> Emoji:
        """|coro|

        Retrieves an emoji for the current application.

        .. versionadded:: 2.5

        Parameters
        ----------
        emoji_id: :class:`int`
            The emoji ID to retrieve.

        Raises
        ------
        MissingApplicationID
            The application ID could not be found.
        HTTPException
            Retrieving the emoji failed.

        Returns
        -------
        :class:`.Emoji`
            The emoji requested.
        """
        if self.application_id is None:
            raise MissingApplicationID

        data = await self.http.get_application_emoji(self.application_id, emoji_id)
        return Emoji(guild=Object(0), state=self._connection, data=data)

    async def fetch_application_emojis(self) -> List[Emoji]:
        """|coro|

        Retrieves all emojis for the current application.

        .. versionadded:: 2.5

        Raises
        -------
        MissingApplicationID
            The application ID could not be found.
        HTTPException
            Retrieving the emojis failed.

        Returns
        -------
        List[:class:`.Emoji`]
            The list of emojis for the current application.
        """
        if self.application_id is None:
            raise MissingApplicationID

        data = await self.http.get_application_emojis(self.application_id)
        return [Emoji(guild=Object(0), state=self._connection, data=emoji) for emoji in data['items']]
