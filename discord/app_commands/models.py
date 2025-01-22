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
from datetime import datetime

from .errors import MissingApplicationID
from ..flags import AppCommandContext, AppInstallationType
from .translator import TranslationContextLocation, TranslationContext, locale_str, Translator
from ..permissions import Permissions
from ..enums import (
    AppCommandOptionType,
    AppCommandType,
    AppCommandPermissionType,
    ChannelType,
    Locale,
    try_enum,
)
from ..mixins import Hashable
from ..utils import _get_as_snowflake, parse_time, snowflake_time, MISSING
from ..object import Object
from ..role import Role
from ..member import Member

from typing import Any, Dict, Generic, List, TYPE_CHECKING, Optional, TypeVar, Union

__all__ = (
    'AppCommand',
    'AppCommandGroup',
    'AppCommandChannel',
    'AppCommandThread',
    'AppCommandPermissions',
    'GuildAppCommandPermissions',
    'Argument',
    'Choice',
    'AllChannels',
)

ChoiceT = TypeVar('ChoiceT', str, int, float, Union[str, int, float])


def is_app_command_argument_type(value: int) -> bool:
    return 11 >= value >= 3


if TYPE_CHECKING:
    from ..types.command import (
        ApplicationCommand as ApplicationCommandPayload,
        ApplicationCommandOption,
        ApplicationCommandOptionChoice,
        ApplicationCommandPermissions,
        GuildApplicationCommandPermissions,
    )
    from ..types.interactions import (
        PartialChannel,
        PartialThread,
    )
    from ..types.threads import (
        ThreadMetadata,
        ThreadArchiveDuration,
    )

    from ..abc import Snowflake
    from ..state import ConnectionState
    from ..guild import GuildChannel, Guild
    from ..channel import TextChannel
    from ..threads import Thread
    from ..user import User

    ApplicationCommandParent = Union['AppCommand', 'AppCommandGroup']


class AllChannels:
    """Represents all channels for application command permissions.

    .. versionadded:: 2.0

    Attributes
    -----------
    guild: :class:`~discord.Guild`
        The guild the application command permission is for.
    """

    __slots__ = ('guild',)

    def __init__(self, guild: Guild):
        self.guild: Guild = guild

    @property
    def id(self) -> int:
        """:class:`int`: The ID sentinel used to represent all channels. Equivalent to the guild's ID minus 1."""
        return self.guild.id - 1

    def __repr__(self) -> str:
        return f'<AllChannels guild={self.guild}>'


def _to_locale_dict(data: Dict[str, str]) -> Dict[Locale, str]:
    return {try_enum(Locale, key): value for key, value in data.items()}


