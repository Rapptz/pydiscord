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

import io
import os
from typing import Any, Literal, Optional, TYPE_CHECKING, Tuple, Union
from .errors import DiscordException
from . import utils
from .file import File

import yarl

# fmt: off
__all__ = (
    'Asset',
)
# fmt: on

if TYPE_CHECKING:
    from typing_extensions import Self

    from .state import ConnectionState
    from .webhook.async_ import _WebhookState

    _State = Union[ConnectionState, _WebhookState]

    ValidStaticFormatTypes = Literal['webp', 'jpeg', 'jpg', 'png']
    ValidAssetFormatTypes = Literal['webp', 'jpeg', 'jpg', 'png', 'gif']

VALID_STATIC_FORMATS = frozenset({"jpeg", "jpg", "webp", "png"})
VALID_ASSET_FORMATS = VALID_STATIC_FORMATS | {"gif"}


MISSING = utils.MISSING


class AssetMixin:
    __slots__ = ()
    url: str
    _state: Optional[Any]

    async def read(self) -> bytes:
        """|coro|

        Retrieves the content of this asset as a :class:`bytes` object.

        Raises
        ------
        DiscordException
            There was no internal connection state.
        HTTPException
            Downloading the asset failed.
        NotFound
            The asset was deleted.

        Returns
        -------
        :class:`bytes`
            The content of the asset.
        """
        if self._state is None:
            raise DiscordException('Invalid state (no ConnectionState provided)')

        return await self._state.http.get_from_cdn(self.url)

    async def save(self, fp: Union[str, bytes, os.PathLike[Any], io.BufferedIOBase], *, seek_begin: bool = True) -> int:
        """|coro|

        Saves this asset into a file-like object.

        Parameters
        ----------
        fp: Union[:class:`io.BufferedIOBase`, :class:`os.PathLike`]
            The file-like object to save this asset to or the filename
            to use. If a filename is passed then a file is created with that
            filename and used instead.
        seek_begin: :class:`bool`
            Whether to seek to the beginning of the file after saving is
            successfully done.

        Raises
        ------
        DiscordException
            There was no internal connection state.
        HTTPException
            Downloading the asset failed.
        NotFound
            The asset was deleted.

        Returns
        --------
        :class:`int`
            The number of bytes written.
        """

        data = await self.read()
        if isinstance(fp, io.BufferedIOBase):
            written = fp.write(data)
            if seek_begin:
                fp.seek(0)
            return written
        else:
            with open(fp, 'wb') as f:
                return f.write(data)

    async def to_file(
        self,
        *,
        filename: Optional[str] = MISSING,
        description: Optional[str] = None,
        spoiler: bool = False,
    ) -> File:
        """|coro|

        Converts the asset into a :class:`File` suitable for sending via
        :meth:`abc.Messageable.send`.

        .. versionadded:: 2.0

        Parameters
        -----------
        filename: Optional[:class:`str`]
            The filename of the file. If not provided, then the filename from
            the asset's URL is used.
        description: Optional[:class:`str`]
            The description for the file.
        spoiler: :class:`bool`
            Whether the file is a spoiler.

        Raises
        ------
        DiscordException
            The asset does not have an associated state.
        ValueError
            The asset is a unicode emoji.
        TypeError
            The asset is a sticker with lottie type.
        HTTPException
            Downloading the asset failed.
        NotFound
            The asset was deleted.

        Returns
        -------
        :class:`File`
            The asset as a file suitable for sending.
        """

        data = await self.read()
        file_filename = filename if filename is not MISSING else yarl.URL(self.url).name
        return File(io.BytesIO(data), filename=file_filename, description=description, spoiler=spoiler)


