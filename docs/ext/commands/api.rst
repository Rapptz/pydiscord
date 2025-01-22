.. currentmodule:: discord

API Reference
===============

The following section outlines the API of discord.py's command extension module.

.. _ext_commands_api_bot:

Bots
------

Bot
~~~~

.. attributetable:: discord.ext.commands.Bot

.. autoclass:: discord.ext.commands.Bot
    :members:
    :inherited-members:
    :exclude-members: after_invoke, before_invoke, check, check_once, command, event, group, hybrid_command, hybrid_group, listen

    .. automethod:: Bot.after_invoke()
        :decorator:

    .. automethod:: Bot.before_invoke()
        :decorator:

    .. automethod:: Bot.check()
        :decorator:

    .. automethod:: Bot.check_once()
        :decorator:

    .. automethod:: Bot.command(*args, **kwargs)
        :decorator:

    .. automethod:: Bot.event()
        :decorator:

    .. automethod:: Bot.group(*args, **kwargs)
        :decorator:

    .. automethod:: Bot.hybrid_command(name=..., with_app_command=True, *args, **kwargs)
        :decorator:

    .. automethod:: Bot.hybrid_group(name=..., with_app_command=True, *args, **kwargs)
        :decorator:

    .. automethod:: Bot.listen(name=None)
        :decorator:

AutoShardedBot
~~~~~~~~~~~~~~~~

.. attributetable:: discord.ext.commands.AutoShardedBot

.. autoclass:: discord.ext.commands.AutoShardedBot
    :members:

Prefix Helpers
----------------

.. autofunction:: discord.ext.commands.when_mentioned

.. autofunction:: discord.ext.commands.when_mentioned_or

.. _ext_commands_api_events:

Event Reference
-----------------

These events function similar to :ref:`the regular events <discord-api-events>`, except they
are custom to the command extension module.

.. function:: discord.ext.commands.on_command_error(ctx, error)

    An error handler that is called when an error is raised
    inside a command either through user input error, check
    failure, or an error in your own code.

    A default one is provided (:meth:`.Bot.on_command_error`).

    :param ctx: The invocation context.
    :type ctx: :class:`.Context`
    :param error: The error that was raised.
    :type error: :class:`.CommandError` derived

.. function:: discord.ext.commands.on_command(ctx)

    An event that is called when a command is found and is about to be invoked.

    This event is called regardless of whether the command itself succeeds via
    error or completes.

    :param ctx: The invocation context.
    :type ctx: :class:`.Context`

.. function:: discord.ext.commands.on_command_completion(ctx)

    An event that is called when a command has completed its invocation.

    This event is called only if the command succeeded, i.e. all checks have
    passed and the user input it correctly.

    :param ctx: The invocation context.
    :type ctx: :class:`.Context`

.. _ext_commands_api_command:

Commands
----------

Decorators
~~~~~~~~~~~~

.. autofunction:: discord.ext.commands.command
    :decorator:

.. autofunction:: discord.ext.commands.group
    :decorator:

.. autofunction:: discord.ext.commands.hybrid_command
    :decorator:

.. autofunction:: discord.ext.commands.hybrid_group
    :decorator:


Command
~~~~~~~~~

.. attributetable:: discord.ext.commands.Command

.. autoclass:: discord.ext.commands.Command
    :members:
    :special-members: __call__
    :exclude-members: after_invoke, before_invoke, error

    .. automethod:: Command.after_invoke()
        :decorator:

    .. automethod:: Command.before_invoke()
        :decorator:

    .. automethod:: Command.error()
        :decorator:

Group
~~~~~~

.. attributetable:: discord.ext.commands.Group

.. autoclass:: discord.ext.commands.Group
    :members:
    :inherited-members:
    :exclude-members: after_invoke, before_invoke, command, error, group

    .. automethod:: Group.after_invoke()
        :decorator:

    .. automethod:: Group.before_invoke()
        :decorator:

    .. automethod:: Group.command(*args, **kwargs)
        :decorator:

    .. automethod:: Group.error()
        :decorator:

    .. automethod:: Group.group(*args, **kwargs)
        :decorator:

GroupMixin
~~~~~~~~~~~

.. attributetable:: discord.ext.commands.GroupMixin

.. autoclass:: discord.ext.commands.GroupMixin
    :members:
    :exclude-members: command, group

    .. automethod:: GroupMixin.command(*args, **kwargs)
        :decorator:

    .. automethod:: GroupMixin.group(*args, **kwargs)
        :decorator:

HybridCommand
~~~~~~~~~~~~~~

.. attributetable:: discord.ext.commands.HybridCommand

.. autoclass:: discord.ext.commands.HybridCommand
    :members:
    :special-members: __call__
    :exclude-members: after_invoke, autocomplete, before_invoke, error

    .. automethod:: HybridCommand.after_invoke()
        :decorator:

    .. automethod:: HybridCommand.autocomplete(name)
        :decorator:

    .. automethod:: HybridCommand.before_invoke()
        :decorator:

    .. automethod:: HybridCommand.error()
        :decorator:

HybridGroup
~~~~~~~~~~~~

.. attributetable:: discord.ext.commands.HybridGroup

.. autoclass:: discord.ext.commands.HybridGroup
    :members:
    :inherited-members:
    :exclude-members: after_invoke, autocomplete, before_invoke, command, error, group

    .. automethod:: HybridGroup.after_invoke()
        :decorator:

    .. automethod:: HybridGroup.autocomplete(name)
        :decorator:

    .. automethod:: HybridGroup.before_invoke()
        :decorator:

    .. automethod:: HybridGroup.command(*args, **kwargs)
        :decorator:

    .. automethod:: HybridGroup.error()
        :decorator:

    .. automethod:: HybridGroup.group(*args, **kwargs)
        :decorator:


.. _ext_commands_api_cogs:

Cogs
------

Cog
~~~~

.. attributetable:: discord.ext.commands.Cog

.. autoclass:: discord.ext.commands.Cog
    :members:

GroupCog
~~~~~~~~~

.. attributetable:: discord.ext.commands.GroupCog

.. autoclass:: discord.ext.commands.GroupCog
    :members: interaction_check


CogMeta
~~~~~~~~

.. attributetable:: discord.ext.commands.CogMeta

.. autoclass:: discord.ext.commands.CogMeta
    :members:

.. _ext_commands_help_command:

Help Commands
---------------

HelpCommand
~~~~~~~~~~~~

.. attributetable:: discord.ext.commands.HelpCommand

.. autoclass:: discord.ext.commands.HelpCommand
    :members:

DefaultHelpCommand
~~~~~~~~~~~~~~~~~~~

.. attributetable:: discord.ext.commands.DefaultHelpCommand

.. autoclass:: discord.ext.commands.DefaultHelpCommand
    :members:
    :exclude-members: send_bot_help, send_cog_help, send_group_help, send_command_help, prepare_help_command

MinimalHelpCommand
~~~~~~~~~~~~~~~~~~~

.. attributetable:: discord.ext.commands.MinimalHelpCommand

.. autoclass:: discord.ext.commands.MinimalHelpCommand
    :members:
    :exclude-members: send_bot_help, send_cog_help, send_group_help, send_command_help, prepare_help_command

Paginator
~~~~~~~~~~

.. attributetable:: discord.ext.commands.Paginator

.. autoclass:: discord.ext.commands.Paginator
    :members:

Enums
------

.. class:: BucketType
    :module: discord.ext.commands

    Specifies a type of bucket for, e.g. a cooldown.

    .. attribute:: default

        The default bucket operates on a global basis.
    .. attribute:: user

        The user bucket operates on a per-user basis.
    .. attribute:: guild

        The guild bucket operates on a per-guild basis.
    .. attribute:: channel

        The channel bucket operates on a per-channel basis.
    .. attribute:: member

        The member bucket operates on a per-member basis.
    .. attribute:: category

        The category bucket operates on a per-category basis.
    .. attribute:: role

        The role bucket operates on a per-role basis.

        .. versionadded:: 1.3


