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

import itertools
import copy
import functools
import re

from typing import (
    TYPE_CHECKING,
    Optional,
    Generator,
    List,
    TypeVar,
    Callable,
    Any,
    Dict,
    Tuple,
    Iterable,
    Sequence,
    Mapping,
)

import discord.utils

from .core import Group, Command, get_signature_parameters
from .errors import CommandError

if TYPE_CHECKING:
    from typing_extensions import Self

    import discord.abc

    from .bot import BotBase
    from .context import Context
    from .cog import Cog
    from .parameters import Parameter

    from ._types import (
        UserCheck,
        BotT,
        _Bot,
    )

__all__ = (
    'Paginator',
    'HelpCommand',
    'DefaultHelpCommand',
    'MinimalHelpCommand',
)

FuncT = TypeVar('FuncT', bound=Callable[..., Any])

MISSING: Any = discord.utils.MISSING

# help -> shows info of bot on top/bottom and lists subcommands
# help command -> shows detailed info of command
# help command <subcommand chain> -> same as above

# <description>

# <command signature with aliases>

# <long doc>

# Cog:
#   <command> <shortdoc>
#   <command> <shortdoc>
# Other Cog:
#   <command> <shortdoc>
# No Category:
#   <command> <shortdoc>

# Type <prefix>help command for more info on a command.
# You can also type <prefix>help category for more info on a category.


class Paginator:
    """A class that aids in paginating code blocks for Discord messages.

    .. container:: operations

        .. describe:: len(x)

            Returns the total number of characters in the paginator.

    Attributes
    -----------
    prefix: Optional[:class:`str`]
        The prefix inserted to every page. e.g. three backticks, if any.
    suffix: Optional[:class:`str`]
        The suffix appended at the end of every page. e.g. three backticks, if any.
    max_size: :class:`int`
        The maximum amount of codepoints allowed in a page.
    linesep: :class:`str`
        The character string inserted between lines. e.g. a newline character.
            .. versionadded:: 1.7
    """

    def __init__(
        self, prefix: Optional[str] = '```', suffix: Optional[str] = '```', max_size: int = 2000, linesep: str = '\n'
    ) -> None:
        self.prefix: Optional[str] = prefix
        self.suffix: Optional[str] = suffix
        self.max_size: int = max_size
        self.linesep: str = linesep
        self.clear()

    def clear(self) -> None:
        """Clears the paginator to have no pages."""
        if self.prefix is not None:
            self._current_page: List[str] = [self.prefix]
            self._count: int = len(self.prefix) + self._linesep_len  # prefix + newline
        else:
            self._current_page = []
            self._count = 0
        self._pages: List[str] = []

    @property
    def _prefix_len(self) -> int:
        return len(self.prefix) if self.prefix else 0

    @property
    def _suffix_len(self) -> int:
        return len(self.suffix) if self.suffix else 0

    @property
    def _linesep_len(self) -> int:
        return len(self.linesep)

    def add_line(self, line: str = '', *, empty: bool = False) -> None:
        """Adds a line to the current page.

        If the line exceeds the :attr:`max_size` then an exception
        is raised.

        Parameters
        -----------
        line: :class:`str`
            The line to add.
        empty: :class:`bool`
            Indicates if another empty line should be added.

        Raises
        ------
        RuntimeError
            The line was too big for the current :attr:`max_size`.
        """
        max_page_size = self.max_size - self._prefix_len - self._suffix_len - 2 * self._linesep_len
        if len(line) > max_page_size:
            raise RuntimeError(f'Line exceeds maximum page size {max_page_size}')

        if self._count + len(line) + self._linesep_len > self.max_size - self._suffix_len:
            self.close_page()

        self._count += len(line) + self._linesep_len
        self._current_page.append(line)

        if empty:
            self._current_page.append('')
            self._count += self._linesep_len

    def close_page(self) -> None:
        """Prematurely terminate a page."""
        if self.suffix is not None:
            self._current_page.append(self.suffix)
        self._pages.append(self.linesep.join(self._current_page))

        if self.prefix is not None:
            self._current_page = [self.prefix]
            self._count = len(self.prefix) + self._linesep_len  # prefix + linesep
        else:
            self._current_page = []
            self._count = 0

    def __len__(self) -> int:
        total = sum(len(p) for p in self._pages)
        return total + self._count

    @property
    def pages(self) -> List[str]:
        """List[:class:`str`]: Returns the rendered list of pages."""
        # we have more than just the prefix in our current page
        if len(self._current_page) > (0 if self.prefix is None else 1):
            # Render and include current page without closing
            current_page = self.linesep.join(
                [*self._current_page, self.suffix] if self.suffix is not None else self._current_page
            )
            return [*self._pages, current_page]

        return self._pages

    def __repr__(self) -> str:
        fmt = '<Paginator prefix: {0.prefix!r} suffix: {0.suffix!r} linesep: {0.linesep!r} max_size: {0.max_size} count: {0._count}>'
        return fmt.format(self)


def _not_overridden(f: FuncT) -> FuncT:
    f.__help_command_not_overridden__ = True
    return f


