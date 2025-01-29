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

# If you're wondering why this is essentially copy pasted from the async_.py
# file, then it's due to needing two separate types to make the typing shenanigans
# a bit easier to write. It's an unfortunate design. Originally, these types were
# merged and an adapter was used to differentiate between the async and sync versions.
# However, this proved to be difficult to provide typings for, so here we are.

from __future__ import annotations

import threading
import logging
import json
import time
import re

from urllib.parse import quote as urlquote
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING, Sequence, Tuple, Union, TypeVar, Type, overload
import weakref

from .. import utils
from ..errors import HTTPException, Forbidden, NotFound, DiscordServerError
from ..message import Message, MessageFlags
from ..http import Route, handle_message_parameters
from ..channel import PartialMessageable, ForumTag

from .async_ import BaseWebhook, _WebhookState

__all__ = (
    'SyncWebhook',
    'SyncWebhookMessage',
)

_log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from typing_extensions import Self
    from types import TracebackType

    from ..file import File
    from ..embeds import Embed
    from ..poll import Poll
    from ..mentions import AllowedMentions
    from ..message import Attachment
    from ..abc import Snowflake
    from ..state import ConnectionState
    from ..ui import View
    from ..types.webhook import (
        Webhook as WebhookPayload,
    )
    from ..types.message import (
        Message as MessagePayload,
    )
    from ..types.snowflake import SnowflakeList

    BE = TypeVar('BE', bound=BaseException)

    try:
        from requests import Session, Response
    except ModuleNotFoundError:
        pass

MISSING: Any = utils.MISSING


class DeferredLock:
    def __init__(self, lock: threading.Lock) -> None:
        self.lock: threading.Lock = lock
        self.delta: Optional[float] = None

    def __enter__(self) -> Self:
        self.lock.acquire()
        return self

    def delay_by(self, delta: float) -> None:
        self.delta = delta

    def __exit__(
        self,
        exc_type: Optional[Type[BE]],
        exc: Optional[BE],
        traceback: Optional[TracebackType],
    ) -> None:
        if self.delta:
            time.sleep(self.delta)
        self.lock.release()


