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

from typing import TYPE_CHECKING, List, Literal, Optional, TypedDict

from .snowflake import Snowflake, SnowflakeList

if TYPE_CHECKING:
    from typing_extensions import NotRequired

ClanBadge = Literal[
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
]
ClanBanner = Literal[
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
]
ClanPlayStyle = Literal[
    0,
    1,
    2,
    3,
    4,
    5,
]


class PartialClan(TypedDict):
    tag: str
    badge: ClanBadge


# We override almost everything because some may be missing on
# full clan objects.
class Clan(PartialClan):
    id: Snowflake
    name: str
    icon_hash: Optional[str]
    member_count: int
    description: str
    play_style: NotRequired[ClanPlayStyle]
    search_terms: NotRequired[List[str]]
    game_application_ids: NotRequired[SnowflakeList]
    badge: NotRequired[ClanBadge]
    badge_hash: NotRequired[str]
    badge_color_primary: NotRequired[str]
    badge_color_secondary: NotRequired[str]
    banner: NotRequired[ClanBanner]
    banner_hash: NotRequired[str]
    brand_color_primary: NotRequired[str]
    brand_color_seconday: NotRequired[str]
    wildcard_descriptors: NotRequired[List[str]]


# This is not the same as a partial clan as
# the badge the PartialClan provides is one
# of the enum members, but here is the hash
# pretty weird though lol
class UserClan(TypedDict):
    tag: Optional[str]
    badge: Optional[str]
    identity_guild_id: Optional[Snowflake]
    identity_enabled: bool
