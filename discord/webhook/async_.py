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
import asyncio
import re

from urllib.parse import quote as urlquote
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING, Sequence, Tuple, Union, TypeVar, Type, overload
from contextvars import ContextVar
import weakref

import aiohttp

from .. import utils
from ..errors import HTTPException, Forbidden, NotFound, DiscordServerError
from ..message import Message
from ..enums import try_enum, WebhookType, ChannelType, DefaultAvatar
from ..user import BaseUser, User
from ..flags import MessageFlags
from ..asset import Asset
from ..partial_emoji import PartialEmoji
from ..http import Route, handle_message_parameters, MultipartParameters, HTTPClient, json_or_text
from ..mixins import Hashable
from ..channel import TextChannel, ForumChannel, PartialMessageable, ForumTag
from ..file import File

__all__ = (
    'Webhook',
    'WebhookMessage',
    'PartialWebhookChannel',
    'PartialWebhookGuild',
)

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from typing_extensions import Self
    from types import TracebackType

    from ..embeds import Embed
    from ..client import Client
    from ..mentions import AllowedMentions
    from ..message import Attachment
    from ..state import ConnectionState
    from ..http import Response
    from ..guild import Guild
    from ..emoji import Emoji
    from ..channel import VoiceChannel
    from ..abc import Snowflake
    from ..ui.view import View
    from ..poll import Poll
    import datetime
    from ..types.webhook import (
        Webhook as WebhookPayload,
        SourceGuild as SourceGuildPayload,
    )
    from ..types.message import (
        Message as MessagePayload,
    )
    from ..types.user import (
        User as UserPayload,
        PartialUser as PartialUserPayload,
    )
    from ..types.channel import (
        PartialChannel as PartialChannelPayload,
    )
    from ..types.emoji import PartialEmoji as PartialEmojiPayload
    from ..types.snowflake import SnowflakeList
    from ..types.interactions import (
        InteractionCallback as InteractionCallbackResponsePayload,
    )

    BE = TypeVar('BE', bound=BaseException)
    _State = Union[ConnectionState, '_WebhookState']

MISSING: Any = utils.MISSING


class AsyncDeferredLock:
    def __init__(self, lock: asyncio.Lock):
        self.lock = lock
        self.delta: Optional[float] = None

    async def __aenter__(self) -> Self:
        await self.lock.acquire()
        return self

    def delay_by(self, delta: float) -> None:
        self.delta = delta

    async def __aexit__(
        self,
        exc_type: Optional[Type[BE]],
        exc: Optional[BE],
        traceback: Optional[TracebackType],
    ) -> None:
        if self.delta:
            await asyncio.sleep(self.delta)
        self.lock.release()


