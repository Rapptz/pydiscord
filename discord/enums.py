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

import types
from collections import namedtuple
from typing import Any, ClassVar, Dict, List, Optional, TYPE_CHECKING, Tuple, Type, TypeVar, Iterator, Mapping

__all__ = (
    'Enum',
    'ChannelType',
    'MessageType',
    'SpeakingState',
    'VerificationLevel',
    'ContentFilter',
    'Status',
    'DefaultAvatar',
    'AuditLogAction',
    'AuditLogActionCategory',
    'UserFlags',
    'ActivityType',
    'NotificationLevel',
    'TeamMembershipState',
    'TeamMemberRole',
    'WebhookType',
    'ExpireBehaviour',
    'ExpireBehavior',
    'StickerType',
    'StickerFormatType',
    'InviteTarget',
    'VideoQualityMode',
    'ComponentType',
    'ButtonStyle',
    'TextStyle',
    'PrivacyLevel',
    'InteractionType',
    'InteractionResponseType',
    'NSFWLevel',
    'MFALevel',
    'Locale',
    'EntityType',
    'EventStatus',
    'AppCommandType',
    'AppCommandOptionType',
    'AppCommandPermissionType',
    'AutoModRuleTriggerType',
    'AutoModRuleEventType',
    'AutoModRuleActionType',
    'ForumLayoutType',
    'ForumOrderType',
    'SelectDefaultValueType',
    'SKUType',
    'EntitlementType',
    'EntitlementOwnerType',
    'PollLayoutType',
    'VoiceChannelEffectAnimationType',
    'SubscriptionStatus',
    'MessageReferenceType',
)


def _create_value_cls(name: str, comparable: bool):
    # All the type ignores here are due to the type checker being unable to recognise
    # Runtime type creation without exploding.
    cls = namedtuple('_EnumValue_' + name, 'name value')
    cls.__repr__ = lambda self: f'<{name}.{self.name}: {self.value!r}>'  # type: ignore
    cls.__str__ = lambda self: f'{name}.{self.name}'  # type: ignore
    if comparable:
        cls.__le__ = lambda self, other: isinstance(other, self.__class__) and self.value <= other.value  # type: ignore
        cls.__ge__ = lambda self, other: isinstance(other, self.__class__) and self.value >= other.value  # type: ignore
        cls.__lt__ = lambda self, other: isinstance(other, self.__class__) and self.value < other.value  # type: ignore
        cls.__gt__ = lambda self, other: isinstance(other, self.__class__) and self.value > other.value  # type: ignore
    return cls


def _is_descriptor(obj):
    return hasattr(obj, '__get__') or hasattr(obj, '__set__') or hasattr(obj, '__delete__')


