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

from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Mapping,
    NamedTuple,
    Optional,
    TYPE_CHECKING,
    Sequence,
    Tuple,
    TypeVar,
    Union,
    overload,
)
import datetime

import discord.abc
from .scheduled_event import ScheduledEvent
from .permissions import PermissionOverwrite, Permissions
from .enums import (
    ChannelType,
    ForumLayoutType,
    ForumOrderType,
    PrivacyLevel,
    try_enum,
    VideoQualityMode,
    EntityType,
    VoiceChannelEffectAnimationType,
)
from .mixins import Hashable
from . import utils
from .utils import MISSING
from .asset import Asset
from .errors import ClientException
from .stage_instance import StageInstance
from .threads import Thread
from .partial_emoji import _EmojiTag, PartialEmoji
from .flags import ChannelFlags, MessageFlags
from .http import handle_message_parameters
from .object import Object
from .soundboard import BaseSoundboardSound, SoundboardDefaultSound

__all__ = (
    'TextChannel',
    'VoiceChannel',
    'StageChannel',
    'DMChannel',
    'CategoryChannel',
    'ForumTag',
    'ForumChannel',
    'GroupChannel',
    'PartialMessageable',
    'VoiceChannelEffect',
    'VoiceChannelSoundEffect',
)

if TYPE_CHECKING:
    from typing_extensions import Self

    from .types.threads import ThreadArchiveDuration
    from .role import Role
    from .member import Member, VoiceState
    from .abc import Snowflake, SnowflakeTime
    from .embeds import Embed
    from .message import Message, PartialMessage, EmojiInputType
    from .mentions import AllowedMentions
    from .webhook import Webhook
    from .state import ConnectionState
    from .sticker import GuildSticker, StickerItem
    from .file import File
    from .user import ClientUser, User, BaseUser
    from .guild import Guild, GuildChannel as GuildChannelType
    from .ui.view import View
    from .types.channel import (
        TextChannel as TextChannelPayload,
        NewsChannel as NewsChannelPayload,
        VoiceChannel as VoiceChannelPayload,
        StageChannel as StageChannelPayload,
        DMChannel as DMChannelPayload,
        CategoryChannel as CategoryChannelPayload,
        GroupDMChannel as GroupChannelPayload,
        ForumChannel as ForumChannelPayload,
        MediaChannel as MediaChannelPayload,
        ForumTag as ForumTagPayload,
        VoiceChannelEffect as VoiceChannelEffectPayload,
    )
    from .types.snowflake import SnowflakeList
    from .types.soundboard import BaseSoundboardSound as BaseSoundboardSoundPayload
    from .soundboard import SoundboardSound

    OverwriteKeyT = TypeVar('OverwriteKeyT', Role, BaseUser, Object, Union[Role, Member, Object])


class ThreadWithMessage(NamedTuple):
    thread: Thread
    message: Message


class VoiceChannelEffectAnimation(NamedTuple):
    id: int
    type: VoiceChannelEffectAnimationType


