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
from typing import Any, Callable, ClassVar, Coroutine, Dict, Iterator, List, Optional, Sequence, TYPE_CHECKING, Tuple, Type
from functools import partial
from itertools import groupby

import asyncio
import logging
import sys
import time
import os
from .item import Item, ItemCallbackType
from .dynamic import DynamicItem
from ..components import (
    Component,
    ActionRow as ActionRowComponent,
    _component_factory,
    Button as ButtonComponent,
    SelectMenu as SelectComponent,
)

# fmt: off
__all__ = (
    'View',
)
# fmt: on


if TYPE_CHECKING:
    from typing_extensions import Self
    import re

    from ..interactions import Interaction
    from ..message import Message
    from ..types.components import Component as ComponentPayload
    from ..types.interactions import ModalSubmitComponentInteractionData as ModalSubmitComponentInteractionDataPayload
    from ..state import ConnectionState
    from .modal import Modal


_log = logging.getLogger(__name__)


def _walk_all_components(components: List[Component]) -> Iterator[Component]:
    for item in components:
        if isinstance(item, ActionRowComponent):
            yield from item.children
        else:
            yield item


def _component_to_item(component: Component) -> Item:
    if isinstance(component, ButtonComponent):
        from .button import Button

        return Button.from_component(component)
    if isinstance(component, SelectComponent):
        from .select import BaseSelect

        return BaseSelect.from_component(component)

    return Item.from_component(component)


class _ViewWeights:
    # fmt: off
    __slots__ = (
        'weights',
    )
    # fmt: on

    def __init__(self, children: List[Item]):
        self.weights: List[int] = [0, 0, 0, 0, 0]

        key = lambda i: sys.maxsize if i.row is None else i.row
        children = sorted(children, key=key)
        for row, group in groupby(children, key=key):
            for item in group:
                self.add_item(item)

    def find_open_space(self, item: Item) -> int:
        for index, weight in enumerate(self.weights):
            if weight + item.width <= 5:
                return index

        raise ValueError('could not find open space for item')

    def add_item(self, item: Item) -> None:
        if item.row is not None:
            total = self.weights[item.row] + item.width
            if total > 5:
                raise ValueError(f'item would not fit at row {item.row} ({total} > 5 width)')
            self.weights[item.row] = total
            item._rendered_row = item.row
        else:
            index = self.find_open_space(item)
            self.weights[index] += item.width
            item._rendered_row = index

    def remove_item(self, item: Item) -> None:
        if item._rendered_row is not None:
            self.weights[item._rendered_row] -= item.width
            item._rendered_row = None

    def clear(self) -> None:
        self.weights = [0, 0, 0, 0, 0]


class _ViewCallback:
    __slots__ = ('view', 'callback', 'item')

    def __init__(self, callback: ItemCallbackType[Any, Any], view: View, item: Item[View]) -> None:
        self.callback: ItemCallbackType[Any, Any] = callback
        self.view: View = view
        self.item: Item[View] = item

    def __call__(self, interaction: Interaction) -> Coroutine[Any, Any, Any]:
        return self.callback(self.view, interaction, self.item)


