# -*- coding: utf-8 -*-

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
from typing import Any, Dict, Literal, Optional, Generic, TYPE_CHECKING, Sequence, Tuple, Union, List, overload
import asyncio
import datetime

from . import utils
from .enums import try_enum, Locale, InteractionType, InteractionResponseType
from .errors import InteractionResponded, HTTPException, ClientException, DiscordException
from .flags import MessageFlags
from .channel import ChannelType
from ._types import ClientT
from .sku import Entitlement

from .user import User
from .member import Member
from .message import Message, Attachment
from .permissions import Permissions
from .http import handle_message_parameters
from .webhook.async_ import async_context, Webhook, interaction_response_params, interaction_message_response_params
from .app_commands.installs import AppCommandContext
from .app_commands.namespace import Namespace
from .app_commands.translator import locale_str, TranslationContext, TranslationContextLocation
from .channel import _threaded_channel_factory

__all__ = (
    'Interaction',
    'InteractionMessage',
    'InteractionResponse',
    'InteractionCallback',
    'InteractionCallbackResource',
    'InteractionCallbackActivity',
)

if TYPE_CHECKING:
    from .types.interactions import (
        Interaction as InteractionPayload,
        InteractionData,
        ApplicationCommandInteractionData,
        InteractionCallback as InteractionCallbackPayload,
        InteractionCallbackActivity as InteractionCallbackActivityPayload,
        InteractionCallbackResponse as InteractionCallbackResponsePayload,
        InteractionCallbackResource as InteractionCallbackResourcePayload,
    )
    from .types.webhook import (
        Webhook as WebhookPayload,
    )
    from .types.snowflake import Snowflake
    from .guild import Guild
    from .state import ConnectionState
    from .file import File
    from .mentions import AllowedMentions
    from aiohttp import ClientSession
    from .embeds import Embed
    from .ui.view import View
    from .app_commands.models import Choice, ChoiceT
    from .ui.modal import Modal
    from .channel import VoiceChannel, StageChannel, TextChannel, ForumChannel, CategoryChannel, DMChannel, GroupChannel
    from .threads import Thread
    from .app_commands.commands import Command, ContextMenu
    from .poll import Poll

    InteractionChannel = Union[
        VoiceChannel,
        StageChannel,
        TextChannel,
        ForumChannel,
        CategoryChannel,
        Thread,
        DMChannel,
        GroupChannel,
    ]

MISSING: Any = utils.MISSING


