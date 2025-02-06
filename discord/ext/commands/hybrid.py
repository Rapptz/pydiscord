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

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    List,
    Tuple,
    Type,
    TypeVar,
    Union,
    Optional,
)

import discord
import inspect
from discord import app_commands
from discord.utils import MISSING, maybe_coroutine, async_all
from .core import Command, Group
from .errors import BadArgument, CommandRegistrationError, CommandError, HybridCommandError, ConversionError, DisabledCommand
from .converter import Converter, Range, Greedy, run_converters, CONVERTER_MAPPING
from .parameters import Parameter
from .flags import is_flag, FlagConverter
from .cog import Cog
from .view import StringView

if TYPE_CHECKING:
    from typing_extensions import Self, ParamSpec, Concatenate
    from ._types import ContextT, Coro, BotT
    from .bot import Bot
    from .context import Context
    from discord.app_commands.commands import (
        Check as AppCommandCheck,
        AutocompleteCallback,
        ChoiceT,
    )


__all__ = (
    'HybridCommand',
    'HybridGroup',
    'hybrid_command',
    'hybrid_group',
)

T = TypeVar('T')
U = TypeVar('U')
CogT = TypeVar('CogT', bound='Cog')
CommandT = TypeVar('CommandT', bound='Command[Any, ..., Any]')
# CHT = TypeVar('CHT', bound='Check')
GroupT = TypeVar('GroupT', bound='Group[Any, ..., Any]')
_NoneType = type(None)

if TYPE_CHECKING:
    P = ParamSpec('P')
    P2 = ParamSpec('P2')

    CommandCallback = Union[
        Callable[Concatenate[CogT, ContextT, P], Coro[T]],
        Callable[Concatenate[ContextT, P], Coro[T]],
    ]
else:
    P = TypeVar('P')
    P2 = TypeVar('P2')


class _CallableDefault:
    __slots__ = ('func',)

    def __init__(self, func: Callable[[Context], Any]) -> None:
        self.func: Callable[[Context], Any] = func

    @property
    def __class__(self) -> Any:
        return _NoneType


def is_converter(converter: Any) -> bool:
    return (inspect.isclass(converter) and issubclass(converter, Converter)) or isinstance(converter, Converter)


def is_transformer(converter: Any) -> bool:
    return hasattr(converter, '__discord_app_commands_transformer__') or hasattr(
        converter, '__discord_app_commands_transform__'
    )


def required_pos_arguments(func: Callable[..., Any]) -> int:
    sig = inspect.signature(func)
    return sum(p.default is p.empty for p in sig.parameters.values())


class ConverterTransformer(app_commands.Transformer):
    def __init__(self, converter: Any, parameter: Parameter) -> None:
        super().__init__()
        self.converter: Any = converter
        self.parameter: Parameter = parameter

        try:
            module = converter.__module__
        except AttributeError:
            pass
        else:
            if module is not None and (module.startswith('discord.') and not module.endswith('converter')):
                self.converter = CONVERTER_MAPPING.get(converter, converter)

    async def transform(self, interaction: discord.Interaction, value: str, /) -> Any:
        ctx = interaction._baton
        converter = self.converter
        ctx.current_parameter = self.parameter
        ctx.current_argument = value
        try:
            if inspect.isclass(converter) and issubclass(converter, Converter):
                if inspect.ismethod(converter.convert):
                    return await converter.convert(ctx, value)
                else:
                    return await converter().convert(ctx, value)
            elif isinstance(converter, Converter):
                return await converter.convert(ctx, value)
        except CommandError:
            raise
        except Exception as exc:
            raise ConversionError(converter, exc) from exc  # type: ignore


class CallableTransformer(app_commands.Transformer):
    def __init__(self, func: Callable[[str], Any]) -> None:
        super().__init__()
        self.func: Callable[[str], Any] = func

    async def transform(self, interaction: discord.Interaction, value: str, /) -> Any:
        try:
            return self.func(value)
        except CommandError:
            raise
        except Exception as exc:
            raise BadArgument(f'Converting to "{self.func.__name__}" failed') from exc


