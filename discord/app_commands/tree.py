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
import logging
import inspect

from typing import (
    Any,
    TYPE_CHECKING,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Generic,
    List,
    Literal,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    overload,
)
from collections import Counter


from .namespace import Namespace, ResolveKey
from .models import AppCommand
from .commands import Command, ContextMenu, Group
from .errors import (
    AppCommandError,
    CommandAlreadyRegistered,
    CommandNotFound,
    CommandSignatureMismatch,
    CommandLimitReached,
    CommandSyncFailure,
    MissingApplicationID,
)
from .installs import AppCommandContext, AppInstallationType
from .translator import Translator, locale_str
from ..errors import ClientException, HTTPException
from ..enums import AppCommandType, InteractionType
from ..utils import MISSING, _get_as_snowflake, _is_submodule, _shorten
from .._types import ClientT


if TYPE_CHECKING:
    from ..types.interactions import ApplicationCommandInteractionData, ApplicationCommandInteractionDataOption
    from ..types.command import ApplicationCommand
    from ..interactions import Interaction
    from ..abc import Snowflake
    from .commands import ContextMenuCallback, CommandCallback, P, T

    ErrorFunc = Callable[
        [Interaction[ClientT], AppCommandError],
        Coroutine[Any, Any, Any],
    ]

__all__ = ('CommandTree',)

_log = logging.getLogger(__name__)


def _retrieve_guild_ids(
    command: Any, guild: Optional[Snowflake] = MISSING, guilds: Sequence[Snowflake] = MISSING
) -> Optional[Set[int]]:
    if guild is not MISSING and guilds is not MISSING:
        raise TypeError('cannot mix guild and guilds keyword arguments')

    # guilds=[] or guilds=[...]
    if guild is MISSING:
        # If no arguments are given then it should default to the ones
        # given to the guilds(...) decorator or None for global.
        if guilds is MISSING:
            return getattr(command, '_guild_ids', None)

        # guilds=[] is the same as global
        if len(guilds) == 0:
            return None

        return {g.id for g in guilds}

    # At this point it should be...
    # guild=None or guild=Object
    if guild is None:
        return None
    return {guild.id}