.. _ext_commands_api_checks:

Checks
-------

.. autofunction:: discord.ext.commands.check(predicate)
    :decorator:

.. autofunction:: discord.ext.commands.check_any(*checks)
    :decorator:

.. autofunction:: discord.ext.commands.has_role(item)
    :decorator:

.. autofunction:: discord.ext.commands.has_permissions(**perms)
    :decorator:

.. autofunction:: discord.ext.commands.has_guild_permissions(**perms)
    :decorator:

.. autofunction:: discord.ext.commands.has_any_role(*items)
    :decorator:

.. autofunction:: discord.ext.commands.bot_has_role(item)
    :decorator:

.. autofunction:: discord.ext.commands.bot_has_permissions(**perms)
    :decorator:

.. autofunction:: discord.ext.commands.bot_has_guild_permissions(**perms)
    :decorator:

.. autofunction:: discord.ext.commands.bot_has_any_role(*items)
    :decorator:

.. autofunction:: discord.ext.commands.cooldown(rate, per, type=discord.ext.commands.BucketType.default)
    :decorator:

.. autofunction:: discord.ext.commands.dynamic_cooldown(cooldown, type)
    :decorator:

.. autofunction:: discord.ext.commands.max_concurrency(number, per=discord.ext.commands.BucketType.default, *, wait=False)
    :decorator:

.. autofunction:: discord.ext.commands.before_invoke(coro)
    :decorator:

.. autofunction:: discord.ext.commands.after_invoke(coro)
    :decorator:

.. autofunction:: discord.ext.commands.guild_only(,)
    :decorator:

.. autofunction:: discord.ext.commands.dm_only(,)
    :decorator:

.. autofunction:: discord.ext.commands.is_owner(,)
    :decorator:

.. autofunction:: discord.ext.commands.is_nsfw(,)
    :decorator:

.. _ext_commands_api_context:

Context
--------

.. attributetable:: discord.ext.commands.Context

.. autoclass:: discord.ext.commands.Context
    :members:
    :inherited-members:
    :exclude-members: typing

    .. automethod:: discord.ext.commands.Context.typing
        :async-with:

.. _ext_commands_api_converters:

Converters
------------

.. attributetable:: discord.ext.commands.Converter

.. autoclass:: discord.ext.commands.Converter
    :members:

.. attributetable:: discord.ext.commands.ObjectConverter

.. autoclass:: discord.ext.commands.ObjectConverter
    :members:

.. attributetable:: discord.ext.commands.MemberConverter

.. autoclass:: discord.ext.commands.MemberConverter
    :members:

.. attributetable:: discord.ext.commands.UserConverter

.. autoclass:: discord.ext.commands.UserConverter
    :members:

.. attributetable:: discord.ext.commands.MessageConverter

.. autoclass:: discord.ext.commands.MessageConverter
    :members:

.. attributetable:: discord.ext.commands.PartialMessageConverter

.. autoclass:: discord.ext.commands.PartialMessageConverter
    :members:

.. attributetable:: discord.ext.commands.GuildChannelConverter

.. autoclass:: discord.ext.commands.GuildChannelConverter
    :members:

.. attributetable:: discord.ext.commands.TextChannelConverter

.. autoclass:: discord.ext.commands.TextChannelConverter
    :members:

.. attributetable:: discord.ext.commands.VoiceChannelConverter

.. autoclass:: discord.ext.commands.VoiceChannelConverter
    :members:

.. attributetable:: discord.ext.commands.StageChannelConverter

.. autoclass:: discord.ext.commands.StageChannelConverter
    :members:

.. attributetable:: discord.ext.commands.CategoryChannelConverter

.. autoclass:: discord.ext.commands.CategoryChannelConverter
    :members:

.. attributetable:: discord.ext.commands.ForumChannelConverter

.. autoclass:: discord.ext.commands.ForumChannelConverter
    :members:

.. attributetable:: discord.ext.commands.InviteConverter

.. autoclass:: discord.ext.commands.InviteConverter
    :members:

.. attributetable:: discord.ext.commands.GuildConverter

.. autoclass:: discord.ext.commands.GuildConverter
    :members:

.. attributetable:: discord.ext.commands.RoleConverter

.. autoclass:: discord.ext.commands.RoleConverter
    :members:

.. attributetable:: discord.ext.commands.GameConverter

.. autoclass:: discord.ext.commands.GameConverter
    :members:

.. attributetable:: discord.ext.commands.ColourConverter

.. autoclass:: discord.ext.commands.ColourConverter
    :members:

.. attributetable:: discord.ext.commands.EmojiConverter

.. autoclass:: discord.ext.commands.EmojiConverter
    :members:

.. attributetable:: discord.ext.commands.PartialEmojiConverter

.. autoclass:: discord.ext.commands.PartialEmojiConverter
    :members:

.. attributetable:: discord.ext.commands.ThreadConverter

.. autoclass:: discord.ext.commands.ThreadConverter
    :members:

.. attributetable:: discord.ext.commands.GuildStickerConverter

.. autoclass:: discord.ext.commands.GuildStickerConverter
    :members:

.. attributetable:: discord.ext.commands.ScheduledEventConverter

.. autoclass:: discord.ext.commands.ScheduledEventConverter
    :members:

.. attributetable:: discord.ext.commands.clean_content

.. autoclass:: discord.ext.commands.clean_content
    :members:

.. attributetable:: discord.ext.commands.Greedy

.. autoclass:: discord.ext.commands.Greedy()

.. attributetable:: discord.ext.commands.Range

.. autoclass:: discord.ext.commands.Range()

.. autofunction:: discord.ext.commands.run_converters

Flag Converter
~~~~~~~~~~~~~~~

.. attributetable:: discord.ext.commands.FlagConverter

.. autoclass:: discord.ext.commands.FlagConverter
    :members:

.. attributetable:: discord.ext.commands.Flag

.. autoclass:: discord.ext.commands.Flag()
    :members:

.. autofunction:: discord.ext.commands.flag


Defaults
--------

.. attributetable:: discord.ext.commands.Parameter

.. autoclass:: discord.ext.commands.Parameter()
    :members:

.. autofunction:: discord.ext.commands.parameter

.. autofunction:: discord.ext.commands.param

.. data:: discord.ext.commands.Author

    A default :class:`Parameter` which returns the :attr:`~.Context.author` for this context.

    .. versionadded:: 2.0

.. data:: discord.ext.commands.CurrentChannel

    A default :class:`Parameter` which returns the :attr:`~.Context.channel` for this context.

    .. versionadded:: 2.0

.. data:: discord.ext.commands.CurrentGuild

    A default :class:`Parameter` which returns the :attr:`~.Context.guild` for this context. This will never be ``None``. If the command is called in a DM context then :exc:`~discord.ext.commands.NoPrivateMessage` is raised to the error handlers.

    .. versionadded:: 2.0

.. _ext_commands_api_errors:

Exceptions
-----------

.. autoexception:: discord.ext.commands.CommandError
    :members:

.. autoexception:: discord.ext.commands.ConversionError
    :members:

.. autoexception:: discord.ext.commands.MissingRequiredArgument
    :members:

.. autoexception:: discord.ext.commands.MissingRequiredAttachment
    :members:

.. autoexception:: discord.ext.commands.MissingRequiredSticker
    :members:

.. autoexception:: discord.ext.commands.ArgumentParsingError
    :members:

.. autoexception:: discord.ext.commands.UnexpectedQuoteError
    :members:

.. autoexception:: discord.ext.commands.InvalidEndOfQuotedStringError
    :members:

.. autoexception:: discord.ext.commands.ExpectedClosingQuoteError
    :members:

.. autoexception:: discord.ext.commands.BadArgument
    :members:

.. autoexception:: discord.ext.commands.BadUnionArgument
    :members:

.. autoexception:: discord.ext.commands.BadLiteralArgument
    :members:

.. autoexception:: discord.ext.commands.PrivateMessageOnly
    :members:

.. autoexception:: discord.ext.commands.NoPrivateMessage
    :members:

.. autoexception:: discord.ext.commands.CheckFailure
    :members:

.. autoexception:: discord.ext.commands.CheckAnyFailure
    :members:

.. autoexception:: discord.ext.commands.CommandNotFound
    :members:

.. autoexception:: discord.ext.commands.DisabledCommand
    :members:

.. autoexception:: discord.ext.commands.CommandInvokeError
    :members:

.. autoexception:: discord.ext.commands.TooManyArguments
    :members:

.. autoexception:: discord.ext.commands.UserInputError
    :members:

.. autoexception:: discord.ext.commands.CommandOnCooldown
    :members:

.. autoexception:: discord.ext.commands.MaxConcurrencyReached
    :members:

.. autoexception:: discord.ext.commands.NotOwner
    :members:

.. autoexception:: discord.ext.commands.MessageNotFound
    :members:

.. autoexception:: discord.ext.commands.MemberNotFound
    :members:

.. autoexception:: discord.ext.commands.GuildNotFound
    :members:

.. autoexception:: discord.ext.commands.UserNotFound
    :members:

.. autoexception:: discord.ext.commands.ChannelNotFound
    :members:

.. autoexception:: discord.ext.commands.ChannelNotReadable
    :members:

.. autoexception:: discord.ext.commands.ThreadNotFound
    :members:

.. autoexception:: discord.ext.commands.BadColourArgument
    :members:

.. autoexception:: discord.ext.commands.RoleNotFound
    :members:

.. autoexception:: discord.ext.commands.BadInviteArgument
    :members:

.. autoexception:: discord.ext.commands.EmojiNotFound
    :members:

.. autoexception:: discord.ext.commands.PartialEmojiConversionFailure
    :members:

.. autoexception:: discord.ext.commands.GuildStickerNotFound
    :members:

.. autoexception:: discord.ext.commands.ScheduledEventNotFound
    :members:

.. autoexception:: discord.ext.commands.SoundboardSoundNotFound
    :members:

.. autoexception:: discord.ext.commands.BadBoolArgument
    :members:

.. autoexception:: discord.ext.commands.RangeError
    :members:

.. autoexception:: discord.ext.commands.MissingPermissions
    :members:

.. autoexception:: discord.ext.commands.BotMissingPermissions
    :members:

.. autoexception:: discord.ext.commands.MissingRole
    :members:

.. autoexception:: discord.ext.commands.BotMissingRole
    :members:

.. autoexception:: discord.ext.commands.MissingAnyRole
    :members:

.. autoexception:: discord.ext.commands.BotMissingAnyRole
    :members:

.. autoexception:: discord.ext.commands.NSFWChannelRequired
    :members:

.. autoexception:: discord.ext.commands.FlagError
    :members:

.. autoexception:: discord.ext.commands.BadFlagArgument
    :members:

.. autoexception:: discord.ext.commands.MissingFlagArgument
    :members:

.. autoexception:: discord.ext.commands.TooManyFlags
    :members:

.. autoexception:: discord.ext.commands.MissingRequiredFlag
    :members:

.. autoexception:: discord.ext.commands.ExtensionError
    :members:

.. autoexception:: discord.ext.commands.ExtensionAlreadyLoaded
    :members:

.. autoexception:: discord.ext.commands.ExtensionNotLoaded
    :members:

.. autoexception:: discord.ext.commands.NoEntryPointError
    :members:

.. autoexception:: discord.ext.commands.ExtensionFailed
    :members:

.. autoexception:: discord.ext.commands.ExtensionNotFound
    :members:

.. autoexception:: discord.ext.commands.CommandRegistrationError
    :members:

.. autoexception:: discord.ext.commands.HybridCommandError
    :members:


Exception Hierarchy
~~~~~~~~~~~~~~~~~~~~~

.. exception_hierarchy::

    - :exc:`~.DiscordException`
        - :exc:`~.commands.CommandError`
            - :exc:`~.commands.ConversionError`
            - :exc:`~.commands.UserInputError`
                - :exc:`~.commands.MissingRequiredArgument`
                - :exc:`~.commands.MissingRequiredAttachment`
                - :exc:`~.commands.MissingRequiredSticker`
                - :exc:`~.commands.TooManyArguments`
                - :exc:`~.commands.BadArgument`
                    - :exc:`~.commands.MessageNotFound`
                    - :exc:`~.commands.MemberNotFound`
                    - :exc:`~.commands.GuildNotFound`
                    - :exc:`~.commands.UserNotFound`
                    - :exc:`~.commands.ChannelNotFound`
                    - :exc:`~.commands.ChannelNotReadable`
                    - :exc:`~.commands.BadColourArgument`
                    - :exc:`~.commands.RoleNotFound`
                    - :exc:`~.commands.BadInviteArgument`
                    - :exc:`~.commands.EmojiNotFound`
                    - :exc:`~.commands.GuildStickerNotFound`
                    - :exc:`~.commands.ScheduledEventNotFound`
                    - :exc:`~.commands.SoundboardSoundNotFound`
                    - :exc:`~.commands.PartialEmojiConversionFailure`
                    - :exc:`~.commands.BadBoolArgument`
                    - :exc:`~.commands.RangeError`
                    - :exc:`~.commands.ThreadNotFound`
                    - :exc:`~.commands.FlagError`
                        - :exc:`~.commands.BadFlagArgument`
                        - :exc:`~.commands.MissingFlagArgument`
                        - :exc:`~.commands.TooManyFlags`
                        - :exc:`~.commands.MissingRequiredFlag`
                - :exc:`~.commands.BadUnionArgument`
                - :exc:`~.commands.BadLiteralArgument`
                - :exc:`~.commands.ArgumentParsingError`
                    - :exc:`~.commands.UnexpectedQuoteError`
                    - :exc:`~.commands.InvalidEndOfQuotedStringError`
                    - :exc:`~.commands.ExpectedClosingQuoteError`
            - :exc:`~.commands.CommandNotFound`
            - :exc:`~.commands.CheckFailure`
                - :exc:`~.commands.CheckAnyFailure`
                - :exc:`~.commands.PrivateMessageOnly`
                - :exc:`~.commands.NoPrivateMessage`
                - :exc:`~.commands.NotOwner`
                - :exc:`~.commands.MissingPermissions`
                - :exc:`~.commands.BotMissingPermissions`
                - :exc:`~.commands.MissingRole`
                - :exc:`~.commands.BotMissingRole`
                - :exc:`~.commands.MissingAnyRole`
                - :exc:`~.commands.BotMissingAnyRole`
                - :exc:`~.commands.NSFWChannelRequired`
            - :exc:`~.commands.DisabledCommand`
            - :exc:`~.commands.CommandInvokeError`
            - :exc:`~.commands.CommandOnCooldown`
            - :exc:`~.commands.MaxConcurrencyReached`
            - :exc:`~.commands.HybridCommandError`
        - :exc:`~.commands.ExtensionError`
            - :exc:`~.commands.ExtensionAlreadyLoaded`
            - :exc:`~.commands.ExtensionNotLoaded`
            - :exc:`~.commands.NoEntryPointError`
            - :exc:`~.commands.ExtensionFailed`
            - :exc:`~.commands.ExtensionNotFound`
    - :exc:`~.ClientException`
        - :exc:`~.commands.CommandRegistrationError`