class AppCommand(Hashable):
    """Represents an application command.

    In common parlance this is referred to as a "Slash Command" or a
    "Context Menu Command".

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two application commands are equal.

        .. describe:: x != y

            Checks if two application commands are not equal.

        .. describe:: hash(x)

            Returns the application command's hash.

        .. describe:: str(x)

            Returns the application command's name.

    Attributes
    -----------
    id: :class:`int`
        The application command's ID.
    application_id: :class:`int`
        The application command's application's ID.
    type: :class:`~discord.AppCommandType`
        The application command's type.
    name: :class:`str`
        The application command's name.
    description: :class:`str`
        The application command's description.
    name_localizations: Dict[:class:`~discord.Locale`, :class:`str`]
        The localised names of the application command. Used for display purposes.
    description_localizations: Dict[:class:`~discord.Locale`, :class:`str`]
        The localised descriptions of the application command. Used for display purposes.
    options: List[Union[:class:`Argument`, :class:`AppCommandGroup`]]
        A list of options.
    default_member_permissions: Optional[:class:`~discord.Permissions`]
        The default member permissions that can run this command.
    dm_permission: :class:`bool`
        A boolean that indicates whether this command can be run in direct messages.
    allowed_contexts: Optional[:class:`~discord.app_commands.AppCommandContext`]
        The contexts that this command is allowed to be used in. Overrides the ``dm_permission`` attribute.

        .. versionadded:: 2.4
    allowed_installs: Optional[:class:`~discord.app_commands.AppInstallationType`]
        The installation contexts that this command is allowed to be installed in.

        .. versionadded:: 2.4
    guild_id: Optional[:class:`int`]
        The ID of the guild this command is registered in. A value of ``None``
        denotes that it is a global command.
    nsfw: :class:`bool`
        Whether the command is NSFW and should only work in NSFW channels.
    """

    __slots__ = (
        'id',
        'type',
        'application_id',
        'name',
        'description',
        'name_localizations',
        'description_localizations',
        'guild_id',
        'options',
        'default_member_permissions',
        'dm_permission',
        'allowed_contexts',
        'allowed_installs',
        'nsfw',
        '_state',
    )

    def __init__(self, *, data: ApplicationCommandPayload, state: ConnectionState) -> None:
        self._state: ConnectionState = state
        self._from_data(data)

    def _from_data(self, data: ApplicationCommandPayload) -> None:
        self.id: int = int(data['id'])
        self.application_id: int = int(data['application_id'])
        self.name: str = data['name']
        self.description: str = data['description']
        self.guild_id: Optional[int] = _get_as_snowflake(data, 'guild_id')
        self.type: AppCommandType = try_enum(AppCommandType, data.get('type', 1))
        self.options: List[Union[Argument, AppCommandGroup]] = [
            app_command_option_factory(data=d, parent=self, state=self._state) for d in data.get('options', [])
        ]
        self.default_member_permissions: Optional[Permissions]
        permissions = data.get('default_member_permissions')
        if permissions is None:
            self.default_member_permissions = None
        else:
            self.default_member_permissions = Permissions(int(permissions))

        dm_permission = data.get('dm_permission')
        # For some reason this field can be explicit null and mean True
        if dm_permission is None:
            dm_permission = True

        self.dm_permission: bool = dm_permission

        allowed_contexts = data.get('contexts')
        if allowed_contexts is None:
            self.allowed_contexts: Optional[AppCommandContext] = None
        else:
            self.allowed_contexts = AppCommandContext._from_value(allowed_contexts)

        allowed_installs = data.get('integration_types')
        if allowed_installs is None:
            self.allowed_installs: Optional[AppInstallationType] = None
        else:
            self.allowed_installs = AppInstallationType._from_value(allowed_installs)

        self.nsfw: bool = data.get('nsfw', False)
        self.name_localizations: Dict[Locale, str] = _to_locale_dict(data.get('name_localizations') or {})
        self.description_localizations: Dict[Locale, str] = _to_locale_dict(data.get('description_localizations') or {})

    def to_dict(self) -> ApplicationCommandPayload:
        return {
            'id': self.id,
            'type': self.type.value,
            'application_id': self.application_id,
            'name': self.name,
            'description': self.description,
            'name_localizations': {str(k): v for k, v in self.name_localizations.items()},
            'description_localizations': {str(k): v for k, v in self.description_localizations.items()},
            'contexts': self.allowed_contexts.to_array() if self.allowed_contexts is not None else None,
            'integration_types': self.allowed_installs.to_array() if self.allowed_installs is not None else None,
            'options': [opt.to_dict() for opt in self.options],
        }  # type: ignore # Type checker does not understand this literal.

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id!r} name={self.name!r} type={self.type!r}>'

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention the given AppCommand."""
        return f'</{self.name}:{self.id}>'

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`~discord.Guild`]: Returns the guild this command is registered to
        if it exists.
        """
        return self._state._get_guild(self.guild_id)

    async def delete(self) -> None:
        """|coro|

        Deletes the application command.

        Raises
        -------
        NotFound
            The application command was not found.
        Forbidden
            You do not have permission to delete this application command.
        HTTPException
            Deleting the application command failed.
        MissingApplicationID
            The client does not have an application ID.
        """
        state = self._state
        if not state.application_id:
            raise MissingApplicationID

        if self.guild_id:
            await state.http.delete_guild_command(
                state.application_id,
                self.guild_id,
                self.id,
            )
        else:
            await state.http.delete_global_command(
                state.application_id,
                self.id,
            )

        tree = self._state._command_tree
        if tree:
            tree._command_ids.get(self.guild_id, {}).pop(self.name, None)

    async def edit(
        self,
        *,
        name: str = MISSING,
        description: str = MISSING,
        default_member_permissions: Optional[Permissions] = MISSING,
        dm_permission: bool = MISSING,
        options: List[Union[Argument, AppCommandGroup]] = MISSING,
    ) -> AppCommand:
        """|coro|

        Edits the application command.

        Parameters
        -----------
        name: :class:`str`
            The new name for the application command.
        description: :class:`str`
            The new description for the application command.
        default_member_permissions: Optional[:class:`~discord.Permissions`]
            The new default permissions needed to use this application command.
            Pass value of ``None`` to remove any permission requirements.
        dm_permission: :class:`bool`
            Indicates if the application command can be used in DMs.
        options: List[Union[:class:`Argument`, :class:`AppCommandGroup`]]
            List of new options for this application command.

        Raises
        -------
        NotFound
            The application command was not found.
        Forbidden
            You do not have permission to edit this application command.
        HTTPException
            Editing the application command failed.
        MissingApplicationID
            The client does not have an application ID.

        Returns
        --------
        :class:`AppCommand`
            The newly edited application command.
        """
        state = self._state
        if not state.application_id:
            raise MissingApplicationID

        payload = {}

        if name is not MISSING:
            payload['name'] = name

        if description is not MISSING:
            payload['description'] = description

        if default_member_permissions is not MISSING:
            if default_member_permissions is not None:
                payload['default_member_permissions'] = default_member_permissions.value
            else:
                payload['default_member_permissions'] = None

        if self.guild_id is None and dm_permission is not MISSING:
            payload['dm_permission'] = dm_permission

        if options is not MISSING:
            payload['options'] = [option.to_dict() for option in options]

        if not payload:
            return self

        if self.guild_id:
            data = await state.http.edit_guild_command(
                state.application_id,
                self.guild_id,
                self.id,
                payload,
            )
        else:
            data = await state.http.edit_global_command(
                state.application_id,
                self.id,
                payload,
            )

        tree = self._state._command_tree
        if tree:
            tree._update_command_ids(data)

        return AppCommand(data=data, state=state)

    async def fetch_permissions(self, guild: Snowflake) -> GuildAppCommandPermissions:
        """|coro|

        Retrieves this command's permission in the guild.

        Parameters
        -----------
        guild: :class:`~discord.abc.Snowflake`
            The guild to retrieve the permissions from.

        Raises
        -------
        Forbidden
            You do not have permission to fetch the application command's permissions.
        HTTPException
            Fetching the application command's permissions failed.
        MissingApplicationID
            The client does not have an application ID.
        NotFound
            The application command's permissions could not be found.
            This can also indicate that the permissions are synced with the guild
            (i.e. they are unchanged from the default).

        Returns
        --------
        :class:`GuildAppCommandPermissions`
            An object representing the application command's permissions in the guild.
        """
        state = self._state
        if not state.application_id:
            raise MissingApplicationID

        data = await state.http.get_application_command_permissions(
            state.application_id,
            guild.id,
            self.id,
        )
        return GuildAppCommandPermissions(data=data, state=state, command=self)


