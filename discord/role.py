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
from typing import Any, Dict, List, Optional, Union, overload, TYPE_CHECKING

from .asset import Asset
from .permissions import Permissions
from .colour import Colour
from .mixins import Hashable
from .utils import snowflake_time, _bytes_to_base64_data, _get_as_snowflake, MISSING
from .flags import RoleFlags

__all__ = (
    'RoleTags',
    'Role',
)

if TYPE_CHECKING:
    import datetime
    from .types.role import (
        Role as RolePayload,
        RoleTags as RoleTagPayload,
    )
    from .types.guild import RolePositionUpdate
    from .guild import Guild
    from .member import Member
    from .state import ConnectionState


class RoleTags:
    """Represents tags on a role.

    A role tag is a piece of extra information attached to a managed role
    that gives it context for the reason the role is managed.

    While this can be accessed, a useful interface is also provided in the
    :class:`Role` and :class:`Guild` classes as well.

    .. versionadded:: 1.6

    Attributes
    ------------
    bot_id: Optional[:class:`int`]
        The bot's user ID that manages this role.
    integration_id: Optional[:class:`int`]
        The integration ID that manages the role.
    subscription_listing_id: Optional[:class:`int`]
        The ID of this role's subscription SKU and listing.

        .. versionadded:: 2.2
    """

    __slots__ = (
        'bot_id',
        'integration_id',
        '_premium_subscriber',
        '_available_for_purchase',
        'subscription_listing_id',
        '_guild_connections',
    )

    def __init__(self, data: RoleTagPayload):
        self.bot_id: Optional[int] = _get_as_snowflake(data, 'bot_id')
        self.integration_id: Optional[int] = _get_as_snowflake(data, 'integration_id')
        self.subscription_listing_id: Optional[int] = _get_as_snowflake(data, 'subscription_listing_id')

        # NOTE: The API returns "null" for this if it's valid, which corresponds to None.
        # This is different from other fields where "null" means "not there".
        # So in this case, a value of None is the same as True.
        # Which means we would need a different sentinel.
        self._premium_subscriber: bool = data.get('premium_subscriber', MISSING) is None
        self._available_for_purchase: bool = data.get('available_for_purchase', MISSING) is None
        self._guild_connections: bool = data.get('guild_connections', MISSING) is None

    def is_bot_managed(self) -> bool:
        """:class:`bool`: Whether the role is associated with a bot."""
        return self.bot_id is not None

    def is_premium_subscriber(self) -> bool:
        """:class:`bool`: Whether the role is the premium subscriber, AKA "boost", role for the guild."""
        return self._premium_subscriber

    def is_integration(self) -> bool:
        """:class:`bool`: Whether the role is managed by an integration."""
        return self.integration_id is not None

    def is_available_for_purchase(self) -> bool:
        """:class:`bool`: Whether the role is available for purchase.

        .. versionadded:: 2.2
        """
        return self._available_for_purchase

    def is_guild_connection(self) -> bool:
        """:class:`bool`: Whether the role is a guild's linked role.

        .. versionadded:: 2.2
        """
        return self._guild_connections

    def __repr__(self) -> str:
        return (
            f'<RoleTags bot_id={self.bot_id} integration_id={self.integration_id} '
            f'premium_subscriber={self.is_premium_subscriber()}>'
        )