class VoiceChannelSoundEffect(BaseSoundboardSound):
    """Represents a Discord voice channel sound effect.

    .. versionadded:: 2.5

    .. container:: operations

        .. describe:: x == y

            Checks if two sound effects are equal.

        .. describe:: x != y

            Checks if two sound effects are not equal.

        .. describe:: hash(x)

            Returns the sound effect's hash.

    Attributes
    ------------
    id: :class:`int`
        The ID of the sound.
    volume: :class:`float`
        The volume of the sound as floating point percentage (e.g. ``1.0`` for 100%).
    """

    __slots__ = ('_state',)

    def __init__(self, *, state: ConnectionState, id: int, volume: float):
        data: BaseSoundboardSoundPayload = {
            'sound_id': id,
            'volume': volume,
        }
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} volume={self.volume}>"

    @property
    def created_at(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: Returns the snowflake's creation time in UTC.
        Returns ``None`` if it's a default sound."""
        if self.is_default():
            return None
        else:
            return utils.snowflake_time(self.id)

    def is_default(self) -> bool:
        """:class:`bool`: Whether it's a default sound or not."""
        # if it's smaller than the Discord Epoch it cannot be a snowflake
        return self.id < utils.DISCORD_EPOCH


class VoiceChannelEffect:
    """Represents a Discord voice channel effect.

    .. versionadded:: 2.5

    Attributes
    ------------
    channel: :class:`VoiceChannel`
        The channel in which the effect is sent.
    user: Optional[:class:`Member`]
        The user who sent the effect. ``None`` if not found in cache.
    animation: Optional[:class:`VoiceChannelEffectAnimation`]
        The animation the effect has. Returns ``None`` if the effect has no animation.
    emoji: Optional[:class:`PartialEmoji`]
        The emoji of the effect.
    sound: Optional[:class:`VoiceChannelSoundEffect`]
        The sound of the effect. Returns ``None`` if it's an emoji effect.
    """

    __slots__ = ('channel', 'user', 'animation', 'emoji', 'sound')

    def __init__(self, *, state: ConnectionState, data: VoiceChannelEffectPayload, guild: Guild):
        self.channel: VoiceChannel = guild.get_channel(int(data['channel_id']))  # type: ignore # will always be a VoiceChannel
        self.user: Optional[Member] = guild.get_member(int(data['user_id']))
        self.animation: Optional[VoiceChannelEffectAnimation] = None

        animation_id = data.get('animation_id')
        if animation_id is not None:
            animation_type = try_enum(VoiceChannelEffectAnimationType, data['animation_type'])  # type: ignore # cannot be None here
            self.animation = VoiceChannelEffectAnimation(id=animation_id, type=animation_type)

        emoji = data.get('emoji')
        self.emoji: Optional[PartialEmoji] = PartialEmoji.from_dict(emoji) if emoji is not None else None
        self.sound: Optional[VoiceChannelSoundEffect] = None

        sound_id: Optional[int] = utils._get_as_snowflake(data, 'sound_id')
        if sound_id is not None:
            sound_volume = data.get('sound_volume') or 0.0
            self.sound = VoiceChannelSoundEffect(state=state, id=sound_id, volume=sound_volume)

    def __repr__(self) -> str:
        attrs = [
            ('channel', self.channel),
            ('user', self.user),
            ('animation', self.animation),
            ('emoji', self.emoji),
            ('sound', self.sound),
        ]
        inner = ' '.join('%s=%r' % t for t in attrs)
        return f"<{self.__class__.__name__} {inner}>"

    def is_sound(self) -> bool:
        """:class:`bool`: Whether the effect is a sound or not."""
        return self.sound is not None


class TextChannel(discord.abc.Messageable, discord.abc.GuildChannel, Hashable):
    """Represents a Discord guild text channel.

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
    name: :class:`str`
        The channel name.
    guild: :class:`Guild`
        The guild the channel belongs to.
    id: :class:`int`
        The channel ID.
    category_id: Optional[:class:`int`]
        The category channel ID this channel belongs to, if applicable.
    topic: Optional[:class:`str`]
        The channel's topic. ``None`` if it doesn't exist.
    position: :class:`int`
        The position in the channel list. This is a number that starts at 0. e.g. the
        top channel is position 0.
    last_message_id: Optional[:class:`int`]
        The last message ID of the message sent to this channel. It may
        *not* point to an existing or valid message.
    slowmode_delay: :class:`int`
        The number of seconds a member must wait between sending messages
        in this channel. A value of ``0`` denotes that it is disabled.
        Bots and users with :attr:`~Permissions.manage_channels` or
        :attr:`~Permissions.manage_messages` bypass slowmode.
    nsfw: :class:`bool`
        If the channel is marked as "not safe for work" or "age restricted".
    default_auto_archive_duration: :class:`int`
        The default auto archive duration in minutes for threads created in this channel.

        .. versionadded:: 2.0
    default_thread_slowmode_delay: :class:`int`
        The default slowmode delay in seconds for threads created in this channel.

        .. versionadded:: 2.3
    """

    __slots__ = (
        'name',
        'id',
        'guild',
        'topic',
        '_state',
        'nsfw',
        'category_id',
        'position',
        'slowmode_delay',
        '_overwrites',
        '_type',
        'last_message_id',
        'default_auto_archive_duration',
        'default_thread_slowmode_delay',
    )

    def __init__(self, *, state: ConnectionState, guild: Guild, data: Union[TextChannelPayload, NewsChannelPayload]):
        self._state: ConnectionState = state
        self.id: int = int(data['id'])
        self._type: Literal[0, 5] = data['type']
        self._update(guild, data)

    def __repr__(self) -> str:
        attrs = [
            ('id', self.id),
            ('name', self.name),
            ('position', self.position),
            ('nsfw', self.nsfw),
            ('news', self.is_news()),
            ('category_id', self.category_id),
        ]
        joined = ' '.join('%s=%r' % t for t in attrs)
        return f'<{self.__class__.__name__} {joined}>'

    def _update(self, guild: Guild, data: Union[TextChannelPayload, NewsChannelPayload]) -> None:
        self.guild: Guild = guild
        self.name: str = data['name']
        self.category_id: Optional[int] = utils._get_as_snowflake(data, 'parent_id')
        self.topic: Optional[str] = data.get('topic')
        self.position: int = data['position']
        self.nsfw: bool = data.get('nsfw', False)
        # Does this need coercion into `int`? No idea yet.
        self.slowmode_delay: int = data.get('rate_limit_per_user', 0)
        self.default_auto_archive_duration: ThreadArchiveDuration = data.get('default_auto_archive_duration', 1440)
        self.default_thread_slowmode_delay: int = data.get('default_thread_rate_limit_per_user', 0)
        self._type: Literal[0, 5] = data.get('type', self._type)
        self.last_message_id: Optional[int] = utils._get_as_snowflake(data, 'last_message_id')
        self._fill_overwrites(data)

    async def _get_channel(self) -> Self:
        return self

    @property
    def type(self) -> Literal[ChannelType.text, ChannelType.news]:
        """:class:`ChannelType`: The channel's Discord type."""
        if self._type == 0:
            return ChannelType.text
        return ChannelType.news

    @property
    def _sorting_bucket(self) -> int:
        return ChannelType.text.value

    @property
    def _scheduled_event_entity_type(self) -> Optional[EntityType]:
        return None

    @utils.copy_doc(discord.abc.GuildChannel.permissions_for)
    def permissions_for(self, obj: Union[Member, Role], /) -> Permissions:
        base = super().permissions_for(obj)
        self._apply_implicit_permissions(base)

        # text channels do not have voice related permissions
        denied = Permissions.voice()
        base.value &= ~denied.value
        return base

    @property
    def members(self) -> List[Member]:
        """List[:class:`Member`]: Returns all members that can see this channel."""
        return [m for m in self.guild.members if self.permissions_for(m).read_messages]

    @property
    def threads(self) -> List[Thread]:
        """List[:class:`Thread`]: Returns all the threads that you can see.

        .. versionadded:: 2.0
        """
        return [thread for thread in self.guild._threads.values() if thread.parent_id == self.id]

    def is_nsfw(self) -> bool:
        """:class:`bool`: Checks if the channel is NSFW."""
        return self.nsfw

    def is_news(self) -> bool:
        """:class:`bool`: Checks if the channel is a news channel."""
        return self._type == ChannelType.news.value

    @property
    def last_message(self) -> Optional[Message]:
        """Retrieves the last message from this channel in cache.

        The message might not be valid or point to an existing message.

        .. admonition:: Reliable Fetching
            :class: helpful

            For a slightly more reliable method of fetching the
            last message, consider using either :meth:`history`
            or :meth:`fetch_message` with the :attr:`last_message_id`
            attribute.

        Returns
        ---------
        Optional[:class:`Message`]
            The last message in this channel or ``None`` if not found.
        """
        return self._state._get_message(self.last_message_id) if self.last_message_id else None

    @overload
    async def edit(self) -> Optional[TextChannel]:
        ...

    @overload
    async def edit(self, *, position: int, reason: Optional[str] = ...) -> None:
        ...

    @overload
    async def edit(
        self,
        *,
        reason: Optional[str] = ...,
        name: str = ...,
        topic: str = ...,
        position: int = ...,
        nsfw: bool = ...,
        sync_permissions: bool = ...,
        category: Optional[CategoryChannel] = ...,
        slowmode_delay: int = ...,
        default_auto_archive_duration: ThreadArchiveDuration = ...,
        default_thread_slowmode_delay: int = ...,
        type: ChannelType = ...,
        overwrites: Mapping[OverwriteKeyT, PermissionOverwrite] = ...,
    ) -> TextChannel:
        ...

    async def edit(self, *, reason: Optional[str] = None, **options: Any) -> Optional[TextChannel]:
        """|coro|

        Edits the channel.

        You must have :attr:`~Permissions.manage_channels` to do this.

        .. versionchanged:: 1.3
            The ``overwrites`` keyword-only parameter was added.

        .. versionchanged:: 1.4
            The ``type`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited channel is returned instead.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` or
            :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The new channel name.
        topic: :class:`str`
            The new channel's topic.
        position: :class:`int`
            The new channel's position.
        nsfw: :class:`bool`
            To mark the channel as NSFW or not.
        sync_permissions: :class:`bool`
            Whether to sync permissions with the channel's new or pre-existing
            category. Defaults to ``False``.
        category: Optional[:class:`CategoryChannel`]
            The new category for this channel. Can be ``None`` to remove the
            category.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for user in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
        type: :class:`ChannelType`
            Change the type of this text channel. Currently, only conversion between
            :attr:`ChannelType.text` and :attr:`ChannelType.news` is supported. This
            is only available to guilds that contain ``NEWS`` in :attr:`Guild.features`.
        reason: Optional[:class:`str`]
            The reason for editing this channel. Shows up on the audit log.
        overwrites: :class:`Mapping`
            A :class:`Mapping` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply to the channel.
        default_auto_archive_duration: :class:`int`
            The new default auto archive duration in minutes for threads created in this channel.
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.

            .. versionadded:: 2.0
        default_thread_slowmode_delay: :class:`int`
            The new default slowmode delay in seconds for threads created in this channel.

            .. versionadded:: 2.3
        Raises
        ------
        ValueError
            The new ``position`` is less than 0 or greater than the number of channels.
        TypeError
            The permission overwrite information is not in proper form.
        Forbidden
            You do not have permissions to edit the channel.
        HTTPException
            Editing the channel failed.

        Returns
        --------
        Optional[:class:`.TextChannel`]
            The newly edited text channel. If the edit was only positional
            then ``None`` is returned instead.
        """

        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore

    @utils.copy_doc(discord.abc.GuildChannel.clone)
    async def clone(
        self,
        *,
        name: Optional[str] = None,
        category: Optional[CategoryChannel] = None,
        reason: Optional[str] = None,
    ) -> TextChannel:
        base: Dict[Any, Any] = {
            'topic': self.topic,
            'nsfw': self.nsfw,
            'default_auto_archive_duration': self.default_auto_archive_duration,
            'default_thread_rate_limit_per_user': self.default_thread_slowmode_delay,
        }
        if not self.is_news():
            base['rate_limit_per_user'] = self.slowmode_delay
        return await self._clone_impl(
            base,
            name=name,
            category=category,
            reason=reason,
        )

    async def delete_messages(self, messages: Iterable[Snowflake], *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes a list of messages. This is similar to :meth:`Message.delete`
        except it bulk deletes multiple messages.

        As a special case, if the number of messages is 0, then nothing
        is done. If the number of messages is 1 then single message
        delete is done. If it's more than two, then bulk delete is used.

        You cannot bulk delete more than 100 messages or messages that
        are older than 14 days old.

        You must have :attr:`~Permissions.manage_messages` to do this.

        .. versionchanged:: 2.0

            ``messages`` parameter is now positional-only.

            The ``reason`` keyword-only parameter was added.

        Parameters
        -----------
        messages: Iterable[:class:`abc.Snowflake`]
            An iterable of messages denoting which ones to bulk delete.
        reason: Optional[:class:`str`]
            The reason for deleting the messages. Shows up on the audit log.

        Raises
        ------
        ClientException
            The number of messages to delete was more than 100.
        Forbidden
            You do not have proper permissions to delete the messages.
        NotFound
            If single delete, then the message was already deleted.
        HTTPException
            Deleting the messages failed.
        """
        if not isinstance(messages, (list, tuple)):
            messages = list(messages)

        if len(messages) == 0:
            return  # do nothing

        if len(messages) == 1:
            message_id: int = messages[0].id
            await self._state.http.delete_message(self.id, message_id)
            return

        if len(messages) > 100:
            raise ClientException('Can only bulk delete messages up to 100 messages')

        message_ids: SnowflakeList = [m.id for m in messages]
        await self._state.http.delete_messages(self.id, message_ids, reason=reason)

    async def purge(
        self,
        *,
        limit: Optional[int] = 100,
        check: Callable[[Message], bool] = MISSING,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
        around: Optional[SnowflakeTime] = None,
        oldest_first: Optional[bool] = None,
        bulk: bool = True,
        reason: Optional[str] = None,
    ) -> List[Message]:
        """|coro|

        Purges a list of messages that meet the criteria given by the predicate
        ``check``. If a ``check`` is not provided then all messages are deleted
        without discrimination.

        You must have :attr:`~Permissions.manage_messages` to
        delete messages even if they are your own.
        Having :attr:`~Permissions.read_message_history` is
        also needed to retrieve message history.

        .. versionchanged:: 2.0

            The ``reason`` keyword-only parameter was added.

        Examples
        ---------

        Deleting bot's messages ::

            def is_me(m):
                return m.author == client.user

            deleted = await channel.purge(limit=100, check=is_me)
            await channel.send(f'Deleted {len(deleted)} message(s)')

        Parameters
        -----------
        limit: Optional[:class:`int`]
            The number of messages to search through. This is not the number
            of messages that will be deleted, though it can be.
        check: Callable[[:class:`Message`], :class:`bool`]
            The function used to check if a message should be deleted.
            It must take a :class:`Message` as its sole parameter.
        before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``before`` in :meth:`history`.
        after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``after`` in :meth:`history`.
        around: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``around`` in :meth:`history`.
        oldest_first: Optional[:class:`bool`]
            Same as ``oldest_first`` in :meth:`history`.
        bulk: :class:`bool`
            If ``True``, use bulk delete. Setting this to ``False`` is useful for mass-deleting
            a bot's own messages without :attr:`Permissions.manage_messages`. When ``True``, will
            fall back to single delete if messages are older than two weeks.
        reason: Optional[:class:`str`]
            The reason for purging the messages. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have proper permissions to do the actions required.
        HTTPException
            Purging the messages failed.

        Returns
        --------
        List[:class:`.Message`]
            The list of messages that were deleted.
        """
        return await discord.abc._purge_helper(
            self,
            limit=limit,
            check=check,
            before=before,
            after=after,
            around=around,
            oldest_first=oldest_first,
            bulk=bulk,
            reason=reason,
        )

    async def webhooks(self) -> List[Webhook]:
        """|coro|

        Gets the list of webhooks from this channel.

        You must have :attr:`~.Permissions.manage_webhooks` to do this.

        Raises
        -------
        Forbidden
            You don't have permissions to get the webhooks.

        Returns
        --------
        List[:class:`Webhook`]
            The webhooks for this channel.
        """

        from .webhook import Webhook

        data = await self._state.http.channel_webhooks(self.id)
        return [Webhook.from_state(d, state=self._state) for d in data]

    async def create_webhook(self, *, name: str, avatar: Optional[bytes] = None, reason: Optional[str] = None) -> Webhook:
        """|coro|

        Creates a webhook for this channel.

        You must have :attr:`~.Permissions.manage_webhooks` to do this.

        .. versionchanged:: 1.1
            Added the ``reason`` keyword-only parameter.

        Parameters
        -------------
        name: :class:`str`
            The webhook's name.
        avatar: Optional[:class:`bytes`]
            A :term:`py:bytes-like object` representing the webhook's default avatar.
            This operates similarly to :meth:`~ClientUser.edit`.
        reason: Optional[:class:`str`]
            The reason for creating this webhook. Shows up in the audit logs.

        Raises
        -------
        HTTPException
            Creating the webhook failed.
        Forbidden
            You do not have permissions to create a webhook.

        Returns
        --------
        :class:`Webhook`
            The created webhook.
        """

        from .webhook import Webhook

        if avatar is not None:
            avatar = utils._bytes_to_base64_data(avatar)  # type: ignore # Silence reassignment error

        data = await self._state.http.create_webhook(self.id, name=str(name), avatar=avatar, reason=reason)
        return Webhook.from_state(data, state=self._state)

    async def follow(self, *, destination: TextChannel, reason: Optional[str] = None) -> Webhook:
        """|coro|

        Follows a channel using a webhook.

        Only news channels can be followed.

        .. note::

            The webhook returned will not provide a token to do webhook
            actions, as Discord does not provide it.

        .. versionadded:: 1.3

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        -----------
        destination: :class:`TextChannel`
            The channel you would like to follow from.
        reason: Optional[:class:`str`]
            The reason for following the channel. Shows up on the destination guild's audit log.

            .. versionadded:: 1.4

        Raises
        -------
        HTTPException
            Following the channel failed.
        Forbidden
            You do not have the permissions to create a webhook.
        ClientException
            The channel is not a news channel.
        TypeError
            The destination channel is not a text channel.

        Returns
        --------
        :class:`Webhook`
            The created webhook.
        """

        if not self.is_news():
            raise ClientException('The channel must be a news channel.')

        if not isinstance(destination, TextChannel):
            raise TypeError(f'Expected TextChannel received {destination.__class__.__name__}')

        from .webhook import Webhook

        data = await self._state.http.follow_webhook(self.id, webhook_channel_id=destination.id, reason=reason)
        return Webhook._as_follower(data, channel=destination, user=self._state.user)

    def get_partial_message(self, message_id: int, /) -> PartialMessage:
        """Creates a :class:`PartialMessage` from the message ID.

        This is useful if you want to work with a message and only have its ID without
        doing an unnecessary API call.

        .. versionadded:: 1.6

        .. versionchanged:: 2.0

            ``message_id`` parameter is now positional-only.

        Parameters
        ------------
        message_id: :class:`int`
            The message ID to create a partial message for.

        Returns
        ---------
        :class:`PartialMessage`
            The partial message.
        """

        from .message import PartialMessage

        return PartialMessage(channel=self, id=message_id)

    def get_thread(self, thread_id: int, /) -> Optional[Thread]:
        """Returns a thread with the given ID.

        .. note::

            This does not always retrieve archived threads, as they are not retained in the internal
            cache. Use :func:`Guild.fetch_channel` instead.

        .. versionadded:: 2.0

        Parameters
        -----------
        thread_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`Thread`]
            The returned thread or ``None`` if not found.
        """
        return self.guild.get_thread(thread_id)

    async def create_thread(
        self,
        *,
        name: str,
        message: Optional[Snowflake] = None,
        auto_archive_duration: ThreadArchiveDuration = MISSING,
        type: Optional[ChannelType] = None,
        reason: Optional[str] = None,
        invitable: bool = True,
        slowmode_delay: Optional[int] = None,
    ) -> Thread:
        """|coro|

        Creates a thread in this text channel.

        To create a public thread, you must have :attr:`~discord.Permissions.create_public_threads`.
        For a private thread, :attr:`~discord.Permissions.create_private_threads` is needed instead.

        .. versionadded:: 2.0

        Parameters
        -----------
        name: :class:`str`
            The name of the thread.
        message: Optional[:class:`abc.Snowflake`]
            A snowflake representing the message to create the thread with.
            If ``None`` is passed then a private thread is created.
            Defaults to ``None``.
        auto_archive_duration: :class:`int`
            The duration in minutes before a thread is automatically hidden from the channel list.
            If not provided, the channel's default auto archive duration is used.

            Must be one of ``60``, ``1440``, ``4320``, or ``10080``, if provided.
        type: Optional[:class:`ChannelType`]
            The type of thread to create. If a ``message`` is passed then this parameter
            is ignored, as a thread created with a message is always a public thread.
            By default this creates a private thread if this is ``None``.
        reason: :class:`str`
            The reason for creating a new thread. Shows up on the audit log.
        invitable: :class:`bool`
            Whether non-moderators can add users to the thread. Only applicable to private threads.
            Defaults to ``True``.
        slowmode_delay: Optional[:class:`int`]
            Specifies the slowmode rate limit for user in this channel, in seconds.
            The maximum value possible is ``21600``. By default no slowmode rate limit
            if this is ``None``.

        Raises
        -------
        Forbidden
            You do not have permissions to create a thread.
        HTTPException
            Starting the thread failed.

        Returns
        --------
        :class:`Thread`
            The created thread
        """

        if type is None:
            type = ChannelType.private_thread

        if message is None:
            data = await self._state.http.start_thread_without_message(
                self.id,
                name=name,
                auto_archive_duration=auto_archive_duration or self.default_auto_archive_duration,
                type=type.value,  # type: ignore # we're assuming that the user is passing a valid variant
                reason=reason,
                invitable=invitable,
                rate_limit_per_user=slowmode_delay,
            )
        else:
            data = await self._state.http.start_thread_with_message(
                self.id,
                message.id,
                name=name,
                auto_archive_duration=auto_archive_duration or self.default_auto_archive_duration,
                reason=reason,
                rate_limit_per_user=slowmode_delay,
            )

        return Thread(guild=self.guild, state=self._state, data=data)

    async def archived_threads(
        self,
        *,
        private: bool = False,
        joined: bool = False,
        limit: Optional[int] = 100,
        before: Optional[Union[Snowflake, datetime.datetime]] = None,
    ) -> AsyncIterator[Thread]:
        """Returns an :term:`asynchronous iterator` that iterates over all archived threads in this text channel,
        in order of decreasing ID for joined threads, and decreasing :attr:`Thread.archive_timestamp` otherwise.

        You must have :attr:`~Permissions.read_message_history` to do this. If iterating over private threads
        then :attr:`~Permissions.manage_threads` is also required.

        .. versionadded:: 2.0

        Parameters
        -----------
        limit: Optional[:class:`bool`]
            The number of threads to retrieve.
            If ``None``, retrieves every archived thread in the channel. Note, however,
            that this would make it a slow operation.
        before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve archived channels before the given date or ID.
        private: :class:`bool`
            Whether to retrieve private archived threads.
        joined: :class:`bool`
            Whether to retrieve private archived threads that you've joined.
            You cannot set ``joined`` to ``True`` and ``private`` to ``False``.

        Raises
        ------
        Forbidden
            You do not have permissions to get archived threads.
        HTTPException
            The request to get the archived threads failed.
        ValueError
            ``joined`` was set to ``True`` and ``private`` was set to ``False``. You cannot retrieve public archived
            threads that you have joined.

        Yields
        -------
        :class:`Thread`
            The archived threads.
        """
        if joined and not private:
            raise ValueError('Cannot retrieve joined public archived threads')

        before_timestamp = None

        if isinstance(before, datetime.datetime):
            if joined:
                before_timestamp = str(utils.time_snowflake(before, high=False))
            else:
                before_timestamp = before.isoformat()
        elif before is not None:
            if joined:
                before_timestamp = str(before.id)
            else:
                before_timestamp = utils.snowflake_time(before.id).isoformat()

        update_before = lambda data: data['thread_metadata']['archive_timestamp']
        endpoint = self.guild._state.http.get_public_archived_threads

        if joined:
            update_before = lambda data: data['id']
            endpoint = self.guild._state.http.get_joined_private_archived_threads
        elif private:
            endpoint = self.guild._state.http.get_private_archived_threads

        while True:
            retrieve = 100
            if limit is not None:
                if limit <= 0:
                    return
                retrieve = max(2, min(retrieve, limit))

            data = await endpoint(self.id, before=before_timestamp, limit=retrieve)

            threads = data.get('threads', [])
            for raw_thread in threads:
                yield Thread(guild=self.guild, state=self.guild._state, data=raw_thread)
                # Currently the API doesn't let you request less than 2 threads.
                # Bail out early if we had to retrieve more than what the limit was.
                if limit is not None:
                    limit -= 1
                    if limit <= 0:
                        return

            if not data.get('has_more', False):
                return

            before_timestamp = update_before(threads[-1])


class VocalGuildChannel(discord.abc.Messageable, discord.abc.Connectable, discord.abc.GuildChannel, Hashable):
    __slots__ = (
        'name',
        'id',
        'guild',
        'nsfw',
        'bitrate',
        'user_limit',
        '_state',
        'position',
        'slowmode_delay',
        '_overwrites',
        'category_id',
        'rtc_region',
        'video_quality_mode',
        'last_message_id',
    )

    def __init__(self, *, state: ConnectionState, guild: Guild, data: Union[VoiceChannelPayload, StageChannelPayload]):
        self._state: ConnectionState = state
        self.id: int = int(data['id'])
        self._update(guild, data)

    async def _get_channel(self) -> Self:
        return self

    def _get_voice_client_key(self) -> Tuple[int, str]:
        return self.guild.id, 'guild_id'

    def _get_voice_state_pair(self) -> Tuple[int, int]:
        return self.guild.id, self.id

    def _update(self, guild: Guild, data: Union[VoiceChannelPayload, StageChannelPayload]) -> None:
        self.guild: Guild = guild
        self.name: str = data['name']
        self.nsfw: bool = data.get('nsfw', False)
        self.rtc_region: Optional[str] = data.get('rtc_region')
        self.video_quality_mode: VideoQualityMode = try_enum(VideoQualityMode, data.get('video_quality_mode', 1))
        self.category_id: Optional[int] = utils._get_as_snowflake(data, 'parent_id')
        self.last_message_id: Optional[int] = utils._get_as_snowflake(data, 'last_message_id')
        self.position: int = data['position']
        self.slowmode_delay = data.get('rate_limit_per_user', 0)
        self.bitrate: int = data['bitrate']
        self.user_limit: int = data['user_limit']
        self._fill_overwrites(data)

    @property
    def _sorting_bucket(self) -> int:
        return ChannelType.voice.value

    def is_nsfw(self) -> bool:
        """:class:`bool`: Checks if the channel is NSFW.

        .. versionadded:: 2.0
        """
        return self.nsfw

    @property
    def members(self) -> List[Member]:
        """List[:class:`Member`]: Returns all members that are currently inside this voice channel."""
        ret = []
        for user_id, state in self.guild._voice_states.items():
            if state.channel and state.channel.id == self.id:
                member = self.guild.get_member(user_id)
                if member is not None:
                    ret.append(member)
        return ret

    @property
    def voice_states(self) -> Dict[int, VoiceState]:
        """Returns a mapping of member IDs who have voice states in this channel.

        .. versionadded:: 1.3

        .. note::

            This function is intentionally low level to replace :attr:`members`
            when the member cache is unavailable.

        Returns
        --------
        Mapping[:class:`int`, :class:`VoiceState`]
            The mapping of member ID to a voice state.
        """
        # fmt: off
        return {
            key: value
            for key, value in self.guild._voice_states.items()
            if value.channel and value.channel.id == self.id
        }
        # fmt: on

    @property
    def scheduled_events(self) -> List[ScheduledEvent]:
        """List[:class:`ScheduledEvent`]: Returns all scheduled events for this channel.

        .. versionadded:: 2.0
        """
        return [event for event in self.guild.scheduled_events if event.channel_id == self.id]

    @utils.copy_doc(discord.abc.GuildChannel.permissions_for)
    def permissions_for(self, obj: Union[Member, Role], /) -> Permissions:
        base = super().permissions_for(obj)
        self._apply_implicit_permissions(base)

        # voice channels cannot be edited by people who can't connect to them
        # It also implicitly denies all other voice perms
        if not base.connect:
            denied = Permissions.voice()
            denied.update(manage_channels=True, manage_roles=True)
            base.value &= ~denied.value
        return base

    @property
    def last_message(self) -> Optional[Message]:
        """Retrieves the last message from this channel in cache.

        The message might not be valid or point to an existing message.

        .. versionadded:: 2.0

        .. admonition:: Reliable Fetching
            :class: helpful

            For a slightly more reliable method of fetching the
            last message, consider using either :meth:`history`
            or :meth:`fetch_message` with the :attr:`last_message_id`
            attribute.

        Returns
        ---------
        Optional[:class:`Message`]
            The last message in this channel or ``None`` if not found.
        """
        return self._state._get_message(self.last_message_id) if self.last_message_id else None

    def get_partial_message(self, message_id: int, /) -> PartialMessage:
        """Creates a :class:`PartialMessage` from the message ID.

        This is useful if you want to work with a message and only have its ID without
        doing an unnecessary API call.

        .. versionadded:: 2.0

        Parameters
        ------------
        message_id: :class:`int`
            The message ID to create a partial message for.

        Returns
        ---------
        :class:`PartialMessage`
            The partial message.
        """

        from .message import PartialMessage

        return PartialMessage(channel=self, id=message_id)  # type: ignore # VocalGuildChannel is an impl detail

    async def delete_messages(self, messages: Iterable[Snowflake], *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes a list of messages. This is similar to :meth:`Message.delete`
        except it bulk deletes multiple messages.

        As a special case, if the number of messages is 0, then nothing
        is done. If the number of messages is 1 then single message
        delete is done. If it's more than two, then bulk delete is used.

        You cannot bulk delete more than 100 messages or messages that
        are older than 14 days old.

        You must have :attr:`~Permissions.manage_messages` to do this.

        .. versionadded:: 2.0

        Parameters
        -----------
        messages: Iterable[:class:`abc.Snowflake`]
            An iterable of messages denoting which ones to bulk delete.
        reason: Optional[:class:`str`]
            The reason for deleting the messages. Shows up on the audit log.

        Raises
        ------
        ClientException
            The number of messages to delete was more than 100.
        Forbidden
            You do not have proper permissions to delete the messages.
        NotFound
            If single delete, then the message was already deleted.
        HTTPException
            Deleting the messages failed.
        """
        if not isinstance(messages, (list, tuple)):
            messages = list(messages)

        if len(messages) == 0:
            return  # do nothing

        if len(messages) == 1:
            message_id: int = messages[0].id
            await self._state.http.delete_message(self.id, message_id)
            return

        if len(messages) > 100:
            raise ClientException('Can only bulk delete messages up to 100 messages')

        message_ids: SnowflakeList = [m.id for m in messages]
        await self._state.http.delete_messages(self.id, message_ids, reason=reason)

    async def purge(
        self,
        *,
        limit: Optional[int] = 100,
        check: Callable[[Message], bool] = MISSING,
        before: Optional[SnowflakeTime] = None,
        after: Optional[SnowflakeTime] = None,
        around: Optional[SnowflakeTime] = None,
        oldest_first: Optional[bool] = None,
        bulk: bool = True,
        reason: Optional[str] = None,
    ) -> List[Message]:
        """|coro|

        Purges a list of messages that meet the criteria given by the predicate
        ``check``. If a ``check`` is not provided then all messages are deleted
        without discrimination.

        You must have :attr:`~Permissions.manage_messages` to
        delete messages even if they are your own.
        Having :attr:`~Permissions.read_message_history` is
        also needed to retrieve message history.

        .. versionadded:: 2.0

        Examples
        ---------

        Deleting bot's messages ::

            def is_me(m):
                return m.author == client.user

            deleted = await channel.purge(limit=100, check=is_me)
            await channel.send(f'Deleted {len(deleted)} message(s)')

        Parameters
        -----------
        limit: Optional[:class:`int`]
            The number of messages to search through. This is not the number
            of messages that will be deleted, though it can be.
        check: Callable[[:class:`Message`], :class:`bool`]
            The function used to check if a message should be deleted.
            It must take a :class:`Message` as its sole parameter.
        before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``before`` in :meth:`history`.
        after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``after`` in :meth:`history`.
        around: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``around`` in :meth:`history`.
        oldest_first: Optional[:class:`bool`]
            Same as ``oldest_first`` in :meth:`history`.
        bulk: :class:`bool`
            If ``True``, use bulk delete. Setting this to ``False`` is useful for mass-deleting
            a bot's own messages without :attr:`Permissions.manage_messages`. When ``True``, will
            fall back to single delete if messages are older than two weeks.
        reason: Optional[:class:`str`]
            The reason for purging the messages. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have proper permissions to do the actions required.
        HTTPException
            Purging the messages failed.

        Returns
        --------
        List[:class:`.Message`]
            The list of messages that were deleted.
        """

        return await discord.abc._purge_helper(
            self,
            limit=limit,
            check=check,
            before=before,
            after=after,
            around=around,
            oldest_first=oldest_first,
            bulk=bulk,
            reason=reason,
        )

    async def webhooks(self) -> List[Webhook]:
        """|coro|

        Gets the list of webhooks from this channel.

        You must have :attr:`~.Permissions.manage_webhooks` to do this.

        .. versionadded:: 2.0

        Raises
        -------
        Forbidden
            You don't have permissions to get the webhooks.

        Returns
        --------
        List[:class:`Webhook`]
            The webhooks for this channel.
        """

        from .webhook import Webhook

        data = await self._state.http.channel_webhooks(self.id)
        return [Webhook.from_state(d, state=self._state) for d in data]

    async def create_webhook(self, *, name: str, avatar: Optional[bytes] = None, reason: Optional[str] = None) -> Webhook:
        """|coro|

        Creates a webhook for this channel.

        You must have :attr:`~.Permissions.manage_webhooks` to do this.

        .. versionadded:: 2.0

        Parameters
        -------------
        name: :class:`str`
            The webhook's name.
        avatar: Optional[:class:`bytes`]
            A :term:`py:bytes-like object` representing the webhook's default avatar.
            This operates similarly to :meth:`~ClientUser.edit`.
        reason: Optional[:class:`str`]
            The reason for creating this webhook. Shows up in the audit logs.

        Raises
        -------
        HTTPException
            Creating the webhook failed.
        Forbidden
            You do not have permissions to create a webhook.

        Returns
        --------
        :class:`Webhook`
            The created webhook.
        """

        from .webhook import Webhook

        if avatar is not None:
            avatar = utils._bytes_to_base64_data(avatar)  # type: ignore # Silence reassignment error

        data = await self._state.http.create_webhook(self.id, name=str(name), avatar=avatar, reason=reason)
        return Webhook.from_state(data, state=self._state)

    @utils.copy_doc(discord.abc.GuildChannel.clone)
    async def clone(
        self, *, name: Optional[str] = None, category: Optional[CategoryChannel] = None, reason: Optional[str] = None
    ) -> Self:
        base = {
            'bitrate': self.bitrate,
            'user_limit': self.user_limit,
            'rate_limit_per_user': self.slowmode_delay,
            'nsfw': self.nsfw,
            'video_quality_mode': self.video_quality_mode.value,
        }
        if self.rtc_region:
            base['rtc_region'] = self.rtc_region

        return await self._clone_impl(
            base,
            name=name,
            category=category,
            reason=reason,
        )


class VoiceChannel(VocalGuildChannel):
    """Represents a Discord guild voice channel.

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
    name: :class:`str`
        The channel name.
    guild: :class:`Guild`
        The guild the channel belongs to.
    id: :class:`int`
        The channel ID.
    nsfw: :class:`bool`
        If the channel is marked as "not safe for work" or "age restricted".

        .. versionadded:: 2.0
    category_id: Optional[:class:`int`]
        The category channel ID this channel belongs to, if applicable.
    position: :class:`int`
        The position in the channel list. This is a number that starts at 0. e.g. the
        top channel is position 0.
    bitrate: :class:`int`
        The channel's preferred audio bitrate in bits per second.
    user_limit: :class:`int`
        The channel's limit for number of members that can be in a voice channel.
    rtc_region: Optional[:class:`str`]
        The region for the voice channel's voice communication.
        A value of ``None`` indicates automatic voice region detection.

        .. versionadded:: 1.7

        .. versionchanged:: 2.0
            The type of this attribute has changed to :class:`str`.
    video_quality_mode: :class:`VideoQualityMode`
        The camera video quality for the voice channel's participants.

        .. versionadded:: 2.0
    last_message_id: Optional[:class:`int`]
        The last message ID of the message sent to this channel. It may
        *not* point to an existing or valid message.

        .. versionadded:: 2.0
    slowmode_delay: :class:`int`
        The number of seconds a member must wait between sending messages
        in this channel. A value of ``0`` denotes that it is disabled.
        Bots and users with :attr:`~Permissions.manage_channels` or
        :attr:`~Permissions.manage_messages` bypass slowmode.

        .. versionadded:: 2.2
    status: Optional[:class:`str`]
        The status of the voice channel. ``None`` if no status is set.
        This is not available for the fetch methods such as :func:`Guild.fetch_channel`
        or :func:`Client.fetch_channel`

        .. versionadded:: 2.5
    """

    __slots__ = ('status',)

    def __init__(self, *, state: ConnectionState, guild: Guild, data: VoiceChannelPayload) -> None:
        super().__init__(state=state, guild=guild, data=data)
        self.status: Optional[str] = data.get('status') or None  # empty string -> None

    def __repr__(self) -> str:
        attrs = [
            ('id', self.id),
            ('name', self.name),
            ('rtc_region', self.rtc_region),
            ('position', self.position),
            ('bitrate', self.bitrate),
            ('video_quality_mode', self.video_quality_mode),
            ('user_limit', self.user_limit),
            ('category_id', self.category_id),
        ]
        joined = ' '.join('%s=%r' % t for t in attrs)
        return f'<{self.__class__.__name__} {joined}>'

    @property
    def _scheduled_event_entity_type(self) -> Optional[EntityType]:
        return EntityType.voice

    @property
    def type(self) -> Literal[ChannelType.voice]:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.voice

    @overload
    async def edit(self) -> None:
        ...

    @overload
    async def edit(self, *, position: int, reason: Optional[str] = ...) -> None:
        ...

    @overload
    async def edit(
        self,
        *,
        name: str = ...,
        nsfw: bool = ...,
        bitrate: int = ...,
        user_limit: int = ...,
        position: int = ...,
        sync_permissions: int = ...,
        category: Optional[CategoryChannel] = ...,
        overwrites: Mapping[OverwriteKeyT, PermissionOverwrite] = ...,
        rtc_region: Optional[str] = ...,
        video_quality_mode: VideoQualityMode = ...,
        slowmode_delay: int = ...,
        status: Optional[str] = ...,
        reason: Optional[str] = ...,
    ) -> VoiceChannel:
        ...

    async def edit(self, *, reason: Optional[str] = None, **options: Any) -> Optional[VoiceChannel]:
        """|coro|

        Edits the channel.

        You must have :attr:`~Permissions.manage_channels` to do this.

        .. versionchanged:: 1.3
            The ``overwrites`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited channel is returned instead.

        .. versionchanged:: 2.0
            The ``region`` parameter now accepts :class:`str` instead of an enum.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The new channel's name.
        bitrate: :class:`int`
            The new channel's bitrate.
        nsfw: :class:`bool`
            To mark the channel as NSFW or not.
        user_limit: :class:`int`
            The new channel's user limit.
        position: :class:`int`
            The new channel's position.
        sync_permissions: :class:`bool`
            Whether to sync permissions with the channel's new or pre-existing
            category. Defaults to ``False``.
        category: Optional[:class:`CategoryChannel`]
            The new category for this channel. Can be ``None`` to remove the
            category.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for user in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
        reason: Optional[:class:`str`]
            The reason for editing this channel. Shows up on the audit log.
        overwrites: :class:`Mapping`
            A :class:`Mapping` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply to the channel.
        rtc_region: Optional[:class:`str`]
            The new region for the voice channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.

            .. versionadded:: 1.7
        video_quality_mode: :class:`VideoQualityMode`
            The camera video quality for the voice channel's participants.

            .. versionadded:: 2.0
        status: Optional[:class:`str`]
            The new voice channel status. It can be up to 500 characters.
            Can be ``None`` to remove the status.

            .. versionadded:: 2.4

        Raises
        ------
        TypeError
            If the permission overwrite information is not in proper form.
        Forbidden
            You do not have permissions to edit the channel.
        HTTPException
            Editing the channel failed.

        Returns
        --------
        Optional[:class:`.VoiceChannel`]
            The newly edited voice channel. If the edit was only positional
            then ``None`` is returned instead.
        """
        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore

    async def send_sound(self, sound: Union[SoundboardSound, SoundboardDefaultSound], /) -> None:
        """|coro|

        Sends a soundboard sound for this channel.

        You must have :attr:`~Permissions.speak` and :attr:`~Permissions.use_soundboard` to do this.
        Additionally, you must have :attr:`~Permissions.use_external_sounds` if the sound is from
        a different guild.

        .. versionadded:: 2.5

        Parameters
        -----------
        sound: Union[:class:`SoundboardSound`, :class:`SoundboardDefaultSound`]
            The sound to send for this channel.

        Raises
        -------
        Forbidden
            You do not have permissions to send a sound for this channel.
        HTTPException
            Sending the sound failed.
        """
        payload = {'sound_id': sound.id}
        if not isinstance(sound, SoundboardDefaultSound) and self.guild.id != sound.guild.id:
            payload['source_guild_id'] = sound.guild.id

        await self._state.http.send_soundboard_sound(self.id, **payload)


class StageChannel(VocalGuildChannel):
    """Represents a Discord guild stage channel.

    .. versionadded:: 1.7

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
    name: :class:`str`
        The channel name.
    guild: :class:`Guild`
        The guild the channel belongs to.
    id: :class:`int`
        The channel ID.
    nsfw: :class:`bool`
        If the channel is marked as "not safe for work" or "age restricted".

        .. versionadded:: 2.0
    topic: Optional[:class:`str`]
        The channel's topic. ``None`` if it isn't set.
    category_id: Optional[:class:`int`]
        The category channel ID this channel belongs to, if applicable.
    position: :class:`int`
        The position in the channel list. This is a number that starts at 0. e.g. the
        top channel is position 0.
    bitrate: :class:`int`
        The channel's preferred audio bitrate in bits per second.
    user_limit: :class:`int`
        The channel's limit for number of members that can be in a stage channel.
    rtc_region: Optional[:class:`str`]
        The region for the stage channel's voice communication.
        A value of ``None`` indicates automatic voice region detection.
    video_quality_mode: :class:`VideoQualityMode`
        The camera video quality for the stage channel's participants.

        .. versionadded:: 2.0
    last_message_id: Optional[:class:`int`]
        The last message ID of the message sent to this channel. It may
        *not* point to an existing or valid message.

        .. versionadded:: 2.2
    slowmode_delay: :class:`int`
        The number of seconds a member must wait between sending messages
        in this channel. A value of ``0`` denotes that it is disabled.
        Bots and users with :attr:`~Permissions.manage_channels` or
        :attr:`~Permissions.manage_messages` bypass slowmode.

        .. versionadded:: 2.2
    """

    __slots__ = ('topic',)

    def __repr__(self) -> str:
        attrs = [
            ('id', self.id),
            ('name', self.name),
            ('topic', self.topic),
            ('rtc_region', self.rtc_region),
            ('position', self.position),
            ('bitrate', self.bitrate),
            ('video_quality_mode', self.video_quality_mode),
            ('user_limit', self.user_limit),
            ('category_id', self.category_id),
        ]
        joined = ' '.join('%s=%r' % t for t in attrs)
        return f'<{self.__class__.__name__} {joined}>'

    def _update(self, guild: Guild, data: StageChannelPayload) -> None:
        super()._update(guild, data)
        self.topic: Optional[str] = data.get('topic')

    @property
    def _scheduled_event_entity_type(self) -> Optional[EntityType]:
        return EntityType.stage_instance

    @property
    def requesting_to_speak(self) -> List[Member]:
        """List[:class:`Member`]: A list of members who are requesting to speak in the stage channel."""
        return [member for member in self.members if member.voice and member.voice.requested_to_speak_at is not None]

    @property
    def speakers(self) -> List[Member]:
        """List[:class:`Member`]: A list of members who have been permitted to speak in the stage channel.

        .. versionadded:: 2.0
        """
        return [
            member
            for member in self.members
            if member.voice and not member.voice.suppress and member.voice.requested_to_speak_at is None
        ]

    @property
    def listeners(self) -> List[Member]:
        """List[:class:`Member`]: A list of members who are listening in the stage channel.

        .. versionadded:: 2.0
        """
        return [member for member in self.members if member.voice and member.voice.suppress]

    @property
    def moderators(self) -> List[Member]:
        """List[:class:`Member`]: A list of members who are moderating the stage channel.

        .. versionadded:: 2.0
        """
        required_permissions = Permissions.stage_moderator()
        return [member for member in self.members if self.permissions_for(member) >= required_permissions]

    @property
    def type(self) -> Literal[ChannelType.stage_voice]:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.stage_voice

    @property
    def instance(self) -> Optional[StageInstance]:
        """Optional[:class:`StageInstance`]: The running stage instance of the stage channel.

        .. versionadded:: 2.0
        """
        return utils.get(self.guild.stage_instances, channel_id=self.id)

    async def create_instance(
        self,
        *,
        topic: str,
        privacy_level: PrivacyLevel = MISSING,
        send_start_notification: bool = False,
        scheduled_event: Snowflake = MISSING,
        reason: Optional[str] = None,
    ) -> StageInstance:
        """|coro|

        Create a stage instance.

        You must have :attr:`~Permissions.manage_channels` to do this.

        .. versionadded:: 2.0

        Parameters
        -----------
        topic: :class:`str`
            The stage instance's topic.
        privacy_level: :class:`PrivacyLevel`
            The stage instance's privacy level. Defaults to :attr:`PrivacyLevel.guild_only`.
        send_start_notification: :class:`bool`
            Whether to send a start notification. This sends a push notification to @everyone if ``True``. Defaults to ``False``.
            You must have :attr:`~Permissions.mention_everyone` to do this.

            .. versionadded:: 2.3
        scheduled_event: :class:`~discord.abc.Snowflake`
            The guild scheduled event associated with the stage instance.

            .. versionadded:: 2.4
        reason: :class:`str`
            The reason the stage instance was created. Shows up on the audit log.

        Raises
        ------
        TypeError
            If the ``privacy_level`` parameter is not the proper type.
        Forbidden
            You do not have permissions to create a stage instance.
        HTTPException
            Creating a stage instance failed.

        Returns
        --------
        :class:`StageInstance`
            The newly created stage instance.
        """

        payload: Dict[str, Any] = {'channel_id': self.id, 'topic': topic}

        if privacy_level is not MISSING:
            if not isinstance(privacy_level, PrivacyLevel):
                raise TypeError('privacy_level field must be of type PrivacyLevel')

            payload['privacy_level'] = privacy_level.value

        if scheduled_event is not MISSING:
            payload['guild_scheduled_event_id'] = scheduled_event.id

        payload['send_start_notification'] = send_start_notification

        data = await self._state.http.create_stage_instance(**payload, reason=reason)
        return StageInstance(guild=self.guild, state=self._state, data=data)

    async def fetch_instance(self) -> StageInstance:
        """|coro|

        Gets the running :class:`StageInstance`.

        .. versionadded:: 2.0

        Raises
        -------
        NotFound
            The stage instance or channel could not be found.
        HTTPException
            Getting the stage instance failed.

        Returns
        --------
        :class:`StageInstance`
            The stage instance.
        """
        data = await self._state.http.get_stage_instance(self.id)
        return StageInstance(guild=self.guild, state=self._state, data=data)

    @overload
    async def edit(self) -> None:
        ...

    @overload
    async def edit(self, *, position: int, reason: Optional[str] = ...) -> None:
        ...

    @overload
    async def edit(
        self,
        *,
        name: str = ...,
        nsfw: bool = ...,
        bitrate: int = ...,
        user_limit: int = ...,
        position: int = ...,
        sync_permissions: int = ...,
        category: Optional[CategoryChannel] = ...,
        overwrites: Mapping[OverwriteKeyT, PermissionOverwrite] = ...,
        rtc_region: Optional[str] = ...,
        video_quality_mode: VideoQualityMode = ...,
        slowmode_delay: int = ...,
        reason: Optional[str] = ...,
    ) -> StageChannel:
        ...

    async def edit(self, *, reason: Optional[str] = None, **options: Any) -> Optional[StageChannel]:
        """|coro|

        Edits the channel.

        You must have :attr:`~Permissions.manage_channels` to do this.

        .. versionchanged:: 2.0
            The ``topic`` parameter must now be set via :attr:`create_instance`.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited channel is returned instead.

        .. versionchanged:: 2.0
            The ``region`` parameter now accepts :class:`str` instead of an enum.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` instead of
            ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The new channel's name.
        bitrate: :class:`int`
            The new channel's bitrate.
        position: :class:`int`
            The new channel's position.
        nsfw: :class:`bool`
            To mark the channel as NSFW or not.
        user_limit: :class:`int`
            The new channel's user limit.
        sync_permissions: :class:`bool`
            Whether to sync permissions with the channel's new or pre-existing
            category. Defaults to ``False``.
        category: Optional[:class:`CategoryChannel`]
            The new category for this channel. Can be ``None`` to remove the
            category.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for user in this channel, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
        reason: Optional[:class:`str`]
            The reason for editing this channel. Shows up on the audit log.
        overwrites: :class:`Mapping`
            A :class:`Mapping` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply to the channel.
        rtc_region: Optional[:class:`str`]
            The new region for the stage channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.
        video_quality_mode: :class:`VideoQualityMode`
            The camera video quality for the stage channel's participants.

            .. versionadded:: 2.0

        Raises
        ------
        ValueError
            If the permission overwrite information is not in proper form.
        Forbidden
            You do not have permissions to edit the channel.
        HTTPException
            Editing the channel failed.

        Returns
        --------
        Optional[:class:`.StageChannel`]
            The newly edited stage channel. If the edit was only positional
            then ``None`` is returned instead.
        """

        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore


class CategoryChannel(discord.abc.GuildChannel, Hashable):
    """Represents a Discord channel category.

    These are useful to group channels to logical compartments.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the category's hash.

        .. describe:: str(x)

            Returns the category's name.

    Attributes
    -----------
    name: :class:`str`
        The category name.
    guild: :class:`Guild`
        The guild the category belongs to.
    id: :class:`int`
        The category channel ID.
    position: :class:`int`
        The position in the category list. This is a number that starts at 0. e.g. the
        top category is position 0.
    nsfw: :class:`bool`
        If the channel is marked as "not safe for work".

        .. note::

            To check if the channel or the guild of that channel are marked as NSFW, consider :meth:`is_nsfw` instead.
    """

    __slots__ = ('name', 'id', 'guild', 'nsfw', '_state', 'position', '_overwrites', 'category_id')

    def __init__(self, *, state: ConnectionState, guild: Guild, data: CategoryChannelPayload):
        self._state: ConnectionState = state
        self.id: int = int(data['id'])
        self._update(guild, data)

    def __repr__(self) -> str:
        return f'<CategoryChannel id={self.id} name={self.name!r} position={self.position} nsfw={self.nsfw}>'

    def _update(self, guild: Guild, data: CategoryChannelPayload) -> None:
        self.guild: Guild = guild
        self.name: str = data['name']
        self.category_id: Optional[int] = utils._get_as_snowflake(data, 'parent_id')
        self.nsfw: bool = data.get('nsfw', False)
        self.position: int = data['position']
        self._fill_overwrites(data)

    @property
    def _sorting_bucket(self) -> int:
        return ChannelType.category.value

    @property
    def _scheduled_event_entity_type(self) -> Optional[EntityType]:
        return None

    @property
    def type(self) -> Literal[ChannelType.category]:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.category

    def is_nsfw(self) -> bool:
        """:class:`bool`: Checks if the category is NSFW."""
        return self.nsfw

    @utils.copy_doc(discord.abc.GuildChannel.clone)
    async def clone(
        self,
        *,
        name: Optional[str] = None,
        category: Optional[CategoryChannel] = None,
        reason: Optional[str] = None,
    ) -> CategoryChannel:
        return await self._clone_impl({'nsfw': self.nsfw}, name=name, reason=reason)

    @overload
    async def edit(self) -> None:
        ...

    @overload
    async def edit(self, *, position: int, reason: Optional[str] = ...) -> None:
        ...

    @overload
    async def edit(
        self,
        *,
        name: str = ...,
        position: int = ...,
        nsfw: bool = ...,
        overwrites: Mapping[OverwriteKeyT, PermissionOverwrite] = ...,
        reason: Optional[str] = ...,
    ) -> CategoryChannel:
        ...

    async def edit(self, *, reason: Optional[str] = None, **options: Any) -> Optional[CategoryChannel]:
        """|coro|

        Edits the channel.

        You must have :attr:`~Permissions.manage_channels` to do this.

        .. versionchanged:: 1.3
            The ``overwrites`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited channel is returned instead.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` or
            :exc:`ValueError` instead of ``InvalidArgument``.

        Parameters
        ----------
        name: :class:`str`
            The new category's name.
        position: :class:`int`
            The new category's position.
        nsfw: :class:`bool`
            To mark the category as NSFW or not.
        reason: Optional[:class:`str`]
            The reason for editing this category. Shows up on the audit log.
        overwrites: :class:`Mapping`
            A :class:`Mapping` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply to the channel.

        Raises
        ------
        ValueError
            If position is less than 0 or greater than the number of categories.
        TypeError
            The overwrite information is not in proper form.
        Forbidden
            You do not have permissions to edit the category.
        HTTPException
            Editing the category failed.

        Returns
        --------
        Optional[:class:`.CategoryChannel`]
            The newly edited category channel. If the edit was only positional
            then ``None`` is returned instead.
        """

        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore

    @utils.copy_doc(discord.abc.GuildChannel.move)
    async def move(self, **kwargs: Any) -> None:
        kwargs.pop('category', None)
        await super().move(**kwargs)

    @property
    def channels(self) -> List[GuildChannelType]:
        """List[:class:`abc.GuildChannel`]: Returns the channels that are under this category.

        These are sorted by the official Discord UI, which places voice channels below the text channels.
        """

        def comparator(channel):
            return (not isinstance(channel, TextChannel), channel.position)

        ret = [c for c in self.guild.channels if c.category_id == self.id]
        ret.sort(key=comparator)
        return ret

    @property
    def text_channels(self) -> List[TextChannel]:
        """List[:class:`TextChannel`]: Returns the text channels that are under this category."""
        ret = [c for c in self.guild.channels if c.category_id == self.id and isinstance(c, TextChannel)]
        ret.sort(key=lambda c: (c.position, c.id))
        return ret

    @property
    def voice_channels(self) -> List[VoiceChannel]:
        """List[:class:`VoiceChannel`]: Returns the voice channels that are under this category."""
        ret = [c for c in self.guild.channels if c.category_id == self.id and isinstance(c, VoiceChannel)]
        ret.sort(key=lambda c: (c.position, c.id))
        return ret

    @property
    def stage_channels(self) -> List[StageChannel]:
        """List[:class:`StageChannel`]: Returns the stage channels that are under this category.

        .. versionadded:: 1.7
        """
        ret = [c for c in self.guild.channels if c.category_id == self.id and isinstance(c, StageChannel)]
        ret.sort(key=lambda c: (c.position, c.id))
        return ret

    @property
    def forums(self) -> List[ForumChannel]:
        """List[:class:`ForumChannel`]: Returns the forum channels that are under this category.

        .. versionadded:: 2.4
        """
        r = [c for c in self.guild.channels if c.category_id == self.id and isinstance(c, ForumChannel)]
        r.sort(key=lambda c: (c.position, c.id))
        return r

    async def create_text_channel(self, name: str, **options: Any) -> TextChannel:
        """|coro|

        A shortcut method to :meth:`Guild.create_text_channel` to create a :class:`TextChannel` in the category.

        Returns
        -------
        :class:`TextChannel`
            The channel that was just created.
        """
        return await self.guild.create_text_channel(name, category=self, **options)

    async def create_voice_channel(self, name: str, **options: Any) -> VoiceChannel:
        """|coro|

        A shortcut method to :meth:`Guild.create_voice_channel` to create a :class:`VoiceChannel` in the category.

        Returns
        -------
        :class:`VoiceChannel`
            The channel that was just created.
        """
        return await self.guild.create_voice_channel(name, category=self, **options)

    async def create_stage_channel(self, name: str, **options: Any) -> StageChannel:
        """|coro|

        A shortcut method to :meth:`Guild.create_stage_channel` to create a :class:`StageChannel` in the category.

        .. versionadded:: 1.7

        Returns
        -------
        :class:`StageChannel`
            The channel that was just created.
        """
        return await self.guild.create_stage_channel(name, category=self, **options)

    async def create_forum(self, name: str, **options: Any) -> ForumChannel:
        """|coro|

        A shortcut method to :meth:`Guild.create_forum` to create a :class:`ForumChannel` in the category.

        .. versionadded:: 2.0

        Returns
        --------
        :class:`ForumChannel`
            The channel that was just created.
        """
        return await self.guild.create_forum(name, category=self, **options)


class ForumTag(Hashable):
    """Represents a forum tag that can be applied to a thread within a :class:`ForumChannel`.

    .. versionadded:: 2.1

    .. container:: operations

        .. describe:: x == y

            Checks if two forum tags are equal.

        .. describe:: x != y

            Checks if two forum tags are not equal.

        .. describe:: hash(x)

            Returns the forum tag's hash.

        .. describe:: str(x)

            Returns the forum tag's name.


    Attributes
    -----------
    id: :class:`int`
        The ID of the tag. If this was manually created then the ID will be ``0``.
    name: :class:`str`
        The name of the tag. Can only be up to 20 characters.
    moderated: :class:`bool`
        Whether this tag can only be added or removed by a moderator with
        the :attr:`~Permissions.manage_threads` permission.
    emoji: Optional[:class:`PartialEmoji`]
        The emoji that is used to represent this tag.
        Note that if the emoji is a custom emoji, it will *not* have name information.
    """

    __slots__ = ('name', 'id', 'moderated', 'emoji')

    def __init__(self, *, name: str, emoji: Optional[EmojiInputType] = None, moderated: bool = False) -> None:
        self.name: str = name
        self.id: int = 0
        self.moderated: bool = moderated
        self.emoji: Optional[PartialEmoji] = None
        if isinstance(emoji, _EmojiTag):
            self.emoji = emoji._to_partial()
        elif isinstance(emoji, str):
            self.emoji = PartialEmoji.from_str(emoji)
        elif emoji is not None:
            raise TypeError(f'emoji must be a Emoji, PartialEmoji, str or None not {emoji.__class__.__name__}')

    @classmethod
    def from_data(cls, *, state: ConnectionState, data: ForumTagPayload) -> Self:
        self = cls.__new__(cls)
        self.name = data['name']
        self.id = int(data['id'])
        self.moderated = data.get('moderated', False)

        emoji_name = data['emoji_name'] or ''
        emoji_id = utils._get_as_snowflake(data, 'emoji_id') or None  # Coerce 0 -> None
        if not emoji_name and not emoji_id:
            self.emoji = None
        else:
            self.emoji = PartialEmoji.with_state(state=state, name=emoji_name, id=emoji_id)
        return self

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            'name': self.name,
            'moderated': self.moderated,
        }
        if self.emoji is not None:
            payload.update(self.emoji._to_forum_tag_payload())
        else:
            payload.update(emoji_id=None, emoji_name=None)

        if self.id:
            payload['id'] = self.id

        return payload

    def __repr__(self) -> str:
        return f'<ForumTag id={self.id} name={self.name!r} emoji={self.emoji!r} moderated={self.moderated}>'

    def __str__(self) -> str:
        return self.name