class Choice(Generic[ChoiceT]):
    """Represents an application command argument choice.

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two choices are equal.

        .. describe:: x != y

            Checks if two choices are not equal.

        .. describe:: hash(x)

            Returns the choice's hash.

    Parameters
    -----------
    name: Union[:class:`str`, :class:`locale_str`]
        The name of the choice. Used for display purposes.
        Can only be up to 100 characters.
    name_localizations: Dict[:class:`~discord.Locale`, :class:`str`]
        The localised names of the choice. Used for display purposes.
    value: Union[:class:`int`, :class:`str`, :class:`float`]
        The value of the choice. If it's a string, it can only be
        up to 100 characters long.
    """

    __slots__ = ('name', 'value', '_locale_name', 'name_localizations')

    def __init__(self, *, name: Union[str, locale_str], value: ChoiceT):
        name, locale = (name.message, name) if isinstance(name, locale_str) else (name, None)
        self.name: str = name
        self._locale_name: Optional[locale_str] = locale
        self.value: ChoiceT = value
        self.name_localizations: Dict[Locale, str] = {}

    @classmethod
    def from_dict(cls, data: ApplicationCommandOptionChoice) -> Choice[ChoiceT]:
        self = cls.__new__(cls)
        self.name = data['name']
        self.value = data['value']  # type: ignore # This seems to break every other pyright release
        self.name_localizations = _to_locale_dict(data.get('name_localizations') or {})
        return self

    def __eq__(self, o: object) -> bool:
        return isinstance(o, Choice) and self.name == o.name and self.value == o.value

    def __hash__(self) -> int:
        return hash((self.name, self.value))

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name={self.name!r}, value={self.value!r})'

    @property
    def _option_type(self) -> AppCommandOptionType:
        if isinstance(self.value, int):
            return AppCommandOptionType.integer
        elif isinstance(self.value, float):
            return AppCommandOptionType.number
        elif isinstance(self.value, str):
            return AppCommandOptionType.string
        else:
            raise TypeError(
                f'invalid Choice value type given, expected int, str, or float but received {self.value.__class__.__name__}'
            )

    async def get_translated_payload(self, translator: Translator) -> Dict[str, Any]:
        base = self.to_dict()
        name_localizations: Dict[str, str] = {}
        context = TranslationContext(location=TranslationContextLocation.choice_name, data=self)
        if self._locale_name:
            for locale in Locale:
                translation = await translator._checked_translate(self._locale_name, locale, context)
                if translation is not None:
                    name_localizations[locale.value] = translation

        if name_localizations:
            base['name_localizations'] = name_localizations

        return base

    async def get_translated_payload_for_locale(self, translator: Translator, locale: Locale) -> Dict[str, Any]:
        base = self.to_dict()
        if self._locale_name:
            context = TranslationContext(location=TranslationContextLocation.choice_name, data=self)
            translation = await translator._checked_translate(self._locale_name, locale, context)
            if translation is not None:
                base['name'] = translation

        return base

    def to_dict(self) -> Dict[str, Any]:
        base = {
            'name': self.name,
            'value': self.value,
        }
        if self.name_localizations:
            base['name_localizations'] = {str(k): v for k, v in self.name_localizations.items()}
        return base


