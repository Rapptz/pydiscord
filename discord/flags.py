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

from functools import reduce
from operator import or_
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    overload,
)

from .enums import UserFlags

if TYPE_CHECKING:
    from typing_extensions import Self


__all__ = (
    'SystemChannelFlags',
    'MessageFlags',
    'PublicUserFlags',
    'Intents',
    'MemberCacheFlags',
    'ApplicationFlags',
    'ChannelFlags',
    'AutoModPresets',
    'MemberFlags',
    'AppCommandContext',
    'AttachmentFlags',
    'RoleFlags',
    'AppInstallationType',
    'SKUFlags',
    'EmbedFlags',
)

BF = TypeVar('BF', bound='BaseFlags')


class flag_value:
    def __init__(self, func: Callable[[Any], int]):
        self.flag: int = func(None)
        self.__doc__: Optional[str] = func.__doc__

    @overload
    def __get__(self, instance: None, owner: Type[BF]) -> Self:
        ...

    @overload
    def __get__(self, instance: BF, owner: Type[BF]) -> bool:
        ...

    def __get__(self, instance: Optional[BF], owner: Type[BF]) -> Any:
        if instance is None:
            return self
        return instance._has_flag(self.flag)

    def __set__(self, instance: BaseFlags, value: bool) -> None:
        instance._set_flag(self.flag, value)

    def __repr__(self) -> str:
        return f'<flag_value flag={self.flag!r}>'


class alias_flag_value(flag_value):
    pass


def fill_with_flags(*, inverted: bool = False) -> Callable[[Type[BF]], Type[BF]]:
    def decorator(cls: Type[BF]) -> Type[BF]:
        # fmt: off
        cls.VALID_FLAGS = {
            name: value.flag
            for name, value in cls.__dict__.items()
            if isinstance(value, flag_value)
        }
        # fmt: on

        if inverted:
            max_bits = max(cls.VALID_FLAGS.values()).bit_length()
            cls.DEFAULT_VALUE = -1 + (2**max_bits)
        else:
            cls.DEFAULT_VALUE = 0

        return cls

    return decorator


# n.b. flags must inherit from this and use the decorator above
class BaseFlags:
    VALID_FLAGS: ClassVar[Dict[str, int]]
    DEFAULT_VALUE: ClassVar[int]

    value: int

    __slots__ = ('value',)

    def __init__(self, **kwargs: bool):
        self.value = self.DEFAULT_VALUE
        for key, value in kwargs.items():
            if key not in self.VALID_FLAGS:
                raise TypeError(f'{key!r} is not a valid flag name.')
            setattr(self, key, value)

    @classmethod
    def _from_value(cls, value: int) -> Self:
        self = cls.__new__(cls)
        self.value = value
        return self

    def __or__(self, other: Self) -> Self:
        return self._from_value(self.value | other.value)

    def __and__(self, other: Self) -> Self:
        return self._from_value(self.value & other.value)

    def __xor__(self, other: Self) -> Self:
        return self._from_value(self.value ^ other.value)

    def __ior__(self, other: Self) -> Self:
        self.value |= other.value
        return self

    def __iand__(self, other: Self) -> Self:
        self.value &= other.value
        return self

    def __ixor__(self, other: Self) -> Self:
        self.value ^= other.value
        return self

    def __invert__(self) -> Self:
        max_bits = max(self.VALID_FLAGS.values()).bit_length()
        max_value = -1 + (2**max_bits)
        return self._from_value(self.value ^ max_value)

    def __bool__(self) -> bool:
        return self.value != self.DEFAULT_VALUE

    def __eq__(self, other: object) -> bool:
        return isinstance(other, self.__class__) and self.value == other.value

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} value={self.value}>'

    def __iter__(self) -> Iterator[Tuple[str, bool]]:
        for name, value in self.__class__.__dict__.items():
            if isinstance(value, alias_flag_value):
                continue

            if isinstance(value, flag_value):
                yield (name, self._has_flag(value.flag))

    def _has_flag(self, o: int) -> bool:
        return (self.value & o) == o

    def _set_flag(self, o: int, toggle: bool) -> None:
        if toggle is True:
            self.value |= o
        elif toggle is False:
            self.value &= ~o
        else:
            raise TypeError(f'Value to set for {self.__class__.__name__} must be a bool.')


@fill_with_flags(inverted=True)
class SystemChannelFlags(BaseFlags):
    r"""Wraps up a Discord system channel flag value.

    Similar to :class:`Permissions`\, the properties provided are two way.
    You can set and retrieve individual bits using the properties as if they
    were regular bools. This allows you to edit the system flags easily.

    To construct an object you can pass keyword arguments denoting the flags
    to enable or disable.

    .. container:: operations

        .. describe:: x == y

            Checks if two flags are equal.

        .. describe:: x != y

            Checks if two flags are not equal.

        .. describe:: x | y, x |= y

            Returns a SystemChannelFlags instance with all enabled flags from
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x & y, x &= y

            Returns a SystemChannelFlags instance with only flags enabled on
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x ^ y, x ^= y

            Returns a SystemChannelFlags instance with only flags enabled on
            only one of x or y, not on both.

            .. versionadded:: 2.0

        .. describe:: ~x

            Returns a SystemChannelFlags instance with all flags inverted from x.

            .. versionadded:: 2.0

        .. describe:: hash(x)

               Return the flag's hash.

        .. describe:: iter(x)

               Returns an iterator of ``(name, value)`` pairs. This allows it
               to be, for example, constructed as a dict or a list of pairs.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

            .. versionadded:: 2.0

    Attributes
    -----------
    value: :class:`int`
        The raw value. This value is a bit array field of a 53-bit integer
        representing the currently available flags. You should query
        flags via the properties rather than using this raw value.
    """

    __slots__ = ()

    # For some reason the flags for system channels are "inverted"
    # ergo, if they're set then it means "suppress" (off in the GUI toggle)
    # Since this is counter-intuitive from an API perspective and annoying
    # these will be inverted automatically

    def _has_flag(self, o: int) -> bool:
        return (self.value & o) != o

    def _set_flag(self, o: int, toggle: bool) -> None:
        if toggle is True:
            self.value &= ~o
        elif toggle is False:
            self.value |= o
        else:
            raise TypeError('Value to set for SystemChannelFlags must be a bool.')

    @flag_value
    def join_notifications(self):
        """:class:`bool`: Returns ``True`` if the system channel is used for member join notifications."""
        return 1

    @flag_value
    def premium_subscriptions(self):
        """:class:`bool`: Returns ``True`` if the system channel is used for "Nitro boosting" notifications."""
        return 2

    @flag_value
    def guild_reminder_notifications(self):
        """:class:`bool`: Returns ``True`` if the system channel is used for server setup helpful tips notifications.

        .. versionadded:: 2.0
        """
        return 4

    @flag_value
    def join_notification_replies(self):
        """:class:`bool`: Returns ``True`` if sticker reply button ("Wave to say hi!") is
        shown for member join notifications.

        .. versionadded:: 2.0
        """
        return 8

    @flag_value
    def role_subscription_purchase_notifications(self):
        """:class:`bool`: Returns ``True`` if role subscription purchase and renewal
        notifications are enabled.

        .. versionadded:: 2.2
        """
        return 16

    @flag_value
    def role_subscription_purchase_notification_replies(self):
        """:class:`bool`: Returns ``True`` if the role subscription notifications
        have a sticker reply button.

        .. versionadded:: 2.2
        """
        return 32