class EnumMeta(type):
    if TYPE_CHECKING:
        __name__: ClassVar[str]
        _enum_member_names_: ClassVar[List[str]]
        _enum_member_map_: ClassVar[Dict[str, Any]]
        _enum_value_map_: ClassVar[Dict[Any, Any]]

    def __new__(
        cls,
        name: str,
        bases: Tuple[type, ...],
        attrs: Dict[str, Any],
        *,
        comparable: bool = False,
    ) -> EnumMeta:
        value_mapping = {}
        member_mapping = {}
        member_names = []

        value_cls = _create_value_cls(name, comparable)
        for key, value in list(attrs.items()):
            is_descriptor = _is_descriptor(value)
            if key[0] == '_' and not is_descriptor:
                continue

            # Special case classmethod to just pass through
            if isinstance(value, classmethod):
                continue

            if is_descriptor:
                setattr(value_cls, key, value)
                del attrs[key]
                continue

            try:
                new_value = value_mapping[value]
            except KeyError:
                new_value = value_cls(name=key, value=value)
                value_mapping[value] = new_value
                member_names.append(key)

            member_mapping[key] = new_value
            attrs[key] = new_value

        attrs['_enum_value_map_'] = value_mapping
        attrs['_enum_member_map_'] = member_mapping
        attrs['_enum_member_names_'] = member_names
        attrs['_enum_value_cls_'] = value_cls
        actual_cls = super().__new__(cls, name, bases, attrs)
        value_cls._actual_enum_cls_ = actual_cls  # type: ignore # Runtime attribute isn't understood
        return actual_cls

    def __iter__(cls) -> Iterator[Any]:
        return (cls._enum_member_map_[name] for name in cls._enum_member_names_)

    def __reversed__(cls) -> Iterator[Any]:
        return (cls._enum_member_map_[name] for name in reversed(cls._enum_member_names_))

    def __len__(cls) -> int:
        return len(cls._enum_member_names_)

    def __repr__(cls) -> str:
        return f'<enum {cls.__name__}>'

    @property
    def __members__(cls) -> Mapping[str, Any]:
        return types.MappingProxyType(cls._enum_member_map_)

    def __call__(cls, value: str) -> Any:
        try:
            return cls._enum_value_map_[value]
        except (KeyError, TypeError):
            raise ValueError(f"{value!r} is not a valid {cls.__name__}")

    def __getitem__(cls, key: str) -> Any:
        return cls._enum_member_map_[key]

    def __setattr__(cls, name: str, value: Any) -> None:
        raise TypeError('Enums are immutable.')

    def __delattr__(cls, attr: str) -> None:
        raise TypeError('Enums are immutable')

    def __instancecheck__(self, instance: Any) -> bool:
        # isinstance(x, Y)
        # -> __instancecheck__(Y, x)
        try:
            return instance._actual_enum_cls_ is self
        except AttributeError:
            return False


if TYPE_CHECKING:
    from enum import Enum
else:

    class Enum(metaclass=EnumMeta):
        @classmethod
        def try_value(cls, value):
            try:
                return cls._enum_value_map_[value]
            except (KeyError, TypeError):
                return value


class ChannelType(Enum):
    text = 0
    private = 1
    voice = 2
    group = 3
    category = 4
    news = 5
    news_thread = 10
    public_thread = 11
    private_thread = 12
    stage_voice = 13
    forum = 15
    media = 16

    def __str__(self) -> str:
        return self.name


class MessageReferenceType(Enum):
    default = 0
    reply = 0
    forward = 1


class MessageType(Enum):
    default = 0
    recipient_add = 1
    recipient_remove = 2
    call = 3
    channel_name_change = 4
    channel_icon_change = 5
    pins_add = 6
    new_member = 7
    premium_guild_subscription = 8
    premium_guild_tier_1 = 9
    premium_guild_tier_2 = 10
    premium_guild_tier_3 = 11
    channel_follow_add = 12
    guild_stream = 13
    guild_discovery_disqualified = 14
    guild_discovery_requalified = 15
    guild_discovery_grace_period_initial_warning = 16
    guild_discovery_grace_period_final_warning = 17
    thread_created = 18
    reply = 19
    chat_input_command = 20
    thread_starter_message = 21
    guild_invite_reminder = 22
    context_menu_command = 23
    auto_moderation_action = 24
    role_subscription_purchase = 25
    interaction_premium_upsell = 26
    stage_start = 27
    stage_end = 28
    stage_speaker = 29
    stage_raise_hand = 30
    stage_topic = 31
    guild_application_premium_subscription = 32
    guild_incident_alert_mode_enabled = 36
    guild_incident_alert_mode_disabled = 37
    guild_incident_report_raid = 38
    guild_incident_report_false_alarm = 39
    purchase_notification = 44
    poll_result = 46


class SpeakingState(Enum):
    none = 0
    voice = 1
    soundshare = 2
    priority = 4

    def __str__(self) -> str:
        return self.name

    def __int__(self) -> int:
        return self.value


class VerificationLevel(Enum, comparable=True):
    none = 0
    low = 1
    medium = 2
    high = 3
    highest = 4

    def __str__(self) -> str:
        return self.name


class ContentFilter(Enum, comparable=True):
    disabled = 0
    no_role = 1
    all_members = 2

    def __str__(self) -> str:
        return self.name