class AppCommandChannel(Hashable):
    """Represents an application command partially resolved channel object.

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns the channel's name.

    Attributes
    -----------
    id: :class:`int`
        The ID of the channel.
    type: :class:`~discord.ChannelType`
        The type of channel.
    name: :class:`str`
        The name of the channel.
    permissions: :class:`~discord.Permissions`
        The resolved permissions of the user who invoked
        the application command in that channel.
    guild_id: :class:`int`
        The guild ID this channel belongs to.
    """

    __slots__ = (
        'id',
        'type',
        'name',
        'permissions',
        'guild_id',
        '_state',
    )

    def __init__(
        self,
        *,
        state: ConnectionState,
        data: PartialChannel,
        guild_id: int,
    ):
        self._state: ConnectionState = state
        self.guild_id: int = guild_id
        self.id: int = int(data['id'])
        self.type: ChannelType = try_enum(ChannelType, data['type'])
        self.name: str = data['name']
        self.permissions: Permissions = Permissions(int(data['permissions']))

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id!r} name={self.name!r} type={self.type!r}>'

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`~discord.Guild`]: The channel's guild, from cache, if found."""
        return self._state._get_guild(self.guild_id)

    def resolve(self) -> Optional[GuildChannel]:
        """Resolves the application command channel to the appropriate channel
        from cache if found.

        Returns
        --------
        Optional[:class:`.abc.GuildChannel`]
            The resolved guild channel or ``None`` if not found in cache.
        """
        guild = self._state._get_guild(self.guild_id)
        if guild is not None:
            return guild.get_channel(self.id)
        return None

    async def fetch(self) -> GuildChannel:
        """|coro|

        Fetches the partial channel to a full :class:`.abc.GuildChannel`.

        Raises
        --------
        NotFound
            The channel was not found.
        Forbidden
            You do not have the permissions required to get a channel.
        HTTPException
            Retrieving the channel failed.

        Returns
        --------
        :class:`.abc.GuildChannel`
            The full channel.
        """
        client = self._state._get_client()
        return await client.fetch_channel(self.id)  # type: ignore # This is explicit narrowing

    @property
    def mention(self) -> str:
        """:class:`str`: The string that allows you to mention the channel."""
        return f'<#{self.id}>'

    @property
    def created_at(self) -> datetime:
        """:class:`datetime.datetime`: An aware timestamp of when this channel was created in UTC."""
        return snowflake_time(self.id)