class ForumChannel(discord.abc.GuildChannel, Hashable):
    """Represents a Discord guild forum channel.

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two forums are equal.

        .. describe:: x != y

            Checks if two forums are not equal.

        .. describe:: hash(x)

            Returns the forum's hash.

        .. describe:: str(x)

            Returns the forum's name.

    Attributes
    -----------
    name: :class:`str`
        The forum name.
    guild: :class:`Guild`
        The guild the forum belongs to.
    id: :class:`int`
        The forum ID.
    category_id: Optional[:class:`int`]
        The category channel ID this forum belongs to, if applicable.
    topic: Optional[:class:`str`]
        The forum's topic. ``None`` if it doesn't exist. Called "Guidelines" in the UI.
        Can be up to 4096 characters long.
    position: :class:`int`
        The position in the channel list. This is a number that starts at 0. e.g. the
        top channel is position 0.
    last_message_id: Optional[:class:`int`]
        The last thread ID that was created on this forum. This technically also
        coincides with the message ID that started the thread that was created.
        It may *not* point to an existing or valid thread or message.
    slowmode_delay: :class:`int`
        The number of seconds a member must wait between creating threads
        in this forum. A value of ``0`` denotes that it is disabled.
        Bots and users with :attr:`~Permissions.manage_channels` or
        :attr:`~Permissions.manage_messages` bypass slowmode.
    nsfw: :class:`bool`
        If the forum is marked as "not safe for work" or "age restricted".
    default_auto_archive_duration: :class:`int`
        The default auto archive duration in minutes for threads created in this forum.
    default_thread_slowmode_delay: :class:`int`
        The default slowmode delay in seconds for threads created in this forum.

        .. versionadded:: 2.1
    default_reaction_emoji: Optional[:class:`PartialEmoji`]
        The default reaction emoji for threads created in this forum to show in the
        add reaction button.

        .. versionadded:: 2.1
    default_layout: :class:`ForumLayoutType`
        The default layout for posts in this forum channel.
        Defaults to :attr:`ForumLayoutType.not_set`.

        .. versionadded:: 2.2
    default_sort_order: Optional[:class:`ForumOrderType`]
        The default sort order for posts in this forum channel.

        .. versionadded:: 2.3
    """

    __slots__ = (
        'name',
        'id',
        'guild',
        'topic',
        '_state',
        '_flags',
        '_type',
        'nsfw',
        'category_id',
        'position',
        'slowmode_delay',
        '_overwrites',
        'last_message_id',
        'default_auto_archive_duration',
        'default_thread_slowmode_delay',
        'default_reaction_emoji',
        'default_layout',
        'default_sort_order',
        '_available_tags',
        '_flags',
    )

    def __init__(self, *, state: ConnectionState, guild: Guild, data: Union[ForumChannelPayload, MediaChannelPayload]):
        self._state: ConnectionState = state
        self.id: int = int(data['id'])
        self._type: Literal[15, 16] = data['type']
        self._update(guild, data)

    def __repr__(self) -> str:
        attrs = [
            ('id', self.id),
            ('name', self.name),
            ('position', self.position),
            ('nsfw', self.nsfw),
            ('category_id', self.category_id),
        ]
        joined = ' '.join('%s=%r' % t for t in attrs)
        return f'<{self.__class__.__name__} {joined}>'

    def _update(self, guild: Guild, data: Union[ForumChannelPayload, MediaChannelPayload]) -> None:
        self.guild: Guild = guild
        self.name: str = data['name']
        self.category_id: Optional[int] = utils._get_as_snowflake(data, 'parent_id')
        self.topic: Optional[str] = data.get('topic')
        self.position: int = data['position']
        self.nsfw: bool = data.get('nsfw', False)
        self.slowmode_delay: int = data.get('rate_limit_per_user', 0)
        self.default_auto_archive_duration: ThreadArchiveDuration = data.get('default_auto_archive_duration', 1440)
        self.last_message_id: Optional[int] = utils._get_as_snowflake(data, 'last_message_id')
        # This takes advantage of the fact that dicts are ordered since Python 3.7
        tags = [ForumTag.from_data(state=self._state, data=tag) for tag in data.get('available_tags', [])]
        self.default_thread_slowmode_delay: int = data.get('default_thread_rate_limit_per_user', 0)
        self.default_layout: ForumLayoutType = try_enum(ForumLayoutType, data.get('default_forum_layout', 0))
        self._available_tags: Dict[int, ForumTag] = {tag.id: tag for tag in tags}

        self.default_reaction_emoji: Optional[PartialEmoji] = None
        default_reaction_emoji = data.get('default_reaction_emoji')
        if default_reaction_emoji:
            self.default_reaction_emoji = PartialEmoji.with_state(
                state=self._state,
                id=utils._get_as_snowflake(default_reaction_emoji, 'emoji_id') or None,  # Coerce 0 -> None
                name=default_reaction_emoji.get('emoji_name') or '',
            )

        self.default_sort_order: Optional[ForumOrderType] = None
        default_sort_order = data.get('default_sort_order')
        if default_sort_order is not None:
            self.default_sort_order = try_enum(ForumOrderType, default_sort_order)

        self._flags: int = data.get('flags', 0)
        self._fill_overwrites(data)

    @property
    def type(self) -> Literal[ChannelType.forum, ChannelType.media]:
        """:class:`ChannelType`: The channel's Discord type."""
        if self._type == 16:
            return ChannelType.media
        return ChannelType.forum

    @property
    def _sorting_bucket(self) -> int:
        return ChannelType.text.value

    @property
    def members(self) -> List[Member]:
        """List[:class:`Member`]: Returns all members that can see this channel.

        .. versionadded:: 2.5
        """
        return [m for m in self.guild.members if self.permissions_for(m).read_messages]

    @property
    def _scheduled_event_entity_type(self) -> Optional[EntityType]:
        return None

    @utils.copy_doc(discord.abc.GuildChannel.permissions_for)
    def permissions_for(self, obj: Union[Member, Role], /) -> Permissions:
        base = super().permissions_for(obj)
        self._apply_implicit_permissions(base)

        # text channels do not have voice related permissions
        denied = Permissions.voice()
        base.value &= ~denied.value
        return base

    def get_thread(self, thread_id: int, /) -> Optional[Thread]:
        """Returns a thread with the given ID.

        .. note::

            This does not always retrieve archived threads, as they are not retained in the internal
            cache. Use :func:`Guild.fetch_channel` instead.

        .. versionadded:: 2.2

        Parameters
        -----------
        thread_id: :class:`int`
            The ID to search for.

        Returns
        --------
        Optional[:class:`Thread`]
            The returned thread or ``None`` if not found.
        """
        thread = self.guild.get_thread(thread_id)
        if thread is not None and thread.parent_id == self.id:
            return thread
        return None

    @property
    def threads(self) -> List[Thread]:
        """List[:class:`Thread`]: Returns all the threads that you can see."""
        return [thread for thread in self.guild._threads.values() if thread.parent_id == self.id]

    @property
    def flags(self) -> ChannelFlags:
        """:class:`ChannelFlags`: The flags associated with this thread.

        .. versionadded:: 2.1
        """
        return ChannelFlags._from_value(self._flags)

    @property
    def available_tags(self) -> Sequence[ForumTag]:
        """Sequence[:class:`ForumTag`]: Returns all the available tags for this forum.

        .. versionadded:: 2.1
        """
        return utils.SequenceProxy(self._available_tags.values())

    def get_tag(self, tag_id: int, /) -> Optional[ForumTag]:
        """Returns the tag with the given ID.

        .. versionadded:: 2.1

        Parameters
        ----------
        tag_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`ForumTag`]
            The tag with the given ID, or ``None`` if not found.
        """
        return self._available_tags.get(tag_id)

    def is_nsfw(self) -> bool:
        """:class:`bool`: Checks if the forum is NSFW."""
        return self.nsfw

    def is_media(self) -> bool:
        """:class:`bool`: Checks if the channel is a media channel.

        .. versionadded:: 2.4
        """
        return self._type == ChannelType.media.value

    @utils.copy_doc(discord.abc.GuildChannel.clone)
    async def clone(
        self,
        *,
        name: Optional[str] = None,
        category: Optional[CategoryChannel],
        reason: Optional[str] = None,
    ) -> ForumChannel:
        base = {
            'topic': self.topic,
            'rate_limit_per_user': self.slowmode_delay,
            'nsfw': self.nsfw,
            'default_auto_archive_duration': self.default_auto_archive_duration,
            'available_tags': [tag.to_dict() for tag in self.available_tags],
            'default_thread_rate_limit_per_user': self.default_thread_slowmode_delay,
        }
        if self.default_sort_order:
            base['default_sort_order'] = self.default_sort_order.value
        if self.default_reaction_emoji:
            base['default_reaction_emoji'] = self.default_reaction_emoji._to_forum_tag_payload()
        if not self.is_media() and self.default_layout:
            base['default_forum_layout'] = self.default_layout.value

        return await self._clone_impl(
            base,
            name=name,
            category=category,
            reason=reason,
        )

    @overload
    async def edit(self) -> None:
        ...

    @overload
    async def edit(self, *, position: int, reason: Optional[str] = ...) -> None:
        ...

    @overload
    async def edit(
        self,
        *,
        reason: Optional[str] = ...,
        name: str = ...,
        topic: str = ...,
        position: int = ...,
        nsfw: bool = ...,
        sync_permissions: bool = ...,
        category: Optional[CategoryChannel] = ...,
        slowmode_delay: int = ...,
        default_auto_archive_duration: ThreadArchiveDuration = ...,
        type: ChannelType = ...,
        overwrites: Mapping[OverwriteKeyT, PermissionOverwrite] = ...,
        available_tags: Sequence[ForumTag] = ...,
        default_thread_slowmode_delay: int = ...,
        default_reaction_emoji: Optional[EmojiInputType] = ...,
        default_layout: ForumLayoutType = ...,
        default_sort_order: ForumOrderType = ...,
        require_tag: bool = ...,
    ) -> ForumChannel:
        ...

    async def edit(self, *, reason: Optional[str] = None, **options: Any) -> Optional[ForumChannel]:
        """|coro|

        Edits the forum.

        You must have :attr:`~Permissions.manage_channels` to do this.

        Parameters
        ----------
        name: :class:`str`
            The new forum name.
        topic: :class:`str`
            The new forum's topic.
        position: :class:`int`
            The new forum's position.
        nsfw: :class:`bool`
            To mark the forum as NSFW or not.
        sync_permissions: :class:`bool`
            Whether to sync permissions with the forum's new or pre-existing
            category. Defaults to ``False``.
        category: Optional[:class:`CategoryChannel`]
            The new category for this forum. Can be ``None`` to remove the
            category.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for user in this forum, in seconds.
            A value of ``0`` disables slowmode. The maximum value possible is ``21600``.
        type: :class:`ChannelType`
            Change the type of this text forum. Currently, only conversion between
            :attr:`ChannelType.text` and :attr:`ChannelType.news` is supported. This
            is only available to guilds that contain ``NEWS`` in :attr:`Guild.features`.
        reason: Optional[:class:`str`]
            The reason for editing this forum. Shows up on the audit log.
        overwrites: :class:`Mapping`
            A :class:`Mapping` of target (either a role or a member) to
            :class:`PermissionOverwrite` to apply to the forum.
        default_auto_archive_duration: :class:`int`
            The new default auto archive duration in minutes for threads created in this channel.
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.
        available_tags: Sequence[:class:`ForumTag`]
            The new available tags for this forum.

            .. versionadded:: 2.1
        default_thread_slowmode_delay: :class:`int`
            The new default slowmode delay for threads in this channel.

            .. versionadded:: 2.1
        default_reaction_emoji: Optional[Union[:class:`Emoji`, :class:`PartialEmoji`, :class:`str`]]
            The new default reaction emoji for threads in this channel.

            .. versionadded:: 2.1
        default_layout: :class:`ForumLayoutType`
            The new default layout for posts in this forum.

            .. versionadded:: 2.2
        default_sort_order: Optional[:class:`ForumOrderType`]
            The new default sort order for posts in this forum.

            .. versionadded:: 2.3
        require_tag: :class:`bool`
            Whether to require a tag for threads in this channel or not.

            .. versionadded:: 2.1

        Raises
        ------
        ValueError
            The new ``position`` is less than 0 or greater than the number of channels.
        TypeError
            The permission overwrite information is not in proper form or a type
            is not the expected type.
        Forbidden
            You do not have permissions to edit the forum.
        HTTPException
            Editing the forum failed.

        Returns
        --------
        Optional[:class:`.ForumChannel`]
            The newly edited forum channel. If the edit was only positional
            then ``None`` is returned instead.
        """

        try:
            tags: Sequence[ForumTag] = options.pop('available_tags')
        except KeyError:
            pass
        else:
            options['available_tags'] = [tag.to_dict() for tag in tags]

        try:
            default_reaction_emoji: Optional[EmojiInputType] = options.pop('default_reaction_emoji')
        except KeyError:
            pass
        else:
            if default_reaction_emoji is None:
                options['default_reaction_emoji'] = None
            elif isinstance(default_reaction_emoji, _EmojiTag):
                options['default_reaction_emoji'] = default_reaction_emoji._to_partial()._to_forum_tag_payload()
            elif isinstance(default_reaction_emoji, str):
                options['default_reaction_emoji'] = PartialEmoji.from_str(default_reaction_emoji)._to_forum_tag_payload()

        try:
            require_tag = options.pop('require_tag')
        except KeyError:
            pass
        else:
            flags = self.flags
            flags.require_tag = require_tag
            options['flags'] = flags.value

        try:
            layout = options.pop('default_layout')
        except KeyError:
            pass
        else:
            if not isinstance(layout, ForumLayoutType):
                raise TypeError(f'default_layout parameter must be a ForumLayoutType not {layout.__class__.__name__}')

            options['default_forum_layout'] = layout.value

        try:
            sort_order = options.pop('default_sort_order')
        except KeyError:
            pass
        else:
            if sort_order is None:
                options['default_sort_order'] = None
            else:
                if not isinstance(sort_order, ForumOrderType):
                    raise TypeError(
                        f'default_sort_order parameter must be a ForumOrderType not {sort_order.__class__.__name__}'
                    )

                options['default_sort_order'] = sort_order.value

        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore

    async def create_tag(
        self,
        *,
        name: str,
        emoji: Optional[PartialEmoji] = None,
        moderated: bool = False,
        reason: Optional[str] = None,
    ) -> ForumTag:
        """|coro|

        Creates a new tag in this forum.

        You must have :attr:`~Permissions.manage_channels` to do this.

        Parameters
        ----------
        name: :class:`str`
            The name of the tag. Can only be up to 20 characters.
        emoji: Optional[Union[:class:`str`, :class:`PartialEmoji`]]
            The emoji to use for the tag.
        moderated: :class:`bool`
            Whether the tag can only be applied by moderators.
        reason: Optional[:class:`str`]
            The reason for creating this tag. Shows up on the audit log.

        Raises
        ------
        Forbidden
            You do not have permissions to create a tag in this forum.
        HTTPException
            Creating the tag failed.

        Returns
        -------
        :class:`ForumTag`
            The newly created tag.
        """

        prior = list(self._available_tags.values())
        result = ForumTag(name=name, emoji=emoji, moderated=moderated)
        prior.append(result)
        payload = await self._state.http.edit_channel(
            self.id, reason=reason, available_tags=[tag.to_dict() for tag in prior]
        )
        try:
            result.id = int(payload['available_tags'][-1]['id'])  # type: ignore
        except (KeyError, IndexError, ValueError):
            pass

        return result

    async def create_thread(
        self,
        *,
        name: str,
        auto_archive_duration: ThreadArchiveDuration = MISSING,
        slowmode_delay: Optional[int] = None,
        content: Optional[str] = None,
        tts: bool = False,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        stickers: Sequence[Union[GuildSticker, StickerItem]] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        mention_author: bool = MISSING,
        applied_tags: Sequence[ForumTag] = MISSING,
        view: View = MISSING,
        suppress_embeds: bool = False,
        reason: Optional[str] = None,
    ) -> ThreadWithMessage:
        """|coro|

        Creates a thread in this forum.

        This thread is a public thread with the initial message given. Currently in order
        to start a thread in this forum, the user needs :attr:`~discord.Permissions.send_messages`.

        You must send at least one of ``content``, ``embed``, ``embeds``, ``file``, ``files``,
        or ``view`` to create a thread in a forum, since forum channels must have a starter message.

        Parameters
        -----------
        name: :class:`str`
            The name of the thread.
        auto_archive_duration: :class:`int`
            The duration in minutes before a thread is automatically hidden from the channel list.
            If not provided, the channel's default auto archive duration is used.

            Must be one of ``60``, ``1440``, ``4320``, or ``10080``, if provided.
        slowmode_delay: Optional[:class:`int`]
            Specifies the slowmode rate limit for user in this channel, in seconds.
            The maximum value possible is ``21600``. By default no slowmode rate limit
            if this is ``None``.
        content: Optional[:class:`str`]
            The content of the message to send with the thread.
        tts: :class:`bool`
            Indicates if the message should be sent using text-to-speech.
        embed: :class:`~discord.Embed`
            The rich embed for the content.
        embeds: List[:class:`~discord.Embed`]
            A list of embeds to upload. Must be a maximum of 10.
        file: :class:`~discord.File`
            The file to upload.
        files: List[:class:`~discord.File`]
            A list of files to upload. Must be a maximum of 10.
        allowed_mentions: :class:`~discord.AllowedMentions`
            Controls the mentions being processed in this message. If this is
            passed, then the object is merged with :attr:`~discord.Client.allowed_mentions`.
            The merging behaviour only overrides attributes that have been explicitly passed
            to the object, otherwise it uses the attributes set in :attr:`~discord.Client.allowed_mentions`.
            If no object is passed at all then the defaults given by :attr:`~discord.Client.allowed_mentions`
            are used instead.
        mention_author: :class:`bool`
            If set, overrides the :attr:`~discord.AllowedMentions.replied_user` attribute of ``allowed_mentions``.
        applied_tags: List[:class:`discord.ForumTag`]
            A list of tags to apply to the thread.
        view: :class:`discord.ui.View`
            A Discord UI View to add to the message.
        stickers: Sequence[Union[:class:`~discord.GuildSticker`, :class:`~discord.StickerItem`]]
            A list of stickers to upload. Must be a maximum of 3.
        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This sends the message without any embeds if set to ``True``.
        reason: :class:`str`
            The reason for creating a new thread. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permissions to create a thread.
        HTTPException
            Starting the thread failed.
        ValueError
            The ``files`` or ``embeds`` list is not of the appropriate size.
        TypeError
            You specified both ``file`` and ``files``,
            or you specified both ``embed`` and ``embeds``.

        Returns
        --------
        Tuple[:class:`Thread`, :class:`Message`]
            The created thread with the created message.
            This is also accessible as a namedtuple with ``thread`` and ``message`` fields.
        """

        state = self._state
        previous_allowed_mention = state.allowed_mentions
        if stickers is MISSING:
            sticker_ids = MISSING
        else:
            sticker_ids: SnowflakeList = [s.id for s in stickers]

        if view and not hasattr(view, '__discord_ui_view__'):
            raise TypeError(f'view parameter must be View not {view.__class__.__name__}')

        if suppress_embeds:
            flags = MessageFlags._from_value(4)
        else:
            flags = MISSING

        content = str(content) if content else MISSING

        channel_payload = {
            'name': name,
            'auto_archive_duration': auto_archive_duration or self.default_auto_archive_duration,
            'rate_limit_per_user': slowmode_delay,
            'type': 11,  # Private threads don't seem to be allowed
        }

        if applied_tags is not MISSING:
            channel_payload['applied_tags'] = [str(tag.id) for tag in applied_tags]

        with handle_message_parameters(
            content=content,
            tts=tts,
            file=file,
            files=files,
            embed=embed,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            previous_allowed_mentions=previous_allowed_mention,
            mention_author=None if mention_author is MISSING else mention_author,
            stickers=sticker_ids,
            view=view,
            flags=flags,
            channel_payload=channel_payload,
        ) as params:
            # Circular import
            from .message import Message

            data = await state.http.start_thread_in_forum(self.id, params=params, reason=reason)
            thread = Thread(guild=self.guild, state=self._state, data=data)
            message = Message(state=self._state, channel=thread, data=data['message'])
            if view and not view.is_finished():
                self._state.store_view(view, message.id)

            return ThreadWithMessage(thread=thread, message=message)

    async def webhooks(self) -> List[Webhook]:
        """|coro|

        Gets the list of webhooks from this channel.

        You must have :attr:`~.Permissions.manage_webhooks` to do this.

        Raises
        -------
        Forbidden
            You don't have permissions to get the webhooks.

        Returns
        --------
        List[:class:`Webhook`]
            The webhooks for this channel.
        """

        from .webhook import Webhook

        data = await self._state.http.channel_webhooks(self.id)
        return [Webhook.from_state(d, state=self._state) for d in data]

    async def create_webhook(self, *, name: str, avatar: Optional[bytes] = None, reason: Optional[str] = None) -> Webhook:
        """|coro|

        Creates a webhook for this channel.

        You must have :attr:`~.Permissions.manage_webhooks` to do this.

        Parameters
        -------------
        name: :class:`str`
            The webhook's name.
        avatar: Optional[:class:`bytes`]
            A :term:`py:bytes-like object` representing the webhook's default avatar.
            This operates similarly to :meth:`~ClientUser.edit`.
        reason: Optional[:class:`str`]
            The reason for creating this webhook. Shows up in the audit logs.

        Raises
        -------
        HTTPException
            Creating the webhook failed.
        Forbidden
            You do not have permissions to create a webhook.

        Returns
        --------
        :class:`Webhook`
            The created webhook.
        """

        from .webhook import Webhook

        if avatar is not None:
            avatar = utils._bytes_to_base64_data(avatar)  # type: ignore # Silence reassignment error

        data = await self._state.http.create_webhook(self.id, name=str(name), avatar=avatar, reason=reason)
        return Webhook.from_state(data, state=self._state)

    async def archived_threads(
        self,
        *,
        limit: Optional[int] = 100,
        before: Optional[Union[Snowflake, datetime.datetime]] = None,
    ) -> AsyncIterator[Thread]:
        """Returns an :term:`asynchronous iterator` that iterates over all archived threads in this forum
        in order of decreasing :attr:`Thread.archive_timestamp`.

        You must have :attr:`~Permissions.read_message_history` to do this.

        .. versionadded:: 2.0

        Parameters
        -----------
        limit: Optional[:class:`bool`]
            The number of threads to retrieve.
            If ``None``, retrieves every archived thread in the channel. Note, however,
            that this would make it a slow operation.
        before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve archived channels before the given date or ID.

        Raises
        ------
        Forbidden
            You do not have permissions to get archived threads.
        HTTPException
            The request to get the archived threads failed.

        Yields
        -------
        :class:`Thread`
            The archived threads.
        """
        before_timestamp = None

        if isinstance(before, datetime.datetime):
            before_timestamp = before.isoformat()
        elif before is not None:
            before_timestamp = utils.snowflake_time(before.id).isoformat()

        update_before = lambda data: data['thread_metadata']['archive_timestamp']

        while True:
            retrieve = 100
            if limit is not None:
                if limit <= 0:
                    return
                retrieve = max(2, min(retrieve, limit))

            data = await self.guild._state.http.get_public_archived_threads(self.id, before=before_timestamp, limit=retrieve)

            threads = data.get('threads', [])
            for raw_thread in threads:
                yield Thread(guild=self.guild, state=self.guild._state, data=raw_thread)
                # Currently the API doesn't let you request less than 2 threads.
                # Bail out early if we had to retrieve more than what the limit was.
                if limit is not None:
                    limit -= 1
                    if limit <= 0:
                        return

            if not data.get('has_more', False):
                return

            before_timestamp = update_before(threads[-1])