class Status(Enum):
    online = 'online'
    offline = 'offline'
    idle = 'idle'
    dnd = 'dnd'
    do_not_disturb = 'dnd'
    invisible = 'invisible'

    def __str__(self) -> str:
        return self.value


class DefaultAvatar(Enum):
    blurple = 0
    grey = 1
    gray = 1
    green = 2
    orange = 3
    red = 4
    pink = 5

    def __str__(self) -> str:
        return self.name


class NotificationLevel(Enum, comparable=True):
    all_messages = 0
    only_mentions = 1


class AuditLogActionCategory(Enum):
    create = 1
    delete = 2
    update = 3


class AuditLogAction(Enum):
    # fmt: off
    guild_update                                      = 1
    channel_create                                    = 10
    channel_update                                    = 11
    channel_delete                                    = 12
    overwrite_create                                  = 13
    overwrite_update                                  = 14
    overwrite_delete                                  = 15
    kick                                              = 20
    member_prune                                      = 21
    ban                                               = 22
    unban                                             = 23
    member_update                                     = 24
    member_role_update                                = 25
    member_move                                       = 26
    member_disconnect                                 = 27
    bot_add                                           = 28
    role_create                                       = 30
    role_update                                       = 31
    role_delete                                       = 32
    invite_create                                     = 40
    invite_update                                     = 41
    invite_delete                                     = 42
    webhook_create                                    = 50
    webhook_update                                    = 51
    webhook_delete                                    = 52
    emoji_create                                      = 60
    emoji_update                                      = 61
    emoji_delete                                      = 62
    message_delete                                    = 72
    message_bulk_delete                               = 73
    message_pin                                       = 74
    message_unpin                                     = 75
    integration_create                                = 80
    integration_update                                = 81
    integration_delete                                = 82
    stage_instance_create                             = 83
    stage_instance_update                             = 84
    stage_instance_delete                             = 85
    sticker_create                                    = 90
    sticker_update                                    = 91
    sticker_delete                                    = 92
    scheduled_event_create                            = 100
    scheduled_event_update                            = 101
    scheduled_event_delete                            = 102
    thread_create                                     = 110
    thread_update                                     = 111
    thread_delete                                     = 112
    app_command_permission_update                     = 121
    soundboard_sound_create                           = 130
    soundboard_sound_update                           = 131
    soundboard_sound_delete                           = 132
    automod_rule_create                               = 140
    automod_rule_update                               = 141
    automod_rule_delete                               = 142
    automod_block_message                             = 143
    automod_flag_message                              = 144
    automod_timeout_member                            = 145
    creator_monetization_request_created              = 150
    creator_monetization_terms_accepted               = 151
    voice_channel_status_update                       = 192
    voice_channel_status_delete                       = 193
    # fmt: on

    @property
    def category(self) -> Optional[AuditLogActionCategory]:
        # fmt: off
        lookup: Dict[AuditLogAction, Optional[AuditLogActionCategory]] = {
            AuditLogAction.guild_update:                             AuditLogActionCategory.update,
            AuditLogAction.channel_create:                           AuditLogActionCategory.create,
            AuditLogAction.channel_update:                           AuditLogActionCategory.update,
            AuditLogAction.channel_delete:                           AuditLogActionCategory.delete,
            AuditLogAction.overwrite_create:                         AuditLogActionCategory.create,
            AuditLogAction.overwrite_update:                         AuditLogActionCategory.update,
            AuditLogAction.overwrite_delete:                         AuditLogActionCategory.delete,
            AuditLogAction.kick:                                     None,
            AuditLogAction.member_prune:                             None,
            AuditLogAction.ban:                                      None,
            AuditLogAction.unban:                                    None,
            AuditLogAction.member_update:                            AuditLogActionCategory.update,
            AuditLogAction.member_role_update:                       AuditLogActionCategory.update,
            AuditLogAction.member_move:                              None,
            AuditLogAction.member_disconnect:                        None,
            AuditLogAction.bot_add:                                  None,
            AuditLogAction.role_create:                              AuditLogActionCategory.create,
            AuditLogAction.role_update:                              AuditLogActionCategory.update,
            AuditLogAction.role_delete:                              AuditLogActionCategory.delete,
            AuditLogAction.invite_create:                            AuditLogActionCategory.create,
            AuditLogAction.invite_update:                            AuditLogActionCategory.update,
            AuditLogAction.invite_delete:                            AuditLogActionCategory.delete,
            AuditLogAction.webhook_create:                           AuditLogActionCategory.create,
            AuditLogAction.webhook_update:                           AuditLogActionCategory.update,
            AuditLogAction.webhook_delete:                           AuditLogActionCategory.delete,
            AuditLogAction.emoji_create:                             AuditLogActionCategory.create,
            AuditLogAction.emoji_update:                             AuditLogActionCategory.update,
            AuditLogAction.emoji_delete:                             AuditLogActionCategory.delete,
            AuditLogAction.message_delete:                           AuditLogActionCategory.delete,
            AuditLogAction.message_bulk_delete:                      AuditLogActionCategory.delete,
            AuditLogAction.message_pin:                              None,
            AuditLogAction.message_unpin:                            None,
            AuditLogAction.integration_create:                       AuditLogActionCategory.create,
            AuditLogAction.integration_update:                       AuditLogActionCategory.update,
            AuditLogAction.integration_delete:                       AuditLogActionCategory.delete,
            AuditLogAction.stage_instance_create:                    AuditLogActionCategory.create,
            AuditLogAction.stage_instance_update:                    AuditLogActionCategory.update,
            AuditLogAction.stage_instance_delete:                    AuditLogActionCategory.delete,
            AuditLogAction.sticker_create:                           AuditLogActionCategory.create,
            AuditLogAction.sticker_update:                           AuditLogActionCategory.update,
            AuditLogAction.sticker_delete:                           AuditLogActionCategory.delete,
            AuditLogAction.scheduled_event_create:                   AuditLogActionCategory.create,
            AuditLogAction.scheduled_event_update:                   AuditLogActionCategory.update,
            AuditLogAction.scheduled_event_delete:                   AuditLogActionCategory.delete,
            AuditLogAction.thread_create:                            AuditLogActionCategory.create,
            AuditLogAction.thread_delete:                            AuditLogActionCategory.delete,
            AuditLogAction.thread_update:                            AuditLogActionCategory.update,
            AuditLogAction.app_command_permission_update:            AuditLogActionCategory.update,
            AuditLogAction.automod_rule_create:                      AuditLogActionCategory.create,
            AuditLogAction.automod_rule_update:                      AuditLogActionCategory.update,
            AuditLogAction.automod_rule_delete:                      AuditLogActionCategory.delete,
            AuditLogAction.automod_block_message:                    None,
            AuditLogAction.automod_flag_message:                     None,
            AuditLogAction.automod_timeout_member:                   None,
            AuditLogAction.creator_monetization_request_created:     None,
            AuditLogAction.creator_monetization_terms_accepted:      None,
            AuditLogAction.soundboard_sound_create:                  AuditLogActionCategory.create,
            AuditLogAction.soundboard_sound_update:                  AuditLogActionCategory.update,
            AuditLogAction.soundboard_sound_delete:                  AuditLogActionCategory.delete,
            AuditLogAction.voice_channel_status_update:              AuditLogActionCategory.update,
            AuditLogAction.voice_channel_status_delete:              AuditLogActionCategory.delete,
        }
        # fmt: on
        return lookup[self]

    @property
    def target_type(self) -> Optional[str]:
        v = self.value
        if v == -1:
            return 'all'
        elif v < 10:
            return 'guild'
        elif v < 20:
            return 'channel'
        elif v < 30:
            return 'user'
        elif v < 40:
            return 'role'
        elif v < 50:
            return 'invite'
        elif v < 60:
            return 'webhook'
        elif v < 70:
            return 'emoji'
        elif v == 73:
            return 'channel'
        elif v < 80:
            return 'message'
        elif v < 83:
            return 'integration'
        elif v < 90:
            return 'stage_instance'
        elif v < 93:
            return 'sticker'
        elif v < 103:
            return 'guild_scheduled_event'
        elif v < 113:
            return 'thread'
        elif v < 122:
            return 'integration_or_app_command'
        elif 139 < v < 143:
            return 'auto_moderation'
        elif v < 146:
            return 'user'
        elif v < 152:
            return 'creator_monetization'
        elif v < 194:
            return 'voice_channel_status'