class AppCommandThread(Hashable):
    """Represents an application command partially resolved thread object.

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two thread are equal.

        .. describe:: x != y

            Checks if two thread are not equal.

        .. describe:: hash(x)

            Returns the thread's hash.

        .. describe:: str(x)

            Returns the thread's name.

    Attributes
    -----------
    id: :class:`int`
        The ID of the thread.
    type: :class:`~discord.ChannelType`
        The type of thread.
    name: :class:`str`
        The name of the thread.
    parent_id: :class:`int`
        The parent text channel ID this thread belongs to.
    permissions: :class:`~discord.Permissions`
        The resolved permissions of the user who invoked
        the application command in that thread.
    guild_id: :class:`int`
        The guild ID this thread belongs to.
    archived: :class:`bool`
        Whether the thread is archived.
    locked: :class:`bool`
        Whether the thread is locked.
    invitable: :class:`bool`
        Whether non-moderators can add other non-moderators to this thread.
        This is always ``True`` for public threads.
    archiver_id: Optional[:class:`int`]
        The user's ID that archived this thread.
    auto_archive_duration: :class:`int`
        The duration in minutes until the thread is automatically hidden from the channel list.
        Usually a value of 60, 1440, 4320 and 10080.
    archive_timestamp: :class:`datetime.datetime`
        An aware timestamp of when the thread's archived status was last updated in UTC.
    """

    __slots__ = (
        'id',
        'type',
        'name',
        'permissions',
        'guild_id',
        'parent_id',
        'archived',
        'archiver_id',
        'auto_archive_duration',
        'archive_timestamp',
        'locked',
        'invitable',
        '_created_at',
        '_state',
    )

    def __init__(
        self,
        *,
        state: ConnectionState,
        data: PartialThread,
        guild_id: int,
    ):
        self._state: ConnectionState = state
        self.guild_id: int = guild_id
        self.id: int = int(data['id'])
        self.parent_id: int = int(data['parent_id'])
        self.type: ChannelType = try_enum(ChannelType, data['type'])
        self.name: str = data['name']
        self.permissions: Permissions = Permissions(int(data['permissions']))
        self._unroll_metadata(data['thread_metadata'])

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id!r} name={self.name!r} archived={self.archived} type={self.type!r}>'

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`~discord.Guild`]: The channel's guild, from cache, if found."""
        return self._state._get_guild(self.guild_id)

    def _unroll_metadata(self, data: ThreadMetadata) -> None:
        self.archived: bool = data['archived']
        self.archiver_id: Optional[int] = _get_as_snowflake(data, 'archiver_id')
        self.auto_archive_duration: ThreadArchiveDuration = data['auto_archive_duration']
        self.archive_timestamp: datetime = parse_time(data['archive_timestamp'])
        self.locked: bool = data.get('locked', False)
        self.invitable: bool = data.get('invitable', True)
        self._created_at: Optional[datetime] = parse_time(data.get('create_timestamp'))

    @property
    def parent(self) -> Optional[TextChannel]:
        """Optional[:class:`~discord.TextChannel`]: The parent channel this thread belongs to."""
        return self.guild.get_channel(self.parent_id)  # type: ignore

    @property
    def mention(self) -> str:
        """:class:`str`: The string that allows you to mention the thread."""
        return f'<#{self.id}>'

    @property
    def created_at(self) -> Optional[datetime]:
        """An aware timestamp of when the thread was created in UTC.

        .. note::

            This timestamp only exists for threads created after 9 January 2022, otherwise returns ``None``.
        """
        return self._created_at

    def resolve(self) -> Optional[Thread]:
        """Resolves the application command channel to the appropriate channel
        from cache if found.

        Returns
        --------
        Optional[:class:`.abc.GuildChannel`]
            The resolved guild channel or ``None`` if not found in cache.
        """
        guild = self._state._get_guild(self.guild_id)
        if guild is not None:
            return guild.get_thread(self.id)
        return None

    async def fetch(self) -> Thread:
        """|coro|

        Fetches the partial channel to a full :class:`~discord.Thread`.

        Raises
        --------
        NotFound
            The thread was not found.
        Forbidden
            You do not have the permissions required to get a thread.
        HTTPException
            Retrieving the thread failed.

        Returns
        --------
        :class:`~discord.Thread`
            The full thread.
        """
        client = self._state._get_client()
        return await client.fetch_channel(self.id)  # type: ignore # This is explicit narrowing