class DMChannel(discord.abc.Messageable, discord.abc.PrivateChannel, Hashable):
    """Represents a Discord direct message channel.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns a string representation of the channel

    Attributes
    ----------
    recipient: Optional[:class:`User`]
        The user you are participating with in the direct message channel.
        If this channel is received through the gateway, the recipient information
        may not be always available.
    recipients: List[:class:`User`]
        The users you are participating with in the DM channel.

        .. versionadded:: 2.4
    me: :class:`ClientUser`
        The user presenting yourself.
    id: :class:`int`
        The direct message channel ID.
    """

    __slots__ = ('id', 'recipients', 'me', '_state')

    def __init__(self, *, me: ClientUser, state: ConnectionState, data: DMChannelPayload):
        self._state: ConnectionState = state
        self.recipients: List[User] = [state.store_user(u) for u in data.get('recipients', [])]
        self.me: ClientUser = me
        self.id: int = int(data['id'])

    async def _get_channel(self) -> Self:
        return self

    def __str__(self) -> str:
        if self.recipient:
            return f'Direct Message with {self.recipient}'
        return 'Direct Message with Unknown User'

    def __repr__(self) -> str:
        return f'<DMChannel id={self.id} recipient={self.recipient!r}>'

    @classmethod
    def _from_message(cls, state: ConnectionState, channel_id: int) -> Self:
        self = cls.__new__(cls)
        self._state = state
        self.id = channel_id
        self.recipients = []
        # state.user won't be None here
        self.me = state.user  # type: ignore
        return self

    @property
    def recipient(self) -> Optional[User]:
        if self.recipients:
            return self.recipients[0]
        return None

    @property
    def type(self) -> Literal[ChannelType.private]:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.private

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: The guild this DM channel belongs to. Always ``None``.

        This is mainly provided for compatibility purposes in duck typing.

        .. versionadded:: 2.0
        """
        return None

    @property
    def jump_url(self) -> str:
        """:class:`str`: Returns a URL that allows the client to jump to the channel.

        .. versionadded:: 2.0
        """
        return f'https://discord.com/channels/@me/{self.id}'

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the direct message channel's creation time in UTC."""
        return utils.snowflake_time(self.id)

    def permissions_for(self, obj: Any = None, /) -> Permissions:
        """Handles permission resolution for a :class:`User`.

        This function is there for compatibility with other channel types.

        Actual direct messages do not really have the concept of permissions.

        This returns all the Text related permissions set to ``True`` except:

        - :attr:`~Permissions.send_tts_messages`: You cannot send TTS messages in a DM.
        - :attr:`~Permissions.manage_messages`: You cannot delete others messages in a DM.
        - :attr:`~Permissions.create_private_threads`: There are no threads in a DM.
        - :attr:`~Permissions.create_public_threads`: There are no threads in a DM.
        - :attr:`~Permissions.manage_threads`: There are no threads in a DM.
        - :attr:`~Permissions.send_messages_in_threads`: There are no threads in a DM.

        .. versionchanged:: 2.0

            ``obj`` parameter is now positional-only.

        .. versionchanged:: 2.1

            Thread related permissions are now set to ``False``.

        Parameters
        -----------
        obj: :class:`User`
            The user to check permissions for. This parameter is ignored
            but kept for compatibility with other ``permissions_for`` methods.

        Returns
        --------
        :class:`Permissions`
            The resolved permissions.
        """
        return Permissions._dm_permissions()

    def get_partial_message(self, message_id: int, /) -> PartialMessage:
        """Creates a :class:`PartialMessage` from the message ID.

        This is useful if you want to work with a message and only have its ID without
        doing an unnecessary API call.

        .. versionadded:: 1.6

        .. versionchanged:: 2.0

            ``message_id`` parameter is now positional-only.

        Parameters
        ------------
        message_id: :class:`int`
            The message ID to create a partial message for.

        Returns
        ---------
        :class:`PartialMessage`
            The partial message.
        """

        from .message import PartialMessage

        return PartialMessage(channel=self, id=message_id)