class CommandTree(Generic[ClientT]):
    """Represents a container that holds application command information.

    Parameters
    -----------
    client: :class:`~discord.Client`
        The client instance to get application command information from.
    fallback_to_global: :class:`bool`
        If a guild-specific command is not found when invoked, then try falling back into
        a global command in the tree. For example, if the tree locally has a ``/ping`` command
        under the global namespace but the guild has a guild-specific ``/ping``, instead of failing
        to find the guild-specific ``/ping`` command it will fall back to the global ``/ping`` command.
        This has the potential to raise more :exc:`~discord.app_commands.CommandSignatureMismatch` errors
        than usual. Defaults to ``True``.
    allowed_contexts: :class:`~discord.app_commands.AppCommandContext`
        The default allowed contexts that applies to all commands in this tree.
        Note that you can override this on a per command basis.

        .. versionadded:: 2.4
    allowed_installs: :class:`~discord.app_commands.AppInstallationType`
        The default allowed install locations that apply to all commands in this tree.
        Note that you can override this on a per command basis.

        .. versionadded:: 2.4
    store_app_command_ids: :class:`bool`
        Whether to store the application command IDs on the tree. These can be used to mention a command.
        Defaults to ``False``.

        This must be enabled if you want to use :meth:`get_command_mention` or :meth:`get_command_id`.

        .. versionadded:: 2.5
    """

    def __init__(
        self,
        client: ClientT,
        *,
        fallback_to_global: bool = True,
        allowed_contexts: AppCommandContext = MISSING,
        allowed_installs: AppInstallationType = MISSING,
        store_app_command_ids: bool = False,
    ):
        self.client: ClientT = client
        self._http = client.http
        self._state = client._connection

        if self._state._command_tree is not None:
            raise ClientException('This client already has an associated command tree.')

        self._state._command_tree = self
        self.fallback_to_global: bool = fallback_to_global
        self.allowed_contexts = AppCommandContext() if allowed_contexts is MISSING else allowed_contexts
        self.allowed_installs = AppInstallationType() if allowed_installs is MISSING else allowed_installs
        self._guild_commands: Dict[int, Dict[str, Union[Command, Group]]] = {}
        self._global_commands: Dict[str, Union[Command, Group]] = {}
        # (name, guild_id, command_type): Command
        # The above two mappings can use this structure too but we need fast retrieval
        # by name and guild_id in the above case while here it isn't as important since
        # it's uncommon and N=5 anyway.
        self._context_menus: Dict[Tuple[str, Optional[int], int], ContextMenu] = {}

        self.store_app_command_ids: bool = store_app_command_ids
        self._command_ids: Dict[Optional[int], Dict[str, int]] = {}

    async def fetch_command(self, command_id: int, /, *, guild: Optional[Snowflake] = None) -> AppCommand:
        """|coro|

        Fetches an application command from the application.

        Parameters
        -----------
        command_id: :class:`int`
            The ID of the command to fetch.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to fetch the command from. If not passed then the global command
            is fetched instead.

        Raises
        -------
        HTTPException
            Fetching the command failed.
        MissingApplicationID
            The application ID could not be found.
        NotFound
            The application command was not found.
            This could also be because the command is a guild command
            and the guild was not specified and vice versa.

        Returns
        --------
        :class:`~discord.app_commands.AppCommand`
            The application command.
        """
        if self.client.application_id is None:
            raise MissingApplicationID

        if guild is None:
            command = await self._http.get_global_command(self.client.application_id, command_id)
        else:
            command = await self._http.get_guild_command(self.client.application_id, guild.id, command_id)

        self._update_command_ids(command)
        return AppCommand(data=command, state=self._state)

    async def fetch_commands(self, *, guild: Optional[Snowflake] = None) -> List[AppCommand]:
        """|coro|

        Fetches the application's current commands.

        If no guild is passed then global commands are fetched, otherwise
        the guild's commands are fetched instead.

        .. note::

            This includes context menu commands.

        Parameters
        -----------
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to fetch the commands from. If not passed then global commands
            are fetched instead.

        Raises
        -------
        HTTPException
            Fetching the commands failed.
        MissingApplicationID
            The application ID could not be found.

        Returns
        --------
        List[:class:`~discord.app_commands.AppCommand`]
            The application's commands.
        """
        if self.client.application_id is None:
            raise MissingApplicationID

        if guild is None:
            commands = await self._http.get_global_commands(self.client.application_id)
        else:
            commands = await self._http.get_guild_commands(self.client.application_id, guild.id)

        self._update_command_ids(*commands)
        return [AppCommand(data=command, state=self._state) for command in commands]

    def get_command_id(
        self, command: Union[AppCommand, Command, ContextMenu, Group, str], /, *, guild: Optional[Snowflake] = None
    ) -> Optional[int]:
        """Gets the command ID for a command.

        Parameters
        -----------
        name: Union[:class:`~discord.app_commands.Command`, :class:`~discord.app_commands.ContextMenu`, :class:`~discord.app_commands.Group`, :class:`str`]
            The name of the command to get the ID for.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to get the command ID for. If not passed then the global command
            ID is fetched instead.

        Returns
        --------
        Optional[:class:`int`]
            The command ID if found, otherwise ``None``.

            .. note::

                Group commands will return the ID of the root command. Subcommands do not have their own IDs.
        """
        name: Optional[str] = None

        if isinstance(command, AppCommand):
            return command.id

        if isinstance(command, (Command, Group, ContextMenu)):
            name = (command.root_parent or command).name if not isinstance(command, ContextMenu) else command.name
        elif isinstance(command, str):
            name = command.split()[0]

        return self._command_ids.get(guild.id if guild else None, {}).get(name)

    def get_command_mention(
        self, command: Union[AppCommand, Command, ContextMenu, Group, str], /, *, guild: Optional[Snowflake] = None
    ) -> Optional[str]:
        """Gets the mention string for a command.

        Parameters
        -----------
        command: Union[:class:`~discord.app_commands.Command`, :class:`~discord.app_commands.ContextMenu`, :class:`~discord.app_commands.Group`, :class:`str`]
            The command to get the mention string for.

        Returns
        --------
        Optional[:class:`str`]
            The mention string for the command if found, otherwise ``None``.

            .. note::

                Remember that groups cannot be mentioned, only with a subcommand.
        """
        if isinstance(command, AppCommand):
            return command.mention

        command_id = self.get_command_id(command, guild=guild)
        if command_id is None:
            return None

        if isinstance(command, (Command, Group, ContextMenu)):
            full_name = command.qualified_name
        elif isinstance(command, str):
            full_name = command

        return f'</{full_name}:{command_id}>'

    def get_command_ids(self, guild: Optional[Snowflake] = None) -> Dict[str, int]:
        """Gets all command IDs for the given guild.

        Parameters
        -----------
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to get the command IDs for. If not passed then the global command
            IDs are returned instead.

        Returns
        --------
        Dict[:class:`str`, :class:`int`]
            A dictionary of command names and their IDs.
        """
        return self._command_ids.get(guild.id if guild else None, {})

    def copy_global_to(self, *, guild: Snowflake) -> None:
        """Copies all global commands to the specified guild.

        This method is mainly available for development purposes, as it allows you
        to copy your global commands over to a testing guild easily.

        Note that this method will *override* pre-existing guild commands that would conflict.

        Parameters
        -----------
        guild: :class:`~discord.abc.Snowflake`
            The guild to copy the commands to.

        Raises
        --------
        CommandLimitReached
            The maximum number of commands was reached for that guild.
            This is currently 100 for slash commands and 5 for context menu commands.
        """

        try:
            mapping = self._guild_commands[guild.id].copy()
        except KeyError:
            mapping = {}

        mapping.update(self._global_commands)
        if len(mapping) > 100:
            raise CommandLimitReached(guild_id=guild.id, limit=100)

        ctx_menu: Dict[Tuple[str, Optional[int], int], ContextMenu] = {
            (name, guild.id, cmd_type): cmd
            for ((name, g, cmd_type), cmd) in self._context_menus.items()
            if g is None or g == guild.id
        }

        counter = Counter(cmd_type for _, _, cmd_type in ctx_menu)
        for cmd_type, count in counter.items():
            if count > 5:
                as_enum = AppCommandType(cmd_type)
                raise CommandLimitReached(guild_id=guild.id, limit=5, type=as_enum)

        self._context_menus.update(ctx_menu)
        self._guild_commands[guild.id] = mapping

    def add_command(
        self,
        command: Union[Command[Any, ..., Any], ContextMenu, Group],
        /,
        *,
        guild: Optional[Snowflake] = MISSING,
        guilds: Sequence[Snowflake] = MISSING,
        override: bool = False,
    ) -> None:
        """Adds an application command to the tree.

        This only adds the command locally -- in order to sync the commands
        and enable them in the client, :meth:`sync` must be called.

        The root parent of the command is added regardless of the type passed.

        Parameters
        -----------
        command: Union[:class:`Command`, :class:`Group`]
            The application command or group to add.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to add the command to. If not given or ``None`` then it
            becomes a global command instead.

            .. note ::

                Due to a Discord limitation, this keyword argument cannot be used in conjunction with
                contexts (e.g. :func:`.app_commands.allowed_contexts`) or installation types
                (e.g. :func:`.app_commands.allowed_installs`).

        guilds: List[:class:`~discord.abc.Snowflake`]
            The list of guilds to add the command to. This cannot be mixed
            with the ``guild`` parameter. If no guilds are given at all
            then it becomes a global command instead.

            .. note ::

                Due to a Discord limitation, this keyword argument cannot be used in conjunction with
                contexts (e.g. :func:`.app_commands.allowed_contexts`) or installation types
                (e.g. :func:`.app_commands.allowed_installs`).

        override: :class:`bool`
            Whether to override a command with the same name. If ``False``
            an exception is raised. Default is ``False``.

        Raises
        --------
        ~discord.app_commands.CommandAlreadyRegistered
            The command was already registered and no override was specified.
        TypeError
            The application command passed is not a valid application command.
            Or, ``guild`` and ``guilds`` were both given.
        CommandLimitReached
            The maximum number of commands was reached globally or for that guild.
            This is currently 100 for slash commands and 5 for context menu commands.
        """

        guild_ids = _retrieve_guild_ids(command, guild, guilds)
        if isinstance(command, ContextMenu):
            type = command.type.value
            name = command.name

            def _context_menu_add_helper(
                guild_id: Optional[int],
                data: Dict[Tuple[str, Optional[int], int], ContextMenu],
                name: str = name,
                type: int = type,
            ) -> None:
                key = (name, guild_id, type)
                found = key in self._context_menus
                if found and not override:
                    raise CommandAlreadyRegistered(name, guild_id)

                # If the key is found and overridden then it shouldn't count as an extra addition
                # read as `0 if override and found else 1` if confusing
                to_add = not (override and found)
                total = sum(1 for _, g, t in self._context_menus if g == guild_id and t == type)
                if total + to_add > 5:
                    raise CommandLimitReached(guild_id=guild_id, limit=5, type=AppCommandType(type))
                data[key] = command

            if guild_ids is None:
                _context_menu_add_helper(None, self._context_menus)
            else:
                current: Dict[Tuple[str, Optional[int], int], ContextMenu] = {}
                for guild_id in guild_ids:
                    _context_menu_add_helper(guild_id, current)

                # Update at the end in order to make sure the update is atomic.
                # An error during addition could end up making the context menu mapping
                # have a partial state
                self._context_menus.update(current)
            return
        elif not isinstance(command, (Command, Group)):
            raise TypeError(f'Expected an application command, received {command.__class__.__name__} instead')

        # todo: validate application command groups having children (required)

        root = command.root_parent or command
        name = root.name
        if guild_ids is not None:
            # Validate that the command can be added first, before actually
            # adding it into the mapping. This ensures atomicity.
            for guild_id in guild_ids:
                commands = self._guild_commands.get(guild_id, {})
                found = name in commands
                if found and not override:
                    raise CommandAlreadyRegistered(name, guild_id)

                to_add = not (override and found)
                if len(commands) + to_add > 100:
                    raise CommandLimitReached(guild_id=guild_id, limit=100)

            # Actually add the command now that it has been verified to be okay.
            for guild_id in guild_ids:
                commands = self._guild_commands.setdefault(guild_id, {})
                commands[name] = root
        else:
            found = name in self._global_commands
            if found and not override:
                raise CommandAlreadyRegistered(name, None)

            to_add = not (override and found)
            if len(self._global_commands) + to_add > 100:
                raise CommandLimitReached(guild_id=None, limit=100)
            self._global_commands[name] = root

    @overload
    def remove_command(
        self,
        command: str,
        /,
        *,
        guild: Optional[Snowflake] = ...,
        type: Literal[AppCommandType.message, AppCommandType.user],
    ) -> Optional[ContextMenu]:
        ...

    @overload
    def remove_command(
        self,
        command: str,
        /,
        *,
        guild: Optional[Snowflake] = ...,
        type: Literal[AppCommandType.chat_input] = ...,
    ) -> Optional[Union[Command[Any, ..., Any], Group]]:
        ...

    @overload
    def remove_command(
        self,
        command: str,
        /,
        *,
        guild: Optional[Snowflake] = ...,
        type: AppCommandType,
    ) -> Optional[Union[Command[Any, ..., Any], ContextMenu, Group]]:
        ...

    def remove_command(
        self,
        command: str,
        /,
        *,
        guild: Optional[Snowflake] = None,
        type: AppCommandType = AppCommandType.chat_input,
    ) -> Optional[Union[Command[Any, ..., Any], ContextMenu, Group]]:
        """Removes an application command from the tree.

        This only removes the command locally -- in order to sync the commands
        and remove them in the client, :meth:`sync` must be called.

        Parameters
        -----------
        command: :class:`str`
            The name of the root command to remove.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to remove the command from. If not given or ``None`` then it
            removes a global command instead.
        type: :class:`~discord.AppCommandType`
            The type of command to remove. Defaults to :attr:`~discord.AppCommandType.chat_input`,
            i.e. slash commands.

        Returns
        ---------
        Optional[Union[:class:`Command`, :class:`ContextMenu`, :class:`Group`]]
            The application command that got removed.
            If nothing was removed then ``None`` is returned instead.
        """

        if type is AppCommandType.chat_input:
            if guild is None:
                return self._global_commands.pop(command, None)
            else:
                try:
                    commands = self._guild_commands[guild.id]
                except KeyError:
                    return None
                else:
                    return commands.pop(command, None)
        elif type in (AppCommandType.user, AppCommandType.message):
            guild_id = None if guild is None else guild.id
            key = (command, guild_id, type.value)
            return self._context_menus.pop(key, None)

    def clear_commands(self, *, guild: Optional[Snowflake], type: Optional[AppCommandType] = None) -> None:
        """Clears all application commands from the tree.

        This only removes the commands locally -- in order to sync the commands
        and remove them in the client, :meth:`sync` must be called.

        Parameters
        -----------
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to remove the commands from. If ``None`` then it
            removes all global commands instead.
        type: :class:`~discord.AppCommandType`
            The type of command to clear. If not given or ``None`` then it removes all commands
            regardless of the type.
        """

        if type is None or type is AppCommandType.chat_input:
            if guild is None:
                self._global_commands.clear()
            else:
                try:
                    commands = self._guild_commands[guild.id]
                except KeyError:
                    pass
                else:
                    commands.clear()

        guild_id = None if guild is None else guild.id
        if type is None:
            self._context_menus = {
                (name, _guild_id, value): cmd
                for (name, _guild_id, value), cmd in self._context_menus.items()
                if _guild_id != guild_id
            }
        elif type in (AppCommandType.user, AppCommandType.message):
            self._context_menus = {
                (name, _guild_id, value): cmd
                for (name, _guild_id, value), cmd in self._context_menus.items()
                if _guild_id != guild_id or value != type.value
            }

    @overload
    def get_command(
        self,
        command: str,
        /,
        *,
        guild: Optional[Snowflake] = ...,
        type: Literal[AppCommandType.message, AppCommandType.user],
    ) -> Optional[ContextMenu]:
        ...

    @overload
    def get_command(
        self,
        command: str,
        /,
        *,
        guild: Optional[Snowflake] = ...,
        type: Literal[AppCommandType.chat_input] = ...,
    ) -> Optional[Union[Command[Any, ..., Any], Group]]:
        ...

    @overload
    def get_command(
        self,
        command: str,
        /,
        *,
        guild: Optional[Snowflake] = ...,
        type: AppCommandType,
    ) -> Optional[Union[Command[Any, ..., Any], ContextMenu, Group]]:
        ...

    def get_command(
        self,
        command: str,
        /,
        *,
        guild: Optional[Snowflake] = None,
        type: AppCommandType = AppCommandType.chat_input,
    ) -> Optional[Union[Command[Any, ..., Any], ContextMenu, Group]]:
        """Gets an application command from the tree.

        Parameters
        -----------
        command: :class:`str`
            The name of the root command to get.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to get the command from. If not given or ``None`` then it
            gets a global command instead.
        type: :class:`~discord.AppCommandType`
            The type of command to get. Defaults to :attr:`~discord.AppCommandType.chat_input`,
            i.e. slash commands.

        Returns
        ---------
        Optional[Union[:class:`Command`, :class:`ContextMenu`, :class:`Group`]]
            The application command that was found.
            If nothing was found then ``None`` is returned instead.
        """

        if type is AppCommandType.chat_input:
            if guild is None:
                return self._global_commands.get(command)
            else:
                try:
                    commands = self._guild_commands[guild.id]
                except KeyError:
                    return None
                else:
                    return commands.get(command)
        elif type in (AppCommandType.user, AppCommandType.message):
            guild_id = None if guild is None else guild.id
            key = (command, guild_id, type.value)
            return self._context_menus.get(key)

    @overload
    def get_commands(
        self,
        *,
        guild: Optional[Snowflake] = ...,
        type: Literal[AppCommandType.message, AppCommandType.user],
    ) -> List[ContextMenu]:
        ...

    @overload
    def get_commands(
        self,
        *,
        guild: Optional[Snowflake] = ...,
        type: Literal[AppCommandType.chat_input],
    ) -> List[Union[Command[Any, ..., Any], Group]]:
        ...

    @overload
    def get_commands(
        self,
        *,
        guild: Optional[Snowflake] = ...,
        type: AppCommandType,
    ) -> Union[List[Union[Command[Any, ..., Any], Group]], List[ContextMenu]]:
        ...

    @overload
    def get_commands(
        self,
        *,
        guild: Optional[Snowflake] = ...,
        type: Optional[AppCommandType] = ...,
    ) -> List[Union[Command[Any, ..., Any], Group, ContextMenu]]:
        ...

    def get_commands(
        self,
        *,
        guild: Optional[Snowflake] = None,
        type: Optional[AppCommandType] = None,
    ) -> Union[
        List[ContextMenu],
        List[Union[Command[Any, ..., Any], Group]],
        List[Union[Command[Any, ..., Any], Group, ContextMenu]],
    ]:
        """Gets all application commands from the tree.

        Parameters
        -----------
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to get the commands from, not including global commands.
            If not given or ``None`` then only global commands are returned.
        type: Optional[:class:`~discord.AppCommandType`]
            The type of commands to get. When not given or ``None``, then all
            command types are returned.

        Returns
        ---------
        List[Union[:class:`ContextMenu`, :class:`Command`, :class:`Group`]]
            The application commands from the tree.
        """
        if type is None:
            return self._get_all_commands(guild=guild)

        if type is AppCommandType.chat_input:
            if guild is None:
                return list(self._global_commands.values())
            else:
                try:
                    commands = self._guild_commands[guild.id]
                except KeyError:
                    return []
                else:
                    return list(commands.values())
        else:
            guild_id = None if guild is None else guild.id
            value = type.value
            return [command for ((_, g, t), command) in self._context_menus.items() if g == guild_id and t == value]

    @overload
    def walk_commands(
        self,
        *,
        guild: Optional[Snowflake] = ...,
        type: Literal[AppCommandType.message, AppCommandType.user],
    ) -> Generator[ContextMenu, None, None]:
        ...

    @overload
    def walk_commands(
        self,
        *,
        guild: Optional[Snowflake] = ...,
        type: Literal[AppCommandType.chat_input] = ...,
    ) -> Generator[Union[Command[Any, ..., Any], Group], None, None]:
        ...

    @overload
    def walk_commands(
        self,
        *,
        guild: Optional[Snowflake] = ...,
        type: AppCommandType,
    ) -> Union[Generator[Union[Command[Any, ..., Any], Group], None, None], Generator[ContextMenu, None, None]]:
        ...

    def walk_commands(
        self,
        *,
        guild: Optional[Snowflake] = None,
        type: AppCommandType = AppCommandType.chat_input,
    ) -> Union[Generator[Union[Command[Any, ..., Any], Group], None, None], Generator[ContextMenu, None, None]]:
        """An iterator that recursively walks through all application commands and child commands from the tree.

        Parameters
        -----------
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to iterate the commands from, not including global commands.
            If not given or ``None`` then only global commands are iterated.
        type: :class:`~discord.AppCommandType`
            The type of commands to iterate over. Defaults to :attr:`~discord.AppCommandType.chat_input`,
            i.e. slash commands.

        Yields
        ---------
        Union[:class:`ContextMenu`, :class:`Command`, :class:`Group`]
            The application commands from the tree.
        """

        if type is AppCommandType.chat_input:
            if guild is None:
                for cmd in self._global_commands.values():
                    yield cmd
                    if isinstance(cmd, Group):
                        yield from cmd.walk_commands()
            else:
                try:
                    commands = self._guild_commands[guild.id]
                except KeyError:
                    return
                else:
                    for cmd in commands.values():
                        yield cmd
                        if isinstance(cmd, Group):
                            yield from cmd.walk_commands()
        else:
            guild_id = None if guild is None else guild.id
            value = type.value
            for (_, g, t), command in self._context_menus.items():
                if g == guild_id and t == value:
                    yield command

    def _get_all_commands(
        self, *, guild: Optional[Snowflake] = None
    ) -> List[Union[Command[Any, ..., Any], Group, ContextMenu]]:
        if guild is None:
            base: List[Union[Command[Any, ..., Any], Group, ContextMenu]] = list(self._global_commands.values())
            base.extend(cmd for ((_, g, _), cmd) in self._context_menus.items() if g is None)
            return base
        else:
            try:
                commands = self._guild_commands[guild.id]
            except KeyError:
                guild_id = guild.id
                return [cmd for ((_, g, _), cmd) in self._context_menus.items() if g == guild_id]
            else:
                base: List[Union[Command[Any, ..., Any], Group, ContextMenu]] = list(commands.values())
                guild_id = guild.id
                base.extend(cmd for ((_, g, _), cmd) in self._context_menus.items() if g == guild_id)
                return base

    def _remove_with_module(self, name: str) -> None:
        remove: List[Any] = []
        for key, cmd in self._context_menus.items():
            if cmd.module is not None and _is_submodule(name, cmd.module):
                remove.append(key)

        for key in remove:
            del self._context_menus[key]

        remove = []
        for key, cmd in self._global_commands.items():
            if cmd.module is not None and _is_submodule(name, cmd.module):
                remove.append(key)

        for key in remove:
            del self._global_commands[key]

        for mapping in self._guild_commands.values():
            remove = []
            for key, cmd in mapping.items():
                if cmd.module is not None and _is_submodule(name, cmd.module):
                    remove.append(key)

            for key in remove:
                del mapping[key]

    async def on_error(self, interaction: Interaction[ClientT], error: AppCommandError, /) -> None:
        """|coro|

        A callback that is called when any command raises an :exc:`AppCommandError`.

        The default implementation logs the exception using the library logger
        if the command does not have any error handlers attached to it.

        To get the command that failed, :attr:`discord.Interaction.command` should
        be used.

        Parameters
        -----------
        interaction: :class:`~discord.Interaction`
            The interaction that is being handled.
        error: :exc:`AppCommandError`
            The exception that was raised.
        """

        command = interaction.command
        if command is not None:
            if command._has_any_error_handlers():
                return

            _log.error('Ignoring exception in command %r', command.name, exc_info=error)
        else:
            _log.error('Ignoring exception in command tree', exc_info=error)

    def error(self, coro: ErrorFunc[ClientT]) -> ErrorFunc[ClientT]:
        """A decorator that registers a coroutine as a local error handler.

        This must match the signature of the :meth:`on_error` callback.

        The error passed will be derived from :exc:`AppCommandError`.

        Parameters
        -----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the local error handler.

        Raises
        -------
        TypeError
            The coroutine passed is not actually a coroutine or does
            not match the signature.
        """

        if not inspect.iscoroutinefunction(coro):
            raise TypeError('The error handler must be a coroutine.')

        params = inspect.signature(coro).parameters
        if len(params) != 2:
            raise TypeError('error handler must have 2 parameters')

        self.on_error = coro
        return coro

    def command(
        self,
        *,
        name: Union[str, locale_str] = MISSING,
        description: Union[str, locale_str] = MISSING,
        nsfw: bool = False,
        guild: Optional[Snowflake] = MISSING,
        guilds: Sequence[Snowflake] = MISSING,
        auto_locale_strings: bool = True,
        extras: Dict[Any, Any] = MISSING,
    ) -> Callable[[CommandCallback[Group, P, T]], Command[Group, P, T]]:
        """A decorator that creates an application command from a regular function directly under this tree.

        Parameters
        ------------
        name: Union[:class:`str`, :class:`locale_str`]
            The name of the application command. If not given, it defaults to a lower-case
            version of the callback name.
        description: Union[:class:`str`, :class:`locale_str`]
            The description of the application command. This shows up in the UI to describe
            the application command. If not given, it defaults to the first line of the docstring
            of the callback shortened to 100 characters.
        nsfw: :class:`bool`
            Whether the command is NSFW and should only work in NSFW channels. Defaults to ``False``.

            Due to a Discord limitation, this does not work on subcommands.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to add the command to. If not given or ``None`` then it
            becomes a global command instead.

            .. note ::

                Due to a Discord limitation, this keyword argument cannot be used in conjunction with
                contexts (e.g. :func:`.app_commands.allowed_contexts`) or installation types
                (e.g. :func:`.app_commands.allowed_installs`).

        guilds: List[:class:`~discord.abc.Snowflake`]
            The list of guilds to add the command to. This cannot be mixed
            with the ``guild`` parameter. If no guilds are given at all
            then it becomes a global command instead.

            .. note ::

                Due to a Discord limitation, this keyword argument cannot be used in conjunction with
                contexts (e.g. :func:`.app_commands.allowed_contexts`) or installation types
                (e.g. :func:`.app_commands.allowed_installs`).

        auto_locale_strings: :class:`bool`
            If this is set to ``True``, then all translatable strings will implicitly
            be wrapped into :class:`locale_str` rather than :class:`str`. This could
            avoid some repetition and be more ergonomic for certain defaults such
            as default command names, command descriptions, and parameter names.
            Defaults to ``True``.
        extras: :class:`dict`
            A dictionary that can be used to store extraneous data.
            The library will not touch any values or keys within this dictionary.
        """

        def decorator(func: CommandCallback[Group, P, T]) -> Command[Group, P, T]:
            if not inspect.iscoroutinefunction(func):
                raise TypeError('command function must be a coroutine function')

            if description is MISSING:
                if func.__doc__ is None:
                    desc = '…'
                else:
                    desc = _shorten(func.__doc__)
            else:
                desc = description

            command = Command(
                name=name if name is not MISSING else func.__name__,
                description=desc,
                callback=func,
                nsfw=nsfw,
                parent=None,
                auto_locale_strings=auto_locale_strings,
                extras=extras,
            )
            self.add_command(command, guild=guild, guilds=guilds)
            return command

        return decorator

    def context_menu(
        self,
        *,
        name: Union[str, locale_str] = MISSING,
        nsfw: bool = False,
        guild: Optional[Snowflake] = MISSING,
        guilds: Sequence[Snowflake] = MISSING,
        auto_locale_strings: bool = True,
        extras: Dict[Any, Any] = MISSING,
    ) -> Callable[[ContextMenuCallback], ContextMenu]:
        """A decorator that creates an application command context menu from a regular function directly under this tree.

        This function must have a signature of :class:`~discord.Interaction` as its first parameter
        and taking either a :class:`~discord.Member`, :class:`~discord.User`, or :class:`~discord.Message`,
        or a :obj:`typing.Union` of ``Member`` and ``User`` as its second parameter.

        Examples
        ---------

        .. code-block:: python3

            @app_commands.context_menu()
            async def react(interaction: discord.Interaction, message: discord.Message):
                await interaction.response.send_message('Very cool message!', ephemeral=True)

            @app_commands.context_menu()
            async def ban(interaction: discord.Interaction, user: discord.Member):
                await interaction.response.send_message(f'Should I actually ban {user}...', ephemeral=True)

        Parameters
        ------------
        name: Union[:class:`str`, :class:`locale_str`]
            The name of the context menu command. If not given, it defaults to a title-case
            version of the callback name. Note that unlike regular slash commands this can
            have spaces and upper case characters in the name.
        nsfw: :class:`bool`
            Whether the command is NSFW and should only work in NSFW channels. Defaults to ``False``.

            Due to a Discord limitation, this does not work on subcommands.
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to add the command to. If not given or ``None`` then it
            becomes a global command instead.

            .. note ::

                Due to a Discord limitation, this keyword argument cannot be used in conjunction with
                contexts (e.g. :func:`.app_commands.allowed_contexts`) or installation types
                (e.g. :func:`.app_commands.allowed_installs`).

        guilds: List[:class:`~discord.abc.Snowflake`]
            The list of guilds to add the command to. This cannot be mixed
            with the ``guild`` parameter. If no guilds are given at all
            then it becomes a global command instead.

            .. note ::

                Due to a Discord limitation, this keyword argument cannot be used in conjunction with
                contexts (e.g. :func:`.app_commands.allowed_contexts`) or installation types
                (e.g. :func:`.app_commands.allowed_installs`).

        auto_locale_strings: :class:`bool`
            If this is set to ``True``, then all translatable strings will implicitly
            be wrapped into :class:`locale_str` rather than :class:`str`. This could
            avoid some repetition and be more ergonomic for certain defaults such
            as default command names, command descriptions, and parameter names.
            Defaults to ``True``.
        extras: :class:`dict`
            A dictionary that can be used to store extraneous data.
            The library will not touch any values or keys within this dictionary.
        """

        def decorator(func: ContextMenuCallback) -> ContextMenu:
            if not inspect.iscoroutinefunction(func):
                raise TypeError('context menu function must be a coroutine function')

            actual_name = func.__name__.title() if name is MISSING else name
            context_menu = ContextMenu(
                name=actual_name,
                nsfw=nsfw,
                callback=func,
                auto_locale_strings=auto_locale_strings,
                extras=extras,
            )
            self.add_command(context_menu, guild=guild, guilds=guilds)
            return context_menu

        return decorator

    @property
    def translator(self) -> Optional[Translator]:
        """Optional[:class:`Translator`]: The translator, if any, responsible for handling translation of commands.

        To change the translator, use :meth:`set_translator`.
        """
        return self._state._translator

    async def set_translator(self, translator: Optional[Translator]) -> None:
        """|coro|

        Sets the translator to use for translating commands.

        If a translator was previously set, it will be unloaded using its
        :meth:`Translator.unload` method.

        When a translator is set, it will be loaded using its :meth:`Translator.load` method.

        Parameters
        ------------
        translator: Optional[:class:`Translator`]
            The translator to use. If ``None`` then the translator is just removed and unloaded.

        Raises
        -------
        TypeError
            The translator was not ``None`` or a :class:`Translator` instance.
        """

        if translator is not None and not isinstance(translator, Translator):
            raise TypeError(f'expected None or Translator instance, received {translator.__class__.__name__} instead')

        old_translator = self._state._translator
        if old_translator is not None:
            await old_translator.unload()

        if translator is None:
            self._state._translator = None
        else:
            await translator.load()
            self._state._translator = translator

    async def sync(self, *, guild: Optional[Snowflake] = None) -> List[AppCommand]:
        """|coro|

        Syncs the application commands to Discord.

        This also runs the translator to get the translated strings necessary for
        feeding back into Discord.

        This must be called for the application commands to show up.

        Parameters
        -----------
        guild: Optional[:class:`~discord.abc.Snowflake`]
            The guild to sync the commands to. If ``None`` then it
            syncs all global commands instead.

        Raises
        -------
        HTTPException
            Syncing the commands failed.
        CommandSyncFailure
            Syncing the commands failed due to a user related error, typically because
            the command has invalid data. This is equivalent to an HTTP status code of
            400.
        Forbidden
            The client does not have the ``applications.commands`` scope in the guild.
        MissingApplicationID
            The client does not have an application ID.
        TranslationError
            An error occurred while translating the commands.

        Returns
        --------
        List[:class:`AppCommand`]
            The application's commands that got synced.
        """

        if self.client.application_id is None:
            raise MissingApplicationID

        commands = self._get_all_commands(guild=guild)

        translator = self.translator
        if translator:
            payload = [await command.get_translated_payload(self, translator) for command in commands]
        else:
            payload = [command.to_dict(self) for command in commands]

        try:
            if guild is None:
                data = await self._http.bulk_upsert_global_commands(self.client.application_id, payload=payload)
            else:
                data = await self._http.bulk_upsert_guild_commands(self.client.application_id, guild.id, payload=payload)
        except HTTPException as e:
            if e.status == 400 and e.code == 50035:
                raise CommandSyncFailure(e, commands) from None
            raise

        self._update_command_ids(*data)
        return [AppCommand(data=d, state=self._state) for d in data]

    def _update_command_ids(self, *data: Union[ApplicationCommandInteractionData, ApplicationCommand]) -> None:
        if not self.store_app_command_ids:
            return

        for d in data:
            command_id: int = int(d['id'])
            name: str = d['name']
            guild_id: Optional[int] = _get_as_snowflake(d, 'guild_id')
            try:
                self._command_ids[guild_id][name] = command_id
            except KeyError:
                self._command_ids[guild_id] = {name: command_id}

    async def _dispatch_error(self, interaction: Interaction[ClientT], error: AppCommandError, /) -> None:
        command = interaction.command
        interaction.command_failed = True
        try:
            if isinstance(command, Command):
                await command._invoke_error_handlers(interaction, error)
        finally:
            await self.on_error(interaction, error)

    def _from_interaction(self, interaction: Interaction[ClientT]) -> None:
        async def wrapper():
            try:
                await self._call(interaction)
            except AppCommandError as e:
                await self._dispatch_error(interaction, e)

        self.client.loop.create_task(wrapper(), name='CommandTree-invoker')

    def _get_context_menu(self, data: ApplicationCommandInteractionData) -> Optional[ContextMenu]:
        name = data['name']
        guild_id = _get_as_snowflake(data, 'guild_id')
        t = data.get('type', 1)
        cmd = self._context_menus.get((name, guild_id, t))
        if cmd is None and self.fallback_to_global:
            return self._context_menus.get((name, None, t))
        return cmd

    def _get_app_command_options(
        self, data: ApplicationCommandInteractionData
    ) -> Tuple[Command[Any, ..., Any], List[ApplicationCommandInteractionDataOption]]:
        parents: List[str] = []
        name = data['name']

        command_guild_id = _get_as_snowflake(data, 'guild_id')
        if command_guild_id:
            try:
                guild_commands = self._guild_commands[command_guild_id]
            except KeyError:
                command = None if not self.fallback_to_global else self._global_commands.get(name)
            else:
                command = guild_commands.get(name)
                if command is None and self.fallback_to_global:
                    command = self._global_commands.get(name)
        else:
            command = self._global_commands.get(name)

        # If it's not found at this point then it's not gonna be found at any point
        if command is None:
            raise CommandNotFound(name, parents)

        # This could be done recursively but it'd be a bother due to the state needed
        # to be tracked above like the parents, the actual command type, and the
        # resulting options we care about
        searching = True
        options: List[ApplicationCommandInteractionDataOption] = data.get('options', [])
        while searching:
            for option in options:
                # Find subcommands
                if option.get('type', 0) in (1, 2):
                    parents.append(name)
                    name = option['name']
                    command = command._get_internal_command(name)
                    if command is None:
                        raise CommandNotFound(name, parents)
                    options = option.get('options', [])
                    break
                else:
                    searching = False
                    break
            else:
                break

        if isinstance(command, Group):
            # Right now, groups can't be invoked. This is a Discord limitation in how they
            # do slash commands. So if we're here and we have a Group rather than a Command instance
            # then something in the code is out of date from the data that Discord has.
            raise CommandSignatureMismatch(command)

        return (command, options)

    async def _call_context_menu(
        self, interaction: Interaction[ClientT], data: ApplicationCommandInteractionData, type: int
    ) -> None:
        name = data['name']
        guild_id = _get_as_snowflake(data, 'guild_id')
        ctx_menu = self._context_menus.get((name, guild_id, type))
        if ctx_menu is None and self.fallback_to_global:
            ctx_menu = self._context_menus.get((name, None, type))

        # Pre-fill the cached slot to prevent re-computation
        interaction._cs_command = ctx_menu

        if ctx_menu is None:
            raise CommandNotFound(name, [], AppCommandType(type))

        resolved = Namespace._get_resolved_items(interaction, data.get('resolved', {}))

        # This is annotated as str | int but realistically this will always be str
        target_id: Optional[Union[str, int]] = data.get('target_id')
        # Right now, the only types are message and user
        # Therefore, there's no conflict with snowflakes

        # This will always work at runtime
        key = ResolveKey.any_with(target_id)  # type: ignore
        value = resolved.get(key)
        if ctx_menu.type.value != type:
            raise CommandSignatureMismatch(ctx_menu)

        if value is None:
            raise AppCommandError('This should not happen if Discord sent well-formed data.')

        # I assume I don't have to type check here.
        try:
            await ctx_menu._invoke(interaction, value)
        except AppCommandError as e:
            if ctx_menu.on_error is not None:
                await ctx_menu.on_error(interaction, e)
            await self.on_error(interaction, e)
        else:
            self.client.dispatch('app_command_completion', interaction, ctx_menu)

    async def interaction_check(self, interaction: Interaction[ClientT], /) -> bool:
        """|coro|

        A global check to determine if an :class:`~discord.Interaction` should
        be processed by the tree.

        The default implementation returns True (all interactions are processed),
        but can be overridden if custom behaviour is desired.
        """
        return True

    async def _call(self, interaction: Interaction[ClientT]) -> None:
        if not await self.interaction_check(interaction):
            interaction.command_failed = True
            return

        data: ApplicationCommandInteractionData = interaction.data  # type: ignore
        self._update_command_ids(data)
        type = data.get('type', 1)
        if type != 1:
            # Context menu command...
            await self._call_context_menu(interaction, data, type)
            return

        command, options = self._get_app_command_options(data)

        # Pre-fill the cached slot to prevent re-computation
        interaction._cs_command = command

        # At this point options refers to the arguments of the command
        # and command refers to the class type we care about
        namespace = Namespace(interaction, data.get('resolved', {}), options)

        # Same pre-fill as above
        interaction._cs_namespace = namespace

        # Auto complete handles the namespace differently... so at this point this is where we decide where that is.
        if interaction.type is InteractionType.autocomplete:
            focused = next((opt['name'] for opt in options if opt.get('focused')), None)
            if focused is None:
                raise AppCommandError('This should not happen, but there is no focused element. This is a Discord bug.')

            try:
                await command._invoke_autocomplete(interaction, focused, namespace)
            except Exception:
                # Suppress exception since it can't be handled anyway.
                _log.exception('Ignoring exception in autocomplete for %r', command.qualified_name)

            return

        try:
            await command._invoke_with_namespace(interaction, namespace)
        except AppCommandError as e:
            interaction.command_failed = True
            await command._invoke_error_handlers(interaction, e)
            await self.on_error(interaction, e)
        else:
            if not interaction.command_failed:
                self.client.dispatch('app_command_completion', interaction, command)
