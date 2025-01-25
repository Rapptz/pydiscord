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
import collections
import collections.abc
import inspect
import importlib.util
import sys
import logging
import types
from typing import (
    Any,
    Callable,
    Mapping,
    List,
    Dict,
    TYPE_CHECKING,
    Optional,
    Sequence,
    TypeVar,
    Type,
    Union,
    Iterable,
    Collection,
    overload,
)

import discord
from discord import app_commands
from discord.app_commands.tree import _retrieve_guild_ids
from discord.utils import MISSING, _is_submodule

from .core import GroupMixin
from .view import StringView
from .context import Context
from . import errors
from .help import HelpCommand, DefaultHelpCommand
from .cog import Cog
from .hybrid import hybrid_command, hybrid_group, HybridCommand, HybridGroup

if TYPE_CHECKING:
    from typing_extensions import Self

    import importlib.machinery

    from discord.message import Message
    from discord.interactions import Interaction
    from discord.abc import User, Snowflake
    from ._types import (
        _Bot,
        BotT,
        UserCheck,
        CoroFunc,
        ContextT,
        MaybeAwaitableFunc,
    )
    from .core import Command
    from .hybrid import CommandCallback, ContextT, P

    _Prefix = Union[Iterable[str], str]
    _PrefixCallable = MaybeAwaitableFunc[[BotT, Message], _Prefix]
    PrefixType = Union[_Prefix, _PrefixCallable[BotT]]

__all__ = (
    'when_mentioned',
    'when_mentioned_or',
    'Bot',
    'AutoShardedBot',
)

T = TypeVar('T')
CFT = TypeVar('CFT', bound='CoroFunc')

_log = logging.getLogger(__name__)


def when_mentioned(bot: _Bot, msg: Message, /) -> List[str]:
    """A callable that implements a command prefix equivalent to being mentioned.

    These are meant to be passed into the :attr:`.Bot.command_prefix` attribute.

        .. versionchanged:: 2.0

            ``bot`` and ``msg`` parameters are now positional-only.
    """
    # bot.user will never be None when this is called
    return [f'<@{bot.user.id}> ', f'<@!{bot.user.id}> ']  # type: ignore


def when_mentioned_or(*prefixes: str) -> Callable[[_Bot, Message], List[str]]:
    """A callable that implements when mentioned or other prefixes provided.

    These are meant to be passed into the :attr:`.Bot.command_prefix` attribute.

    Example
    --------

    .. code-block:: python3

        bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'))


    .. note::

        This callable returns another callable, so if this is done inside a custom
        callable, you must call the returned callable, for example:

        .. code-block:: python3

            async def get_prefix(bot, message):
                extras = await prefixes_for(message.guild) # returns a list
                return commands.when_mentioned_or(*extras)(bot, message)


    See Also
    ----------
    :func:`.when_mentioned`
    """

    def inner(bot, msg):
        r = list(prefixes)
        r = when_mentioned(bot, msg) + r
        return r

    return inner


class _DefaultRepr:
    def __repr__(self):
        return '<default-help-command>'


_default: Any = _DefaultRepr()