@fill_with_flags()
class MessageFlags(BaseFlags):
    r"""Wraps up a Discord Message flag value.

    See :class:`SystemChannelFlags`.

    .. container:: operations

        .. describe:: x == y

            Checks if two flags are equal.
        .. describe:: x != y

            Checks if two flags are not equal.

        .. describe:: x | y, x |= y

            Returns a MessageFlags instance with all enabled flags from
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x & y, x &= y

            Returns a MessageFlags instance with only flags enabled on
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x ^ y, x ^= y

            Returns a MessageFlags instance with only flags enabled on
            only one of x or y, not on both.

            .. versionadded:: 2.0

        .. describe:: ~x

            Returns a MessageFlags instance with all flags inverted from x.

            .. versionadded:: 2.0

        .. describe:: hash(x)

               Return the flag's hash.
        .. describe:: iter(x)

               Returns an iterator of ``(name, value)`` pairs. This allows it
               to be, for example, constructed as a dict or a list of pairs.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

            .. versionadded:: 2.0

    .. versionadded:: 1.3

    Attributes
    -----------
    value: :class:`int`
        The raw value. This value is a bit array field of a 53-bit integer
        representing the currently available flags. You should query
        flags via the properties rather than using this raw value.
    """

    __slots__ = ()

    @flag_value
    def crossposted(self):
        """:class:`bool`: Returns ``True`` if the message is the original crossposted message."""
        return 1

    @flag_value
    def is_crossposted(self):
        """:class:`bool`: Returns ``True`` if the message was crossposted from another channel."""
        return 2

    @flag_value
    def suppress_embeds(self):
        """:class:`bool`: Returns ``True`` if the message's embeds have been suppressed."""
        return 4

    @flag_value
    def source_message_deleted(self):
        """:class:`bool`: Returns ``True`` if the source message for this crosspost has been deleted."""
        return 8

    @flag_value
    def urgent(self):
        """:class:`bool`: Returns ``True`` if the source message is an urgent message.

        An urgent message is one sent by Discord Trust and Safety.
        """
        return 16

    @flag_value
    def has_thread(self):
        """:class:`bool`: Returns ``True`` if the source message is associated with a thread.

        .. versionadded:: 2.0
        """
        return 32

    @flag_value
    def ephemeral(self):
        """:class:`bool`: Returns ``True`` if the source message is ephemeral.

        .. versionadded:: 2.0
        """
        return 64

    @flag_value
    def loading(self):
        """:class:`bool`: Returns ``True`` if the message is an interaction response and the bot
        is "thinking".

        .. versionadded:: 2.0
        """
        return 128

    @flag_value
    def failed_to_mention_some_roles_in_thread(self):
        """:class:`bool`: Returns ``True`` if the message failed to mention some roles in a thread
        and add their members to the thread.

        .. versionadded:: 2.0
        """
        return 256

    @flag_value
    def suppress_notifications(self):
        """:class:`bool`: Returns ``True`` if the message will not trigger push and desktop notifications.

        .. versionadded:: 2.2
        """
        return 4096

    @alias_flag_value
    def silent(self):
        """:class:`bool`: Alias for :attr:`suppress_notifications`.

        .. versionadded:: 2.2
        """
        return 4096

    @flag_value
    def voice(self):
        """:class:`bool`: Returns ``True`` if the message is a voice message.

        .. versionadded:: 2.3
        """
        return 8192

    @flag_value
    def forwarded(self):
        """:class:`bool`: Returns ``True`` if the message is a forwarded message.

        .. versionadded:: 2.5
        """
        return 16384


@fill_with_flags()
class PublicUserFlags(BaseFlags):
    r"""Wraps up the Discord User Public flags.

    .. container:: operations

        .. describe:: x == y

            Checks if two PublicUserFlags are equal.
        .. describe:: x != y

            Checks if two PublicUserFlags are not equal.

        .. describe:: x | y, x |= y

            Returns a PublicUserFlags instance with all enabled flags from
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x & y, x &= y

            Returns a PublicUserFlags instance with only flags enabled on
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x ^ y, x ^= y

            Returns a PublicUserFlags instance with only flags enabled on
            only one of x or y, not on both.

            .. versionadded:: 2.0

        .. describe:: ~x

            Returns a PublicUserFlags instance with all flags inverted from x.

            .. versionadded:: 2.0

        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

            .. versionadded:: 2.0

    .. versionadded:: 1.4

    Attributes
    -----------
    value: :class:`int`
        The raw value. This value is a bit array field of a 53-bit integer
        representing the currently available flags. You should query
        flags via the properties rather than using this raw value.
    """

    __slots__ = ()

    @flag_value
    def staff(self):
        """:class:`bool`: Returns ``True`` if the user is a Discord Employee."""
        return UserFlags.staff.value

    @flag_value
    def partner(self):
        """:class:`bool`: Returns ``True`` if the user is a Discord Partner."""
        return UserFlags.partner.value

    @flag_value
    def hypesquad(self):
        """:class:`bool`: Returns ``True`` if the user is a HypeSquad Events member."""
        return UserFlags.hypesquad.value

    @flag_value
    def bug_hunter(self):
        """:class:`bool`: Returns ``True`` if the user is a Bug Hunter"""
        return UserFlags.bug_hunter.value

    @flag_value
    def hypesquad_bravery(self):
        """:class:`bool`: Returns ``True`` if the user is a HypeSquad Bravery member."""
        return UserFlags.hypesquad_bravery.value

    @flag_value
    def hypesquad_brilliance(self):
        """:class:`bool`: Returns ``True`` if the user is a HypeSquad Brilliance member."""
        return UserFlags.hypesquad_brilliance.value

    @flag_value
    def hypesquad_balance(self):
        """:class:`bool`: Returns ``True`` if the user is a HypeSquad Balance member."""
        return UserFlags.hypesquad_balance.value

    @flag_value
    def early_supporter(self):
        """:class:`bool`: Returns ``True`` if the user is an Early Supporter."""
        return UserFlags.early_supporter.value

    @flag_value
    def team_user(self):
        """:class:`bool`: Returns ``True`` if the user is a Team User."""
        return UserFlags.team_user.value

    @flag_value
    def system(self):
        """:class:`bool`: Returns ``True`` if the user is a system user (i.e. represents Discord officially)."""
        return UserFlags.system.value

    @flag_value
    def bug_hunter_level_2(self):
        """:class:`bool`: Returns ``True`` if the user is a Bug Hunter Level 2"""
        return UserFlags.bug_hunter_level_2.value

    @flag_value
    def verified_bot(self):
        """:class:`bool`: Returns ``True`` if the user is a Verified Bot."""
        return UserFlags.verified_bot.value

    @flag_value
    def verified_bot_developer(self):
        """:class:`bool`: Returns ``True`` if the user is an Early Verified Bot Developer."""
        return UserFlags.verified_bot_developer.value

    @alias_flag_value
    def early_verified_bot_developer(self):
        """:class:`bool`: An alias for :attr:`verified_bot_developer`.

        .. versionadded:: 1.5
        """
        return UserFlags.verified_bot_developer.value

    @flag_value
    def discord_certified_moderator(self):
        """:class:`bool`: Returns ``True`` if the user is a Discord Certified Moderator.

        .. versionadded:: 2.0
        """
        return UserFlags.discord_certified_moderator.value

    @flag_value
    def bot_http_interactions(self):
        """:class:`bool`: Returns ``True`` if the user is a bot that only uses HTTP interactions
        and is shown in the online member list.

        .. versionadded:: 2.0
        """
        return UserFlags.bot_http_interactions.value

    @flag_value
    def spammer(self):
        """:class:`bool`: Returns ``True`` if the user is flagged as a spammer by Discord.

        .. versionadded:: 2.0
        """
        return UserFlags.spammer.value

    @flag_value
    def active_developer(self):
        """:class:`bool`: Returns ``True`` if the user is an active developer.

        .. versionadded:: 2.1
        """
        return UserFlags.active_developer.value

    def all(self) -> List[UserFlags]:
        """List[:class:`UserFlags`]: Returns all public flags the user has."""
        return [public_flag for public_flag in UserFlags if self._has_flag(public_flag.value)]


