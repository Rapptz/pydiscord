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

import inspect
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    Iterable,
    List,
    Literal,
    Optional,
    overload,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    runtime_checkable,
)
import types

import discord

from .errors import *

if TYPE_CHECKING:
    from discord.state import Channel
    from discord.threads import Thread

    from .parameters import Parameter
    from ._types import BotT, _Bot, ContextT
    from .context import Context

__all__ = (
    'Converter',
    'ObjectConverter',
    'MemberConverter',
    'UserConverter',
    'MessageConverter',
    'PartialMessageConverter',
    'TextChannelConverter',
    'InviteConverter',
    'GuildConverter',
    'RoleConverter',
    'GameConverter',
    'ColourConverter',
    'ColorConverter',
    'VoiceChannelConverter',
    'StageChannelConverter',
    'EmojiConverter',
    'PartialEmojiConverter',
    'CategoryChannelConverter',
    'ForumChannelConverter',
    'IDConverter',
    'ThreadConverter',
    'GuildChannelConverter',
    'GuildStickerConverter',
    'ScheduledEventConverter',
    'SoundboardSoundConverter',
    'clean_content',
    'Greedy',
    'Range',
    'run_converters',
)


def _get_from_guilds(bot: _Bot, getter: str, argument: Any) -> Any:
    result = None
    for guild in bot.guilds:
        result = getattr(guild, getter)(argument)
        if result:
            return result
    return result


_utils_get = discord.utils.get
T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
CT = TypeVar('CT', bound=discord.abc.GuildChannel)
TT = TypeVar('TT', bound=discord.Thread)


@runtime_checkable
class Converter(Protocol[T_co]):
    """The base class of custom converters that require the :class:`.Context`
    to be passed to be useful.

    This allows you to implement converters that function similar to the
    special cased ``discord`` classes.

    Classes that derive from this should override the :meth:`~.Converter.convert`
    method to do its conversion logic. This method must be a :ref:`coroutine <coroutine>`.
    """

    async def convert(self, ctx: ContextT, argument: str) -> T_co:
        """|coro|

        The method to override to do conversion logic.

        If an error is found while converting, it is recommended to
        raise a :exc:`.CommandError` derived exception as it will
        properly propagate to the error handlers.

        Note that if this method is called manually, :exc:`Exception`
        should be caught to handle the cases where a subclass does
        not explicitly inherit from :exc:`.CommandError`.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context that the argument is being used in.
        argument: :class:`str`
            The argument that is being converted.

        Raises
        -------
        CommandError
            A generic exception occurred when converting the argument.
        BadArgument
            The converter failed to convert the argument.
        """
        raise NotImplementedError('Derived classes need to implement this.')


_ID_REGEX = re.compile(r'([0-9]{15,20})$')


class IDConverter(Converter[T_co]):
    @staticmethod
    def _get_id_match(argument):
        return _ID_REGEX.match(argument)


