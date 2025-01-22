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

from typing import TYPE_CHECKING, Optional

from . import utils
from .mixins import Hashable
from .partial_emoji import PartialEmoji, _EmojiTag
from .user import User
from .utils import MISSING
from .asset import Asset, AssetMixin

if TYPE_CHECKING:
    import datetime
    from typing import Dict, Any

    from .types.soundboard import (
        BaseSoundboardSound as BaseSoundboardSoundPayload,
        SoundboardDefaultSound as SoundboardDefaultSoundPayload,
        SoundboardSound as SoundboardSoundPayload,
    )
    from .state import ConnectionState
    from .guild import Guild
    from .message import EmojiInputType

__all__ = ('BaseSoundboardSound', 'SoundboardDefaultSound', 'SoundboardSound')


class BaseSoundboardSound(Hashable, AssetMixin):
    """Represents a generic Discord soundboard sound.

    .. versionadded:: 2.5

    .. container:: operations

        .. describe:: x == y

            Checks if two sounds are equal.

        .. describe:: x != y

            Checks if two sounds are not equal.

        .. describe:: hash(x)

            Returns the sound's hash.

    Attributes
    ------------
    id: :class:`int`
        The ID of the sound.
    volume: :class:`float`
        The volume of the sound as floating point percentage (e.g. ``1.0`` for 100%).
    """

    __slots__ = ('_state', 'id', 'volume')

    def __init__(self, *, state: ConnectionState, data: BaseSoundboardSoundPayload):
        self._state: ConnectionState = state
        self.id: int = int(data['sound_id'])
        self._update(data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self.id == other.id
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def _update(self, data: BaseSoundboardSoundPayload):
        self.volume: float = data['volume']

    @property
    def url(self) -> str:
        """:class:`str`: Returns the URL of the sound."""
        return f'{Asset.BASE}/soundboard-sounds/{self.id}'


class SoundboardDefaultSound(BaseSoundboardSound):
    """Represents a Discord soundboard default sound.

    .. versionadded:: 2.5

    .. container:: operations

        .. describe:: x == y

            Checks if two sounds are equal.

        .. describe:: x != y

            Checks if two sounds are not equal.

        .. describe:: hash(x)

            Returns the sound's hash.

    Attributes
    ------------
    id: :class:`int`
        The ID of the sound.
    volume: :class:`float`
        The volume of the sound as floating point percentage (e.g. ``1.0`` for 100%).
    name: :class:`str`
        The name of the sound.
    emoji: :class:`PartialEmoji`
        The emoji of the sound.
    """

    __slots__ = ('name', 'emoji')

    def __init__(self, *, state: ConnectionState, data: SoundboardDefaultSoundPayload):
        self.name: str = data['name']
        self.emoji: PartialEmoji = PartialEmoji(name=data['emoji_name'])
        super().__init__(state=state, data=data)

    def __repr__(self) -> str:
        attrs = [
            ('id', self.id),
            ('name', self.name),
            ('volume', self.volume),
            ('emoji', self.emoji),
        ]
        inner = ' '.join('%s=%r' % t for t in attrs)
        return f"<{self.__class__.__name__} {inner}>"

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention this default sound."""
        return f'<sound:0:{self.id}>'


class SoundboardSound(BaseSoundboardSound):
    """Represents a Discord soundboard sound.

    .. versionadded:: 2.5

    .. container:: operations

        .. describe:: x == y

            Checks if two sounds are equal.

        .. describe:: x != y

            Checks if two sounds are not equal.

        .. describe:: hash(x)

            Returns the sound's hash.

    Attributes
    ------------
    id: :class:`int`
        The ID of the sound.
    volume: :class:`float`
        The volume of the sound as floating point percentage (e.g. ``1.0`` for 100%).
    name: :class:`str`
        The name of the sound.
    emoji: Optional[:class:`PartialEmoji`]
        The emoji of the sound. ``None`` if no emoji is set.
    guild: :class:`Guild`
        The guild in which the sound is uploaded.
    available: :class:`bool`
        Whether this sound is available for use.
    """

    __slots__ = ('_state', 'name', 'emoji', '_user', 'available', '_user_id', 'guild')

    def __init__(self, *, guild: Guild, state: ConnectionState, data: SoundboardSoundPayload):
        super().__init__(state=state, data=data)
        self.guild = guild
        self._user_id = utils._get_as_snowflake(data, 'user_id')
        self._user = data.get('user')

        self._update(data)

    def __repr__(self) -> str:
        attrs = [
            ('id', self.id),
            ('name', self.name),
            ('volume', self.volume),
            ('emoji', self.emoji),
            ('user', self.user),
        ]
        inner = ' '.join('%s=%r' % t for t in attrs)
        return f"<{self.__class__.__name__} {inner}>"

    def _update(self, data: SoundboardSoundPayload):
        super()._update(data)

        self.name: str = data['name']
        self.emoji: Optional[PartialEmoji] = None

        emoji_id = utils._get_as_snowflake(data, 'emoji_id')
        emoji_name = data['emoji_name']
        if emoji_id is not None or emoji_name is not None:
            self.emoji = PartialEmoji(id=emoji_id, name=emoji_name)  # type: ignore # emoji_name cannot be None here

        self.available: bool = data['available']

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the snowflake's creation time in UTC."""
        return utils.snowflake_time(self.id)

    @property
    def user(self) -> Optional[User]:
        """Optional[:class:`User`]: The user who uploaded the sound."""
        if self._user is None:
            if self._user_id is None:
                return None
            return self._state.get_user(self._user_id)
        return User(state=self._state, data=self._user)

    @property
    def mention(self) -> str:
        """:class:`str`: Returns a string that allows you to mention this sound."""
        return f'<sound:{self.guild.id}:{self.id}>'

    async def edit(
        self,
        *,
        name: str = MISSING,
        volume: Optional[float] = MISSING,
        emoji: Optional[EmojiInputType] = MISSING,
        reason: Optional[str] = None,
    ):
        """|coro|

        Edits the soundboard sound.

        You must have :attr:`~Permissions.manage_expressions` to edit the sound.
        If the sound was created by the client, you must have either :attr:`~Permissions.manage_expressions`
        or :attr:`~Permissions.create_expressions`.

        Parameters
        ----------
        name: :class:`str`
            The new name of the sound. Must be between 2 and 32 characters.
        volume: Optional[:class:`float`]
            The new volume of the sound. Must be between 0 and 1.
        emoji: Optional[Union[:class:`Emoji`, :class:`PartialEmoji`, :class:`str`]]
            The new emoji of the sound.
        reason: Optional[:class:`str`]
            The reason for editing this sound. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permissions to edit the soundboard sound.
        HTTPException
            Editing the soundboard sound failed.

        Returns
        -------
        :class:`SoundboardSound`
            The newly updated soundboard sound.
        """

        payload: Dict[str, Any] = {}

        if name is not MISSING:
            payload['name'] = name

        if volume is not MISSING:
            payload['volume'] = volume

        if emoji is not MISSING:
            if emoji is None:
                payload['emoji_id'] = None
                payload['emoji_name'] = None
            else:
                if isinstance(emoji, _EmojiTag):
                    partial_emoji = emoji._to_partial()
                elif isinstance(emoji, str):
                    partial_emoji = PartialEmoji.from_str(emoji)
                else:
                    partial_emoji = None

                if partial_emoji is not None:
                    if partial_emoji.id is None:
                        payload['emoji_name'] = partial_emoji.name
                    else:
                        payload['emoji_id'] = partial_emoji.id

        data = await self._state.http.edit_soundboard_sound(self.guild.id, self.id, reason=reason, **payload)
        return SoundboardSound(guild=self.guild, state=self._state, data=data)

    async def delete(self, *, reason: Optional[str] = None) -> None:
        """|coro|

        Deletes the soundboard sound.

        You must have :attr:`~Permissions.manage_expressions` to delete the sound.
        If the sound was created by the client, you must have either :attr:`~Permissions.manage_expressions`
        or :attr:`~Permissions.create_expressions`.

        Parameters
        -----------
        reason: Optional[:class:`str`]
            The reason for deleting this sound. Shows up on the audit log.

        Raises
        -------
        Forbidden
            You do not have permissions to delete the soundboard sound.
        HTTPException
            Deleting the soundboard sound failed.
        """
        await self._state.http.delete_soundboard_sound(self.guild.id, self.id, reason=reason)
