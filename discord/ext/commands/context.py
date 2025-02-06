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

import re
from typing import TYPE_CHECKING, Any, Dict, Generator, Generic, List, Optional, TypeVar, Union, Sequence, Type, overload

import discord.abc
import discord.utils
from discord import Interaction, Message, Attachment, MessageType, User, PartialMessageable, Permissions, ChannelType, Thread
from discord.context_managers import Typing
from .view import StringView

from ._types import BotT

if TYPE_CHECKING:
    from typing_extensions import Self, ParamSpec, TypeGuard

    from discord.abc import MessageableChannel
    from discord.guild import Guild
    from discord.member import Member
    from discord.state import ConnectionState
    from discord.user import ClientUser
    from discord.voice_client import VoiceProtocol
    from discord.embeds import Embed
    from discord.file import File
    from discord.mentions import AllowedMentions
    from discord.sticker import GuildSticker, StickerItem
    from discord.message import MessageReference, PartialMessage
    from discord.ui import View
    from discord.types.interactions import ApplicationCommandInteractionData
    from discord.poll import Poll

    from .cog import Cog
    from .core import Command
    from .parameters import Parameter

    from types import TracebackType
    from ._types import ContextT

    BE = TypeVar('BE', bound=BaseException)

# fmt: off
__all__ = (
    'Context',
)
# fmt: on

MISSING: Any = discord.utils.MISSING


T = TypeVar('T')
CogT = TypeVar('CogT', bound="Cog")

if TYPE_CHECKING:
    P = ParamSpec('P')
else:
    P = TypeVar('P')


def is_cog(obj: Any) -> TypeGuard[Cog]:
    return hasattr(obj, '__cog_commands__')


class DeferTyping:
    def __init__(self, ctx: ContextT, *, ephemeral: bool):
        self.ctx: ContextT = ctx
        self.ephemeral: bool = ephemeral

    async def do_defer(self) -> None:
        if self.ctx.interaction and not self.ctx.interaction.response.is_done():
            await self.ctx.interaction.response.defer(ephemeral=self.ephemeral)

    def __await__(self) -> Generator[Any, None, None]:
        return self.do_defer().__await__()

    async def __aenter__(self) -> None:
        await self.do_defer()

    async def __aexit__(
        self,
        exc_type: Optional[Type[BE]],
        exc: Optional[BE],
        traceback: Optional[TracebackType],
    ) -> None:
        pass