class UserFlags(Enum):
    staff = 1
    partner = 2
    hypesquad = 4
    bug_hunter = 8
    mfa_sms = 16
    premium_promo_dismissed = 32
    hypesquad_bravery = 64
    hypesquad_brilliance = 128
    hypesquad_balance = 256
    early_supporter = 512
    team_user = 1024
    system = 4096
    has_unread_urgent_messages = 8192
    bug_hunter_level_2 = 16384
    verified_bot = 65536
    verified_bot_developer = 131072
    discord_certified_moderator = 262144
    bot_http_interactions = 524288
    spammer = 1048576
    active_developer = 4194304


class ActivityType(Enum):
    unknown = -1
    playing = 0
    streaming = 1
    listening = 2
    watching = 3
    custom = 4
    competing = 5

    def __int__(self) -> int:
        return self.value


class TeamMembershipState(Enum):
    invited = 1
    accepted = 2


class TeamMemberRole(Enum):
    admin = 'admin'
    developer = 'developer'
    read_only = 'read_only'


class WebhookType(Enum):
    incoming = 1
    channel_follower = 2
    application = 3


class ExpireBehaviour(Enum):
    remove_role = 0
    kick = 1


ExpireBehavior = ExpireBehaviour


class StickerType(Enum):
    standard = 1
    guild = 2