class Argument:
    """Represents an application command argument.

    .. versionadded:: 2.0

    Attributes
    ------------
    type: :class:`~discord.AppCommandOptionType`
        The type of argument.
    name: :class:`str`
        The name of the argument.
    description: :class:`str`
        The description of the argument.
    name_localizations: Dict[:class:`~discord.Locale`, :class:`str`]
        The localised names of the argument. Used for display purposes.
    description_localizations: Dict[:class:`~discord.Locale`, :class:`str`]
        The localised descriptions of the argument. Used for display purposes.
    required: :class:`bool`
        Whether the argument is required.
    choices: List[:class:`Choice`]
        A list of choices for the command to choose from for this argument.
    parent: Union[:class:`AppCommand`, :class:`AppCommandGroup`]
        The parent application command that has this argument.
    channel_types: List[:class:`~discord.ChannelType`]
        The channel types that are allowed for this parameter.
    min_value: Optional[Union[:class:`int`, :class:`float`]]
        The minimum supported value for this parameter.
    max_value: Optional[Union[:class:`int`, :class:`float`]]
        The maximum supported value for this parameter.
    min_length: Optional[:class:`int`]
        The minimum allowed length for this parameter.
    max_length: Optional[:class:`int`]
        The maximum allowed length for this parameter.
    autocomplete: :class:`bool`
        Whether the argument has autocomplete.
    """

    __slots__ = (
        'type',
        'name',
        'description',
        'name_localizations',
        'description_localizations',
        'required',
        'choices',
        'channel_types',
        'min_value',
        'max_value',
        'min_length',
        'max_length',
        'autocomplete',
        'parent',
        '_state',
    )

    def __init__(
        self, *, parent: ApplicationCommandParent, data: ApplicationCommandOption, state: Optional[ConnectionState] = None
    ) -> None:
        self._state: Optional[ConnectionState] = state
        self.parent: ApplicationCommandParent = parent
        self._from_data(data)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} name={self.name!r} type={self.type!r} required={self.required}>'

    def _from_data(self, data: ApplicationCommandOption) -> None:
        self.type: AppCommandOptionType = try_enum(AppCommandOptionType, data['type'])
        self.name: str = data['name']
        self.description: str = data['description']
        self.required: bool = data.get('required', False)
        self.min_value: Optional[Union[int, float]] = data.get('min_value')
        self.max_value: Optional[Union[int, float]] = data.get('max_value')
        self.min_length: Optional[int] = data.get('min_length')
        self.max_length: Optional[int] = data.get('max_length')
        self.autocomplete: bool = data.get('autocomplete', False)
        self.channel_types: List[ChannelType] = [try_enum(ChannelType, d) for d in data.get('channel_types', [])]
        self.choices: List[Choice[Union[int, float, str]]] = [Choice.from_dict(d) for d in data.get('choices', [])]
        self.name_localizations: Dict[Locale, str] = _to_locale_dict(data.get('name_localizations') or {})
        self.description_localizations: Dict[Locale, str] = _to_locale_dict(data.get('description_localizations') or {})

    def to_dict(self) -> ApplicationCommandOption:
        return {
            'name': self.name,
            'type': self.type.value,
            'description': self.description,
            'required': self.required,
            'choices': [choice.to_dict() for choice in self.choices],
            'channel_types': [channel_type.value for channel_type in self.channel_types],
            'min_value': self.min_value,
            'max_value': self.max_value,
            'min_length': self.min_length,
            'max_length': self.max_length,
            'autocomplete': self.autocomplete,
            'options': [],
            'name_localizations': {str(k): v for k, v in self.name_localizations.items()},
            'description_localizations': {str(k): v for k, v in self.description_localizations.items()},
        }  # type: ignore # Type checker does not understand this literal.