class BotBase(GroupMixin[None]):
    def __init__(
        self,
        command_prefix: PrefixType[BotT],
        *,
        help_command: Optional[HelpCommand] = _default,
        tree_cls: Type[app_commands.CommandTree[Any]] = app_commands.CommandTree,
        description: Optional[str] = None,
        allowed_contexts: app_commands.AppCommandContext = MISSING,
        allowed_installs: app_commands.AppInstallationType = MISSING,
        intents: discord.Intents,
        **options: Any,
    ) -> None:
        super().__init__(intents=intents, **options)
        self.command_prefix: PrefixType[BotT] = command_prefix
        self.extra_events: Dict[str, List[CoroFunc]] = {}
        # Self doesn't have the ClientT bound, but since this is a mixin it technically does
        self.__tree: app_commands.CommandTree[Self] = tree_cls(self)  # type: ignore
        if allowed_contexts is not MISSING:
            self.__tree.allowed_contexts = allowed_contexts
        if allowed_installs is not MISSING:
            self.__tree.allowed_installs = allowed_installs

        self.__cogs: Dict[str, Cog] = {}
        self.__extensions: Dict[str, types.ModuleType] = {}
        self._checks: List[UserCheck] = []
        self._check_once: List[UserCheck] = []
        self._before_invoke: Optional[CoroFunc] = None
        self._after_invoke: Optional[CoroFunc] = None
        self._help_command: Optional[HelpCommand] = None
        self.description: str = inspect.cleandoc(description) if description else ''
        self.owner_id: Optional[int] = options.get('owner_id')
        self.owner_ids: Optional[Collection[int]] = options.get('owner_ids', set())
        self.strip_after_prefix: bool = options.get('strip_after_prefix', False)

        if self.owner_id and self.owner_ids:
            raise TypeError('Both owner_id and owner_ids are set.')

        if self.owner_ids and not isinstance(self.owner_ids, collections.abc.Collection):
            raise TypeError(f'owner_ids must be a collection not {self.owner_ids.__class__.__name__}')

        if help_command is _default:
            self.help_command = DefaultHelpCommand()
        else:
            self.help_command = help_command

    # internal helpers

    async def _async_setup_hook(self) -> None:
        # self/super() resolves to Client/AutoShardedClient
        await super()._async_setup_hook()  # type: ignore
        prefix = self.command_prefix

        # This has to be here because for the default logging set up to capture
        # the logging calls, they have to come after the `Client.run` call.
        # The best place to do this is in an async init scenario
        if not self.intents.message_content:  # type: ignore
            trigger_warning = (
                (callable(prefix) and prefix is not when_mentioned)
                or isinstance(prefix, str)
                or (isinstance(prefix, collections.abc.Iterable) and len(list(prefix)) >= 1)
            )
            if trigger_warning:
                _log.warning('Privileged message content intent is missing, commands may not work as expected.')

    def dispatch(self, event_name: str, /, *args: Any, **kwargs: Any) -> None:
        # super() will resolve to Client
        super().dispatch(event_name, *args, **kwargs)  # type: ignore
        ev = 'on_' + event_name
        for event in self.extra_events.get(ev, []):
            self._schedule_event(event, ev, *args, **kwargs)  # type: ignore

    @discord.utils.copy_doc(discord.Client.close)
    async def close(self) -> None:
        for extension in tuple(self.__extensions):
            try:
                await self.unload_extension(extension)
            except Exception:
                pass

        for cog in tuple(self.__cogs):
            try:
                await self.remove_cog(cog)
            except Exception:
                pass

        await super().close()  # type: ignore

    # GroupMixin overrides

    def add_command(
        self,
        command: Command[Any, ..., Any],
        /,
        *,
        guild: Optional[Snowflake] = MISSING,
        guilds: Sequence[Snowflake] = MISSING,
    ) -> None:
        """Adds a :class:`.Command` into the internal list of commands.

        This is usually not called, instead the :meth:`~.GroupMixin.command` or
        :meth:`~.GroupMixin.group` shortcut decorators are used instead.

        .. versionchanged:: 1.4
             Raise :exc:`.CommandRegistrationError` instead of generic :exc:`.ClientException`

        .. versionchanged:: 2.0

            ``command`` parameter is now positional-only.

        Parameters
        -----------
        command: :class:`Command`
            The command to add.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            If the command is a hybrid command with an application command attached, then this
            will be the guild the app command will be added to.
            If not given, the app command will be global.

            .. versionadded:: 2.3
        guilds: List[:class:`~discord.abc.Snowflake`]
            If the command is a hybrid command with an application command attached, then these
            would be the guilds the app command will be added to.
            If not given, the app command will be global. Cannot be mixed with
            ``guild``.

            .. versionadded:: 2.3

        Raises
        -------
        CommandRegistrationError
            If the command or its alias is already registered by different command.
        TypeError
            If the command passed is not a subclass of :class:`.Command`. Or, guild and guilds were both given.
        """
        super().add_command(command)
        if isinstance(command, (HybridCommand, HybridGroup)) and command.app_command:
            # If a cog is also inheriting from app_commands.Group then it'll also
            # add the hybrid commands as text commands, which would recursively add the
            # hybrid commands as slash commands. This check just terminates that recursion
            # from happening
            if command.cog is None or not command.cog.__cog_is_app_commands_group__:
                self.tree.add_command(command.app_command, guild=guild, guilds=guilds)

    @discord.utils.copy_doc(GroupMixin.remove_command)
    def remove_command(self, name: str, /) -> Optional[Command[Any, ..., Any]]:
        cmd: Optional[Command[Any, ..., Any]] = super().remove_command(name)
        if isinstance(cmd, (HybridCommand, HybridGroup)) and cmd.app_command:
            # See above
            if cmd.cog is not None and cmd.cog.__cog_is_app_commands_group__:
                return cmd

            guild_ids: Optional[List[int]] = cmd.app_command._guild_ids
            if guild_ids is None:
                self.__tree.remove_command(name)
            else:
                for guild_id in guild_ids:
                    self.__tree.remove_command(name, guild=discord.Object(id=guild_id))

        return cmd

    def hybrid_command(
        self,
        name: Union[str, app_commands.locale_str] = MISSING,
        with_app_command: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> Callable[[CommandCallback[Any, ContextT, P, T]], HybridCommand[Any, P, T]]:
        """A shortcut decorator that invokes :func:`~discord.ext.commands.hybrid_command` and adds it to
        the internal command list via :meth:`add_command`.

        Returns
        --------
        Callable[..., :class:`HybridCommand`]
            A decorator that converts the provided method into a Command, adds it to the bot, then returns it.
        """

        def decorator(func: CommandCallback[Any, ContextT, P, T]):
            kwargs.setdefault('parent', self)
            result = hybrid_command(name=name, *args, with_app_command=with_app_command, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator

    def hybrid_group(
        self,
        name: Union[str, app_commands.locale_str] = MISSING,
        with_app_command: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> Callable[[CommandCallback[Any, ContextT, P, T]], HybridGroup[Any, P, T]]:
        """A shortcut decorator that invokes :func:`~discord.ext.commands.hybrid_group` and adds it to
        the internal command list via :meth:`add_command`.

        Returns
        --------
        Callable[..., :class:`HybridGroup`]
            A decorator that converts the provided method into a Group, adds it to the bot, then returns it.
        """

        def decorator(func: CommandCallback[Any, ContextT, P, T]):
            kwargs.setdefault('parent', self)
            result = hybrid_group(name=name, *args, with_app_command=with_app_command, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator

    # Error handler

    async def on_command_error(self, context: Context[BotT], exception: errors.CommandError, /) -> None:
        """|coro|

        The default command error handler provided by the bot.

        By default this logs to the library logger, however it could be
        overridden to have a different implementation.

        This only fires if you do not specify any listeners for command error.

        .. versionchanged:: 2.0

            ``context`` and ``exception`` parameters are now positional-only.
            Instead of writing to ``sys.stderr`` this now uses the library logger.
        """
        if self.extra_events.get('on_command_error', None):
            return

        command = context.command
        if command and command.has_error_handler():
            return

        cog = context.cog
        if cog and cog.has_error_handler():
            return

        _log.error('Ignoring exception in command %s', command, exc_info=exception)

    # global check registration

    def check(self, func: T, /) -> T:
        r"""A decorator that adds a global check to the bot.

        A global check is similar to a :func:`.check` that is applied
        on a per command basis except it is run before any command checks
        have been verified and applies to every command the bot has.

        .. note::

            This function can either be a regular function or a coroutine.

        Similar to a command :func:`.check`\, this takes a single parameter
        of type :class:`.Context` and can only raise exceptions inherited from
        :exc:`.CommandError`.

        Example
        ---------

        .. code-block:: python3

            @bot.check
            def check_commands(ctx):
                return ctx.command.qualified_name in allowed_commands

        .. versionchanged:: 2.0

            ``func`` parameter is now positional-only.
        """
        # T was used instead of Check to ensure the type matches on return
        self.add_check(func)  # type: ignore
        return func

    def add_check(self, func: UserCheck[ContextT], /, *, call_once: bool = False) -> None:
        """Adds a global check to the bot.

        This is the non-decorator interface to :meth:`.check`
        and :meth:`.check_once`.

        .. versionchanged:: 2.0

            ``func`` parameter is now positional-only.

        .. seealso:: The :func:`~discord.ext.commands.check` decorator

        Parameters
        -----------
        func
            The function that was used as a global check.
        call_once: :class:`bool`
            If the function should only be called once per
            :meth:`.invoke` call.
        """

        if call_once:
            self._check_once.append(func)
        else:
            self._checks.append(func)

    def remove_check(self, func: UserCheck[ContextT], /, *, call_once: bool = False) -> None:
        """Removes a global check from the bot.

        This function is idempotent and will not raise an exception
        if the function is not in the global checks.

        .. versionchanged:: 2.0

            ``func`` parameter is now positional-only.

        Parameters
        -----------
        func
            The function to remove from the global checks.
        call_once: :class:`bool`
            If the function was added with ``call_once=True`` in
            the :meth:`.Bot.add_check` call or using :meth:`.check_once`.
        """
        l = self._check_once if call_once else self._checks

        try:
            l.remove(func)
        except ValueError:
            pass

    def check_once(self, func: CFT, /) -> CFT:
        r"""A decorator that adds a "call once" global check to the bot.

        Unlike regular global checks, this one is called only once
        per :meth:`.invoke` call.

        Regular global checks are called whenever a command is called
        or :meth:`.Command.can_run` is called. This type of check
        bypasses that and ensures that it's called only once, even inside
        the default help command.

        .. note::

            When using this function the :class:`.Context` sent to a group subcommand
            may only parse the parent command and not the subcommands due to it
            being invoked once per :meth:`.Bot.invoke` call.

        .. note::

            This function can either be a regular function or a coroutine.

        Similar to a command :func:`.check`\, this takes a single parameter
        of type :class:`.Context` and can only raise exceptions inherited from
        :exc:`.CommandError`.

        Example
        ---------

        .. code-block:: python3

            @bot.check_once
            def whitelist(ctx):
                return ctx.message.author.id in my_whitelist

        .. versionchanged:: 2.0

            ``func`` parameter is now positional-only.

        """
        self.add_check(func, call_once=True)
        return func

    async def can_run(self, ctx: Context[BotT], /, *, call_once: bool = False) -> bool:
        data = self._check_once if call_once else self._checks

        if len(data) == 0:
            return True

        return await discord.utils.async_all(f(ctx) for f in data)

    async def is_owner(self, user: User, /) -> bool:
        """|coro|

        Checks if a :class:`~discord.User` or :class:`~discord.Member` is the owner of
        this bot.

        If an :attr:`owner_id` is not set, it is fetched automatically
        through the use of :meth:`~.Bot.application_info`.

        .. versionchanged:: 1.3
            The function also checks if the application is team-owned if
            :attr:`owner_ids` is not set.

        .. versionchanged:: 2.0

            ``user`` parameter is now positional-only.

        .. versionchanged:: 2.4

            This function now respects the team member roles if the bot is team-owned.
            In order to be considered an owner, they must be either an admin or
            a developer.

        Parameters
        -----------
        user: :class:`.abc.User`
            The user to check for.

        Returns
        --------
        :class:`bool`
            Whether the user is the owner.
        """

        if self.owner_id:
            return user.id == self.owner_id
        elif self.owner_ids:
            return user.id in self.owner_ids
        else:
            app: discord.AppInfo = await self.application_info()  # type: ignore
            if app.team:
                self.owner_ids = ids = {
                    m.id
                    for m in app.team.members
                    if m.role in (discord.TeamMemberRole.admin, discord.TeamMemberRole.developer)
                }
                return user.id in ids
            else:
                self.owner_id = owner_id = app.owner.id
                return user.id == owner_id

    def before_invoke(self, coro: CFT, /) -> CFT:
        """A decorator that registers a coroutine as a pre-invoke hook.

        A pre-invoke hook is called directly before the command is
        called. This makes it a useful function to set up database
        connections or any type of set up required.

        This pre-invoke hook takes a sole parameter, a :class:`.Context`.

        .. note::

            The :meth:`~.Bot.before_invoke` and :meth:`~.Bot.after_invoke` hooks are
            only called if all checks and argument parsing procedures pass
            without error. If any check or argument parsing procedures fail
            then the hooks are not called.

        .. versionchanged:: 2.0

            ``coro`` parameter is now positional-only.

        Parameters
        -----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the pre-invoke hook.

        Raises
        -------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('The pre-invoke hook must be a coroutine.')

        self._before_invoke = coro
        return coro

    def after_invoke(self, coro: CFT, /) -> CFT:
        r"""A decorator that registers a coroutine as a post-invoke hook.

        A post-invoke hook is called directly after the command is
        called. This makes it a useful function to clean-up database
        connections or any type of clean up required.

        This post-invoke hook takes a sole parameter, a :class:`.Context`.

        .. note::

            Similar to :meth:`~.Bot.before_invoke`\, this is not called unless
            checks and argument parsing procedures succeed. This hook is,
            however, **always** called regardless of the internal command
            callback raising an error (i.e. :exc:`.CommandInvokeError`\).
            This makes it ideal for clean-up scenarios.

        .. versionchanged:: 2.0

            ``coro`` parameter is now positional-only.

        Parameters
        -----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the post-invoke hook.

        Raises
        -------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('The post-invoke hook must be a coroutine.')

        self._after_invoke = coro
        return coro

    # listener registration

    def add_listener(self, func: CoroFunc, /, name: str = MISSING) -> None:
        """The non decorator alternative to :meth:`.listen`.

        .. versionchanged:: 2.0

            ``func`` parameter is now positional-only.

        Parameters
        -----------
        func: :ref:`coroutine <coroutine>`
            The function to call.
        name: :class:`str`
            The name of the event to listen for. Defaults to ``func.__name__``.

        Example
        --------

        .. code-block:: python3

            async def on_ready(): pass
            async def my_message(message): pass

            bot.add_listener(on_ready)
            bot.add_listener(my_message, 'on_message')

        """
        name = func.__name__ if name is MISSING else name

        if not asyncio.iscoroutinefunction(func):
            raise TypeError('Listeners must be coroutines')

        if name in self.extra_events:
            self.extra_events[name].append(func)
        else:
            self.extra_events[name] = [func]

    def remove_listener(self, func: CoroFunc, /, name: str = MISSING) -> None:
        """Removes a listener from the pool of listeners.

        .. versionchanged:: 2.0

            ``func`` parameter is now positional-only.

        Parameters
        -----------
        func
            The function that was used as a listener to remove.
        name: :class:`str`
            The name of the event we want to remove. Defaults to
            ``func.__name__``.
        """

        name = func.__name__ if name is MISSING else name

        if name in self.extra_events:
            try:
                self.extra_events[name].remove(func)
            except ValueError:
                pass

    def listen(self, name: str = MISSING) -> Callable[[CFT], CFT]:
        """A decorator that registers another function as an external
        event listener. Basically this allows you to listen to multiple
        events from different places e.g. such as :func:`.on_ready`

        The functions being listened to must be a :ref:`coroutine <coroutine>`.

        Example
        --------

        .. code-block:: python3

            @bot.listen()
            async def on_message(message):
                print('one')

            # in some other file...

            @bot.listen('on_message')
            async def my_message(message):
                print('two')

        Would print one and two in an unspecified order.

        Raises
        -------
        TypeError
            The function being listened to is not a coroutine.
        """

        def decorator(func: CFT) -> CFT:
            self.add_listener(func, name)
            return func

        return decorator

    # cogs

    async def add_cog(
        self,
        cog: Cog,
        /,
        *,
        override: bool = False,
        guild: Optional[Snowflake] = MISSING,
        guilds: Sequence[Snowflake] = MISSING,
    ) -> None:
        """|coro|

        Adds a "cog" to the bot.

        A cog is a class that has its own event listeners and commands.

        If the cog is a :class:`.app_commands.Group` then it is added to
        the bot's :class:`~discord.app_commands.CommandTree` as well.

        .. note::

            Exceptions raised inside a :class:`.Cog`'s :meth:`~.Cog.cog_load` method will be
            propagated to the caller.

        .. versionchanged:: 2.0

            :exc:`.ClientException` is raised when a cog with the same name
            is already loaded.

        .. versionchanged:: 2.0

            ``cog`` parameter is now positional-only.

        .. versionchanged:: 2.0

            This method is now a :term:`coroutine`.

        Parameters
        -----------
        cog: :class:`.Cog`
            The cog to register to the bot.
        override: :class:`bool`
            If a previously loaded cog with the same name should be ejected
            instead of raising an error.

            .. versionadded:: 2.0
        guild: Optional[:class:`~discord.abc.Snowflake`]
            If the cog has application commands, then this would
            the guild the app commands will be added to.
            If not given, all app commands will be global.

            .. versionchanged:: 2.3
                This kwarg is now also used by hybrid app commands.
            .. versionadded:: 2.0
        guilds: List[:class:`~discord.abc.Snowflake`]
            If the cog has application commands, then these
            would the guilds the app commands will be added to.
            If not given, all app commands will be global. Cannot be mixed with
            ``guild``.

            .. versionchanged:: 2.3
                This kwarg is now also used by hybrid app commands.
            .. versionadded:: 2.0

        Raises
        -------
        TypeError
            The cog does not inherit from :class:`.Cog`. Or, guild and guilds were both given.
        CommandError
            An error happened during loading.
        ClientException
            A cog with the same name is already loaded.
        """

        if not isinstance(cog, Cog):
            raise TypeError('cogs must derive from Cog')

        cog_name = cog.__cog_name__
        existing = self.__cogs.get(cog_name)

        if existing is not None:
            if not override:
                raise discord.ClientException(f'Cog named {cog_name!r} already loaded')
            await self.remove_cog(cog_name, guild=guild, guilds=guilds)

        if cog.__cog_app_commands_group__:
            self.__tree.add_command(cog.__cog_app_commands_group__, override=override, guild=guild, guilds=guilds)

        cog = await cog._inject(self, override=override, guild=guild, guilds=guilds)
        self.__cogs[cog_name] = cog

    def get_cog(self, name: str, /) -> Optional[Cog]:
        """Gets the cog instance requested.

        If the cog is not found, ``None`` is returned instead.

        .. versionchanged:: 2.0

            ``name`` parameter is now positional-only.

        Parameters
        -----------
        name: :class:`str`
            The name of the cog you are requesting.
            This is equivalent to the name passed via keyword
            argument in class creation or the class name if unspecified.

        Returns
        --------
        Optional[:class:`Cog`]
            The cog that was requested. If not found, returns ``None``.
        """
        return self.__cogs.get(name)

    async def remove_cog(
        self,
        name: str,
        /,
        *,
        guild: Optional[Snowflake] = MISSING,
        guilds: Sequence[Snowflake] = MISSING,
    ) -> Optional[Cog]:
        """|coro|

        Removes a cog from the bot and returns it.

        All registered commands and event listeners that the
        cog has registered will be removed as well.

        If no cog is found then this method has no effect.

        .. versionchanged:: 2.0

            ``name`` parameter is now positional-only.

        .. versionchanged:: 2.0

            This method is now a :term:`coroutine`.

        Parameters
        -----------
        name: :class:`str`
            The name of the cog to remove.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            If the cog is an application command group, then this would be the
            guild where the cog group would be removed from. If not given then
            a global command is removed instead instead.

            .. versionadded:: 2.0
        guilds: List[:class:`~discord.abc.Snowflake`]
            If the cog is an application command group, then this would be the
            guilds where the cog group would be removed from. If not given then
            a global command is removed instead instead. Cannot be mixed with
            ``guild``.

            .. versionadded:: 2.0

        Returns
        -------
        Optional[:class:`.Cog`]
             The cog that was removed. ``None`` if not found.
        """

        cog = self.__cogs.pop(name, None)
        if cog is None:
            return

        help_command = self._help_command
        if help_command and help_command.cog is cog:
            help_command.cog = None

        guild_ids = _retrieve_guild_ids(cog, guild, guilds)
        if cog.__cog_app_commands_group__:
            if guild_ids is None:
                self.__tree.remove_command(name)
            else:
                for guild_id in guild_ids:
                    self.__tree.remove_command(name, guild=discord.Object(guild_id))

        await cog._eject(self, guild_ids=guild_ids)

        return cog

    @property
    def cogs(self) -> Mapping[str, Cog]:
        """Mapping[:class:`str`, :class:`Cog`]: A read-only mapping of cog name to cog."""
        return types.MappingProxyType(self.__cogs)

    # extensions

    async def _remove_module_references(self, name: str) -> None:
        # find all references to the module
        # remove the cogs registered from the module
        for cogname, cog in self.__cogs.copy().items():
            if _is_submodule(name, cog.__module__):
                await self.remove_cog(cogname)

        # remove all the commands from the module
        for cmd in self.all_commands.copy().values():
            if cmd.module is not None and _is_submodule(name, cmd.module):
                if isinstance(cmd, GroupMixin):
                    cmd.recursively_remove_all_commands()
                self.remove_command(cmd.name)

        # remove all the listeners from the module
        for event_list in self.extra_events.copy().values():
            remove = []
            for index, event in enumerate(event_list):
                if event.__module__ is not None and _is_submodule(name, event.__module__):
                    remove.append(index)

            for index in reversed(remove):
                del event_list[index]

        # remove all relevant application commands from the tree
        self.__tree._remove_with_module(name)

    async def _call_module_finalizers(self, lib: types.ModuleType, key: str) -> None:
        try:
            func = getattr(lib, 'teardown')
        except AttributeError:
            pass
        else:
            try:
                await func(self)
            except Exception:
                pass
        finally:
            self.__extensions.pop(key, None)
            sys.modules.pop(key, None)
            name = lib.__name__
            for module in list(sys.modules.keys()):
                if _is_submodule(name, module):
                    del sys.modules[module]

    async def _load_from_module_spec(self, spec: importlib.machinery.ModuleSpec, key: str) -> None:
        # precondition: key not in self.__extensions
        lib = importlib.util.module_from_spec(spec)
        sys.modules[key] = lib
        try:
            spec.loader.exec_module(lib)  # type: ignore
        except Exception as e:
            del sys.modules[key]
            raise errors.ExtensionFailed(key, e) from e

        try:
            setup = getattr(lib, 'setup')
        except AttributeError:
            del sys.modules[key]
            raise errors.NoEntryPointError(key)

        try:
            await setup(self)
        except Exception as e:
            del sys.modules[key]
            await self._remove_module_references(lib.__name__)
            await self._call_module_finalizers(lib, key)
            raise errors.ExtensionFailed(key, e) from e
        else:
            self.__extensions[key] = lib

    def _resolve_name(self, name: str, package: Optional[str]) -> str:
        try:
            return importlib.util.resolve_name(name, package)
        except ImportError:
            raise errors.ExtensionNotFound(name)

    async def load_extension(self, name: str, *, package: Optional[str] = None) -> None:
        """|coro|

        Loads an extension.

        An extension is a python module that contains commands, cogs, or
        listeners.

        An extension must have a global function, ``setup`` defined as
        the entry point on what to do when the extension is loaded. This entry
        point must have a single argument, the ``bot``.

        .. versionchanged:: 2.0

            This method is now a :term:`coroutine`.

        Parameters
        ------------
        name: :class:`str`
            The extension name to load. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.
        package: Optional[:class:`str`]
            The package name to resolve relative imports with.
            This is required when loading an extension using a relative path, e.g ``.foo.test``.
            Defaults to ``None``.

            .. versionadded:: 1.7

        Raises
        --------
        ExtensionNotFound
            The extension could not be imported.
            This is also raised if the name of the extension could not
            be resolved using the provided ``package`` parameter.
        ExtensionAlreadyLoaded
            The extension is already loaded.
        NoEntryPointError
            The extension does not have a setup function.
        ExtensionFailed
            The extension or its setup function had an execution error.
        """

        name = self._resolve_name(name, package)
        if name in self.__extensions:
            raise errors.ExtensionAlreadyLoaded(name)

        spec = importlib.util.find_spec(name)
        if spec is None:
            raise errors.ExtensionNotFound(name)

        await self._load_from_module_spec(spec, name)

    async def unload_extension(self, name: str, *, package: Optional[str] = None) -> None:
        """|coro|

        Unloads an extension.

        When the extension is unloaded, all commands, listeners, and cogs are
        removed from the bot and the module is un-imported.

        The extension can provide an optional global function, ``teardown``,
        to do miscellaneous clean-up if necessary. This function takes a single
        parameter, the ``bot``, similar to ``setup`` from
        :meth:`~.Bot.load_extension`.

        .. versionchanged:: 2.0

            This method is now a :term:`coroutine`.

        Parameters
        ------------
        name: :class:`str`
            The extension name to unload. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.
        package: Optional[:class:`str`]
            The package name to resolve relative imports with.
            This is required when unloading an extension using a relative path, e.g ``.foo.test``.
            Defaults to ``None``.

            .. versionadded:: 1.7

        Raises
        -------
        ExtensionNotFound
            The name of the extension could not
            be resolved using the provided ``package`` parameter.
        ExtensionNotLoaded
            The extension was not loaded.
        """

        name = self._resolve_name(name, package)
        lib = self.__extensions.get(name)
        if lib is None:
            raise errors.ExtensionNotLoaded(name)

        await self._remove_module_references(lib.__name__)
        await self._call_module_finalizers(lib, name)

    async def reload_extension(self, name: str, *, package: Optional[str] = None) -> None:
        """|coro|

        Atomically reloads an extension.

        This replaces the extension with the same extension, only refreshed. This is
        equivalent to a :meth:`unload_extension` followed by a :meth:`load_extension`
        except done in an atomic way. That is, if an operation fails mid-reload then
        the bot will roll-back to the prior working state.

        Parameters
        ------------
        name: :class:`str`
            The extension name to reload. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.
        package: Optional[:class:`str`]
            The package name to resolve relative imports with.
            This is required when reloading an extension using a relative path, e.g ``.foo.test``.
            Defaults to ``None``.

            .. versionadded:: 1.7

        Raises
        -------
        ExtensionNotLoaded
            The extension was not loaded.
        ExtensionNotFound
            The extension could not be imported.
            This is also raised if the name of the extension could not
            be resolved using the provided ``package`` parameter.
        NoEntryPointError
            The extension does not have a setup function.
        ExtensionFailed
            The extension setup function had an execution error.
        """

        name = self._resolve_name(name, package)
        lib = self.__extensions.get(name)
        if lib is None:
            raise errors.ExtensionNotLoaded(name)

        # get the previous module states from sys modules
        # fmt: off
        modules = {
            name: module
            for name, module in sys.modules.items()
            if _is_submodule(lib.__name__, name)
        }
        # fmt: on

        try:
            # Unload and then load the module...
            await self._remove_module_references(lib.__name__)
            await self._call_module_finalizers(lib, name)
            await self.load_extension(name)
        except Exception:
            # if the load failed, the remnants should have been
            # cleaned from the load_extension function call
            # so let's load it from our old compiled library.
            await lib.setup(self)
            self.__extensions[name] = lib

            # revert sys.modules back to normal and raise back to caller
            sys.modules.update(modules)
            raise

    @property
    def extensions(self) -> Mapping[str, types.ModuleType]:
        """Mapping[:class:`str`, :class:`py:types.ModuleType`]: A read-only mapping of extension name to extension."""
        return types.MappingProxyType(self.__extensions)

    # help command stuff

    @property
    def help_command(self) -> Optional[HelpCommand]:
        return self._help_command

    @help_command.setter
    def help_command(self, value: Optional[HelpCommand]) -> None:
        if value is not None:
            if not isinstance(value, HelpCommand):
                raise TypeError('help_command must be a subclass of HelpCommand')
            if self._help_command is not None:
                self._help_command._remove_from_bot(self)
            self._help_command = value
            value._add_to_bot(self)
        elif self._help_command is not None:
            self._help_command._remove_from_bot(self)
            self._help_command = None
        else:
            self._help_command = None

    # application command interop

    # As mentioned above, this is a mixin so the Self type hint fails here.
    # However, since the only classes that can use this are subclasses of Client
    # anyway, then this is sound.
    @property
    def tree(self) -> app_commands.CommandTree[Self]:  # type: ignore
        """:class:`~discord.app_commands.CommandTree`: The command tree responsible for handling the application commands
        in this bot.

        .. versionadded:: 2.0
        """
        return self.__tree

    # command processing

    async def get_prefix(self, message: Message, /) -> Union[List[str], str]:
        """|coro|

        Retrieves the prefix the bot is listening to
        with the message as a context.

        .. versionchanged:: 2.0

            ``message`` parameter is now positional-only.

        Parameters
        -----------
        message: :class:`discord.Message`
            The message context to get the prefix of.

        Returns
        --------
        Union[List[:class:`str`], :class:`str`]
            A list of prefixes or a single prefix that the bot is
            listening for.
        """
        prefix = ret = self.command_prefix

        if callable(prefix):
            # self will be a Bot or AutoShardedBot
            ret = await discord.utils.maybe_coroutine(prefix, self, message)  # type: ignore

        if not isinstance(ret, str):
            try:
                ret = list(ret)  # type: ignore
            except TypeError:
                # It's possible that a generator raised this exception.  Don't
                # replace it with our own error if that's the case.
                if isinstance(ret, collections.abc.Iterable):
                    raise

                raise TypeError(
                    "command_prefix must be plain string, iterable of strings, or callable "
                    f"returning either of these, not {ret.__class__.__name__}"
                )

        return ret

    @overload
    async def get_context(
        self,
        origin: Union[Message, Interaction],
        /,
    ) -> Context[Self]:  # type: ignore
        ...

    @overload
    async def get_context(
        self,
        origin: Union[Message, Interaction],
        /,
        *,
        cls: Type[ContextT],
    ) -> ContextT:
        ...

    async def get_context(
        self,
        origin: Union[Message, Interaction],
        /,
        *,
        cls: Type[ContextT] = MISSING,
    ) -> Any:
        r"""|coro|

        Returns the invocation context from the message or interaction.

        This is a more low-level counter-part for :meth:`.process_commands`
        to allow users more fine grained control over the processing.

        The returned context is not guaranteed to be a valid invocation
        context, :attr:`.Context.valid` must be checked to make sure it is.
        If the context is not valid then it is not a valid candidate to be
        invoked under :meth:`~.Bot.invoke`.

        .. note::

            In order for the custom context to be used inside an interaction-based
            context (such as :class:`HybridCommand`) then this method must be
            overridden to return that class.

        .. versionchanged:: 2.0

            ``message`` parameter is now positional-only and renamed to ``origin``.

        Parameters
        -----------
        origin: Union[:class:`discord.Message`, :class:`discord.Interaction`]
            The message or interaction to get the invocation context from.
        cls
            The factory class that will be used to create the context.
            By default, this is :class:`.Context`. Should a custom
            class be provided, it must be similar enough to :class:`.Context`\'s
            interface.

        Returns
        --------
        :class:`.Context`
            The invocation context. The type of this can change via the
            ``cls`` parameter.
        """
        if cls is MISSING:
            cls = Context  # type: ignore

        if isinstance(origin, discord.Interaction):
            return await cls.from_interaction(origin)

        view = StringView(origin.content)
        ctx = cls(prefix=None, view=view, bot=self, message=origin)

        if origin.author.id == self.user.id:  # type: ignore
            return ctx

        prefix = await self.get_prefix(origin)
        invoked_prefix = prefix

        if isinstance(prefix, str):
            if not view.skip_string(prefix):
                return ctx
        else:
            try:
                # if the context class' __init__ consumes something from the view this
                # will be wrong.  That seems unreasonable though.
                if origin.content.startswith(tuple(prefix)):
                    invoked_prefix = discord.utils.find(view.skip_string, prefix)
                else:
                    return ctx

            except TypeError:
                if not isinstance(prefix, list):
                    raise TypeError(
                        "get_prefix must return either a string or a list of string, " f"not {prefix.__class__.__name__}"
                    )

                # It's possible a bad command_prefix got us here.
                for value in prefix:
                    if not isinstance(value, str):
                        raise TypeError(
                            "Iterable command_prefix or list returned from get_prefix must "
                            f"contain only strings, not {value.__class__.__name__}"
                        )

                # Getting here shouldn't happen
                raise

        if self.strip_after_prefix:
            view.skip_ws()

        invoker = view.get_word()
        ctx.invoked_with = invoker
        # type-checker fails to narrow invoked_prefix type.
        ctx.prefix = invoked_prefix  # type: ignore
        ctx.command = self.all_commands.get(invoker)
        return ctx

    async def invoke(self, ctx: Context[BotT], /) -> None:
        """|coro|

        Invokes the command given under the invocation context and
        handles all the internal event dispatch mechanisms.

        .. versionchanged:: 2.0

            ``ctx`` parameter is now positional-only.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context to invoke.
        """
        if ctx.command is not None:
            self.dispatch('command', ctx)
            try:
                if await self.can_run(ctx, call_once=True):
                    await ctx.command.invoke(ctx)
                else:
                    raise errors.CheckFailure('The global check once functions failed.')
            except errors.CommandError as exc:
                await ctx.command.dispatch_error(ctx, exc)
            else:
                self.dispatch('command_completion', ctx)
        elif ctx.invoked_with:
            exc = errors.CommandNotFound(f'Command "{ctx.invoked_with}" is not found')
            self.dispatch('command_error', ctx, exc)

    async def process_commands(self, message: Message, /) -> None:
        """|coro|

        This function processes the commands that have been registered
        to the bot and other groups. Without this coroutine, none of the
        commands will be triggered.

        By default, this coroutine is called inside the :func:`.on_message`
        event. If you choose to override the :func:`.on_message` event, then
        you should invoke this coroutine as well.

        This is built using other low level tools, and is equivalent to a
        call to :meth:`~.Bot.get_context` followed by a call to :meth:`~.Bot.invoke`.

        This also checks if the message's author is a bot and doesn't
        call :meth:`~.Bot.get_context` or :meth:`~.Bot.invoke` if so.

        .. versionchanged:: 2.0

            ``message`` parameter is now positional-only.

        Parameters
        -----------
        message: :class:`discord.Message`
            The message to process commands for.
        """
        if message.author.bot:
            return

        ctx = await self.get_context(message)
        # the type of the invocation context's bot attribute will be correct
        await self.invoke(ctx)  # type: ignore

    async def on_message(self, message: Message, /) -> None:
        await self.process_commands(message)


class Bot(BotBase, discord.Client):
    """Represents a Discord bot.

    This class is a subclass of :class:`discord.Client` and as a result
    anything that you can do with a :class:`discord.Client` you can do with
    this bot.

    This class also subclasses :class:`.GroupMixin` to provide the functionality
    to manage commands.

    Unlike :class:`discord.Client`, this class does not require manually setting
    a :class:`~discord.app_commands.CommandTree` and is automatically set upon
    instantiating the class.

    .. container:: operations

        .. describe:: async with x

            Asynchronously initialises the bot and automatically cleans up.

            .. versionadded:: 2.0

    Attributes
    -----------
    command_prefix
        The command prefix is what the message content must contain initially
        to have a command invoked. This prefix could either be a string to
        indicate what the prefix should be, or a callable that takes in the bot
        as its first parameter and :class:`discord.Message` as its second
        parameter and returns the prefix. This is to facilitate "dynamic"
        command prefixes. This callable can be either a regular function or
        a coroutine.

        An empty string as the prefix always matches, enabling prefix-less
        command invocation. While this may be useful in DMs it should be avoided
        in servers, as it's likely to cause performance issues and unintended
        command invocations.

        The command prefix could also be an iterable of strings indicating that
        multiple checks for the prefix should be used and the first one to
        match will be the invocation prefix. You can get this prefix via
        :attr:`.Context.prefix`.

        .. note::

            When passing multiple prefixes be careful to not pass a prefix
            that matches a longer prefix occurring later in the sequence.  For
            example, if the command prefix is ``('!', '!?')``  the ``'!?'``
            prefix will never be matched to any message as the previous one
            matches messages starting with ``!?``. This is especially important
            when passing an empty string, it should always be last as no prefix
            after it will be matched.
    case_insensitive: :class:`bool`
        Whether the commands should be case insensitive. Defaults to ``False``. This
        attribute does not carry over to groups. You must set it to every group if
        you require group commands to be case insensitive as well.
    description: :class:`str`
        The content prefixed into the default help message.
    help_command: Optional[:class:`.HelpCommand`]
        The help command implementation to use. This can be dynamically
        set at runtime. To remove the help command pass ``None``. For more
        information on implementing a help command, see :ref:`ext_commands_help_command`.
    owner_id: Optional[:class:`int`]
        The user ID that owns the bot. If this is not set and is then queried via
        :meth:`.is_owner` then it is fetched automatically using
        :meth:`~.Bot.application_info`.
    owner_ids: Optional[Collection[:class:`int`]]
        The user IDs that owns the bot. This is similar to :attr:`owner_id`.
        If this is not set and the application is team based, then it is
        fetched automatically using :meth:`~.Bot.application_info`.
        For performance reasons it is recommended to use a :class:`set`
        for the collection. You cannot set both ``owner_id`` and ``owner_ids``.

        .. versionadded:: 1.3
    strip_after_prefix: :class:`bool`
        Whether to strip whitespace characters after encountering the command
        prefix. This allows for ``!   hello`` and ``!hello`` to both work if
        the ``command_prefix`` is set to ``!``. Defaults to ``False``.

        .. versionadded:: 1.7
    tree_cls: Type[:class:`~discord.app_commands.CommandTree`]
        The type of application command tree to use. Defaults to :class:`~discord.app_commands.CommandTree`.

        .. versionadded:: 2.0
    allowed_contexts: :class:`~discord.app_commands.AppCommandContext`
        The default allowed contexts that applies to all application commands
        in the application command tree.

        Note that you can override this on a per command basis.

        .. versionadded:: 2.4
    allowed_installs: :class:`~discord.app_commands.AppInstallationType`
        The default allowed install locations that apply to all application commands
        in the application command tree.

        Note that you can override this on a per command basis.

        .. versionadded:: 2.4
    """

    pass


class AutoShardedBot(BotBase, discord.AutoShardedClient):
    """This is similar to :class:`.Bot` except that it is inherited from
    :class:`discord.AutoShardedClient` instead.

    .. container:: operations

        .. describe:: async with x

            Asynchronously initialises the bot and automatically cleans.

            .. versionadded:: 2.0
    """

    pass