class _HelpCommandImpl(Command):
    def __init__(self, inject: HelpCommand, *args: Any, **kwargs: Any) -> None:
        super().__init__(inject.command_callback, *args, **kwargs)
        self._original: HelpCommand = inject
        self._injected: HelpCommand = inject
        self.params: Dict[str, Parameter] = get_signature_parameters(inject.command_callback, globals(), skip_parameters=1)

    async def prepare(self, ctx: Context[Any]) -> None:
        self._injected = injected = self._original.copy()
        injected.context = ctx
        self.callback = injected.command_callback
        self.params = get_signature_parameters(injected.command_callback, globals(), skip_parameters=1)

        on_error = injected.on_help_command_error
        if not hasattr(on_error, '__help_command_not_overridden__'):
            if self.cog is not None:
                self.on_error = self._on_error_cog_implementation
            else:
                self.on_error = on_error

        await super().prepare(ctx)

    async def _parse_arguments(self, ctx: Context[BotT]) -> None:
        # Make the parser think we don't have a cog so it doesn't
        # inject the parameter into `ctx.args`.
        original_cog = self.cog
        self.cog = None
        try:
            await super()._parse_arguments(ctx)
        finally:
            self.cog = original_cog

    async def _on_error_cog_implementation(self, _, ctx: Context[BotT], error: CommandError) -> None:
        await self._injected.on_help_command_error(ctx, error)

    def _inject_into_cog(self, cog: Cog) -> None:
        # Warning: hacky

        # Make the cog think that get_commands returns this command
        # as well if we inject it without modifying __cog_commands__
        # since that's used for the injection and ejection of cogs.
        def wrapped_get_commands(
            *, _original: Callable[[], List[Command[Any, ..., Any]]] = cog.get_commands
        ) -> List[Command[Any, ..., Any]]:
            ret = _original()
            ret.append(self)
            return ret

        # Ditto here
        def wrapped_walk_commands(
            *, _original: Callable[[], Generator[Command[Any, ..., Any], None, None]] = cog.walk_commands
        ):
            yield from _original()
            yield self

        functools.update_wrapper(wrapped_get_commands, cog.get_commands)
        functools.update_wrapper(wrapped_walk_commands, cog.walk_commands)
        cog.get_commands = wrapped_get_commands
        cog.walk_commands = wrapped_walk_commands
        self.cog = cog

    def _eject_cog(self) -> None:
        if self.cog is None:
            return

        # revert back into their original methods
        cog = self.cog
        cog.get_commands = cog.get_commands.__wrapped__
        cog.walk_commands = cog.walk_commands.__wrapped__
        self.cog = None

        # Revert `on_error` to use the original one in case of race conditions
        self.on_error = self._injected.on_help_command_error

    def update(self, **kwargs: Any) -> None:
        cog = self.cog
        self.__init__(self._original, **dict(self.__original_kwargs__, **kwargs))
        self.cog = cog