class GreedyTransformer(app_commands.Transformer):
    def __init__(self, converter: Any, parameter: Parameter) -> None:
        super().__init__()
        self.converter: Any = converter
        self.parameter: Parameter = parameter

    async def transform(self, interaction: discord.Interaction, value: str, /) -> Any:
        view = StringView(value)
        result = []
        ctx = interaction._baton
        ctx.current_parameter = parameter = self.parameter
        converter = self.converter

        while True:
            view.skip_ws()
            ctx.current_argument = arg = view.get_quoted_word()
            if arg is None:
                break

            # This propagates the exception
            converted = await run_converters(ctx, converter, arg, parameter)
            result.append(converted)

        return result


def replace_parameter(
    param: inspect.Parameter,
    converter: Any,
    callback: Callable[..., Any],
    original: Parameter,
    mapping: Dict[str, inspect.Parameter],
) -> inspect.Parameter:
    try:
        # If it's a supported annotation (i.e. a transformer) just let it pass as-is.
        app_commands.transformers.get_supported_annotation(converter)
    except TypeError:
        # Fallback to see if the behaviour needs changing
        origin = getattr(converter, '__origin__', None)
        args = getattr(converter, '__args__', [])
        if isinstance(converter, Range):
            r = converter
            param = param.replace(annotation=app_commands.Range[r.annotation, r.min, r.max])
        elif isinstance(converter, Greedy):
            # Greedy is "optional" in ext.commands
            # However, in here, it probably makes sense to make it required.
            # I'm unsure how to allow the user to choose right now.
            inner = converter.converter
            if inner is discord.Attachment:
                raise TypeError('discord.Attachment with Greedy is not supported in hybrid commands')

            param = param.replace(annotation=GreedyTransformer(inner, original))
        elif is_flag(converter):
            callback.__hybrid_command_flag__ = (param.name, converter)
            descriptions = {}
            renames = {}
            for flag in converter.__commands_flags__.values():
                name = flag.attribute
                flag_param = inspect.Parameter(
                    name=name,
                    kind=param.kind,
                    default=flag.default if flag.default is not MISSING else inspect.Parameter.empty,
                    annotation=flag.annotation,
                )
                pseudo = replace_parameter(flag_param, flag.annotation, callback, original, mapping)
                if name in mapping:
                    raise TypeError(f'{name!r} flag would shadow a pre-existing parameter')
                if flag.description is not MISSING:
                    descriptions[name] = flag.description
                if flag.name != flag.attribute:
                    renames[name] = flag.name
                if pseudo.default is not pseudo.empty:
                    # This ensures the default is wrapped around _CallableDefault if callable
                    # else leaves it as-is.
                    pseudo = pseudo.replace(
                        default=_CallableDefault(flag.default) if callable(flag.default) else flag.default
                    )

                mapping[name] = pseudo

            # Manually call the decorators
            if descriptions:
                app_commands.describe(**descriptions)(callback)
            if renames:
                app_commands.rename(**renames)(callback)

        elif is_converter(converter) or converter in CONVERTER_MAPPING:
            param = param.replace(annotation=ConverterTransformer(converter, original))
        elif origin is Union:
            if len(args) == 2 and args[-1] is _NoneType:
                # Special case Optional[X] where X is a single type that can optionally be a converter
                inner = args[0]
                is_inner_transformer = is_transformer(inner)
                if is_converter(inner) and not is_inner_transformer:
                    param = param.replace(annotation=Optional[ConverterTransformer(inner, original)])  # type: ignore
            else:
                raise
        elif origin:
            # Unsupported typing.X annotation e.g. typing.Dict, typing.Tuple, typing.List, etc.
            raise
        elif callable(converter) and not inspect.isclass(converter):
            param_count = required_pos_arguments(converter)
            if param_count != 1:
                raise
            param = param.replace(annotation=CallableTransformer(converter))

    return param