class Role(Hashable):
    """Represents a Discord role in a :class:`Guild`.

    .. container:: operations

        .. describe:: x == y

            Checks if two roles are equal.

        .. describe:: x != y

            Checks if two roles are not equal.

        .. describe:: x > y

            Checks if a role is higher than another in the hierarchy.

        .. describe:: x < y

            Checks if a role is lower than another in the hierarchy.

        .. describe:: x >= y

            Checks if a role is higher or equal to another in the hierarchy.

        .. describe:: x <= y

            Checks if a role is lower or equal to another in the hierarchy.

        .. describe:: hash(x)

            Return the role's hash.

        .. describe:: str(x)

            Returns the role's name.

    Attributes
    ----------
    id: :class:`int`
        The ID for the role.
    name: :class:`str`
        The name of the role.
    guild: :class:`Guild`
        The guild the role belongs to.
    hoist: :class:`bool`
         Indicates if the role will be displayed separately from other members.
    position: :class:`int`
        The position of the role. This number is usually positive. The bottom
        role has a position of 0.

        .. warning::

            Multiple roles can have the same position number. As a consequence
            of this, comparing via role position is prone to subtle bugs if
            checking for role hierarchy. The recommended and correct way to
            compare for roles in the hierarchy is using the comparison
            operators on the role objects themselves.

    unicode_emoji: Optional[:class:`str`]
        The role's unicode emoji, if available.

        .. note::

            If :attr:`icon` is not ``None``, it is displayed as role icon
            instead of the unicode emoji under this attribute.

            If you want the icon that a role has displayed, consider using :attr:`display_icon`.

        .. versionadded:: 2.0

    managed: :class:`bool`
        Indicates if the role is managed by the guild through some form of
        integrations such as Twitch.
    mentionable: :class:`bool`
        Indicates if the role can be mentioned by users.
    tags: Optional[:class:`RoleTags`]
        The role tags associated with this role.
    """

    __slots__ = (
        'id',
        'name',
        '_permissions',
        '_colour',
        'position',
        '_icon',
        'unicode_emoji',
        'managed',
        'mentionable',
        'hoist',
        'guild',
        'tags',
        '_flags',
        '_state',
    )

    def __init__(self, *, guild: Guild, state: ConnectionState, data: RolePayload):
        self.guild: Guild = guild
        self._state: ConnectionState = state
        self.id: int = int(data['id'])
        self._update(data)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<Role id={self.id} name={self.name!r}>'

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Role) or not isinstance(self, Role):
            return NotImplemented

        if self.guild != other.guild:
            raise RuntimeError('cannot compare roles from two different guilds.')

        # the @everyone role is always the lowest role in hierarchy
        guild_id = self.guild.id
        if self.id == guild_id:
            # everyone_role < everyone_role -> False
            return other.id != guild_id

        if self.position < other.position:
            return True

        if self.position == other.position:
            return self.id > other.id

        return False

    def __le__(self, other: Any) -> bool:
        r = Role.__lt__(other, self)
        if r is NotImplemented:
            return NotImplemented
        return not r

    def __gt__(self, other: Any) -> bool:
        return Role.__lt__(other, self)

    def __ge__(self, other: object) -> bool:
        r = Role.__lt__(self, other)
        if r is NotImplemented:
            return NotImplemented
        return not r

    def _update(self, data: RolePayload):
        self.name: str = data['name']
        self._permissions: int = int(data.get('permissions', 0))
        self.position: int = data.get('position', 0)
        self._colour: int = data.get('color', 0)
        self.hoist: bool = data.get('hoist', False)
        self._icon: Optional[str] = data.get('icon')
        self.unicode_emoji: Optional[str] = data.get('unicode_emoji')
        self.managed: bool = data.get('managed', False)
        self.mentionable: bool = data.get('mentionable', False)
        self.tags: Optional[RoleTags]
        self._flags: int = data.get('flags', 0)

        try:
            self.tags = RoleTags(data['tags'])
        except KeyError:
            self.tags = None

    def is_default(self) -> bool:
        """:class:`bool`: Checks if the role is the default role."""
        return self.guild.id == self.id

    def is_bot_managed(self) -> bool:
        """:class:`bool`: Whether the role is associated with a bot.

        .. versionadded:: 1.6
        """
        return self.tags is not None and self.tags.is_bot_managed()

    def is_premium_subscriber(self) -> bool:
        """:class:`bool`: Whether the role is the premium subscriber, AKA "boost", role for the guild.

        .. versionadded:: 1.6
        """
        return self.tags is not None and self.tags.is_premium_subscriber()

    def is_integration(self) -> bool:
        """:class:`bool`: Whether the role is managed by an integration.

        .. versionadded:: 1.6
        """
        return self.tags is not None and self.tags.is_integration()

    def is_assignable(self) -> bool:
        """:class:`bool`: Whether the role is able to be assigned or removed by the bot.

        .. versionadded:: 2.0
        """
        me = self.guild.me
        return not self.is_default() and not self.managed and (me.top_role > self or me.id == self.guild.owner_id)

    @property
    def permissions(self) -> Permissions:
        """:class:`Permissions`: Returns the role's permissions."""
        return Permissions(self._permissions)

    @property
    def colour(self) -> Colour:
        """:class:`Colour`: Returns the role colour. An alias exists under ``color``."""
        return Colour(self._colour)

    @property
    def color(self) -> Colour:
        """:class:`Colour`: Returns the role color. An alias exists under ``colour``."""
        return self.colour

    @property
    def icon(self) -> Optional[Asset]:
        """Optional[:class:`.Asset`]: Returns the role's icon asset, if available.

        .. note::
            If this is ``None``, the role might instead have unicode emoji as its icon
            if :attr:`unicode_emoji` is not ``None``.

            If you want the icon that a role has displayed, consider using :attr:`display_icon`.

        .. versionadded:: 2.0
        """
        if self._icon is None:
            return None
        return Asset._from_icon(self._state, self.id, self._icon, path='role')

    @property
    def display_icon(self) -> Optional[Union[Asset, str]]:
        """Optional[Union[:class:`.Asset`, :class:`str`]]: Returns the role's display icon, if available.

        .. versionadded:: 2.0
        """
        return self.icon or self.unicode_emoji

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the role's creation time in UTC."""
        return snowflake_time(self.id)

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention a role."""
        return f'<@&{self.id}>'

    @property
    def members(self) -> List[Member]:
        """List[:class:`Member`]: Returns all the members with this role."""
        all_members = list(self.guild._members.values())
        if self.is_default():
            return all_members

        role_id = self.id
        return [member for member in all_members if member._roles.has(role_id)]

    @property
    def flags(self) -> RoleFlags:
        """:class:`RoleFlags`: Returns the role's flags.

        .. versionadded:: 2.4
        """
        return RoleFlags._from_value(self._flags)

    async def _move(self, position: int, reason: Optional[str]) -> None:
        if position <= 0:
            raise ValueError("Cannot move role to position 0 or below")

        if self.is_default():
            raise ValueError("Cannot move default role")

        if self.position == position:
            return  # Save discord the extra request.

        http = self._state.http

        change_range = range(min(self.position, position), max(self.position, position) + 1)
        roles = [r.id for r in self.guild.roles[1:] if r.position in change_range and r.id != self.id]

        if self.position > position:
            roles.insert(0, self.id)
        else:
            roles.append(self.id)

        payload: List[RolePositionUpdate] = [{"id": z[0], "position": z[1]} for z in zip(roles, change_range)]
        await http.move_role_position(self.guild.id, payload, reason=reason)

    async def edit(
        self,
        *,
        name: str = MISSING,
        permissions: Permissions = MISSING,
        colour: Union[Colour, int] = MISSING,
        color: Union[Colour, int] = MISSING,
        hoist: bool = MISSING,
        display_icon: Optional[Union[bytes, str]] = MISSING,
        mentionable: bool = MISSING,
        position: int = MISSING,
        reason: Optional[str] = MISSING,
    ) -> Optional[Role]:
        """|coro|

        Edits the role.

        You must have :attr:`~Permissions.manage_roles` to do this.

        All fields are optional.

        .. versionchanged:: 1.4
            Can now pass ``int`` to ``colour`` keyword-only parameter.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited role is returned instead.

        .. versionadded:: 2.0
            The ``display_icon`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        -----------
        name: :class:`str`
            The new role name to change to.
        permissions: :class:`Permissions`
            The new permissions to change to.
        colour: Union[:class:`Colour`, :class:`int`]
            The new colour to change to. (aliased to color as well)
        hoist: :class:`bool`
            Indicates if the role should be shown separately in the member list.
        display_icon: Optional[Union[:class:`bytes`, :class:`str`]]
            A :term:`py:bytes-like object` representing the icon
            or :class:`str` representing unicode emoji that should be used as a role icon.
            Could be ``None`` to denote removal of the icon.
            Only PNG/JPEG is supported.
            This is only available to guilds that contain ``ROLE_ICONS`` in :attr:`Guild.features`.
        mentionable: :class:`bool`
            Indicates if the role should be mentionable by others.
        position: :class:`int`
            The new role's position. This must be below your top role's
            position or it will fail.
        reason: Optional[:class:`str`]
            The reason for editing this role. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permissions to change the role.
        HTTPException
            Editing the role failed.
        ValueError
            An invalid position was given or the default
            role was asked to be moved.

        Returns
        --------
        :class:`Role`
            The newly edited role.
        """
        if position is not MISSING:
            await self._move(position, reason=reason)

        payload: Dict[str, Any] = {}
        if color is not MISSING:
            colour = color

        if colour is not MISSING:
            if isinstance(colour, int):
                payload['color'] = colour
            else:
                payload['color'] = colour.value

        if name is not MISSING:
            payload['name'] = name

        if permissions is not MISSING:
            payload['permissions'] = permissions.value

        if hoist is not MISSING:
            payload['hoist'] = hoist

        if display_icon is not MISSING:
            payload['icon'] = None
            payload['unicode_emoji'] = None
            if isinstance(display_icon, bytes):
                payload['icon'] = _bytes_to_base64_data(display_icon)
            else:
                payload['unicode_emoji'] = display_icon

        if mentionable is not MISSING:
            payload['mentionable'] = mentionable

        data = await self._state.http.edit_role(self.guild.id, self.id, reason=reason, **payload)
        return Role(guild=self.guild, data=data, state=self._state)

    @overload
    async def move(self, *, beginning: bool, offset: int = ..., reason: Optional[str] = ...):
        ...

    @overload
    async def move(self, *, end: bool, offset: int = ..., reason: Optional[str] = ...):
        ...

    @overload
    async def move(self, *, above: Role, offset: int = ..., reason: Optional[str] = ...):
        ...

    @overload
    async def move(self, *, below: Role, offset: int = ..., reason: Optional[str] = ...):
        ...

    async def move(
        self,
        *,
        beginning: Optional[bool] = None,
        end: Optional[bool] = None,
        above: Optional[Role] = None,
        below: Optional[Role] = None,
        offset: int = 0,
        reason: Optional[str] = None,
    ):
        """|coro|

        A rich interface to help move a role relative to other roles.

        You must have :attr:`~discord.Permissions.manage_roles` to do this,
        and you cannot move roles above the client's top role in the guild.

        .. versionadded:: 2.5

        Parameters
        -----------
        beginning: bool
            Whether to move this at the beginning of the role list, above the default role.
            This is mutually exclusive with `end`, `above`, and `below`.
        end: bool
            Whether to move this at the end of the role list.
            This is mutually exclusive with `beginning`, `above`, and `below`.
        above: :class:`Role`
            The role that should be above our current role.
            This mutually exclusive with `beginning`, `end`, and `below`.
        below: :class:`Role`
            The role that should be below our current role.
            This mutually exclusive with `beginning`, `end`, and `above`.
        offset: int
            The number of roles to offset the move by. For example,
            an offset of ``2`` with ``beginning=True`` would move
            it 2 above the beginning. A positive number moves it above
            while a negative number moves it below. Note that this
            number is relative and computed after the ``beginning``,
            ``end``, ``before``, and ``after`` parameters.
        reason: Optional[:class:`str`]
            The reason for editing this role. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You cannot move the role there, or lack permissions to do so.
        HTTPException
            Moving the role failed.
        TypeError
            A bad mix of arguments were passed.
        ValueError
            An invalid role was passed.

        Returns
        --------
        List[:class:`Role`]
            A list of all the roles in the guild.
        """
        if sum(bool(a) for a in (beginning, end, above, below)) > 1:
            raise TypeError('Only one of [above, below, end, end] can be used.')

        target = above or below
        if target:
            if target not in self.guild.roles:
                raise ValueError("Target role is from a different guild")
            if above == self.guild.default_role:
                raise ValueError("Role cannot be moved below the default role")
            if self == target:
                raise ValueError("Target role cannot be itself")

        _guild_roles = self.guild.roles
        roles = [r for r in _guild_roles if r != self]
        if beginning:
            index = 1
        elif end:
            index = len(roles)
        elif above in roles:
            index = roles.index(above)
        elif below in roles:
            index = roles.index(below) + 1
        else:
            index = _guild_roles.index(self)
        roles.insert(max((index + offset), 1), self)

        payload: List[RolePositionUpdate] = [{"id": role.id, "position": idx} for idx, role in enumerate(roles)]
        await self._state.http.move_role_position(self.guild.id, payload, reason=reason)

    async def delete(self, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the role.

        You must have :attr:`~Permissions.manage_roles` to do this.

        Parameters
        -----------
        reason: Optional[:class:`str`]
            The reason for deleting this role. Shows up on the audit log.

        Raises
        --------
        Forbidden
            You do not have permissions to delete the role.
        HTTPException
            Deleting the role failed.
        """

        await self._state.http.delete_role(self.guild.id, self.id, reason=reason)