class ObjectConverter(IDConverter[discord.Object]):
    """Converts to a :class:`~discord.Object`.

    The argument must follow the valid ID or mention formats (e.g. ``<@80088516616269824>``).

    .. versionadded:: 2.0

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by member, role, or channel mention.
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.Object:
        match = self._get_id_match(argument) or re.match(r'<(?:@(?:!|&)?|#)([0-9]{15,20})>$', argument)

        if match is None:
            raise ObjectNotFound(argument)

        result = int(match.group(1))

        return discord.Object(id=result)


class MemberConverter(IDConverter[discord.Member]):
    """Converts to a :class:`~discord.Member`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by username#discriminator (deprecated).
    4. Lookup by username#0 (deprecated, only gets users that migrated from their discriminator).
    5. Lookup by user name.
    6. Lookup by global name.
    7. Lookup by guild nickname.

    .. versionchanged:: 1.5
         Raise :exc:`.MemberNotFound` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 1.5.1
        This converter now lazily fetches members from the gateway and HTTP APIs,
        optionally caching the result if :attr:`.MemberCacheFlags.joined` is enabled.

    .. deprecated:: 2.3
        Looking up users by discriminator will be removed in a future version due to
        the removal of discriminators in an API change.
    """

    async def query_member_named(self, guild: discord.Guild, argument: str) -> Optional[discord.Member]:
        cache = guild._state.member_cache_flags.joined
        username, _, discriminator = argument.rpartition('#')

        # If # isn't found then "discriminator" actually has the username
        if not username:
            discriminator, username = username, discriminator

        if discriminator == '0' or (len(discriminator) == 4 and discriminator.isdigit()):
            lookup = username
            predicate = lambda m: m.name == username and m.discriminator == discriminator
        else:
            lookup = argument
            predicate = lambda m: m.name == argument or m.global_name == argument or m.nick == argument

        members = await guild.query_members(lookup, limit=100, cache=cache)
        return discord.utils.find(predicate, members)

    async def query_member_by_id(self, bot: _Bot, guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
        ws = bot._get_websocket(shard_id=guild.shard_id)
        cache = guild._state.member_cache_flags.joined
        if ws.is_ratelimited():
            # If we're being rate limited on the WS, then fall back to using the HTTP API
            # So we don't have to wait ~60 seconds for the query to finish
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                return None

            if cache:
                guild._add_member(member)
            return member

        # If we're not being rate limited then we can use the websocket to actually query
        members = await guild.query_members(limit=1, user_ids=[user_id], cache=cache)
        if not members:
            return None
        return members[0]

    async def convert(self, ctx: ContextT, argument: str) -> discord.Member:
        bot = ctx.bot
        match = self._get_id_match(argument) or re.match(r'<@!?([0-9]{15,20})>$', argument)
        guild = ctx.guild
        result = None
        user_id = None

        if match is None:
            # not a mention...
            if guild:
                result = guild.get_member_named(argument)
            else:
                result = _get_from_guilds(bot, 'get_member_named', argument)
        else:
            user_id = int(match.group(1))
            if guild:
                result = guild.get_member(user_id) or _utils_get(ctx.message.mentions, id=user_id)
            else:
                result = _get_from_guilds(bot, 'get_member', user_id)

        if not isinstance(result, discord.Member):
            if guild is None:
                raise MemberNotFound(argument)

            if user_id is not None:
                result = await self.query_member_by_id(bot, guild, user_id)
            else:
                result = await self.query_member_named(guild, argument)

            if not result:
                raise MemberNotFound(argument)

        return result


class UserConverter(IDConverter[discord.User]):
    """Converts to a :class:`~discord.User`.

    All lookups are via the global user cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by username#discriminator (deprecated).
    4. Lookup by username#0 (deprecated, only gets users that migrated from their discriminator).
    5. Lookup by user name.
    6. Lookup by global name.

    .. versionchanged:: 1.5
         Raise :exc:`.UserNotFound` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 1.6
        This converter now lazily fetches users from the HTTP APIs if an ID is passed
        and it's not available in cache.

    .. deprecated:: 2.3
        Looking up users by discriminator will be removed in a future version due to
        the removal of discriminators in an API change.
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.User:
        match = self._get_id_match(argument) or re.match(r'<@!?([0-9]{15,20})>$', argument)
        result = None
        state = ctx._state

        if match is not None:
            user_id = int(match.group(1))
            result = ctx.bot.get_user(user_id) or _utils_get(ctx.message.mentions, id=user_id)
            if result is None:
                try:
                    result = await ctx.bot.fetch_user(user_id)
                except discord.HTTPException:
                    raise UserNotFound(argument) from None

            return result  # type: ignore

        username, _, discriminator = argument.rpartition('#')

        # If # isn't found then "discriminator" actually has the username
        if not username:
            discriminator, username = username, discriminator

        if discriminator == '0' or (len(discriminator) == 4 and discriminator.isdigit()):
            predicate = lambda u: u.name == username and u.discriminator == discriminator
        else:
            predicate = lambda u: u.name == argument or u.global_name == argument

        result = discord.utils.find(predicate, state._users.values())
        if result is None:
            raise UserNotFound(argument)

        return result


class PartialMessageConverter(Converter[discord.PartialMessage]):
    """Converts to a :class:`discord.PartialMessage`.

    .. versionadded:: 1.7

    The creation strategy is as follows (in order):

    1. By "{channel ID}-{message ID}" (retrieved by shift-clicking on "Copy ID")
    2. By message ID (The message is assumed to be in the context channel.)
    3. By message URL
    """

    @staticmethod
    def _get_id_matches(ctx: ContextT, argument: str) -> Tuple[Optional[int], int, int]:
        id_regex = re.compile(r'(?:(?P<channel_id>[0-9]{15,20})-)?(?P<message_id>[0-9]{15,20})$')
        link_regex = re.compile(
            r'https?://(?:(ptb|canary|www)\.)?discord(?:app)?\.com/channels/'
            r'(?P<guild_id>[0-9]{15,20}|@me)'
            r'/(?P<channel_id>[0-9]{15,20})/(?P<message_id>[0-9]{15,20})/?$'
        )
        match = id_regex.match(argument) or link_regex.match(argument)
        if not match:
            raise MessageNotFound(argument)
        data = match.groupdict()
        channel_id = discord.utils._get_as_snowflake(data, 'channel_id') or ctx.channel.id
        message_id = int(data['message_id'])
        guild_id = data.get('guild_id')
        if guild_id is None:
            guild_id = ctx.guild and ctx.guild.id
        elif guild_id == '@me':
            guild_id = None
        else:
            guild_id = int(guild_id)
        return guild_id, message_id, channel_id

    @staticmethod
    def _resolve_channel(
        ctx: ContextT, guild_id: Optional[int], channel_id: Optional[int]
    ) -> Optional[Union[Channel, Thread]]:
        if channel_id is None:
            # we were passed just a message id so we can assume the channel is the current context channel
            return ctx.channel

        if guild_id is not None:
            guild = ctx.bot.get_guild(guild_id)
            if guild is None:
                return None
            return guild._resolve_channel(channel_id)

        return ctx.bot.get_channel(channel_id)

    async def convert(self, ctx: ContextT, argument: str) -> discord.PartialMessage:
        guild_id, message_id, channel_id = self._get_id_matches(ctx, argument)
        channel = self._resolve_channel(ctx, guild_id, channel_id)
        if not channel or not isinstance(channel, discord.abc.Messageable):
            raise ChannelNotFound(channel_id)
        return discord.PartialMessage(channel=channel, id=message_id)


