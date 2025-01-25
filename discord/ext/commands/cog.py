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
import discord
import logging
from discord import app_commands
from discord.utils import maybe_coroutine, _to_kebab_case

from typing import (
    Any,
    Callable,
    ClassVar,
    Coroutine,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    TYPE_CHECKING,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

from ._types import _BaseCommand, BotT

if TYPE_CHECKING:
    from typing_extensions import Self
    from discord.abc import Snowflake
    from discord._types import ClientT

    from .bot import BotBase
    from .context import Context
    from .core import Command

__all__ = (
    'CogMeta',
    'Cog',
    'GroupCog',
)

FuncT = TypeVar('FuncT', bound=Callable[..., Any])

MISSING: Any = discord.utils.MISSING
_log = logging.getLogger(__name__)


class CogMeta(type):
    """A metaclass for defining a cog.

    Note that you should probably not use this directly. It is exposed
    purely for documentation purposes along with making custom metaclasses to intermix
    with other metaclasses such as the :class:`abc.ABCMeta` metaclass.

    For example, to create an abstract cog mixin class, the following would be done.

    .. code-block:: python3

        import abc

        class CogABCMeta(commands.CogMeta, abc.ABCMeta):
            pass

        class SomeMixin(metaclass=abc.ABCMeta):
            pass

        class SomeCogMixin(SomeMixin, commands.Cog, metaclass=CogABCMeta):
            pass

    .. note::

        When passing an attribute of a metaclass that is documented below, note
        that you must pass it as a keyword-only argument to the class creation
        like the following example:

        .. code-block:: python3

            class MyCog(commands.Cog, name='My Cog'):
                pass

    Attributes
    -----------
    name: :class:`str`
        The cog name. By default, it is the name of the class with no modification.
    description: :class:`str`
        The cog description. By default, it is the cleaned docstring of the class.

        .. versionadded:: 1.6

    command_attrs: :class:`dict`
        A list of attributes to apply to every command inside this cog. The dictionary
        is passed into the :class:`Command` options at ``__init__``.
        If you specify attributes inside the command attribute in the class, it will
        override the one specified inside this attribute. For example:

        .. code-block:: python3

            class MyCog(commands.Cog, command_attrs=dict(hidden=True)):
                @commands.command()
                async def foo(self, ctx):
                    pass # hidden -> True

                @commands.command(hidden=False)
                async def bar(self, ctx):
                    pass # hidden -> False

    group_name: Union[:class:`str`, :class:`~discord.app_commands.locale_str`]
        The group name of a cog. This is only applicable for :class:`GroupCog` instances.
        By default, it's the same value as :attr:`name`.

        .. versionadded:: 2.0
    group_description: Union[:class:`str`, :class:`~discord.app_commands.locale_str`]
        The group description of a cog. This is only applicable for :class:`GroupCog` instances.
        By default, it's the same value as :attr:`description`.

        .. versionadded:: 2.0
    group_nsfw: :class:`bool`
        Whether the application command group is NSFW. This is only applicable for :class:`GroupCog` instances.
        By default, it's ``False``.

        .. versionadded:: 2.0
    group_auto_locale_strings: :class:`bool`
        If this is set to ``True``, then all translatable strings will implicitly
        be wrapped into :class:`~discord.app_commands.locale_str` rather
        than :class:`str`. Defaults to ``True``.

        .. versionadded:: 2.0
    group_extras: :class:`dict`
        A dictionary that can be used to store extraneous data.
        This is only applicable for :class:`GroupCog` instances.
        The library will not touch any values or keys within this dictionary.

        .. versionadded:: 2.1
    """

    __cog_name__: str
    __cog_description__: str
    __cog_group_name__: Union[str, app_commands.locale_str]
    __cog_group_description__: Union[str, app_commands.locale_str]
    __cog_group_nsfw__: bool
    __cog_group_auto_locale_strings__: bool
    __cog_group_extras__: Dict[Any, Any]
    __cog_settings__: Dict[str, Any]
    __cog_commands__: List[Command[Any, ..., Any]]
    __cog_app_commands__: List[Union[app_commands.Group, app_commands.Command[Any, ..., Any]]]
    __cog_listeners__: List[Tuple[str, str]]

    def __new__(cls, *args: Any, **kwargs: Any) -> CogMeta:
        name, bases, attrs = args
        if any(issubclass(base, app_commands.Group) for base in bases):
            raise TypeError(
                'Cannot inherit from app_commands.Group with commands.Cog, consider using commands.GroupCog instead'
            )

        # If name='...' is given but not group_name='...' then name='...' is used for both.
        # If neither is given then cog name is the class name but group name is kebab case
        try:
            cog_name = kwargs.pop('name')
        except KeyError:
            cog_name = name
            try:
                group_name = kwargs.pop('group_name')
            except KeyError:
                group_name = _to_kebab_case(name)
        else:
            group_name = kwargs.pop('group_name', cog_name)

        attrs['__cog_settings__'] = kwargs.pop('command_attrs', {})
        attrs['__cog_name__'] = cog_name
        attrs['__cog_group_name__'] = group_name
        attrs['__cog_group_nsfw__'] = kwargs.pop('group_nsfw', False)
        attrs['__cog_group_auto_locale_strings__'] = kwargs.pop('group_auto_locale_strings', True)
        attrs['__cog_group_extras__'] = kwargs.pop('group_extras', {})

        description = kwargs.pop('description', None)
        if description is None:
            description = inspect.cleandoc(attrs.get('__doc__', ''))

        attrs['__cog_description__'] = description
        attrs['__cog_group_description__'] = kwargs.pop('group_description', description or '\u2026')

        commands = {}
        cog_app_commands = {}
        listeners = {}
        no_bot_cog = 'Commands or listeners must not start with cog_ or bot_ (in method {0.__name__}.{1})'

        new_cls = super().__new__(cls, name, bases, attrs, **kwargs)
        for base in reversed(new_cls.__mro__):
            for elem, value in base.__dict__.items():
                if elem in commands:
                    del commands[elem]
                if elem in listeners:
                    del listeners[elem]

                is_static_method = isinstance(value, staticmethod)
                if is_static_method:
                    value = value.__func__
                if isinstance(value, _BaseCommand):
                    if is_static_method:
                        raise TypeError(f'Command in method {base}.{elem!r} must not be staticmethod.')
                    if elem.startswith(('cog_', 'bot_')):
                        raise TypeError(no_bot_cog.format(base, elem))
                    commands[elem] = value
                elif isinstance(value, (app_commands.Group, app_commands.Command)) and value.parent is None:
                    if is_static_method:
                        raise TypeError(f'Command in method {base}.{elem!r} must not be staticmethod.')
                    if elem.startswith(('cog_', 'bot_')):
                        raise TypeError(no_bot_cog.format(base, elem))
                    cog_app_commands[elem] = value
                elif inspect.iscoroutinefunction(value):
                    try:
                        getattr(value, '__cog_listener__')
                    except AttributeError:
                        continue
                    else:
                        if elem.startswith(('cog_', 'bot_')):
                            raise TypeError(no_bot_cog.format(base, elem))
                        listeners[elem] = value

        new_cls.__cog_commands__ = list(commands.values())  # this will be copied in Cog.__new__
        new_cls.__cog_app_commands__ = list(cog_app_commands.values())

        listeners_as_list = []
        for listener in listeners.values():
            for listener_name in listener.__cog_listener_names__:
                # I use __name__ instead of just storing the value so I can inject
                # the self attribute when the time comes to add them to the bot
                listeners_as_list.append((listener_name, listener.__name__))

        new_cls.__cog_listeners__ = listeners_as_list
        return new_cls

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args)

    @classmethod
    def qualified_name(cls) -> str:
        return cls.__cog_name__


