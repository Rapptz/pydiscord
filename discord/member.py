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

import datetime
import inspect
import itertools
from operator import attrgetter
from typing import Any, Awaitable, Callable, Collection, Dict, List, Optional, TYPE_CHECKING, Tuple, TypeVar, Union

import discord.abc

from . import utils
from .asset import Asset
from .utils import MISSING
from .user import BaseUser, ClientUser, User, _UserTag
from .permissions import Permissions
from .enums import Status
from .errors import ClientException
from .colour import Colour
from .object import Object
from .flags import MemberFlags
from .presences import ClientStatus

__all__ = (
    'VoiceState',
    'Member',
)

T = TypeVar('T', bound=type)

if TYPE_CHECKING:
    from typing_extensions import Self

    from .channel import DMChannel, VoiceChannel, StageChannel
    from .flags import PublicUserFlags
    from .guild import Guild
    from .activity import ActivityTypes
    from .presences import RawPresenceUpdateEvent
    from .types.member import (
        MemberWithUser as MemberWithUserPayload,
        Member as MemberPayload,
        UserWithMember as UserWithMemberPayload,
    )
    from .types.gateway import GuildMemberUpdateEvent
    from .types.user import User as UserPayload, AvatarDecorationData
    from .abc import Snowflake
    from .state import ConnectionState
    from .message import Message
    from .role import Role
    from .types.voice import (
        GuildVoiceState as GuildVoiceStatePayload,
        VoiceState as VoiceStatePayload,
    )

    VocalGuildChannel = Union[VoiceChannel, StageChannel]


class VoiceState:
    """Represents a Discord user's voice state.

    Attributes
    ------------
    deaf: :class:`bool`
        Indicates if the user is currently deafened by the guild.
    mute: :class:`bool`
        Indicates if the user is currently muted by the guild.
    self_mute: :class:`bool`
        Indicates if the user is currently muted by their own accord.
    self_deaf: :class:`bool`
        Indicates if the user is currently deafened by their own accord.
    self_stream: :class:`bool`
        Indicates if the user is currently streaming via 'Go Live' feature.

        .. versionadded:: 1.3

    self_video: :class:`bool`
        Indicates if the user is currently broadcasting video.
    suppress: :class:`bool`
        Indicates if the user is suppressed from speaking.

        Only applies to stage channels.

        .. versionadded:: 1.7

    requested_to_speak_at: Optional[:class:`datetime.datetime`]
        An aware datetime object that specifies the date and time in UTC that the member
        requested to speak. It will be ``None`` if they are not requesting to speak
        anymore or have been accepted to speak.

        Only applicable to stage channels.

        .. versionadded:: 1.7

    afk: :class:`bool`
        Indicates if the user is currently in the AFK channel in the guild.
    channel: Optional[Union[:class:`VoiceChannel`, :class:`StageChannel`]]
        The voice channel that the user is currently connected to. ``None`` if the user
        is not currently in a voice channel.
    """

    __slots__ = (
        'session_id',
        'deaf',
        'mute',
        'self_mute',
        'self_stream',
        'self_video',
        'self_deaf',
        'afk',
        'channel',
        'requested_to_speak_at',
        'suppress',
    )

    def __init__(
        self, *, data: Union[VoiceStatePayload, GuildVoiceStatePayload], channel: Optional[VocalGuildChannel] = None
    ):
        self.session_id: Optional[str] = data.get('session_id')
        self._update(data, channel)

    def _update(self, data: Union[VoiceStatePayload, GuildVoiceStatePayload], channel: Optional[VocalGuildChannel]):
        self.self_mute: bool = data.get('self_mute', False)
        self.self_deaf: bool = data.get('self_deaf', False)
        self.self_stream: bool = data.get('self_stream', False)
        self.self_video: bool = data.get('self_video', False)
        self.afk: bool = data.get('suppress', False)
        self.mute: bool = data.get('mute', False)
        self.deaf: bool = data.get('deaf', False)
        self.suppress: bool = data.get('suppress', False)
        self.requested_to_speak_at: Optional[datetime.datetime] = utils.parse_time(data.get('request_to_speak_timestamp'))
        self.channel: Optional[VocalGuildChannel] = channel

    def __repr__(self) -> str:
        attrs = [
            ('self_mute', self.self_mute),
            ('self_deaf', self.self_deaf),
            ('self_stream', self.self_stream),
            ('suppress', self.suppress),
            ('requested_to_speak_at', self.requested_to_speak_at),
            ('channel', self.channel),
        ]
        inner = ' '.join('%s=%r' % t for t in attrs)
        return f'<{self.__class__.__name__} {inner}>'