class MessageConverter(IDConverter[discord.Message]):
    """Converts to a :class:`discord.Message`.

    .. versionadded:: 1.1

    The lookup strategy is as follows (in order):

    1. Lookup by "{channel ID}-{message ID}" (retrieved by shift-clicking on "Copy ID")
    2. Lookup by message ID (the message **must** be in the context channel)
    3. Lookup by message URL

    .. versionchanged:: 1.5
         Raise :exc:`.ChannelNotFound`, :exc:`.MessageNotFound` or :exc:`.ChannelNotReadable` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.Message:
        guild_id, message_id, channel_id = PartialMessageConverter._get_id_matches(ctx, argument)
        message = ctx.bot._connection._get_message(message_id)
        if message:
            return message
        channel = PartialMessageConverter._resolve_channel(ctx, guild_id, channel_id)
        if not channel or not isinstance(channel, discord.abc.Messageable):
            raise ChannelNotFound(channel_id)
        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            raise MessageNotFound(argument)
        except discord.Forbidden:
            raise ChannelNotReadable(channel)  # type: ignore # type-checker thinks channel could be a DMChannel at this point


class GuildChannelConverter(IDConverter[discord.abc.GuildChannel]):
    """Converts to a :class:`~discord.abc.GuildChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by channel URL.
    4. Lookup by name.

    .. versionadded:: 2.0

    .. versionchanged:: 2.4
        Add lookup by channel URL, accessed via "Copy Link" in the Discord client within channels.
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.abc.GuildChannel:
        return self._resolve_channel(ctx, argument, 'channels', discord.abc.GuildChannel)

    @staticmethod
    def _parse_from_url(argument: str) -> Optional[re.Match[str]]:
        link_regex = re.compile(
            r'https?://(?:(?:ptb|canary|www)\.)?discord(?:app)?\.com/channels/'
            r'(?:[0-9]{15,20}|@me)'
            r'/([0-9]{15,20})(?:/(?:[0-9]{15,20})/?)?$'
        )
        return link_regex.match(argument)

    @staticmethod
    def _resolve_channel(ctx: ContextT, argument: str, attribute: str, type: Type[CT]) -> CT:
        bot = ctx.bot

        match = (
            IDConverter._get_id_match(argument)
            or re.match(r'<#([0-9]{15,20})>$', argument)
            or GuildChannelConverter._parse_from_url(argument)
        )
        result = None
        guild = ctx.guild

        if match is None:
            # not a mention
            if guild:
                iterable: Iterable[CT] = getattr(guild, attribute)
                result: Optional[CT] = discord.utils.get(iterable, name=argument)
            else:

                def check(c):
                    return isinstance(c, type) and c.name == argument

                result = discord.utils.find(check, bot.get_all_channels())  # type: ignore
        else:
            channel_id = int(match.group(1))
            if guild:
                # guild.get_channel returns an explicit union instead of the base class
                result = guild.get_channel(channel_id)  # type: ignore
            else:
                result = _get_from_guilds(bot, 'get_channel', channel_id)

        if not isinstance(result, type):
            raise ChannelNotFound(argument)

        return result

    @staticmethod
    def _resolve_thread(ctx: ContextT, argument: str, attribute: str, type: Type[TT]) -> TT:
        match = (
            IDConverter._get_id_match(argument)
            or re.match(r'<#([0-9]{15,20})>$', argument)
            or GuildChannelConverter._parse_from_url(argument)
        )
        result = None
        guild = ctx.guild

        if match is None:
            # not a mention
            if guild:
                iterable: Iterable[TT] = getattr(guild, attribute)
                result: Optional[TT] = discord.utils.get(iterable, name=argument)
        else:
            thread_id = int(match.group(1))
            if guild:
                result = guild.get_thread(thread_id)  # type: ignore

        if not result or not isinstance(result, type):
            raise ThreadNotFound(argument)

        return result


class TextChannelConverter(IDConverter[discord.TextChannel]):
    """Converts to a :class:`~discord.TextChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by channel URL.
    4. Lookup by name

    .. versionchanged:: 1.5
         Raise :exc:`.ChannelNotFound` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 2.4
        Add lookup by channel URL, accessed via "Copy Link" in the Discord client within channels.
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.TextChannel:
        return GuildChannelConverter._resolve_channel(ctx, argument, 'text_channels', discord.TextChannel)


