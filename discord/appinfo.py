# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2015-2019 Rapptz

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

from .user import User
from .asset import Asset
from .team import Team


class AppInfo:
    """Represents the application info for the bot provided by Discord.


    Attributes
    -------------
    id: :class:`int`
        The application ID.
    name: :class:`str`
        The application name.
    owner: :class:`User`
        The application owner.
    team: Optional[:class:`Team`]
        The application's team.
    icon: Optional[:class:`str`]
        The icon hash, if it exists.
    description: Optional[:class:`str`]
        The application description.
    bot_public: :class:`bool`
        Whether the bot can be invited by anyone or if it is locked
        to the application owner.
    bot_require_code_grant: :class:`bool`
        Whether the bot requires the completion of the full oauth2 code
        grant flow to join.
    rpc_origins: Optional[List[:class:`str`]]
        A list of RPC origin URLs, if RPC is enabled.
    game_info: Optional[:class:GameInfo]
        If this application is a game sold on Discord,
        this field will be the information related to the game.
    """
    __slots__ = ('_state', 'description', 'id', 'name', 'rpc_origins',
                 'bot_public', 'bot_require_code_grant', 'owner', 'icon',
                 'game_info')

    def __init__(self, state, data):
        self._state = state

        self.id = int(data['id'])
        self.name = data['name']
        self.description = data['description']
        self.icon = data['icon']
        self.rpc_origins = data['rpc_origins']
        self.bot_public = data['bot_public']
        self.bot_require_code_grant = data['bot_require_code_grant']
        self.owner = User(state=self._state, data=data['owner'])

        team = data.get('team')
        self.team = Team(state, team) if team else None

        self.summary = data['summary']
        self.verify_key = data['verify_key']

        guild_id = data.get('guild_id')
        self.guild = self._state._get_guild(int(guild_id)) if guild_id else None

        primary_sku_id = data.get('primary_sku_id')
        self.primary_sku_id = int(primary_sku_id) if primary_sku_id else None
        self.slug = data.get('slug')
        self.cover_image = data.get('cover_image')

    def __repr__(self):
        return '<{0.__class__.__name__} id={0.id} name={0.name!r} description={0.description!r} public={0.bot_public} ' \
               'owner={0.owner!r}>'.format(self)

    @property
    def icon_url(self):
        """:class:`.Asset`: Retrieves the application's icon asset."""
        return Asset._from_icon(self._state, self, 'app')

    @property
    def cover_image_url(self):
        """:class:`.Asset`: Retrieves the cover image on a store embed."""
        return Asset._from_cover_image(self._state, self)