def flatten_user(cls: T) -> T:
    for attr, value in itertools.chain(BaseUser.__dict__.items(), User.__dict__.items()):
        # ignore private/special methods
        if attr.startswith('_'):
            continue

        # don't override what we already have
        if attr in cls.__dict__:
            continue

        # if it's a slotted attribute or a property, redirect it
        # slotted members are implemented as member_descriptors in Type.__dict__
        if not hasattr(value, '__annotations__'):
            getter = attrgetter('_user.' + attr)
            setattr(cls, attr, property(getter, doc=f'Equivalent to :attr:`User.{attr}`'))
        else:
            # Technically, this can also use attrgetter
            # However I'm not sure how I feel about "functions" returning properties
            # It probably breaks something in Sphinx.
            # probably a member function by now
            def generate_function(x):
                # We want sphinx to properly show coroutine functions as coroutines
                if inspect.iscoroutinefunction(value):

                    async def general(self, *args, **kwargs):  # type: ignore
                        return await getattr(self._user, x)(*args, **kwargs)

                else:

                    def general(self, *args, **kwargs):
                        return getattr(self._user, x)(*args, **kwargs)

                general.__name__ = x
                return general

            func = generate_function(attr)
            func = utils.copy_doc(value)(func)
            setattr(cls, attr, func)

    return cls