class VoiceChannelConverter(IDConverter[discord.VoiceChannel]):
    """Converts to a :class:`~discord.VoiceChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by channel URL.
    4. Lookup by name

    .. versionchanged:: 1.5
         Raise :exc:`.ChannelNotFound` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 2.4
        Add lookup by channel URL, accessed via "Copy Link" in the Discord client within channels.
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.VoiceChannel:
        return GuildChannelConverter._resolve_channel(ctx, argument, 'voice_channels', discord.VoiceChannel)


class StageChannelConverter(IDConverter[discord.StageChannel]):
    """Converts to a :class:`~discord.StageChannel`.

    .. versionadded:: 1.7

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by channel URL.
    4. Lookup by name

    .. versionchanged:: 2.4
        Add lookup by channel URL, accessed via "Copy Link" in the Discord client within channels.
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.StageChannel:
        return GuildChannelConverter._resolve_channel(ctx, argument, 'stage_channels', discord.StageChannel)


class CategoryChannelConverter(IDConverter[discord.CategoryChannel]):
    """Converts to a :class:`~discord.CategoryChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by channel URL.
    4. Lookup by name

    .. versionchanged:: 2.4
        Add lookup by channel URL, accessed via "Copy Link" in the Discord client within channels.

    .. versionchanged:: 1.5
         Raise :exc:`.ChannelNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.CategoryChannel:
        return GuildChannelConverter._resolve_channel(ctx, argument, 'categories', discord.CategoryChannel)


class ThreadConverter(IDConverter[discord.Thread]):
    """Converts to a :class:`~discord.Thread`.

    All lookups are via the local guild.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by channel URL.
    4. Lookup by name.

    .. versionadded: 2.0

    .. versionchanged:: 2.4
        Add lookup by channel URL, accessed via "Copy Link" in the Discord client within channels.
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.Thread:
        return GuildChannelConverter._resolve_thread(ctx, argument, 'threads', discord.Thread)


