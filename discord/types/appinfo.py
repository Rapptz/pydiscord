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

from typing import Literal, Dict, TypedDict, List, Optional
from typing_extensions import NotRequired

from .user import User
from .team import Team
from .snowflake import Snowflake
from .emoji import Emoji


class InstallParams(TypedDict):
    scopes: List[str]
    permissions: str


class AppIntegrationTypeConfig(TypedDict):
    oauth2_install_params: NotRequired[InstallParams]


class BaseAppInfo(TypedDict):
    id: Snowflake
    name: str
    verify_key: str
    icon: Optional[str]
    summary: str
    description: str
    flags: int
    approximate_user_install_count: NotRequired[int]
    cover_image: NotRequired[str]
    terms_of_service_url: NotRequired[str]
    privacy_policy_url: NotRequired[str]
    rpc_origins: NotRequired[List[str]]
    interactions_endpoint_url: NotRequired[Optional[str]]
    redirect_uris: NotRequired[List[str]]
    role_connections_verification_url: NotRequired[Optional[str]]


class AppInfo(BaseAppInfo):
    owner: User
    bot_public: bool
    bot_require_code_grant: bool
    team: NotRequired[Team]
    guild_id: NotRequired[Snowflake]
    primary_sku_id: NotRequired[Snowflake]
    slug: NotRequired[str]
    hook: NotRequired[bool]
    max_participants: NotRequired[int]
    tags: NotRequired[List[str]]
    install_params: NotRequired[InstallParams]
    custom_install_url: NotRequired[str]
    integration_types_config: NotRequired[Dict[Literal["0", "1"], AppIntegrationTypeConfig]]


class PartialAppInfo(BaseAppInfo, total=False):
    hook: bool
    max_participants: int
    approximate_guild_count: int


class GatewayAppInfo(TypedDict):
    id: Snowflake
    flags: int


class ListAppEmojis(TypedDict):
    items: List[Emoji]