class HelpCommand:
    r"""The base implementation for help command formatting.

    .. note::

        Internally instances of this class are deep copied every time
        the command itself is invoked to prevent a race condition
        mentioned in :issue:`2123`.

        This means that relying on the state of this class to be
        the same between command invocations would not work as expected.

    Attributes
    ------------
    context: Optional[:class:`Context`]
        The context that invoked this help formatter. This is generally set after
        the help command assigned, :func:`command_callback`\, has been called.
    show_hidden: :class:`bool`
        Specifies if hidden commands should be shown in the output.
        Defaults to ``False``.
    verify_checks: Optional[:class:`bool`]
        Specifies if commands should have their :attr:`.Command.checks` called
        and verified. If ``True``, always calls :attr:`.Command.checks`.
        If ``None``, only calls :attr:`.Command.checks` in a guild setting.
        If ``False``, never calls :attr:`.Command.checks`. Defaults to ``True``.

        .. versionchanged:: 1.7
    command_attrs: :class:`dict`
        A dictionary of options to pass in for the construction of the help command.
        This allows you to change the command behaviour without actually changing
        the implementation of the command. The attributes will be the same as the
        ones passed in the :class:`.Command` constructor.
    """

    MENTION_TRANSFORMS = {
        '@everyone': '@\u200beveryone',
        '@here': '@\u200bhere',
        r'<@!?[0-9]{17,22}>': '@deleted-user',
        r'<@&[0-9]{17,22}>': '@deleted-role',
    }

    MENTION_PATTERN = re.compile('|'.join(MENTION_TRANSFORMS.keys()))

    if TYPE_CHECKING:
        __original_kwargs__: Dict[str, Any]
        __original_args__: Tuple[Any, ...]

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        # To prevent race conditions of a single instance while also allowing
        # for settings to be passed the original arguments passed must be assigned
        # to allow for easier copies (which will be made when the help command is actually called)
        # see issue 2123
        self = super().__new__(cls)

        # Shallow copies cannot be used in this case since it is not unusual to pass
        # instances that need state, e.g. Paginator or what have you into the function
        # The keys can be safely copied as-is since they're 99.99% certain of being
        # string keys
        deepcopy = copy.deepcopy
        self.__original_kwargs__ = {k: deepcopy(v) for k, v in kwargs.items()}
        self.__original_args__ = deepcopy(args)
        return self

    def __init__(self, **options: Any) -> None:
        self.show_hidden: bool = options.pop('show_hidden', False)
        self.verify_checks: bool = options.pop('verify_checks', True)
        self.command_attrs: Dict[str, Any]
        self.command_attrs = attrs = options.pop('command_attrs', {})
        attrs.setdefault('name', 'help')
        attrs.setdefault('help', 'Shows this message')
        self.context: Context[_Bot] = MISSING
        self._command_impl = _HelpCommandImpl(self, **self.command_attrs)

    def copy(self) -> Self:
        obj = self.__class__(*self.__original_args__, **self.__original_kwargs__)
        obj._command_impl = self._command_impl
        return obj

    def _add_to_bot(self, bot: BotBase) -> None:
        self._command_impl.update(**self.command_attrs)
        bot.add_command(self._command_impl)

    def _remove_from_bot(self, bot: BotBase) -> None:
        bot.remove_command(self._command_impl.name)
        self._command_impl._eject_cog()

    def add_check(self, func: UserCheck[Context[Any]], /) -> None:
        """
        Adds a check to the help command.

        .. versionadded:: 1.4

        .. versionchanged:: 2.0

            ``func`` parameter is now positional-only.

        .. seealso:: The :func:`~discord.ext.commands.check` decorator

        Parameters
        ----------
        func
            The function that will be used as a check.
        """

        self._command_impl.add_check(func)

    def remove_check(self, func: UserCheck[Context[Any]], /) -> None:
        """
        Removes a check from the help command.

        This function is idempotent and will not raise an exception if
        the function is not in the command's checks.

        .. versionadded:: 1.4

        .. versionchanged:: 2.0

            ``func`` parameter is now positional-only.

        Parameters
        ----------
        func
            The function to remove from the checks.
        """

        self._command_impl.remove_check(func)

    def get_bot_mapping(self) -> Dict[Optional[Cog], List[Command[Any, ..., Any]]]:
        """Retrieves the bot mapping passed to :meth:`send_bot_help`."""
        bot = self.context.bot
        mapping: Dict[Optional[Cog], List[Command[Any, ..., Any]]] = {cog: cog.get_commands() for cog in bot.cogs.values()}
        mapping[None] = [c for c in bot.commands if c.cog is None]
        return mapping

    @property
    def invoked_with(self) -> Optional[str]:
        """Similar to :attr:`Context.invoked_with` except properly handles
        the case where :meth:`Context.send_help` is used.

        If the help command was used regularly then this returns
        the :attr:`Context.invoked_with` attribute. Otherwise, if
        it the help command was called using :meth:`Context.send_help`
        then it returns the internal command name of the help command.

        Returns
        ---------
        Optional[:class:`str`]
            The command name that triggered this invocation.
        """
        command_name = self._command_impl.name
        ctx = self.context
        if ctx is MISSING or ctx.command is None or ctx.command.qualified_name != command_name:
            return command_name
        return ctx.invoked_with

    def get_command_signature(self, command: Command[Any, ..., Any], /) -> str:
        """Retrieves the signature portion of the help page.

        .. versionchanged:: 2.0

            ``command`` parameter is now positional-only.

        Parameters
        ------------
        command: :class:`Command`
            The command to get the signature of.

        Returns
        --------
        :class:`str`
            The signature for the command.
        """
        parent: Optional[Group[Any, ..., Any]] = command.parent  # type: ignore # the parent will be a Group
        entries = []
        while parent is not None:
            if not parent.signature or parent.invoke_without_command:
                entries.append(parent.name)
            else:
                entries.append(parent.name + ' ' + parent.signature)
            parent = parent.parent  # type: ignore
        parent_sig = ' '.join(reversed(entries))

        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = f'[{command.name}|{aliases}]'
            if parent_sig:
                fmt = parent_sig + ' ' + fmt
            alias = fmt
        else:
            alias = command.name if not parent_sig else parent_sig + ' ' + command.name

        return f'{self.context.clean_prefix}{alias} {command.signature}'

    def remove_mentions(self, string: str, /) -> str:
        """Removes mentions from the string to prevent abuse.

        This includes ``@everyone``, ``@here``, member mentions and role mentions.

        .. versionchanged:: 2.0

            ``string`` parameter is now positional-only.

        Returns
        -------
        :class:`str`
            The string with mentions removed.
        """

        def replace(obj: re.Match, *, transforms: Dict[str, str] = self.MENTION_TRANSFORMS) -> str:
            return transforms.get(obj.group(0), '@invalid')

        return self.MENTION_PATTERN.sub(replace, string)

    @property
    def cog(self) -> Optional[Cog]:
        """A property for retrieving or setting the cog for the help command.

        When a cog is set for the help command, it is as-if the help command
        belongs to that cog. All cog special methods will apply to the help
        command and it will be automatically unset on unload.

        To unbind the cog from the help command, you can set it to ``None``.

        Returns
        --------
        Optional[:class:`Cog`]
            The cog that is currently set for the help command.
        """
        return self._command_impl.cog

    @cog.setter
    def cog(self, cog: Optional[Cog]) -> None:
        # Remove whatever cog is currently valid, if any
        self._command_impl._eject_cog()

        # If a new cog is set then inject it.
        if cog is not None:
            self._command_impl._inject_into_cog(cog)

    def command_not_found(self, string: str, /) -> str:
        """|maybecoro|

        A method called when a command is not found in the help command.
        This is useful to override for i18n.

        Defaults to ``No command called {0} found.``

        .. versionchanged:: 2.0

            ``string`` parameter is now positional-only.

        Parameters
        ------------
        string: :class:`str`
            The string that contains the invalid command. Note that this has
            had mentions removed to prevent abuse.

        Returns
        ---------
        :class:`str`
            The string to use when a command has not been found.
        """
        return f'No command called "{string}" found.'

    def subcommand_not_found(self, command: Command[Any, ..., Any], string: str, /) -> str:
        """|maybecoro|

        A method called when a command did not have a subcommand requested in the help command.
        This is useful to override for i18n.

        Defaults to either:

        - ``'Command "{command.qualified_name}" has no subcommands.'``
            - If there is no subcommand in the ``command`` parameter.
        - ``'Command "{command.qualified_name}" has no subcommand named {string}'``
            - If the ``command`` parameter has subcommands but not one named ``string``.

        .. versionchanged:: 2.0

            ``command`` and ``string`` parameters are now positional-only.

        Parameters
        ------------
        command: :class:`Command`
            The command that did not have the subcommand requested.
        string: :class:`str`
            The string that contains the invalid subcommand. Note that this has
            had mentions removed to prevent abuse.

        Returns
        ---------
        :class:`str`
            The string to use when the command did not have the subcommand requested.
        """
        if isinstance(command, Group) and len(command.all_commands) > 0:
            return f'Command "{command.qualified_name}" has no subcommand named {string}'
        return f'Command "{command.qualified_name}" has no subcommands.'

    async def filter_commands(
        self,
        commands: Iterable[Command[Any, ..., Any]],
        /,
        *,
        sort: bool = False,
        key: Optional[Callable[[Command[Any, ..., Any]], Any]] = None,
    ) -> List[Command[Any, ..., Any]]:
        """|coro|

        Returns a filtered list of commands and optionally sorts them.

        This takes into account the :attr:`verify_checks` and :attr:`show_hidden`
        attributes.

        .. versionchanged:: 2.0

            ``commands`` parameter is now positional-only.

        Parameters
        ------------
        commands: Iterable[:class:`Command`]
            An iterable of commands that are getting filtered.
        sort: :class:`bool`
            Whether to sort the result.
        key: Optional[Callable[[:class:`Command`], Any]]
            An optional key function to pass to :func:`py:sorted` that
            takes a :class:`Command` as its sole parameter. If ``sort`` is
            passed as ``True`` then this will default as the command name.

        Returns
        ---------
        List[:class:`Command`]
            A list of commands that passed the filter.
        """

        if sort and key is None:
            key = lambda c: c.name

        iterator = commands if self.show_hidden else filter(lambda c: not c.hidden, commands)

        if self.verify_checks is False:
            # if we do not need to verify the checks then we can just
            # run it straight through normally without using await.
            return sorted(iterator, key=key) if sort else list(iterator)  # type: ignore # the key shouldn't be None

        if self.verify_checks is None and not self.context.guild:
            # if verify_checks is None and we're in a DM, don't verify
            return sorted(iterator, key=key) if sort else list(iterator)  # type: ignore

        # if we're here then we need to check every command if it can run
        async def predicate(cmd: Command[Any, ..., Any]) -> bool:
            try:
                return await cmd.can_run(self.context)
            except CommandError:
                return False

        ret = []
        for cmd in iterator:
            valid = await predicate(cmd)
            if valid:
                ret.append(cmd)

        if sort:
            ret.sort(key=key)
        return ret

    def get_max_size(self, commands: Sequence[Command[Any, ..., Any]], /) -> int:
        """Returns the largest name length of the specified command list.

        .. versionchanged:: 2.0

            ``commands`` parameter is now positional-only.

        Parameters
        ------------
        commands: Sequence[:class:`Command`]
            A sequence of commands to check for the largest size.

        Returns
        --------
        :class:`int`
            The maximum width of the commands.
        """

        as_lengths = (discord.utils._string_width(c.name) for c in commands)
        return max(as_lengths, default=0)

    def get_destination(self) -> discord.abc.MessageableChannel:
        """Returns the :class:`~discord.abc.Messageable` where the help command will be output.

        You can override this method to customise the behaviour.

        By default this returns the context's channel.

        Returns
        -------
        :class:`.abc.Messageable`
            The destination where the help command will be output.
        """
        return self.context.channel

    async def send_error_message(self, error: str, /) -> None:
        """|coro|

        Handles the implementation when an error happens in the help command.
        For example, the result of :meth:`command_not_found` will be passed here.

        You can override this method to customise the behaviour.

        By default, this sends the error message to the destination
        specified by :meth:`get_destination`.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

        .. versionchanged:: 2.0

            ``error`` parameter is now positional-only.

        Parameters
        ------------
        error: :class:`str`
            The error message to display to the user. Note that this has
            had mentions removed to prevent abuse.
        """
        destination = self.get_destination()
        await destination.send(error)

    @_not_overridden
    async def on_help_command_error(self, ctx: Context[BotT], error: CommandError, /) -> None:
        """|coro|

        The help command's error handler, as specified by :ref:`ext_commands_error_handler`.

        Useful to override if you need some specific behaviour when the error handler
        is called.

        By default this method does nothing and just propagates to the default
        error handlers.

        .. versionchanged:: 2.0

            ``ctx`` and ``error`` parameters are now positional-only.

        Parameters
        ------------
        ctx: :class:`Context`
            The invocation context.
        error: :class:`CommandError`
            The error that was raised.
        """
        pass

    async def send_bot_help(self, mapping: Mapping[Optional[Cog], List[Command[Any, ..., Any]]], /) -> None:
        """|coro|

        Handles the implementation of the bot command page in the help command.
        This function is called when the help command is called with no arguments.

        It should be noted that this method does not return anything -- rather the
        actual message sending should be done inside this method. Well behaved subclasses
        should use :meth:`get_destination` to know where to send, as this is a customisation
        point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

            Also, the commands in the mapping are not filtered. To do the filtering
            you will have to call :meth:`filter_commands` yourself.

        .. versionchanged:: 2.0

            ``mapping`` parameter is now positional-only.

        Parameters
        ------------
        mapping: Mapping[Optional[:class:`Cog`], List[:class:`Command`]]
            A mapping of cogs to commands that have been requested by the user for help.
            The key of the mapping is the :class:`~.commands.Cog` that the command belongs to, or
            ``None`` if there isn't one, and the value is a list of commands that belongs to that cog.
        """
        return None

    async def send_cog_help(self, cog: Cog, /) -> None:
        """|coro|

        Handles the implementation of the cog page in the help command.
        This function is called when the help command is called with a cog as the argument.

        It should be noted that this method does not return anything -- rather the
        actual message sending should be done inside this method. Well behaved subclasses
        should use :meth:`get_destination` to know where to send, as this is a customisation
        point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

            To get the commands that belong to this cog see :meth:`Cog.get_commands`.
            The commands returned not filtered. To do the filtering you will have to call
            :meth:`filter_commands` yourself.

        .. versionchanged:: 2.0

            ``cog`` parameter is now positional-only.

        Parameters
        -----------
        cog: :class:`Cog`
            The cog that was requested for help.
        """
        return None

    async def send_group_help(self, group: Group[Any, ..., Any], /) -> None:
        """|coro|

        Handles the implementation of the group page in the help command.
        This function is called when the help command is called with a group as the argument.

        It should be noted that this method does not return anything -- rather the
        actual message sending should be done inside this method. Well behaved subclasses
        should use :meth:`get_destination` to know where to send, as this is a customisation
        point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

            To get the commands that belong to this group without aliases see
            :attr:`Group.commands`. The commands returned not filtered. To do the
            filtering you will have to call :meth:`filter_commands` yourself.

        .. versionchanged:: 2.0

            ``group`` parameter is now positional-only.

        Parameters
        -----------
        group: :class:`Group`
            The group that was requested for help.
        """
        return None

    async def send_command_help(self, command: Command[Any, ..., Any], /) -> None:
        """|coro|

        Handles the implementation of the single command page in the help command.

        It should be noted that this method does not return anything -- rather the
        actual message sending should be done inside this method. Well behaved subclasses
        should use :meth:`get_destination` to know where to send, as this is a customisation
        point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with :attr:`HelpCommand.context`.

        .. admonition:: Showing Help
            :class: helpful

            There are certain attributes and methods that are helpful for a help command
            to show such as the following:

            - :attr:`Command.help`
            - :attr:`Command.brief`
            - :attr:`Command.short_doc`
            - :attr:`Command.description`
            - :meth:`get_command_signature`

            There are more than just these attributes but feel free to play around with
            these to help you get started to get the output that you want.

        .. versionchanged:: 2.0

            ``command`` parameter is now positional-only.

        Parameters
        -----------
        command: :class:`Command`
            The command that was requested for help.
        """
        return None

    async def prepare_help_command(self, ctx: Context[BotT], command: Optional[str] = None, /) -> None:
        """|coro|

        A low level method that can be used to prepare the help command
        before it does anything. For example, if you need to prepare
        some state in your subclass before the command does its processing
        then this would be the place to do it.

        The default implementation does nothing.

        .. note::

            This is called *inside* the help command callback body. So all
            the usual rules that happen inside apply here as well.

        .. versionchanged:: 2.0

            ``ctx`` and ``command`` parameters are now positional-only.

        Parameters
        -----------
        ctx: :class:`Context`
            The invocation context.
        command: Optional[:class:`str`]
            The argument passed to the help command.
        """
        pass

    async def command_callback(self, ctx: Context[BotT], /, *, command: Optional[str] = None) -> None:
        """|coro|

        The actual implementation of the help command.

        It is not recommended to override this method and instead change
        the behaviour through the methods that actually get dispatched.

        - :meth:`send_bot_help`
        - :meth:`send_cog_help`
        - :meth:`send_group_help`
        - :meth:`send_command_help`
        - :meth:`get_destination`
        - :meth:`command_not_found`
        - :meth:`subcommand_not_found`
        - :meth:`send_error_message`
        - :meth:`on_help_command_error`
        - :meth:`prepare_help_command`

        .. versionchanged:: 2.0

            ``ctx`` parameter is now positional-only.
        """
        await self.prepare_help_command(ctx, command)

        bot = ctx.bot

        if command is None:
            mapping = self.get_bot_mapping()
            return await self.send_bot_help(mapping)

        # Check if it's a cog
        cog = bot.get_cog(command)
        if cog is not None:
            return await self.send_cog_help(cog)

        maybe_coro = discord.utils.maybe_coroutine

        # If it's not a cog then it's a command.
        # Since we want to have detailed errors when someone
        # passes an invalid subcommand, we need to walk through
        # the command group chain ourselves.
        keys = command.split(' ')
        cmd = bot.all_commands.get(keys[0])
        if cmd is None:
            string = await maybe_coro(self.command_not_found, self.remove_mentions(keys[0]))
            return await self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)  # type: ignore
            except AttributeError:
                string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                return await self.send_error_message(string)
            else:
                if found is None:
                    string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                    return await self.send_error_message(string)
                cmd = found

        if isinstance(cmd, Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)