def replace_parameters(
    parameters: Dict[str, Parameter], callback: Callable[..., Any], signature: inspect.Signature
) -> List[inspect.Parameter]:
    # Need to convert commands.Parameter back to inspect.Parameter so this will be a bit ugly
    params = signature.parameters.copy()
    for name, parameter in parameters.items():
        converter = parameter.converter
        # Parameter.converter properly infers from the default and has a str default
        # This allows the actual signature to inherit this property
        param = params[name].replace(annotation=converter)
        param = replace_parameter(param, converter, callback, parameter, params)

        if parameter.default is not parameter.empty:
            default = _CallableDefault(parameter.default) if callable(parameter.default) else parameter.default
            param = param.replace(default=default)

        if isinstance(param.default, Parameter):
            # If we're here, then it hasn't been handled yet so it should be removed completely
            param = param.replace(default=parameter.empty)

        # Flags are flattened out and thus don't get their parameter in the actual mapping
        if hasattr(converter, '__commands_is_flag__'):
            del params[name]
            continue

        params[name] = param

    return list(params.values())


class HybridAppCommand(discord.app_commands.Command[CogT, P, T]):
    __commands_is_hybrid_app_command__: ClassVar[bool] = True

    def __init__(
        self,
        wrapped: Union[HybridCommand[CogT, ..., T], HybridGroup[CogT, ..., T]],
        name: Optional[Union[str, app_commands.locale_str]] = None,
    ) -> None:
        signature = inspect.signature(wrapped.callback)
        params = replace_parameters(wrapped.params, wrapped.callback, signature)
        wrapped.callback.__signature__ = signature.replace(parameters=params)
        nsfw = getattr(wrapped.callback, '__discord_app_commands_is_nsfw__', False)
        try:
            super().__init__(
                name=name or wrapped._locale_name or wrapped.name,
                callback=wrapped.callback,  # type: ignore # Signature doesn't match but we're overriding the invoke
                description=wrapped._locale_description or wrapped.description or wrapped.short_doc or '…',
                nsfw=nsfw,
            )
        finally:
            del wrapped.callback.__signature__

        self.wrapped: Union[HybridCommand[CogT, ..., T], HybridGroup[CogT, ..., T]] = wrapped
        self.binding: Optional[CogT] = wrapped.cog
        # This technically means only one flag converter is supported
        self.flag_converter: Optional[Tuple[str, Type[FlagConverter]]] = getattr(
            wrapped.callback, '__hybrid_command_flag__', None
        )
        self.module = wrapped.module

    def _copy_with(self, **kwargs) -> Self:
        copy: Self = super()._copy_with(**kwargs)  # type: ignore
        copy.wrapped = self.wrapped
        copy.flag_converter = self.flag_converter
        return copy

    def copy(self) -> Self:
        bindings = {
            self.binding: self.binding,
        }
        return self._copy_with(parent=self.parent, binding=self.binding, bindings=bindings)

    async def _transform_arguments(
        self, interaction: discord.Interaction, namespace: app_commands.Namespace
    ) -> Dict[str, Any]:
        values = namespace.__dict__
        transformed_values = {}

        for param in self._params.values():
            try:
                value = values[param.display_name]
            except KeyError:
                if not param.required:
                    if isinstance(param.default, _CallableDefault):
                        transformed_values[param.name] = await maybe_coroutine(param.default.func, interaction._baton)
                    else:
                        transformed_values[param.name] = param.default
                else:
                    raise app_commands.CommandSignatureMismatch(self) from None
            else:
                transformed_values[param.name] = await param.transform(interaction, value)

        if self.flag_converter is not None:
            param_name, flag_cls = self.flag_converter
            flag = flag_cls.__new__(flag_cls)
            for f in flag_cls.__commands_flags__.values():
                try:
                    value = transformed_values.pop(f.attribute)
                except KeyError:
                    raise app_commands.CommandSignatureMismatch(self) from None
                else:
                    setattr(flag, f.attribute, value)

            transformed_values[param_name] = flag

        return transformed_values

    async def _check_can_run(self, interaction: discord.Interaction) -> bool:
        # Hybrid checks must run like so:
        # - Bot global check once
        # - Bot global check
        # - Parent interaction check
        # - Cog/group interaction check
        # - Cog check
        # - Local interaction checks
        # - Local command checks

        bot: Bot = interaction.client  # type: ignore
        ctx: Context[Bot] = interaction._baton

        if not await bot.can_run(ctx, call_once=True):
            return False

        if not await bot.can_run(ctx):
            return False

        if self.parent is not None and self.parent is not self.binding:
            # For commands with a parent which isn't the binding, i.e.
            # <binding>
            #     <parent>
            #         <command>
            # The parent check needs to be called first
            if not await maybe_coroutine(self.parent.interaction_check, interaction):
                return False

        if self.binding is not None:
            try:
                # Type checker does not like runtime attribute retrieval
                check: AppCommandCheck = self.binding.interaction_check
            except AttributeError:
                pass
            else:
                ret = await maybe_coroutine(check, interaction)
                if not ret:
                    return False

            local_check = Cog._get_overridden_method(self.binding.cog_check)
            if local_check is not None:
                ret = await maybe_coroutine(local_check, ctx)
                if not ret:
                    return False

        if self.checks and not await async_all(f(interaction) for f in self.checks):
            return False

        if self.wrapped.checks and not await async_all(f(ctx) for f in self.wrapped.checks):
            return False

        return True

    async def _invoke_with_namespace(self, interaction: discord.Interaction, namespace: app_commands.Namespace) -> Any:
        # Wrap the interaction into a Context
        bot: Bot = interaction.client  # type: ignore

        # Unfortunately, `get_context` has to be called for this to work.
        # If someone doesn't inherit this to replace it with their custom class
        # then this doesn't work.
        interaction._baton = ctx = await bot.get_context(interaction)
        command = self.wrapped
        bot.dispatch('command', ctx)
        value = None
        callback_completed = False
        try:
            await command.prepare(ctx)
            # This lies and just always passes a Context instead of an Interaction.
            value = await self._do_call(ctx, ctx.kwargs)  # type: ignore
            callback_completed = True
        except app_commands.CommandSignatureMismatch:
            raise
        except (app_commands.TransformerError, app_commands.CommandInvokeError) as e:
            if isinstance(e.__cause__, CommandError):
                exc = e.__cause__
            else:
                exc = HybridCommandError(e)
                exc.__cause__ = e
            await command.dispatch_error(ctx, exc.with_traceback(e.__traceback__))
        except app_commands.AppCommandError as e:
            exc = HybridCommandError(e)
            exc.__cause__ = e
            await command.dispatch_error(ctx, exc.with_traceback(e.__traceback__))
        except CommandError as e:
            await command.dispatch_error(ctx, e)
        finally:
            if command._max_concurrency is not None:
                await command._max_concurrency.release(ctx.message)

            if callback_completed:
                await command.call_after_hooks(ctx)

        if not ctx.command_failed:
            bot.dispatch('command_completion', ctx)

        interaction.command_failed = ctx.command_failed
        return value