class ForumChannelConverter(IDConverter[discord.ForumChannel]):
    """Converts to a :class:`~discord.ForumChannel`.

    All lookups are via the local guild. If in a DM context, then the lookup
    is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by channel URL.
    4. Lookup by name

    .. versionadded:: 2.0

    .. versionchanged:: 2.4
        Add lookup by channel URL, accessed via "Copy Link" in the Discord client within channels.
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.ForumChannel:
        return GuildChannelConverter._resolve_channel(ctx, argument, 'forums', discord.ForumChannel)


class ColourConverter(Converter[discord.Colour]):
    """Converts to a :class:`~discord.Colour`.

    .. versionchanged:: 1.5
        Add an alias named ColorConverter

    The following formats are accepted:

    - ``0x<hex>``
    - ``#<hex>``
    - ``0x#<hex>``
    - ``rgb(<number>, <number>, <number>)``
    - Any of the ``classmethod`` in :class:`~discord.Colour`

        - The ``_`` in the name can be optionally replaced with spaces.

    Like CSS, ``<number>`` can be either 0-255 or 0-100% and ``<hex>`` can be
    either a 6 digit hex number or a 3 digit hex shortcut (e.g. #fff).

    .. versionchanged:: 1.5
         Raise :exc:`.BadColourArgument` instead of generic :exc:`.BadArgument`

    .. versionchanged:: 1.7
        Added support for ``rgb`` function and 3-digit hex shortcuts
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.Colour:
        try:
            return discord.Colour.from_str(argument)
        except ValueError:
            arg = argument.lower().replace(' ', '_')
            method = getattr(discord.Colour, arg, None)
            if arg.startswith('from_') or method is None or not inspect.ismethod(method):
                raise BadColourArgument(arg)
            return method()


ColorConverter = ColourConverter


class RoleConverter(IDConverter[discord.Role]):
    """Converts to a :class:`~discord.Role`.

    All lookups are via the local guild. If in a DM context, the converter raises
    :exc:`.NoPrivateMessage` exception.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by mention.
    3. Lookup by name

    .. versionchanged:: 1.5
         Raise :exc:`.RoleNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.Role:
        guild = ctx.guild
        if not guild:
            raise NoPrivateMessage()

        match = self._get_id_match(argument) or re.match(r'<@&([0-9]{15,20})>$', argument)
        if match:
            result = guild.get_role(int(match.group(1)))
        else:
            result = discord.utils.get(guild._roles.values(), name=argument)

        if result is None:
            raise RoleNotFound(argument)
        return result


class GameConverter(Converter[discord.Game]):
    """Converts to a :class:`~discord.Game`."""

    async def convert(self, ctx: ContextT, argument: str) -> discord.Game:
        return discord.Game(name=argument)


class InviteConverter(Converter[discord.Invite]):
    """Converts to a :class:`~discord.Invite`.

    This is done via an HTTP request using :meth:`.Bot.fetch_invite`.

    .. versionchanged:: 1.5
         Raise :exc:`.BadInviteArgument` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.Invite:
        try:
            invite = await ctx.bot.fetch_invite(argument)
            return invite
        except Exception as exc:
            raise BadInviteArgument(argument) from exc


class GuildConverter(IDConverter[discord.Guild]):
    """Converts to a :class:`~discord.Guild`.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by name. (There is no disambiguation for Guilds with multiple matching names).

    .. versionadded:: 1.7
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.Guild:
        match = self._get_id_match(argument)
        result = None

        if match is not None:
            guild_id = int(match.group(1))
            result = ctx.bot.get_guild(guild_id)

        if result is None:
            result = discord.utils.get(ctx.bot.guilds, name=argument)

            if result is None:
                raise GuildNotFound(argument)
        return result


class EmojiConverter(IDConverter[discord.Emoji]):
    """Converts to a :class:`~discord.Emoji`.

    All lookups are done for the local guild first, if available. If that lookup
    fails, then it checks the client's global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by extracting ID from the emoji.
    3. Lookup by name

    .. versionchanged:: 1.5
         Raise :exc:`.EmojiNotFound` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.Emoji:
        match = self._get_id_match(argument) or re.match(r'<a?:[a-zA-Z0-9\_]{1,32}:([0-9]{15,20})>$', argument)
        result = None
        bot = ctx.bot
        guild = ctx.guild

        if match is None:
            # Try to get the emoji by name. Try local guild first.
            if guild:
                result = discord.utils.get(guild.emojis, name=argument)

            if result is None:
                result = discord.utils.get(bot.emojis, name=argument)
        else:
            emoji_id = int(match.group(1))

            # Try to look up emoji by id.
            result = bot.get_emoji(emoji_id)

        if result is None:
            raise EmojiNotFound(argument)

        return result


class PartialEmojiConverter(Converter[discord.PartialEmoji]):
    """Converts to a :class:`~discord.PartialEmoji`.

    This is done by extracting the animated flag, name and ID from the emoji.

    .. versionchanged:: 1.5
         Raise :exc:`.PartialEmojiConversionFailure` instead of generic :exc:`.BadArgument`
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.PartialEmoji:
        match = re.match(r'<(a?):([a-zA-Z0-9\_]{1,32}):([0-9]{15,20})>$', argument)

        if match:
            emoji_animated = bool(match.group(1))
            emoji_name = match.group(2)
            emoji_id = int(match.group(3))

            return discord.PartialEmoji.with_state(
                ctx.bot._connection, animated=emoji_animated, name=emoji_name, id=emoji_id
            )

        raise PartialEmojiConversionFailure(argument)


class GuildStickerConverter(IDConverter[discord.GuildSticker]):
    """Converts to a :class:`~discord.GuildSticker`.

    All lookups are done for the local guild first, if available. If that lookup
    fails, then it checks the client's global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by name.

    .. versionadded:: 2.0
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.GuildSticker:
        match = self._get_id_match(argument)
        result = None
        bot = ctx.bot
        guild = ctx.guild

        if match is None:
            # Try to get the sticker by name. Try local guild first.
            if guild:
                result = discord.utils.get(guild.stickers, name=argument)

            if result is None:
                result = discord.utils.get(bot.stickers, name=argument)
        else:
            sticker_id = int(match.group(1))

            # Try to look up sticker by id.
            result = bot.get_sticker(sticker_id)

        if result is None:
            raise GuildStickerNotFound(argument)

        return result


class ScheduledEventConverter(IDConverter[discord.ScheduledEvent]):
    """Converts to a :class:`~discord.ScheduledEvent`.

    Lookups are done for the local guild if available. Otherwise, for a DM context,
    lookup is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by url.
    3. Lookup by name.

    .. versionadded:: 2.0
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.ScheduledEvent:
        guild = ctx.guild
        match = self._get_id_match(argument)
        result = None

        if match:
            # ID match
            event_id = int(match.group(1))
            if guild:
                result = guild.get_scheduled_event(event_id)
            else:
                for guild in ctx.bot.guilds:
                    result = guild.get_scheduled_event(event_id)
                    if result:
                        break
        else:
            pattern = (
                r'https?://(?:(ptb|canary|www)\.)?discord\.com/events/'
                r'(?P<guild_id>[0-9]{15,20})/'
                r'(?P<event_id>[0-9]{15,20})$'
            )
            match = re.match(pattern, argument, flags=re.I)
            if match:
                # URL match
                guild = ctx.bot.get_guild(int(match.group('guild_id')))

                if guild:
                    event_id = int(match.group('event_id'))
                    result = guild.get_scheduled_event(event_id)
            else:
                # lookup by name
                if guild:
                    result = discord.utils.get(guild.scheduled_events, name=argument)
                else:
                    for guild in ctx.bot.guilds:
                        result = discord.utils.get(guild.scheduled_events, name=argument)
                        if result:
                            break
        if result is None:
            raise ScheduledEventNotFound(argument)

        return result


class SoundboardSoundConverter(IDConverter[discord.SoundboardSound]):
    """Converts to a :class:`~discord.SoundboardSound`.

    Lookups are done for the local guild if available. Otherwise, for a DM context,
    lookup is done by the global cache.

    The lookup strategy is as follows (in order):

    1. Lookup by ID.
    2. Lookup by name.

    .. versionadded:: 2.5
    """

    async def convert(self, ctx: ContextT, argument: str) -> discord.SoundboardSound:
        guild = ctx.guild
        match = self._get_id_match(argument)
        result = None

        if match:
            # ID match
            sound_id = int(match.group(1))
            if guild:
                result = guild.get_soundboard_sound(sound_id)
            else:
                result = ctx.bot.get_soundboard_sound(sound_id)
        else:
            # lookup by name
            if guild:
                result = discord.utils.get(guild.soundboard_sounds, name=argument)
            else:
                result = discord.utils.get(ctx.bot.soundboard_sounds, name=argument)
        if result is None:
            raise SoundboardSoundNotFound(argument)

        return result


class clean_content(Converter[str]):
    """Converts the argument to mention scrubbed version of
    said content.

    This behaves similarly to :attr:`~discord.Message.clean_content`.

    Attributes
    ------------
    fix_channel_mentions: :class:`bool`
        Whether to clean channel mentions.
    use_nicknames: :class:`bool`
        Whether to use nicknames when transforming mentions.
    escape_markdown: :class:`bool`
        Whether to also escape special markdown characters.
    remove_markdown: :class:`bool`
        Whether to also remove special markdown characters. This option is not supported with ``escape_markdown``

        .. versionadded:: 1.7
    """

    def __init__(
        self,
        *,
        fix_channel_mentions: bool = False,
        use_nicknames: bool = True,
        escape_markdown: bool = False,
        remove_markdown: bool = False,
    ) -> None:
        self.fix_channel_mentions = fix_channel_mentions
        self.use_nicknames = use_nicknames
        self.escape_markdown = escape_markdown
        self.remove_markdown = remove_markdown

    async def convert(self, ctx: ContextT, argument: str) -> str:
        msg = ctx.message

        if ctx.guild:

            def resolve_member(id: int) -> str:
                m = _utils_get(msg.mentions, id=id) or ctx.guild.get_member(id)  # type: ignore
                return f'@{m.display_name if self.use_nicknames else m.name}' if m else '@deleted-user'

            def resolve_role(id: int) -> str:
                r = _utils_get(msg.role_mentions, id=id) or ctx.guild.get_role(id)  # type: ignore
                return f'@{r.name}' if r else '@deleted-role'

        else:

            def resolve_member(id: int) -> str:
                m = _utils_get(msg.mentions, id=id) or ctx.bot.get_user(id)
                return f'@{m.display_name}' if m else '@deleted-user'

            def resolve_role(id: int) -> str:
                return '@deleted-role'

        if self.fix_channel_mentions and ctx.guild:

            def resolve_channel(id: int) -> str:
                c = ctx.guild._resolve_channel(id)  # type: ignore
                return f'#{c.name}' if c else '#deleted-channel'

        else:

            def resolve_channel(id: int) -> str:
                return f'<#{id}>'

        transforms = {
            '@': resolve_member,
            '@!': resolve_member,
            '#': resolve_channel,
            '@&': resolve_role,
        }

        def repl(match: re.Match) -> str:
            type = match[1]
            id = int(match[2])
            transformed = transforms[type](id)
            return transformed

        result = re.sub(r'<(@[!&]?|#)([0-9]{15,20})>', repl, argument)
        if self.escape_markdown:
            result = discord.utils.escape_markdown(result)
        elif self.remove_markdown:
            result = discord.utils.remove_markdown(result)

        # Completely ensure no mentions escape:
        return discord.utils.escape_mentions(result)


class Greedy(List[T]):
    r"""A special converter that greedily consumes arguments until it can't.
    As a consequence of this behaviour, most input errors are silently discarded,
    since it is used as an indicator of when to stop parsing.

    When a parser error is met the greedy converter stops converting, undoes the
    internal string parsing routine, and continues parsing regularly.

    For example, in the following code:

    .. code-block:: python3

        @commands.command()
        async def test(ctx, numbers: Greedy[int], reason: str):
            await ctx.send("numbers: {}, reason: {}".format(numbers, reason))

    An invocation of ``[p]test 1 2 3 4 5 6 hello`` would pass ``numbers`` with
    ``[1, 2, 3, 4, 5, 6]`` and ``reason`` with ``hello``\.

    For more information, check :ref:`ext_commands_special_converters`.

    .. note::

        For interaction based contexts the conversion error is propagated
        rather than swallowed due to the difference in user experience with
        application commands.
    """

    __slots__ = ('converter',)

    def __init__(self, *, converter: T) -> None:
        self.converter: T = converter

    def __repr__(self) -> str:
        converter = getattr(self.converter, '__name__', repr(self.converter))
        return f'Greedy[{converter}]'

    def __class_getitem__(cls, params: Union[Tuple[T], T]) -> Greedy[T]:
        if not isinstance(params, tuple):
            params = (params,)
        if len(params) != 1:
            raise TypeError('Greedy[...] only takes a single argument')
        converter = params[0]

        args = getattr(converter, '__args__', ())
        if discord.utils.PY_310 and converter.__class__ is types.UnionType:  # type: ignore
            converter = Union[args]  # type: ignore

        origin = getattr(converter, '__origin__', None)

        if not (callable(converter) or isinstance(converter, Converter) or origin is not None):
            raise TypeError('Greedy[...] expects a type or a Converter instance.')

        if converter in (str, type(None)) or origin is Greedy:
            raise TypeError(f'Greedy[{converter.__name__}] is invalid.')  # type: ignore

        if origin is Union and type(None) in args:
            raise TypeError(f'Greedy[{converter!r}] is invalid.')

        return cls(converter=converter)

    @property
    def constructed_converter(self) -> Any:
        # Only construct a converter once in order to maintain state between convert calls
        if (
            inspect.isclass(self.converter)
            and issubclass(self.converter, Converter)
            and not inspect.ismethod(self.converter.convert)
        ):
            return self.converter()
        return self.converter


if TYPE_CHECKING:
    from typing_extensions import Annotated as Range
else:

    class Range:
        """A special converter that can be applied to a parameter to require a numeric
        or string type to fit within the range provided.

        During type checking time this is equivalent to :obj:`typing.Annotated` so type checkers understand
        the intent of the code.

        Some example ranges:

        - ``Range[int, 10]`` means the minimum is 10 with no maximum.
        - ``Range[int, None, 10]`` means the maximum is 10 with no minimum.
        - ``Range[int, 1, 10]`` means the minimum is 1 and the maximum is 10.
        - ``Range[float, 1.0, 5.0]`` means the minimum is 1.0 and the maximum is 5.0.
        - ``Range[str, 1, 10]`` means the minimum length is 1 and the maximum length is 10.

        Inside a :class:`HybridCommand` this functions equivalently to :class:`discord.app_commands.Range`.

        If the value cannot be converted to the provided type or is outside the given range,
        :class:`~.ext.commands.BadArgument` or :class:`~.ext.commands.RangeError` is raised to
        the appropriate error handlers respectively.

        .. versionadded:: 2.0

        Examples
        ----------

        .. code-block:: python3

            @bot.command()
            async def range(ctx: commands.Context, value: commands.Range[int, 10, 12]):
                await ctx.send(f'Your value is {value}')
        """

        def __init__(
            self,
            *,
            annotation: Any,
            min: Optional[Union[int, float]] = None,
            max: Optional[Union[int, float]] = None,
        ) -> None:
            self.annotation: Any = annotation
            self.min: Optional[Union[int, float]] = min
            self.max: Optional[Union[int, float]] = max

            if min and max and min > max:
                raise TypeError('minimum cannot be larger than maximum')

        async def convert(self, ctx: ContextT, value: str) -> Union[int, float]:
            try:
                count = converted = self.annotation(value)
            except ValueError:
                raise BadArgument(
                    f'Converting to "{self.annotation.__name__}" failed for parameter "{ctx.current_parameter.name}".'
                )

            if self.annotation is str:
                count = len(value)

            if (self.min is not None and count < self.min) or (self.max is not None and count > self.max):
                raise RangeError(converted, minimum=self.min, maximum=self.max)

            return converted

        def __call__(self) -> None:
            # Trick to allow it inside typing.Union
            pass

        def __or__(self, rhs) -> Any:
            return Union[self, rhs]

        def __repr__(self) -> str:
            return f'{self.__class__.__name__}[{self.annotation.__name__}, {self.min}, {self.max}]'

        def __class_getitem__(cls, obj) -> Range:
            if not isinstance(obj, tuple):
                raise TypeError(f'expected tuple for arguments, received {obj.__class__.__name__} instead')

            if len(obj) == 2:
                obj = (*obj, None)
            elif len(obj) != 3:
                raise TypeError('Range accepts either two or three arguments with the first being the type of range.')

            annotation, min, max = obj

            if min is None and max is None:
                raise TypeError('Range must not be empty')

            if min is not None and max is not None:
                # At this point max and min are both not none
                if type(min) != type(max):
                    raise TypeError('Both min and max in Range must be the same type')

            if annotation not in (int, float, str):
                raise TypeError(f'expected int, float, or str as range type, received {annotation!r} instead')

            if annotation in (str, int):
                cast = int
            else:
                cast = float

            return cls(
                annotation=annotation,
                min=cast(min) if min is not None else None,
                max=cast(max) if max is not None else None,
            )


def _convert_to_bool(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
        return True
    elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
        return False
    else:
        raise BadBoolArgument(lowered)


_GenericAlias = type(List[T])  # type: ignore


def is_generic_type(tp: Any, *, _GenericAlias: type = _GenericAlias) -> bool:
    return isinstance(tp, type) and issubclass(tp, Generic) or isinstance(tp, _GenericAlias)


CONVERTER_MAPPING: Dict[type, Any] = {
    discord.Object: ObjectConverter,
    discord.Member: MemberConverter,
    discord.User: UserConverter,
    discord.Message: MessageConverter,
    discord.PartialMessage: PartialMessageConverter,
    discord.TextChannel: TextChannelConverter,
    discord.Invite: InviteConverter,
    discord.Guild: GuildConverter,
    discord.Role: RoleConverter,
    discord.Game: GameConverter,
    discord.Colour: ColourConverter,
    discord.VoiceChannel: VoiceChannelConverter,
    discord.StageChannel: StageChannelConverter,
    discord.Emoji: EmojiConverter,
    discord.PartialEmoji: PartialEmojiConverter,
    discord.CategoryChannel: CategoryChannelConverter,
    discord.Thread: ThreadConverter,
    discord.abc.GuildChannel: GuildChannelConverter,
    discord.GuildSticker: GuildStickerConverter,
    discord.ScheduledEvent: ScheduledEventConverter,
    discord.ForumChannel: ForumChannelConverter,
    discord.SoundboardSound: SoundboardSoundConverter,
}


async def _actual_conversion(ctx: ContextT, converter: Any, argument: str, param: inspect.Parameter):
    if converter is bool:
        return _convert_to_bool(argument)

    try:
        module = converter.__module__
    except AttributeError:
        pass
    else:
        if module is not None and (module.startswith('discord.') and not module.endswith('converter')):
            converter = CONVERTER_MAPPING.get(converter, converter)

    try:
        if inspect.isclass(converter) and issubclass(converter, Converter):
            if inspect.ismethod(converter.convert):
                return await converter.convert(ctx, argument)
            else:
                return await converter().convert(ctx, argument)
        elif isinstance(converter, Converter):
            return await converter.convert(ctx, argument)  # type: ignore
    except CommandError:
        raise
    except Exception as exc:
        raise ConversionError(converter, exc) from exc  # type: ignore

    try:
        return converter(argument)
    except CommandError:
        raise
    except Exception as exc:
        try:
            name = converter.__name__
        except AttributeError:
            name = converter.__class__.__name__

        raise BadArgument(f'Converting to "{name}" failed for parameter "{param.name}".') from exc


@overload
async def run_converters(
    ctx: ContextT, converter: Union[Type[Converter[T]], Converter[T]], argument: str, param: Parameter
) -> T:
    ...


@overload
async def run_converters(ctx: ContextT, converter: Any, argument: str, param: Parameter) -> Any:
    ...


async def run_converters(ctx: ContextT, converter: Any, argument: str, param: Parameter) -> Any:
    """|coro|

    Runs converters for a given converter, argument, and parameter.

    This function does the same work that the library does under the hood.

    .. versionadded:: 2.0

    Parameters
    ------------
    ctx: :class:`Context`
        The invocation context to run the converters under.
    converter: Any
        The converter to run, this corresponds to the annotation in the function.
    argument: :class:`str`
        The argument to convert to.
    param: :class:`Parameter`
        The parameter being converted. This is mainly for error reporting.

    Raises
    -------
    CommandError
        The converter failed to convert.

    Returns
    --------
    Any
        The resulting conversion.
    """
    origin = getattr(converter, '__origin__', None)

    if origin is Union:
        errors = []
        _NoneType = type(None)
        union_args = converter.__args__
        for conv in union_args:
            # if we got to this part in the code, then the previous conversions have failed
            # so we should just undo the view, return the default, and allow parsing to continue
            # with the other parameters
            if conv is _NoneType and param.kind != param.VAR_POSITIONAL:
                ctx.view.undo()
                return None if param.required else await param.get_default(ctx)

            try:
                value = await run_converters(ctx, conv, argument, param)
            except CommandError as exc:
                errors.append(exc)
            else:
                return value

        # if we're here, then we failed all the converters
        raise BadUnionArgument(param, union_args, errors)

    if origin is Literal:
        errors = []
        conversions = {}
        literal_args = converter.__args__
        for literal in literal_args:
            literal_type = type(literal)
            try:
                value = conversions[literal_type]
            except KeyError:
                try:
                    value = await _actual_conversion(ctx, literal_type, argument, param)
                except CommandError as exc:
                    errors.append(exc)
                    conversions[literal_type] = object()
                    continue
                else:
                    conversions[literal_type] = value

            if value == literal:
                return value

        # if we're here, then we failed to match all the literals
        raise BadLiteralArgument(param, literal_args, errors, argument)

    # This must be the last if-clause in the chain of origin checking
    # Nearly every type is a generic type within the typing library
    # So care must be taken to make sure a more specialised origin handle
    # isn't overwritten by the widest if clause
    if origin is not None and is_generic_type(converter):
        converter = origin

    return await _actual_conversion(ctx, converter, argument, param)