class Interaction(Generic[ClientT]):
    """Represents a Discord interaction.

    An interaction happens when a user does an action that needs to
    be notified. Current examples are slash commands and components.

    .. versionadded:: 2.0

    Attributes
    -----------
    id: :class:`int`
        The interaction's ID.
    type: :class:`InteractionType`
        The interaction type.
    guild_id: Optional[:class:`int`]
        The guild ID the interaction was sent from.
    channel: Optional[Union[:class:`abc.GuildChannel`, :class:`abc.PrivateChannel`, :class:`Thread`]]
        The channel the interaction was sent from.

        Note that due to a Discord limitation, if sent from a DM channel :attr:`~DMChannel.recipient` is ``None``.
    entitlement_sku_ids: List[:class:`int`]
        The entitlement SKU IDs that the user has.
    entitlements: List[:class:`Entitlement`]
        The entitlements that the guild or user has.
    application_id: :class:`int`
        The application ID that the interaction was for.
    user: Union[:class:`User`, :class:`Member`]
        The user or member that sent the interaction.
    message: Optional[:class:`Message`]
        The message that sent this interaction.

        This is only available for :attr:`InteractionType.component` interactions.
    token: :class:`str`
        The token to continue the interaction. These are valid
        for 15 minutes.
    data: :class:`dict`
        The raw interaction data.
    locale: :class:`Locale`
        The locale of the user invoking the interaction.
    guild_locale: Optional[:class:`Locale`]
        The preferred locale of the guild the interaction was sent from, if any.
    extras: :class:`dict`
        A dictionary that can be used to store extraneous data for use during
        interaction processing. The library will not touch any values or keys
        within this dictionary.
    command_failed: :class:`bool`
        Whether the command associated with this interaction failed to execute.
        This includes checks and execution.
    context: :class:`.AppCommandContext`
        The context of the interaction.

        .. versionadded:: 2.4
    """

    __slots__: Tuple[str, ...] = (
        'id',
        'type',
        'guild_id',
        'data',
        'application_id',
        'message',
        'user',
        'token',
        'version',
        'locale',
        'guild_locale',
        'extras',
        'command_failed',
        'entitlement_sku_ids',
        'entitlements',
        "context",
        '_integration_owners',
        '_permissions',
        '_app_permissions',
        '_state',
        '_client',
        '_session',
        '_baton',
        '_original_response',
        '_cs_response',
        '_cs_followup',
        'channel',
        '_cs_namespace',
        '_cs_command',
    )

    def __init__(self, *, data: InteractionPayload, state: ConnectionState[ClientT]):
        self._state: ConnectionState[ClientT] = state
        self._client: ClientT = state._get_client()
        self._session: ClientSession = state.http._HTTPClient__session  # type: ignore # Mangled attribute for __session
        self._original_response: Optional[InteractionMessage] = None
        # This baton is used for extra data that might be useful for the lifecycle of
        # an interaction. This is mainly for internal purposes and it gives it a free-for-all slot.
        self._baton: Any = MISSING
        self.extras: Dict[Any, Any] = {}
        self.command_failed: bool = False
        self._from_data(data)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} id={self.id} type={self.type!r} guild_id={self.guild_id!r} user={self.user!r}>'

    def _from_data(self, data: InteractionPayload):
        self.id: int = int(data['id'])
        self.type: InteractionType = try_enum(InteractionType, data['type'])
        self.data: Optional[InteractionData] = data.get('data')
        self.token: str = data['token']
        self.version: int = data['version']
        self.guild_id: Optional[int] = utils._get_as_snowflake(data, 'guild_id')
        self.channel: Optional[InteractionChannel] = None
        self.application_id: int = int(data['application_id'])
        self.entitlement_sku_ids: List[int] = [int(x) for x in data.get('entitlement_skus', []) or []]
        self.entitlements: List[Entitlement] = [Entitlement(self._state, x) for x in data.get('entitlements', [])]
        # This is not entirely useful currently, unsure how to expose it in a way that it is.
        self._integration_owners: Dict[int, Snowflake] = {
            int(k): int(v) for k, v in data.get('authorizing_integration_owners', {}).items()
        }
        try:
            self.context = AppCommandContext._from_value([data['context']])
        except KeyError:
            self.context = AppCommandContext()

        self.locale: Locale = try_enum(Locale, data.get('locale', 'en-US'))
        self.guild_locale: Optional[Locale]
        try:
            self.guild_locale = try_enum(Locale, data['guild_locale'])
        except KeyError:
            self.guild_locale = None

        guild = None
        if self.guild_id:
            # The data type is a TypedDict but it doesn't narrow to Dict[str, Any] properly
            guild = self._state._get_or_create_unavailable_guild(self.guild_id, data=data.get('guild'))  # type: ignore
            if guild.me is None and self._client.user is not None:
                guild._add_member(Member._from_client_user(user=self._client.user, guild=guild, state=self._state))

        raw_channel = data.get('channel', {})
        channel_id = utils._get_as_snowflake(raw_channel, 'id')
        if channel_id is not None and guild is not None:
            self.channel = guild and guild._resolve_channel(channel_id)

        raw_ch_type = raw_channel.get('type')
        if self.channel is None and raw_ch_type is not None:
            factory, ch_type = _threaded_channel_factory(raw_ch_type)  # type is never None
            if factory is None:
                logging.info('Unknown channel type {type} for channel ID {id}.'.format_map(raw_channel))
            else:
                if ch_type in (ChannelType.group, ChannelType.private):
                    self.channel = factory(me=self._client.user, data=raw_channel, state=self._state)  # type: ignore
                elif guild is not None:
                    self.channel = factory(guild=guild, state=self._state, data=raw_channel)  # type: ignore

        self.message: Optional[Message]
        try:
            # The channel and message payloads are mismatched yet handled properly at runtime
            self.message = Message(state=self._state, channel=self.channel, data=data['message'])  # type: ignore
        except KeyError:
            self.message = None

        self.user: Union[User, Member] = MISSING
        self._permissions: int = 0
        self._app_permissions: int = int(data.get('app_permissions', 0))

        if guild is not None:
            # Upgrade Message.guild in case it's missing with partial guild data
            if self.message is not None and self.message.guild is None:
                self.message.guild = guild

            try:
                member = data['member']  # type: ignore # The key is optional and handled
            except KeyError:
                pass
            else:
                self.user = Member(state=self._state, guild=guild, data=member)
                self._permissions = self.user._permissions or 0
        else:
            try:
                self.user = User(state=self._state, data=data['user'])  # type: ignore # The key is optional and handled
            except KeyError:
                pass

    @property
    def client(self) -> ClientT:
        """:class:`Client`: The client that is handling this interaction.

        Note that :class:`AutoShardedClient`, :class:`~.commands.Bot`, and
        :class:`~.commands.AutoShardedBot` are all subclasses of client.
        """
        return self._client

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: The guild the interaction was sent from."""
        # The user.guild attribute is set in __init__ to the fallback guild if available
        # Therefore, we can use that instead of recreating it every time this property is
        # accessed
        return (self._state and self._state._get_guild(self.guild_id)) or getattr(self.user, 'guild', None)

    @property
    def channel_id(self) -> Optional[int]:
        """Optional[:class:`int`]: The ID of the channel the interaction was sent from."""
        return self.channel.id if self.channel is not None else None

    @property
    def permissions(self) -> Permissions:
        """:class:`Permissions`: The resolved permissions of the member in the channel, including overwrites.

        In a non-guild context where this doesn't apply, an empty permissions object is returned.
        """
        return Permissions(self._permissions)

    @property
    def app_permissions(self) -> Permissions:
        """:class:`Permissions`: The resolved permissions of the application or the bot, including overwrites."""
        return Permissions(self._app_permissions)

    @utils.cached_slot_property('_cs_namespace')
    def namespace(self) -> Namespace:
        """:class:`app_commands.Namespace`: The resolved namespace for this interaction.

        If the interaction is not an application command related interaction or the client does not have a
        tree attached to it then this returns an empty namespace.
        """
        if self.type not in (InteractionType.application_command, InteractionType.autocomplete):
            return Namespace(self, {}, [])

        tree = self._state._command_tree
        if tree is None:
            return Namespace(self, {}, [])

        # The type checker does not understand this narrowing
        data: ApplicationCommandInteractionData = self.data  # type: ignore

        try:
            _, options = tree._get_app_command_options(data)
        except DiscordException:
            options = []

        return Namespace(self, data.get('resolved', {}), options)

    @utils.cached_slot_property('_cs_command')
    def command(self) -> Optional[Union[Command[Any, ..., Any], ContextMenu]]:
        """Optional[Union[:class:`app_commands.Command`, :class:`app_commands.ContextMenu`]]: The command being called from
        this interaction.

        If the interaction is not an application command related interaction or the command is not found in the client's
        attached tree then ``None`` is returned.
        """
        if self.type not in (InteractionType.application_command, InteractionType.autocomplete):
            return None

        tree = self._state._command_tree
        if tree is None:
            return None

        # The type checker does not understand this narrowing
        data: ApplicationCommandInteractionData = self.data  # type: ignore
        cmd_type = data.get('type', 1)
        if cmd_type == 1:
            try:
                command, _ = tree._get_app_command_options(data)
            except DiscordException:
                return None
            else:
                return command
        else:
            return tree._get_context_menu(data)

    @utils.cached_slot_property('_cs_response')
    def response(self) -> InteractionResponse[ClientT]:
        """:class:`InteractionResponse`: Returns an object responsible for handling responding to the interaction.

        A response can only be done once. If secondary messages need to be sent, consider using :attr:`followup`
        instead.
        """
        return InteractionResponse(self)

    @utils.cached_slot_property('_cs_followup')
    def followup(self) -> Webhook:
        """:class:`Webhook`: Returns the follow up webhook for follow up interactions."""
        payload: WebhookPayload = {
            'id': self.application_id,
            'type': 3,
            'token': self.token,
        }
        return Webhook.from_state(data=payload, state=self._state)

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: When the interaction was created."""
        return utils.snowflake_time(self.id)

    @property
    def expires_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: When the interaction expires."""
        return self.created_at + datetime.timedelta(minutes=15)

    def is_expired(self) -> bool:
        """:class:`bool`: Returns ``True`` if the interaction is expired."""
        return utils.utcnow() >= self.expires_at

    def is_guild_integration(self) -> bool:
        """:class:`bool`: Returns ``True`` if the interaction is a guild integration.

        .. versionadded:: 2.4
        """
        if self.guild_id:
            return self.guild_id == self._integration_owners.get(0)
        return False

    def is_user_integration(self) -> bool:
        """:class:`bool`: Returns ``True`` if the interaction is a user integration.

        .. versionadded:: 2.4
        """
        return self.user.id == self._integration_owners.get(1)

    async def original_response(self) -> InteractionMessage:
        """|coro|

        Fetches the original interaction response message associated with the interaction.

        If the interaction response was a newly created message (i.e. through :meth:`InteractionResponse.send_message`
        or :meth:`InteractionResponse.defer`, where ``thinking`` is ``True``) then this returns the message that was sent
        using that response. Otherwise, this returns the message that triggered the interaction (i.e.
        through a component).

        Repeated calls to this will return a cached value.

        Raises
        -------
        HTTPException
            Fetching the original response message failed.
        ClientException
            The channel for the message could not be resolved.
        NotFound
            The interaction response message does not exist.

        Returns
        --------
        InteractionMessage
            The original interaction response message.
        """

        if self._original_response is not None:
            return self._original_response

        # TODO: fix later to not raise?
        channel = self.channel
        if channel is None:
            raise ClientException('Channel for message could not be resolved')

        adapter = async_context.get()
        http = self._state.http
        data = await adapter.get_original_interaction_response(
            application_id=self.application_id,
            token=self.token,
            session=self._session,
            proxy=http.proxy,
            proxy_auth=http.proxy_auth,
        )
        state = _InteractionMessageState(self, self._state)
        # The state and channel parameters are mocked here
        message = InteractionMessage(state=state, channel=channel, data=data)  # type: ignore
        self._original_response = message
        return message

    async def edit_original_response(
        self,
        *,
        content: Optional[str] = MISSING,
        embeds: Sequence[Embed] = MISSING,
        embed: Optional[Embed] = MISSING,
        attachments: Sequence[Union[Attachment, File]] = MISSING,
        view: Optional[View] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
        poll: Poll = MISSING,
    ) -> InteractionMessage:
        """|coro|

        Edits the original interaction response message.

        This is a lower level interface to :meth:`InteractionMessage.edit` in case
        you do not want to fetch the message and save an HTTP request.

        This method is also the only way to edit the original message if
        the message sent was ephemeral.

        Parameters
        ------------
        content: Optional[:class:`str`]
            The content to edit the message with or ``None`` to clear it.
        embeds: List[:class:`Embed`]
            A list of embeds to edit the message with.
        embed: Optional[:class:`Embed`]
            The embed to edit the message with. ``None`` suppresses the embeds.
            This should not be mixed with the ``embeds`` parameter.
        attachments: List[Union[:class:`Attachment`, :class:`File`]]
            A list of attachments to keep in the message as well as new files to upload. If ``[]`` is passed
            then all attachments are removed.

            .. note::

                New files will always appear after current attachments.

        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
            See :meth:`.abc.Messageable.send` for more information.
        view: Optional[:class:`~discord.ui.View`]
            The updated view to update this message with. If ``None`` is passed then
            the view is removed.
        poll: :class:`Poll`
            The poll to create when editing the message.

            .. versionadded:: 2.5

            .. note::

                This is only accepted when the response type is :attr:`InteractionResponseType.deferred_channel_message`.

        Raises
        -------
        HTTPException
            Editing the message failed.
        NotFound
            The interaction response message does not exist.
        Forbidden
            Edited a message that is not yours.
        TypeError
            You specified both ``embed`` and ``embeds``
        ValueError
            The length of ``embeds`` was invalid.

        Returns
        --------
        :class:`InteractionMessage`
            The newly edited message.
        """

        previous_mentions: Optional[AllowedMentions] = self._state.allowed_mentions
        with handle_message_parameters(
            content=content,
            attachments=attachments,
            embed=embed,
            embeds=embeds,
            view=view,
            allowed_mentions=allowed_mentions,
            previous_allowed_mentions=previous_mentions,
            poll=poll,
        ) as params:
            adapter = async_context.get()
            http = self._state.http
            data = await adapter.edit_original_interaction_response(
                self.application_id,
                self.token,
                session=self._session,
                proxy=http.proxy,
                proxy_auth=http.proxy_auth,
                payload=params.payload,
                multipart=params.multipart,
                files=params.files,
            )

        # The message channel types should always match
        state = _InteractionMessageState(self, self._state)
        message = InteractionMessage(state=state, channel=self.channel, data=data)  # type: ignore
        if view and not view.is_finished():
            self._state.store_view(view, message.id, interaction_id=self.id)
        return message

    async def delete_original_response(self) -> None:
        """|coro|

        Deletes the original interaction response message.

        This is a lower level interface to :meth:`InteractionMessage.delete` in case
        you do not want to fetch the message and save an HTTP request.

        Raises
        -------
        HTTPException
            Deleting the message failed.
        NotFound
            The interaction response message does not exist or has already been deleted.
        Forbidden
            Deleted a message that is not yours.
        """
        adapter = async_context.get()
        http = self._state.http
        await adapter.delete_original_interaction_response(
            self.application_id,
            self.token,
            session=self._session,
            proxy=http.proxy,
            proxy_auth=http.proxy_auth,
        )

    async def translate(
        self, string: Union[str, locale_str], *, locale: Locale = MISSING, data: Any = MISSING
    ) -> Optional[str]:
        """|coro|

        Translates a string using the set :class:`~discord.app_commands.Translator`.

        .. versionadded:: 2.1

        Parameters
        ----------
        string: Union[:class:`str`, :class:`~discord.app_commands.locale_str`]
            The string to translate.
            :class:`~discord.app_commands.locale_str` can be used to add more context,
            information, or any metadata necessary.
        locale: :class:`Locale`
            The locale to use, this is handy if you want the translation
            for a specific locale.
            Defaults to the user's :attr:`.locale`.
        data: Any
            The extraneous data that is being translated.
            If not specified, either :attr:`.command` or :attr:`.message` will be passed,
            depending on which is available in the context.

        Returns
        --------
        Optional[:class:`str`]
            The translated string, or ``None`` if a translator was not set.
        """
        translator = self._state._translator
        if not translator:
            return None

        if not isinstance(string, locale_str):
            string = locale_str(string)
        if locale is MISSING:
            locale = self.locale
        if data is MISSING:
            data = self.command or self.message

        context = TranslationContext(location=TranslationContextLocation.other, data=data)
        return await translator.translate(string, locale=locale, context=context)


class InteractionCallbackActivity:
    """Represents an activity instance returned by an interaction callback.

    .. versionadded:: 2.5

    Attributes
    ----------
    id: :class:`str`
        The activity instance ID.
    """

    __slots__ = ('id',)

    def __init__(self, *, data: InteractionCallbackActivityPayload) -> None:
        self.id: str = data['id']

    def __repr__(self) -> str:
        return f'<InteractionCallbackActivity id={self.id!r}>'


class InteractionCallback:
    """Represents an interaction callback invoking interaction.

    Attributes
    ----------
    id: :class:`int`
        The ID of the interaction.
    type: :class:`InteractionType`
        The interaction response type.
    activity_instance_id: Optional[:class:`str`]
        The ID of the activity that was launched as response of this interaction.
    message_id: Optional[:class:`int`]
        The ID of the message that was sent as response of this interaction.
    """

    __slots__ = (
        '_state',
        'id',
        '_message',
        'type',
        'activity_instance_id',
        'message_id',
    )

    def __init__(self, *, data: InteractionCallbackResponsePayload, state: ConnectionState) -> None:
        self._state: ConnectionState = state
        self.id: int = int(data['id'])
        self._message: Optional[Message] = None
        self._update(data)

    def __repr__(self) -> str:
        return f'<InteractionCallback id={self.id}>'

    def _update(self, data: InteractionCallbackResponsePayload) -> None:
        self.type: InteractionType = try_enum(InteractionType, data['type'])
        self.activity_instance_id: Optional[str] = data.get('activity_instance_id')
        self.message_id: Optional[int] = utils._get_as_snowflake(data, 'response_message_id')

    @property
    def message(self) -> Optional[Message]:
        """Optional[:class:`Message`]: Returns the cached message, or ``None``."""
        return self._message or self._state._get_message(self.message_id)


class InteractionCallbackResource(Generic[ClientT]):
    """Represents an interaction callback's resource.

    Attributes
    ----------
    type: :class:`InteractionResponseType`
        The interaction callback response type.
    activity: Optional[:class:`InteractionCallbackActivity`]
        The activity that was launched as a response to the interaction.
    message: Optional[:class:`InteractionMessage`]
        The message that was sent as a response to the interaction.
    """

    __slots__ = (
        '_state',
        '_parent',
        'activity',
        'message',
        'type',
    )

    def __init__(
        self,
        *,
        data: InteractionCallbackResourcePayload,
        state: ConnectionState,
        parent: InteractionCallbackResponse,
    ) -> None:
        self._state: ConnectionState = state
        self._parent: InteractionCallbackResponse = parent
        self.activity: Optional[InteractionCallbackActivity] = None
        self.message: Optional[InteractionMessage] = None
        self._update(data)

    def _update(self, data: InteractionCallbackResourcePayload) -> None:
        try:
            self.type: InteractionResponseType = try_enum(InteractionResponseType, data['type'])
        except KeyError:
            pass

        try:
            self.activity = InteractionCallbackActivity(data=data['activity_instance'])
        except KeyError:
            pass

        try:
            self.message = InteractionMessage(
                state=self._state,
                channel=self._parent._parent.channel,  # type: ignore
                data=data['message'],
            )
        except KeyError:
            pass

        self._parent.interaction._message = self.message


class InteractionCallbackResponse(Generic[ClientT]):
    """Represents a Discord response to an interaction.

    .. versionadded:: 2.5

    Attributes
    ----------
    interaction: :class:`InteractionCallback`
        The interaction callback response.
    resource: :class:`InteractionCallbackResource`
        The interaction callback resource.
    """

    __slots__ = (
        '_parent',
        '_state',
        'interaction',
        'resource',
    )

    def __init__(
        self,
        *,
        parent: Interaction[ClientT],
        data: InteractionCallbackPayload,
    ) -> None:
        self._parent: Interaction[ClientT] = parent
        self._state: ConnectionState = parent._state

        self.interaction: InteractionCallback = InteractionCallback(data=data['interaction'], state=self._state)
        self.resource: Optional[InteractionCallbackResource] = None

    def __repr__(self) -> str:
        return f'<InteractionCallbackResponse interaction_id={self.interaction.id}>'

    def _update(self, data: InteractionCallbackPayload) -> None:
        interaction = data['interaction']
        resource = data.get('resource', {})
        self.interaction._update(interaction)
        if self.resource:
            self.resource._update(resource)  # pyright: ignore[reportArgumentType]
        else:
            self.resource = InteractionCallbackResource(data=resource, state=self._state, parent=self)  # type: ignore

        self._parent._original_response = self.interaction.message  # type: ignore


class InteractionResponse(Generic[ClientT]):
    """Represents a Discord interaction response.

    This type can be accessed through :attr:`Interaction.response`.

    .. versionadded:: 2.0
    """

    __slots__: Tuple[str, ...] = (
        '_response_type',
        '_parent',
    )

    def __init__(self, parent: Interaction[ClientT]):
        self._parent: Interaction[ClientT] = parent
        self._response_type: Optional[InteractionResponseType] = None

    def is_done(self) -> bool:
        """:class:`bool`: Indicates whether an interaction response has been done before.

        An interaction can only be responded to once.
        """
        return self._response_type is not None

    @property
    def type(self) -> Optional[InteractionResponseType]:
        """:class:`InteractionResponseType`: The type of response that was sent, ``None`` if response is not done."""
        return self._response_type

    @overload
    async def defer(
        self,
        *,
        ephemeral: bool = ...,
        thinking: bool = ...,
        with_response: Literal[True] = ...,
    ) -> InteractionCallbackResponse[ClientT]:
        ...

    @overload
    async def defer(
        self,
        *,
        ephemeral: bool = ...,
        thinking: bool = ...,
        with_response: Literal[False] = False,
    ) -> None:
        ...

    async def defer(
        self,
        *,
        ephemeral: bool = False,
        thinking: bool = False,
        with_response: bool = True,
    ) -> Optional[InteractionCallbackResponse[ClientT]]:
        """|coro|

        Defers the interaction response.

        This is typically used when the interaction is acknowledged
        and a secondary action will be done later.

        This is only supported with the following interaction types:

        - :attr:`InteractionType.application_command`
        - :attr:`InteractionType.component`
        - :attr:`InteractionType.modal_submit`

        Parameters
        -----------
        ephemeral: :class:`bool`
            Indicates whether the deferred message will eventually be ephemeral.
            This only applies to :attr:`InteractionType.application_command` interactions, or if ``thinking`` is ``True``.
        thinking: :class:`bool`
            Indicates whether the deferred type should be :attr:`InteractionResponseType.deferred_channel_message`
            instead of the default :attr:`InteractionResponseType.deferred_message_update` if both are valid.
            In UI terms, this is represented as if the bot is thinking of a response. It is your responsibility to
            eventually send a followup message via :attr:`Interaction.followup` to make this thinking state go away.
            Application commands (AKA Slash commands) cannot use :attr:`InteractionResponseType.deferred_message_update`.
        with_response: :class:`bool`
            Whether to return the interaction response callback resource.

            .. versionadded:: 2.5

        Raises
        -------
        HTTPException
            Deferring the interaction failed.
        InteractionResponded
            This interaction has already been responded to before.

        Returns
        -------
        Optional[:class:`InteractionCallback`]
            The interaction callback resource, or ``None``.
        """
        if self._response_type:
            raise InteractionResponded(self._parent)

        defer_type: int = 0
        data: Optional[Dict[str, Any]] = None
        parent = self._parent
        if parent.type is InteractionType.component or parent.type is InteractionType.modal_submit:
            defer_type = (
                InteractionResponseType.deferred_channel_message.value
                if thinking
                else InteractionResponseType.deferred_message_update.value
            )
            if thinking and ephemeral:
                data = {'flags': 64}
        elif parent.type is InteractionType.application_command:
            defer_type = InteractionResponseType.deferred_channel_message.value
            if ephemeral:
                data = {'flags': 64}

        if defer_type:
            adapter = async_context.get()
            params = interaction_response_params(type=defer_type, data=data)
            http = parent._state.http
            response = await adapter.create_interaction_response(
                parent.id,
                parent.token,
                session=parent._session,
                proxy=http.proxy,
                proxy_auth=http.proxy_auth,
                params=params,
                with_response=with_response,
            )
            self._response_type = InteractionResponseType(defer_type)
            if response:
                return InteractionCallbackResponse(
                    parent=parent,
                    data=response,
                )

    async def pong(self) -> None:
        """|coro|

        Pongs the ping interaction.

        This should rarely be used.

        Raises
        -------
        HTTPException
            Ponging the interaction failed.
        InteractionResponded
            This interaction has already been responded to before.
        """
        if self._response_type:
            raise InteractionResponded(self._parent)

        parent = self._parent
        if parent.type is InteractionType.ping:
            adapter = async_context.get()
            params = interaction_response_params(InteractionResponseType.pong.value)
            http = parent._state.http
            await adapter.create_interaction_response(
                parent.id,
                parent.token,
                session=parent._session,
                proxy=http.proxy,
                proxy_auth=http.proxy_auth,
                params=params,
            )
            self._response_type = InteractionResponseType.pong

    @overload
    async def send_message(
        self,
        content: Optional[Any] = ...,
        *,
        embed: Embed = ...,
        embeds: Sequence[Embed] = ...,
        file: File = ...,
        files: Sequence[File] = ...,
        view: View = ...,
        tts: bool = ...,
        ephemeral: bool = ...,
        allowed_mentions: AllowedMentions = ...,
        suppress_embeds: bool = ...,
        silent: bool = ...,
        delete_after: Optional[float] = ...,
        poll: Poll = ...,
        with_response: Literal[True] = ...,
    ) -> InteractionCallbackResponse[ClientT]:
        ...

    @overload
    async def send_message(
        self,
        content: Optional[Any] = ...,
        *,
        embed: Embed = ...,
        embeds: Sequence[Embed] = ...,
        file: File = ...,
        files: Sequence[File] = ...,
        view: View = ...,
        tts: bool = ...,
        ephemeral: bool = ...,
        allowed_mentions: AllowedMentions = ...,
        suppress_embeds: bool = ...,
        silent: bool = ...,
        delete_after: Optional[float] = ...,
        poll: Poll = ...,
        with_response: Literal[False] = False,
    ) -> None:
        ...

    async def send_message(
        self,
        content: Optional[Any] = None,
        *,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        view: View = MISSING,
        tts: bool = False,
        ephemeral: bool = False,
        allowed_mentions: AllowedMentions = MISSING,
        suppress_embeds: bool = False,
        silent: bool = False,
        delete_after: Optional[float] = None,
        poll: Poll = MISSING,
        with_response: bool = True,
    ) -> Optional[InteractionCallbackResponse[ClientT]]:
        """|coro|

        Responds to this interaction by sending a message.

        Parameters
        -----------
        content: Optional[:class:`str`]
            The content of the message to send.
        embeds: List[:class:`Embed`]
            A list of embeds to send with the content. Maximum of 10. This cannot
            be mixed with the ``embed`` parameter.
        embed: :class:`Embed`
            The rich embed for the content to send. This cannot be mixed with
            ``embeds`` parameter.
        file: :class:`~discord.File`
            The file to upload.
        files: List[:class:`~discord.File`]
            A list of files to upload. Must be a maximum of 10.
        tts: :class:`bool`
            Indicates if the message should be sent using text-to-speech.
        view: :class:`discord.ui.View`
            The view to send with the message.
        ephemeral: :class:`bool`
            Indicates if the message should only be visible to the user who started the interaction.
            If a view is sent with an ephemeral message and it has no timeout set then the timeout
            is set to 15 minutes.
        allowed_mentions: :class:`~discord.AllowedMentions`
            Controls the mentions being processed in this message. See :meth:`.abc.Messageable.send` for
            more information.
        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This sends the message without any embeds if set to ``True``.
        silent: :class:`bool`
            Whether to suppress push and desktop notifications for the message. This will increment the mention counter
            in the UI, but will not actually send a notification.

            .. versionadded:: 2.2
        delete_after: :class:`float`
            If provided, the number of seconds to wait in the background
            before deleting the message we just sent. If the deletion fails,
            then it is silently ignored.

            .. versionadded:: 2.1
        poll: :class:`~discord.Poll`
            The poll to send with this message.

            .. versionadded:: 2.4
        with_response: :class:`bool`
            Whether to return the interaction response callback resource.

            .. versionadded:: 2.5

        Raises
        -------
        HTTPException
            Sending the message failed.
        TypeError
            You specified both ``embed`` and ``embeds`` or ``file`` and ``files``.
        ValueError
            The length of ``embeds`` was invalid.
        InteractionResponded
            This interaction has already been responded to before.

        Returns
        -------
        Optional[:class:`InteractionCallback`]
            The interaction callback data, or ``None``.
        """
        if self._response_type:
            raise InteractionResponded(self._parent)

        if ephemeral or suppress_embeds or silent:
            flags = MessageFlags._from_value(0)
            flags.ephemeral = ephemeral
            flags.suppress_embeds = suppress_embeds
            flags.suppress_notifications = silent
        else:
            flags = MISSING

        parent = self._parent
        adapter = async_context.get()
        params = interaction_message_response_params(
            type=InteractionResponseType.channel_message.value,
            content=content,
            tts=tts,
            embeds=embeds,
            embed=embed,
            file=file,
            files=files,
            previous_allowed_mentions=parent._state.allowed_mentions,
            allowed_mentions=allowed_mentions,
            flags=flags,
            view=view,
            poll=poll,
        )

        http = parent._state.http
        response = await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            proxy=http.proxy,
            proxy_auth=http.proxy_auth,
            params=params,
            with_response=with_response,
        )

        if view is not MISSING and not view.is_finished():
            if ephemeral and view.timeout is None:
                view.timeout = 15 * 60.0

            # If the interaction type isn't an application command then there's no way
            # to obtain this interaction_id again, so just default to None
            entity_id = parent.id if parent.type is InteractionType.application_command else None
            self._parent._state.store_view(view, entity_id)

        self._response_type = InteractionResponseType.channel_message

        if delete_after is not None:

            async def inner_call(delay: float = delete_after):
                await asyncio.sleep(delay)
                try:
                    await self._parent.delete_original_response()
                except HTTPException:
                    pass

            asyncio.create_task(inner_call())
        if response:
            return InteractionCallbackResponse(
                parent=parent,
                data=response,
            )

    @overload
    async def edit_message(
        self,
        *,
        content: Optional[Any] = ...,
        embed: Optional[Embed] = ...,
        embeds: Sequence[Embed] = ...,
        attachments: Sequence[Union[Attachment, File]] = ...,
        view: Optional[View] = ...,
        allowed_mentions: Optional[AllowedMentions] = ...,
        delete_after: Optional[float] = ...,
        suppress_embeds: bool = ...,
        with_response: Literal[True] = ...,
    ) -> InteractionCallbackResponse[ClientT]:
        ...

    @overload
    async def edit_message(
        self,
        *,
        content: Optional[Any] = ...,
        embed: Optional[Embed] = ...,
        embeds: Sequence[Embed] = ...,
        attachments: Sequence[Union[Attachment, File]] = ...,
        view: Optional[View] = ...,
        allowed_mentions: Optional[AllowedMentions] = ...,
        delete_after: Optional[float] = ...,
        suppress_embeds: bool = ...,
        with_response: Literal[False] = False,
    ) -> None:
        ...

    async def edit_message(
        self,
        *,
        content: Optional[Any] = MISSING,
        embed: Optional[Embed] = MISSING,
        embeds: Sequence[Embed] = MISSING,
        attachments: Sequence[Union[Attachment, File]] = MISSING,
        view: Optional[View] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = MISSING,
        delete_after: Optional[float] = None,
        suppress_embeds: bool = MISSING,
        with_response: bool = True,
    ) -> Optional[InteractionCallbackResponse[ClientT]]:
        """|coro|

        Responds to this interaction by editing the original message of
        a component or modal interaction.

        Parameters
        -----------
        content: Optional[:class:`str`]
            The new content to replace the message with. ``None`` removes the content.
        embeds: List[:class:`Embed`]
            A list of embeds to edit the message with.
        embed: Optional[:class:`Embed`]
            The embed to edit the message with. ``None`` suppresses the embeds.
            This should not be mixed with the ``embeds`` parameter.
        attachments: List[Union[:class:`Attachment`, :class:`File`]]
            A list of attachments to keep in the message as well as new files to upload. If ``[]`` is passed
            then all attachments are removed.

            .. note::

                New files will always appear after current attachments.

        view: Optional[:class:`~discord.ui.View`]
            The updated view to update this message with. If ``None`` is passed then
            the view is removed.
        allowed_mentions: Optional[:class:`~discord.AllowedMentions`]
            Controls the mentions being processed in this message. See :meth:`.Message.edit`
            for more information.
        delete_after: :class:`float`
            If provided, the number of seconds to wait in the background
            before deleting the message we just edited. If the deletion fails,
            then it is silently ignored.

            .. versionadded:: 2.2
        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This removes
            all the embeds if set to ``True``. If set to ``False``
            this brings the embeds back if they were suppressed.
            Using this parameter requires :attr:`~.Permissions.manage_messages`.

            .. versionadded:: 2.4
        with_response: :class:`bool`
            Whether to return the interaction response callback resource.

            .. versionadded:: 2.5

        Raises
        -------
        HTTPException
            Editing the message failed.
        TypeError
            You specified both ``embed`` and ``embeds``.
        InteractionResponded
            This interaction has already been responded to before.

        Returns
        -------
        Optional[:class:`InteractionCallback`]
            The interaction callback data, or ``None``.
        """
        if self._response_type:
            raise InteractionResponded(self._parent)

        parent = self._parent
        msg = parent.message
        state = parent._state
        if msg is not None:
            message_id = msg.id
            # If this was invoked via an application command then we can use its original interaction ID
            # Since this is used as a cache key for view updates
            original_interaction_id = msg.interaction_metadata.id if msg.interaction_metadata is not None else None
        else:
            message_id = None
            original_interaction_id = None

        if parent.type not in (InteractionType.component, InteractionType.modal_submit):
            return

        if view is not MISSING and message_id is not None:
            state.prevent_view_updates_for(message_id)

        if suppress_embeds is not MISSING:
            flags = MessageFlags._from_value(0)
            flags.suppress_embeds = suppress_embeds
        else:
            flags = MISSING

        adapter = async_context.get()
        params = interaction_message_response_params(
            type=InteractionResponseType.message_update.value,
            content=content,
            embed=embed,
            embeds=embeds,
            view=view,
            attachments=attachments,
            previous_allowed_mentions=parent._state.allowed_mentions,
            allowed_mentions=allowed_mentions,
            flags=flags,
        )

        http = parent._state.http
        response = await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            proxy=http.proxy,
            proxy_auth=http.proxy_auth,
            params=params,
            with_response=with_response,
        )

        if view and not view.is_finished():
            state.store_view(view, message_id, interaction_id=original_interaction_id)

        self._response_type = InteractionResponseType.message_update

        if delete_after is not None:

            async def inner_call(delay: float = delete_after):
                await asyncio.sleep(delay)
                try:
                    await self._parent.delete_original_response()
                except HTTPException:
                    pass

            asyncio.create_task(inner_call())

        if response:
            return InteractionCallbackResponse(
                parent=parent,
                data=response,
            )

    @overload
    async def send_modal(
        self, modal: Modal, /, *, with_response: Literal[True] = ...
    ) -> InteractionCallbackResponse[ClientT]:
        ...

    @overload
    async def send_modal(self, modal: Modal, /, *, with_response: Literal[False] = False) -> None:
        ...

    async def send_modal(
        self, modal: Modal, /, *, with_response: bool = True
    ) -> Optional[InteractionCallbackResponse[ClientT]]:
        """|coro|

        Responds to this interaction by sending a modal.

        Parameters
        -----------
        modal: :class:`~discord.ui.Modal`
            The modal to send.
        with_response: :class:`bool`
            Whether to return the interaction response callback resource.

            .. versionadded:: 2.5

        Raises
        -------
        HTTPException
            Sending the modal failed.
        InteractionResponded
            This interaction has already been responded to before.

        Returns
        -------
        Optional[:class:`InteractionCallback`]
            The interaction callback data, or ``None``.
        """
        if self._response_type:
            raise InteractionResponded(self._parent)

        parent = self._parent

        adapter = async_context.get()
        http = parent._state.http

        params = interaction_response_params(InteractionResponseType.modal.value, modal.to_dict())
        response = await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            proxy=http.proxy,
            proxy_auth=http.proxy_auth,
            params=params,
            with_response=with_response,
        )
        if not modal.is_finished():
            self._parent._state.store_view(modal)
        self._response_type = InteractionResponseType.modal

        if response:
            return InteractionCallbackResponse(
                parent=parent,
                data=response,
            )

    async def autocomplete(self, choices: Sequence[Choice[ChoiceT]]) -> None:
        """|coro|

        Responds to this interaction by giving the user the choices they can use.

        Parameters
        -----------
        choices: List[:class:`~discord.app_commands.Choice`]
            The list of new choices as the user is typing.

        Raises
        -------
        HTTPException
            Sending the choices failed.
        ValueError
            This interaction cannot respond with autocomplete.
        InteractionResponded
            This interaction has already been responded to before.
        """
        if self._response_type:
            raise InteractionResponded(self._parent)

        translator = self._parent._state._translator
        if translator is not None:
            user_locale = self._parent.locale
            payload: Dict[str, Any] = {
                'choices': [await option.get_translated_payload_for_locale(translator, user_locale) for option in choices],
            }
        else:
            payload: Dict[str, Any] = {
                'choices': [option.to_dict() for option in choices],
            }

        parent = self._parent
        if parent.type is not InteractionType.autocomplete:
            raise ValueError('cannot respond to this interaction with autocomplete.')

        adapter = async_context.get()
        http = parent._state.http
        params = interaction_response_params(type=InteractionResponseType.autocomplete_result.value, data=payload)
        await adapter.create_interaction_response(
            parent.id,
            parent.token,
            session=parent._session,
            proxy=http.proxy,
            proxy_auth=http.proxy_auth,
            params=params,
        )

        self._response_type = InteractionResponseType.autocomplete_result


class _InteractionMessageState:
    __slots__ = ('_parent', '_interaction')

    def __init__(self, interaction: Interaction, parent: ConnectionState):
        self._interaction: Interaction = interaction
        self._parent: ConnectionState = parent

    def _get_guild(self, guild_id):
        return self._parent._get_guild(guild_id)

    def store_user(self, data, *, cache: bool = True):
        return self._parent.store_user(data, cache=cache)

    def create_user(self, data):
        return self._parent.create_user(data)

    @property
    def http(self):
        return self._parent.http

    def __getattr__(self, attr):
        return getattr(self._parent, attr)


class InteractionMessage(Message):
    """Represents the original interaction response message.

    This allows you to edit or delete the message associated with
    the interaction response. To retrieve this object see :meth:`Interaction.original_response`.

    This inherits from :class:`discord.Message` with changes to
    :meth:`edit` and :meth:`delete` to work.

    .. versionadded:: 2.0
    """

    __slots__ = ()
    _state: _InteractionMessageState

    async def edit(
        self,
        *,
        content: Optional[str] = MISSING,
        embeds: Sequence[Embed] = MISSING,
        embed: Optional[Embed] = MISSING,
        attachments: Sequence[Union[Attachment, File]] = MISSING,
        view: Optional[View] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
        delete_after: Optional[float] = None,
        poll: Poll = MISSING,
    ) -> InteractionMessage:
        """|coro|

        Edits the message.

        Parameters
        ------------
        content: Optional[:class:`str`]
            The content to edit the message with or ``None`` to clear it.
        embeds: List[:class:`Embed`]
            A list of embeds to edit the message with.
        embed: Optional[:class:`Embed`]
            The embed to edit the message with. ``None`` suppresses the embeds.
            This should not be mixed with the ``embeds`` parameter.
        attachments: List[Union[:class:`Attachment`, :class:`File`]]
            A list of attachments to keep in the message as well as new files to upload. If ``[]`` is passed
            then all attachments are removed.

            .. note::

                New files will always appear after current attachments.

        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
            See :meth:`.abc.Messageable.send` for more information.
        view: Optional[:class:`~discord.ui.View`]
            The updated view to update this message with. If ``None`` is passed then
            the view is removed.
        delete_after: Optional[:class:`float`]
            If provided, the number of seconds to wait in the background
            before deleting the message we just sent. If the deletion fails,
            then it is silently ignored.

            .. versionadded:: 2.2
        poll: :class:`~discord.Poll`
            The poll to create when editing the message.

            .. versionadded:: 2.5

            .. note::

                This is only accepted if the interaction response's :attr:`InteractionResponse.type`
                attribute is :attr:`InteractionResponseType.deferred_channel_message`.

        Raises
        -------
        HTTPException
            Editing the message failed.
        Forbidden
            Edited a message that is not yours.
        TypeError
            You specified both ``embed`` and ``embeds``
        ValueError
            The length of ``embeds`` was invalid.

        Returns
        ---------
        :class:`InteractionMessage`
            The newly edited message.
        """
        res = await self._state._interaction.edit_original_response(
            content=content,
            embeds=embeds,
            embed=embed,
            attachments=attachments,
            view=view,
            allowed_mentions=allowed_mentions,
            poll=poll,
        )
        if delete_after is not None:
            await self.delete(delay=delete_after)
        return res

    async def add_files(self, *files: File) -> InteractionMessage:
        r"""|coro|

        Adds new files to the end of the message attachments.

        .. versionadded:: 2.0

        Parameters
        -----------
        \*files: :class:`File`
            New files to add to the message.

        Raises
        -------
        HTTPException
            Editing the message failed.
        Forbidden
            Tried to edit a message that isn't yours.

        Returns
        ---------
        :class:`InteractionMessage`
            The newly edited message.
        """
        return await self.edit(attachments=[*self.attachments, *files])

    async def remove_attachments(self, *attachments: Attachment) -> InteractionMessage:
        r"""|coro|

        Removes attachments from the message.

        .. versionadded:: 2.0

        Parameters
        -----------
        \*attachments: :class:`Attachment`
            Attachments to remove from the message.

        Raises
        -------
        HTTPException
            Editing the message failed.
        Forbidden
            Tried to edit a message that isn't yours.

        Returns
        ---------
        :class:`InteractionMessage`
            The newly edited message.
        """
        return await self.edit(attachments=[a for a in self.attachments if a not in attachments])

    async def delete(self, *, delay: Optional[float] = None) -> None:
        """|coro|

        Deletes the message.

        Parameters
        -----------
        delay: Optional[:class:`float`]
            If provided, the number of seconds to wait before deleting the message.
            The waiting is done in the background and deletion failures are ignored.

        Raises
        ------
        Forbidden
            You do not have proper permissions to delete the message.
        NotFound
            The message was deleted already.
        HTTPException
            Deleting the message failed.
        """

        if delay is not None:

            async def inner_call(delay: float = delay):
                await asyncio.sleep(delay)
                try:
                    await self._state._interaction.delete_original_response()
                except HTTPException:
                    pass

            asyncio.create_task(inner_call())
        else:
            await self._state._interaction.delete_original_response()