class AppCommandGroup:
    """Represents an application command subcommand.

    .. versionadded:: 2.0

    Attributes
    ------------
    type: :class:`~discord.AppCommandOptionType`
        The type of subcommand.
    name: :class:`str`
        The name of the subcommand.
    description: :class:`str`
        The description of the subcommand.
    name_localizations: Dict[:class:`~discord.Locale`, :class:`str`]
        The localised names of the subcommand. Used for display purposes.
    description_localizations: Dict[:class:`~discord.Locale`, :class:`str`]
        The localised descriptions of the subcommand. Used for display purposes.
    options: List[Union[:class:`Argument`, :class:`AppCommandGroup`]]
        A list of options.
    parent: Union[:class:`AppCommand`, :class:`AppCommandGroup`]
        The parent application command.
    """

    __slots__ = (
        'type',
        'name',
        'description',
        'name_localizations',
        'description_localizations',
        'options',
        'parent',
        '_state',
    )

    def __init__(
        self, *, parent: ApplicationCommandParent, data: ApplicationCommandOption, state: Optional[ConnectionState] = None
    ) -> None:
        self.parent: ApplicationCommandParent = parent
        self._state: Optional[ConnectionState] = state
        self._from_data(data)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} name={self.name!r} type={self.type!r}>'

    @property
    def qualified_name(self) -> str:
        """:class:`str`: Returns the fully qualified command name.

        The qualified name includes the parent name as well. For example,
        in a command like ``/foo bar`` the qualified name is ``foo bar``.
        """
        # A B C
        #     ^ self
        #   ^ parent
        # ^ grandparent
        names = [self.name, self.parent.name]
        if isinstance(self.parent, AppCommandGroup):
            names.append(self.parent.parent.name)

        return ' '.join(reversed(names))

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention the given AppCommandGroup."""
        if isinstance(self.parent, AppCommand):
            base_command = self.parent
        else:
            base_command = self.parent.parent
        return f'</{self.qualified_name}:{base_command.id}>'  # type: ignore

    def _from_data(self, data: ApplicationCommandOption) -> None:
        self.type: AppCommandOptionType = try_enum(AppCommandOptionType, data['type'])
        self.name: str = data['name']
        self.description: str = data['description']
        self.options: List[Union[Argument, AppCommandGroup]] = [
            app_command_option_factory(data=d, parent=self, state=self._state) for d in data.get('options', [])
        ]
        self.name_localizations: Dict[Locale, str] = _to_locale_dict(data.get('name_localizations') or {})
        self.description_localizations: Dict[Locale, str] = _to_locale_dict(data.get('description_localizations') or {})

    def to_dict(self) -> 'ApplicationCommandOption':
        return {
            'name': self.name,
            'type': self.type.value,
            'description': self.description,
            'options': [arg.to_dict() for arg in self.options],
            'name_localizations': {str(k): v for k, v in self.name_localizations.items()},
            'description_localizations': {str(k): v for k, v in self.description_localizations.items()},
        }  # type: ignore # Type checker does not understand this literal.


class AppCommandPermissions:
    """Represents the permissions for an application command.

    .. versionadded:: 2.0

    Attributes
    -----------
    guild: :class:`~discord.Guild`
        The guild associated with this permission.
    id: :class:`int`
        The ID of the permission target, such as a role, channel, or guild.
        The special ``guild_id - 1`` sentinel is used to represent "all channels".
    target: Any
        The role, user, or channel associated with this permission. This could also be the :class:`AllChannels` sentinel type.
        Falls back to :class:`~discord.Object` if the target could not be found in the cache.
    type: :class:`.AppCommandPermissionType`
        The type of permission.
    permission: :class:`bool`
        The permission value. ``True`` for allow, ``False`` for deny.
    """

    __slots__ = ('id', 'type', 'permission', 'target', 'guild', '_state')

    def __init__(self, *, data: ApplicationCommandPermissions, guild: Guild, state: ConnectionState) -> None:
        self._state: ConnectionState = state
        self.guild: Guild = guild

        self.id: int = int(data['id'])
        self.type: AppCommandPermissionType = try_enum(AppCommandPermissionType, data['type'])
        self.permission: bool = data['permission']

        _object = None
        _type = MISSING

        if self.type is AppCommandPermissionType.user:
            _object = guild.get_member(self.id) or self._state.get_user(self.id)
            _type = Member
        elif self.type is AppCommandPermissionType.channel:
            if self.id == (guild.id - 1):
                _object = AllChannels(guild)
            else:
                _object = guild.get_channel(self.id)
        elif self.type is AppCommandPermissionType.role:
            _object = guild.get_role(self.id)
            _type = Role

        if _object is None:
            _object = Object(id=self.id, type=_type)

        self.target: Union[Object, User, Member, Role, AllChannels, GuildChannel] = _object

    def to_dict(self) -> ApplicationCommandPermissions:
        return {
            'id': self.target.id,
            'type': self.type.value,
            'permission': self.permission,
        }


class GuildAppCommandPermissions:
    """Represents the permissions for an application command in a guild.

    .. versionadded:: 2.0

    Attributes
    -----------
    application_id: :class:`int`
        The application ID.
    command: :class:`.AppCommand`
        The application command associated with the permissions.
    id: :class:`int`
        ID of the command or the application ID.
        When this is the application ID instead of a command ID,
        the permissions apply to all commands that do not contain explicit overwrites.
    guild_id: :class:`int`
        The guild ID associated with the permissions.
    permissions: List[:class:`AppCommandPermissions`]
       The permissions, this is a max of 100.
    """

    __slots__ = ('id', 'application_id', 'command', 'guild_id', 'permissions', '_state')

    def __init__(self, *, data: GuildApplicationCommandPermissions, state: ConnectionState, command: AppCommand) -> None:
        self._state: ConnectionState = state
        self.command: AppCommand = command

        self.id: int = int(data['id'])
        self.application_id: int = int(data['application_id'])
        self.guild_id: int = int(data['guild_id'])
        guild = self.guild
        self.permissions: List[AppCommandPermissions] = [
            AppCommandPermissions(data=value, guild=guild, state=self._state) for value in data['permissions']
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {'permissions': [p.to_dict() for p in self.permissions]}

    @property
    def guild(self) -> Guild:
        """:class:`~discord.Guild`: The guild associated with the permissions."""
        return self._state._get_or_create_unavailable_guild(self.guild_id)


def app_command_option_factory(
    parent: ApplicationCommandParent, data: ApplicationCommandOption, *, state: Optional[ConnectionState] = None
) -> Union[Argument, AppCommandGroup]:
    if is_app_command_argument_type(data['type']):
        return Argument(parent=parent, data=data, state=state)
    else:
        return AppCommandGroup(parent=parent, data=data, state=state)