class View:
    """Represents a UI view.

    This object must be inherited to create a UI within Discord.

    .. versionadded:: 2.0

    Parameters
    -----------
    timeout: Optional[:class:`float`]
        Timeout in seconds from last interaction with the UI before no longer accepting input.
        If ``None`` then there is no timeout.
    """

    __discord_ui_view__: ClassVar[bool] = True
    __discord_ui_modal__: ClassVar[bool] = False
    __view_children_items__: ClassVar[List[ItemCallbackType[Any, Any]]] = []

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()

        children: Dict[str, ItemCallbackType[Any, Any]] = {}
        for base in reversed(cls.__mro__):
            for name, member in base.__dict__.items():
                if hasattr(member, '__discord_ui_model_type__'):
                    children[name] = member

        if len(children) > 25:
            raise TypeError('View cannot have more than 25 children')

        cls.__view_children_items__ = list(children.values())

    def _init_children(self) -> List[Item[Self]]:
        children = []
        for func in self.__view_children_items__:
            item: Item = func.__discord_ui_model_type__(**func.__discord_ui_model_kwargs__)
            item.callback = _ViewCallback(func, self, item)
            item._view = self
            setattr(self, func.__name__, item)
            children.append(item)
        return children

    def __init__(self, *, timeout: Optional[float] = 180.0):
        self.__timeout = timeout
        self._children: List[Item[Self]] = self._init_children()
        self.__weights = _ViewWeights(self._children)
        self.id: str = os.urandom(16).hex()
        self._cache_key: Optional[int] = None
        self.__cancel_callback: Optional[Callable[[View], None]] = None
        self.__timeout_expiry: Optional[float] = None
        self.__timeout_task: Optional[asyncio.Task[None]] = None
        self.__stopped: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} timeout={self.timeout} children={len(self._children)}>'

    async def __timeout_task_impl(self) -> None:
        while True:
            # Guard just in case someone changes the value of the timeout at runtime
            if self.timeout is None:
                return

            if self.__timeout_expiry is None:
                return self._dispatch_timeout()

            # Check if we've elapsed our currently set timeout
            now = time.monotonic()
            if now >= self.__timeout_expiry:
                return self._dispatch_timeout()

            # Wait N seconds to see if timeout data has been refreshed
            await asyncio.sleep(self.__timeout_expiry - now)

    def _is_stateless(self) -> bool:
        # this is used by webhooks to check whether a view requires a state attached
        # or not, this simply is, whether a view has a component other than a url button
        from .button import Button

        return all(isinstance(ch, Button) and ch.url is not None for ch in self.children)

    def to_components(self) -> List[Dict[str, Any]]:
        def key(item: Item) -> int:
            return item._rendered_row or 0

        children = sorted(self._children, key=key)
        components: List[Dict[str, Any]] = []
        for _, group in groupby(children, key=key):
            children = [item.to_component_dict() for item in group]
            if not children:
                continue

            components.append(
                {
                    'type': 1,
                    'components': children,
                }
            )

        return components

    def _refresh_timeout(self) -> None:
        if self.__timeout:
            self.__timeout_expiry = time.monotonic() + self.__timeout

    @property
    def timeout(self) -> Optional[float]:
        """Optional[:class:`float`]: The timeout in seconds from last interaction with the UI before no longer accepting input.
        If ``None`` then there is no timeout.
        """
        return self.__timeout

    @timeout.setter
    def timeout(self, value: Optional[float]) -> None:
        # If the timeout task is already running this allows it to update
        # the expiry while it's running
        if self.__timeout_task is not None:
            if value is not None:
                self.__timeout_expiry = time.monotonic() + value
            else:
                self.__timeout_expiry = None

        self.__timeout = value

    @property
    def children(self) -> List[Item[Self]]:
        """List[:class:`Item`]: The list of children attached to this view."""
        return self._children.copy()

    @classmethod
    def from_message(cls, message: Message, /, *, timeout: Optional[float] = 180.0) -> View:
        """Converts a message's components into a :class:`View`.

        The :attr:`.Message.components` of a message are read-only
        and separate types from those in the ``discord.ui`` namespace.
        In order to modify and edit message components they must be
        converted into a :class:`View` first.

        Parameters
        -----------
        message: :class:`discord.Message`
            The message with components to convert into a view.
        timeout: Optional[:class:`float`]
            The timeout of the converted view.

        Returns
        --------
        :class:`View`
            The converted view. This always returns a :class:`View` and not
            one of its subclasses.
        """
        view = View(timeout=timeout)
        row = 0
        for component in message.components:
            if isinstance(component, ActionRowComponent):
                for child in component.children:
                    item = _component_to_item(child)
                    item.row = row
                    view.add_item(item)
                row += 1
            else:
                item = _component_to_item(component)
                item.row = row
                view.add_item(item)

        return view

    def add_item(self, item: Item[Any]) -> Self:
        """Adds an item to the view.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        -----------
        item: :class:`Item`
            The item to add to the view.

        Raises
        --------
        TypeError
            An :class:`Item` was not passed.
        ValueError
            Maximum number of children has been exceeded (25)
            or the row the item is trying to be added to is full.
        """

        if len(self._children) >= 25:
            raise ValueError('maximum number of children exceeded')

        if not isinstance(item, Item):
            raise TypeError(f'expected Item not {item.__class__.__name__}')

        self.__weights.add_item(item)

        item._view = self
        self._children.append(item)
        return self

    def remove_item(self, item: Item[Any]) -> Self:
        """Removes an item from the view.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        -----------
        item: :class:`Item`
            The item to remove from the view.
        """

        try:
            self._children.remove(item)
        except ValueError:
            pass
        else:
            self.__weights.remove_item(item)
        return self

    def clear_items(self) -> Self:
        """Removes all items from the view.

        This function returns the class instance to allow for fluent-style
        chaining.
        """
        self._children.clear()
        self.__weights.clear()
        return self

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        """|coro|

        A callback that is called when an interaction happens within the view
        that checks whether the view should process item callbacks for the interaction.

        This is useful to override if, for example, you want to ensure that the
        interaction author is a given user.

        The default implementation of this returns ``True``.

        .. note::

            If an exception occurs within the body then the check
            is considered a failure and :meth:`on_error` is called.

        Parameters
        -----------
        interaction: :class:`~discord.Interaction`
            The interaction that occurred.

        Returns
        ---------
        :class:`bool`
            Whether the view children's callbacks should be called.
        """
        return True

    async def on_timeout(self) -> None:
        """|coro|

        A callback that is called when a view's timeout elapses without being explicitly stopped.
        """
        pass

    async def on_error(self, interaction: Interaction, error: Exception, item: Item[Any], /) -> None:
        """|coro|

        A callback that is called when an item's callback or :meth:`interaction_check`
        fails with an error.

        The default implementation logs to the library logger.

        Parameters
        -----------
        interaction: :class:`~discord.Interaction`
            The interaction that led to the failure.
        error: :class:`Exception`
            The exception that was raised.
        item: :class:`Item`
            The item that failed the dispatch.
        """
        _log.error('Ignoring exception in view %r for item %r', self, item, exc_info=error)

    async def _scheduled_task(self, item: Item, interaction: Interaction):
        try:
            item._refresh_state(interaction, interaction.data)  # type: ignore

            allow = await item.interaction_check(interaction) and await self.interaction_check(interaction)
            if not allow:
                return

            if self.timeout:
                self.__timeout_expiry = time.monotonic() + self.timeout

            await item.callback(interaction)
        except Exception as e:
            return await self.on_error(interaction, e, item)

    def _start_listening_from_store(self, store: ViewStore) -> None:
        self.__cancel_callback = partial(store.remove_view)
        if self.timeout:
            if self.__timeout_task is not None:
                self.__timeout_task.cancel()

            self.__timeout_expiry = time.monotonic() + self.timeout
            self.__timeout_task = asyncio.create_task(self.__timeout_task_impl())

    def _dispatch_timeout(self):
        if self.__stopped.done():
            return

        if self.__cancel_callback:
            self.__cancel_callback(self)
            self.__cancel_callback = None

        self.__stopped.set_result(True)
        asyncio.create_task(self.on_timeout(), name=f'discord-ui-view-timeout-{self.id}')

    def _dispatch_item(self, item: Item, interaction: Interaction):
        if self.__stopped.done():
            return

        asyncio.create_task(self._scheduled_task(item, interaction), name=f'discord-ui-view-dispatch-{self.id}')

    def _refresh(self, components: List[Component]) -> None:
        # fmt: off
        old_state: Dict[str, Item[Any]] = {
            item.custom_id: item  # type: ignore
            for item in self._children
            if item.is_dispatchable()
        }
        # fmt: on

        for component in _walk_all_components(components):
            custom_id = getattr(component, 'custom_id', None)
            if custom_id is None:
                continue

            try:
                older = old_state[custom_id]
            except KeyError:
                _log.debug('View interaction referenced an unknown item custom_id %s. Discarding', custom_id)
                continue
            else:
                older._refresh_component(component)

    def stop(self) -> None:
        """Stops listening to interaction events from this view.

        This operation cannot be undone.
        """
        if not self.__stopped.done():
            self.__stopped.set_result(False)

        self.__timeout_expiry = None
        if self.__timeout_task is not None:
            self.__timeout_task.cancel()
            self.__timeout_task = None

        if self.__cancel_callback:
            self.__cancel_callback(self)
            self.__cancel_callback = None

    def is_finished(self) -> bool:
        """:class:`bool`: Whether the view has finished interacting."""
        return self.__stopped.done()

    def is_dispatching(self) -> bool:
        """:class:`bool`: Whether the view has been added for dispatching purposes."""
        return self.__cancel_callback is not None

    def is_persistent(self) -> bool:
        """:class:`bool`: Whether the view is set up as persistent.

        A persistent view has all their components with a set ``custom_id`` and
        a :attr:`timeout` set to ``None``.
        """
        return self.timeout is None and all(item.is_persistent() for item in self._children)

    async def wait(self) -> bool:
        """|coro|

        Waits until the view has finished interacting.

        A view is considered finished when :meth:`stop` is called
        or it times out.

        Returns
        --------
        :class:`bool`
            If ``True``, then the view timed out. If ``False`` then
            the view finished normally.
        """
        return await self.__stopped


