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

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Union

from .enums import try_enum, MemberVerificationFieldType
from .utils import MISSING, parse_time

if TYPE_CHECKING:
    from typing_extensions import Self

    from .guild import Guild
    from .state import ConnectionState

    from .types.member_verification import (
        MemberVerificationField as MemberVerificationFieldPayload,
        MemberVerificationForm as MemberVerificationFormPayload,
    )

__all__ = (
    'MemberVerificationForm',
    'MemberVerificationField',
    'PartialMemberVerificationField',
)


class PartialMemberVerificationField:
    """Represents a partial member verification form field.

    Parameters
    ----------
    type: :class:`MemberVerificationFieldType`
        The type of field.
    label: :class:`str`
        The field label. Can be up to 300 characters.
    choices: List[:class:`str`]
        The choices the user has available. Can have up to 8 items, and each one
        can be up to 150 characters.

        Must be passed if ``type`` is :attr:`MemberVerificationFieldType.multiple_choice`.
    values: Optional[List[:class:`str`]]
        The rules that the user must agree to. Can have up to 16 items, and each one
        can be up to 300 characters.

        Must be passed if ``type`` is :attr:`MemberVerificationFieldType.terms`.
    required: :class:`bool`
        Whether this field is required.
    description: Optional[:class:`str`]
        The field description.
    automations: Optional[List[:class:`str`]]
        ...
    placeholder: Optional[:class:`str`]
        The field placeholder.
    """

    if TYPE_CHECKING:
        type: MemberVerificationFieldType
        label: str
        required: bool
        _choices: List[str]
        _values: Optional[List[str]]
        description: Optional[str]
        automations: Optional[List[str]]
        _placeholder: Optional[str]

    __slots__ = (
        'type',
        'label',
        'required',
        '_choices',
        '_values',
        'description',
        'automations',
        '_placeholder',
    )

    def __init__(
        self,
        *,
        type: MemberVerificationFieldType,
        label: str,
        required: bool,
        choices: List[str] = MISSING,
        values: Optional[List[str]] = MISSING,
        description: Optional[str] = None,
        automations: Optional[List[str]] = None,
        placeholder: Optional[str] = MISSING,
    ) -> None:
        self.type: MemberVerificationFieldType = type
        self.label: str = label
        self.required: bool = required
        self._choices: List[str] = choices
        self._values: Optional[List[str]] = values
        self.description: Optional[str] = description
        self.automations: Optional[List[str]] = automations
        self._placeholder: Optional[str] = placeholder

    @property
    def choices(self) -> List[str]:
        """List[:class:`str`]: The choices the user has available."""
        if self._choices is MISSING:
            return []
        return self._choices

    @choices.setter
    def choices(self, value: List[str]) -> None:
        self._choices = value

    @property
    def values(self) -> Optional[List[str]]:
        """Optional[List[:class:`str`]]: The rules the user must agree to, or ``None``."""
        if self._values is MISSING:
            return None
        return self._values

    @values.setter
    def values(self, value: Optional[List[str]]) -> None:
        self._values = value

    @property
    def placeholder(self) -> Optional[str]:
        """Optional[:class:`str`]: Returns the field placeholder, or ``None``."""
        if self._placeholder is MISSING:
            return None
        return self._placeholder

    @placeholder.setter
    def placeholder(self, value: Optional[str]) -> None:
        self._placeholder = value

    def to_dict(self) -> MemberVerificationFieldPayload:
        payload: MemberVerificationFieldPayload = {
            'field_type': self.type.value,
            'label': self.label,
            'required': self.required,
            'description': self.description,
            'automations': self.automations,
        }

        if self._choices is not MISSING:
            payload['choices'] = self._choices

        if self._values is not MISSING:
            payload['values'] = self._values

        if self._placeholder is not MISSING:
            payload['placeholder'] = self._placeholder
        return payload


class MemberVerificationField(PartialMemberVerificationField):
    """Represents a member verification form field.

    .. versionadded:: 2.5

    Attributes
    ----------
    type: :class:`MemberVerificationFieldType`
        The type of field.
    label: :class:`str`
        The field label. Can be up to 300 characters.
    response: Union[:class:`str`, :class:`int`, :class:`bool`]
        The user input on the field.

        If ``type`` is :attr:`MemberVerificationFieldType.terms` then this should
        be ``True``.

        If ``type`` is :attr:`MemberVerificationFieldType.multiple_choice` then this
        represents the index of the selected choice.
    required: :class:`bool`
        Whether this field is required for a successful application.
    description: Optional[:class:`str`]
        The field description.
    automations: List[:class:`str`]
        ...
    """

    __slots__ = (
        '_state',
        'response',
    )

    if TYPE_CHECKING:
        _state: ConnectionState
        response: Optional[Union[str, int, bool]]

    def __init__(self, *, data: MemberVerificationFieldPayload, state: ConnectionState) -> None:
        self._state: ConnectionState = state
        self._update(data)

    def _update(self, data: MemberVerificationFieldPayload) -> None:
        super().__init__(
            type=try_enum(MemberVerificationFieldType, data['field_type']),
            label=data['label'],
            choices=data.get('choices', MISSING),
            values=data.get('values', MISSING),
            required=data['required'],
            description=data['description'],
            automations=data['automations'],
            placeholder=data.get('placeholder', MISSING),
        )
        try:
            self.response: Optional[Union[str, int, bool]] = data['response']
        except KeyError:
            self.response = None


class MemberVerificationForm:
    """Represents a member verification form.

    Parameters
    ----------
    fields: Sequence[:class:`PartialMemberVerificationField`]
        The fields this form has. Can be up to 5 items.
    description: Optional[:class:`str`]
        A description of what the clan is about. Can be different
        from guild description. Can be up to 300 characters. Defaults
        to ``None``.
    """

    __slots__ = (
        '_guild',
        '_last_modified',
        'fields',
        'description',
    )

    def __init__(
        self,
        *,
        fields: List[PartialMemberVerificationField],
        description: Optional[str] = None,
    ) -> None:
        self.fields: List[PartialMemberVerificationField] = fields
        self.description: Optional[str] = description

        self._guild: Optional[Guild] = None
        self._last_modified: Optional[datetime] = None

    @classmethod
    def _from_data(cls, *, data: MemberVerificationFormPayload, state: ConnectionState, guild: Optional[Guild]) -> Self:
        self = cls(
            fields=[MemberVerificationField(data=f, state=state) for f in data['form_fields']],
            description=data.get('description'),
        )
        if guild:
            self._guild = guild
        else:
            # If guild is misteriously None then we use the guild preview
            # the data offers us.
            guild_data = data.get('guild')

            if guild_data is not None:
                from .guild import Guild  # circular import

                self._guild = Guild(data=guild_data, state=state)  # type: ignore

        self._last_modified = parse_time(data.get('version'))

        return self

    @property
    def guild(self) -> Optional[Guild]:
        """Optional[:class:`Guild`]: The guild this member verification is for."""
        return self._guild

    @property
    def last_modified_at(self) -> Optional[datetime]:
        """Optional[:class:`datetime.datetime`]: The timestamp at which the verification
        has been latest modified, or ``None``.
        """
        return self._last_modified

    def to_dict(self) -> MemberVerificationFieldPayload:
        return {
            'form_fields': [f.to_dict() for f in self.fields],  # type:ignore
            'description': self.description,
        }
