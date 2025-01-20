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

from typing import TYPE_CHECKING, Dict, List, Optional

from . import utils
from .enums import ClanBannerStyle, ClanPlayStyle, try_enum, ClanBadgeType
from .mixins import Hashable
from .object import Object
from .colour import Colour
from .asset import Asset

if TYPE_CHECKING:

    from .guild import Guild
    from .state import ConnectionState

    from .types.clan import (
        PartialClan as PartialClanPayload,
        Clan as ClanPayload,
        UserClan as UserClanPayload,
    )

__all__ = ('UserClan', 'PartialClan', 'Clan')


class UserClan:
    """Represents a partial clan accessible via a user.

    .. versionadded:: 2.5

    .. container:: operations

        .. describe:: x == y

            Checks if two user clans are equal.

        .. describe:: x != y

            Checks if two user clans are not equal.

    .. versionadded:: 2.5

    Attributes
    ----------
    enabled: :class:`bool`
        Whether the user is displaying their clan tag.
    guild_id: Optional[:class:`int`]
        The guild ID the clan is from.

        .. note::

            This will be ``None`` if :attr:`.enabled` is ``False``.
    tag: Optional[:class:`str`]
        The clan tag.

        .. note::

            This will be ``None`` if :attr:`.enabled` is ``False``.
    """

    __slots__ = (
        '_state',
        'guild_id',
        'enabled',
        'tag',
        '_badge_hash',
    )

    def __init__(self, *, data: UserClanPayload, state: ConnectionState) -> None:
        self._state: ConnectionState = state
        self.guild_id: Optional[int] = utils._get_as_snowflake(data, 'identity_guild_id')
        self.enabled: bool = data['identity_enabled']
        self.tag: Optional[str] = data.get('tag')
        self._badge_hash: Optional[str] = data.get('badge')

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and self.tag == other.tag and self.guild_id == other.guild_id

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return f'<UserClan enabled={self.enabled} guild_id={self.guild_id} tag={self.tag!r}>'

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: Returns the cached guild this clan is from."""
        return self._state._get_guild(self.guild_id)

    @property
    def badge(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the clan badge asset.

        .. note::

            This will be ``None`` if :attr:`.enabled` is ``False``.
        """
        if self._badge_hash is None or self.guild_id is None:
            return None
        return Asset._from_clan_badge(self._state, self.guild_id, self._badge_hash)


class PartialClan:
    """Represents a partial clan.

    .. versionadded:: 2.5

    Attributes
    ----------
    tag: :class:`str`
        The clan tag.
    badge_type: Optional[:class:`ClanBadgeType`]
        The clan badge type, or ``None``.
    """

    __slots__ = (
        '_state',
        'tag',
        'badge_type',
    )

    def __init__(self, *, data: PartialClanPayload, state: ConnectionState) -> None:
        self._state: ConnectionState = state
        self.tag: str = data['tag']
        try:
            self.badge_type: Optional[ClanBadgeType] = try_enum(ClanBadgeType, data['badge'])
        except KeyError:
            self.badge_type = None