def _cog_special_method(func: FuncT) -> FuncT:
    func.__cog_special_method__ = None
    return func


class Cog(metaclass=CogMeta):
    """The base class that all cogs must inherit from.

    A cog is a collection of commands, listeners, and optional state to
    help group commands together. More information on them can be found on
    the :ref:`ext_commands_cogs` page.

    When inheriting from this class, the options shown in :class:`CogMeta`
    are equally valid here.
    """

    __cog_name__: str
    __cog_description__: str
    __cog_group_name__: Union[str, app_commands.locale_str]
    __cog_group_description__: Union[str, app_commands.locale_str]
    __cog_settings__: Dict[str, Any]
    __cog_commands__: List[Command[Self, ..., Any]]
    __cog_app_commands__: List[Union[app_commands.Group, app_commands.Command[Self, ..., Any]]]
    __cog_listeners__: List[Tuple[str, str]]
    __cog_is_app_commands_group__: ClassVar[bool] = False
    __cog_app_commands_group__: Optional[app_commands.Group]
    __discord_app_commands_error_handler__: Optional[
        Callable[[discord.Interaction, app_commands.AppCommandError], Coroutine[Any, Any, None]]
    ]

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        # For issue 426, we need to store a copy of the command objects
        # since we modify them to inject `self` to them.
        # To do this, we need to interfere with the Cog creation process.
        self = super().__new__(cls)
        cmd_attrs = cls.__cog_settings__

        # Either update the command with the cog provided defaults or copy it.
        # r.e type ignore, type-checker complains about overriding a ClassVar
        self.__cog_commands__ = tuple(c._update_copy(cmd_attrs) for c in cls.__cog_commands__)  # type: ignore

        lookup = {cmd.qualified_name: cmd for cmd in self.__cog_commands__}

        # Register the application commands
        children: List[Union[app_commands.Group, app_commands.Command[Self, ..., Any]]] = []
        app_command_refs: Dict[str, Union[app_commands.Group, app_commands.Command[Self, ..., Any]]] = {}

        if cls.__cog_is_app_commands_group__:
            group = app_commands.Group(
                name=cls.__cog_group_name__,
                description=cls.__cog_group_description__,
                nsfw=cls.__cog_group_nsfw__,
                auto_locale_strings=cls.__cog_group_auto_locale_strings__,
                parent=None,
                guild_ids=getattr(cls, '__discord_app_commands_default_guilds__', None),
                guild_only=getattr(cls, '__discord_app_commands_guild_only__', False),
                allowed_contexts=getattr(cls, '__discord_app_commands_contexts__', None),
                allowed_installs=getattr(cls, '__discord_app_commands_installation_types__', None),
                default_permissions=getattr(cls, '__discord_app_commands_default_permissions__', None),
                extras=cls.__cog_group_extras__,
            )
        else:
            group = None

        self.__cog_app_commands_group__ = group

        # Update the Command instances dynamically as well
        for command in self.__cog_commands__:
            setattr(self, command.callback.__name__, command)
            parent = command.parent
            if parent is not None:
                # Get the latest parent reference
                parent = lookup[parent.qualified_name]  # type: ignore

                # Hybrid commands already deal with updating the reference
                # Due to the copy below, so we need to handle them specially
                if hasattr(parent, '__commands_is_hybrid__') and hasattr(command, '__commands_is_hybrid__'):
                    current: Optional[Union[app_commands.Group, app_commands.Command[Self, ..., Any]]] = getattr(
                        command, 'app_command', None
                    )
                    updated = app_command_refs.get(command.qualified_name)
                    if current and updated:
                        command.app_command = updated  # type: ignore  # Safe attribute access

                # Update our parent's reference to our self
                parent.remove_command(command.name)  # type: ignore
                parent.add_command(command)  # type: ignore

            if hasattr(command, '__commands_is_hybrid__') and parent is None:
                app_command: Optional[Union[app_commands.Group, app_commands.Command[Self, ..., Any]]] = getattr(
                    command, 'app_command', None
                )
                if app_command:
                    group_parent = self.__cog_app_commands_group__
                    app_command = app_command._copy_with(parent=group_parent, binding=self)
                    # The type checker does not see the app_command attribute even though it exists
                    command.app_command = app_command  # type: ignore

                    # Update all the references to point to the new copy
                    if isinstance(app_command, app_commands.Group):
                        for child in app_command.walk_commands():
                            app_command_refs[child.qualified_name] = child
                            if hasattr(child, '__commands_is_hybrid_app_command__') and child.qualified_name in lookup:
                                child.wrapped = lookup[child.qualified_name]  # type: ignore

                    if self.__cog_app_commands_group__:
                        children.append(app_command)

        if Cog._get_overridden_method(self.cog_app_command_error) is not None:
            error_handler = self.cog_app_command_error
        else:
            error_handler = None

        self.__discord_app_commands_error_handler__ = error_handler

        for command in cls.__cog_app_commands__:
            copy = command._copy_with(parent=self.__cog_app_commands_group__, binding=self)

            # Update set bindings
            if copy._attr:
                setattr(self, copy._attr, copy)

            if isinstance(copy, app_commands.Group):
                copy.__discord_app_commands_error_handler__ = error_handler
                for command in copy._children.values():
                    if isinstance(command, app_commands.Group):
                        command.__discord_app_commands_error_handler__ = error_handler

            children.append(copy)

        self.__cog_app_commands__ = children
        if self.__cog_app_commands_group__:
            self.__cog_app_commands_group__.module = cls.__module__
            mapping = {cmd.name: cmd for cmd in children}
            if len(mapping) > 25:
                raise TypeError('maximum number of application command children exceeded')

            self.__cog_app_commands_group__._children = mapping

        return self

    def get_commands(self) -> List[Command[Self, ..., Any]]:
        r"""Returns the commands that are defined inside this cog.

        This does *not* include :class:`discord.app_commands.Command` or :class:`discord.app_commands.Group`
        instances.

        Returns
        --------
        List[:class:`.Command`]
            A :class:`list` of :class:`.Command`\s that are
            defined inside this cog, not including subcommands.
        """
        return [c for c in self.__cog_commands__ if c.parent is None]

    def get_app_commands(self) -> List[Union[app_commands.Command[Self, ..., Any], app_commands.Group]]:
        r"""Returns the app commands that are defined inside this cog.

        Returns
        --------
        List[Union[:class:`discord.app_commands.Command`, :class:`discord.app_commands.Group`]]
            A :class:`list` of :class:`discord.app_commands.Command`\s and :class:`discord.app_commands.Group`\s that are
            defined inside this cog, not including subcommands.
        """
        return [c for c in self.__cog_app_commands__ if c.parent is None]

    @property
    def qualified_name(self) -> str:
        """:class:`str`: Returns the cog's specified name, not the class name."""
        return self.__cog_name__

    @property
    def description(self) -> str:
        """:class:`str`: Returns the cog's description, typically the cleaned docstring."""
        return self.__cog_description__

    @description.setter
    def description(self, description: str) -> None:
        self.__cog_description__ = description

    def walk_commands(self) -> Generator[Command[Self, ..., Any], None, None]:
        """An iterator that recursively walks through this cog's commands and subcommands.

        Yields
        ------
        Union[:class:`.Command`, :class:`.Group`]
            A command or group from the cog.
        """
        from .core import GroupMixin

        for command in self.__cog_commands__:
            if command.parent is None:
                yield command
                if isinstance(command, GroupMixin):
                    yield from command.walk_commands()

    def walk_app_commands(self) -> Generator[Union[app_commands.Command[Self, ..., Any], app_commands.Group], None, None]:
        """An iterator that recursively walks through this cog's app commands and subcommands.

        Yields
        ------
        Union[:class:`discord.app_commands.Command`, :class:`discord.app_commands.Group`]
            An app command or group from the cog.
        """
        for command in self.__cog_app_commands__:
            yield command
            if isinstance(command, app_commands.Group):
                yield from command.walk_commands()

    @property
    def app_command(self) -> Optional[app_commands.Group]:
        """Optional[:class:`discord.app_commands.Group`]: Returns the associated group with this cog.

        This is only available if inheriting from :class:`GroupCog`.
        """
        return self.__cog_app_commands_group__

    def get_listeners(self) -> List[Tuple[str, Callable[..., Any]]]:
        """Returns a :class:`list` of (name, function) listener pairs that are defined in this cog.

        Returns
        --------
        List[Tuple[:class:`str`, :ref:`coroutine <coroutine>`]]
            The listeners defined in this cog.
        """
        return [(name, getattr(self, method_name)) for name, method_name in self.__cog_listeners__]

    @classmethod
    def _get_overridden_method(cls, method: FuncT) -> Optional[FuncT]:
        """Return None if the method is not overridden. Otherwise returns the overridden method."""
        return getattr(method.__func__, '__cog_special_method__', method)

    @classmethod
    def listener(cls, name: str = MISSING) -> Callable[[FuncT], FuncT]:
        """A decorator that marks a function as a listener.

        This is the cog equivalent of :meth:`.Bot.listen`.

        Parameters
        ------------
        name: :class:`str`
            The name of the event being listened to. If not provided, it
            defaults to the function's name.

        Raises
        --------
        TypeError
            The function is not a coroutine function or a string was not passed as
            the name.
        """

        if name is not MISSING and not isinstance(name, str):
            raise TypeError(f'Cog.listener expected str but received {name.__class__.__name__} instead.')

        def decorator(func: FuncT) -> FuncT:
            actual = func
            if isinstance(actual, staticmethod):
                actual = actual.__func__
            if not inspect.iscoroutinefunction(actual):
                raise TypeError('Listener function must be a coroutine function.')
            actual.__cog_listener__ = True
            to_assign = name or actual.__name__
            try:
                actual.__cog_listener_names__.append(to_assign)
            except AttributeError:
                actual.__cog_listener_names__ = [to_assign]
            # we have to return `func` instead of `actual` because
            # we need the type to be `staticmethod` for the metaclass
            # to pick it up but the metaclass unfurls the function and
            # thus the assignments need to be on the actual function
            return func

        return decorator

    def has_error_handler(self) -> bool:
        """:class:`bool`: Checks whether the cog has an error handler.

        .. versionadded:: 1.7
        """
        return not hasattr(self.cog_command_error.__func__, '__cog_special_method__')

    def has_app_command_error_handler(self) -> bool:
        """:class:`bool`: Checks whether the cog has an app error handler.

        .. versionadded:: 2.1
        """
        return not hasattr(self.cog_app_command_error.__func__, '__cog_special_method__')

    @_cog_special_method
    async def cog_load(self) -> None:
        """|maybecoro|

        A special method that is called when the cog gets loaded.

        Subclasses must replace this if they want special asynchronous loading behaviour.
        Note that the ``__init__`` special method does not allow asynchronous code to run
        inside it, thus this is helpful for setting up code that needs to be asynchronous.

        .. versionadded:: 2.0
        """
        pass

    @_cog_special_method
    async def cog_unload(self) -> None:
        """|maybecoro|

        A special method that is called when the cog gets removed.

        Subclasses must replace this if they want special unloading behaviour.

        Exceptions raised in this method are ignored during extension unloading.

        .. versionchanged:: 2.0

            This method can now be a :term:`coroutine`.
        """
        pass

    @_cog_special_method
    def bot_check_once(self, ctx: Context[BotT]) -> bool:
        """A special method that registers as a :meth:`.Bot.check_once`
        check.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def bot_check(self, ctx: Context[BotT]) -> bool:
        """A special method that registers as a :meth:`.Bot.check`
        check.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def cog_check(self, ctx: Context[BotT]) -> bool:
        """A special method that registers as a :func:`~discord.ext.commands.check`
        for every command and subcommand in this cog.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def interaction_check(self, interaction: discord.Interaction[ClientT], /) -> bool:
        """A special method that registers as a :func:`discord.app_commands.check`
        for every app command and subcommand in this cog.

        This function **can** be a coroutine and must take a sole parameter,
        ``interaction``, to represent the :class:`~discord.Interaction`.

        .. versionadded:: 2.0
        """
        return True

    @_cog_special_method
    async def cog_command_error(self, ctx: Context[BotT], error: Exception) -> None:
        """|coro|

        A special method that is called whenever an error
        is dispatched inside this cog.

        This is similar to :func:`.on_command_error` except only applying
        to the commands inside this cog.

        This **must** be a coroutine.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context where the error happened.
        error: :class:`CommandError`
            The error that happened.
        """
        pass

    @_cog_special_method
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """|coro|

        A special method that is called whenever an error within
        an application command is dispatched inside this cog.

        This is similar to :func:`discord.app_commands.CommandTree.on_error` except
        only applying to the application commands inside this cog.

        This **must** be a coroutine.

        Parameters
        -----------
        interaction: :class:`~discord.Interaction`
            The interaction that is being handled.
        error: :exc:`~discord.app_commands.AppCommandError`
            The exception that was raised.
        """
        pass

    @_cog_special_method
    async def cog_before_invoke(self, ctx: Context[BotT]) -> None:
        """|coro|

        A special method that acts as a cog local pre-invoke hook.

        This is similar to :meth:`.Command.before_invoke`.

        This **must** be a coroutine.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context.
        """
        pass

    @_cog_special_method
    async def cog_after_invoke(self, ctx: Context[BotT]) -> None:
        """|coro|

        A special method that acts as a cog local post-invoke hook.

        This is similar to :meth:`.Command.after_invoke`.

        This **must** be a coroutine.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context.
        """
        pass

    async def _inject(self, bot: BotBase, override: bool, guild: Optional[Snowflake], guilds: Sequence[Snowflake]) -> Self:
        cls = self.__class__

        # we'll call this first so that errors can propagate without
        # having to worry about undoing anything
        await maybe_coroutine(self.cog_load)

        # realistically, the only thing that can cause loading errors
        # is essentially just the command loading, which raises if there are
        # duplicates. When this condition is met, we want to undo all what
        # we've added so far for some form of atomic loading.
        for index, command in enumerate(self.__cog_commands__):
            command.cog = self
            if command.parent is None:
                try:
                    bot.add_command(command, guild=guild, guilds=guilds)
                except Exception as e:
                    # undo our additions
                    for to_undo in self.__cog_commands__[:index]:
                        if to_undo.parent is None:
                            bot.remove_command(to_undo.name)
                    try:
                        await maybe_coroutine(self.cog_unload)
                    finally:
                        raise e

        # check if we're overriding the default
        if cls.bot_check is not Cog.bot_check:
            bot.add_check(self.bot_check)

        if cls.bot_check_once is not Cog.bot_check_once:
            bot.add_check(self.bot_check_once, call_once=True)

        # while Bot.add_listener can raise if it's not a coroutine,
        # this precondition is already met by the listener decorator
        # already, thus this should never raise.
        # Outside of, memory errors and the like...
        for name, method_name in self.__cog_listeners__:
            bot.add_listener(getattr(self, method_name), name)

        # Only do this if these are "top level" commands
        if not self.__cog_app_commands_group__:
            for command in self.__cog_app_commands__:
                # This is already atomic
                bot.tree.add_command(command, override=override, guild=guild, guilds=guilds)

        return self

    async def _eject(self, bot: BotBase, guild_ids: Optional[Iterable[int]]) -> None:
        cls = self.__class__

        try:
            for command in self.__cog_commands__:
                if command.parent is None:
                    bot.remove_command(command.name)

            if not self.__cog_app_commands_group__:
                for command in self.__cog_app_commands__:
                    guild_ids = guild_ids or command._guild_ids
                    if guild_ids is None:
                        bot.tree.remove_command(command.name)
                    else:
                        for guild_id in guild_ids:
                            bot.tree.remove_command(command.name, guild=discord.Object(id=guild_id))

            for name, method_name in self.__cog_listeners__:
                bot.remove_listener(getattr(self, method_name), name)

            if cls.bot_check is not Cog.bot_check:
                bot.remove_check(self.bot_check)

            if cls.bot_check_once is not Cog.bot_check_once:
                bot.remove_check(self.bot_check_once, call_once=True)
        finally:
            try:
                await maybe_coroutine(self.cog_unload)
            except Exception:
                _log.exception('Ignoring exception in cog unload for Cog %r (%r)', cls, self.qualified_name)


class GroupCog(Cog):
    """Represents a cog that also doubles as a parent :class:`discord.app_commands.Group` for
    the application commands defined within it.

    This inherits from :class:`Cog` and the options in :class:`CogMeta` also apply to this.
    See the :class:`Cog` documentation for methods.

    Decorators such as :func:`~discord.app_commands.guild_only`, :func:`~discord.app_commands.guilds`,
    and :func:`~discord.app_commands.default_permissions` will apply to the group if used on top of the
    cog.

    Hybrid commands will also be added to the Group, giving the ability to categorize slash commands into
    groups, while keeping the prefix-style command as a root-level command.

    For example:

    .. code-block:: python3

        from discord import app_commands
        from discord.ext import commands

        @app_commands.guild_only()
        class MyCog(commands.GroupCog, group_name='my-cog'):
            pass

    .. versionadded:: 2.0
    """

    __cog_is_app_commands_group__: ClassVar[bool] = True