class HybridCommand(Command[CogT, P, T]):
    r"""A class that is both an application command and a regular text command.

    This has the same parameters and attributes as a regular :class:`~discord.ext.commands.Command`.
    However, it also doubles as an :class:`application command <discord.app_commands.Command>`. In order
    for this to work, the callbacks must have the same subset that is supported by application
    commands.

    These are not created manually, instead they are created via the
    decorator or functional interface.

    .. versionadded:: 2.0
    """

    __commands_is_hybrid__: ClassVar[bool] = True

    def __init__(
        self,
        func: CommandCallback[CogT, Context[Any], P, T],
        /,
        *,
        name: Union[str, app_commands.locale_str] = MISSING,
        description: Union[str, app_commands.locale_str] = MISSING,
        **kwargs: Any,
    ) -> None:
        name, name_locale = (name.message, name) if isinstance(name, app_commands.locale_str) else (name, None)
        if name is not MISSING:
            kwargs['name'] = name
        description, description_locale = (
            (description.message, description) if isinstance(description, app_commands.locale_str) else (description, None)
        )
        if description is not MISSING:
            kwargs['description'] = description

        super().__init__(func, **kwargs)
        self.with_app_command: bool = kwargs.pop('with_app_command', True)
        self._locale_name: Optional[app_commands.locale_str] = name_locale
        self._locale_description: Optional[app_commands.locale_str] = description_locale

        self.app_command: Optional[HybridAppCommand[CogT, Any, T]] = (
            HybridAppCommand(self) if self.with_app_command else None
        )

    @property
    def cog(self) -> CogT:
        return self._cog

    @cog.setter
    def cog(self, value: CogT) -> None:
        self._cog = value
        if self.app_command is not None:
            self.app_command.binding = value

    async def can_run(self, ctx: ContextT, /) -> bool:
        if not self.enabled:
            raise DisabledCommand(f'{self.name} command is disabled')

        if ctx.interaction is not None and self.app_command:
            return await self.app_command._check_can_run(ctx.interaction)
        else:
            return await super().can_run(ctx)

    async def _parse_arguments(self, ctx: ContextT) -> None:
        interaction = ctx.interaction
        if interaction is None:
            return await super()._parse_arguments(ctx)
        elif self.app_command:
            ctx.kwargs = await self.app_command._transform_arguments(interaction, interaction.namespace)

    def _ensure_assignment_on_copy(self, other: Self) -> Self:
        copy = super()._ensure_assignment_on_copy(other)
        if self.app_command is None:
            copy.app_command = None
        else:
            copy.app_command = self.app_command.copy()
            copy.app_command.wrapped = copy
        return copy

    def autocomplete(
        self, name: str
    ) -> Callable[[AutocompleteCallback[CogT, ChoiceT]], AutocompleteCallback[CogT, ChoiceT]]:
        """A decorator that registers a coroutine as an autocomplete prompt for a parameter.

        This is the same as :meth:`~discord.app_commands.Command.autocomplete`. It is only
        applicable for the application command and doesn't do anything if the command is
        a regular command.

        .. note::

            Similar to the :meth:`~discord.app_commands.Command.autocomplete` method, this
            takes :class:`~discord.Interaction` as a parameter rather than a :class:`Context`.

        Parameters
        -----------
        name: :class:`str`
            The parameter name to register as autocomplete.

        Raises
        -------
        TypeError
            The coroutine passed is not actually a coroutine or
            the parameter is not found or of an invalid type.
        """
        if self.app_command is None:
            raise TypeError('This command does not have a registered application command')

        return self.app_command.autocomplete(name)