class GroupChannel(discord.abc.Messageable, discord.abc.PrivateChannel, Hashable):
    """Represents a Discord group channel.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns a string representation of the channel

    Attributes
    ----------
    recipients: List[:class:`User`]
        The users you are participating with in the group channel.
    me: :class:`ClientUser`
        The user presenting yourself.
    id: :class:`int`
        The group channel ID.
    owner: Optional[:class:`User`]
        The user that owns the group channel.
    owner_id: :class:`int`
        The owner ID that owns the group channel.

        .. versionadded:: 2.0
    name: Optional[:class:`str`]
        The group channel's name if provided.
    """

    __slots__ = ('id', 'recipients', 'owner_id', 'owner', '_icon', 'name', 'me', '_state')

    def __init__(self, *, me: ClientUser, state: ConnectionState, data: GroupChannelPayload):
        self._state: ConnectionState = state
        self.id: int = int(data['id'])
        self.me: ClientUser = me
        self._update_group(data)

    def _update_group(self, data: GroupChannelPayload) -> None:
        self.owner_id: Optional[int] = utils._get_as_snowflake(data, 'owner_id')
        self._icon: Optional[str] = data.get('icon')
        self.name: Optional[str] = data.get('name')
        self.recipients: List[User] = [self._state.store_user(u) for u in data.get('recipients', [])]

        self.owner: Optional[BaseUser]
        if self.owner_id == self.me.id:
            self.owner = self.me
        else:
            self.owner = utils.find(lambda u: u.id == self.owner_id, self.recipients)

    async def _get_channel(self) -> Self:
        return self

    def __str__(self) -> str:
        if self.name:
            return self.name

        if len(self.recipients) == 0:
            return 'Unnamed'

        return ', '.join(map(lambda x: x.name, self.recipients))

    def __repr__(self) -> str:
        return f'<GroupChannel id={self.id} name={self.name!r}>'

    @property
    def type(self) -> Literal[ChannelType.group]:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.group

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: The guild this group channel belongs to. Always ``None``.

        This is mainly provided for compatibility purposes in duck typing.

        .. versionadded:: 2.0
        """
        return None

    @property
    def icon(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the channel's icon asset if available."""
        if self._icon is None:
            return None
        return Asset._from_icon(self._state, self.id, self._icon, path='channel')

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the channel's creation time in UTC."""
        return utils.snowflake_time(self.id)

    @property
    def jump_url(self) -> str:
        """:class:`str`: Returns a URL that allows the client to jump to the channel.

        .. versionadded:: 2.0
        """
        return f'https://discord.com/channels/@me/{self.id}'

    def permissions_for(self, obj: Snowflake, /) -> Permissions:
        """Handles permission resolution for a :class:`User`.

        This function is there for compatibility with other channel types.

        Actual direct messages do not really have the concept of permissions.

        This returns all the Text related permissions set to ``True`` except:

        - :attr:`~Permissions.send_tts_messages`: You cannot send TTS messages in a DM.
        - :attr:`~Permissions.manage_messages`: You cannot delete others messages in a DM.
        - :attr:`~Permissions.create_private_threads`: There are no threads in a DM.
        - :attr:`~Permissions.create_public_threads`: There are no threads in a DM.
        - :attr:`~Permissions.manage_threads`: There are no threads in a DM.
        - :attr:`~Permissions.send_messages_in_threads`: There are no threads in a DM.

        This also checks the kick_members permission if the user is the owner.

        .. versionchanged:: 2.0

            ``obj`` parameter is now positional-only.

        .. versionchanged:: 2.1

            Thread related permissions are now set to ``False``.

        Parameters
        -----------
        obj: :class:`~discord.abc.Snowflake`
            The user to check permissions for.

        Returns
        --------
        :class:`Permissions`
            The resolved permissions for the user.
        """

        base = Permissions._dm_permissions()
        base.mention_everyone = True

        if obj.id == self.owner_id:
            base.kick_members = True

        return base

    async def leave(self) -> None:
        """|coro|

        Leave the group.

        If you are the only one in the group, this deletes it as well.

        Raises
        -------
        HTTPException
            Leaving the group failed.
        """

        await self._state.http.leave_group(self.id)