class Context(discord.abc.Messageable, Generic[BotT]):
    r"""Represents the context in which a command is being invoked under.

    This class contains a lot of meta data to help you understand more about
    the invocation context. This class is not created manually and is instead
    passed around to commands as the first parameter.

    This class implements the :class:`~discord.abc.Messageable` ABC.

    Attributes
    -----------
    message: :class:`.Message`
        The message that triggered the command being executed.

        .. note::

            In the case of an interaction based context, this message is "synthetic"
            and does not actually exist. Therefore, the ID on it is invalid similar
            to ephemeral messages.
    bot: :class:`.Bot`
        The bot that contains the command being executed.
    args: :class:`list`
        The list of transformed arguments that were passed into the command.
        If this is accessed during the :func:`.on_command_error` event
        then this list could be incomplete.
    kwargs: :class:`dict`
        A dictionary of transformed arguments that were passed into the command.
        Similar to :attr:`args`\, if this is accessed in the
        :func:`.on_command_error` event then this dict could be incomplete.
    current_parameter: Optional[:class:`Parameter`]
        The parameter that is currently being inspected and converted.
        This is only of use for within converters.

        .. versionadded:: 2.0
    current_argument: Optional[:class:`str`]
        The argument string of the :attr:`current_parameter` that is currently being converted.
        This is only of use for within converters.

        .. versionadded:: 2.0
    interaction: Optional[:class:`~discord.Interaction`]
        The interaction associated with this context.

        .. versionadded:: 2.0
    prefix: Optional[:class:`str`]
        The prefix that was used to invoke the command. For interaction based contexts,
        this is ``/`` for slash commands and ``\u200b`` for context menu commands.
    command: Optional[:class:`Command`]
        The command that is being invoked currently.
    invoked_with: Optional[:class:`str`]
        The command name that triggered this invocation. Useful for finding out
        which alias called the command.
    invoked_parents: List[:class:`str`]
        The command names of the parents that triggered this invocation. Useful for
        finding out which aliases called the command.

        For example in commands ``?a b c test``, the invoked parents are ``['a', 'b', 'c']``.

        .. versionadded:: 1.7

    invoked_subcommand: Optional[:class:`Command`]
        The subcommand that was invoked.
        If no valid subcommand was invoked then this is equal to ``None``.
    subcommand_passed: Optional[:class:`str`]
        The string that was attempted to call a subcommand. This does not have
        to point to a valid registered subcommand and could just point to a
        nonsense string. If nothing was passed to attempt a call to a
        subcommand then this is set to ``None``.
    command_failed: :class:`bool`
        A boolean that indicates if the command failed to be parsed, checked,
        or invoked.
    """

    def __init__(
        self,
        *,
        message: Message,
        bot: BotT,
        view: StringView,
        args: List[Any] = MISSING,
        kwargs: Dict[str, Any] = MISSING,
        prefix: Optional[str] = None,
        command: Optional[Command[Any, ..., Any]] = None,
        invoked_with: Optional[str] = None,
        invoked_parents: List[str] = MISSING,
        invoked_subcommand: Optional[Command[Any, ..., Any]] = None,
        subcommand_passed: Optional[str] = None,
        command_failed: bool = False,
        current_parameter: Optional[Parameter] = None,
        current_argument: Optional[str] = None,
        interaction: Optional[Interaction[BotT]] = None,
    ):
        self.message: Message = message
        self.bot: BotT = bot
        self.args: List[Any] = args or []
        self.kwargs: Dict[str, Any] = kwargs or {}
        self.prefix: Optional[str] = prefix
        self.command: Optional[Command[Any, ..., Any]] = command
        self.view: StringView = view
        self.invoked_with: Optional[str] = invoked_with
        self.invoked_parents: List[str] = invoked_parents or []
        self.invoked_subcommand: Optional[Command[Any, ..., Any]] = invoked_subcommand
        self.subcommand_passed: Optional[str] = subcommand_passed
        self.command_failed: bool = command_failed
        self.current_parameter: Optional[Parameter] = current_parameter
        self.current_argument: Optional[str] = current_argument
        self.interaction: Optional[Interaction[BotT]] = interaction
        self._state: ConnectionState = self.message._state

    @classmethod
    async def from_interaction(cls, interaction: Interaction[BotT], /) -> Self:
        """|coro|

        Creates a context from a :class:`discord.Interaction`. This only
        works on application command based interactions, such as slash commands
        or context menus.

        On slash command based interactions this creates a synthetic :class:`~discord.Message`
        that points to an ephemeral message that the command invoker has executed. This means
        that :attr:`Context.author` returns the member that invoked the command.

        In a message context menu based interaction, the :attr:`Context.message` attribute
        is the message that the command is being executed on. This means that :attr:`Context.author`
        returns the author of the message being targetted. To get the member that invoked
        the command then :attr:`discord.Interaction.user` should be used instead.

        .. versionadded:: 2.0

        Parameters
        -----------
        interaction: :class:`discord.Interaction`
            The interaction to create a context with.

        Raises
        -------
        ValueError
            The interaction does not have a valid command.
        TypeError
            The interaction client is not derived from :class:`Bot` or :class:`AutoShardedBot`.
        """

        # Circular import
        from .bot import BotBase

        if not isinstance(interaction.client, BotBase):
            raise TypeError('Interaction client is not derived from commands.Bot or commands.AutoShardedBot')

        command = interaction.command
        if command is None:
            raise ValueError('interaction does not have command data')

        bot: BotT = interaction.client
        data: ApplicationCommandInteractionData = interaction.data  # type: ignore
        if interaction.message is None:
            synthetic_payload = {
                'id': interaction.id,
                'reactions': [],
                'embeds': [],
                'mention_everyone': False,
                'tts': False,
                'pinned': False,
                'edited_timestamp': None,
                'type': MessageType.chat_input_command if data.get('type', 1) == 1 else MessageType.context_menu_command,
                'flags': 64,
                'content': '',
                'mentions': [],
                'mention_roles': [],
                'attachments': [],
            }

            if interaction.channel_id is None:
                raise RuntimeError('interaction channel ID is null, this is probably a Discord bug')

            channel = interaction.channel or PartialMessageable(
                state=interaction._state, guild_id=interaction.guild_id, id=interaction.channel_id
            )
            message = Message(state=interaction._state, channel=channel, data=synthetic_payload)  # type: ignore
            message.author = interaction.user
            message.attachments = [a for _, a in interaction.namespace if isinstance(a, Attachment)]
        else:
            message = interaction.message

        prefix = '/' if data.get('type', 1) == 1 else '\u200b'  # Mock the prefix
        ctx = cls(
            message=message,
            bot=bot,
            view=StringView(''),
            args=[],
            kwargs={},
            prefix=prefix,
            interaction=interaction,
            invoked_with=command.name,
            command=command,  # type: ignore # this will be a hybrid command, technically
        )
        interaction._baton = ctx
        ctx.command_failed = interaction.command_failed
        return ctx

    async def invoke(self, command: Command[CogT, P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
        r"""|coro|

        Calls a command with the arguments given.

        This is useful if you want to just call the callback that a
        :class:`.Command` holds internally.

        .. note::

            This does not handle converters, checks, cooldowns, pre-invoke,
            or after-invoke hooks in any matter. It calls the internal callback
            directly as-if it was a regular function.

            You must take care in passing the proper arguments when
            using this function.

        .. versionchanged:: 2.0

            ``command`` parameter is now positional-only.

        Parameters
        -----------
        command: :class:`.Command`
            The command that is going to be called.
        \*args
            The arguments to use.
        \*\*kwargs
            The keyword arguments to use.

        Raises
        -------
        TypeError
            The command argument to invoke is missing.
        """
        return await command(self, *args, **kwargs)

    async def reinvoke(self, *, call_hooks: bool = False, restart: bool = True) -> None:
        """|coro|

        Calls the command again.

        This is similar to :meth:`~.Context.invoke` except that it bypasses
        checks, cooldowns, and error handlers.

        .. note::

            If you want to bypass :exc:`.UserInputError` derived exceptions,
            it is recommended to use the regular :meth:`~.Context.invoke`
            as it will work more naturally. After all, this will end up
            using the old arguments the user has used and will thus just
            fail again.

        Parameters
        ------------
        call_hooks: :class:`bool`
            Whether to call the before and after invoke hooks.
        restart: :class:`bool`
            Whether to start the call chain from the very beginning
            or where we left off (i.e. the command that caused the error).
            The default is to start where we left off.

        Raises
        -------
        ValueError
            The context to reinvoke is not valid.
        """
        cmd = self.command
        view = self.view
        if cmd is None:
            raise ValueError('This context is not valid.')

        # some state to revert to when we're done
        index, previous = view.index, view.previous
        invoked_with = self.invoked_with
        invoked_subcommand = self.invoked_subcommand
        invoked_parents = self.invoked_parents
        subcommand_passed = self.subcommand_passed

        if restart:
            to_call = cmd.root_parent or cmd
            view.index = len(self.prefix or '')
            view.previous = 0
            self.invoked_parents = []
            self.invoked_with = view.get_word()  # advance to get the root command
        else:
            to_call = cmd

        try:
            await to_call.reinvoke(self, call_hooks=call_hooks)
        finally:
            self.command = cmd
            view.index = index
            view.previous = previous
            self.invoked_with = invoked_with
            self.invoked_subcommand = invoked_subcommand
            self.invoked_parents = invoked_parents
            self.subcommand_passed = subcommand_passed

    @property
    def valid(self) -> bool:
        """:class:`bool`: Checks if the invocation context is valid to be invoked with."""
        return self.prefix is not None and self.command is not None

    async def _get_channel(self) -> discord.abc.Messageable:
        return self.channel

    @property
    def clean_prefix(self) -> str:
        """:class:`str`: The cleaned up invoke prefix. i.e. mentions are ``@name`` instead of ``<@id>``.

        .. versionadded:: 2.0
        """
        if self.prefix is None:
            return ''

        user = self.me
        # this breaks if the prefix mention is not the bot itself but I
        # consider this to be an *incredibly* strange use case. I'd rather go
        # for this common use case rather than waste performance for the
        # odd one.
        pattern = re.compile(r"<@!?%s>" % user.id)
        return pattern.sub("@%s" % user.display_name.replace('\\', r'\\'), self.prefix)

    @property
    def cog(self) -> Optional[Cog]:
        """Optional[:class:`.Cog`]: Returns the cog associated with this context's command. None if it does not exist."""

        if self.command is None:
            return None
        return self.command.cog

    @property
    def filesize_limit(self) -> int:
        """:class:`int`: Returns the maximum number of bytes files can have when uploaded to this guild or DM channel associated with this context.

        .. versionadded:: 2.3
        """
        return self.guild.filesize_limit if self.guild is not None else discord.utils.DEFAULT_FILE_SIZE_LIMIT_BYTES

    @discord.utils.cached_property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`.Guild`]: Returns the guild associated with this context's command. None if not available."""
        return self.message.guild

    @discord.utils.cached_property
    def channel(self) -> MessageableChannel:
        """Union[:class:`.abc.Messageable`]: Returns the channel associated with this context's command.
        Shorthand for :attr:`.Message.channel`.
        """
        return self.message.channel

    @discord.utils.cached_property
    def author(self) -> Union[User, Member]:
        """Union[:class:`~discord.User`, :class:`.Member`]:
        Returns the author associated with this context's command. Shorthand for :attr:`.Message.author`
        """
        return self.message.author

    @discord.utils.cached_property
    def me(self) -> Union[Member, ClientUser]:
        """Union[:class:`.Member`, :class:`.ClientUser`]:
        Similar to :attr:`.Guild.me` except it may return the :class:`.ClientUser` in private message contexts.
        """
        # bot.user will never be None at this point.
        return self.guild.me if self.guild is not None else self.bot.user  # type: ignore

    @discord.utils.cached_property
    def permissions(self) -> Permissions:
        """:class:`.Permissions`: Returns the resolved permissions for the invoking user in this channel.
        Shorthand for :meth:`.abc.GuildChannel.permissions_for` or :attr:`.Interaction.permissions`.

        .. versionadded:: 2.0
        """
        if self.interaction is None and self.channel.type is ChannelType.private:
            return Permissions._dm_permissions()
        if not self.interaction:
            # channel and author will always match relevant types here
            return self.channel.permissions_for(self.author)  # type: ignore
        base = self.interaction.permissions
        if self.channel.type in (ChannelType.voice, ChannelType.stage_voice):
            if not base.connect:
                # voice channels cannot be edited by people who can't connect to them
                # It also implicitly denies all other voice perms
                denied = Permissions.voice()
                denied.update(manage_channels=True, manage_roles=True)
                base.value &= ~denied.value
        else:
            # text channels do not have voice related permissions
            denied = Permissions.voice()
            base.value &= ~denied.value
        return base

    @discord.utils.cached_property
    def bot_permissions(self) -> Permissions:
        """:class:`.Permissions`: Returns the resolved permissions for the bot in this channel.
        Shorthand for :meth:`.abc.GuildChannel.permissions_for` or :attr:`.Interaction.app_permissions`.

        For interaction-based commands, this will reflect the effective permissions
        for :class:`Context` calls, which may differ from calls through
        other :class:`.abc.Messageable` endpoints, like :attr:`channel`.

        Notably, sending messages, embedding links, and attaching files are always
        permitted, while reading messages might not be.

        .. versionadded:: 2.0
        """
        channel = self.channel
        if self.interaction is None and channel.type == ChannelType.private:
            return Permissions._dm_permissions()
        if not self.interaction:
            # channel and me will always match relevant types here
            return channel.permissions_for(self.me)  # type: ignore
        guild = channel.guild
        base = self.interaction.app_permissions
        if self.channel.type in (ChannelType.voice, ChannelType.stage_voice):
            if not base.connect:
                # voice channels cannot be edited by people who can't connect to them
                # It also implicitly denies all other voice perms
                denied = Permissions.voice()
                denied.update(manage_channels=True, manage_roles=True)
                base.value &= ~denied.value
        else:
            # text channels do not have voice related permissions
            denied = Permissions.voice()
            base.value &= ~denied.value
        base.update(
            embed_links=True,
            attach_files=True,
            send_tts_messages=False,
        )
        if isinstance(channel, Thread):
            base.send_messages_in_threads = True
        else:
            base.send_messages = True
        return base

    @property
    def voice_client(self) -> Optional[VoiceProtocol]:
        r"""Optional[:class:`.VoiceProtocol`]: A shortcut to :attr:`.Guild.voice_client`\, if applicable."""
        g = self.guild
        return g.voice_client if g else None

    async def send_help(self, *args: Any) -> Any:
        """send_help(entity=<bot>)

        |coro|

        Shows the help command for the specified entity if given.
        The entity can be a command or a cog.

        If no entity is given, then it'll show help for the
        entire bot.

        If the entity is a string, then it looks up whether it's a
        :class:`Cog` or a :class:`Command`.

        .. note::

            Due to the way this function works, instead of returning
            something similar to :meth:`~.commands.HelpCommand.command_not_found`
            this returns ``None`` on bad input or no help command.

        Parameters
        ------------
        entity: Optional[Union[:class:`Command`, :class:`Cog`, :class:`str`]]
            The entity to show help for.

        Returns
        --------
        Any
            The result of the help command, if any.
        """
        from .core import Command, Group, wrap_callback
        from .errors import CommandError

        bot = self.bot
        cmd = bot.help_command

        if cmd is None:
            return None

        cmd = cmd.copy()
        cmd.context = self

        if len(args) == 0:
            await cmd.prepare_help_command(self, None)
            mapping = cmd.get_bot_mapping()
            injected = wrap_callback(cmd.send_bot_help)
            try:
                return await injected(mapping)
            except CommandError as e:
                await cmd.on_help_command_error(self, e)
                return None

        entity = args[0]
        if isinstance(entity, str):
            entity = bot.get_cog(entity) or bot.get_command(entity)

        if entity is None:
            return None

        try:
            entity.qualified_name
        except AttributeError:
            # if we're here then it's not a cog, group, or command.
            return None

        await cmd.prepare_help_command(self, entity.qualified_name)

        try:
            if is_cog(entity):
                injected = wrap_callback(cmd.send_cog_help)
                return await injected(entity)
            elif isinstance(entity, Group):
                injected = wrap_callback(cmd.send_group_help)
                return await injected(entity)
            elif isinstance(entity, Command):
                injected = wrap_callback(cmd.send_command_help)
                return await injected(entity)
            else:
                return None
        except CommandError as e:
            await cmd.on_help_command_error(self, e)

    @overload
    async def reply(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embed: Embed = ...,
        file: File = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        suppress_embeds: bool = ...,
        ephemeral: bool = ...,
        silent: bool = ...,
        poll: Poll = ...,
    ) -> Message:
        ...

    @overload
    async def reply(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embed: Embed = ...,
        files: Sequence[File] = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        suppress_embeds: bool = ...,
        ephemeral: bool = ...,
        silent: bool = ...,
        poll: Poll = ...,
    ) -> Message:
        ...

    @overload
    async def reply(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embeds: Sequence[Embed] = ...,
        file: File = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        suppress_embeds: bool = ...,
        ephemeral: bool = ...,
        silent: bool = ...,
        poll: Poll = ...,
    ) -> Message:
        ...

    @overload
    async def reply(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embeds: Sequence[Embed] = ...,
        files: Sequence[File] = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        suppress_embeds: bool = ...,
        ephemeral: bool = ...,
        silent: bool = ...,
        poll: Poll = ...,
    ) -> Message:
        ...

    async def reply(self, content: Optional[str] = None, **kwargs: Any) -> Message:
        """|coro|

        A shortcut method to :meth:`send` to reply to the
        :class:`~discord.Message` referenced by this context.

        For interaction based contexts, this is the same as :meth:`send`.

        .. versionadded:: 1.6

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` or
            :exc:`ValueError` instead of ``InvalidArgument``.

        Raises
        --------
        ~discord.HTTPException
            Sending the message failed.
        ~discord.Forbidden
            You do not have the proper permissions to send the message.
        ValueError
            The ``files`` list is not of the appropriate size
        TypeError
            You specified both ``file`` and ``files``.

        Returns
        ---------
        :class:`~discord.Message`
            The message that was sent.
        """
        if self.interaction is None:
            return await self.send(content, reference=self.message, **kwargs)
        else:
            return await self.send(content, **kwargs)

    def typing(self, *, ephemeral: bool = False) -> Union[Typing, DeferTyping]:
        """Returns an asynchronous context manager that allows you to send a typing indicator to
        the destination for an indefinite period of time, or 10 seconds if the context manager
        is called using ``await``.

        In an interaction based context, this is equivalent to a :meth:`defer` call and
        does not do any typing calls.

        Example Usage: ::

            async with channel.typing():
                # simulate something heavy
                await asyncio.sleep(20)

            await channel.send('Done!')

        Example Usage: ::

            await channel.typing()
            # Do some computational magic for about 10 seconds
            await channel.send('Done!')

        .. versionchanged:: 2.0
            This no longer works with the ``with`` syntax, ``async with`` must be used instead.

        .. versionchanged:: 2.0
            Added functionality to ``await`` the context manager to send a typing indicator for 10 seconds.

        Parameters
        -----------
        ephemeral: :class:`bool`
            Indicates whether the deferred message will eventually be ephemeral.
            Only valid for interaction based contexts.

            .. versionadded:: 2.0
        """
        if self.interaction is None:
            return Typing(self)
        return DeferTyping(self, ephemeral=ephemeral)

    async def defer(self, *, ephemeral: bool = False) -> None:
        """|coro|

        Defers the interaction based contexts.

        This is typically used when the interaction is acknowledged
        and a secondary action will be done later.

        If this isn't an interaction based context then it does nothing.

        Parameters
        -----------
        ephemeral: :class:`bool`
            Indicates whether the deferred message will eventually be ephemeral.

        Raises
        -------
        HTTPException
            Deferring the interaction failed.
        InteractionResponded
            This interaction has already been responded to before.
        """

        if self.interaction:
            await self.interaction.response.defer(ephemeral=ephemeral)

    @overload
    async def send(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embed: Embed = ...,
        file: File = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        suppress_embeds: bool = ...,
        ephemeral: bool = ...,
        silent: bool = ...,
        poll: Poll = ...,
    ) -> Message:
        ...

    @overload
    async def send(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embed: Embed = ...,
        files: Sequence[File] = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        suppress_embeds: bool = ...,
        ephemeral: bool = ...,
        silent: bool = ...,
        poll: Poll = ...,
    ) -> Message:
        ...

    @overload
    async def send(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embeds: Sequence[Embed] = ...,
        file: File = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        suppress_embeds: bool = ...,
        ephemeral: bool = ...,
        silent: bool = ...,
        poll: Poll = ...,
    ) -> Message:
        ...

    @overload
    async def send(
        self,
        content: Optional[str] = ...,
        *,
        tts: bool = ...,
        embeds: Sequence[Embed] = ...,
        files: Sequence[File] = ...,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = ...,
        delete_after: float = ...,
        nonce: Union[str, int] = ...,
        allowed_mentions: AllowedMentions = ...,
        reference: Union[Message, MessageReference, PartialMessage] = ...,
        mention_author: bool = ...,
        view: View = ...,
        suppress_embeds: bool = ...,
        ephemeral: bool = ...,
        silent: bool = ...,
        poll: Poll = ...,
    ) -> Message:
        ...

    async def send(
        self,
        content: Optional[str] = None,
        *,
        tts: bool = False,
        embed: Optional[Embed] = None,
        embeds: Optional[Sequence[Embed]] = None,
        file: Optional[File] = None,
        files: Optional[Sequence[File]] = None,
        stickers: Optional[Sequence[Union[GuildSticker, StickerItem]]] = None,
        delete_after: Optional[float] = None,
        nonce: Optional[Union[str, int]] = None,
        allowed_mentions: Optional[AllowedMentions] = None,
        reference: Optional[Union[Message, MessageReference, PartialMessage]] = None,
        mention_author: Optional[bool] = None,
        view: Optional[View] = None,
        suppress_embeds: bool = False,
        ephemeral: bool = False,
        silent: bool = False,
        poll: Poll = MISSING,
    ) -> Message:
        """|coro|

        Sends a message to the destination with the content given.

        This works similarly to :meth:`~discord.abc.Messageable.send` for non-interaction contexts.

        For interaction based contexts this does one of the following:

        - :meth:`discord.InteractionResponse.send_message` if no response has been given.
        - A followup message if a response has been given.
        - Regular send if the interaction has expired

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` or
            :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ------------
        content: Optional[:class:`str`]
            The content of the message to send.
        tts: :class:`bool`
            Indicates if the message should be sent using text-to-speech.
        embed: :class:`~discord.Embed`
            The rich embed for the content.
        file: :class:`~discord.File`
            The file to upload.
        files: List[:class:`~discord.File`]
            A list of files to upload. Must be a maximum of 10.
        nonce: :class:`int`
            The nonce to use for sending this message. If the message was successfully sent,
            then the message will have a nonce with this value.
        delete_after: :class:`float`
            If provided, the number of seconds to wait in the background
            before deleting the message we just sent. If the deletion fails,
            then it is silently ignored.
        allowed_mentions: :class:`~discord.AllowedMentions`
            Controls the mentions being processed in this message. If this is
            passed, then the object is merged with :attr:`~discord.Client.allowed_mentions`.
            The merging behaviour only overrides attributes that have been explicitly passed
            to the object, otherwise it uses the attributes set in :attr:`~discord.Client.allowed_mentions`.
            If no object is passed at all then the defaults given by :attr:`~discord.Client.allowed_mentions`
            are used instead.

            .. versionadded:: 1.4

        reference: Union[:class:`~discord.Message`, :class:`~discord.MessageReference`, :class:`~discord.PartialMessage`]
            A reference to the :class:`~discord.Message` to which you are replying, this can be created using
            :meth:`~discord.Message.to_reference` or passed directly as a :class:`~discord.Message`. You can control
            whether this mentions the author of the referenced message using the :attr:`~discord.AllowedMentions.replied_user`
            attribute of ``allowed_mentions`` or by setting ``mention_author``.

            This is ignored for interaction based contexts.

            .. versionadded:: 1.6

        mention_author: Optional[:class:`bool`]
            If set, overrides the :attr:`~discord.AllowedMentions.replied_user` attribute of ``allowed_mentions``.
            This is ignored for interaction based contexts.

            .. versionadded:: 1.6
        view: :class:`discord.ui.View`
            A Discord UI View to add to the message.

            .. versionadded:: 2.0
        embeds: List[:class:`~discord.Embed`]
            A list of embeds to upload. Must be a maximum of 10.

            .. versionadded:: 2.0
        stickers: Sequence[Union[:class:`~discord.GuildSticker`, :class:`~discord.StickerItem`]]
            A list of stickers to upload. Must be a maximum of 3. This is ignored for interaction based contexts.

            .. versionadded:: 2.0
        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This sends the message without any embeds if set to ``True``.

            .. versionadded:: 2.0
        ephemeral: :class:`bool`
            Indicates if the message should only be visible to the user who started the interaction.
            If a view is sent with an ephemeral message and it has no timeout set then the timeout
            is set to 15 minutes. **This is only applicable in contexts with an interaction**.

            .. versionadded:: 2.0
        silent: :class:`bool`
            Whether to suppress push and desktop notifications for the message. This will increment the mention counter
            in the UI, but will not actually send a notification.

            .. versionadded:: 2.2

        poll: :class:`~discord.Poll`
            The poll to send with this message.

            .. versionadded:: 2.4

        Raises
        --------
        ~discord.HTTPException
            Sending the message failed.
        ~discord.Forbidden
            You do not have the proper permissions to send the message.
        ValueError
            The ``files`` list is not of the appropriate size.
        TypeError
            You specified both ``file`` and ``files``,
            or you specified both ``embed`` and ``embeds``,
            or the ``reference`` object is not a :class:`~discord.Message`,
            :class:`~discord.MessageReference` or :class:`~discord.PartialMessage`.

        Returns
        ---------
        :class:`~discord.Message`
            The message that was sent.
        """

        if self.interaction is None or self.interaction.is_expired():
            return await super().send(
                content=content,
                tts=tts,
                embed=embed,
                embeds=embeds,
                file=file,
                files=files,
                stickers=stickers,
                delete_after=delete_after,
                nonce=nonce,
                allowed_mentions=allowed_mentions,
                reference=reference,
                mention_author=mention_author,
                view=view,
                suppress_embeds=suppress_embeds,
                silent=silent,
                poll=poll,
            )  # type: ignore # The overloads don't support Optional but the implementation does

        # Convert the kwargs from None to MISSING to appease the remaining implementations
        kwargs = {
            'content': content,
            'tts': tts,
            'embed': MISSING if embed is None else embed,
            'embeds': MISSING if embeds is None else embeds,
            'file': MISSING if file is None else file,
            'files': MISSING if files is None else files,
            'allowed_mentions': MISSING if allowed_mentions is None else allowed_mentions,
            'view': MISSING if view is None else view,
            'suppress_embeds': suppress_embeds,
            'ephemeral': ephemeral,
            'silent': silent,
            'poll': poll,
        }

        if self.interaction.response.is_done():
            msg = await self.interaction.followup.send(**kwargs, wait=True)
        else:
            await self.interaction.response.send_message(**kwargs)
            msg = await self.interaction.original_response()

        if delete_after is not None:
            await msg.delete(delay=delete_after)
        return msg