class ViewStore:
    def __init__(self, state: ConnectionState):
        # entity_id: {(component_type, custom_id): Item}
        self._views: Dict[Optional[int], Dict[Tuple[int, str], Item[View]]] = {}
        # message_id: View
        self._synced_message_views: Dict[int, View] = {}
        # custom_id: Modal
        self._modals: Dict[str, Modal] = {}
        # component_type is the key
        self._dynamic_items: Dict[re.Pattern[str], Type[DynamicItem[Item[Any]]]] = {}
        self._state: ConnectionState = state

    @property
    def persistent_views(self) -> Sequence[View]:
        # fmt: off
        views = {
            item.view.id: item.view
            for items in self._views.values()
            for item in items.values()
            if item.view and item.view.is_persistent()
        }
        # fmt: on
        return list(views.values())

    def add_dynamic_items(self, *items: Type[DynamicItem[Item[Any]]]) -> None:
        for item in items:
            pattern = item.__discord_ui_compiled_template__
            self._dynamic_items[pattern] = item

    def remove_dynamic_items(self, *items: Type[DynamicItem[Item[Any]]]) -> None:
        for item in items:
            pattern = item.__discord_ui_compiled_template__
            self._dynamic_items.pop(pattern, None)

    def add_view(self, view: View, message_id: Optional[int] = None) -> None:
        view._start_listening_from_store(self)
        if view.__discord_ui_modal__:
            self._modals[view.custom_id] = view  # type: ignore
            return

        dispatch_info = self._views.setdefault(message_id, {})
        is_fully_dynamic = True
        for item in view._children:
            if isinstance(item, DynamicItem):
                pattern = item.__discord_ui_compiled_template__
                self._dynamic_items[pattern] = item.__class__
            elif item.is_dispatchable():
                dispatch_info[(item.type.value, item.custom_id)] = item  # type: ignore
                is_fully_dynamic = False

        view._cache_key = message_id
        if message_id is not None and not is_fully_dynamic:
            self._synced_message_views[message_id] = view

    def remove_view(self, view: View) -> None:
        if view.__discord_ui_modal__:
            self._modals.pop(view.custom_id, None)  # type: ignore
            return

        dispatch_info = self._views.get(view._cache_key)
        if dispatch_info:
            for item in view._children:
                if isinstance(item, DynamicItem):
                    pattern = item.__discord_ui_compiled_template__
                    self._dynamic_items.pop(pattern, None)
                elif item.is_dispatchable():
                    dispatch_info.pop((item.type.value, item.custom_id), None)  # type: ignore

            if len(dispatch_info) == 0:
                self._views.pop(view._cache_key, None)

        self._synced_message_views.pop(view._cache_key, None)  # type: ignore

    async def schedule_dynamic_item_call(
        self,
        component_type: int,
        factory: Type[DynamicItem[Item[Any]]],
        interaction: Interaction,
        custom_id: str,
        match: re.Match[str],
    ) -> None:
        if interaction.message is None:
            return

        view = View.from_message(interaction.message, timeout=None)

        try:
            base_item_index, base_item = next(
                (index, child)
                for index, child in enumerate(view._children)
                if child.type.value == component_type and getattr(child, 'custom_id', None) == custom_id
            )
        except StopIteration:
            return

        try:
            item = await factory.from_custom_id(interaction, base_item, match)
        except Exception:
            _log.exception('Ignoring exception in dynamic item creation for %r', factory)
            return

        # Swap the item in the view with our new dynamic item
        view._children[base_item_index] = item
        item._view = view
        item._rendered_row = base_item._rendered_row
        item._refresh_state(interaction, interaction.data)  # type: ignore

        try:
            allow = await item.interaction_check(interaction)
        except Exception:
            allow = False

        if not allow:
            return

        try:
            await item.callback(interaction)
        except Exception:
            _log.exception('Ignoring exception in dynamic item callback for %r', item)

    def dispatch_dynamic_items(self, component_type: int, custom_id: str, interaction: Interaction) -> None:
        for pattern, item in self._dynamic_items.items():
            match = pattern.fullmatch(custom_id)
            if match is not None:
                asyncio.create_task(
                    self.schedule_dynamic_item_call(component_type, item, interaction, custom_id, match),
                    name=f'discord-ui-dynamic-item-{item.__name__}-{custom_id}',
                )

    def dispatch_view(self, component_type: int, custom_id: str, interaction: Interaction) -> None:
        self.dispatch_dynamic_items(component_type, custom_id, interaction)
        interaction_id: Optional[int] = None
        message_id: Optional[int] = None
        # Realistically, in a component based interaction the Interaction.message will never be None
        # However, this guard is just in case Discord screws up somehow
        msg = interaction.message
        if msg is not None:
            message_id = msg.id
            if msg.interaction_metadata:
                interaction_id = msg.interaction_metadata.id

        key = (component_type, custom_id)

        # The entity_id can either be message_id, interaction_id, or None in that priority order.
        item: Optional[Item[View]] = None
        if message_id is not None:
            item = self._views.get(message_id, {}).get(key)

        if item is None and interaction_id is not None:
            try:
                items = self._views.pop(interaction_id)
            except KeyError:
                item = None
            else:
                item = items.get(key)
                # If we actually got the items, then these keys should probably be moved
                # to the proper message_id instead of the interaction_id as they are now.
                # An interaction_id is only used as a temporary stop gap for
                # InteractionResponse.send_message so multiple view instances do not
                # override each other.
                # NOTE: Fix this mess if /callback endpoint ever gets proper return types
                self._views.setdefault(message_id, {}).update(items)

        if item is None:
            # Fallback to None message_id searches in case a persistent view
            # was added without an associated message_id
            item = self._views.get(None, {}).get(key)

        # If 3 lookups failed at this point then just discard it
        if item is None:
            return

        # Note, at this point the View is *not* None
        item.view._dispatch_item(item, interaction)  # type: ignore

    def dispatch_modal(
        self,
        custom_id: str,
        interaction: Interaction,
        components: List[ModalSubmitComponentInteractionDataPayload],
    ) -> None:
        modal = self._modals.get(custom_id)
        if modal is None:
            _log.debug("Modal interaction referencing unknown custom_id %s. Discarding", custom_id)
            return

        modal._dispatch_submit(interaction, components)

    def remove_interaction_mapping(self, interaction_id: int) -> None:
        # This is called before re-adding the view
        self._views.pop(interaction_id, None)
        self._synced_message_views.pop(interaction_id, None)

    def is_message_tracked(self, message_id: int) -> bool:
        return message_id in self._synced_message_views

    def remove_message_tracking(self, message_id: int) -> Optional[View]:
        return self._synced_message_views.pop(message_id, None)

    def update_from_message(self, message_id: int, data: List[ComponentPayload]) -> None:
        components: List[Component] = []

        for component_data in data:
            component = _component_factory(component_data)

            if component is not None:
                components.append(component)

        # pre-req: is_message_tracked == true
        view = self._synced_message_views[message_id]
        view._refresh(components)