@fill_with_flags()
class Intents(BaseFlags):
    r"""Wraps up a Discord gateway intent flag.

    Similar to :class:`Permissions`\, the properties provided are two way.
    You can set and retrieve individual bits using the properties as if they
    were regular bools.

    To construct an object you can pass keyword arguments denoting the flags
    to enable or disable.

    This is used to disable certain gateway features that are unnecessary to
    run your bot. To make use of this, it is passed to the ``intents`` keyword
    argument of :class:`Client`.

    .. versionadded:: 1.5

    .. container:: operations

        .. describe:: x == y

            Checks if two flags are equal.
        .. describe:: x != y

            Checks if two flags are not equal.

        .. describe:: x | y, x |= y

            Returns an Intents instance with all enabled flags from
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x & y, x &= y

            Returns an Intents instance with only flags enabled on
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x ^ y, x ^= y

            Returns an Intents instance with only flags enabled on
            only one of x or y, not on both.

            .. versionadded:: 2.0

        .. describe:: ~x

            Returns an Intents instance with all flags inverted from x.

            .. versionadded:: 2.0

        .. describe:: hash(x)

               Return the flag's hash.
        .. describe:: iter(x)

               Returns an iterator of ``(name, value)`` pairs. This allows it
               to be, for example, constructed as a dict or a list of pairs.

        .. describe:: bool(b)

            Returns whether any intent is enabled.

            .. versionadded:: 2.0

    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    def __init__(self, value: int = 0, **kwargs: bool) -> None:
        self.value: int = value
        for key, value in kwargs.items():
            if key not in self.VALID_FLAGS:
                raise TypeError(f'{key!r} is not a valid flag name.')
            setattr(self, key, value)

    @classmethod
    def all(cls: Type[Intents]) -> Intents:
        """A factory method that creates a :class:`Intents` with everything enabled."""
        value = reduce(lambda a, b: a | b, cls.VALID_FLAGS.values())
        self = cls.__new__(cls)
        self.value = value
        return self

    @classmethod
    def none(cls: Type[Intents]) -> Intents:
        """A factory method that creates a :class:`Intents` with everything disabled."""
        self = cls.__new__(cls)
        self.value = self.DEFAULT_VALUE
        return self

    @classmethod
    def default(cls: Type[Intents]) -> Intents:
        """A factory method that creates a :class:`Intents` with everything enabled
        except :attr:`presences`, :attr:`members`, and :attr:`message_content`.
        """
        self = cls.all()
        self.presences = False
        self.members = False
        self.message_content = False
        return self

    @flag_value
    def guilds(self):
        """:class:`bool`: Whether guild related events are enabled.

        This corresponds to the following events:

        - :func:`on_guild_join`
        - :func:`on_guild_remove`
        - :func:`on_guild_available`
        - :func:`on_guild_unavailable`
        - :func:`on_guild_channel_update`
        - :func:`on_guild_channel_create`
        - :func:`on_guild_channel_delete`
        - :func:`on_guild_channel_pins_update`
        - :func:`on_thread_create`
        - :func:`on_thread_join`
        - :func:`on_thread_update`
        - :func:`on_thread_delete`

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Client.guilds`
        - :class:`Guild` and all its attributes.
        - :meth:`Client.get_channel`
        - :meth:`Client.get_all_channels`

        It is highly advisable to leave this intent enabled for your bot to function.
        """
        return 1 << 0

    @flag_value
    def members(self):
        """:class:`bool`: Whether guild member related events are enabled.

        This corresponds to the following events:

        - :func:`on_member_join`
        - :func:`on_member_remove`
        - :func:`on_member_update`
        - :func:`on_user_update`
        - :func:`on_thread_member_join`
        - :func:`on_thread_member_remove`

        This also corresponds to the following attributes and classes in terms of cache:

        - :meth:`Client.get_all_members`
        - :meth:`Client.get_user`
        - :meth:`Guild.chunk`
        - :meth:`Guild.fetch_members`
        - :meth:`Guild.get_member`
        - :attr:`Guild.members`
        - :attr:`Member.roles`
        - :attr:`Member.nick`
        - :attr:`Member.premium_since`
        - :attr:`User.name`
        - :attr:`User.avatar`
        - :attr:`User.discriminator`
        - :attr:`User.global_name`

        For more information go to the :ref:`member intent documentation <need_members_intent>`.

        .. note::

            Currently, this requires opting in explicitly via the developer portal as well.
            Bots in over 100 guilds will need to apply to Discord for verification.
        """
        return 1 << 1

    @flag_value
    def moderation(self):
        """:class:`bool`: Whether guild moderation related events are enabled.

        This corresponds to the following events:

        - :func:`on_member_ban`
        - :func:`on_member_unban`
        - :func:`on_audit_log_entry_create`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 2

    @alias_flag_value
    def bans(self):
        """:class:`bool`: An alias of :attr:`moderation`.

        .. versionchanged:: 2.2
            Changed to an alias.
        """
        return 1 << 2

    @alias_flag_value
    def emojis(self):
        """:class:`bool`: Alias of :attr:`.expressions`.

        .. versionchanged:: 2.0
            Changed to an alias.
        """
        return 1 << 3

    @alias_flag_value
    def emojis_and_stickers(self):
        """:class:`bool`: Alias of :attr:`.expressions`.

        .. versionadded:: 2.0

        .. versionchanged:: 2.5
            Changed to an alias.
        """
        return 1 << 3

    @flag_value
    def expressions(self):
        """:class:`bool`: Whether guild emoji, sticker, and soundboard sound related events are enabled.

        .. versionadded:: 2.5

        This corresponds to the following events:

        - :func:`on_guild_emojis_update`
        - :func:`on_guild_stickers_update`
        - :func:`on_soundboard_sound_create`
        - :func:`on_soundboard_sound_update`
        - :func:`on_soundboard_sound_delete`

        This also corresponds to the following attributes and classes in terms of cache:

        - :class:`Emoji`
        - :class:`GuildSticker`
        - :class:`SoundboardSound`
        - :meth:`Client.get_emoji`
        - :meth:`Client.get_sticker`
        - :meth:`Client.get_soundboard_sound`
        - :meth:`Client.emojis`
        - :meth:`Client.stickers`
        - :meth:`Client.soundboard_sounds`
        - :attr:`Guild.emojis`
        - :attr:`Guild.stickers`
        - :attr:`Guild.soundboard_sounds`
        """
        return 1 << 3

    @flag_value
    def integrations(self):
        """:class:`bool`: Whether guild integration related events are enabled.

        This corresponds to the following events:

        - :func:`on_guild_integrations_update`
        - :func:`on_integration_create`
        - :func:`on_integration_update`
        - :func:`on_raw_integration_delete`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 4

    @flag_value
    def webhooks(self):
        """:class:`bool`: Whether guild webhook related events are enabled.

        This corresponds to the following events:

        - :func:`on_webhooks_update`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 5

    @flag_value
    def invites(self):
        """:class:`bool`: Whether guild invite related events are enabled.

        This corresponds to the following events:

        - :func:`on_invite_create`
        - :func:`on_invite_delete`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 6

    @flag_value
    def voice_states(self):
        """:class:`bool`: Whether guild voice state related events are enabled.

        This corresponds to the following events:

        - :func:`on_voice_state_update`

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`VoiceChannel.members`
        - :attr:`VoiceChannel.voice_states`
        - :attr:`Member.voice`

        .. note::

            This intent is required to connect to voice.
        """
        return 1 << 7

    @flag_value
    def presences(self):
        """:class:`bool`: Whether guild presence related events are enabled.

        This corresponds to the following events:

        - :func:`on_presence_update`

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Member.activities`
        - :attr:`Member.status`
        - :attr:`Member.raw_status`

        For more information go to the :ref:`presence intent documentation <need_presence_intent>`.

        .. note::

            Currently, this requires opting in explicitly via the developer portal as well.
            Bots in over 100 guilds will need to apply to Discord for verification.
        """
        return 1 << 8

    @alias_flag_value
    def messages(self):
        """:class:`bool`: Whether guild and direct message related events are enabled.

        This is a shortcut to set or get both :attr:`guild_messages` and :attr:`dm_messages`.

        This corresponds to the following events:

        - :func:`on_message` (both guilds and DMs)
        - :func:`on_message_edit` (both guilds and DMs)
        - :func:`on_message_delete` (both guilds and DMs)
        - :func:`on_raw_message_delete` (both guilds and DMs)
        - :func:`on_raw_message_edit` (both guilds and DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :class:`Message`
        - :attr:`Client.cached_messages`

        Note that due to an implicit relationship this also corresponds to the following events:

        - :func:`on_reaction_add` (both guilds and DMs)
        - :func:`on_reaction_remove` (both guilds and DMs)
        - :func:`on_reaction_clear` (both guilds and DMs)
        """
        return (1 << 9) | (1 << 12)

    @flag_value
    def guild_messages(self):
        """:class:`bool`: Whether guild message related events are enabled.

        See also :attr:`dm_messages` for DMs or :attr:`messages` for both.

        This corresponds to the following events:

        - :func:`on_message` (only for guilds)
        - :func:`on_message_edit` (only for guilds)
        - :func:`on_message_delete` (only for guilds)
        - :func:`on_raw_message_delete` (only for guilds)
        - :func:`on_raw_message_edit` (only for guilds)

        This also corresponds to the following attributes and classes in terms of cache:

        - :class:`Message`
        - :attr:`Client.cached_messages` (only for guilds)

        Note that due to an implicit relationship this also corresponds to the following events:

        - :func:`on_reaction_add` (only for guilds)
        - :func:`on_reaction_remove` (only for guilds)
        - :func:`on_reaction_clear` (only for guilds)
        """
        return 1 << 9

    @flag_value
    def dm_messages(self):
        """:class:`bool`: Whether direct message related events are enabled.

        See also :attr:`guild_messages` for guilds or :attr:`messages` for both.

        This corresponds to the following events:

        - :func:`on_message` (only for DMs)
        - :func:`on_message_edit` (only for DMs)
        - :func:`on_message_delete` (only for DMs)
        - :func:`on_raw_message_delete` (only for DMs)
        - :func:`on_raw_message_edit` (only for DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :class:`Message`
        - :attr:`Client.cached_messages` (only for DMs)

        Note that due to an implicit relationship this also corresponds to the following events:

        - :func:`on_reaction_add` (only for DMs)
        - :func:`on_reaction_remove` (only for DMs)
        - :func:`on_reaction_clear` (only for DMs)
        """
        return 1 << 12

    @alias_flag_value
    def reactions(self):
        """:class:`bool`: Whether guild and direct message reaction related events are enabled.

        This is a shortcut to set or get both :attr:`guild_reactions` and :attr:`dm_reactions`.

        This corresponds to the following events:

        - :func:`on_reaction_add` (both guilds and DMs)
        - :func:`on_reaction_remove` (both guilds and DMs)
        - :func:`on_reaction_clear` (both guilds and DMs)
        - :func:`on_raw_reaction_add` (both guilds and DMs)
        - :func:`on_raw_reaction_remove` (both guilds and DMs)
        - :func:`on_raw_reaction_clear` (both guilds and DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Message.reactions` (both guild and DM messages)
        """
        return (1 << 10) | (1 << 13)

    @flag_value
    def guild_reactions(self):
        """:class:`bool`: Whether guild message reaction related events are enabled.

        See also :attr:`dm_reactions` for DMs or :attr:`reactions` for both.

        This corresponds to the following events:

        - :func:`on_reaction_add` (only for guilds)
        - :func:`on_reaction_remove` (only for guilds)
        - :func:`on_reaction_clear` (only for guilds)
        - :func:`on_raw_reaction_add` (only for guilds)
        - :func:`on_raw_reaction_remove` (only for guilds)
        - :func:`on_raw_reaction_clear` (only for guilds)

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Message.reactions` (only for guild messages)
        """
        return 1 << 10

    @flag_value
    def dm_reactions(self):
        """:class:`bool`: Whether direct message reaction related events are enabled.

        See also :attr:`guild_reactions` for guilds or :attr:`reactions` for both.

        This corresponds to the following events:

        - :func:`on_reaction_add` (only for DMs)
        - :func:`on_reaction_remove` (only for DMs)
        - :func:`on_reaction_clear` (only for DMs)
        - :func:`on_raw_reaction_add` (only for DMs)
        - :func:`on_raw_reaction_remove` (only for DMs)
        - :func:`on_raw_reaction_clear` (only for DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Message.reactions` (only for DM messages)
        """
        return 1 << 13

    @alias_flag_value
    def typing(self):
        """:class:`bool`: Whether guild and direct message typing related events are enabled.

        This is a shortcut to set or get both :attr:`guild_typing` and :attr:`dm_typing`.

        This corresponds to the following events:

        - :func:`on_typing` (both guilds and DMs)

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return (1 << 11) | (1 << 14)

    @flag_value
    def guild_typing(self):
        """:class:`bool`: Whether guild and direct message typing related events are enabled.

        See also :attr:`dm_typing` for DMs or :attr:`typing` for both.

        This corresponds to the following events:

        - :func:`on_typing` (only for guilds)

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 11

    @flag_value
    def dm_typing(self):
        """:class:`bool`: Whether guild and direct message typing related events are enabled.

        See also :attr:`guild_typing` for guilds or :attr:`typing` for both.

        This corresponds to the following events:

        - :func:`on_typing` (only for DMs)

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 14

    @flag_value
    def message_content(self):
        """:class:`bool`: Whether message content, attachments, embeds and components will be available in messages
        which do not meet the following criteria:

        - The message was sent by the client
        - The message was sent in direct messages
        - The message mentions the client

        This applies to the following events:

        - :func:`on_message`
        - :func:`on_message_edit`
        - :func:`on_message_delete`
        - :func:`on_raw_message_edit`

        For more information go to the :ref:`message content intent documentation <need_message_content_intent>`.

        .. note::

            Currently, this requires opting in explicitly via the developer portal as well.
            Bots in over 100 guilds will need to apply to Discord for verification.

        .. versionadded:: 2.0
        """
        return 1 << 15

    @flag_value
    def guild_scheduled_events(self):
        """:class:`bool`: Whether guild scheduled event related events are enabled.

        This corresponds to the following events:

        - :func:`on_scheduled_event_create`
        - :func:`on_scheduled_event_update`
        - :func:`on_scheduled_event_delete`
        - :func:`on_scheduled_event_user_add`
        - :func:`on_scheduled_event_user_remove`

        .. versionadded:: 2.0
        """
        return 1 << 16

    @alias_flag_value
    def auto_moderation(self):
        """:class:`bool`: Whether auto moderation related events are enabled.

        This is a shortcut to set or get both :attr:`auto_moderation_configuration`
        and :attr:`auto_moderation_execution`.

        This corresponds to the following events:

        - :func:`on_automod_rule_create`
        - :func:`on_automod_rule_update`
        - :func:`on_automod_rule_delete`
        - :func:`on_automod_action`

        .. versionadded:: 2.0
        """
        return (1 << 20) | (1 << 21)

    @flag_value
    def auto_moderation_configuration(self):
        """:class:`bool`: Whether auto moderation configuration related events are enabled.

        This corresponds to the following events:

        - :func:`on_automod_rule_create`
        - :func:`on_automod_rule_update`
        - :func:`on_automod_rule_delete`

        .. versionadded:: 2.0
        """
        return 1 << 20

    @flag_value
    def auto_moderation_execution(self):
        """:class:`bool`: Whether auto moderation execution related events are enabled.

        This corresponds to the following events:
        - :func:`on_automod_action`

        .. versionadded:: 2.0
        """
        return 1 << 21

    @alias_flag_value
    def polls(self):
        """:class:`bool`: Whether guild and direct messages poll related events are enabled.

        This is a shortcut to set or get both :attr:`guild_polls` and :attr:`dm_polls`.

        This corresponds to the following events:

        - :func:`on_poll_vote_add` (both guilds and DMs)
        - :func:`on_poll_vote_remove` (both guilds and DMs)
        - :func:`on_raw_poll_vote_add` (both guilds and DMs)
        - :func:`on_raw_poll_vote_remove` (both guilds and DMs)

        .. versionadded:: 2.4
        """
        return (1 << 24) | (1 << 25)

    @flag_value
    def guild_polls(self):
        """:class:`bool`: Whether guild poll related events are enabled.

        See also :attr:`dm_polls` and :attr:`polls`.

        This corresponds to the following events:

        - :func:`on_poll_vote_add` (only for guilds)
        - :func:`on_poll_vote_remove` (only for guilds)
        - :func:`on_raw_poll_vote_add` (only for guilds)
        - :func:`on_raw_poll_vote_remove` (only for guilds)

        .. versionadded:: 2.4
        """
        return 1 << 24

    @flag_value
    def dm_polls(self):
        """:class:`bool`: Whether direct messages poll related events are enabled.

        See also :attr:`guild_polls` and :attr:`polls`.

        This corresponds to the following events:

        - :func:`on_poll_vote_add` (only for DMs)
        - :func:`on_poll_vote_remove` (only for DMs)
        - :func:`on_raw_poll_vote_add` (only for DMs)
        - :func:`on_raw_poll_vote_remove` (only for DMs)

        .. versionadded:: 2.4
        """
        return 1 << 25


@fill_with_flags()
class MemberCacheFlags(BaseFlags):
    """Controls the library's cache policy when it comes to members.

    This allows for finer grained control over what members are cached.
    Note that the bot's own member is always cached. This class is passed
    to the ``member_cache_flags`` parameter in :class:`Client`.

    Due to a quirk in how Discord works, in order to ensure proper cleanup
    of cache resources it is recommended to have :attr:`Intents.members`
    enabled. Otherwise the library cannot know when a member leaves a guild and
    is thus unable to cleanup after itself.

    To construct an object you can pass keyword arguments denoting the flags
    to enable or disable.

    The default value is all flags enabled.

    .. versionadded:: 1.5

    .. container:: operations

        .. describe:: x == y

            Checks if two flags are equal.
        .. describe:: x != y

            Checks if two flags are not equal.

        .. describe:: x | y, x |= y

            Returns a MemberCacheFlags instance with all enabled flags from
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x & y, x &= y

            Returns a MemberCacheFlags instance with only flags enabled on
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x ^ y, x ^= y

            Returns a MemberCacheFlags instance with only flags enabled on
            only one of x or y, not on both.

            .. versionadded:: 2.0

        .. describe:: ~x

            Returns a MemberCacheFlags instance with all flags inverted from x.

            .. versionadded:: 2.0

        .. describe:: hash(x)

               Return the flag's hash.
        .. describe:: iter(x)

               Returns an iterator of ``(name, value)`` pairs. This allows it
               to be, for example, constructed as a dict or a list of pairs.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

            .. versionadded:: 2.0

    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    def __init__(self, **kwargs: bool):
        bits = max(self.VALID_FLAGS.values()).bit_length()
        self.value: int = (1 << bits) - 1
        for key, value in kwargs.items():
            if key not in self.VALID_FLAGS:
                raise TypeError(f'{key!r} is not a valid flag name.')
            setattr(self, key, value)

    @classmethod
    def all(cls: Type[MemberCacheFlags]) -> MemberCacheFlags:
        """A factory method that creates a :class:`MemberCacheFlags` with everything enabled."""
        bits = max(cls.VALID_FLAGS.values()).bit_length()
        value = (1 << bits) - 1
        self = cls.__new__(cls)
        self.value = value
        return self

    @classmethod
    def none(cls: Type[MemberCacheFlags]) -> MemberCacheFlags:
        """A factory method that creates a :class:`MemberCacheFlags` with everything disabled."""
        self = cls.__new__(cls)
        self.value = self.DEFAULT_VALUE
        return self

    @property
    def _empty(self):
        return self.value == self.DEFAULT_VALUE

    @flag_value
    def voice(self):
        """:class:`bool`: Whether to cache members that are in voice.

        This requires :attr:`Intents.voice_states`.

        Members that leave voice are no longer cached.
        """
        return 1

    @flag_value
    def joined(self):
        """:class:`bool`: Whether to cache members that joined the guild
        or are chunked as part of the initial log in flow.

        This requires :attr:`Intents.members`.

        Members that leave the guild are no longer cached.
        """
        return 2

    @classmethod
    def from_intents(cls: Type[MemberCacheFlags], intents: Intents) -> MemberCacheFlags:
        """A factory method that creates a :class:`MemberCacheFlags` based on
        the currently selected :class:`Intents`.

        Parameters
        ------------
        intents: :class:`Intents`
            The intents to select from.

        Returns
        ---------
        :class:`MemberCacheFlags`
            The resulting member cache flags.
        """

        self = cls.none()
        if intents.members:
            self.joined = True
        if intents.voice_states:
            self.voice = True

        return self

    def _verify_intents(self, intents: Intents):
        if self.voice and not intents.voice_states:
            raise ValueError('MemberCacheFlags.voice requires Intents.voice_states')

        if self.joined and not intents.members:
            raise ValueError('MemberCacheFlags.joined requires Intents.members')

    @property
    def _voice_only(self):
        return self.value == 1


@fill_with_flags()
class ApplicationFlags(BaseFlags):
    r"""Wraps up the Discord Application flags.

    .. container:: operations

        .. describe:: x == y

            Checks if two ApplicationFlags are equal.
        .. describe:: x != y

            Checks if two ApplicationFlags are not equal.

        .. describe:: x | y, x |= y

            Returns an ApplicationFlags instance with all enabled flags from
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x & y, x &= y

            Returns an ApplicationFlags instance with only flags enabled on
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x ^ y, x ^= y

            Returns an ApplicationFlags instance with only flags enabled on
            only one of x or y, not on both.

            .. versionadded:: 2.0

        .. describe:: ~x

            Returns an ApplicationFlags instance with all flags inverted from x.

            .. versionadded:: 2.0

        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

    .. versionadded:: 2.0

    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    @flag_value
    def auto_mod_badge(self):
        """:class:`bool`: Returns ``True`` if the application uses at least 100 automod rules across all guilds.
        This shows up as a badge in the official client.

        .. versionadded:: 2.3
        """
        return 1 << 6

    @flag_value
    def gateway_presence(self):
        """:class:`bool`: Returns ``True`` if the application is verified and is allowed to
        receive presence information over the gateway.
        """
        return 1 << 12

    @flag_value
    def gateway_presence_limited(self):
        """:class:`bool`: Returns ``True`` if the application is allowed to receive limited
        presence information over the gateway.
        """
        return 1 << 13

    @flag_value
    def gateway_guild_members(self):
        """:class:`bool`: Returns ``True`` if the application is verified and is allowed to
        receive guild members information over the gateway.
        """
        return 1 << 14

    @flag_value
    def gateway_guild_members_limited(self):
        """:class:`bool`: Returns ``True`` if the application is allowed to receive limited
        guild members information over the gateway.
        """
        return 1 << 15

    @flag_value
    def verification_pending_guild_limit(self):
        """:class:`bool`: Returns ``True`` if the application is currently pending verification
        and has hit the guild limit.
        """
        return 1 << 16

    @flag_value
    def embedded(self):
        """:class:`bool`: Returns ``True`` if the application is embedded within the Discord client."""
        return 1 << 17

    @flag_value
    def gateway_message_content(self):
        """:class:`bool`: Returns ``True`` if the application is verified and is allowed to
        read message content in guilds."""
        return 1 << 18

    @flag_value
    def gateway_message_content_limited(self):
        """:class:`bool`: Returns ``True`` if the application is unverified and is allowed to
        read message content in guilds."""
        return 1 << 19

    @flag_value
    def app_commands_badge(self):
        """:class:`bool`: Returns ``True`` if the application has registered a global application
        command. This shows up as a badge in the official client."""
        return 1 << 23

    @flag_value
    def active(self):
        """:class:`bool`: Returns ``True`` if the application has had at least one global application
        command used in the last 30 days.

        .. versionadded:: 2.1
        """
        return 1 << 24


@fill_with_flags()
class ChannelFlags(BaseFlags):
    r"""Wraps up the Discord :class:`~discord.abc.GuildChannel` or :class:`Thread` flags.

    .. container:: operations

        .. describe:: x == y

            Checks if two channel flags are equal.
        .. describe:: x != y

            Checks if two channel flags are not equal.

        .. describe:: x | y, x |= y

            Returns a ChannelFlags instance with all enabled flags from
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x & y, x &= y

            Returns a ChannelFlags instance with only flags enabled on
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x ^ y, x ^= y

            Returns a ChannelFlags instance with only flags enabled on
            only one of x or y, not on both.

            .. versionadded:: 2.0

        .. describe:: ~x

            Returns a ChannelFlags instance with all flags inverted from x.

            .. versionadded:: 2.0

        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

    .. versionadded:: 2.0

    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    @flag_value
    def pinned(self):
        """:class:`bool`: Returns ``True`` if the thread is pinned to the forum channel."""
        return 1 << 1

    @flag_value
    def require_tag(self):
        """:class:`bool`: Returns ``True`` if a tag is required to be specified when creating a thread
        in a :class:`ForumChannel`.

        .. versionadded:: 2.1
        """
        return 1 << 4

    @flag_value
    def hide_media_download_options(self):
        """:class:`bool`: Returns ``True`` if the client hides embedded media download options in a :class:`ForumChannel`.
        Only available in media channels.

        .. versionadded:: 2.4
        """
        return 1 << 15


class ArrayFlags(BaseFlags):
    @classmethod
    def _from_value(cls: Type[Self], value: Sequence[int]) -> Self:
        self = cls.__new__(cls)
        # This is a micro-optimization given the frequency this object can be created.
        # (1).__lshift__ is used in place of lambda x: 1 << x
        # prebinding to a method of a constant rather than define a lambda.
        # Pairing this with map, is essentially equivalent to (1 << x for x in value)
        # reduction using operator.or_ instead of defining a lambda each call
        # Discord sends these starting with a value of 1
        # Rather than subtract 1 from each element prior to left shift,
        # we shift right by 1 once at the end.
        self.value = reduce(or_, map((1).__lshift__, value), 0) >> 1
        return self

    def to_array(self, *, offset: int = 0) -> List[int]:
        return [i + offset for i in range(self.value.bit_length()) if self.value & (1 << i)]

    @classmethod
    def all(cls: Type[Self]) -> Self:
        """A factory method that creates an instance of ArrayFlags with everything enabled."""
        bits = max(cls.VALID_FLAGS.values()).bit_length()
        value = (1 << bits) - 1
        self = cls.__new__(cls)
        self.value = value
        return self

    @classmethod
    def none(cls: Type[Self]) -> Self:
        """A factory method that creates an instance of ArrayFlags with everything disabled."""
        self = cls.__new__(cls)
        self.value = self.DEFAULT_VALUE
        return self


@fill_with_flags()
class AutoModPresets(ArrayFlags):
    r"""Wraps up the Discord :class:`AutoModRule` presets.

    .. versionadded:: 2.0


    .. container:: operations

        .. describe:: x == y

            Checks if two AutoMod preset flags are equal.

        .. describe:: x != y

            Checks if two AutoMod preset flags are not equal.

        .. describe:: x | y, x |= y

            Returns an AutoModPresets instance with all enabled flags from
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x & y, x &= y

            Returns an AutoModPresets instance with only flags enabled on
            both x and y.

            .. versionadded:: 2.0

        .. describe:: x ^ y, x ^= y

            Returns an AutoModPresets instance with only flags enabled on
            only one of x or y, not on both.

            .. versionadded:: 2.0

        .. describe:: ~x

            Returns an AutoModPresets instance with all flags inverted from x.

            .. versionadded:: 2.0

        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    def to_array(self) -> List[int]:
        return super().to_array(offset=1)

    @flag_value
    def profanity(self):
        """:class:`bool`: Whether to use the preset profanity filter."""
        return 1 << 0

    @flag_value
    def sexual_content(self):
        """:class:`bool`: Whether to use the preset sexual content filter."""
        return 1 << 1

    @flag_value
    def slurs(self):
        """:class:`bool`: Whether to use the preset slurs filter."""
        return 1 << 2


@fill_with_flags()
class AppCommandContext(ArrayFlags):
    r"""Wraps up the Discord :class:`~discord.app_commands.Command` execution context.

    .. versionadded:: 2.4

    .. container:: operations

        .. describe:: x == y

            Checks if two AppCommandContext flags are equal.

        .. describe:: x != y

            Checks if two AppCommandContext flags are not equal.

        .. describe:: x | y, x |= y

            Returns an AppCommandContext instance with all enabled flags from
            both x and y.

        .. describe:: x & y, x &= y

            Returns an AppCommandContext instance with only flags enabled on
            both x and y.

        .. describe:: x ^ y, x ^= y

            Returns an AppCommandContext instance with only flags enabled on
            only one of x or y, not on both.

        .. describe:: ~x

            Returns an AppCommandContext instance with all flags inverted from x

        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    DEFAULT_VALUE = 3

    @flag_value
    def guild(self):
        """:class:`bool`: Whether the context allows usage in a guild."""
        return 1 << 0

    @flag_value
    def dm_channel(self):
        """:class:`bool`: Whether the context allows usage in a DM channel."""
        return 1 << 1

    @flag_value
    def private_channel(self):
        """:class:`bool`: Whether the context allows usage in a DM or a GDM channel."""
        return 1 << 2


@fill_with_flags()
class AppInstallationType(ArrayFlags):
    r"""Represents the installation location of an application command.

    .. versionadded:: 2.4

    .. container:: operations

        .. describe:: x == y

            Checks if two AppInstallationType flags are equal.

        .. describe:: x != y

            Checks if two AppInstallationType flags are not equal.

        .. describe:: x | y, x |= y

            Returns an AppInstallationType instance with all enabled flags from
            both x and y.

        .. describe:: x & y, x &= y

            Returns an AppInstallationType instance with only flags enabled on
            both x and y.

        .. describe:: x ^ y, x ^= y

            Returns an AppInstallationType instance with only flags enabled on
            only one of x or y, not on both.

        .. describe:: ~x

            Returns an AppInstallationType instance with all flags inverted from x

        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    @flag_value
    def guild(self):
        """:class:`bool`: Whether the integration is a guild install."""
        return 1 << 0

    @flag_value
    def user(self):
        """:class:`bool`: Whether the integration is a user install."""
        return 1 << 1


@fill_with_flags()
class MemberFlags(BaseFlags):
    r"""Wraps up the Discord Guild Member flags

    .. versionadded:: 2.2

    .. container:: operations

        .. describe:: x == y

            Checks if two MemberFlags are equal.

        .. describe:: x != y

            Checks if two MemberFlags are not equal.

        .. describe:: x | y, x |= y

            Returns a MemberFlags instance with all enabled flags from
            both x and y.

        .. describe:: x & y, x &= y

            Returns a MemberFlags instance with only flags enabled on
            both x and y.

        .. describe:: x ^ y, x ^= y

            Returns a MemberFlags instance with only flags enabled on
            only one of x or y, not on both.

        .. describe:: ~x

            Returns a MemberFlags instance with all flags inverted from x.

        .. describe:: hash(x)

            Return the flag's hash.

        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.


    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    @flag_value
    def did_rejoin(self):
        """:class:`bool`: Returns ``True`` if the member left and rejoined the :attr:`~discord.Member.guild`."""
        return 1 << 0

    @flag_value
    def completed_onboarding(self):
        """:class:`bool`: Returns ``True`` if the member has completed onboarding."""
        return 1 << 1

    @flag_value
    def bypasses_verification(self):
        """:class:`bool`: Returns ``True`` if the member can bypass the guild verification requirements."""
        return 1 << 2

    @flag_value
    def started_onboarding(self):
        """:class:`bool`: Returns ``True`` if the member has started onboarding."""
        return 1 << 3

    @flag_value
    def guest(self):
        """:class:`bool`: Returns ``True`` if the member is a guest and can only access
        the voice channel they were invited to.

        .. versionadded:: 2.5
        """
        return 1 << 4

    @flag_value
    def started_home_actions(self):
        """:class:`bool`: Returns ``True`` if the member has started Server Guide new member actions.

        .. versionadded:: 2.5
        """
        return 1 << 5

    @flag_value
    def completed_home_actions(self):
        """:class:`bool`: Returns ``True`` if the member has completed Server Guide new member actions.

        .. versionadded:: 2.5
        """
        return 1 << 6

    @flag_value
    def automod_quarantined_username(self):
        """:class:`bool`: Returns ``True`` if the member's username, nickname, or global name has been
        blocked by AutoMod.

        .. versionadded:: 2.5
        """
        return 1 << 7

    @flag_value
    def dm_settings_upsell_acknowledged(self):
        """:class:`bool`: Returns ``True`` if the member has dismissed the DM settings upsell.

        .. versionadded:: 2.5
        """
        return 1 << 9


@fill_with_flags()
class AttachmentFlags(BaseFlags):
    r"""Wraps up the Discord Attachment flags

    .. versionadded:: 2.4

    .. container:: operations

        .. describe:: x == y

            Checks if two AttachmentFlags are equal.

        .. describe:: x != y

            Checks if two AttachmentFlags are not equal.

        .. describe:: x | y, x |= y

            Returns a AttachmentFlags instance with all enabled flags from
            both x and y.

        .. describe:: x & y, x &= y

            Returns a AttachmentFlags instance with only flags enabled on
            both x and y.

        .. describe:: x ^ y, x ^= y

            Returns a AttachmentFlags instance with only flags enabled on
            only one of x or y, not on both.

        .. describe:: ~x

            Returns a AttachmentFlags instance with all flags inverted from x.

        .. describe:: hash(x)

            Return the flag's hash.

        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.


    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    @flag_value
    def clip(self):
        """:class:`bool`: Returns ``True`` if the attachment is a clip."""
        return 1 << 0

    @flag_value
    def thumbnail(self):
        """:class:`bool`: Returns ``True`` if the attachment is a thumbnail."""
        return 1 << 1

    @flag_value
    def remix(self):
        """:class:`bool`: Returns ``True`` if the attachment has been edited using the remix feature."""
        return 1 << 2

    @flag_value
    def spoiler(self):
        """:class:`bool`: Returns ``True`` if the attachment was marked as a spoiler."""
        return 1 << 3

    @flag_value
    def contains_explicit_media(self):
        """:class:`bool`: Returns ``True`` if the attachment was flagged as sensitive content."""
        return 1 << 4

    @flag_value
    def animated(self):
        """:class:`bool`: Returns ``True`` if the attachment is an animated image."""
        return 1 << 5


@fill_with_flags()
class RoleFlags(BaseFlags):
    r"""Wraps up the Discord Role flags

    .. versionadded:: 2.4

    .. container:: operations

        .. describe:: x == y

            Checks if two RoleFlags are equal.

        .. describe:: x != y

            Checks if two RoleFlags are not equal.

        .. describe:: x | y, x |= y

            Returns a RoleFlags instance with all enabled flags from
            both x and y.

        .. describe:: x & y, x &= y

            Returns a RoleFlags instance with only flags enabled on
            both x and y.

        .. describe:: x ^ y, x ^= y

            Returns a RoleFlags instance with only flags enabled on
            only one of x or y, not on both.

        .. describe:: ~x

            Returns a RoleFlags instance with all flags inverted from x.

        .. describe:: hash(x)

            Return the flag's hash.

        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.


    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    @flag_value
    def in_prompt(self):
        """:class:`bool`: Returns ``True`` if the role can be selected by members in an onboarding prompt."""
        return 1 << 0


@fill_with_flags()
class SKUFlags(BaseFlags):
    r"""Wraps up the Discord SKU flags

    .. versionadded:: 2.4

    .. container:: operations

        .. describe:: x == y

            Checks if two SKUFlags are equal.

        .. describe:: x != y

            Checks if two SKUFlags are not equal.

        .. describe:: x | y, x |= y

            Returns a SKUFlags instance with all enabled flags from
            both x and y.

        .. describe:: x & y, x &= y

            Returns a SKUFlags instance with only flags enabled on
            both x and y.

        .. describe:: x ^ y, x ^= y

            Returns a SKUFlags instance with only flags enabled on
            only one of x or y, not on both.

        .. describe:: ~x

            Returns a SKUFlags instance with all flags inverted from x.

        .. describe:: hash(x)

            Return the flag's hash.

        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.


    Attributes
    -----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    @flag_value
    def available(self):
        """:class:`bool`: Returns ``True`` if the SKU is available for purchase."""
        return 1 << 2

    @flag_value
    def guild_subscription(self):
        """:class:`bool`: Returns ``True`` if the SKU is a guild subscription."""
        return 1 << 7

    @flag_value
    def user_subscription(self):
        """:class:`bool`: Returns ``True`` if the SKU is a user subscription."""
        return 1 << 8


@fill_with_flags()
class EmbedFlags(BaseFlags):
    r"""Wraps up the Discord Embed flags

    .. versionadded:: 2.5

    .. container:: operations

        .. describe:: x == y

            Checks if two EmbedFlags are equal.

        .. describe:: x != y

            Checks if two EmbedFlags are not equal.

        .. describe:: x | y, x |= y

            Returns an EmbedFlags instance with all enabled flags from
            both x and y.

        .. describe:: x ^ y, x ^= y

            Returns an EmbedFlags instance with only flags enabled on
            only one of x or y, not on both.

        .. describe:: ~x

            Returns an EmbedFlags instance with all flags inverted from x.

        .. describe:: hash(x)

            Returns the flag's hash.

        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        .. describe:: bool(b)

            Returns whether any flag is set to ``True``.

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    @flag_value
    def contains_explicit_media(self):
        """:class:`bool`: Returns ``True`` if the embed was flagged as sensitive content."""
        return 1 << 4

    @flag_value
    def content_inventory_entry(self):
        """:class:`bool`: Returns ``True`` if the embed is a reply to an activity card, and is no
        longer displayed.
        """
        return 1 << 5