class StickerFormatType(Enum):
    png = 1
    apng = 2
    lottie = 3
    gif = 4

    @property
    def file_extension(self) -> str:
        # fmt: off
        lookup: Dict[StickerFormatType, str] = {
            StickerFormatType.png: 'png',
            StickerFormatType.apng: 'png',
            StickerFormatType.lottie: 'json',
            StickerFormatType.gif: 'gif',
        }
        # fmt: on
        return lookup.get(self, 'png')


class InviteTarget(Enum):
    unknown = 0
    stream = 1
    embedded_application = 2


class InteractionType(Enum):
    ping = 1
    application_command = 2
    component = 3
    autocomplete = 4
    modal_submit = 5


class InteractionResponseType(Enum):
    pong = 1
    # ack = 2 (deprecated)
    # channel_message = 3 (deprecated)
    channel_message = 4  # (with source)
    deferred_channel_message = 5  # (with source)
    deferred_message_update = 6  # for components
    message_update = 7  # for components
    autocomplete_result = 8
    modal = 9  # for modals
    # premium_required = 10 (deprecated)


class VideoQualityMode(Enum):
    auto = 1
    full = 2

    def __int__(self) -> int:
        return self.value


class ComponentType(Enum):
    action_row = 1
    button = 2
    select = 3
    string_select = 3
    text_input = 4
    user_select = 5
    role_select = 6
    mentionable_select = 7
    channel_select = 8

    def __int__(self) -> int:
        return self.value


class ButtonStyle(Enum):
    primary = 1
    secondary = 2
    success = 3
    danger = 4
    link = 5
    premium = 6

    # Aliases
    blurple = 1
    grey = 2
    gray = 2
    green = 3
    red = 4
    url = 5

    def __int__(self) -> int:
        return self.value


class TextStyle(Enum):
    short = 1
    paragraph = 2

    # Aliases
    long = 2

    def __int__(self) -> int:
        return self.value


class PrivacyLevel(Enum):
    guild_only = 2