class DefaultHelpCommand(HelpCommand):
    """The implementation of the default help command.

    This inherits from :class:`HelpCommand`.

    It extends it with the following attributes.

    Attributes
    ------------
    width: :class:`int`
        The maximum number of characters that fit in a line.
        Defaults to 80.
    sort_commands: :class:`bool`
        Whether to sort the commands in the output alphabetically. Defaults to ``True``.
    dm_help: Optional[:class:`bool`]
        A tribool that indicates if the help command should DM the user instead of
        sending it to the channel it received it from. If the boolean is set to
        ``True``, then all help output is DM'd. If ``False``, none of the help
        output is DM'd. If ``None``, then the bot will only DM when the help
        message becomes too long (dictated by more than :attr:`dm_help_threshold` characters).
        Defaults to ``False``.
    dm_help_threshold: Optional[:class:`int`]
        The number of characters the paginator must accumulate before getting DM'd to the
        user if :attr:`dm_help` is set to ``None``. Defaults to 1000.
    indent: :class:`int`
        How much to indent the commands from a heading. Defaults to ``2``.
    arguments_heading: :class:`str`
        The arguments list's heading string used when the help command is invoked with a command name.
        Useful for i18n. Defaults to ``"Arguments:"``.
        Shown when :attr:`.show_parameter_descriptions` is ``True``.

        .. versionadded:: 2.0
    show_parameter_descriptions: :class:`bool`
        Whether to show the parameter descriptions. Defaults to ``True``.
        Setting this to ``False`` will revert to showing the :attr:`~.commands.Command.signature` instead.

        .. versionadded:: 2.0
    commands_heading: :class:`str`
        The command list's heading string used when the help command is invoked with a category name.
        Useful for i18n. Defaults to ``"Commands:"``
    default_argument_description: :class:`str`
        The default argument description string used when the argument's :attr:`~.commands.Parameter.description` is ``None``.
        Useful for i18n. Defaults to ``"No description given."``

        .. versionadded:: 2.0
    no_category: :class:`str`
        The string used when there is a command which does not belong to any category(cog).
        Useful for i18n. Defaults to ``"No Category"``
    paginator: :class:`Paginator`
        The paginator used to paginate the help command output.
    """

    def __init__(self, **options: Any) -> None:
        self.width: int = options.pop('width', 80)
        self.indent: int = options.pop('indent', 2)
        self.sort_commands: bool = options.pop('sort_commands', True)
        self.dm_help: bool = options.pop('dm_help', False)
        self.dm_help_threshold: int = options.pop('dm_help_threshold', 1000)
        self.arguments_heading: str = options.pop('arguments_heading', "Arguments:")
        self.commands_heading: str = options.pop('commands_heading', 'Commands:')
        self.default_argument_description: str = options.pop('default_argument_description', 'No description given')
        self.no_category: str = options.pop('no_category', 'No Category')
        self.paginator: Paginator = options.pop('paginator', None)
        self.show_parameter_descriptions: bool = options.pop('show_parameter_descriptions', True)

        if self.paginator is None:
            self.paginator: Paginator = Paginator()

        super().__init__(**options)

    def shorten_text(self, text: str, /) -> str:
        """:class:`str`: Shortens text to fit into the :attr:`width`.

        .. versionchanged:: 2.0

            ``text`` parameter is now positional-only.
        """
        if len(text) > self.width:
            return text[: self.width - 3].rstrip() + '...'
        return text

    def get_ending_note(self) -> str:
        """:class:`str`: Returns help command's ending note. This is mainly useful to override for i18n purposes."""
        command_name = self.invoked_with
        return (
            f'Type {self.context.clean_prefix}{command_name} command for more info on a command.\n'
            f'You can also type {self.context.clean_prefix}{command_name} category for more info on a category.'
        )

    def get_command_signature(self, command: Command[Any, ..., Any], /) -> str:
        """Retrieves the signature portion of the help page.

        Calls :meth:`~.HelpCommand.get_command_signature` if :attr:`show_parameter_descriptions` is ``False``
        else returns a modified signature where the command parameters are not shown.

        .. versionadded:: 2.0

        Parameters
        ------------
        command: :class:`Command`
            The command to get the signature of.

        Returns
        --------
        :class:`str`
            The signature for the command.
        """
        if not self.show_parameter_descriptions:
            return super().get_command_signature(command)

        name = command.name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            name = f'[{command.name}|{aliases}]'

        return f'{self.context.clean_prefix}{name}'

    def add_indented_commands(
        self, commands: Sequence[Command[Any, ..., Any]], /, *, heading: str, max_size: Optional[int] = None
    ) -> None:
        """Indents a list of commands after the specified heading.

        The formatting is added to the :attr:`paginator`.

        The default implementation is the command name indented by
        :attr:`indent` spaces, padded to ``max_size`` followed by
        the command's :attr:`Command.short_doc` and then shortened
        to fit into the :attr:`width`.

        .. versionchanged:: 2.0
            ``commands`` parameter is now positional-only.

        Parameters
        -----------
        commands: Sequence[:class:`Command`]
            A list of commands to indent for output.
        heading: :class:`str`
            The heading to add to the output. This is only added
            if the list of commands is greater than 0.
        max_size: Optional[:class:`int`]
            The max size to use for the gap between indents.
            If unspecified, calls :meth:`~HelpCommand.get_max_size` on the
            commands parameter.
        """

        if not commands:
            return

        self.paginator.add_line(heading)
        max_size = max_size or self.get_max_size(commands)

        get_width = discord.utils._string_width
        for command in commands:
            name = command.name
            width = max_size - (get_width(name) - len(name))
            entry = f'{self.indent * " "}{name:<{width}} {command.short_doc}'
            self.paginator.add_line(self.shorten_text(entry))

    def add_command_arguments(self, command: Command[Any, ..., Any], /) -> None:
        """Indents a list of command arguments after the :attr:`.arguments_heading`.

        The default implementation is the argument :attr:`~.commands.Parameter.name` indented by
        :attr:`indent` spaces, padded to ``max_size`` using :meth:`~HelpCommand.get_max_size`
        followed by the argument's :attr:`~.commands.Parameter.description` or
        :attr:`.default_argument_description` and then shortened
        to fit into the :attr:`width` and then :attr:`~.commands.Parameter.displayed_default`
        between () if one is present after that.

        .. versionadded:: 2.0

        Parameters
        -----------
        command: :class:`Command`
            The command to list the arguments for.
        """
        arguments = command.clean_params.values()
        if not arguments:
            return

        self.paginator.add_line(self.arguments_heading)
        max_size = self.get_max_size(arguments)  # type: ignore # not a command

        get_width = discord.utils._string_width
        for argument in arguments:
            name = argument.displayed_name or argument.name
            width = max_size - (get_width(name) - len(name))
            entry = f'{self.indent * " "}{name:<{width}} {argument.description or self.default_argument_description}'
            # we do not want to shorten the default value, if any.
            entry = self.shorten_text(entry)
            if argument.displayed_default is not None:
                entry += f' (default: {argument.displayed_default})'

            self.paginator.add_line(entry)

    async def send_pages(self) -> None:
        """|coro|

        A helper utility to send the page output from :attr:`paginator` to the destination.
        """
        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(page)

    def add_command_formatting(self, command: Command[Any, ..., Any], /) -> None:
        """A utility function to format the non-indented block of commands and groups.

        .. versionchanged:: 2.0

            ``command`` parameter is now positional-only.

        .. versionchanged:: 2.0
            :meth:`.add_command_arguments` is now called if :attr:`.show_parameter_descriptions` is ``True``.

        Parameters
        ------------
        command: :class:`Command`
            The command to format.
        """

        if command.description:
            self.paginator.add_line(command.description, empty=True)

        signature = self.get_command_signature(command)
        self.paginator.add_line(signature, empty=True)

        if command.help:
            try:
                self.paginator.add_line(command.help, empty=True)
            except RuntimeError:
                for line in command.help.splitlines():
                    self.paginator.add_line(line)
                self.paginator.add_line()

        if self.show_parameter_descriptions:
            self.add_command_arguments(command)

    def get_destination(self) -> discord.abc.Messageable:
        ctx = self.context
        if self.dm_help is True:
            return ctx.author
        elif self.dm_help is None and len(self.paginator) > self.dm_help_threshold:
            return ctx.author
        else:
            return ctx.channel

    async def prepare_help_command(self, ctx: Context[BotT], command: Optional[str], /) -> None:
        self.paginator.clear()
        await super().prepare_help_command(ctx, command)

    async def send_bot_help(self, mapping: Mapping[Optional[Cog], List[Command[Any, ..., Any]]], /) -> None:
        ctx = self.context
        bot = ctx.bot

        if bot.description:
            # <description> portion
            self.paginator.add_line(bot.description, empty=True)

        no_category = f'\u200b{self.no_category}:'

        def get_cog_name(cog, *, no_category=no_category):
            return cog.qualified_name + ':' if cog is not None else no_category
        
        cogs = sorted(mapping.keys(), key=get_cog_name)
        max_size = max([self.get_max_size(mapping[cog]) for cog in mapping], default=0)

        for cog in cogs:
            commands = await self.filter_commands(mapping[cog])
            if self.sort_commands:
                commands = sorted(commands, key=lambda c: c.name)
            self.add_indented_commands(commands, heading=get_cog_name(cog), max_size=max_size)

        note = self.get_ending_note()
        if note:
            self.paginator.add_line()
            self.paginator.add_line(note)

        await self.send_pages()

    async def send_command_help(self, command: Command[Any, ..., Any], /) -> None:
        self.add_command_formatting(command)
        self.paginator.close_page()
        await self.send_pages()

    async def send_group_help(self, group: Group[Any, ..., Any], /) -> None:
        self.add_command_formatting(group)

        filtered = await self.filter_commands(group.commands, sort=self.sort_commands)
        self.add_indented_commands(filtered, heading=self.commands_heading)

        if filtered:
            note = self.get_ending_note()
            if note:
                self.paginator.add_line()
                self.paginator.add_line(note)

        await self.send_pages()

    async def send_cog_help(self, cog: Cog, /) -> None:
        if cog.description:
            self.paginator.add_line(cog.description, empty=True)

        filtered = await self.filter_commands(cog.get_commands(), sort=self.sort_commands)
        self.add_indented_commands(filtered, heading=self.commands_heading)

        note = self.get_ending_note()
        if note:
            self.paginator.add_line()
            self.paginator.add_line(note)

        await self.send_pages()