class PartialMessageable(discord.abc.Messageable, Hashable):
    """Represents a partial messageable to aid with working messageable channels when
    only a channel ID is present.

    The only way to construct this class is through :meth:`Client.get_partial_messageable`.

    Note that this class is trimmed down and has no rich attributes.

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two partial messageables are equal.

        .. describe:: x != y

            Checks if two partial messageables are not equal.

        .. describe:: hash(x)

            Returns the partial messageable's hash.

    Attributes
    -----------
    id: :class:`int`
        The channel ID associated with this partial messageable.
    guild_id: Optional[:class:`int`]
        The guild ID associated with this partial messageable.
    type: Optional[:class:`ChannelType`]
        The channel type associated with this partial messageable, if given.
    """

    def __init__(self, state: ConnectionState, id: int, guild_id: Optional[int] = None, type: Optional[ChannelType] = None):
        self._state: ConnectionState = state
        self.id: int = id
        self.guild_id: Optional[int] = guild_id
        self.type: Optional[ChannelType] = type

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id} type={self.type!r}>'

    async def _get_channel(self) -> PartialMessageable:
        return self

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: The guild this partial messageable is in."""
        return self._state._get_guild(self.guild_id)

    @property
    def jump_url(self) -> str:
        """:class:`str`: Returns a URL that allows the client to jump to the channel."""
        if self.guild_id is None:
            return f'https://discord.com/channels/@me/{self.id}'
        return f'https://discord.com/channels/{self.guild_id}/{self.id}'

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the channel's creation time in UTC."""
        return utils.snowflake_time(self.id)

    def permissions_for(self, obj: Any = None, /) -> Permissions:
        """Handles permission resolution for a :class:`User`.

        This function is there for compatibility with other channel types.

        Since partial messageables cannot reasonably have the concept of
        permissions, this will always return :meth:`Permissions.none`.

        Parameters
        -----------
        obj: :class:`User`
            The user to check permissions for. This parameter is ignored
            but kept for compatibility with other ``permissions_for`` methods.

        Returns
        --------
        :class:`Permissions`
            The resolved permissions.
        """

        return Permissions.none()

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention the channel.

        .. versionadded:: 2.5
        """
        return f'<#{self.id}>'

    def get_partial_message(self, message_id: int, /) -> PartialMessage:
        """Creates a :class:`PartialMessage` from the message ID.

        This is useful if you want to work with a message and only have its ID without
        doing an unnecessary API call.

        Parameters
        ------------
        message_id: :class:`int`
            The message ID to create a partial message for.

        Returns
        ---------
        :class:`PartialMessage`
            The partial message.
        """

        from .message import PartialMessage

        return PartialMessage(channel=self, id=message_id)


def _guild_channel_factory(channel_type: int):
    value = try_enum(ChannelType, channel_type)
    if value is ChannelType.text:
        return TextChannel, value
    elif value is ChannelType.voice:
        return VoiceChannel, value
    elif value is ChannelType.category:
        return CategoryChannel, value
    elif value is ChannelType.news:
        return TextChannel, value
    elif value is ChannelType.stage_voice:
        return StageChannel, value
    elif value is ChannelType.forum:
        return ForumChannel, value
    elif value is ChannelType.media:
        return ForumChannel, value
    else:
        return None, value


def _channel_factory(channel_type: int):
    cls, value = _guild_channel_factory(channel_type)
    if value is ChannelType.private:
        return DMChannel, value
    elif value is ChannelType.group:
        return GroupChannel, value
    else:
        return cls, value


def _threaded_channel_factory(channel_type: int):
    cls, value = _channel_factory(channel_type)
    if value in (ChannelType.private_thread, ChannelType.public_thread, ChannelType.news_thread):
        return Thread, value
    return cls, value


def _threaded_guild_channel_factory(channel_type: int):
    cls, value = _guild_channel_factory(channel_type)
    if value in (ChannelType.private_thread, ChannelType.public_thread, ChannelType.news_thread):
        return Thread, value
    return cls, value