class NSFWLevel(Enum, comparable=True):
    default = 0
    explicit = 1
    safe = 2
    age_restricted = 3


class MFALevel(Enum, comparable=True):
    disabled = 0
    require_2fa = 1


class Locale(Enum):
    american_english = 'en-US'
    british_english = 'en-GB'
    bulgarian = 'bg'
    chinese = 'zh-CN'
    taiwan_chinese = 'zh-TW'
    croatian = 'hr'
    czech = 'cs'
    indonesian = 'id'
    danish = 'da'
    dutch = 'nl'
    finnish = 'fi'
    french = 'fr'
    german = 'de'
    greek = 'el'
    hindi = 'hi'
    hungarian = 'hu'
    italian = 'it'
    japanese = 'ja'
    korean = 'ko'
    latin_american_spanish = 'es-419'
    lithuanian = 'lt'
    norwegian = 'no'
    polish = 'pl'
    brazil_portuguese = 'pt-BR'
    romanian = 'ro'
    russian = 'ru'
    spain_spanish = 'es-ES'
    swedish = 'sv-SE'
    thai = 'th'
    turkish = 'tr'
    ukrainian = 'uk'
    vietnamese = 'vi'

    def __str__(self) -> str:
        return self.value


E = TypeVar('E', bound='Enum')


class EntityType(Enum):
    stage_instance = 1
    voice = 2
    external = 3


class EventStatus(Enum):
    scheduled = 1
    active = 2
    completed = 3
    canceled = 4

    ended = 3
    cancelled = 4


class AppCommandOptionType(Enum):
    subcommand = 1
    subcommand_group = 2
    string = 3
    integer = 4
    boolean = 5
    user = 6
    channel = 7
    role = 8
    mentionable = 9
    number = 10
    attachment = 11


class AppCommandType(Enum):
    chat_input = 1
    user = 2
    message = 3


class AppCommandPermissionType(Enum):
    role = 1
    user = 2
    channel = 3


class AutoModRuleTriggerType(Enum):
    keyword = 1
    harmful_link = 2
    spam = 3
    keyword_preset = 4
    mention_spam = 5
    member_profile = 6


class AutoModRuleEventType(Enum):
    message_send = 1
    member_update = 2


class AutoModRuleActionType(Enum):
    block_message = 1
    send_alert_message = 2
    timeout = 3
    block_member_interactions = 4


class ForumLayoutType(Enum):
    not_set = 0
    list_view = 1
    gallery_view = 2


class ForumOrderType(Enum):
    latest_activity = 0
    creation_date = 1


class SelectDefaultValueType(Enum):
    user = 'user'
    role = 'role'
    channel = 'channel'


class SKUType(Enum):
    durable = 2
    consumable = 3
    subscription = 5
    subscription_group = 6


class EntitlementType(Enum):
    purchase = 1
    premium_subscription = 2
    developer_gift = 3
    test_mode_purchase = 4
    free_purchase = 5
    user_gift = 6
    premium_purchase = 7
    application_subscription = 8


class EntitlementOwnerType(Enum):
    guild = 1
    user = 2


class PollLayoutType(Enum):
    default = 1


class InviteType(Enum):
    guild = 0
    group_dm = 1
    friend = 2


class ReactionType(Enum):
    normal = 0
    burst = 1


class VoiceChannelEffectAnimationType(Enum):
    premium = 0
    basic = 1


class SubscriptionStatus(Enum):
    active = 0
    ending = 1
    inactive = 2


def create_unknown_value(cls: Type[E], val: Any) -> E:
    value_cls = cls._enum_value_cls_  # type: ignore # This is narrowed below
    name = f'unknown_{val}'
    return value_cls(name=name, value=val)


def try_enum(cls: Type[E], val: Any) -> E:
    """A function that tries to turn the value into enum ``cls``.

    If it fails it returns a proxy invalid value instead.
    """

    try:
        return cls._enum_value_map_[val]  # type: ignore # All errors are caught below
    except (KeyError, TypeError, AttributeError):
        return create_unknown_value(cls, val)