class MinimalHelpCommand(HelpCommand):
    """An implementation of a help command with minimal output.

    This inherits from :class:`HelpCommand`.

    Attributes
    ------------
    sort_commands: :class:`bool`
        Whether to sort the commands in the output alphabetically. Defaults to ``True``.
    commands_heading: :class:`str`
        The command list's heading string used when the help command is invoked with a category name.
        Useful for i18n. Defaults to ``"Commands"``
    aliases_heading: :class:`str`
        The alias list's heading string used to list the aliases of the command. Useful for i18n.
        Defaults to ``"Aliases:"``.
    dm_help: Optional[:class:`bool`]
        A tribool that indicates if the help command should DM the user instead of
        sending it to the channel it received it from. If the boolean is set to
        ``True``, then all help output is DM'd. If ``False``, none of the help
        output is DM'd. If ``None``, then the bot will only DM when the help
        message becomes too long (dictated by more than :attr:`dm_help_threshold` characters).
        Defaults to ``False``.
    dm_help_threshold: Optional[:class:`int`]
        The number of characters the paginator must accumulate before getting DM'd to the
        user if :attr:`dm_help` is set to ``None``. Defaults to 1000.
    no_category: :class:`str`
        The string used when there is a command which does not belong to any category(cog).
        Useful for i18n. Defaults to ``"No Category"``
    paginator: :class:`Paginator`
        The paginator used to paginate the help command output.
    """

    def __init__(self, **options: Any) -> None:
        self.sort_commands: bool = options.pop('sort_commands', True)
        self.commands_heading: str = options.pop('commands_heading', 'Commands')
        self.dm_help: bool = options.pop('dm_help', False)
        self.dm_help_threshold: int = options.pop('dm_help_threshold', 1000)
        self.aliases_heading: str = options.pop('aliases_heading', 'Aliases:')
        self.no_category: str = options.pop('no_category', 'No Category')
        self.paginator: Paginator = options.pop('paginator', None)

        if self.paginator is None:
            self.paginator: Paginator = Paginator(suffix=None, prefix=None)

        super().__init__(**options)

    async def send_pages(self) -> None:
        """|coro|

        A helper utility to send the page output from :attr:`paginator` to the destination.
        """
        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(page)

    def get_opening_note(self) -> str:
        """Returns help command's opening note. This is mainly useful to override for i18n purposes.

        The default implementation returns ::

            Use `{prefix}{command_name} [command]` for more info on a command.
            You can also use `{prefix}{command_name} [category]` for more info on a category.

        Returns
        -------
        :class:`str`
            The help command opening note.
        """
        command_name = self.invoked_with
        return (
            f'Use `{self.context.clean_prefix}{command_name} [command]` for more info on a command.\n'
            f'You can also use `{self.context.clean_prefix}{command_name} [category]` for more info on a category.'
        )

    def get_command_signature(self, command: Command[Any, ..., Any], /) -> str:
        return f'{self.context.clean_prefix}{command.qualified_name} {command.signature}'

    def get_ending_note(self) -> str:
        """Return the help command's ending note. This is mainly useful to override for i18n purposes.

        The default implementation does nothing.

        Returns
        -------
        :class:`str`
            The help command ending note.
        """
        return ''

    def add_bot_commands_formatting(self, commands: Sequence[Command[Any, ..., Any]], heading: str, /) -> None:
        """Adds the minified bot heading with commands to the output.

        The formatting should be added to the :attr:`paginator`.

        The default implementation is a bold underline heading followed
        by commands separated by an EN SPACE (U+2002) in the next line.

        .. versionchanged:: 2.0

            ``commands`` and ``heading`` parameters are now positional-only.

        Parameters
        -----------
        commands: Sequence[:class:`Command`]
            A list of commands that belong to the heading.
        heading: :class:`str`
            The heading to add to the line.
        """
        if commands:
            # U+2002 Middle Dot
            joined = '\u2002'.join(c.name for c in commands)
            self.paginator.add_line(f'__**{heading}**__')
            self.paginator.add_line(joined)

    def add_subcommand_formatting(self, command: Command[Any, ..., Any], /) -> None:
        """Adds formatting information on a subcommand.

        The formatting should be added to the :attr:`paginator`.

        The default implementation is the prefix and the :attr:`Command.qualified_name`
        optionally followed by an En dash and the command's :attr:`Command.short_doc`.

        .. versionchanged:: 2.0

            ``command`` parameter is now positional-only.

        Parameters
        -----------
        command: :class:`Command`
            The command to show information of.
        """
        fmt = '{0}{1} \N{EN DASH} {2}' if command.short_doc else '{0}{1}'
        self.paginator.add_line(fmt.format(self.context.clean_prefix, command.qualified_name, command.short_doc))

    def add_aliases_formatting(self, aliases: Sequence[str], /) -> None:
        """Adds the formatting information on a command's aliases.

        The formatting should be added to the :attr:`paginator`.

        The default implementation is the :attr:`aliases_heading` bolded
        followed by a comma separated list of aliases.

        This is not called if there are no aliases to format.

        .. versionchanged:: 2.0

            ``aliases`` parameter is now positional-only.

        Parameters
        -----------
        aliases: Sequence[:class:`str`]
            A list of aliases to format.
        """
        self.paginator.add_line(f'**{self.aliases_heading}** {", ".join(aliases)}', empty=True)

    def add_command_formatting(self, command: Command[Any, ..., Any], /) -> None:
        """A utility function to format commands and groups.

        .. versionchanged:: 2.0

            ``command`` parameter is now positional-only.

        Parameters
        ------------
        command: :class:`Command`
            The command to format.
        """

        if command.description:
            self.paginator.add_line(command.description, empty=True)

        signature = self.get_command_signature(command)
        if command.aliases:
            self.paginator.add_line(signature)
            self.add_aliases_formatting(command.aliases)
        else:
            self.paginator.add_line(signature, empty=True)

        if command.help:
            try:
                self.paginator.add_line(command.help, empty=True)
            except RuntimeError:
                for line in command.help.splitlines():
                    self.paginator.add_line(line)
                self.paginator.add_line()

    def get_destination(self) -> discord.abc.Messageable:
        ctx = self.context
        if self.dm_help is True:
            return ctx.author
        elif self.dm_help is None and len(self.paginator) > self.dm_help_threshold:
            return ctx.author
        else:
            return ctx.channel

    async def prepare_help_command(self, ctx: Context[BotT], command: Optional[str], /) -> None:
        self.paginator.clear()
        await super().prepare_help_command(ctx, command)

    async def send_bot_help(self, mapping: Mapping[Optional[Cog], List[Command[Any, ..., Any]]], /) -> None:
        ctx = self.context
        bot = ctx.bot

        if bot.description:
            self.paginator.add_line(bot.description, empty=True)

        note = self.get_opening_note()
        if note:
            self.paginator.add_line(note, empty=True)

        no_category = f'\u200b{self.no_category}'

        def get_category(command: Command[Any, ..., Any], *, no_category: str = no_category) -> str:
            cog = command.cog
            return cog.qualified_name if cog is not None else no_category

        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        to_iterate = itertools.groupby(filtered, key=get_category)

        for category, commands in to_iterate:
            commands = sorted(commands, key=lambda c: c.name) if self.sort_commands else list(commands)
            self.add_bot_commands_formatting(commands, category)

        note = self.get_ending_note()
        if note:
            self.paginator.add_line()
            self.paginator.add_line(note)

        await self.send_pages()

    async def send_cog_help(self, cog: Cog, /) -> None:
        bot = self.context.bot
        if bot.description:
            self.paginator.add_line(bot.description, empty=True)

        note = self.get_opening_note()
        if note:
            self.paginator.add_line(note, empty=True)

        if cog.description:
            self.paginator.add_line(cog.description, empty=True)

        filtered = await self.filter_commands(cog.get_commands(), sort=self.sort_commands)
        if filtered:
            self.paginator.add_line(f'**{cog.qualified_name} {self.commands_heading}**')
            for command in filtered:
                self.add_subcommand_formatting(command)

            note = self.get_ending_note()
            if note:
                self.paginator.add_line()
                self.paginator.add_line(note)

        await self.send_pages()

    async def send_group_help(self, group: Group[Any, ..., Any], /) -> None:
        self.add_command_formatting(group)

        filtered = await self.filter_commands(group.commands, sort=self.sort_commands)
        if filtered:
            note = self.get_opening_note()
            if note:
                self.paginator.add_line(note, empty=True)

            self.paginator.add_line(f'**{self.commands_heading}**')
            for command in filtered:
                self.add_subcommand_formatting(command)

            note = self.get_ending_note()
            if note:
                self.paginator.add_line()
                self.paginator.add_line(note)

        await self.send_pages()

    async def send_command_help(self, command: Command[Any, ..., Any], /) -> None:
        self.add_command_formatting(command)
        self.paginator.close_page()
        await self.send_pages()