class AsyncWebhookAdapter:
    def __init__(self):
        self._locks: weakref.WeakValueDictionary[Any, asyncio.Lock] = weakref.WeakValueDictionary()

    async def request(
        self,
        route: Route,
        session: aiohttp.ClientSession,
        *,
        payload: Optional[Dict[str, Any]] = None,
        multipart: Optional[List[Dict[str, Any]]] = None,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        files: Optional[Sequence[File]] = None,
        reason: Optional[str] = None,
        auth_token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        headers: Dict[str, str] = {}
        files = files or []
        to_send: Optional[Union[str, aiohttp.FormData]] = None
        bucket = (route.webhook_id, route.webhook_token)

        try:
            lock = self._locks[bucket]
        except KeyError:
            self._locks[bucket] = lock = asyncio.Lock()

        if payload is not None:
            headers['Content-Type'] = 'application/json'
            to_send = utils._to_json(payload)

        if auth_token is not None:
            headers['Authorization'] = f'Bot {auth_token}'

        if reason is not None:
            headers['X-Audit-Log-Reason'] = urlquote(reason, safe='/ ')

        response: Optional[aiohttp.ClientResponse] = None
        data: Optional[Union[Dict[str, Any], str]] = None
        method = route.method
        url = route.url
        webhook_id = route.webhook_id

        async with AsyncDeferredLock(lock) as lock:
            for attempt in range(5):
                for file in files:
                    file.reset(seek=attempt)

                if multipart:
                    form_data = aiohttp.FormData(quote_fields=False)
                    for p in multipart:
                        form_data.add_field(**p)
                    to_send = form_data

                try:
                    async with session.request(
                        method, url, data=to_send, headers=headers, params=params, proxy=proxy, proxy_auth=proxy_auth
                    ) as response:
                        _log.debug(
                            'Webhook ID %s with %s %s has returned status code %s',
                            webhook_id,
                            method,
                            url,
                            response.status,
                        )
                        data = await json_or_text(response)

                        remaining = response.headers.get('X-Ratelimit-Remaining')
                        if remaining == '0' and response.status != 429:
                            delta = utils._parse_ratelimit_header(response)
                            _log.debug(
                                'Webhook ID %s has exhausted its rate limit bucket (retry: %s).',
                                webhook_id,
                                delta,
                            )
                            lock.delay_by(delta)

                        if 300 > response.status >= 200:
                            return data

                        if response.status == 429:
                            if not response.headers.get('Via'):
                                raise HTTPException(response, data)
                            fmt = 'Webhook ID %s is rate limited. Retrying in %.2f seconds.'

                            retry_after: float = data['retry_after']  # type: ignore
                            _log.warning(fmt, webhook_id, retry_after)
                            await asyncio.sleep(retry_after)
                            continue

                        if response.status >= 500:
                            await asyncio.sleep(1 + attempt * 2)
                            continue

                        if response.status == 403:
                            raise Forbidden(response, data)
                        elif response.status == 404:
                            raise NotFound(response, data)
                        else:
                            raise HTTPException(response, data)

                except OSError as e:
                    if attempt < 4 and e.errno in (54, 10054):
                        await asyncio.sleep(1 + attempt * 2)
                        continue
                    raise

            if response:
                if response.status >= 500:
                    raise DiscordServerError(response, data)
                raise HTTPException(response, data)

            raise RuntimeError('Unreachable code in HTTP handling.')

    def delete_webhook(
        self,
        webhook_id: int,
        *,
        token: Optional[str] = None,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        reason: Optional[str] = None,
    ) -> Response[None]:
        route = Route('DELETE', '/webhooks/{webhook_id}', webhook_id=webhook_id)
        return self.request(route, session=session, proxy=proxy, proxy_auth=proxy_auth, reason=reason, auth_token=token)

    def delete_webhook_with_token(
        self,
        webhook_id: int,
        token: str,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        reason: Optional[str] = None,
    ) -> Response[None]:
        route = Route('DELETE', '/webhooks/{webhook_id}/{webhook_token}', webhook_id=webhook_id, webhook_token=token)
        return self.request(route, session=session, proxy=proxy, proxy_auth=proxy_auth, reason=reason)

    def edit_webhook(
        self,
        webhook_id: int,
        token: str,
        payload: Dict[str, Any],
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        reason: Optional[str] = None,
    ) -> Response[WebhookPayload]:
        route = Route('PATCH', '/webhooks/{webhook_id}', webhook_id=webhook_id)
        return self.request(
            route,
            session=session,
            proxy=proxy,
            proxy_auth=proxy_auth,
            reason=reason,
            payload=payload,
            auth_token=token,
        )

    def edit_webhook_with_token(
        self,
        webhook_id: int,
        token: str,
        payload: Dict[str, Any],
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        reason: Optional[str] = None,
    ) -> Response[WebhookPayload]:
        route = Route('PATCH', '/webhooks/{webhook_id}/{webhook_token}', webhook_id=webhook_id, webhook_token=token)
        return self.request(route, session=session, proxy=proxy, proxy_auth=proxy_auth, reason=reason, payload=payload)

    def execute_webhook(
        self,
        webhook_id: int,
        token: str,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        payload: Optional[Dict[str, Any]] = None,
        multipart: Optional[List[Dict[str, Any]]] = None,
        files: Optional[Sequence[File]] = None,
        thread_id: Optional[int] = None,
        wait: bool = False,
    ) -> Response[Optional[MessagePayload]]:
        params = {'wait': int(wait)}
        if thread_id:
            params['thread_id'] = thread_id
        route = Route('POST', '/webhooks/{webhook_id}/{webhook_token}', webhook_id=webhook_id, webhook_token=token)
        return self.request(
            route,
            session=session,
            proxy=proxy,
            proxy_auth=proxy_auth,
            payload=payload,
            multipart=multipart,
            files=files,
            params=params,
        )

    def get_webhook_message(
        self,
        webhook_id: int,
        token: str,
        message_id: int,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        thread_id: Optional[int] = None,
    ) -> Response[MessagePayload]:
        route = Route(
            'GET',
            '/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}',
            webhook_id=webhook_id,
            webhook_token=token,
            message_id=message_id,
        )
        params = None if thread_id is None else {'thread_id': thread_id}
        return self.request(route, session=session, proxy=proxy, proxy_auth=proxy_auth, params=params)

    def edit_webhook_message(
        self,
        webhook_id: int,
        token: str,
        message_id: int,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        payload: Optional[Dict[str, Any]] = None,
        multipart: Optional[List[Dict[str, Any]]] = None,
        files: Optional[Sequence[File]] = None,
        thread_id: Optional[int] = None,
    ) -> Response[MessagePayload]:
        route = Route(
            'PATCH',
            '/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}',
            webhook_id=webhook_id,
            webhook_token=token,
            message_id=message_id,
        )
        params = None if thread_id is None else {'thread_id': thread_id}
        return self.request(
            route,
            session=session,
            proxy=proxy,
            proxy_auth=proxy_auth,
            payload=payload,
            multipart=multipart,
            files=files,
            params=params,
        )

    def delete_webhook_message(
        self,
        webhook_id: int,
        token: str,
        message_id: int,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        thread_id: Optional[int] = None,
    ) -> Response[None]:
        route = Route(
            'DELETE',
            '/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}',
            webhook_id=webhook_id,
            webhook_token=token,
            message_id=message_id,
        )
        params = None if thread_id is None else {'thread_id': thread_id}
        return self.request(route, session=session, proxy=proxy, proxy_auth=proxy_auth, params=params)

    def fetch_webhook(
        self,
        webhook_id: int,
        token: str,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
    ) -> Response[WebhookPayload]:
        route = Route('GET', '/webhooks/{webhook_id}', webhook_id=webhook_id)
        return self.request(route, session=session, proxy=proxy, proxy_auth=proxy_auth, auth_token=token)

    def fetch_webhook_with_token(
        self,
        webhook_id: int,
        token: str,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
    ) -> Response[WebhookPayload]:
        route = Route('GET', '/webhooks/{webhook_id}/{webhook_token}', webhook_id=webhook_id, webhook_token=token)
        return self.request(route, session=session, proxy=proxy, proxy_auth=proxy_auth)

    def create_interaction_response(
        self,
        interaction_id: int,
        token: str,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        params: MultipartParameters,
        with_response: bool = MISSING,
    ) -> Response[Optional[InteractionCallbackResponsePayload]]:
        route = Route(
            'POST',
            '/interactions/{webhook_id}/{webhook_token}/callback',
            webhook_id=interaction_id,
            webhook_token=token,
        )

        if with_response is not MISSING:
            request_params = {'with_response': with_response}

        if params.files:
            return self.request(
                route,
                session=session,
                proxy=proxy,
                proxy_auth=proxy_auth,
                files=params.files,
                multipart=params.multipart,
                params=request_params,
            )
        else:
            return self.request(
                route,
                session=session,
                proxy=proxy,
                proxy_auth=proxy_auth,
                payload=params.payload,
                params=request_params,
            )

    def get_original_interaction_response(
        self,
        application_id: int,
        token: str,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
    ) -> Response[MessagePayload]:
        r = Route(
            'GET',
            '/webhooks/{webhook_id}/{webhook_token}/messages/@original',
            webhook_id=application_id,
            webhook_token=token,
        )
        return self.request(r, session=session, proxy=proxy, proxy_auth=proxy_auth)

    def edit_original_interaction_response(
        self,
        application_id: int,
        token: str,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
        payload: Optional[Dict[str, Any]] = None,
        multipart: Optional[List[Dict[str, Any]]] = None,
        files: Optional[Sequence[File]] = None,
    ) -> Response[MessagePayload]:
        r = Route(
            'PATCH',
            '/webhooks/{webhook_id}/{webhook_token}/messages/@original',
            webhook_id=application_id,
            webhook_token=token,
        )
        return self.request(
            r,
            session=session,
            proxy=proxy,
            proxy_auth=proxy_auth,
            payload=payload,
            multipart=multipart,
            files=files,
        )

    def delete_original_interaction_response(
        self,
        application_id: int,
        token: str,
        *,
        session: aiohttp.ClientSession,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
    ) -> Response[None]:
        r = Route(
            'DELETE',
            '/webhooks/{webhook_id}/{webhook_token}/messages/@original',
            webhook_id=application_id,
            webhook_token=token,
        )
        return self.request(r, session=session, proxy=proxy, proxy_auth=proxy_auth)


def interaction_response_params(type: int, data: Optional[Dict[str, Any]] = None) -> MultipartParameters:
    payload: Dict[str, Any] = {
        'type': type,
    }
    if data is not None:
        payload['data'] = data

    return MultipartParameters(payload=payload, multipart=None, files=None)


# This is a subset of handle_message_parameters
def interaction_message_response_params(
    *,
    type: int,
    content: Optional[str] = MISSING,
    tts: bool = False,
    flags: MessageFlags = MISSING,
    file: File = MISSING,
    files: Sequence[File] = MISSING,
    embed: Optional[Embed] = MISSING,
    embeds: Sequence[Embed] = MISSING,
    attachments: Sequence[Union[Attachment, File]] = MISSING,
    view: Optional[View] = MISSING,
    allowed_mentions: Optional[AllowedMentions] = MISSING,
    previous_allowed_mentions: Optional[AllowedMentions] = None,
    poll: Poll = MISSING,
) -> MultipartParameters:
    if files is not MISSING and file is not MISSING:
        raise TypeError('Cannot mix file and files keyword arguments.')
    if embeds is not MISSING and embed is not MISSING:
        raise TypeError('Cannot mix embed and embeds keyword arguments.')

    if file is not MISSING:
        files = [file]

    if attachments is not MISSING and files is not MISSING:
        raise TypeError('Cannot mix attachments and files keyword arguments.')

    data: Optional[Dict[str, Any]] = {
        'tts': tts,
    }

    if embeds is not MISSING:
        if len(embeds) > 10:
            raise ValueError('embeds has a maximum of 10 elements.')
        data['embeds'] = [e.to_dict() for e in embeds]

    if embed is not MISSING:
        if embed is None:
            data['embeds'] = []
        else:
            data['embeds'] = [embed.to_dict()]

    if content is not MISSING:
        if content is not None:
            data['content'] = str(content)
        else:
            data['content'] = None

    if view is not MISSING:
        if view is not None:
            data['components'] = view.to_components()
        else:
            data['components'] = []

    if flags is not MISSING:
        data['flags'] = flags.value

    if allowed_mentions:
        if previous_allowed_mentions is not None:
            data['allowed_mentions'] = previous_allowed_mentions.merge(allowed_mentions).to_dict()
        else:
            data['allowed_mentions'] = allowed_mentions.to_dict()
    elif previous_allowed_mentions is not None:
        data['allowed_mentions'] = previous_allowed_mentions.to_dict()

    if attachments is MISSING:
        attachments = files
    else:
        files = [a for a in attachments if isinstance(a, File)]

    if attachments is not MISSING:
        file_index = 0
        attachments_payload = []
        for attachment in attachments:
            if isinstance(attachment, File):
                attachments_payload.append(attachment.to_dict(file_index))
                file_index += 1
            else:
                attachments_payload.append(attachment.to_dict())

        data['attachments'] = attachments_payload

    if poll is not MISSING:
        data['poll'] = poll._to_dict()

    multipart = []
    if files:
        data = {'type': type, 'data': data}
        multipart.append({'name': 'payload_json', 'value': utils._to_json(data)})
        data = None
        for index, file in enumerate(files):
            multipart.append(
                {
                    'name': f'files[{index}]',
                    'value': file.fp,
                    'filename': file.filename,
                    'content_type': 'application/octet-stream',
                }
            )
    else:
        data = {'type': type, 'data': data}

    return MultipartParameters(payload=data, multipart=multipart, files=files)


async_context: ContextVar[AsyncWebhookAdapter] = ContextVar('async_webhook_context', default=AsyncWebhookAdapter())


class PartialWebhookChannel(Hashable):
    """Represents a partial channel for webhooks.

    These are typically given for channel follower webhooks.

    .. versionadded:: 2.0

    Attributes
    -----------
    id: :class:`int`
        The partial channel's ID.
    name: :class:`str`
        The partial channel's name.
    """

    __slots__ = ('id', 'name')

    def __init__(self, *, data: PartialChannelPayload) -> None:
        self.id: int = int(data['id'])
        self.name: str = data['name']

    def __repr__(self) -> str:
        return f'<PartialWebhookChannel name={self.name!r} id={self.id}>'


class PartialWebhookGuild(Hashable):
    """Represents a partial guild for webhooks.

    These are typically given for channel follower webhooks.

    .. versionadded:: 2.0

    Attributes
    -----------
    id: :class:`int`
        The partial guild's ID.
    name: :class:`str`
        The partial guild's name.
    """

    __slots__ = ('id', 'name', '_icon', '_state')

    def __init__(self, *, data: SourceGuildPayload, state: _State) -> None:
        self._state: _State = state
        self.id: int = int(data['id'])
        self.name: str = data['name']
        self._icon: str = data['icon']

    def __repr__(self) -> str:
        return f'<PartialWebhookGuild name={self.name!r} id={self.id}>'

    @property
    def icon(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns the guild's icon asset, if available."""
        if self._icon is None:
            return None
        return Asset._from_guild_icon(self._state, self.id, self._icon)


class _FriendlyHttpAttributeErrorHelper:
    __slots__ = ()

    def __getattr__(self, attr: str) -> Any:
        raise AttributeError('PartialWebhookState does not support http methods.')


class _WebhookState:
    __slots__ = ('_parent', '_webhook', '_thread')

    def __init__(self, webhook: Any, parent: Optional[_State], thread: Snowflake = MISSING):
        self._webhook: Any = webhook

        self._parent: Optional[ConnectionState]
        if isinstance(parent, _WebhookState):
            self._parent = None
        else:
            self._parent = parent

        self._thread: Snowflake = thread

    def _get_guild(self, guild_id: Optional[int]) -> Optional[Guild]:
        if self._parent is not None:
            return self._parent._get_guild(guild_id)
        return None

    def store_user(self, data: Union[UserPayload, PartialUserPayload], *, cache: bool = True) -> BaseUser:
        if self._parent is not None:
            return self._parent.store_user(data, cache=cache)
        # state parameter is artificial
        return BaseUser(state=self, data=data)  # type: ignore

    def create_user(self, data: Union[UserPayload, PartialUserPayload]) -> BaseUser:
        # state parameter is artificial
        return BaseUser(state=self, data=data)  # type: ignore

    @property
    def allowed_mentions(self) -> Optional[AllowedMentions]:
        return None

    def get_reaction_emoji(self, data: PartialEmojiPayload) -> Union[PartialEmoji, Emoji, str]:
        if self._parent is not None:
            return self._parent.get_reaction_emoji(data)

        emoji_id = utils._get_as_snowflake(data, 'id')

        if not emoji_id:
            # the name key will be a str
            return data['name']  # type: ignore

        return PartialEmoji(animated=data.get('animated', False), id=emoji_id, name=data['name'])  # type: ignore

    @property
    def http(self) -> Union[HTTPClient, _FriendlyHttpAttributeErrorHelper]:
        if self._parent is not None:
            return self._parent.http

        # Some data classes assign state.http and that should be kosher
        # however, using it should result in a late-binding error.
        return _FriendlyHttpAttributeErrorHelper()

    def __getattr__(self, attr: str) -> Any:
        if self._parent is not None:
            return getattr(self._parent, attr)

        raise AttributeError(f'PartialWebhookState does not support {attr!r}.')


class WebhookMessage(Message):
    """Represents a message sent from your webhook.

    This allows you to edit or delete a message sent by your
    webhook.

    This inherits from :class:`discord.Message` with changes to
    :meth:`edit` and :meth:`delete` to work.

    .. versionadded:: 1.6
    """

    _state: _WebhookState

    async def edit(
        self,
        *,
        content: Optional[str] = MISSING,
        embeds: Sequence[Embed] = MISSING,
        embed: Optional[Embed] = MISSING,
        attachments: Sequence[Union[Attachment, File]] = MISSING,
        view: Optional[View] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
    ) -> WebhookMessage:
        """|coro|

        Edits the message.

        .. versionadded:: 1.6

        .. versionchanged:: 2.0
            The edit is no longer in-place, instead the newly edited message is returned.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

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

            .. versionadded:: 2.0
        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
            See :meth:`.abc.Messageable.send` for more information.
        view: Optional[:class:`~discord.ui.View`]
            The updated view to update this message with. If ``None`` is passed then
            the view is removed.

            .. versionadded:: 2.0

        Raises
        -------
        HTTPException
            Editing the message failed.
        Forbidden
            Edited a message that is not yours.
        TypeError
            You specified both ``embed`` and ``embeds``
        ValueError
            The length of ``embeds`` was invalid or
            there was no token associated with this webhook.

        Returns
        --------
        :class:`WebhookMessage`
            The newly edited message.
        """
        return await self._state._webhook.edit_message(
            self.id,
            content=content,
            embeds=embeds,
            embed=embed,
            attachments=attachments,
            view=view,
            allowed_mentions=allowed_mentions,
            thread=self._state._thread,
        )

    async def add_files(self, *files: File) -> WebhookMessage:
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
        --------
        :class:`WebhookMessage`
            The newly edited message.
        """
        return await self.edit(attachments=[*self.attachments, *files])

    async def remove_attachments(self, *attachments: Attachment) -> WebhookMessage:
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
        --------
        :class:`WebhookMessage`
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
                    await self._state._webhook.delete_message(self.id, thread=self._state._thread)
                except HTTPException:
                    pass

            asyncio.create_task(inner_call())
        else:
            await self._state._webhook.delete_message(self.id, thread=self._state._thread)


class BaseWebhook(Hashable):
    __slots__: Tuple[str, ...] = (
        'id',
        'type',
        'guild_id',
        'channel_id',
        'token',
        'auth_token',
        'user',
        'name',
        '_avatar',
        'source_channel',
        'source_guild',
        '_state',
    )

    def __init__(
        self,
        data: WebhookPayload,
        token: Optional[str] = None,
        state: Optional[_State] = None,
    ) -> None:
        self.auth_token: Optional[str] = token
        self._state: _State = state or _WebhookState(self, parent=state)
        self._update(data)

    def _update(self, data: WebhookPayload) -> None:
        self.id: int = int(data['id'])
        self.type: WebhookType = try_enum(WebhookType, int(data['type']))
        self.channel_id: Optional[int] = utils._get_as_snowflake(data, 'channel_id')
        self.guild_id: Optional[int] = utils._get_as_snowflake(data, 'guild_id')
        self.name: Optional[str] = data.get('name')
        self._avatar: Optional[str] = data.get('avatar')
        self.token: Optional[str] = data.get('token')

        user = data.get('user')
        self.user: Optional[Union[BaseUser, User]] = None
        if user is not None:
            # state parameter may be _WebhookState
            self.user = User(state=self._state, data=user)  # type: ignore

        source_channel = data.get('source_channel')
        if source_channel:
            source_channel = PartialWebhookChannel(data=source_channel)

        self.source_channel: Optional[PartialWebhookChannel] = source_channel

        source_guild = data.get('source_guild')
        if source_guild:
            source_guild = PartialWebhookGuild(data=source_guild, state=self._state)

        self.source_guild: Optional[PartialWebhookGuild] = source_guild

    def is_partial(self) -> bool:
        """:class:`bool`: Whether the webhook is a "partial" webhook.

        .. versionadded:: 2.0"""
        return self.channel_id is None

    def is_authenticated(self) -> bool:
        """:class:`bool`: Whether the webhook is authenticated with a bot token.

        .. versionadded:: 2.0
        """
        return self.auth_token is not None

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: The guild this webhook belongs to.

        If this is a partial webhook, then this will always return ``None``.
        """
        return self._state and self._state._get_guild(self.guild_id)

    @property
    def channel(self) -> Optional[Union[ForumChannel, VoiceChannel, TextChannel]]:
        """Optional[Union[:class:`ForumChannel`, :class:`VoiceChannel`, :class:`TextChannel`]]: The channel this webhook belongs to.

        If this is a partial webhook, then this will always return ``None``.
        """
        guild = self.guild
        return guild and guild.get_channel(self.channel_id)  # type: ignore

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the webhook's creation time in UTC."""
        return utils.snowflake_time(self.id)

    @property
    def avatar(self) -> Optional[Asset]:
        """Optional[:class:`Asset`]: Returns an :class:`Asset` for the avatar the webhook has.

        If the webhook does not have a traditional avatar, ``None`` is returned.
        If you want the avatar that a webhook has displayed, consider :attr:`display_avatar`.
        """
        if self._avatar is not None:
            return Asset._from_avatar(self._state, self.id, self._avatar)
        return None

    @property
    def default_avatar(self) -> Asset:
        """
        :class:`Asset`: Returns the default avatar.

        .. versionadded:: 2.0
        """
        return Asset._from_default_avatar(self._state, (self.id >> 22) % len(DefaultAvatar))

    @property
    def display_avatar(self) -> Asset:
        """:class:`Asset`: Returns the webhook's display avatar.

        This is either webhook's default avatar or uploaded avatar.

        .. versionadded:: 2.0
        """
        return self.avatar or self.default_avatar


class Webhook(BaseWebhook):
    """Represents an asynchronous Discord webhook.

    Webhooks are a form to send messages to channels in Discord without a
    bot user or authentication.

    There are two main ways to use Webhooks. The first is through the ones
    received by the library such as :meth:`.Guild.webhooks`,
    :meth:`.TextChannel.webhooks`, :meth:`.VoiceChannel.webhooks`
    and :meth:`.ForumChannel.webhooks`.
    The ones received by the library will automatically be
    bound using the library's internal HTTP session.

    The second form involves creating a webhook object manually using the
    :meth:`~.Webhook.from_url` or :meth:`~.Webhook.partial` classmethods.

    For example, creating a webhook from a URL and using :doc:`aiohttp <aio:index>`:

    .. code-block:: python3

        from discord import Webhook
        import aiohttp

        async def foo():
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url('url-here', session=session)
                await webhook.send('Hello World', username='Foo')

    For a synchronous counterpart, see :class:`SyncWebhook`.

    .. container:: operations

        .. describe:: x == y

            Checks if two webhooks are equal.

        .. describe:: x != y

            Checks if two webhooks are not equal.

        .. describe:: hash(x)

            Returns the webhooks's hash.

    .. versionchanged:: 1.4
        Webhooks are now comparable and hashable.

    Attributes
    ------------
    id: :class:`int`
        The webhook's ID
    type: :class:`WebhookType`
        The type of the webhook.

        .. versionadded:: 1.3

    token: Optional[:class:`str`]
        The authentication token of the webhook. If this is ``None``
        then the webhook cannot be used to make requests.
    guild_id: Optional[:class:`int`]
        The guild ID this webhook is for.
    channel_id: Optional[:class:`int`]
        The channel ID this webhook is for.
    user: Optional[:class:`abc.User`]
        The user this webhook was created by. If the webhook was
        received without authentication then this will be ``None``.
    name: Optional[:class:`str`]
        The default name of the webhook.
    source_guild: Optional[:class:`PartialWebhookGuild`]
        The guild of the channel that this webhook is following.
        Only given if :attr:`type` is :attr:`WebhookType.channel_follower`.

        .. versionadded:: 2.0

    source_channel: Optional[:class:`PartialWebhookChannel`]
        The channel that this webhook is following.
        Only given if :attr:`type` is :attr:`WebhookType.channel_follower`.

        .. versionadded:: 2.0
    """

    __slots__: Tuple[str, ...] = ('session', 'proxy', 'proxy_auth')

    def __init__(
        self,
        data: WebhookPayload,
        session: aiohttp.ClientSession,
        token: Optional[str] = None,
        state: Optional[_State] = None,
        proxy: Optional[str] = None,
        proxy_auth: Optional[aiohttp.BasicAuth] = None,
    ) -> None:
        super().__init__(data, token, state)
        self.session: aiohttp.ClientSession = session
        self.proxy: Optional[str] = proxy
        self.proxy_auth: Optional[aiohttp.BasicAuth] = proxy_auth

    def __repr__(self) -> str:
        return f'<Webhook id={self.id!r} type={self.type!r} name={self.name!r}>'

    @property
    def url(self) -> str:
        """:class:`str` : Returns the webhook's url."""
        return f'https://discord.com/api/webhooks/{self.id}/{self.token}'

    @classmethod
    def partial(
        cls,
        id: int,
        token: str,
        *,
        session: aiohttp.ClientSession = MISSING,
        client: Client = MISSING,
        bot_token: Optional[str] = None,
    ) -> Self:
        """Creates a partial :class:`Webhook`.

        Parameters
        -----------
        id: :class:`int`
            The ID of the webhook.
        token: :class:`str`
            The authentication token of the webhook.
        session: :class:`aiohttp.ClientSession`
            The session to use to send requests with. Note
            that the library does not manage the session and
            will not close it.

            .. versionadded:: 2.0
        client: :class:`Client`
            The client to initialise this webhook with. This allows it to
            attach the client's internal state. If ``session`` is not given
            while this is given then the client's internal session will be used.

            .. versionadded:: 2.2
        bot_token: Optional[:class:`str`]
            The bot authentication token for authenticated requests
            involving the webhook.

            .. versionadded:: 2.0

        Raises
        -------
        TypeError
            Neither ``session`` nor ``client`` were given.

        Returns
        --------
        :class:`Webhook`
            A partial :class:`Webhook`.
            A partial webhook is just a webhook object with an ID and a token.
        """
        data: WebhookPayload = {
            'id': id,
            'type': 1,
            'token': token,
        }

        state = None
        if client is not MISSING:
            state = client._connection
            if session is MISSING:
                session = client.http._HTTPClient__session  # type: ignore

        if session is MISSING:
            raise TypeError('session or client must be given')

        return cls(data, session, token=bot_token, state=state)

    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        session: aiohttp.ClientSession = MISSING,
        client: Client = MISSING,
        bot_token: Optional[str] = None,
    ) -> Self:
        """Creates a partial :class:`Webhook` from a webhook URL.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ------------
        url: :class:`str`
            The URL of the webhook.
        session: :class:`aiohttp.ClientSession`
            The session to use to send requests with. Note
            that the library does not manage the session and
            will not close it.

            .. versionadded:: 2.0
        client: :class:`Client`
            The client to initialise this webhook with. This allows it to
            attach the client's internal state. If ``session`` is not given
            while this is given then the client's internal session will be used.

            .. versionadded:: 2.2
        bot_token: Optional[:class:`str`]
            The bot authentication token for authenticated requests
            involving the webhook.

            .. versionadded:: 2.0

        Raises
        -------
        ValueError
            The URL is invalid.
        TypeError
            Neither ``session`` nor ``client`` were given.

        Returns
        --------
        :class:`Webhook`
            A partial :class:`Webhook`.
            A partial webhook is just a webhook object with an ID and a token.
        """
        m = re.search(r'discord(?:app)?\.com/api/webhooks/(?P<id>[0-9]{17,20})/(?P<token>[A-Za-z0-9\.\-\_]{60,})', url)
        if m is None:
            raise ValueError('Invalid webhook URL given.')

        state = None
        if client is not MISSING:
            state = client._connection
            if session is MISSING:
                session = client.http._HTTPClient__session  # type: ignore

        if session is MISSING:
            raise TypeError('session or client must be given')

        data: Dict[str, Any] = m.groupdict()
        data['type'] = 1
        return cls(data, session, token=bot_token, state=state)  # type: ignore  # Casting dict[str, Any] to WebhookPayload

    @classmethod
    def _as_follower(cls, data, *, channel, user) -> Self:
        name = f"{channel.guild} #{channel}"
        feed: WebhookPayload = {
            'id': data['webhook_id'],
            'type': 2,
            'name': name,
            'channel_id': channel.id,
            'guild_id': channel.guild.id,
            'user': {
                'username': user.name,
                'discriminator': user.discriminator,
                'id': user.id,
                'avatar': user._avatar,
                'avatar_decoration_data': user._avatar_decoration_data,
                'global_name': user.global_name,
            },
        }

        state = channel._state
        http = state.http
        session = http._HTTPClient__session
        proxy_auth = http.proxy_auth
        proxy = http.proxy
        return cls(feed, session=session, state=state, proxy_auth=proxy_auth, proxy=proxy, token=state.http.token)

    @classmethod
    def from_state(cls, data: WebhookPayload, state: ConnectionState) -> Self:
        http = state.http
        session = http._HTTPClient__session  # type: ignore
        proxy_auth = http.proxy_auth
        proxy = http.proxy
        return cls(data, session=session, state=state, proxy_auth=proxy_auth, proxy=proxy, token=state.http.token)

    async def fetch(self, *, prefer_auth: bool = True) -> Webhook:
        """|coro|

        Fetches the current webhook.

        This could be used to get a full webhook from a partial webhook.

        .. versionadded:: 2.0

        .. note::

            When fetching with an unauthenticated webhook, i.e.
            :meth:`is_authenticated` returns ``False``, then the
            returned webhook does not contain any user information.

        Parameters
        -----------
        prefer_auth: :class:`bool`
            Whether to use the bot token over the webhook token
            if available. Defaults to ``True``.

        Raises
        -------
        HTTPException
            Could not fetch the webhook
        NotFound
            Could not find the webhook by this ID
        ValueError
            This webhook does not have a token associated with it.

        Returns
        --------
        :class:`Webhook`
            The fetched webhook.
        """
        adapter = async_context.get()

        if prefer_auth and self.auth_token:
            data = await adapter.fetch_webhook(
                self.id,
                self.auth_token,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
            )
        elif self.token:
            data = await adapter.fetch_webhook_with_token(
                self.id,
                self.token,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
            )
        else:
            raise ValueError('This webhook does not have a token associated with it')

        return Webhook(
            data,
            session=self.session,
            proxy=self.proxy,
            proxy_auth=self.proxy_auth,
            token=self.auth_token,
            state=self._state,
        )

    async def delete(self, *, reason: Optional[str] = None, prefer_auth: bool = True) -> None:
        """|coro|

        Deletes this Webhook.

        Parameters
        ------------
        reason: Optional[:class:`str`]
            The reason for deleting this webhook. Shows up on the audit log.

            .. versionadded:: 1.4
        prefer_auth: :class:`bool`
            Whether to use the bot token over the webhook token
            if available. Defaults to ``True``.

            .. versionadded:: 2.0

        Raises
        -------
        HTTPException
            Deleting the webhook failed.
        NotFound
            This webhook does not exist.
        Forbidden
            You do not have permissions to delete this webhook.
        ValueError
            This webhook does not have a token associated with it.
        """
        if self.token is None and self.auth_token is None:
            raise ValueError('This webhook does not have a token associated with it')

        adapter = async_context.get()

        if prefer_auth and self.auth_token:
            await adapter.delete_webhook(
                self.id,
                token=self.auth_token,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                reason=reason,
            )
        elif self.token:
            await adapter.delete_webhook_with_token(
                self.id,
                self.token,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                reason=reason,
            )

    async def edit(
        self,
        *,
        reason: Optional[str] = None,
        name: Optional[str] = MISSING,
        avatar: Optional[bytes] = MISSING,
        channel: Optional[Snowflake] = None,
        prefer_auth: bool = True,
    ) -> Webhook:
        """|coro|

        Edits this Webhook.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ------------
        name: Optional[:class:`str`]
            The webhook's new default name.
        avatar: Optional[:class:`bytes`]
            A :term:`py:bytes-like object` representing the webhook's new default avatar.
        channel: Optional[:class:`abc.Snowflake`]
            The webhook's new channel. This requires an authenticated webhook.

            .. versionadded:: 2.0
        reason: Optional[:class:`str`]
            The reason for editing this webhook. Shows up on the audit log.

            .. versionadded:: 1.4
        prefer_auth: :class:`bool`
            Whether to use the bot token over the webhook token
            if available. Defaults to ``True``.

            .. versionadded:: 2.0

        Raises
        -------
        HTTPException
            Editing the webhook failed.
        NotFound
            This webhook does not exist.
        ValueError
            This webhook does not have a token associated with it
            or it tried editing a channel without authentication.
        """
        if self.token is None and self.auth_token is None:
            raise ValueError('This webhook does not have a token associated with it')

        payload = {}
        if name is not MISSING:
            payload['name'] = str(name) if name is not None else None

        if avatar is not MISSING:
            payload['avatar'] = utils._bytes_to_base64_data(avatar) if avatar is not None else None

        adapter = async_context.get()

        data: Optional[WebhookPayload] = None
        # If a channel is given, always use the authenticated endpoint
        if channel is not None:
            if self.auth_token is None:
                raise ValueError('Editing channel requires authenticated webhook')

            payload['channel_id'] = channel.id
            data = await adapter.edit_webhook(
                self.id,
                self.auth_token,
                payload=payload,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                reason=reason,
            )
        elif prefer_auth and self.auth_token:
            data = await adapter.edit_webhook(
                self.id,
                self.auth_token,
                payload=payload,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                reason=reason,
            )
        elif self.token:
            data = await adapter.edit_webhook_with_token(
                self.id,
                self.token,
                payload=payload,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                reason=reason,
            )

        if data is None:
            raise RuntimeError('Unreachable code hit: data was not assigned')

        return Webhook(
            data,
            session=self.session,
            proxy=self.proxy,
            proxy_auth=self.proxy_auth,
            token=self.auth_token,
            state=self._state,
        )

    def _create_message(self, data, *, thread: Snowflake):
        state = _WebhookState(self, parent=self._state, thread=thread)
        # state may be artificial (unlikely at this point...)
        if thread is MISSING:
            channel_id = int(data['channel_id'])
            channel = self.channel
            # If this thread is created via thread_name then the channel_id would not be the same as the webhook's channel_id
            # which would be the forum channel.
            if self.channel_id != channel_id:
                type = ChannelType.public_thread if isinstance(channel, ForumChannel) else (channel and channel.type)
                channel = PartialMessageable(state=self._state, guild_id=self.guild_id, id=channel_id, type=type)  # type: ignore
            else:
                channel = self.channel or PartialMessageable(state=self._state, guild_id=self.guild_id, id=channel_id)  # type: ignore
        else:
            channel = self.channel
            if isinstance(channel, (ForumChannel, TextChannel)):
                channel = channel.get_thread(thread.id)

            if channel is None:
                channel = PartialMessageable(state=self._state, guild_id=self.guild_id, id=int(data['channel_id']))  # type: ignore

        # state is artificial
        return WebhookMessage(data=data, state=state, channel=channel)  # type: ignore

    @overload
    async def send(
        self,
        content: str = MISSING,
        *,
        username: str = MISSING,
        avatar_url: Any = MISSING,
        tts: bool = MISSING,
        ephemeral: bool = MISSING,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        view: View = MISSING,
        thread: Snowflake = MISSING,
        thread_name: str = MISSING,
        wait: Literal[True],
        suppress_embeds: bool = MISSING,
        silent: bool = MISSING,
        applied_tags: List[ForumTag] = MISSING,
        poll: Poll = MISSING,
    ) -> WebhookMessage:
        ...

    @overload
    async def send(
        self,
        content: str = MISSING,
        *,
        username: str = MISSING,
        avatar_url: Any = MISSING,
        tts: bool = MISSING,
        ephemeral: bool = MISSING,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        view: View = MISSING,
        thread: Snowflake = MISSING,
        thread_name: str = MISSING,
        wait: Literal[False] = ...,
        suppress_embeds: bool = MISSING,
        silent: bool = MISSING,
        applied_tags: List[ForumTag] = MISSING,
        poll: Poll = MISSING,
    ) -> None:
        ...

    async def send(
        self,
        content: str = MISSING,
        *,
        username: str = MISSING,
        avatar_url: Any = MISSING,
        tts: bool = False,
        ephemeral: bool = False,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        view: View = MISSING,
        thread: Snowflake = MISSING,
        thread_name: str = MISSING,
        wait: bool = False,
        suppress_embeds: bool = False,
        silent: bool = False,
        applied_tags: List[ForumTag] = MISSING,
        poll: Poll = MISSING,
    ) -> Optional[WebhookMessage]:
        """|coro|

        Sends a message using the webhook.

        The content must be a type that can convert to a string through ``str(content)``.

        To upload a single file, the ``file`` parameter should be used with a
        single :class:`File` object.

        If the ``embed`` parameter is provided, it must be of type :class:`Embed` and
        it must be a rich embed type. You cannot mix the ``embed`` parameter with the
        ``embeds`` parameter, which must be a :class:`list` of :class:`Embed` objects to send.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ------------
        content: :class:`str`
            The content of the message to send.
        wait: :class:`bool`
            Whether the server should wait before sending a response. This essentially
            means that the return type of this function changes from ``None`` to
            a :class:`WebhookMessage` if set to ``True``. If the type of webhook
            is :attr:`WebhookType.application` then this is always set to ``True``.
        username: :class:`str`
            The username to send with this message. If no username is provided
            then the default username for the webhook is used.
        avatar_url: :class:`str`
            The avatar URL to send with this message. If no avatar URL is provided
            then the default avatar for the webhook is used. If this is not a
            string then it is explicitly cast using ``str``.
        tts: :class:`bool`
            Indicates if the message should be sent using text-to-speech.
        ephemeral: :class:`bool`
            Indicates if the message should only be visible to the user.
            This is only available to :attr:`WebhookType.application` webhooks.
            If a view is sent with an ephemeral message and it has no timeout set
            then the timeout is set to 15 minutes.

            .. versionadded:: 2.0
        file: :class:`File`
            The file to upload. This cannot be mixed with ``files`` parameter.
        files: List[:class:`File`]
            A list of files to send with the content. This cannot be mixed with the
            ``file`` parameter.
        embed: :class:`Embed`
            The rich embed for the content to send. This cannot be mixed with
            ``embeds`` parameter.
        embeds: List[:class:`Embed`]
            A list of embeds to send with the content. Maximum of 10. This cannot
            be mixed with the ``embed`` parameter.
        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.

            .. versionadded:: 1.4
        view: :class:`discord.ui.View`
            The view to send with the message. You can only send a view
            if this webhook is not partial and has state attached. A
            webhook has state attached if the webhook is managed by the
            library.

            .. versionadded:: 2.0
        thread: :class:`~discord.abc.Snowflake`
            The thread to send this webhook to.

            .. versionadded:: 2.0
        thread_name: :class:`str`
            The thread name to create with this webhook if the webhook belongs
            to a :class:`~discord.ForumChannel`. Note that this is mutually
            exclusive with the ``thread`` parameter, as this will create a
            new thread with the given name.

            .. versionadded:: 2.0
        suppress_embeds: :class:`bool`
            Whether to suppress embeds for the message. This sends the message without any embeds if set to ``True``.

            .. versionadded:: 2.0
        silent: :class:`bool`
            Whether to suppress push and desktop notifications for the message. This will increment the mention counter
            in the UI, but will not actually send a notification.

            .. versionadded:: 2.2
        applied_tags: List[:class:`ForumTag`]
            Tags to apply to the thread if the webhook belongs to a :class:`~discord.ForumChannel`.

            .. versionadded:: 2.4

        poll: :class:`Poll`
            The poll to send with this message.

            .. warning::

                When sending a Poll via webhook, you cannot manually end it.

            .. versionadded:: 2.4

        Raises
        --------
        HTTPException
            Sending the message failed.
        NotFound
            This webhook was not found.
        Forbidden
            The authorization token for the webhook is incorrect.
        TypeError
            You specified both ``embed`` and ``embeds`` or ``file`` and ``files``
            or ``thread`` and ``thread_name``.
        ValueError
            The length of ``embeds`` was invalid, there was no token
            associated with this webhook or ``ephemeral`` was passed
            with the improper webhook type or there was no state
            attached with this webhook when giving it a view.

        Returns
        ---------
        Optional[:class:`WebhookMessage`]
            If ``wait`` is ``True`` then the message that was sent, otherwise ``None``.
        """

        if self.token is None:
            raise ValueError('This webhook does not have a token associated with it')

        previous_mentions: Optional[AllowedMentions] = getattr(self._state, 'allowed_mentions', None)
        if content is None:
            content = MISSING
        if ephemeral or suppress_embeds or silent:
            flags = MessageFlags._from_value(0)
            flags.ephemeral = ephemeral
            flags.suppress_embeds = suppress_embeds
            flags.suppress_notifications = silent
        else:
            flags = MISSING

        application_webhook = self.type is WebhookType.application
        if ephemeral and not application_webhook:
            raise ValueError('ephemeral messages can only be sent from application webhooks')

        if application_webhook:
            wait = True

        if view is not MISSING:
            if isinstance(self._state, _WebhookState):
                raise ValueError('Webhook views require an associated state with the webhook')

            if not hasattr(view, '__discord_ui_view__'):
                raise TypeError(f'expected view parameter to be of type View not {view.__class__.__name__}')

            if ephemeral is True and view.timeout is None:
                view.timeout = 15 * 60.0

        if thread_name is not MISSING and thread is not MISSING:
            raise TypeError('Cannot mix thread_name and thread keyword arguments.')

        if applied_tags is MISSING:
            applied_tag_ids = MISSING
        else:
            applied_tag_ids: SnowflakeList = [tag.id for tag in applied_tags]

        with handle_message_parameters(
            content=content,
            username=username,
            avatar_url=avatar_url,
            tts=tts,
            file=file,
            files=files,
            embed=embed,
            embeds=embeds,
            flags=flags,
            view=view,
            thread_name=thread_name,
            allowed_mentions=allowed_mentions,
            previous_allowed_mentions=previous_mentions,
            applied_tags=applied_tag_ids,
            poll=poll,
        ) as params:
            adapter = async_context.get()
            thread_id: Optional[int] = None
            if thread is not MISSING:
                thread_id = thread.id

            data = await adapter.execute_webhook(
                self.id,
                self.token,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                payload=params.payload,
                multipart=params.multipart,
                files=params.files,
                thread_id=thread_id,
                wait=wait,
            )

        msg = None
        if wait:
            msg = self._create_message(data, thread=thread)

        if view is not MISSING and not view.is_finished():
            message_id = None if msg is None else msg.id
            self._state.store_view(view, message_id)

        if poll is not MISSING and msg:
            poll._update(msg)

        return msg

    async def fetch_message(self, id: int, /, *, thread: Snowflake = MISSING) -> WebhookMessage:
        """|coro|

        Retrieves a single :class:`~discord.WebhookMessage` owned by this webhook.

        .. versionadded:: 2.0

        Parameters
        ------------
        id: :class:`int`
            The message ID to look for.
        thread: :class:`~discord.abc.Snowflake`
            The thread to look in.

        Raises
        --------
        ~discord.NotFound
            The specified message was not found.
        ~discord.Forbidden
            You do not have the permissions required to get a message.
        ~discord.HTTPException
            Retrieving the message failed.
        ValueError
            There was no token associated with this webhook.

        Returns
        --------
        :class:`~discord.WebhookMessage`
            The message asked for.
        """

        if self.token is None:
            raise ValueError('This webhook does not have a token associated with it')

        thread_id: Optional[int] = None
        if thread is not MISSING:
            thread_id = thread.id

        adapter = async_context.get()
        data = await adapter.get_webhook_message(
            self.id,
            self.token,
            id,
            session=self.session,
            proxy=self.proxy,
            proxy_auth=self.proxy_auth,
            thread_id=thread_id,
        )
        return self._create_message(data, thread=thread)

    async def edit_message(
        self,
        message_id: int,
        *,
        content: Optional[str] = MISSING,
        embeds: Sequence[Embed] = MISSING,
        embed: Optional[Embed] = MISSING,
        attachments: Sequence[Union[Attachment, File]] = MISSING,
        view: Optional[View] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
        thread: Snowflake = MISSING,
    ) -> WebhookMessage:
        """|coro|

        Edits a message owned by this webhook.

        This is a lower level interface to :meth:`WebhookMessage.edit` in case
        you only have an ID.

        .. versionadded:: 1.6

        .. versionchanged:: 2.0
            The edit is no longer in-place, instead the newly edited message is returned.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ------------
        message_id: :class:`int`
            The message ID to edit.
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

            .. versionadded:: 2.0
        allowed_mentions: :class:`AllowedMentions`
            Controls the mentions being processed in this message.
            See :meth:`.abc.Messageable.send` for more information.
        view: Optional[:class:`~discord.ui.View`]
            The updated view to update this message with. If ``None`` is passed then
            the view is removed. The webhook must have state attached, similar to
            :meth:`send`.

            .. versionadded:: 2.0
        thread: :class:`~discord.abc.Snowflake`
            The thread the webhook message belongs to.

            .. versionadded:: 2.0

        Raises
        -------
        HTTPException
            Editing the message failed.
        Forbidden
            Edited a message that is not yours.
        TypeError
            You specified both ``embed`` and ``embeds``
        ValueError
            The length of ``embeds`` was invalid,
            there was no token associated with this webhook or the webhook had
            no state.

        Returns
        --------
        :class:`WebhookMessage`
            The newly edited webhook message.
        """

        if self.token is None:
            raise ValueError('This webhook does not have a token associated with it')

        if view is not MISSING:
            if isinstance(self._state, _WebhookState):
                raise ValueError('This webhook does not have state associated with it')

            self._state.prevent_view_updates_for(message_id)

        previous_mentions: Optional[AllowedMentions] = getattr(self._state, 'allowed_mentions', None)
        with handle_message_parameters(
            content=content,
            attachments=attachments,
            embed=embed,
            embeds=embeds,
            view=view,
            allowed_mentions=allowed_mentions,
            previous_allowed_mentions=previous_mentions,
        ) as params:
            thread_id: Optional[int] = None
            if thread is not MISSING:
                thread_id = thread.id

            adapter = async_context.get()
            data = await adapter.edit_webhook_message(
                self.id,
                self.token,
                message_id,
                session=self.session,
                proxy=self.proxy,
                proxy_auth=self.proxy_auth,
                payload=params.payload,
                multipart=params.multipart,
                files=params.files,
                thread_id=thread_id,
            )

        message = self._create_message(data, thread=thread)
        if view and not view.is_finished():
            self._state.store_view(view, message_id)
        return message

    async def delete_message(self, message_id: int, /, *, thread: Snowflake = MISSING) -> None:
        """|coro|

        Deletes a message owned by this webhook.

        This is a lower level interface to :meth:`WebhookMessage.delete` in case
        you only have an ID.

        .. versionadded:: 1.6

        .. versionchanged:: 2.0

            ``message_id`` parameter is now positional-only.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ------------
        message_id: :class:`int`
            The message ID to delete.
        thread: :class:`~discord.abc.Snowflake`
            The thread the webhook message belongs to.

            .. versionadded:: 2.0

        Raises
        -------
        HTTPException
            Deleting the message failed.
        Forbidden
            Deleted a message that is not yours.
        ValueError
            This webhook does not have a token associated with it.
        """
        if self.token is None:
            raise ValueError('This webhook does not have a token associated with it')

        thread_id: Optional[int] = None
        if thread is not MISSING:
            thread_id = thread.id

        adapter = async_context.get()
        await adapter.delete_webhook_message(
            self.id,
            self.token,
            message_id,
            session=self.session,
            proxy=self.proxy,
            proxy_auth=self.proxy_auth,
            thread_id=thread_id,
        )