@flatten_user
class Member(discord.abc.Messageable, _UserTag):
    """Represents a Discord member to a :class:`Guild`.

    This implements a lot of the functionality of :class:`User`.

    .. container:: operations

        .. describe:: x == y

            Checks if two members are equal.
            Note that this works with :class:`User` instances too.

        .. describe:: x != y

            Checks if two members are not equal.
            Note that this works with :class:`User` instances too.

        .. describe:: hash(x)

            Returns the member's hash.

        .. describe:: str(x)

            Returns the member's handle (e.g. ``name`` or ``name#discriminator``).

    Attributes
    ----------
    joined_at: Optional[:class:`datetime.datetime`]
        An aware datetime object that specifies the date and time in UTC that the member joined the guild.
        If the member left and rejoined the guild, this will be the latest date. In certain cases, this can be ``None``.
    activities: Tuple[Union[:class:`BaseActivity`, :class:`Spotify`]]
        The activities that the user is currently doing.

        .. note::

            Due to a Discord API limitation, a user's Spotify activity may not appear
            if they are listening to a song with a title longer
            than 128 characters. See :issue:`1738` for more information.

    guild: :class:`Guild`
        The guild that the member belongs to.
    nick: Optional[:class:`str`]
        The guild specific nickname of the user. Takes precedence over the global name.
    pending: :class:`bool`
        Whether the member is pending member verification.

        .. versionadded:: 1.6
    premium_since: Optional[:class:`datetime.datetime`]
        An aware datetime object that specifies the date and time in UTC when the member used their
        "Nitro boost" on the guild, if available. This could be ``None``.
    timed_out_until: Optional[:class:`datetime.datetime`]
        An aware datetime object that specifies the date and time in UTC that the member's time out will expire.
        This will be set to ``None`` or a time in the past if the user is not timed out.

        .. versionadded:: 2.0
    client_status: :class:`ClientStatus`
        Model which holds information about the status of the member on various clients/platforms via presence updates.

        .. versionadded:: 2.5
    """

    __slots__ = (
        '_roles',
        'joined_at',
        'premium_since',
        'activities',
        'guild',
        'pending',
        'nick',
        'timed_out_until',
        '_permissions',
        'client_status',
        '_user',
        '_state',
        '_avatar',
        '_banner',
        '_flags',
        '_avatar_decoration_data',
    )

    if TYPE_CHECKING:
        name: str
        id: int
        discriminator: str
        global_name: Optional[str]
        bot: bool
        system: bool
        created_at: datetime.datetime
        default_avatar: Asset
        avatar: Optional[Asset]
        dm_channel: Optional[DMChannel]
        create_dm: Callable[[], Awaitable[DMChannel]]
        mutual_guilds: List[Guild]
        public_flags: PublicUserFlags
        banner: Optional[Asset]
        accent_color: Optional[Colour]
        accent_colour: Optional[Colour]
        avatar_decoration: Optional[Asset]
        avatar_decoration_sku_id: Optional[int]

    def __init__(self, *, data: MemberWithUserPayload, guild: Guild, state: ConnectionState):
        self._state: ConnectionState = state
        self._user: User = state.store_user(data['user'])
        self.guild: Guild = guild
        self.joined_at: Optional[datetime.datetime] = utils.parse_time(data.get('joined_at'))
        self.premium_since: Optional[datetime.datetime] = utils.parse_time(data.get('premium_since'))
        self._roles: utils.SnowflakeList = utils.SnowflakeList(map(int, data['roles']))
        self.client_status: ClientStatus = ClientStatus()
        self.activities: Tuple[ActivityTypes, ...] = ()
        self.nick: Optional[str] = data.get('nick', None)
        self.pending: bool = data.get('pending', False)
        self._avatar: Optional[str] = data.get('avatar')
        self._banner: Optional[str] = data.get('banner')
        self._permissions: Optional[int]
        self._flags: int = data['flags']
        self._avatar_decoration_data: Optional[AvatarDecorationData] = data.get('avatar_decoration_data')
        try:
            self._permissions = int(data['permissions'])
        except KeyError:
            self._permissions = None

        self.timed_out_until: Optional[datetime.datetime] = utils.parse_time(data.get('communication_disabled_until'))

    def __str__(self) -> str:
        return str(self._user)

    def __repr__(self) -> str:
        return (
            f'<Member id={self._user.id} name={self._user.name!r} global_name={self._user.global_name!r}'
            f' bot={self._user.bot} nick={self.nick!r} guild={self.guild!r}>'
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _UserTag) and other.id == self.id

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self._user)

    @classmethod
    def _from_message(cls, *, message: Message, data: MemberPayload) -> Self:
        author = message.author
        data['user'] = author._to_minimal_user_json()  # type: ignore
        return cls(data=data, guild=message.guild, state=message._state)  # type: ignore

    @classmethod
    def _from_client_user(cls, *, user: ClientUser, guild: Guild, state: ConnectionState) -> Self:
        data = {
            'roles': [],
            'user': user._to_minimal_user_json(),
            'flags': 0,
        }
        return cls(data=data, guild=guild, state=state)  # type: ignore

    def _update_from_message(self, data: MemberPayload) -> None:
        self.joined_at = utils.parse_time(data.get('joined_at'))
        self.premium_since = utils.parse_time(data.get('premium_since'))
        self._roles = utils.SnowflakeList(map(int, data['roles']))
        self.nick = data.get('nick', None)
        self.pending = data.get('pending', False)
        self.timed_out_until = utils.parse_time(data.get('communication_disabled_until'))
        self._flags = data.get('flags', 0)

    @classmethod
    def _try_upgrade(cls, *, data: UserWithMemberPayload, guild: Guild, state: ConnectionState) -> Union[User, Self]:
        # A User object with a 'member' key
        try:
            member_data = data.pop('member')
        except KeyError:
            return state.create_user(data)
        else:
            member_data['user'] = data  # type: ignore
            return cls(data=member_data, guild=guild, state=state)  # type: ignore

    @classmethod
    def _copy(cls, member: Self) -> Self:
        self = cls.__new__(cls)  # to bypass __init__

        self._roles = utils.SnowflakeList(member._roles, is_sorted=True)
        self.joined_at = member.joined_at
        self.premium_since = member.premium_since
        self.client_status = member.client_status
        self.guild = member.guild
        self.nick = member.nick
        self.pending = member.pending
        self.activities = member.activities
        self.timed_out_until = member.timed_out_until
        self._flags = member._flags
        self._permissions = member._permissions
        self._state = member._state
        self._avatar = member._avatar
        self._banner = member._banner
        self._avatar_decoration_data = member._avatar_decoration_data

        # Reference will not be copied unless necessary by PRESENCE_UPDATE
        # See below
        self._user = member._user
        return self

    async def _get_channel(self) -> DMChannel:
        ch = await self.create_dm()
        return ch

    def _update(self, data: GuildMemberUpdateEvent) -> None:
        # the nickname change is optional,
        # if it isn't in the payload then it didn't change
        try:
            self.nick = data['nick']
        except KeyError:
            pass

        try:
            self.pending = data['pending']
        except KeyError:
            pass

        self.premium_since = utils.parse_time(data.get('premium_since'))
        self.timed_out_until = utils.parse_time(data.get('communication_disabled_until'))
        self._roles = utils.SnowflakeList(map(int, data['roles']))
        self._avatar = data.get('avatar')
        self._banner = data.get('banner')
        self._flags = data.get('flags', 0)
        self._avatar_decoration_data = data.get('avatar_decoration_data')

    def _presence_update(self, raw: RawPresenceUpdateEvent, user: UserPayload) -> Optional[Tuple[User, User]]:
        self.activities = raw.activities
        self.client_status = raw.client_status

        if len(user) > 1:
            return self._update_inner_user(user)

    def _update_inner_user(self, user: UserPayload) -> Optional[Tuple[User, User]]:
        u = self._user
        original = (
            u.name,
            u.discriminator,
            u._avatar,
            u.global_name,
            u._public_flags,
            u._avatar_decoration_data['sku_id'] if u._avatar_decoration_data is not None else None,
        )

        decoration_payload = user.get('avatar_decoration_data')
        # These keys seem to always be available
        modified = (
            user['username'],
            user['discriminator'],
            user['avatar'],
            user.get('global_name'),
            user.get('public_flags', 0),
            decoration_payload['sku_id'] if decoration_payload is not None else None,
        )
        if original != modified:
            to_return = User._copy(self._user)
            u.name, u.discriminator, u._avatar, u.global_name, u._public_flags, u._avatar_decoration_data = (
                user['username'],
                user['discriminator'],
                user['avatar'],
                user.get('global_name'),
                user.get('public_flags', 0),
                decoration_payload,
            )
            # Signal to dispatch on_user_update
            return to_return, u

    @property
    def status(self) -> Status:
        """:class:`Status`: The member's overall status. If the value is unknown, then it will be a :class:`str` instead."""
        return self.client_status.status

    @property
    def raw_status(self) -> str:
        """:class:`str`: The member's overall status as a string value.

        .. versionadded:: 1.5
        """
        return self.client_status._status

    @status.setter
    def status(self, value: Status) -> None:
        # internal use only
        self.client_status._status = str(value)

    @property
    def mobile_status(self) -> Status:
        """:class:`Status`: The member's status on a mobile device, if applicable."""
        return self.client_status.mobile_status

    @property
    def desktop_status(self) -> Status:
        """:class:`Status`: The member's status on the desktop client, if applicable."""
        return self.client_status.desktop_status

    @property
    def web_status(self) -> Status:
        """:class:`Status`: The member's status on the web client, if applicable."""
        return self.client_status.web_status

    def is_on_mobile(self) -> bool:
        """A helper function that determines if a member is active on a mobile device.

        Returns
        -------
        :class:`bool`
        """
        return self.client_status.is_on_mobile()

    @property
    def colour(self) -> Colour:
        """:class:`Colour`: A property that returns a colour denoting the rendered colour
        for the member. If the default colour is the one rendered then an instance
        of :meth:`Colour.default` is returned.

        There is an alias for this named :attr:`color`.
        """

        roles = self.roles[1:]  # remove @everyone

        # highest order of the colour is the one that gets rendered.
        # if the highest is the default colour then the next one with a colour
        # is chosen instead
        for role in reversed(roles):
            if role.colour.value:
                return role.colour
        return Colour.default()

    @property
    def color(self) -> Colour:
        """:class:`Colour`: A property that returns a color denoting the rendered color for
        the member. If the default color is the one rendered then an instance of :meth:`Colour.default`
        is returned.

        There is an alias for this named :attr:`colour`.
        """
        return self.colour

    @property
    def roles(self) -> List[Role]:
        """List[:class:`Role`]: A :class:`list` of :class:`Role` that the member belongs to. Note
        that the first element of this list is always the default '@everyone'
        role.

        These roles are sorted by their position in the role hierarchy.
        """
        result = []
        g = self.guild
        for role_id in self._roles:
            role = g.get_role(role_id)
            if role:
                result.append(role)
        if g.default_role:
            result.append(g.default_role)
        result.sort()
        return result

    @property
    def display_icon(self) -> Optional[Union[str, Asset]]:
        """Optional[Union[:class:`str`, :class:`Asset`]]: A property that returns the role icon that is rendered for
        this member. If no icon is shown then ``None`` is returned.

        .. versionadded:: 2.0
        """

        roles = self.roles[1:]  # remove @everyone
        for role in reversed(roles):
            icon = role.display_icon
            if icon:
                return icon

        return None

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention the member."""
        return f'<@{self._user.id}>'

    @property
    def display_name(self) -> str:
        """:class:`str`: Returns the user's display name.

        For regular users this is just their global name or their username,
        but if they have a guild specific nickname then that
        is returned instead.
        """
        return self.nick or self.global_name or self.name

    @property
    def display_avatar(self) -> Asset:
        """:class:`Asset`: Returns the member's display avatar.

        For regular members this is just their avatar, but
        if they have a guild specific avatar then that
        is returned instead.

        .. versionadded:: 2.0
        """
        return self.guild_avatar or self._user.avatar or self._user.default_avatar

    @property
    def guild_avatar(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns an :class:`Asset` for the guild avatar
        the member has. If unavailable, ``None`` is returned.

        .. versionadded:: 2.0
        """
        if self._avatar is None:
            return None
        return Asset._from_guild_avatar(self._state, self.guild.id, self.id, self._avatar)

    @property
    def display_banner(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the member's displayed banner, if any.

        This is the member's guild banner if available, otherwise it's their
        global banner. If the member has no banner set then ``None`` is returned.

        .. versionadded:: 2.5
        """
        return self.guild_banner or self._user.banner

    @property
    def guild_banner(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns an :class:`Asset` for the guild banner
        the member has. If unavailable, ``None`` is returned.

        .. versionadded:: 2.5
        """
        if self._banner is None:
            return None
        return Asset._from_guild_banner(self._state, self.guild.id, self.id, self._banner)

    @property
    def activity(self) -> Optional[ActivityTypes]:
        """Optional[Union[:class:`BaseActivity`, :class:`Spotify`]]: Returns the primary
        activity the user is currently doing. Could be ``None`` if no activity is being done.

        .. note::

            Due to a Discord API limitation, this may be ``None`` if
            the user is listening to a song on Spotify with a title longer
            than 128 characters. See :issue:`1738` for more information.

        .. note::

            A user may have multiple activities, these can be accessed under :attr:`activities`.
        """
        if self.activities:
            return self.activities[0]

    def mentioned_in(self, message: Message) -> bool:
        """Checks if the member is mentioned in the specified message.

        Parameters
        -----------
        message: :class:`Message`
            The message to check if you're mentioned in.

        Returns
        -------
        :class:`bool`
            Indicates if the member is mentioned in the message.
        """
        if message.guild is None or message.guild.id != self.guild.id:
            return False

        if self._user.mentioned_in(message):
            return True

        return any(self._roles.has(role.id) for role in message.role_mentions)

    @property
    def top_role(self) -> Role:
        """:class:`Role`: Returns the member's highest role.

        This is useful for figuring where a member stands in the role
        hierarchy chain.
        """
        guild = self.guild
        if len(self._roles) == 0:
            return guild.default_role

        return max(guild.get_role(rid) or guild.default_role for rid in self._roles)

    @property
    def guild_permissions(self) -> Permissions:
        """:class:`Permissions`: Returns the member's guild permissions.

        This only takes into consideration the guild permissions
        and not most of the implied permissions or any of the
        channel permission overwrites. For 100% accurate permission
        calculation, please use :meth:`abc.GuildChannel.permissions_for`.

        This does take into consideration guild ownership, the
        administrator implication, and whether the member is timed out.

        .. versionchanged:: 2.0
            Member timeouts are taken into consideration.
        """

        if self.guild.owner_id == self.id:
            return Permissions.all()

        base = Permissions.none()
        for r in self.roles:
            base.value |= r.permissions.value

        if base.administrator:
            return Permissions.all()

        if self.is_timed_out():
            base.value &= Permissions._timeout_mask()

        return base

    @property
    def resolved_permissions(self) -> Optional[Permissions]:
        """Optional[:class:`Permissions`]: Returns the member's resolved permissions
        from an interaction.

        This is only available in interaction contexts and represents the resolved
        permissions of the member in the channel the interaction was executed in.
        This is more or less equivalent to calling :meth:`abc.GuildChannel.permissions_for`
        but stored and returned as an attribute by the Discord API rather than computed.

        .. versionadded:: 2.0
        """
        if self._permissions is None:
            return None
        return Permissions(self._permissions)

    @property
    def voice(self) -> Optional[VoiceState]:
        """Optional[:class:`VoiceState`]: Returns the member's current voice state."""
        return self.guild._voice_state_for(self._user.id)

    @property
    def flags(self) -> MemberFlags:
        """:class:`MemberFlags`: Returns the member's flags.

        .. versionadded:: 2.2
        """
        return MemberFlags._from_value(self._flags)

    async def ban(
        self,
        *,
        delete_message_days: int = MISSING,
        delete_message_seconds: int = MISSING,
        reason: Optional[str] = None,
    ) -> None:
        """|coro|

        Bans this member. Equivalent to :meth:`Guild.ban`.
        """
        await self.guild.ban(
            self,
            reason=reason,
            delete_message_days=delete_message_days,
            delete_message_seconds=delete_message_seconds,
        )

    async def unban(self, *, reason: Optional[str] = None) -> None:
        """|coro|

        Unbans this member. Equivalent to :meth:`Guild.unban`.
        """
        await self.guild.unban(self, reason=reason)

    async def kick(self, *, reason: Optional[str] = None) -> None:
        """|coro|

        Kicks this member. Equivalent to :meth:`Guild.kick`.
        """
        await self.guild.kick(self, reason=reason)

    async def edit(
        self,
        *,
        nick: Optional[str] = MISSING,
        mute: bool = MISSING,
        deafen: bool = MISSING,
        suppress: bool = MISSING,
        roles: Collection[discord.abc.Snowflake] = MISSING,
        voice_channel: Optional[VocalGuildChannel] = MISSING,
        timed_out_until: Optional[datetime.datetime] = MISSING,
        bypass_verification: bool = MISSING,
        reason: Optional[str] = None,
    ) -> Optional[Member]:
        """|coro|

        Edits the member's data.

        Depending on the parameter passed, this requires different permissions listed below:

        +---------------------+---------------------------------------+
        |      Parameter      |              Permission               |
        +---------------------+---------------------------------------+
        | nick                | :attr:`Permissions.manage_nicknames`  |
        +---------------------+---------------------------------------+
        | mute                | :attr:`Permissions.mute_members`      |
        +---------------------+---------------------------------------+
        | deafen              | :attr:`Permissions.deafen_members`    |
        +---------------------+---------------------------------------+
        | roles               | :attr:`Permissions.manage_roles`      |
        +---------------------+---------------------------------------+
        | voice_channel       | :attr:`Permissions.move_members`      |
        +---------------------+---------------------------------------+
        | timed_out_until     | :attr:`Permissions.moderate_members`  |
        +---------------------+---------------------------------------+
        | bypass_verification | :attr:`Permissions.moderate_members`  |
        +---------------------+---------------------------------------+

        All parameters are optional.

        .. versionchanged:: 1.1
            Can now pass ``None`` to ``voice_channel`` to kick a member from voice.

        .. versionchanged:: 2.0
            The newly updated member is now optionally returned, if applicable.

        Parameters
        -----------
        nick: Optional[:class:`str`]
            The member's new nickname. Use ``None`` to remove the nickname.
        mute: :class:`bool`
            Indicates if the member should be guild muted or un-muted.
        deafen: :class:`bool`
            Indicates if the member should be guild deafened or un-deafened.
        suppress: :class:`bool`
            Indicates if the member should be suppressed in stage channels.

            .. versionadded:: 1.7

        roles: List[:class:`Role`]
            The member's new list of roles. This *replaces* the roles.
        voice_channel: Optional[Union[:class:`VoiceChannel`, :class:`StageChannel`]]
            The voice channel to move the member to.
            Pass ``None`` to kick them from voice.
        timed_out_until: Optional[:class:`datetime.datetime`]
            The date the member's timeout should expire, or ``None`` to remove the timeout.
            This must be a timezone-aware datetime object. Consider using :func:`utils.utcnow`.

            .. versionadded:: 2.0
        bypass_verification: :class:`bool`
            Indicates if the member should be allowed to bypass the guild verification requirements.

            .. versionadded:: 2.2

        reason: Optional[:class:`str`]
            The reason for editing this member. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have the proper permissions to do the action requested.
        HTTPException
            The operation failed.
        TypeError
            The datetime object passed to ``timed_out_until`` was not timezone-aware.

        Returns
        --------
        Optional[:class:`.Member`]
            The newly updated member, if applicable. This is not returned
            if certain fields are passed, such as ``suppress``.
        """
        http = self._state.http
        guild_id = self.guild.id
        me = self._state.self_id == self.id
        payload: Dict[str, Any] = {}

        if nick is not MISSING:
            nick = nick or ''
            if me:
                await http.change_my_nickname(guild_id, nick, reason=reason)
            else:
                payload['nick'] = nick

        if deafen is not MISSING:
            payload['deaf'] = deafen

        if mute is not MISSING:
            payload['mute'] = mute

        if suppress is not MISSING:
            voice_state_payload: Dict[str, Any] = {
                'suppress': suppress,
            }

            if self.voice is not None and self.voice.channel is not None:
                voice_state_payload['channel_id'] = self.voice.channel.id

            if suppress or self.bot:
                voice_state_payload['request_to_speak_timestamp'] = None

            if me:
                await http.edit_my_voice_state(guild_id, voice_state_payload)
            else:
                if not suppress:
                    voice_state_payload['request_to_speak_timestamp'] = datetime.datetime.utcnow().isoformat()
                await http.edit_voice_state(guild_id, self.id, voice_state_payload)

        if voice_channel is not MISSING:
            payload['channel_id'] = voice_channel and voice_channel.id

        if roles is not MISSING:
            payload['roles'] = tuple(r.id for r in roles)

        if timed_out_until is not MISSING:
            if timed_out_until is None:
                payload['communication_disabled_until'] = None
            else:
                if timed_out_until.tzinfo is None:
                    raise TypeError(
                        'timed_out_until must be an aware datetime. Consider using discord.utils.utcnow() or datetime.datetime.now().astimezone() for local time.'
                    )
                payload['communication_disabled_until'] = timed_out_until.isoformat()

        if bypass_verification is not MISSING:
            flags = MemberFlags._from_value(self._flags)
            flags.bypasses_verification = bypass_verification
            payload['flags'] = flags.value

        if payload:
            data = await http.edit_member(guild_id, self.id, reason=reason, **payload)
            return Member(data=data, guild=self.guild, state=self._state)

    async def request_to_speak(self) -> None:
        """|coro|

        Request to speak in the connected channel.

        Only applies to stage channels.

        .. note::

            Requesting members that are not the client is equivalent
            to :attr:`.edit` providing ``suppress`` as ``False``.

        .. versionadded:: 1.7

        Raises
        -------
        ClientException
            You are not connected to a voice channel.
        Forbidden
            You do not have the proper permissions to do the action requested.
        HTTPException
            The operation failed.
        """
        if self.voice is None or self.voice.channel is None:
            raise ClientException('Cannot request to speak while not connected to a voice channel.')

        payload = {
            'channel_id': self.voice.channel.id,
            'request_to_speak_timestamp': datetime.datetime.utcnow().isoformat(),
        }

        if self._state.self_id != self.id:
            payload['suppress'] = False
            await self._state.http.edit_voice_state(self.guild.id, self.id, payload)
        else:
            await self._state.http.edit_my_voice_state(self.guild.id, payload)

    async def move_to(self, channel: Optional[VocalGuildChannel], *, reason: Optional[str] = None) -> None:
        """|coro|

        Moves a member to a new voice channel (they must be connected first).

        You must have :attr:`~Permissions.move_members` to do this.

        This raises the same exceptions as :meth:`edit`.

        .. versionchanged:: 1.1
            Can now pass ``None`` to kick a member from voice.

        Parameters
        -----------
        channel: Optional[Union[:class:`VoiceChannel`, :class:`StageChannel`]]
            The new voice channel to move the member to.
            Pass ``None`` to kick them from voice.
        reason: Optional[:class:`str`]
            The reason for doing this action. Shows up on the audit log.
        """
        await self.edit(voice_channel=channel, reason=reason)

    async def timeout(
        self, until: Optional[Union[datetime.timedelta, datetime.datetime]], /, *, reason: Optional[str] = None
    ) -> None:
        """|coro|

        Applies a time out to a member until the specified date time or for the
        given :class:`datetime.timedelta`.

        You must have :attr:`~Permissions.moderate_members` to do this.

        This raises the same exceptions as :meth:`edit`.

        Parameters
        -----------
        until: Optional[Union[:class:`datetime.timedelta`, :class:`datetime.datetime`]]
            If this is a :class:`datetime.timedelta` then it represents the amount of
            time the member should be timed out for. If this is a :class:`datetime.datetime`
            then it's when the member's timeout should expire. If ``None`` is passed then the
            timeout is removed. Note that the API only allows for timeouts up to 28 days.
        reason: Optional[:class:`str`]
            The reason for doing this action. Shows up on the audit log.

        Raises
        -------
        TypeError
            The ``until`` parameter was the wrong type or the datetime was not timezone-aware.
        """

        if until is None:
            timed_out_until = None
        elif isinstance(until, datetime.timedelta):
            timed_out_until = utils.utcnow() + until
        elif isinstance(until, datetime.datetime):
            timed_out_until = until
        else:
            raise TypeError(f'expected None, datetime.datetime, or datetime.timedelta not {until.__class__.__name__}')

        await self.edit(timed_out_until=timed_out_until, reason=reason)

    async def add_roles(self, *roles: Snowflake, reason: Optional[str] = None, atomic: bool = True) -> None:
        r"""|coro|

        Gives the member a number of :class:`Role`\s.

        You must have :attr:`~Permissions.manage_roles` to
        use this, and the added :class:`Role`\s must appear lower in the list
        of roles than the highest role of the client.

        Parameters
        -----------
        \*roles: :class:`abc.Snowflake`
            An argument list of :class:`abc.Snowflake` representing a :class:`Role`
            to give to the member.
        reason: Optional[:class:`str`]
            The reason for adding these roles. Shows up on the audit log.
        atomic: :class:`bool`
            Whether to atomically add roles. This will ensure that multiple
            operations will always be applied regardless of the current
            state of the cache.

        Raises
        -------
        Forbidden
            You do not have permissions to add these roles.
        HTTPException
            Adding roles failed.
        """

        if not atomic:
            new_roles = utils._unique(Object(id=r.id) for s in (self.roles[1:], roles) for r in s)
            await self.edit(roles=new_roles, reason=reason)
        else:
            req = self._state.http.add_role
            guild_id = self.guild.id
            user_id = self.id
            for role in roles:
                await req(guild_id, user_id, role.id, reason=reason)

    async def remove_roles(self, *roles: Snowflake, reason: Optional[str] = None, atomic: bool = True) -> None:
        r"""|coro|

        Removes :class:`Role`\s from this member.

        You must have :attr:`~Permissions.manage_roles` to
        use this, and the removed :class:`Role`\s must appear lower in the list
        of roles than the highest role of the client.

        Parameters
        -----------
        \*roles: :class:`abc.Snowflake`
            An argument list of :class:`abc.Snowflake` representing a :class:`Role`
            to remove from the member.
        reason: Optional[:class:`str`]
            The reason for removing these roles. Shows up on the audit log.
        atomic: :class:`bool`
            Whether to atomically remove roles. This will ensure that multiple
            operations will always be applied regardless of the current
            state of the cache.

        Raises
        -------
        Forbidden
            You do not have permissions to remove these roles.
        HTTPException
            Removing the roles failed.
        """

        if not atomic:
            new_roles = [Object(id=r.id) for r in self.roles[1:]]  # remove @everyone
            for role in roles:
                try:
                    new_roles.remove(Object(id=role.id))
                except ValueError:
                    pass

            await self.edit(roles=new_roles, reason=reason)
        else:
            req = self._state.http.remove_role
            guild_id = self.guild.id
            user_id = self.id
            for role in roles:
                await req(guild_id, user_id, role.id, reason=reason)

    async def fetch_voice(self) -> VoiceState:
        """|coro|

        Retrieves the current voice state from this member.

        .. versionadded:: 2.5

        Raises
        -------
        NotFound
            The member is not in a voice channel.
        Forbidden
            You do not have permissions to get a voice state.
        HTTPException
            Retrieving the voice state failed.

        Returns
        -------
        :class:`VoiceState`
            The current voice state of the member.
        """
        guild_id = self.guild.id
        if self._state.self_id == self.id:
            data = await self._state.http.get_my_voice_state(guild_id)
        else:
            data = await self._state.http.get_voice_state(guild_id, self.id)

        channel_id = data.get('channel_id')
        channel: Optional[VocalGuildChannel] = None
        if channel_id is not None:
            channel = self.guild.get_channel(int(channel_id))  # type: ignore # must be voice channel here

        return VoiceState(data=data, channel=channel)

    def get_role(self, role_id: int, /) -> Optional[Role]:
        """Returns a role with the given ID from roles which the member has.

        .. versionadded:: 2.0

        Parameters
        -----------
        role_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`Role`]
            The role or ``None`` if not found in the member's roles.
        """
        return self.guild.get_role(role_id) if self._roles.has(role_id) else None

    def is_timed_out(self) -> bool:
        """Returns whether this member is timed out.

        .. versionadded:: 2.0

        Returns
        --------
        :class:`bool`
            ``True`` if the member is timed out. ``False`` otherwise.
        """
        if self.timed_out_until is not None:
            return utils.utcnow() < self.timed_out_until
        return False