class Asset(AssetMixin):
    """Represents a CDN asset on Discord.

    .. container:: operations

        .. describe:: str(x)

            Returns the URL of the CDN asset.

        .. describe:: len(x)

            Returns the length of the CDN asset's URL.

        .. describe:: x == y

            Checks if the asset is equal to another asset.

        .. describe:: x != y

            Checks if the asset is not equal to another asset.

        .. describe:: hash(x)

            Returns the hash of the asset.
    """

    __slots__: Tuple[str, ...] = (
        '_state',
        '_url',
        '_animated',
        '_key',
    )

    BASE = 'https://cdn.discordapp.com'

    def __init__(self, state: _State, *, url: str, key: str, animated: bool = False) -> None:
        self._state: _State = state
        self._url: str = url
        self._animated: bool = animated
        self._key: str = key

    @classmethod
    def _from_default_avatar(cls, state: _State, index: int) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/embed/avatars/{index}.png',
            key=str(index),
            animated=False,
        )

    @classmethod
    def _from_avatar(cls, state: _State, user_id: int, avatar: str) -> Self:
        animated = avatar.startswith('a_')
        format = 'gif' if animated else 'png'
        return cls(
            state,
            url=f'{cls.BASE}/avatars/{user_id}/{avatar}.{format}?size=1024',
            key=avatar,
            animated=animated,
        )

    @classmethod
    def _from_guild_avatar(cls, state: _State, guild_id: int, member_id: int, avatar: str) -> Self:
        animated = avatar.startswith('a_')
        format = 'gif' if animated else 'png'
        return cls(
            state,
            url=f"{cls.BASE}/guilds/{guild_id}/users/{member_id}/avatars/{avatar}.{format}?size=1024",
            key=avatar,
            animated=animated,
        )

    @classmethod
    def _from_guild_banner(cls, state: _State, guild_id: int, member_id: int, banner: str) -> Self:
        animated = banner.startswith('a_')
        format = 'gif' if animated else 'png'
        return cls(
            state,
            url=f"{cls.BASE}/guilds/{guild_id}/users/{member_id}/banners/{banner}.{format}?size=1024",
            key=banner,
            animated=animated,
        )

    @classmethod
    def _from_avatar_decoration(cls, state: _State, avatar_decoration: str) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/avatar-decoration-presets/{avatar_decoration}.png?size=96',
            key=avatar_decoration,
            animated=True,
        )

    @classmethod
    def _from_icon(cls, state: _State, object_id: int, icon_hash: str, path: str) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/{path}-icons/{object_id}/{icon_hash}.png?size=1024',
            key=icon_hash,
            animated=False,
        )

    @classmethod
    def _from_app_icon(
        cls, state: _State, object_id: int, icon_hash: str, asset_type: Literal['icon', 'cover_image']
    ) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/app-icons/{object_id}/{asset_type}.png?size=1024',
            key=icon_hash,
            animated=False,
        )

    @classmethod
    def _from_cover_image(cls, state: _State, object_id: int, cover_image_hash: str) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/app-assets/{object_id}/store/{cover_image_hash}.png?size=1024',
            key=cover_image_hash,
            animated=False,
        )

    @classmethod
    def _from_scheduled_event_cover_image(cls, state: _State, scheduled_event_id: int, cover_image_hash: str) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/guild-events/{scheduled_event_id}/{cover_image_hash}.png?size=1024',
            key=cover_image_hash,
            animated=False,
        )

    @classmethod
    def _from_guild_image(cls, state: _State, guild_id: int, image: str, path: str) -> Self:
        animated = image.startswith('a_')
        format = 'gif' if animated else 'png'
        return cls(
            state,
            url=f'{cls.BASE}/{path}/{guild_id}/{image}.{format}?size=1024',
            key=image,
            animated=animated,
        )

    @classmethod
    def _from_guild_icon(cls, state: _State, guild_id: int, icon_hash: str) -> Self:
        animated = icon_hash.startswith('a_')
        format = 'gif' if animated else 'png'
        return cls(
            state,
            url=f'{cls.BASE}/icons/{guild_id}/{icon_hash}.{format}?size=1024',
            key=icon_hash,
            animated=animated,
        )

    @classmethod
    def _from_sticker_banner(cls, state: _State, banner: int) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/app-assets/710982414301790216/store/{banner}.png',
            key=str(banner),
            animated=False,
        )

    @classmethod
    def _from_user_banner(cls, state: _State, user_id: int, banner_hash: str) -> Self:
        animated = banner_hash.startswith('a_')
        format = 'gif' if animated else 'png'
        return cls(
            state,
            url=f'{cls.BASE}/banners/{user_id}/{banner_hash}.{format}?size=512',
            key=banner_hash,
            animated=animated,
        )

    @classmethod
    def _from_clan_badge(cls, state: _State, guild_id: int, badge_hash: str) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/clan-badges/{guild_id}/{badge_hash}.png',
            key=badge_hash,
            animated=False,
        )

    @classmethod
    def _from_clan_banner(cls, state: _State, guild_id: int, banner_hash: str) -> Self:
        return cls(
            state,
            url=f'{cls.BASE}/clan-banners/{guild_id}/{banner_hash}.png',
            key=banner_hash,
            animated=False,
        )

    def __str__(self) -> str:
        return self._url

    def __len__(self) -> int:
        return len(self._url)

    def __repr__(self) -> str:
        shorten = self._url.replace(self.BASE, '')
        return f'<Asset url={shorten!r}>'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Asset) and self._url == other._url

    def __hash__(self) -> int:
        return hash(self._url)

    @property
    def url(self) -> str:
        """:class:`str`: Returns the underlying URL of the asset."""
        return self._url

    @property
    def key(self) -> str:
        """:class:`str`: Returns the identifying key of the asset."""
        return self._key

    def is_animated(self) -> bool:
        """:class:`bool`: Returns whether the asset is animated."""
        return self._animated

    def replace(
        self,
        *,
        size: int = MISSING,
        format: ValidAssetFormatTypes = MISSING,
        static_format: ValidStaticFormatTypes = MISSING,
    ) -> Self:
        """Returns a new asset with the passed components replaced.


        .. versionchanged:: 2.0
            ``static_format`` is now preferred over ``format``
            if both are present and the asset is not animated.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        -----------
        size: :class:`int`
            The new size of the asset.
        format: :class:`str`
            The new format to change it to. Must be either
            'webp', 'jpeg', 'jpg', 'png', or 'gif' if it's animated.
        static_format: :class:`str`
            The new format to change it to if the asset isn't animated.
            Must be either 'webp', 'jpeg', 'jpg', or 'png'.

        Raises
        -------
        ValueError
            An invalid size or format was passed.

        Returns
        --------
        :class:`Asset`
            The newly updated asset.
        """
        url = yarl.URL(self._url)
        path, _ = os.path.splitext(url.path)

        if format is not MISSING:
            if self._animated:
                if format not in VALID_ASSET_FORMATS:
                    raise ValueError(f'format must be one of {VALID_ASSET_FORMATS}')
            else:
                if static_format is MISSING and format not in VALID_STATIC_FORMATS:
                    raise ValueError(f'format must be one of {VALID_STATIC_FORMATS}')
            url = url.with_path(f'{path}.{format}')

        if static_format is not MISSING and not self._animated:
            if static_format not in VALID_STATIC_FORMATS:
                raise ValueError(f'static_format must be one of {VALID_STATIC_FORMATS}')
            url = url.with_path(f'{path}.{static_format}')

        if size is not MISSING:
            if not utils.valid_icon_size(size):
                raise ValueError('size must be a power of 2 between 16 and 4096')
            url = url.with_query(size=size)
        else:
            url = url.with_query(url.raw_query_string)

        url = str(url)
        return self.__class__(state=self._state, url=url, key=self._key, animated=self._animated)

    def with_size(self, size: int, /) -> Self:
        """Returns a new asset with the specified size.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ------------
        size: :class:`int`
            The new size of the asset.

        Raises
        -------
        ValueError
            The asset had an invalid size.

        Returns
        --------
        :class:`Asset`
            The new updated asset.
        """
        if not utils.valid_icon_size(size):
            raise ValueError('size must be a power of 2 between 16 and 4096')

        url = str(yarl.URL(self._url).with_query(size=size))
        return self.__class__(state=self._state, url=url, key=self._key, animated=self._animated)

    def with_format(self, format: ValidAssetFormatTypes, /) -> Self:
        """Returns a new asset with the specified format.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ------------
        format: :class:`str`
            The new format of the asset.

        Raises
        -------
        ValueError
            The asset had an invalid format.

        Returns
        --------
        :class:`Asset`
            The new updated asset.
        """

        if self._animated:
            if format not in VALID_ASSET_FORMATS:
                raise ValueError(f'format must be one of {VALID_ASSET_FORMATS}')
        else:
            if format not in VALID_STATIC_FORMATS:
                raise ValueError(f'format must be one of {VALID_STATIC_FORMATS}')

        url = yarl.URL(self._url)
        path, _ = os.path.splitext(url.path)
        url = str(url.with_path(f'{path}.{format}').with_query(url.raw_query_string))
        return self.__class__(state=self._state, url=url, key=self._key, animated=self._animated)

    def with_static_format(self, format: ValidStaticFormatTypes, /) -> Self:
        """Returns a new asset with the specified static format.

        This only changes the format if the underlying asset is
        not animated. Otherwise, the asset is not changed.

        .. versionchanged:: 2.0
            This function will now raise :exc:`ValueError` instead of
            ``InvalidArgument``.

        Parameters
        ------------
        format: :class:`str`
            The new static format of the asset.

        Raises
        -------
        ValueError
            The asset had an invalid format.

        Returns
        --------
        :class:`Asset`
            The new updated asset.
        """

        if self._animated:
            return self
        return self.with_format(format)