class Clan(Hashable, PartialClan):
    """Represents a clan.

    .. container:: operations

        .. describe:: x == y

            Checks if two clans are equal.

        .. describe:: x != y

            Checks if two clans are not equal.

        .. describe:: hash(x)

            Returns the clan's hash.

        .. describe:: str(x)

            Returns the clan's name.

    .. versionadded:: 2.5

    Attributes
    ----------
    id: :class:`int`
        The guild ID.
    name: :class:`str`
        The guild name.
    tag: :class:`str`
        The clan tag.
    description: :class:`str`
        The clan description.

        .. note::

            This can be different than the guild's description.
    member_count: Optional[:class:`int`]
        An approximate count of the total members in the guild, or ``None``.
    play_style: :class:`ClanPlayStyle`
        The clan play style.
    badge_type: Optional[:class:`ClanBadgeType`]
        The clan badge type, or ``None``.
    banner_style: Optional[:class:`ClanBannerStyle`]
        The clan banner type, or ``None``.
    """

    __slots__ = (
        'id',
        'name',
        'description',
        'play_style',
        'member_count',
        'banner_style',
        '_games',
        '_search_terms',
        '_badge_hash',
        '_banner_hash',
        '_badge_primary_colour',
        '_badge_secondary_colour',
        '_banner_primary_colour',
        '_banner_secondary_colour',
        '_wildcard_descriptors',
        '_verification_form',
    )

    if TYPE_CHECKING:
        id: int
        name: str
        description: str
        play_style: ClanPlayStyle
        member_count: Optional[int]
        banner_style: Optional[ClanBannerStyle]
        _games: Dict[int, Object]
        _search_terms: List[str]
        _badge_hash: Optional[str]
        _banner_hash: Optional[str]
        _badge_primary_colour: Optional[str]
        _badge_secondary_colour: Optional[str]
        _banner_primary_colour: Optional[str]
        _banner_secondary_colour: Optional[str]

    def __init__(self, *, data: ClanPayload, state: ConnectionState) -> None:
        super().__init__(data=data, state=state)  # type: ignore

        self.id: int = int(data['id'])
        self._update(data)

    def _update(self, data: ClanPayload) -> None:
        self.name: str = data['name']
        self.description: str = data['description']
        self.member_count: Optional[int] = data.get('member_count')
        self.play_style: ClanPlayStyle = try_enum(ClanPlayStyle, data.get('play_style', 0))

        try:
            self.banner_style: Optional[ClanBannerStyle] = try_enum(ClanBannerStyle, data['banner'])
        except KeyError:
            self.banner_style = None

        self._games: Dict[int, Object] = {int(g): Object(int(g)) for g in data.get('game_application_ids', [])}
        self._search_terms: List[str] = data.get('search_terms', [])
        self._badge_hash: Optional[str] = data.get('badge_hash')
        self._banner_hash: Optional[str] = data.get('banner_hash')
        self._badge_primary_colour: Optional[str] = data.get('badge_color_primary')
        self._badge_secondary_colour: Optional[str] = data.get('badge_color_secondary')
        self._banner_primary_colour: Optional[str] = data.get('brand_color_primary')
        self._banner_secondary_colour: Optional[str] = data.get('brand_color_secondary')
        self._wildcard_descriptors: List[str] = data.get('wildcard_descriptors', [])

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and self.id == other.id

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'<Clan id={self.id} tag={self.tag!r}>'

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: Returns the respective guild of this clan."""
        return self._state._get_guild(self.id)

    @property
    def games(self) -> List[Object]:
        """List[:class:`Object`]: Returns a list of objects that represent the games
        the clan plays.
        """
        return list(self._games.values())

    @property
    def search_terms(self) -> List[str]:
        """List[:class:`str`]: Returns a read-only list of the interests, topics,
        or traits for the clan.
        """
        return self._search_terms.copy()

    @property
    def wildcard_descriptors(self) -> List[str]:
        """List[:class:`str`]: Returns a read-only list of the terms that describe the
        clan.
        """
        return self._wildcard_descriptors.copy()

    @property
    def badge_primary_colour(self) -> Optional[Colour]:
        """Optional[:class:`Colour`]: A property that returns the clan badge primary colour.

        There is an alias for this named :attr:`badge_primary_color`.
        """

        if self._badge_primary_colour is None:
            return None
        return Colour.from_str(self._badge_primary_colour)

    @property
    def badge_secondary_colour(self) -> Optional[Colour]:
        """Optional[:class:`Colour`]: A property that returns the clan badge secondary colour.

        There is an alias for this named :attr:`badge_secondary_color`.
        """

        if self._badge_secondary_colour is None:
            return None
        return Colour.from_str(self._badge_secondary_colour)

    @property
    def badge_primary_color(self) -> Optional[Colour]:
        """Optional[:class:`Colour`]: A property that returns the clan badge primary color.

        There is an alias for this named :attr:`badge_primary_colour`.
        """
        return self.badge_primary_colour

    @property
    def badge_secondary_color(self) -> Optional[Colour]:
        """Optional[:class:`Colour`]: A property that returns the clan badge secondary color.

        There is an alias for this named :attr:`badge_secondary_colour`.
        """
        return self.badge_secondary_colour

    @property
    def banner_primary_colour(self) -> Optional[Colour]:
        """Optional[:class:`Colour`]: A property that returns the clan banner primary colour.

        There is an alias for this named :attr:`banner_primary_color`.
        """

        if self._banner_primary_colour is None:
            return None
        return Colour.from_str(self._banner_primary_colour)

    @property
    def banner_secondary_colour(self) -> Optional[Colour]:
        """Optional[:class:`Colour`]: A property that returns the clan banner secondary colour.

        There is an alias for this named :attr:`banner_secondary_color`.
        """

        if self._banner_secondary_colour is None:
            return None
        return Colour.from_str(self._banner_secondary_colour)

    @property
    def banner_primary_color(self) -> Optional[Colour]:
        """Optional[:class:`Colour`]: A property that returns the clan banner primary color.

        There is an alias for this named :attr:`banner_primary_colour`.
        """
        return self.banner_primary_colour

    @property
    def banner_secondary_color(self) -> Optional[Colour]:
        """Optional[:class:`Colour`]: A property that returns the clan banner secondary color.

        There is an alias for this named :attr:`banner_secondary_colour`.
        """
        return self.banner_secondary_colour

    @property
    def badge(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the badge asset, or ``None``."""
        if self._badge_hash is None:
            return None
        return Asset._from_clan_badge(self._state, self.id, self._badge_hash)

    @property
    def banner(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the banner asset, or ``None``."""
        if self._banner_hash is None:
            return None
        return Asset._from_clan_banner(self._state, self.id, self._banner_hash)