class HybridGroup(Group[CogT, P, T]):
    r"""A class that is both an application command group and a regular text group.

    This has the same parameters and attributes as a regular :class:`~discord.ext.commands.Group`.
    However, it also doubles as an :class:`application command group <discord.app_commands.Group>`.
    Note that application commands groups cannot have callbacks associated with them, so the callback
    is only called if it's not invoked as an application command.

    Hybrid groups will always have :attr:`Group.invoke_without_command` set to ``True``.

    These are not created manually, instead they are created via the
    decorator or functional interface.

    .. versionadded:: 2.0

    Attributes
    -----------
    fallback: Optional[:class:`str`]
        The command name to use as a fallback for the application command. Since
        application command groups cannot be invoked, this creates a subcommand within
        the group that can be invoked with the given group callback. If ``None``
        then no fallback command is given. Defaults to ``None``.
    fallback_locale: Optional[:class:`~discord.app_commands.locale_str`]
        The fallback command name's locale string, if available.
    """

    __commands_is_hybrid__: ClassVar[bool] = True

    def __init__(
        self,
        *args: Any,
        name: Union[str, app_commands.locale_str] = MISSING,
        description: Union[str, app_commands.locale_str] = MISSING,
        fallback: Optional[Union[str, app_commands.locale_str]] = None,
        **attrs: Any,
    ) -> None:
        name, name_locale = (name.message, name) if isinstance(name, app_commands.locale_str) else (name, None)
        if name is not MISSING:
            attrs['name'] = name
        description, description_locale = (
            (description.message, description) if isinstance(description, app_commands.locale_str) else (description, None)
        )
        if description is not MISSING:
            attrs['description'] = description
        super().__init__(*args, **attrs)
        self.invoke_without_command = True
        self.with_app_command: bool = attrs.pop('with_app_command', True)
        self._locale_name: Optional[app_commands.locale_str] = name_locale
        self._locale_description: Optional[app_commands.locale_str] = description_locale

        parent = None
        if self.parent is not None:
            if isinstance(self.parent, HybridGroup):
                parent = self.parent.app_command
            else:
                raise TypeError(f'HybridGroup parent must be HybridGroup not {self.parent.__class__}')

        # I would love for this to be Optional[app_commands.Group]
        # However, Python does not have conditional typing so it's very hard to
        # make this type depend on the with_app_command bool without a lot of needless repetition
        self.app_command: app_commands.Group = MISSING

        fallback, fallback_locale = (
            (fallback.message, fallback) if isinstance(fallback, app_commands.locale_str) else (fallback, None)
        )
        self.fallback: Optional[str] = fallback
        self.fallback_locale: Optional[app_commands.locale_str] = fallback_locale

        if self.with_app_command:
            guild_ids = attrs.pop('guild_ids', None) or getattr(
                self.callback, '__discord_app_commands_default_guilds__', None
            )
            guild_only = getattr(self.callback, '__discord_app_commands_guild_only__', False)
            default_permissions = getattr(self.callback, '__discord_app_commands_default_permissions__', None)
            nsfw = getattr(self.callback, '__discord_app_commands_is_nsfw__', False)
            contexts = getattr(self.callback, '__discord_app_commands_contexts__', MISSING)
            installs = getattr(self.callback, '__discord_app_commands_installation_types__', MISSING)
            self.app_command = app_commands.Group(
                name=self._locale_name or self.name,
                description=self._locale_description or self.description or self.short_doc or '…',
                guild_ids=guild_ids,
                guild_only=guild_only,
                default_permissions=default_permissions,
                nsfw=nsfw,
                allowed_installs=installs,
                allowed_contexts=contexts,
            )

            # This prevents the group from re-adding the command at __init__
            self.app_command.parent = parent
            self.app_command.module = self.module

            if fallback is not None:
                command = HybridAppCommand(self, name=fallback_locale or fallback)
                self.app_command.add_command(command)

    @property
    def _fallback_command(self) -> Optional[HybridAppCommand[CogT, ..., T]]:
        if self.app_command is MISSING:
            return None
        return self.app_command.get_command(self.fallback)  # type: ignore

    @property
    def cog(self) -> CogT:
        return self._cog

    @cog.setter
    def cog(self, value: CogT) -> None:
        self._cog = value
        fallback = self._fallback_command
        if fallback:
            fallback.binding = value

    async def can_run(self, ctx: ContextT, /) -> bool:
        fallback = self._fallback_command
        if ctx.interaction is not None and fallback:
            return await fallback._check_can_run(ctx.interaction)
        else:
            return await super().can_run(ctx)

    async def _parse_arguments(self, ctx: ContextT) -> None:
        interaction = ctx.interaction
        fallback = self._fallback_command
        if interaction is not None and fallback:
            ctx.kwargs = await fallback._transform_arguments(interaction, interaction.namespace)
        else:
            return await super()._parse_arguments(ctx)

    def _ensure_assignment_on_copy(self, other: Self) -> Self:
        copy = super()._ensure_assignment_on_copy(other)
        copy.fallback = self.fallback
        return copy

    def _update_copy(self, kwargs: Dict[str, Any]) -> Self:
        copy = super()._update_copy(kwargs)
        # This is only really called inside CogMeta
        # I want to ensure that the children of the app command are copied
        # For example, if someone defines an app command using the app_command property
        # while inside the cog. This copy is not propagated in normal means.
        # For some reason doing this copy above will lead to duplicates.
        if copy.app_command and self.app_command:
            # This is a very lazy copy because the CogMeta will properly copy it
            # with bindings and all later
            copy.app_command._children = self.app_command._children.copy()

        # Ensure the copy's fallback wraps the copy
        if copy._fallback_command and self._fallback_command:
            copy._fallback_command.wrapped = copy

        return copy

    def autocomplete(
        self, name: str
    ) -> Callable[[AutocompleteCallback[CogT, ChoiceT]], AutocompleteCallback[CogT, ChoiceT]]:
        """A decorator that registers a coroutine as an autocomplete prompt for a parameter.

        This is the same as :meth:`~discord.app_commands.Command.autocomplete`. It is only
        applicable for the application command and doesn't do anything if the command is
        a regular command.

        This is only available if the group has a fallback application command registered.

        .. note::

            Similar to the :meth:`~discord.app_commands.Command.autocomplete` method, this
            takes :class:`~discord.Interaction` as a parameter rather than a :class:`Context`.

        Parameters
        -----------
        name: :class:`str`
            The parameter name to register as autocomplete.

        Raises
        -------
        TypeError
            The coroutine passed is not actually a coroutine or
            the parameter is not found or of an invalid type.
        """
        if self._fallback_command:
            return self._fallback_command.autocomplete(name)
        else:

            def decorator(func: AutocompleteCallback[CogT, ChoiceT]) -> AutocompleteCallback[CogT, ChoiceT]:
                return func

            return decorator

    def add_command(self, command: Union[HybridGroup[CogT, ..., Any], HybridCommand[CogT, ..., Any]], /) -> None:
        """Adds a :class:`.HybridCommand` into the internal list of commands.

        This is usually not called, instead the :meth:`~.GroupMixin.command` or
        :meth:`~.GroupMixin.group` shortcut decorators are used instead.

        Parameters
        -----------
        command: :class:`HybridCommand`
            The command to add.

        Raises
        -------
        CommandRegistrationError
            If the command or its alias is already registered by different command.
        TypeError
            If the command passed is not a subclass of :class:`.HybridCommand`.
        """

        if not isinstance(command, (HybridCommand, HybridGroup)):
            raise TypeError('The command passed must be a subclass of HybridCommand or HybridGroup')

        if isinstance(command, HybridGroup) and self.parent is not None:
            raise ValueError(f'{command.qualified_name!r} is too nested, groups can only be nested at most one level')

        if command.app_command and self.app_command:
            self.app_command.add_command(command.app_command)

        command.parent = self

        if command.name in self.all_commands:
            raise CommandRegistrationError(command.name)

        self.all_commands[command.name] = command
        for alias in command.aliases:
            if alias in self.all_commands:
                self.remove_command(command.name)
                raise CommandRegistrationError(alias, alias_conflict=True)
            self.all_commands[alias] = command

    def remove_command(self, name: str, /) -> Optional[Command[CogT, ..., Any]]:
        cmd = super().remove_command(name)
        if self.app_command:
            self.app_command.remove_command(name)
        return cmd

    def command(
        self,
        name: Union[str, app_commands.locale_str] = MISSING,
        *args: Any,
        with_app_command: bool = True,
        **kwargs: Any,
    ) -> Callable[[CommandCallback[CogT, ContextT, P2, U]], HybridCommand[CogT, P2, U]]:
        """A shortcut decorator that invokes :func:`~discord.ext.commands.hybrid_command` and adds it to
        the internal command list via :meth:`add_command`.

        Returns
        --------
        Callable[..., :class:`HybridCommand`]
            A decorator that converts the provided method into a Command, adds it to the bot, then returns it.
        """

        def decorator(func: CommandCallback[CogT, ContextT, P2, U]):
            kwargs.setdefault('parent', self)
            result = hybrid_command(name=name, *args, with_app_command=with_app_command, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator

    def group(
        self,
        name: Union[str, app_commands.locale_str] = MISSING,
        *args: Any,
        with_app_command: bool = True,
        **kwargs: Any,
    ) -> Callable[[CommandCallback[CogT, ContextT, P2, U]], HybridGroup[CogT, P2, U]]:
        """A shortcut decorator that invokes :func:`~discord.ext.commands.hybrid_group` and adds it to
        the internal command list via :meth:`~.GroupMixin.add_command`.

        Returns
        --------
        Callable[..., :class:`HybridGroup`]
            A decorator that converts the provided method into a Group, adds it to the bot, then returns it.
        """

        def decorator(func: CommandCallback[CogT, ContextT, P2, U]):
            kwargs.setdefault('parent', self)
            result = hybrid_group(name=name, *args, with_app_command=with_app_command, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator


def hybrid_command(
    name: Union[str, app_commands.locale_str] = MISSING,
    *,
    with_app_command: bool = True,
    **attrs: Any,
) -> Callable[[CommandCallback[CogT, ContextT, P, T]], HybridCommand[CogT, P, T]]:
    r"""A decorator that transforms a function into a :class:`.HybridCommand`.

    A hybrid command is one that functions both as a regular :class:`.Command`
    and one that is also a :class:`app_commands.Command <discord.app_commands.Command>`.

    The callback being attached to the command must be representable as an
    application command callback. Converters are silently converted into a
    :class:`~discord.app_commands.Transformer` with a
    :attr:`discord.AppCommandOptionType.string` type.

    Checks and error handlers are dispatched and called as-if they were commands
    similar to :class:`.Command`. This means that they take :class:`Context` as
    a parameter rather than :class:`discord.Interaction`.

    All checks added using the :func:`.check` & co. decorators are added into
    the function. There is no way to supply your own checks through this
    decorator.

    .. versionadded:: 2.0

    Parameters
    -----------
    name: Union[:class:`str`, :class:`~discord.app_commands.locale_str`]
        The name to create the command with. By default this uses the
        function name unchanged.
    with_app_command: :class:`bool`
        Whether to register the command also as an application command.
    \*\*attrs
        Keyword arguments to pass into the construction of the
        hybrid command.

    Raises
    -------
    TypeError
        If the function is not a coroutine or is already a command.
    """

    def decorator(func: CommandCallback[CogT, ContextT, P, T]) -> HybridCommand[CogT, P, T]:
        if isinstance(func, Command):
            raise TypeError('Callback is already a command.')
        return HybridCommand(func, name=name, with_app_command=with_app_command, **attrs)

    return decorator


def hybrid_group(
    name: Union[str, app_commands.locale_str] = MISSING,
    *,
    with_app_command: bool = True,
    **attrs: Any,
) -> Callable[[CommandCallback[CogT, ContextT, P, T]], HybridGroup[CogT, P, T]]:
    """A decorator that transforms a function into a :class:`.HybridGroup`.

    This is similar to the :func:`~discord.ext.commands.group` decorator except it creates
    a hybrid group instead.

    Parameters
    -----------
    name: Union[:class:`str`, :class:`~discord.app_commands.locale_str`]
        The name to create the group with. By default this uses the
        function name unchanged.
    with_app_command: :class:`bool`
        Whether to register the command also as an application command.

    Raises
    -------
    TypeError
        If the function is not a coroutine or is already a command.
    """

    def decorator(func: CommandCallback[CogT, ContextT, P, T]) -> HybridGroup[CogT, P, T]:
        if isinstance(func, Command):
            raise TypeError('Callback is already a command.')
        return HybridGroup(func, name=name, with_app_command=with_app_command, **attrs)

    return decorator