class WebhookAdapter:
    def __init__(self):
        self._locks: weakref.WeakValueDictionary[Any, threading.Lock] = weakref.WeakValueDictionary()

    def request(
        self,
        route: Route,
        session: Session,
        *,
        payload: Optional[Dict[str, Any]] = None,
        multipart: Optional[List[Dict[str, Any]]] = None,
        files: Optional[Sequence[File]] = None,
        reason: Optional[str] = None,
        auth_token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        headers: Dict[str, str] = {}
        files = files or []
        to_send: Optional[Union[str, bytes, Dict[str, Any]]] = None
        bucket = (route.webhook_id, route.webhook_token)

        try:
            lock = self._locks[bucket]
        except KeyError:
            self._locks[bucket] = lock = threading.Lock()

        if payload is not None:
            headers['Content-Type'] = 'application/json; charset=utf-8'
            to_send = utils._to_json(payload).encode('utf-8')

        if auth_token is not None:
            headers['Authorization'] = f'Bot {auth_token}'

        if reason is not None:
            headers['X-Audit-Log-Reason'] = urlquote(reason, safe='/ ')

        response: Optional[Response] = None
        data: Optional[Union[Dict[str, Any], str]] = None
        file_data: Optional[Dict[str, Any]] = None
        method = route.method
        url = route.url
        webhook_id = route.webhook_id

        with DeferredLock(lock) as lock:
            for attempt in range(5):
                for file in files:
                    file.reset(seek=attempt)

                if multipart:
                    file_data = {}
                    for p in multipart:
                        name = p['name']
                        if name == 'payload_json':
                            to_send = {'payload_json': p['value']}
                        else:
                            file_data[name] = (p['filename'], p['value'], p['content_type'])

                try:
                    with session.request(
                        method, url, data=to_send, files=file_data, headers=headers, params=params
                    ) as response:
                        _log.debug(
                            'Webhook ID %s with %s %s has returned status code %s',
                            webhook_id,
                            method,
                            url,
                            response.status_code,
                        )
                        response.encoding = 'utf-8'
                        # Compatibility with aiohttp
                        response.status = response.status_code  # type: ignore

                        data = response.text or None
                        try:
                            if data and response.headers['Content-Type'] == 'application/json':
                                data = json.loads(data)
                        except KeyError:
                            pass

                        remaining = response.headers.get('X-Ratelimit-Remaining')
                        if remaining == '0' and response.status_code != 429:
                            delta = utils._parse_ratelimit_header(response)
                            _log.debug(
                                'Webhook ID %s has exhausted its rate limit bucket (retry: %s).',
                                webhook_id,
                                delta,
                            )
                            lock.delay_by(delta)

                        if 300 > response.status_code >= 200:
                            return data

                        if response.status_code == 429:
                            if not response.headers.get('Via'):
                                raise HTTPException(response, data)
                            fmt = 'Webhook ID %s is rate limited. Retrying in %.2f seconds.'

                            retry_after: float = data['retry_after']  # type: ignore
                            _log.warning(fmt, webhook_id, retry_after)
                            time.sleep(retry_after)
                            continue

                        if response.status_code >= 500:
                            time.sleep(1 + attempt * 2)
                            continue

                        if response.status_code == 403:
                            raise Forbidden(response, data)
                        elif response.status_code == 404:
                            raise NotFound(response, data)
                        else:
                            raise HTTPException(response, data)

                except OSError as e:
                    if attempt < 4 and e.errno in (54, 10054):
                        time.sleep(1 + attempt * 2)
                        continue
                    raise

            if response:
                if response.status_code >= 500:
                    raise DiscordServerError(response, data)
                raise HTTPException(response, data)

            raise RuntimeError('Unreachable code in HTTP handling.')

    def delete_webhook(
        self,
        webhook_id: int,
        *,
        token: Optional[str] = None,
        session: Session,
        reason: Optional[str] = None,
    ) -> None:
        route = Route('DELETE', '/webhooks/{webhook_id}', webhook_id=webhook_id)
        return self.request(route, session, reason=reason, auth_token=token)

    def delete_webhook_with_token(
        self,
        webhook_id: int,
        token: str,
        *,
        session: Session,
        reason: Optional[str] = None,
    ) -> None:
        route = Route('DELETE', '/webhooks/{webhook_id}/{webhook_token}', webhook_id=webhook_id, webhook_token=token)
        return self.request(route, session, reason=reason)

    def edit_webhook(
        self,
        webhook_id: int,
        token: str,
        payload: Dict[str, Any],
        *,
        session: Session,
        reason: Optional[str] = None,
    ) -> WebhookPayload:
        route = Route('PATCH', '/webhooks/{webhook_id}', webhook_id=webhook_id)
        return self.request(route, session, reason=reason, payload=payload, auth_token=token)

    def edit_webhook_with_token(
        self,
        webhook_id: int,
        token: str,
        payload: Dict[str, Any],
        *,
        session: Session,
        reason: Optional[str] = None,
    ) -> WebhookPayload:
        route = Route('PATCH', '/webhooks/{webhook_id}/{webhook_token}', webhook_id=webhook_id, webhook_token=token)
        return self.request(route, session, reason=reason, payload=payload)

    def execute_webhook(
        self,
        webhook_id: int,
        token: str,
        *,
        session: Session,
        payload: Optional[Dict[str, Any]] = None,
        multipart: Optional[List[Dict[str, Any]]] = None,
        files: Optional[Sequence[File]] = None,
        thread_id: Optional[int] = None,
        wait: bool = False,
        has_view: bool = False,
    ) -> MessagePayload:
        params = {'wait': int(wait), 'with_components': int(has_view)}
        if thread_id:
            params['thread_id'] = thread_id
        route = Route('POST', '/webhooks/{webhook_id}/{webhook_token}', webhook_id=webhook_id, webhook_token=token)
        return self.request(route, session, payload=payload, multipart=multipart, files=files, params=params)

    def get_webhook_message(
        self,
        webhook_id: int,
        token: str,
        message_id: int,
        *,
        session: Session,
        thread_id: Optional[int] = None,
    ) -> MessagePayload:
        route = Route(
            'GET',
            '/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}',
            webhook_id=webhook_id,
            webhook_token=token,
            message_id=message_id,
        )
        params = None if thread_id is None else {'thread_id': thread_id}
        return self.request(route, session, params=params)

    def edit_webhook_message(
        self,
        webhook_id: int,
        token: str,
        message_id: int,
        *,
        session: Session,
        payload: Optional[Dict[str, Any]] = None,
        multipart: Optional[List[Dict[str, Any]]] = None,
        files: Optional[Sequence[File]] = None,
        thread_id: Optional[int] = None,
    ) -> MessagePayload:
        route = Route(
            'PATCH',
            '/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}',
            webhook_id=webhook_id,
            webhook_token=token,
            message_id=message_id,
        )
        params = None if thread_id is None else {'thread_id': thread_id}
        return self.request(route, session, payload=payload, multipart=multipart, files=files, params=params)

    def delete_webhook_message(
        self,
        webhook_id: int,
        token: str,
        message_id: int,
        *,
        session: Session,
        thread_id: Optional[int] = None,
    ) -> None:
        route = Route(
            'DELETE',
            '/webhooks/{webhook_id}/{webhook_token}/messages/{message_id}',
            webhook_id=webhook_id,
            webhook_token=token,
            message_id=message_id,
        )
        params = None if thread_id is None else {'thread_id': thread_id}
        return self.request(route, session, params=params)

    def fetch_webhook(
        self,
        webhook_id: int,
        token: str,
        *,
        session: Session,
    ) -> WebhookPayload:
        route = Route('GET', '/webhooks/{webhook_id}', webhook_id=webhook_id)
        return self.request(route, session=session, auth_token=token)

    def fetch_webhook_with_token(
        self,
        webhook_id: int,
        token: str,
        *,
        session: Session,
    ) -> WebhookPayload:
        route = Route('GET', '/webhooks/{webhook_id}/{webhook_token}', webhook_id=webhook_id, webhook_token=token)
        return self.request(route, session=session)


class _WebhookContext(threading.local):
    adapter: Optional[WebhookAdapter] = None


_context = _WebhookContext()


def _get_webhook_adapter() -> WebhookAdapter:
    if _context.adapter is None:
        _context.adapter = WebhookAdapter()
    return _context.adapter


class SyncWebhookMessage(Message):
    """Represents a message sent from your webhook.

    This allows you to edit or delete a message sent by your
    webhook.

    This inherits from :class:`discord.Message` with changes to
    :meth:`edit` and :meth:`delete` to work.

    .. versionadded:: 2.0
    """

    _state: _WebhookState

    def edit(
        self,
        *,
        content: Optional[str] = MISSING,
        embeds: Sequence[Embed] = MISSING,
        embed: Optional[Embed] = MISSING,
        attachments: Sequence[Union[Attachment, File]] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
    ) -> SyncWebhookMessage:
        """Edits the message.

        .. versionchanged:: 2.0
            This function will now raise :exc:`TypeError` or
            :exc:`ValueError` instead of ``InvalidArgument``.

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
        :class:`SyncWebhookMessage`
            The newly edited message.
        """
        return self._state._webhook.edit_message(
            self.id,
            content=content,
            embeds=embeds,
            embed=embed,
            attachments=attachments,
            allowed_mentions=allowed_mentions,
            thread=self._state._thread,
        )

    def add_files(self, *files: File) -> SyncWebhookMessage:
        r"""Adds new files to the end of the message attachments.

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
        :class:`SyncWebhookMessage`
            The newly edited message.
        """
        return self.edit(attachments=[*self.attachments, *files])

    def remove_attachments(self, *attachments: Attachment) -> SyncWebhookMessage:
        r"""Removes attachments from the message.

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
        :class:`SyncWebhookMessage`
            The newly edited message.
        """
        return self.edit(attachments=[a for a in self.attachments if a not in attachments])

    def delete(self, *, delay: Optional[float] = None) -> None:
        """Deletes the message.

        Parameters
        -----------
        delay: Optional[:class:`float`]
            If provided, the number of seconds to wait before deleting the message.
            This blocks the thread.

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
            time.sleep(delay)
        self._state._webhook.delete_message(self.id, thread=self._state._thread)


class SyncWebhook(BaseWebhook):
    """Represents a synchronous Discord webhook.

    For an asynchronous counterpart, see :class:`Webhook`.

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

    __slots__: Tuple[str, ...] = ('session',)

    def __init__(
        self,
        data: WebhookPayload,
        session: Session,
        token: Optional[str] = None,
        state: Optional[Union[ConnectionState, _WebhookState]] = None,
    ) -> None:
        super().__init__(data, token, state)
        self.session: Session = session

    def __repr__(self) -> str:
        return f'<Webhook id={self.id!r} type={self.type!r} name={self.name!r}>'

    @property
    def url(self) -> str:
        """:class:`str` : Returns the webhook's url."""
        return f'https://discord.com/api/webhooks/{self.id}/{self.token}'

    @classmethod
    def partial(cls, id: int, token: str, *, session: Session = MISSING, bot_token: Optional[str] = None) -> SyncWebhook:
        """Creates a partial :class:`Webhook`.

        Parameters
        -----------
        id: :class:`int`
            The ID of the webhook.
        token: :class:`str`
            The authentication token of the webhook.
        session: :class:`requests.Session`
            The session to use to send requests with. Note
            that the library does not manage the session and
            will not close it. If not given, the ``requests``
            auto session creation functions are used instead.
        bot_token: Optional[:class:`str`]
            The bot authentication token for authenticated requests
            involving the webhook.

        Returns
        --------
        :class:`SyncWebhook`
            A partial :class:`SyncWebhook`.
            A partial :class:`SyncWebhook` is just a :class:`SyncWebhook` object with an ID and a token.
        """
        data: WebhookPayload = {
            'id': id,
            'type': 1,
            'token': token,
        }
        import requests

        if session is not MISSING:
            if not isinstance(session, requests.Session):
                raise TypeError(f'expected requests.Session not {session.__class__.__name__}')
        else:
            session = requests  # type: ignore
        return cls(data, session, token=bot_token)

    @classmethod
    def from_url(cls, url: str, *, session: Session = MISSING, bot_token: Optional[str] = None) -> SyncWebhook:
        """Creates a partial :class:`Webhook` from a webhook URL.

        Parameters
        ------------
        url: :class:`str`
            The URL of the webhook.
        session: :class:`requests.Session`
            The session to use to send requests with. Note
            that the library does not manage the session and
            will not close it. If not given, the ``requests``
            auto session creation functions are used instead.
        bot_token: Optional[:class:`str`]
            The bot authentication token for authenticated requests
            involving the webhook.

        Raises
        -------
        ValueError
            The URL is invalid.

        Returns
        --------
        :class:`SyncWebhook`
            A partial :class:`SyncWebhook`.
            A partial :class:`SyncWebhook` is just a :class:`SyncWebhook` object with an ID and a token.
        """
        m = re.search(r'discord(?:app)?\.com/api/webhooks/(?P<id>[0-9]{17,20})/(?P<token>[A-Za-z0-9\.\-\_]{60,})', url)
        if m is None:
            raise ValueError('Invalid webhook URL given.')

        data: Dict[str, Any] = m.groupdict()
        data['type'] = 1
        import requests

        if session is not MISSING:
            if not isinstance(session, requests.Session):
                raise TypeError(f'expected requests.Session not {session.__class__.__name__}')
        else:
            session = requests  # type: ignore
        return cls(data, session, token=bot_token)  # type: ignore

    def fetch(self, *, prefer_auth: bool = True) -> SyncWebhook:
        """Fetches the current webhook.

        This could be used to get a full webhook from a partial webhook.

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
        :class:`SyncWebhook`
            The fetched webhook.
        """
        adapter: WebhookAdapter = _get_webhook_adapter()

        if prefer_auth and self.auth_token:
            data = adapter.fetch_webhook(self.id, self.auth_token, session=self.session)
        elif self.token:
            data = adapter.fetch_webhook_with_token(self.id, self.token, session=self.session)
        else:
            raise ValueError('This webhook does not have a token associated with it')

        return SyncWebhook(data, self.session, token=self.auth_token, state=self._state)

    def delete(self, *, reason: Optional[str] = None, prefer_auth: bool = True) -> None:
        """Deletes this Webhook.

        Parameters
        ------------
        reason: Optional[:class:`str`]
            The reason for deleting this webhook. Shows up on the audit log.

            .. versionadded:: 1.4
        prefer_auth: :class:`bool`
            Whether to use the bot token over the webhook token
            if available. Defaults to ``True``.

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

        adapter: WebhookAdapter = _get_webhook_adapter()

        if prefer_auth and self.auth_token:
            adapter.delete_webhook(self.id, token=self.auth_token, session=self.session, reason=reason)
        elif self.token:
            adapter.delete_webhook_with_token(self.id, self.token, session=self.session, reason=reason)

    def edit(
        self,
        *,
        reason: Optional[str] = None,
        name: Optional[str] = MISSING,
        avatar: Optional[bytes] = MISSING,
        channel: Optional[Snowflake] = None,
        prefer_auth: bool = True,
    ) -> SyncWebhook:
        """Edits this Webhook.

        Parameters
        ------------
        name: Optional[:class:`str`]
            The webhook's new default name.
        avatar: Optional[:class:`bytes`]
            A :term:`py:bytes-like object` representing the webhook's new default avatar.
        channel: Optional[:class:`abc.Snowflake`]
            The webhook's new channel. This requires an authenticated webhook.
        reason: Optional[:class:`str`]
            The reason for editing this webhook. Shows up on the audit log.

            .. versionadded:: 1.4
        prefer_auth: :class:`bool`
            Whether to use the bot token over the webhook token
            if available. Defaults to ``True``.

        Raises
        -------
        HTTPException
            Editing the webhook failed.
        NotFound
            This webhook does not exist.
        ValueError
            This webhook does not have a token associated with it
            or it tried editing a channel without authentication.

        Returns
        --------
        :class:`SyncWebhook`
            The newly edited webhook.
        """
        if self.token is None and self.auth_token is None:
            raise ValueError('This webhook does not have a token associated with it')

        payload = {}
        if name is not MISSING:
            payload['name'] = str(name) if name is not None else None

        if avatar is not MISSING:
            payload['avatar'] = utils._bytes_to_base64_data(avatar) if avatar is not None else None

        adapter: WebhookAdapter = _get_webhook_adapter()

        data: Optional[WebhookPayload] = None
        # If a channel is given, always use the authenticated endpoint
        if channel is not None:
            if self.auth_token is None:
                raise ValueError('Editing channel requires authenticated webhook')

            payload['channel_id'] = channel.id
            data = adapter.edit_webhook(self.id, self.auth_token, payload=payload, session=self.session, reason=reason)
        elif prefer_auth and self.auth_token:
            data = adapter.edit_webhook(self.id, self.auth_token, payload=payload, session=self.session, reason=reason)
        elif self.token:
            data = adapter.edit_webhook_with_token(self.id, self.token, payload=payload, session=self.session, reason=reason)

        if data is None:
            raise RuntimeError('Unreachable code hit: data was not assigned')

        return SyncWebhook(data=data, session=self.session, token=self.auth_token, state=self._state)

    def _create_message(self, data: MessagePayload, *, thread: Snowflake = MISSING) -> SyncWebhookMessage:
        state = _WebhookState(self, parent=self._state, thread=thread)
        # state may be artificial (unlikely at this point...)
        channel = self.channel or PartialMessageable(state=self._state, guild_id=self.guild_id, id=int(data['channel_id']))  # type: ignore
        # state is artificial
        return SyncWebhookMessage(data=data, state=state, channel=channel)  # type: ignore

    @overload
    def send(
        self,
        content: str = MISSING,
        *,
        username: str = MISSING,
        avatar_url: Any = MISSING,
        tts: bool = MISSING,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        thread: Snowflake = MISSING,
        thread_name: str = MISSING,
        wait: Literal[True],
        suppress_embeds: bool = MISSING,
        silent: bool = MISSING,
        applied_tags: List[ForumTag] = MISSING,
        poll: Poll = MISSING,
    ) -> SyncWebhookMessage:
        ...

    @overload
    def send(
        self,
        content: str = MISSING,
        *,
        username: str = MISSING,
        avatar_url: Any = MISSING,
        tts: bool = MISSING,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        thread: Snowflake = MISSING,
        thread_name: str = MISSING,
        wait: Literal[False] = ...,
        suppress_embeds: bool = MISSING,
        silent: bool = MISSING,
        applied_tags: List[ForumTag] = MISSING,
        poll: Poll = MISSING,
    ) -> None:
        ...

    def send(
        self,
        content: str = MISSING,
        *,
        username: str = MISSING,
        avatar_url: Any = MISSING,
        tts: bool = False,
        file: File = MISSING,
        files: Sequence[File] = MISSING,
        embed: Embed = MISSING,
        embeds: Sequence[Embed] = MISSING,
        allowed_mentions: AllowedMentions = MISSING,
        thread: Snowflake = MISSING,
        thread_name: str = MISSING,
        wait: bool = False,
        suppress_embeds: bool = False,
        silent: bool = False,
        applied_tags: List[ForumTag] = MISSING,
        poll: Poll = MISSING,
        view: View = MISSING,
    ) -> Optional[SyncWebhookMessage]:
        """Sends a message using the webhook.

        The content must be a type that can convert to a string through ``str(content)``.

        To upload a single file, the ``file`` parameter should be used with a
        single :class:`File` object.

        If the ``embed`` parameter is provided, it must be of type :class:`Embed` and
        it must be a rich embed type. You cannot mix the ``embed`` parameter with the
        ``embeds`` parameter, which must be a :class:`list` of :class:`Embed` objects to send.

        Parameters
        ------------
        content: :class:`str`
            The content of the message to send.
        wait: :class:`bool`
            Whether the server should wait before sending a response. This essentially
            means that the return type of this function changes from ``None`` to
            a :class:`WebhookMessage` if set to ``True``.
        username: :class:`str`
            The username to send with this message. If no username is provided
            then the default username for the webhook is used.
        avatar_url: :class:`str`
            The avatar URL to send with this message. If no avatar URL is provided
            then the default avatar for the webhook is used. If this is not a
            string then it is explicitly cast using ``str``.
        tts: :class:`bool`
            Indicates if the message should be sent using text-to-speech.
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
        thread: :class:`~discord.abc.Snowflake`
            The thread to send this message to.

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
        poll: :class:`Poll`
            The poll to send with this message.

            .. warning::

                When sending a Poll via webhook, you cannot manually end it.

            .. versionadded:: 2.4
        view: :class:`~discord.ui.View`
            The view to send with the message. This can only have URL buttons, which donnot
            require a state to be attached to it.

            If you want to send a view with any component attached to it, check :meth:`Webhook.send`.

            .. versionadded:: 2.5

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
            associated with this webhook or you tried to send a view
            with components other than URL buttons.

        Returns
        ---------
        Optional[:class:`SyncWebhookMessage`]
            If ``wait`` is ``True`` then the message that was sent, otherwise ``None``.
        """

        if self.token is None:
            raise ValueError('This webhook does not have a token associated with it')

        previous_mentions: Optional[AllowedMentions] = getattr(self._state, 'allowed_mentions', None)
        if content is None:
            content = MISSING

        if suppress_embeds or silent:
            flags = MessageFlags._from_value(0)
            flags.suppress_embeds = suppress_embeds
            flags.suppress_notifications = silent
        else:
            flags = MISSING

        if view is not MISSING:
            if not hasattr(view, '__discord_ui_view__'):
                raise TypeError(f'expected view parameter to be of type View not {view.__class__.__name__}')

            if not view._is_stateless():
                raise ValueError('SyncWebhook views can only contain URL buttons')

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
            thread_name=thread_name,
            allowed_mentions=allowed_mentions,
            previous_allowed_mentions=previous_mentions,
            flags=flags,
            applied_tags=applied_tag_ids,
            poll=poll,
            view=view,
        ) as params:
            adapter: WebhookAdapter = _get_webhook_adapter()
            thread_id: Optional[int] = None
            if thread is not MISSING:
                thread_id = thread.id

            data = adapter.execute_webhook(
                self.id,
                self.token,
                session=self.session,
                payload=params.payload,
                multipart=params.multipart,
                files=params.files,
                thread_id=thread_id,
                wait=wait,
                has_view=view is not MISSING,
            )

        msg = None

        if wait:
            msg = self._create_message(data, thread=thread)

        if poll is not MISSING and msg:
            poll._update(msg)

        return msg

    def fetch_message(self, id: int, /, *, thread: Snowflake = MISSING) -> SyncWebhookMessage:
        """Retrieves a single :class:`~discord.SyncWebhookMessage` owned by this webhook.

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
        :class:`~discord.SyncWebhookMessage`
            The message asked for.
        """

        if self.token is None:
            raise ValueError('This webhook does not have a token associated with it')

        thread_id: Optional[int] = None
        if thread is not MISSING:
            thread_id = thread.id

        adapter: WebhookAdapter = _get_webhook_adapter()
        data = adapter.get_webhook_message(
            self.id,
            self.token,
            id,
            session=self.session,
            thread_id=thread_id,
        )
        return self._create_message(data, thread=thread)

    def edit_message(
        self,
        message_id: int,
        *,
        content: Optional[str] = MISSING,
        embeds: Sequence[Embed] = MISSING,
        embed: Optional[Embed] = MISSING,
        attachments: Sequence[Union[Attachment, File]] = MISSING,
        allowed_mentions: Optional[AllowedMentions] = None,
        thread: Snowflake = MISSING,
    ) -> SyncWebhookMessage:
        """Edits a message owned by this webhook.

        This is a lower level interface to :meth:`WebhookMessage.edit` in case
        you only have an ID.

        .. versionadded:: 1.6

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
            The length of ``embeds`` was invalid or
            there was no token associated with this webhook.
        """

        if self.token is None:
            raise ValueError('This webhook does not have a token associated with it')

        previous_mentions: Optional[AllowedMentions] = getattr(self._state, 'allowed_mentions', None)
        with handle_message_parameters(
            content=content,
            attachments=attachments,
            embed=embed,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            previous_allowed_mentions=previous_mentions,
        ) as params:
            thread_id: Optional[int] = None
            if thread is not MISSING:
                thread_id = thread.id

            adapter: WebhookAdapter = _get_webhook_adapter()
            data = adapter.edit_webhook_message(
                self.id,
                self.token,
                message_id,
                session=self.session,
                payload=params.payload,
                multipart=params.multipart,
                files=params.files,
                thread_id=thread_id,
            )
            return self._create_message(data, thread=thread)

    def delete_message(self, message_id: int, /, *, thread: Snowflake = MISSING) -> None:
        """Deletes a message owned by this webhook.

        This is a lower level interface to :meth:`WebhookMessage.delete` in case
        you only have an ID.

        .. versionadded:: 1.6

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

        adapter: WebhookAdapter = _get_webhook_adapter()
        adapter.delete_webhook_message(
            self.id,
            self.token,
            message_id,
            session=self.session,
            thread_id=thread_id,
        )
