.. currentmodule:: discord

API Reference
===============

The following section outlines the API of discord.py.

.. note::

    This module uses the Python logging module to log diagnostic and errors
    in an output independent way.  If the logging module is not configured,
    these logs will not be output anywhere.  See :ref:`logging_setup` for
    more information on how to set up and use the logging module with
    discord.py.

Version Related Info
---------------------

There are two main ways to query version information about the library. For guarantees, check :ref:`version_guarantees`.

.. data:: version_info

    A named tuple that is similar to :obj:`py:sys.version_info`.

    Just like :obj:`py:sys.version_info` the valid values for ``releaselevel`` are
    'alpha', 'beta', 'candidate' and 'final'.

.. data:: __version__

    A string representation of the version. e.g. ``'1.0.0rc1'``. This is based
    off of :pep:`440`.

Clients
--------

Client
~~~~~~~

.. attributetable:: Client

.. autoclass:: Client
    :members:
    :exclude-members: event

    .. automethod:: Client.event()
        :decorator:

AutoShardedClient
~~~~~~~~~~~~~~~~~~

.. attributetable:: AutoShardedClient

.. autoclass:: AutoShardedClient
    :members:

Application Info
------------------

AppInfo
~~~~~~~~

.. attributetable:: AppInfo

.. autoclass:: AppInfo()
    :members:

PartialAppInfo
~~~~~~~~~~~~~~~

.. attributetable:: PartialAppInfo

.. autoclass:: PartialAppInfo()
    :members:

AppInstallParams
~~~~~~~~~~~~~~~~

.. attributetable:: AppInstallParams

.. autoclass:: AppInstallParams()
    :members:

Team
~~~~~

.. attributetable:: Team

.. autoclass:: Team()
    :members:

TeamMember
~~~~~~~~~~~

.. attributetable:: TeamMember

.. autoclass:: TeamMember()
    :members:
    :inherited-members:

Voice Related
---------------

VoiceClient
~~~~~~~~~~~~

.. attributetable:: VoiceClient

.. autoclass:: VoiceClient()
    :members:
    :exclude-members: connect, on_voice_state_update, on_voice_server_update

VoiceProtocol
~~~~~~~~~~~~~~~

.. attributetable:: VoiceProtocol

.. autoclass:: VoiceProtocol
    :members:

AudioSource
~~~~~~~~~~~~

.. attributetable:: AudioSource

.. autoclass:: AudioSource
    :members:

PCMAudio
~~~~~~~~~

.. attributetable:: PCMAudio

.. autoclass:: PCMAudio
    :members:

FFmpegAudio
~~~~~~~~~~~~

.. attributetable:: FFmpegAudio

.. autoclass:: FFmpegAudio
    :members:

FFmpegPCMAudio
~~~~~~~~~~~~~~~

.. attributetable:: FFmpegPCMAudio

.. autoclass:: FFmpegPCMAudio
    :members:

FFmpegOpusAudio
~~~~~~~~~~~~~~~~

.. attributetable:: FFmpegOpusAudio

.. autoclass:: FFmpegOpusAudio
    :members:

PCMVolumeTransformer
~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: PCMVolumeTransformer

.. autoclass:: PCMVolumeTransformer
    :members:

Opus Library
~~~~~~~~~~~~~

.. autofunction:: discord.opus.load_opus

.. autofunction:: discord.opus.is_loaded

.. _discord-api-events:

Event Reference
---------------

This section outlines the different types of events listened by :class:`Client`.

There are two ways to register an event, the first way is through the use of
:meth:`Client.event`. The second way is through subclassing :class:`Client` and
overriding the specific events. For example: ::

    import discord

    class MyClient(discord.Client):
        async def on_message(self, message):
            if message.author == self.user:
                return

            if message.content.startswith('$hello'):
                await message.channel.send('Hello World!')


If an event handler raises an exception, :func:`on_error` will be called
to handle it, which defaults to logging the traceback and ignoring the exception.

.. warning::

    All the events must be a |coroutine_link|_. If they aren't, then you might get unexpected
    errors. In order to turn a function into a coroutine they must be ``async def``
    functions.

App Commands
~~~~~~~~~~~~~

.. function:: on_raw_app_command_permissions_update(payload)

    Called when application command permissions are updated.

    .. versionadded:: 2.0

    :param payload: The raw event payload data.
    :type payload: :class:`RawAppCommandPermissionsUpdateEvent`

.. function:: on_app_command_completion(interaction, command)

    Called when a :class:`app_commands.Command` or :class:`app_commands.ContextMenu` has
    successfully completed without error.

    .. versionadded:: 2.0

    :param interaction: The interaction of the command.
    :type interaction: :class:`Interaction`
    :param command: The command that completed successfully
    :type command: Union[:class:`app_commands.Command`, :class:`app_commands.ContextMenu`]

AutoMod
~~~~~~~~

.. function:: on_automod_rule_create(rule)

    Called when a :class:`AutoModRule` is created.
    You must have :attr:`~Permissions.manage_guild` to receive this.

    This requires :attr:`Intents.auto_moderation_configuration` to be enabled.

    .. versionadded:: 2.0

    :param rule: The rule that was created.
    :type rule: :class:`AutoModRule`

.. function:: on_automod_rule_update(rule)

    Called when a :class:`AutoModRule` is updated.
    You must have :attr:`~Permissions.manage_guild` to receive this.

    This requires :attr:`Intents.auto_moderation_configuration` to be enabled.

    .. versionadded:: 2.0

    :param rule: The rule that was updated.
    :type rule: :class:`AutoModRule`

.. function:: on_automod_rule_delete(rule)

    Called when a :class:`AutoModRule` is deleted.
    You must have :attr:`~Permissions.manage_guild` to receive this.

    This requires :attr:`Intents.auto_moderation_configuration` to be enabled.

    .. versionadded:: 2.0

    :param rule: The rule that was deleted.
    :type rule: :class:`AutoModRule`

.. function:: on_automod_action(execution)

    Called when a :class:`AutoModAction` is created/performed.
    You must have :attr:`~Permissions.manage_guild` to receive this.

    This requires :attr:`Intents.auto_moderation_execution` to be enabled.

    .. versionadded:: 2.0

    :param execution: The rule execution that was performed.
    :type execution: :class:`AutoModAction`

Channels
~~~~~~~~~

.. function:: on_guild_channel_delete(channel)
              on_guild_channel_create(channel)

    Called whenever a guild channel is deleted or created.

    Note that you can get the guild from :attr:`~abc.GuildChannel.guild`.

    This requires :attr:`Intents.guilds` to be enabled.

    :param channel: The guild channel that got created or deleted.
    :type channel: :class:`abc.GuildChannel`

.. function:: on_guild_channel_update(before, after)

    Called whenever a guild channel is updated. e.g. changed name, topic, permissions.

    This requires :attr:`Intents.guilds` to be enabled.

    :param before: The updated guild channel's old info.
    :type before: :class:`abc.GuildChannel`
    :param after: The updated guild channel's new info.
    :type after: :class:`abc.GuildChannel`

.. function:: on_guild_channel_pins_update(channel, last_pin)

    Called whenever a message is pinned or unpinned from a guild channel.

    This requires :attr:`Intents.guilds` to be enabled.

    :param channel: The guild channel that had its pins updated.
    :type channel: Union[:class:`abc.GuildChannel`, :class:`Thread`]
    :param last_pin: The latest message that was pinned as an aware datetime in UTC. Could be ``None``.
    :type last_pin: Optional[:class:`datetime.datetime`]

.. function:: on_private_channel_update(before, after)

    Called whenever a private group DM is updated. e.g. changed name or topic.

    This requires :attr:`Intents.messages` to be enabled.

    :param before: The updated group channel's old info.
    :type before: :class:`GroupChannel`
    :param after: The updated group channel's new info.
    :type after: :class:`GroupChannel`

.. function:: on_private_channel_pins_update(channel, last_pin)

    Called whenever a message is pinned or unpinned from a private channel.

    :param channel: The private channel that had its pins updated.
    :type channel: :class:`abc.PrivateChannel`
    :param last_pin: The latest message that was pinned as an aware datetime in UTC. Could be ``None``.
    :type last_pin: Optional[:class:`datetime.datetime`]

.. function:: on_typing(channel, user, when)

    Called when someone begins typing a message.

    The ``channel`` parameter can be a :class:`abc.Messageable` instance.
    Which could either be :class:`TextChannel`, :class:`GroupChannel`, or
    :class:`DMChannel`.

    If the ``channel`` is a :class:`TextChannel` then the ``user`` parameter
    is a :class:`Member`, otherwise it is a :class:`User`.

    If the channel or user could not be found in the internal cache this event
    will not be called, you may use :func:`on_raw_typing` instead.

    This requires :attr:`Intents.typing` to be enabled.

    :param channel: The location where the typing originated from.
    :type channel: :class:`abc.Messageable`
    :param user: The user that started typing.
    :type user: Union[:class:`User`, :class:`Member`]
    :param when: When the typing started as an aware datetime in UTC.
    :type when: :class:`datetime.datetime`

.. function:: on_raw_typing(payload)

    Called when someone begins typing a message. Unlike :func:`on_typing` this
    is called regardless of the channel and user being in the internal cache.

    This requires :attr:`Intents.typing` to be enabled.

    .. versionadded:: 2.0

    :param payload: The raw event payload data.
    :type payload: :class:`RawTypingEvent`

Connection
~~~~~~~~~~~

.. function:: on_connect()

    Called when the client has successfully connected to Discord. This is not
    the same as the client being fully prepared, see :func:`on_ready` for that.

    The warnings on :func:`on_ready` also apply.

.. function:: on_disconnect()

    Called when the client has disconnected from Discord, or a connection attempt to Discord has failed.
    This could happen either through the internet being disconnected, explicit calls to close,
    or Discord terminating the connection one way or the other.

    This function can be called many times without a corresponding :func:`on_connect` call.

.. function:: on_shard_connect(shard_id)

    Similar to :func:`on_connect` except used by :class:`AutoShardedClient`
    to denote when a particular shard ID has connected to Discord.

    .. versionadded:: 1.4

    :param shard_id: The shard ID that has connected.
    :type shard_id: :class:`int`


.. function:: on_shard_disconnect(shard_id)

    Similar to :func:`on_disconnect` except used by :class:`AutoShardedClient`
    to denote when a particular shard ID has disconnected from Discord.

    .. versionadded:: 1.4

    :param shard_id: The shard ID that has disconnected.
    :type shard_id: :class:`int`

Debug
~~~~~~

.. function:: on_error(event, *args, **kwargs)

    Usually when an event raises an uncaught exception, a traceback is
    logged to stderr and the exception is ignored. If you want to
    change this behaviour and handle the exception for whatever reason
    yourself, this event can be overridden. Which, when done, will
    suppress the default action of printing the traceback.

    The information of the exception raised and the exception itself can
    be retrieved with a standard call to :func:`sys.exc_info`.

    .. note::

        ``on_error`` will only be dispatched to :meth:`Client.event`.

        It will not be received by :meth:`Client.wait_for`, or, if used,
        :ref:`ext_commands_api_bot` listeners such as
        :meth:`~ext.commands.Bot.listen` or :meth:`~ext.commands.Cog.listener`.

    .. versionchanged:: 2.0

        The traceback is now logged rather than printed.

    :param event: The name of the event that raised the exception.
    :type event: :class:`str`

    :param args: The positional arguments for the event that raised the
        exception.
    :param kwargs: The keyword arguments for the event that raised the
        exception.

.. function:: on_socket_event_type(event_type)

    Called whenever a websocket event is received from the WebSocket.

    This is mainly useful for logging how many events you are receiving
    from the Discord gateway.

    .. versionadded:: 2.0

    :param event_type: The event type from Discord that is received, e.g. ``'READY'``.
    :type event_type: :class:`str`

.. function:: on_socket_raw_receive(msg)

    Called whenever a message is completely received from the WebSocket, before
    it's processed and parsed. This event is always dispatched when a
    complete message is received and the passed data is not parsed in any way.

    This is only really useful for grabbing the WebSocket stream and
    debugging purposes.

    This requires setting the ``enable_debug_events`` setting in the :class:`Client`.

    .. note::

        This is only for the messages received from the client
        WebSocket. The voice WebSocket will not trigger this event.

    :param msg: The message passed in from the WebSocket library.
    :type msg: :class:`str`

.. function:: on_socket_raw_send(payload)

    Called whenever a send operation is done on the WebSocket before the
    message is sent. The passed parameter is the message that is being
    sent to the WebSocket.

    This is only really useful for grabbing the WebSocket stream and
    debugging purposes.

    This requires setting the ``enable_debug_events`` setting in the :class:`Client`.

    .. note::

        This is only for the messages sent from the client
        WebSocket. The voice WebSocket will not trigger this event.

    :param payload: The message that is about to be passed on to the
                    WebSocket library. It can be :class:`bytes` to denote a binary
                    message or :class:`str` to denote a regular text message.
    :type payload: Union[:class:`bytes`, :class:`str`]


Entitlements
~~~~~~~~~~~~

.. function:: on_entitlement_create(entitlement)

    Called when a user subscribes to a SKU.

    .. versionadded:: 2.4

    :param entitlement: The entitlement that was created.
    :type entitlement: :class:`Entitlement`

.. function:: on_entitlement_update(entitlement)

    Called when a user updates their subscription to a SKU. This is usually called when
    the user renews or cancels their subscription.

    .. versionadded:: 2.4

    :param entitlement: The entitlement that was updated.
    :type entitlement: :class:`Entitlement`

.. function:: on_entitlement_delete(entitlement)

    Called when a users subscription to a SKU is cancelled. This is typically only called when:

    - Discord issues a refund for the subscription.
    - Discord removes an entitlement from a user.

    .. warning::

        This event won't be called if the user cancels their subscription manually, instead
        :func:`on_entitlement_update` will be called with :attr:`Entitlement.ends_at` set to the end of the
        current billing period.

    .. versionadded:: 2.4

    :param entitlement: The entitlement that was deleted.
    :type entitlement: :class:`Entitlement`


Gateway
~~~~~~~~

.. function:: on_ready()

    Called when the client is done preparing the data received from Discord. Usually after login is successful
    and the :attr:`Client.guilds` and co. are filled up.

    .. warning::

        This function is not guaranteed to be the first event called.
        Likewise, this function is **not** guaranteed to only be called
        once. This library implements reconnection logic and thus will
        end up calling this event whenever a RESUME request fails.

.. function:: on_resumed()

    Called when the client has resumed a session.

.. function:: on_shard_ready(shard_id)

    Similar to :func:`on_ready` except used by :class:`AutoShardedClient`
    to denote when a particular shard ID has become ready.

    :param shard_id: The shard ID that is ready.
    :type shard_id: :class:`int`


.. function:: on_shard_resumed(shard_id)

    Similar to :func:`on_resumed` except used by :class:`AutoShardedClient`
    to denote when a particular shard ID has resumed a session.

    .. versionadded:: 1.4

    :param shard_id: The shard ID that has resumed.
    :type shard_id: :class:`int`

Guilds
~~~~~~~

.. function:: on_guild_available(guild)
              on_guild_unavailable(guild)

    Called when a guild becomes available or unavailable. The guild must have
    existed in the :attr:`Client.guilds` cache.

    This requires :attr:`Intents.guilds` to be enabled.

    :param guild: The :class:`Guild` that has changed availability.

.. function:: on_guild_join(guild)

    Called when a :class:`Guild` is either created by the :class:`Client` or when the
    :class:`Client` joins a guild.

    This requires :attr:`Intents.guilds` to be enabled.

    :param guild: The guild that was joined.
    :type guild: :class:`Guild`

.. function:: on_guild_remove(guild)

    Called when a :class:`Guild` is removed from the :class:`Client`.

    This happens through, but not limited to, these circumstances:

    - The client got banned.
    - The client got kicked.
    - The client left the guild.
    - The client or the guild owner deleted the guild.

    In order for this event to be invoked then the :class:`Client` must have
    been part of the guild to begin with. (i.e. it is part of :attr:`Client.guilds`)

    This requires :attr:`Intents.guilds` to be enabled.

    :param guild: The guild that got removed.
    :type guild: :class:`Guild`

.. function:: on_guild_update(before, after)

    Called when a :class:`Guild` updates, for example:

    - Changed name
    - Changed AFK channel
    - Changed AFK timeout
    - etc

    This requires :attr:`Intents.guilds` to be enabled.

    :param before: The guild prior to being updated.
    :type before: :class:`Guild`
    :param after: The guild after being updated.
    :type after: :class:`Guild`

.. function:: on_guild_emojis_update(guild, before, after)

    Called when a :class:`Guild` adds or removes :class:`Emoji`.

    This requires :attr:`Intents.emojis_and_stickers` to be enabled.

    :param guild: The guild who got their emojis updated.
    :type guild: :class:`Guild`
    :param before: A list of emojis before the update.
    :type before: Sequence[:class:`Emoji`]
    :param after: A list of emojis after the update.
    :type after: Sequence[:class:`Emoji`]

.. function:: on_guild_stickers_update(guild, before, after)

    Called when a :class:`Guild` updates its stickers.

    This requires :attr:`Intents.emojis_and_stickers` to be enabled.

    .. versionadded:: 2.0

    :param guild: The guild who got their stickers updated.
    :type guild: :class:`Guild`
    :param before: A list of stickers before the update.
    :type before: Sequence[:class:`GuildSticker`]
    :param after: A list of stickers after the update.
    :type after: Sequence[:class:`GuildSticker`]

.. function:: on_audit_log_entry_create(entry)

    Called when a :class:`Guild` gets a new audit log entry.
    You must have :attr:`~Permissions.view_audit_log` to receive this.

    This requires :attr:`Intents.moderation` to be enabled.

    .. versionadded:: 2.2

    .. warning::

        Audit log entries received through the gateway are subject to data retrieval
        from cache rather than REST. This means that some data might not be present
        when you expect it to be. For example, the :attr:`AuditLogEntry.target`
        attribute will usually be a :class:`discord.Object` and the
        :attr:`AuditLogEntry.user` attribute will depend on user and member cache.

        To get the user ID of entry, :attr:`AuditLogEntry.user_id` can be used instead.

    :param entry: The audit log entry that was created.
    :type entry: :class:`AuditLogEntry`

.. function:: on_invite_create(invite)

    Called when an :class:`Invite` is created.
    You must have :attr:`~Permissions.manage_channels` to receive this.

    .. versionadded:: 1.3

    .. note::

        There is a rare possibility that the :attr:`Invite.guild` and :attr:`Invite.channel`
        attributes will be of :class:`Object` rather than the respective models.

    This requires :attr:`Intents.invites` to be enabled.

    :param invite: The invite that was created.
    :type invite: :class:`Invite`

.. function:: on_invite_delete(invite)

    Called when an :class:`Invite` is deleted.
    You must have :attr:`~Permissions.manage_channels` to receive this.

    .. versionadded:: 1.3

    .. note::

        There is a rare possibility that the :attr:`Invite.guild` and :attr:`Invite.channel`
        attributes will be of :class:`Object` rather than the respective models.

        Outside of those two attributes, the only other attribute guaranteed to be
        filled by the Discord gateway for this event is :attr:`Invite.code`.

    This requires :attr:`Intents.invites` to be enabled.

    :param invite: The invite that was deleted.
    :type invite: :class:`Invite`


Integrations
~~~~~~~~~~~~~

.. function:: on_integration_create(integration)

    Called when an integration is created.

    This requires :attr:`Intents.integrations` to be enabled.

    .. versionadded:: 2.0

    :param integration: The integration that was created.
    :type integration: :class:`Integration`

.. function:: on_integration_update(integration)

    Called when an integration is updated.

    This requires :attr:`Intents.integrations` to be enabled.

    .. versionadded:: 2.0

    :param integration: The integration that was updated.
    :type integration: :class:`Integration`

.. function:: on_guild_integrations_update(guild)

    Called whenever an integration is created, modified, or removed from a guild.

    This requires :attr:`Intents.integrations` to be enabled.

    .. versionadded:: 1.4

    :param guild: The guild that had its integrations updated.
    :type guild: :class:`Guild`

.. function:: on_webhooks_update(channel)

    Called whenever a webhook is created, modified, or removed from a guild channel.

    This requires :attr:`Intents.webhooks` to be enabled.

    :param channel: The channel that had its webhooks updated.
    :type channel: :class:`abc.GuildChannel`

.. function:: on_raw_integration_delete(payload)

    Called when an integration is deleted.

    This requires :attr:`Intents.integrations` to be enabled.

    .. versionadded:: 2.0

    :param payload: The raw event payload data.
    :type payload: :class:`RawIntegrationDeleteEvent`

Interactions
~~~~~~~~~~~~~

.. function:: on_interaction(interaction)

    Called when an interaction happened.

    This currently happens due to slash command invocations or components being used.

    .. warning::

        This is a low level function that is not generally meant to be used.
        If you are working with components, consider using the callbacks associated
        with the :class:`~discord.ui.View` instead as it provides a nicer user experience.

    .. versionadded:: 2.0

    :param interaction: The interaction data.
    :type interaction: :class:`Interaction`

Members
~~~~~~~~

.. function:: on_member_join(member)

    Called when a :class:`Member` joins a :class:`Guild`.

    This requires :attr:`Intents.members` to be enabled.

    :param member: The member who joined.
    :type member: :class:`Member`

.. function:: on_member_remove(member)

    Called when a :class:`Member` leaves a :class:`Guild`.

    If the guild or member could not be found in the internal cache this event
    will not be called, you may use :func:`on_raw_member_remove` instead.

    This requires :attr:`Intents.members` to be enabled.

    :param member: The member who left.
    :type member: :class:`Member`

.. function:: on_raw_member_remove(payload)

    Called when a :class:`Member` leaves a :class:`Guild`.

    Unlike :func:`on_member_remove`
    this is called regardless of the guild or member being in the internal cache.

    This requires :attr:`Intents.members` to be enabled.

    .. versionadded:: 2.0

    :param payload: The raw event payload data.
    :type payload: :class:`RawMemberRemoveEvent`

.. function:: on_member_update(before, after)

    Called when a :class:`Member` updates their profile.

    This is called when one or more of the following things change:

    - nickname
    - roles
    - pending
    - timeout
    - guild avatar
    - flags

    Due to a Discord limitation, this event is not dispatched when a member's timeout expires.

    This requires :attr:`Intents.members` to be enabled.

    :param before: The updated member's old info.
    :type before: :class:`Member`
    :param after: The updated member's updated info.
    :type after: :class:`Member`

.. function:: on_user_update(before, after)

    Called when a :class:`User` updates their profile.

    This is called when one or more of the following things change:

    - avatar
    - username
    - discriminator

    This requires :attr:`Intents.members` to be enabled.

    :param before: The updated user's old info.
    :type before: :class:`User`
    :param after: The updated user's updated info.
    :type after: :class:`User`

.. function:: on_member_ban(guild, user)

    Called when a user gets banned from a :class:`Guild`.

    This requires :attr:`Intents.moderation` to be enabled.

    :param guild: The guild the user got banned from.
    :type guild: :class:`Guild`
    :param user: The user that got banned.
                 Can be either :class:`User` or :class:`Member` depending if
                 the user was in the guild or not at the time of removal.
    :type user: Union[:class:`User`, :class:`Member`]

.. function:: on_member_unban(guild, user)

    Called when a :class:`User` gets unbanned from a :class:`Guild`.

    This requires :attr:`Intents.moderation` to be enabled.

    :param guild: The guild the user got unbanned from.
    :type guild: :class:`Guild`
    :param user: The user that got unbanned.
    :type user: :class:`User`

.. function:: on_presence_update(before, after)

    Called when a :class:`Member` updates their presence.

    This is called when one or more of the following things change:

    - status
    - activity

    This requires :attr:`Intents.presences` and :attr:`Intents.members` to be enabled.

    .. versionadded:: 2.0

    :param before: The updated member's old info.
    :type before: :class:`Member`
    :param after: The updated member's updated info.
    :type after: :class:`Member`

.. function:: on_raw_presence_update(payload)

    Called when a :class:`Member` updates their presence.
    
    This requires :attr:`Intents.presences` to be enabled.

    Unlike :func:`on_presence_update`, when enabled, this is called regardless of the state of internal guild 
    and member caches, and **does not** provide a comparison between the previous and updated states of the :class:`Member`.

    .. important::

        By default, this event is only dispatched when :attr:`Intents.presences` is enabled **and** :attr:`Intents.members` 
        is disabled.

        You can manually override this behaviour by setting the **enable_raw_presences** flag in the :class:`Client`,
        however :attr:`Intents.presences` is always required for this event to work.
    
    .. versionadded:: 2.5

    :param payload: The raw presence update event model.
    :type payload: :class:`RawPresenceUpdateEvent`
        

Messages
~~~~~~~~~

.. function:: on_message(message)

    Called when a :class:`Message` is created and sent.

    This requires :attr:`Intents.messages` to be enabled.

    .. warning::

        Your bot's own messages and private messages are sent through this
        event. This can lead cases of 'recursion' depending on how your bot was
        programmed. If you want the bot to not reply to itself, consider
        checking the user IDs. Note that :class:`~ext.commands.Bot` does not
        have this problem.

    :param message: The current message.
    :type message: :class:`Message`

.. function:: on_message_edit(before, after)

    Called when a :class:`Message` receives an update event. If the message is not found
    in the internal message cache, then these events will not be called.
    Messages might not be in cache if the message is too old
    or the client is participating in high traffic guilds.

    If this occurs increase the :class:`max_messages <Client>` parameter
    or use the :func:`on_raw_message_edit` event instead.

    The following non-exhaustive cases trigger this event:

    - A message has been pinned or unpinned.
    - The message content has been changed.
    - The message has received an embed.

        - For performance reasons, the embed server does not do this in a "consistent" manner.

    - The message's embeds were suppressed or unsuppressed.
    - A call message has received an update to its participants or ending time.

    This requires :attr:`Intents.messages` to be enabled.

    :param before: The previous version of the message.
    :type before: :class:`Message`
    :param after: The current version of the message.
    :type after: :class:`Message`

.. function:: on_message_delete(message)

    Called when a message is deleted. If the message is not found in the
    internal message cache, then this event will not be called.
    Messages might not be in cache if the message is too old
    or the client is participating in high traffic guilds.

    If this occurs increase the :class:`max_messages <Client>` parameter
    or use the :func:`on_raw_message_delete` event instead.

    This requires :attr:`Intents.messages` to be enabled.

    :param message: The deleted message.
    :type message: :class:`Message`

.. function:: on_bulk_message_delete(messages)

    Called when messages are bulk deleted. If none of the messages deleted
    are found in the internal message cache, then this event will not be called.
    If individual messages were not found in the internal message cache,
    this event will still be called, but the messages not found will not be included in
    the messages list. Messages might not be in cache if the message is too old
    or the client is participating in high traffic guilds.

    If this occurs increase the :class:`max_messages <Client>` parameter
    or use the :func:`on_raw_bulk_message_delete` event instead.

    This requires :attr:`Intents.messages` to be enabled.

    :param messages: The messages that have been deleted.
    :type messages: List[:class:`Message`]

.. function:: on_raw_message_edit(payload)

    Called when a message is edited. Unlike :func:`on_message_edit`, this is called
    regardless of the state of the internal message cache.

    If the message is found in the message cache,
    it can be accessed via :attr:`RawMessageUpdateEvent.cached_message`. The cached message represents
    the message before it has been edited. For example, if the content of a message is modified and
    triggers the :func:`on_raw_message_edit` coroutine, the :attr:`RawMessageUpdateEvent.cached_message`
    will return a :class:`Message` object that represents the message before the content was modified.

    Due to the inherently raw nature of this event, the data parameter coincides with
    the raw data given by the :ddocs:`gateway <topics/gateway-events#message-update>`.

    Since the data payload can be partial, care must be taken when accessing stuff in the dictionary.
    One example of a common case of partial data is when the ``'content'`` key is inaccessible. This
    denotes an "embed" only edit, which is an edit in which only the embeds are updated by the Discord
    embed server.

    This requires :attr:`Intents.messages` to be enabled.

    :param payload: The raw event payload data.
    :type payload: :class:`RawMessageUpdateEvent`


.. function:: on_raw_message_delete(payload)

    Called when a message is deleted. Unlike :func:`on_message_delete`, this is
    called regardless of the message being in the internal message cache or not.

    If the message is found in the message cache,
    it can be accessed via :attr:`RawMessageDeleteEvent.cached_message`

    This requires :attr:`Intents.messages` to be enabled.

    :param payload: The raw event payload data.
    :type payload: :class:`RawMessageDeleteEvent`

.. function:: on_raw_bulk_message_delete(payload)

    Called when a bulk delete is triggered. Unlike :func:`on_bulk_message_delete`, this is
    called regardless of the messages being in the internal message cache or not.

    If the messages are found in the message cache,
    they can be accessed via :attr:`RawBulkMessageDeleteEvent.cached_messages`

    This requires :attr:`Intents.messages` to be enabled.

    :param payload: The raw event payload data.
    :type payload: :class:`RawBulkMessageDeleteEvent`

Polls
~~~~~~

.. function:: on_poll_vote_add(user, answer)
              on_poll_vote_remove(user, answer)

    Called when a :class:`Poll` gains or loses a vote. If the ``user`` or ``answer``'s poll
    parent message are not cached then this event will not be called.

    This requires :attr:`Intents.message_content` and :attr:`Intents.polls` to be enabled.

    .. note::

        If the poll allows multiple answers and the user removes or adds multiple votes, this
        event will be called as many times as votes that are added or removed.

    .. versionadded:: 2.4

    :param user: The user that performed the action.
    :type user: Union[:class:`User`, :class:`Member`]
    :param answer: The answer the user voted or removed their vote from.
    :type answer: :class:`PollAnswer`

.. function:: on_raw_poll_vote_add(payload)
              on_raw_poll_vote_remove(payload)

    Called when a :class:`Poll` gains or loses a vote. Unlike :func:`on_poll_vote_add` and :func:`on_poll_vote_remove`
    this is called regardless of the state of the internal user and message cache.

    This requires :attr:`Intents.message_content` and :attr:`Intents.polls` to be enabled.

    .. note::

        If the poll allows multiple answers and the user removes or adds multiple votes, this
        event will be called as many times as votes that are added or removed.

    .. versionadded:: 2.4

    :param payload: The raw event payload data.
    :type payload: :class:`RawPollVoteActionEvent`

Reactions
~~~~~~~~~~

.. function:: on_reaction_add(reaction, user)

    Called when a message has a reaction added to it. Similar to :func:`on_message_edit`,
    if the message is not found in the internal message cache, then this
    event will not be called. Consider using :func:`on_raw_reaction_add` instead.

    .. note::

        To get the :class:`Message` being reacted, access it via :attr:`Reaction.message`.

    This requires :attr:`Intents.reactions` to be enabled.

    .. note::

        This doesn't require :attr:`Intents.members` within a guild context,
        but due to Discord not providing updated user information in a direct message
        it's required for direct messages to receive this event.
        Consider using :func:`on_raw_reaction_add` if you need this and do not otherwise want
        to enable the members intent.

    .. warning::

        This event does not have a way of differentiating whether a reaction is a
        burst reaction (also known as "super reaction") or not. If you need this,
        consider using :func:`on_raw_reaction_add` instead.

    :param reaction: The current state of the reaction.
    :type reaction: :class:`Reaction`
    :param user: The user who added the reaction.
    :type user: Union[:class:`Member`, :class:`User`]

.. function:: on_reaction_remove(reaction, user)

    Called when a message has a reaction removed from it. Similar to on_message_edit,
    if the message is not found in the internal message cache, then this event
    will not be called.

    .. note::

        To get the message being reacted, access it via :attr:`Reaction.message`.

    This requires both :attr:`Intents.reactions` and :attr:`Intents.members` to be enabled.

    .. note::

        Consider using :func:`on_raw_reaction_remove` if you need this and do not want
        to enable the members intent.

    .. warning::

        This event does not have a way of differentiating whether a reaction is a
        burst reaction (also known as "super reaction") or not. If you need this,
        consider using :func:`on_raw_reaction_remove` instead.

    :param reaction: The current state of the reaction.
    :type reaction: :class:`Reaction`
    :param user: The user whose reaction was removed.
    :type user: Union[:class:`Member`, :class:`User`]

.. function:: on_reaction_clear(message, reactions)

    Called when a message has all its reactions removed from it. Similar to :func:`on_message_edit`,
    if the message is not found in the internal message cache, then this event
    will not be called. Consider using :func:`on_raw_reaction_clear` instead.

    This requires :attr:`Intents.reactions` to be enabled.

    :param message: The message that had its reactions cleared.
    :type message: :class:`Message`
    :param reactions: The reactions that were removed.
    :type reactions: List[:class:`Reaction`]

.. function:: on_reaction_clear_emoji(reaction)

    Called when a message has a specific reaction removed from it. Similar to :func:`on_message_edit`,
    if the message is not found in the internal message cache, then this event
    will not be called. Consider using :func:`on_raw_reaction_clear_emoji` instead.

    This requires :attr:`Intents.reactions` to be enabled.

    .. versionadded:: 1.3

    :param reaction: The reaction that got cleared.
    :type reaction: :class:`Reaction`


.. function:: on_raw_reaction_add(payload)

    Called when a message has a reaction added. Unlike :func:`on_reaction_add`, this is
    called regardless of the state of the internal message cache.

    This requires :attr:`Intents.reactions` to be enabled.

    :param payload: The raw event payload data.
    :type payload: :class:`RawReactionActionEvent`

.. function:: on_raw_reaction_remove(payload)

    Called when a message has a reaction removed. Unlike :func:`on_reaction_remove`, this is
    called regardless of the state of the internal message cache.

    This requires :attr:`Intents.reactions` to be enabled.

    :param payload: The raw event payload data.
    :type payload: :class:`RawReactionActionEvent`

.. function:: on_raw_reaction_clear(payload)

    Called when a message has all its reactions removed. Unlike :func:`on_reaction_clear`,
    this is called regardless of the state of the internal message cache.

    This requires :attr:`Intents.reactions` to be enabled.

    :param payload: The raw event payload data.
    :type payload: :class:`RawReactionClearEvent`

.. function:: on_raw_reaction_clear_emoji(payload)

    Called when a message has a specific reaction removed from it. Unlike :func:`on_reaction_clear_emoji` this is called
    regardless of the state of the internal message cache.

    This requires :attr:`Intents.reactions` to be enabled.

    .. versionadded:: 1.3

    :param payload: The raw event payload data.
    :type payload: :class:`RawReactionClearEmojiEvent`


Roles
~~~~~~

.. function:: on_guild_role_create(role)
              on_guild_role_delete(role)

    Called when a :class:`Guild` creates or deletes a new :class:`Role`.

    To get the guild it belongs to, use :attr:`Role.guild`.

    This requires :attr:`Intents.guilds` to be enabled.

    :param role: The role that was created or deleted.
    :type role: :class:`Role`

.. function:: on_guild_role_update(before, after)

    Called when a :class:`Role` is changed guild-wide.

    This requires :attr:`Intents.guilds` to be enabled.

    :param before: The updated role's old info.
    :type before: :class:`Role`
    :param after: The updated role's updated info.
    :type after: :class:`Role`


Scheduled Events
~~~~~~~~~~~~~~~~~

.. function:: on_scheduled_event_create(event)
              on_scheduled_event_delete(event)

    Called when a :class:`ScheduledEvent` is created or deleted.

    This requires :attr:`Intents.guild_scheduled_events` to be enabled.

    .. versionadded:: 2.0

    :param event: The scheduled event that was created or deleted.
    :type event: :class:`ScheduledEvent`

.. function:: on_scheduled_event_update(before, after)

    Called when a :class:`ScheduledEvent` is updated.

    This requires :attr:`Intents.guild_scheduled_events` to be enabled.

    The following, but not limited to, examples illustrate when this event is called:

    - The scheduled start/end times are changed.
    - The channel is changed.
    - The description is changed.
    - The status is changed.
    - The image is changed.

    .. versionadded:: 2.0

    :param before: The scheduled event before the update.
    :type before: :class:`ScheduledEvent`
    :param after: The scheduled event after the update.
    :type after: :class:`ScheduledEvent`

.. function:: on_scheduled_event_user_add(event, user)
              on_scheduled_event_user_remove(event, user)

    Called when a user is added or removed from a :class:`ScheduledEvent`.

    This requires :attr:`Intents.guild_scheduled_events` to be enabled.

    .. versionadded:: 2.0

    :param event: The scheduled event that the user was added or removed from.
    :type event: :class:`ScheduledEvent`
    :param user: The user that was added or removed.
    :type user: :class:`User`


Soundboard
~~~~~~~~~~~

.. function:: on_soundboard_sound_create(sound)
              on_soundboard_sound_delete(sound)

    Called when a :class:`SoundboardSound` is created or deleted.

    .. versionadded:: 2.5

    :param sound: The soundboard sound that was created or deleted.
    :type sound: :class:`SoundboardSound`

.. function:: on_soundboard_sound_update(before, after)

    Called when a :class:`SoundboardSound` is updated.

    The following examples illustrate when this event is called:

    - The name is changed.
    - The emoji is changed.
    - The volume is changed.

    .. versionadded:: 2.5

    :param sound: The soundboard sound that was updated.
    :type sound: :class:`SoundboardSound`


Stages
~~~~~~~

.. function:: on_stage_instance_create(stage_instance)
              on_stage_instance_delete(stage_instance)

    Called when a :class:`StageInstance` is created or deleted for a :class:`StageChannel`.

    .. versionadded:: 2.0

    :param stage_instance: The stage instance that was created or deleted.
    :type stage_instance: :class:`StageInstance`

.. function:: on_stage_instance_update(before, after)

    Called when a :class:`StageInstance` is updated.

    The following, but not limited to, examples illustrate when this event is called:

    - The topic is changed.
    - The privacy level is changed.

    .. versionadded:: 2.0

    :param before: The stage instance before the update.
    :type before: :class:`StageInstance`
    :param after: The stage instance after the update.
    :type after: :class:`StageInstance`


Subscriptions
~~~~~~~~~~~~~

.. function:: on_subscription_create(subscription)

    Called when a subscription is created.

    .. versionadded:: 2.5

    :param subscription: The subscription that was created.
    :type subscription: :class:`Subscription`

.. function:: on_subscription_update(subscription)

    Called when a subscription is updated.

    .. versionadded:: 2.5

    :param subscription: The subscription that was updated.
    :type subscription: :class:`Subscription`

.. function:: on_subscription_delete(subscription)

    Called when a subscription is deleted.

    .. versionadded:: 2.5

    :param subscription: The subscription that was deleted.
    :type subscription: :class:`Subscription`

Threads
~~~~~~~~

.. function:: on_thread_create(thread)

    Called whenever a thread is created.

    Note that you can get the guild from :attr:`Thread.guild`.

    This requires :attr:`Intents.guilds` to be enabled.

    .. versionadded:: 2.0

    :param thread: The thread that was created.
    :type thread: :class:`Thread`

.. function:: on_thread_join(thread)

    Called whenever a thread is joined.

    Note that you can get the guild from :attr:`Thread.guild`.

    This requires :attr:`Intents.guilds` to be enabled.

    .. versionadded:: 2.0

    :param thread: The thread that got joined.
    :type thread: :class:`Thread`

.. function:: on_thread_update(before, after)

    Called whenever a thread is updated. If the thread could
    not be found in the internal cache this event will not be called.
    Threads will not be in the cache if they are archived.

    If you need this information use :func:`on_raw_thread_update` instead.

    This requires :attr:`Intents.guilds` to be enabled.

    .. versionadded:: 2.0

    :param before: The updated thread's old info.
    :type before: :class:`Thread`
    :param after: The updated thread's new info.
    :type after: :class:`Thread`

.. function:: on_thread_remove(thread)

    Called whenever a thread is removed. This is different from a thread being deleted.

    Note that you can get the guild from :attr:`Thread.guild`.

    This requires :attr:`Intents.guilds` to be enabled.

    .. warning::

        Due to technical limitations, this event might not be called
        as soon as one expects. Since the library tracks thread membership
        locally, the API only sends updated thread membership status upon being
        synced by joining a thread.

    .. versionadded:: 2.0

    :param thread: The thread that got removed.
    :type thread: :class:`Thread`

.. function:: on_thread_delete(thread)

    Called whenever a thread is deleted. If the thread could
    not be found in the internal cache this event will not be called.
    Threads will not be in the cache if they are archived.

    If you need this information use :func:`on_raw_thread_delete` instead.

    Note that you can get the guild from :attr:`Thread.guild`.

    This requires :attr:`Intents.guilds` to be enabled.

    .. versionadded:: 2.0

    :param thread: The thread that got deleted.
    :type thread: :class:`Thread`

.. function:: on_raw_thread_update(payload)

    Called whenever a thread is updated. Unlike :func:`on_thread_update` this
    is called regardless of the thread being in the internal thread cache or not.

    This requires :attr:`Intents.guilds` to be enabled.

    .. versionadded:: 2.0

    :param payload: The raw event payload data.
    :type payload: :class:`RawThreadUpdateEvent`

.. function:: on_raw_thread_delete(payload)

    Called whenever a thread is deleted. Unlike :func:`on_thread_delete` this
    is called regardless of the thread being in the internal thread cache or not.

    This requires :attr:`Intents.guilds` to be enabled.

    .. versionadded:: 2.0

    :param payload: The raw event payload data.
    :type payload: :class:`RawThreadDeleteEvent`

.. function:: on_thread_member_join(member)
              on_thread_member_remove(member)

    Called when a :class:`ThreadMember` leaves or joins a :class:`Thread`.

    You can get the thread a member belongs in by accessing :attr:`ThreadMember.thread`.

    This requires :attr:`Intents.members` to be enabled.

    .. versionadded:: 2.0

    :param member: The member who joined or left.
    :type member: :class:`ThreadMember`

.. function:: on_raw_thread_member_remove(payload)

    Called when a :class:`ThreadMember` leaves a :class:`Thread`. Unlike :func:`on_thread_member_remove` this
    is called regardless of the member being in the internal thread's members cache or not.

    This requires :attr:`Intents.members` to be enabled.

    .. versionadded:: 2.0

    :param payload: The raw event payload data.
    :type payload: :class:`RawThreadMembersUpdate`

Voice
~~~~~~

.. function:: on_voice_state_update(member, before, after)

    Called when a :class:`Member` changes their :class:`VoiceState`.

    The following, but not limited to, examples illustrate when this event is called:

    - A member joins a voice or stage channel.
    - A member leaves a voice or stage channel.
    - A member is muted or deafened by their own accord.
    - A member is muted or deafened by a guild administrator.

    This requires :attr:`Intents.voice_states` to be enabled.

    :param member: The member whose voice states changed.
    :type member: :class:`Member`
    :param before: The voice state prior to the changes.
    :type before: :class:`VoiceState`
    :param after: The voice state after the changes.
    :type after: :class:`VoiceState`

.. function:: on_voice_channel_effect(effect)

    Called when a :class:`Member` sends a :class:`VoiceChannelEffect` in a voice channel the bot is in.

    This requires :attr:`Intents.voice_states` to be enabled.

    .. versionadded:: 2.5

    :param effect: The effect that is sent.
    :type effect: :class:`VoiceChannelEffect`

.. _discord-api-utils:

Utility Functions
-----------------

.. autofunction:: discord.utils.find

.. autofunction:: discord.utils.get

.. autofunction:: discord.utils.setup_logging

.. autofunction:: discord.utils.maybe_coroutine

.. autofunction:: discord.utils.snowflake_time

.. autofunction:: discord.utils.time_snowflake

.. autofunction:: discord.utils.oauth_url

.. autofunction:: discord.utils.remove_markdown

.. autofunction:: discord.utils.escape_markdown

.. autofunction:: discord.utils.escape_mentions

.. class:: ResolvedInvite

    A data class which represents a resolved invite returned from :func:`discord.utils.resolve_invite`.

    .. attribute:: code

        The invite code.

        :type: :class:`str`

    ..  attribute:: event

        The id of the scheduled event that the invite refers to.

        :type: Optional[:class:`int`]

.. autofunction:: discord.utils.resolve_invite

.. autofunction:: discord.utils.resolve_template

.. autofunction:: discord.utils.sleep_until

.. autofunction:: discord.utils.utcnow

.. autofunction:: discord.utils.format_dt

.. autofunction:: discord.utils.as_chunks

.. data:: MISSING
    :module: discord.utils

    A type safe sentinel used in the library to represent something as missing. Used to distinguish from ``None`` values.

    .. versionadded:: 2.0

.. _discord-api-enums:

Enumerations
-------------

The API provides some enumerations for certain types of strings to avoid the API
from being stringly typed in case the strings change in the future.

All enumerations are subclasses of an internal class which mimics the behaviour
of :class:`enum.Enum`.

.. class:: ChannelType

    Specifies the type of channel.

    .. attribute:: text

        A text channel.
    .. attribute:: voice

        A voice channel.
    .. attribute:: private

        A private text channel. Also called a direct message.
    .. attribute:: group

        A private group text channel.
    .. attribute:: category

        A category channel.
    .. attribute:: news

        A guild news channel.

    .. attribute:: stage_voice

        A guild stage voice channel.

        .. versionadded:: 1.7

    .. attribute:: news_thread

        A news thread

        .. versionadded:: 2.0

    .. attribute:: public_thread

        A public thread

        .. versionadded:: 2.0

    .. attribute:: private_thread

        A private thread

        .. versionadded:: 2.0

    .. attribute:: forum

        A forum channel.

        .. versionadded:: 2.0

    .. attribute:: media

        A media channel.

        .. versionadded:: 2.4

.. class:: MessageType

    Specifies the type of :class:`Message`. This is used to denote if a message
    is to be interpreted as a system message or a regular message.

    .. container:: operations

      .. describe:: x == y

          Checks if two messages are equal.
      .. describe:: x != y

          Checks if two messages are not equal.

    .. attribute:: default

        The default message type. This is the same as regular messages.
    .. attribute:: recipient_add

        The system message when a user is added to a group private
        message or a thread.
    .. attribute:: recipient_remove

        The system message when a user is removed from a group private
        message or a thread.
    .. attribute:: call

        The system message denoting call state, e.g. missed call, started call,
        etc.
    .. attribute:: channel_name_change

        The system message denoting that a channel's name has been changed.
    .. attribute:: channel_icon_change

        The system message denoting that a channel's icon has been changed.
    .. attribute:: pins_add

        The system message denoting that a pinned message has been added to a channel.
    .. attribute:: new_member

        The system message denoting that a new member has joined a Guild.

    .. attribute:: premium_guild_subscription

        The system message denoting that a member has "nitro boosted" a guild.
    .. attribute:: premium_guild_tier_1

        The system message denoting that a member has "nitro boosted" a guild
        and it achieved level 1.
    .. attribute:: premium_guild_tier_2

        The system message denoting that a member has "nitro boosted" a guild
        and it achieved level 2.
    .. attribute:: premium_guild_tier_3

        The system message denoting that a member has "nitro boosted" a guild
        and it achieved level 3.
    .. attribute:: channel_follow_add

        The system message denoting that an announcement channel has been followed.

        .. versionadded:: 1.3
    .. attribute:: guild_stream

        The system message denoting that a member is streaming in the guild.

        .. versionadded:: 1.7
    .. attribute:: guild_discovery_disqualified

        The system message denoting that the guild is no longer eligible for Server
        Discovery.

        .. versionadded:: 1.7
    .. attribute:: guild_discovery_requalified

        The system message denoting that the guild has become eligible again for Server
        Discovery.

        .. versionadded:: 1.7
    .. attribute:: guild_discovery_grace_period_initial_warning

        The system message denoting that the guild has failed to meet the Server
        Discovery requirements for one week.

        .. versionadded:: 1.7
    .. attribute:: guild_discovery_grace_period_final_warning

        The system message denoting that the guild has failed to meet the Server
        Discovery requirements for 3 weeks in a row.

        .. versionadded:: 1.7
    .. attribute:: thread_created

        The system message denoting that a thread has been created. This is only
        sent if the thread has been created from an older message. The period of time
        required for a message to be considered old cannot be relied upon and is up to
        Discord.

        .. versionadded:: 2.0
    .. attribute:: reply

        The system message denoting that the author is replying to a message.

        .. versionadded:: 2.0
    .. attribute:: chat_input_command

        The system message denoting that a slash command was executed.

        .. versionadded:: 2.0
    .. attribute:: guild_invite_reminder

        The system message sent as a reminder to invite people to the guild.

        .. versionadded:: 2.0
    .. attribute:: thread_starter_message

        The system message denoting the message in the thread that is the one that started the
        thread's conversation topic.

        .. versionadded:: 2.0
    .. attribute:: context_menu_command

        The system message denoting that a context menu command was executed.

        .. versionadded:: 2.0
    .. attribute:: auto_moderation_action

        The system message sent when an AutoMod rule is triggered. This is only
        sent if the rule is configured to sent an alert when triggered.

        .. versionadded:: 2.0
    .. attribute:: role_subscription_purchase

        The system message sent when a user purchases or renews a role subscription.

        .. versionadded:: 2.2
    .. attribute:: interaction_premium_upsell

        The system message sent when a user is given an advertisement to purchase a premium tier for
        an application during an interaction.

        .. versionadded:: 2.2
    .. attribute:: stage_start

        The system message sent when the stage starts.

        .. versionadded:: 2.2
    .. attribute:: stage_end

        The system message sent when the stage ends.

        .. versionadded:: 2.2
    .. attribute:: stage_speaker

        The system message sent when the stage speaker changes.

        .. versionadded:: 2.2
    .. attribute:: stage_raise_hand

        The system message sent when a user is requesting to speak by raising their hands.

        .. versionadded:: 2.2
    .. attribute:: stage_topic

        The system message sent when the stage topic changes.

        .. versionadded:: 2.2
    .. attribute:: guild_application_premium_subscription

        The system message sent when an application's premium subscription is purchased for the guild.

        .. versionadded:: 2.2

    .. attribute:: guild_incident_alert_mode_enabled

        The system message sent when security actions is enabled.

        .. versionadded:: 2.4

    .. attribute:: guild_incident_alert_mode_disabled

        The system message sent when security actions is disabled.

        .. versionadded:: 2.4

    .. attribute:: guild_incident_report_raid

        The system message sent when a raid is reported.

        .. versionadded:: 2.4

    .. attribute:: guild_incident_report_false_alarm

        The system message sent when a false alarm is reported.

        .. versionadded:: 2.4

    .. attribute:: purchase_notification

        The system message sent when a purchase is made in the guild.

        .. versionadded:: 2.5

    .. attribute:: poll_result

        The system message sent when a poll has closed.

.. class:: UserFlags

    Represents Discord User flags.

    .. attribute:: staff

        The user is a Discord Employee.
    .. attribute:: partner

        The user is a Discord Partner.
    .. attribute:: hypesquad

        The user is a HypeSquad Events member.
    .. attribute:: bug_hunter

        The user is a Bug Hunter.
    .. attribute:: mfa_sms

        The user has SMS recovery for Multi Factor Authentication enabled.
    .. attribute:: premium_promo_dismissed

        The user has dismissed the Discord Nitro promotion.
    .. attribute:: hypesquad_bravery

        The user is a HypeSquad Bravery member.
    .. attribute:: hypesquad_brilliance

        The user is a HypeSquad Brilliance member.
    .. attribute:: hypesquad_balance

        The user is a HypeSquad Balance member.
    .. attribute:: early_supporter

        The user is an Early Supporter.
    .. attribute:: team_user

        The user is a Team User.
    .. attribute:: system

        The user is a system user (i.e. represents Discord officially).
    .. attribute:: has_unread_urgent_messages

        The user has an unread system message.
    .. attribute:: bug_hunter_level_2

        The user is a Bug Hunter Level 2.
    .. attribute:: verified_bot

        The user is a Verified Bot.
    .. attribute:: verified_bot_developer

        The user is an Early Verified Bot Developer.
    .. attribute:: discord_certified_moderator

        The user is a Moderator Programs Alumni.
    .. attribute:: bot_http_interactions

        The user is a bot that only uses HTTP interactions and is shown in the online member list.

        .. versionadded:: 2.0
    .. attribute:: spammer

        The user is flagged as a spammer by Discord.

        .. versionadded:: 2.0

    .. attribute:: active_developer

        The user is an active developer.

        .. versionadded:: 2.1

.. class:: ActivityType

    Specifies the type of :class:`Activity`. This is used to check how to
    interpret the activity itself.

    .. attribute:: unknown

        An unknown activity type. This should generally not happen.
    .. attribute:: playing

        A "Playing" activity type.
    .. attribute:: streaming

        A "Streaming" activity type.
    .. attribute:: listening

        A "Listening" activity type.
    .. attribute:: watching

        A "Watching" activity type.
    .. attribute:: custom

        A custom activity type.
    .. attribute:: competing

        A competing activity type.

        .. versionadded:: 1.5

.. class:: VerificationLevel

    Specifies a :class:`Guild`\'s verification level, which is the criteria in
    which a member must meet before being able to send messages to the guild.

    .. container:: operations

        .. versionadded:: 2.0

        .. describe:: x == y

            Checks if two verification levels are equal.
        .. describe:: x != y

            Checks if two verification levels are not equal.
        .. describe:: x > y

            Checks if a verification level is higher than another.
        .. describe:: x < y

            Checks if a verification level is lower than another.
        .. describe:: x >= y

            Checks if a verification level is higher or equal to another.
        .. describe:: x <= y

            Checks if a verification level is lower or equal to another.

    .. attribute:: none

        No criteria set.
    .. attribute:: low

        Member must have a verified email on their Discord account.
    .. attribute:: medium

        Member must have a verified email and be registered on Discord for more
        than five minutes.
    .. attribute:: high

        Member must have a verified email, be registered on Discord for more
        than five minutes, and be a member of the guild itself for more than
        ten minutes.
    .. attribute:: highest

        Member must have a verified phone on their Discord account.

.. class:: NotificationLevel

    Specifies whether a :class:`Guild` has notifications on for all messages or mentions only by default.

    .. container:: operations

        .. versionadded:: 2.0

        .. describe:: x == y

            Checks if two notification levels are equal.
        .. describe:: x != y

            Checks if two notification levels are not equal.
        .. describe:: x > y

            Checks if a notification level is higher than another.
        .. describe:: x < y

            Checks if a notification level is lower than another.
        .. describe:: x >= y

            Checks if a notification level is higher or equal to another.
        .. describe:: x <= y

            Checks if a notification level is lower or equal to another.

    .. attribute:: all_messages

        Members receive notifications for every message regardless of them being mentioned.
    .. attribute:: only_mentions

        Members receive notifications for messages they are mentioned in.

.. class:: ContentFilter

    Specifies a :class:`Guild`\'s explicit content filter, which is the machine
    learning algorithms that Discord uses to detect if an image contains
    pornography or otherwise explicit content.

    .. container:: operations

        .. versionadded:: 2.0

        .. describe:: x == y

            Checks if two content filter levels are equal.
        .. describe:: x != y

            Checks if two content filter levels are not equal.
        .. describe:: x > y

            Checks if a content filter level is higher than another.
        .. describe:: x < y

            Checks if a content filter level is lower than another.
        .. describe:: x >= y

            Checks if a content filter level is higher or equal to another.
        .. describe:: x <= y

            Checks if a content filter level is lower or equal to another.

    .. attribute:: disabled

        The guild does not have the content filter enabled.
    .. attribute:: no_role

        The guild has the content filter enabled for members without a role.
    .. attribute:: all_members

        The guild has the content filter enabled for every member.

.. class:: Status

    Specifies a :class:`Member` 's status.

    .. attribute:: online

        The member is online.
    .. attribute:: offline

        The member is offline.
    .. attribute:: idle

        The member is idle.
    .. attribute:: dnd

        The member is "Do Not Disturb".
    .. attribute:: do_not_disturb

        An alias for :attr:`dnd`.
    .. attribute:: invisible

        The member is "invisible". In reality, this is only used when sending
        a presence a la :meth:`Client.change_presence`. When you receive a
        user's presence this will be :attr:`offline` instead.


.. class:: AuditLogAction

    Represents the type of action being done for a :class:`AuditLogEntry`\,
    which is retrievable via :meth:`Guild.audit_logs`.

    .. attribute:: guild_update

        The guild has updated. Things that trigger this include:

        - Changing the guild vanity URL
        - Changing the guild invite splash
        - Changing the guild AFK channel or timeout
        - Changing the guild voice server region
        - Changing the guild icon, banner, or discovery splash
        - Changing the guild moderation settings
        - Changing things related to the guild widget

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Guild`.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.afk_channel`
        - :attr:`~AuditLogDiff.system_channel`
        - :attr:`~AuditLogDiff.afk_timeout`
        - :attr:`~AuditLogDiff.default_notifications`
        - :attr:`~AuditLogDiff.explicit_content_filter`
        - :attr:`~AuditLogDiff.mfa_level`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.owner`
        - :attr:`~AuditLogDiff.splash`
        - :attr:`~AuditLogDiff.discovery_splash`
        - :attr:`~AuditLogDiff.icon`
        - :attr:`~AuditLogDiff.banner`
        - :attr:`~AuditLogDiff.vanity_url_code`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.preferred_locale`
        - :attr:`~AuditLogDiff.prune_delete_days`
        - :attr:`~AuditLogDiff.public_updates_channel`
        - :attr:`~AuditLogDiff.rules_channel`
        - :attr:`~AuditLogDiff.verification_level`
        - :attr:`~AuditLogDiff.widget_channel`
        - :attr:`~AuditLogDiff.widget_enabled`
        - :attr:`~AuditLogDiff.premium_progress_bar_enabled`
        - :attr:`~AuditLogDiff.system_channel_flags`

    .. attribute:: channel_create

        A new channel was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        either a :class:`abc.GuildChannel` or :class:`Object` with an ID.

        A more filled out object in the :class:`Object` case can be found
        by using :attr:`~AuditLogEntry.after`.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.overwrites`

    .. attribute:: channel_update

        A channel was updated. Things that trigger this include:

        - The channel name or topic was changed
        - The channel bitrate was changed

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`abc.GuildChannel` or :class:`Object` with an ID.

        A more filled out object in the :class:`Object` case can be found
        by using :attr:`~AuditLogEntry.after` or :attr:`~AuditLogEntry.before`.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.position`
        - :attr:`~AuditLogDiff.overwrites`
        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.bitrate`
        - :attr:`~AuditLogDiff.rtc_region`
        - :attr:`~AuditLogDiff.video_quality_mode`
        - :attr:`~AuditLogDiff.default_auto_archive_duration`
        - :attr:`~AuditLogDiff.nsfw`
        - :attr:`~AuditLogDiff.slowmode_delay`
        - :attr:`~AuditLogDiff.user_limit`

    .. attribute:: channel_delete

        A channel was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        an :class:`Object` with an ID.

        A more filled out object can be found by using the
        :attr:`~AuditLogEntry.before` object.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.overwrites`
        - :attr:`~AuditLogDiff.flags`
        - :attr:`~AuditLogDiff.nsfw`
        - :attr:`~AuditLogDiff.slowmode_delay`

    .. attribute:: overwrite_create

        A channel permission overwrite was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`abc.GuildChannel` or :class:`Object` with an ID.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        either a :class:`Role` or :class:`Member`. If the object is not found
        then it is a :class:`Object` with an ID being filled, a name, and a
        ``type`` attribute set to either ``'role'`` or ``'member'`` to help
        dictate what type of ID it is.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.deny`
        - :attr:`~AuditLogDiff.allow`
        - :attr:`~AuditLogDiff.id`
        - :attr:`~AuditLogDiff.type`

    .. attribute:: overwrite_update

        A channel permission overwrite was changed, this is typically
        when the permission values change.

        See :attr:`overwrite_create` for more information on how the
        :attr:`~AuditLogEntry.target` and :attr:`~AuditLogEntry.extra` fields
        are set.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.deny`
        - :attr:`~AuditLogDiff.allow`
        - :attr:`~AuditLogDiff.id`
        - :attr:`~AuditLogDiff.type`

    .. attribute:: overwrite_delete

        A channel permission overwrite was deleted.

        See :attr:`overwrite_create` for more information on how the
        :attr:`~AuditLogEntry.target` and :attr:`~AuditLogEntry.extra` fields
        are set.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.deny`
        - :attr:`~AuditLogDiff.allow`
        - :attr:`~AuditLogDiff.id`
        - :attr:`~AuditLogDiff.type`

    .. attribute:: kick

        A member was kicked.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`User` or :class:`Object` who got kicked.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with one attribute:

        - ``integration_type``: An optional string that denotes the type of integration that did the action.

        When this is the action, :attr:`~AuditLogEntry.changes` is empty.

    .. attribute:: member_prune

        A member prune was triggered.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        set to ``None``.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``delete_member_days``: An integer specifying how far the prune was.
        - ``members_removed``: An integer specifying how many members were removed.

        When this is the action, :attr:`~AuditLogEntry.changes` is empty.

    .. attribute:: ban

        A member was banned.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`User` or :class:`Object` who got banned.

        When this is the action, :attr:`~AuditLogEntry.changes` is empty.

    .. attribute:: unban

        A member was unbanned.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`User` or :class:`Object` who got unbanned.

        When this is the action, :attr:`~AuditLogEntry.changes` is empty.

    .. attribute:: member_update

        A member has updated. This triggers in the following situations:

        - A nickname was changed
        - They were server muted or deafened (or it was undo'd)

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member`, :class:`User`, or :class:`Object` who got updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.nick`
        - :attr:`~AuditLogDiff.mute`
        - :attr:`~AuditLogDiff.deaf`
        - :attr:`~AuditLogDiff.timed_out_until`

    .. attribute:: member_role_update

        A member's role has been updated. This triggers when a member
        either gains a role or loses a role.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member`, :class:`User`, or :class:`Object` who got the role.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with one attribute:

        - ``integration_type``: An optional string that denotes the type of integration that did the action.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.roles`

    .. attribute:: member_move

        A member's voice channel has been updated. This triggers when a
        member is moved to a different voice channel.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``channel``: A :class:`TextChannel` or :class:`Object` with the channel ID where the members were moved.
        - ``count``: An integer specifying how many members were moved.

        .. versionadded:: 1.3

    .. attribute:: member_disconnect

        A member's voice state has changed. This triggers when a
        member is force disconnected from voice.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with one attribute:

        - ``count``: An integer specifying how many members were disconnected.

        .. versionadded:: 1.3

    .. attribute:: bot_add

        A bot was added to the guild.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member`, :class:`User`, or :class:`Object` which was added to the guild.

        .. versionadded:: 1.3

    .. attribute:: role_create

        A new role was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Role` or a :class:`Object` with the ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.colour`
        - :attr:`~AuditLogDiff.mentionable`
        - :attr:`~AuditLogDiff.hoist`
        - :attr:`~AuditLogDiff.icon`
        - :attr:`~AuditLogDiff.unicode_emoji`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.permissions`

    .. attribute:: role_update

        A role was updated. This triggers in the following situations:

        - The name has changed
        - The permissions have changed
        - The colour has changed
        - The role icon (or unicode emoji) has changed
        - Its hoist/mentionable state has changed

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Role` or a :class:`Object` with the ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.colour`
        - :attr:`~AuditLogDiff.mentionable`
        - :attr:`~AuditLogDiff.hoist`
        - :attr:`~AuditLogDiff.icon`
        - :attr:`~AuditLogDiff.unicode_emoji`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.permissions`

    .. attribute:: role_delete

        A role was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Role` or a :class:`Object` with the ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.colour`
        - :attr:`~AuditLogDiff.mentionable`
        - :attr:`~AuditLogDiff.hoist`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.permissions`

    .. attribute:: invite_create

        An invite was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Invite` that was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.max_age`
        - :attr:`~AuditLogDiff.code`
        - :attr:`~AuditLogDiff.temporary`
        - :attr:`~AuditLogDiff.inviter`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.uses`
        - :attr:`~AuditLogDiff.max_uses`

    .. attribute:: invite_update

        An invite was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Invite` that was updated.

    .. attribute:: invite_delete

        An invite was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Invite` that was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.max_age`
        - :attr:`~AuditLogDiff.code`
        - :attr:`~AuditLogDiff.temporary`
        - :attr:`~AuditLogDiff.inviter`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.uses`
        - :attr:`~AuditLogDiff.max_uses`

    .. attribute:: webhook_create

        A webhook was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the webhook ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type` (always set to ``1`` if so)

    .. attribute:: webhook_update

        A webhook was updated. This trigger in the following situations:

        - The webhook name changed
        - The webhook channel changed

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the webhook ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.avatar`

    .. attribute:: webhook_delete

        A webhook was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the webhook ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.type` (always set to ``1`` if so)

    .. attribute:: emoji_create

        An emoji was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Emoji` or :class:`Object` with the emoji ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`

    .. attribute:: emoji_update

        An emoji was updated. This triggers when the name has changed.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Emoji` or :class:`Object` with the emoji ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`

    .. attribute:: emoji_delete

        An emoji was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Object` with the emoji ID.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`

    .. attribute:: message_delete

        A message was deleted by a moderator. Note that this
        only triggers if the message was deleted by someone other than the author.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member`, :class:`User`, or :class:`Object` who had their message deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``count``: An integer specifying how many messages were deleted.
        - ``channel``: A :class:`TextChannel` or :class:`Object` with the channel ID where the message got deleted.

    .. attribute:: message_bulk_delete

        Messages were bulk deleted by a moderator.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`TextChannel` or :class:`Object` with the ID of the channel that was purged.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with one attribute:

        - ``count``: An integer specifying how many messages were deleted.

        .. versionadded:: 1.3

    .. attribute:: message_pin

        A message was pinned in a channel.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member`, :class:`User`, or :class:`Object` who had their message pinned.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``channel``: A :class:`TextChannel` or :class:`Object` with the channel ID where the message was pinned.
        - ``message_id``: the ID of the message which was pinned.

        .. versionadded:: 1.3

    .. attribute:: message_unpin

        A message was unpinned in a channel.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Member`, :class:`User`, or :class:`Object` who had their message unpinned.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with two attributes:

        - ``channel``: A :class:`TextChannel` or :class:`Object` with the channel ID where the message was unpinned.
        - ``message_id``: the ID of the message which was unpinned.

        .. versionadded:: 1.3

    .. attribute:: integration_create

        A guild integration was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`PartialIntegration` or :class:`Object` with the
        integration ID of the integration which was created.

        .. versionadded:: 1.3

    .. attribute:: integration_update

        A guild integration was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`PartialIntegration` or :class:`Object` with the
        integration ID of the integration which was updated.

        .. versionadded:: 1.3

    .. attribute:: integration_delete

        A guild integration was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`PartialIntegration` or :class:`Object` with the
        integration ID of the integration which was deleted.

        .. versionadded:: 1.3

    .. attribute:: stage_instance_create

        A stage instance was started.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`StageInstance` or :class:`Object` with the ID of the stage
        instance which was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.privacy_level`

        .. versionadded:: 2.0

    .. attribute:: stage_instance_update

        A stage instance was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`StageInstance` or :class:`Object` with the ID of the stage
        instance which was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.topic`
        - :attr:`~AuditLogDiff.privacy_level`

        .. versionadded:: 2.0

    .. attribute:: stage_instance_delete

        A stage instance was ended.

        .. versionadded:: 2.0

    .. attribute:: sticker_create

        A sticker was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`GuildSticker` or :class:`Object` with the ID of the sticker
        which was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.format_type`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.available`

        .. versionadded:: 2.0

    .. attribute:: sticker_update

        A sticker was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`GuildSticker` or :class:`Object` with the ID of the sticker
        which was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.format_type`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.available`

        .. versionadded:: 2.0

    .. attribute:: sticker_delete

        A sticker was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`GuildSticker` or :class:`Object` with the ID of the sticker
        which was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.type`
        - :attr:`~AuditLogDiff.format_type`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.available`

        .. versionadded:: 2.0

    .. attribute:: scheduled_event_create

        A scheduled event was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`ScheduledEvent` or :class:`Object` with the ID of the event
        which was created.

        Possible attributes for :class:`AuditLogDiff`:
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.privacy_level`
        - :attr:`~AuditLogDiff.status`
        - :attr:`~AuditLogDiff.entity_type`
        - :attr:`~AuditLogDiff.cover_image`

        .. versionadded:: 2.0

    .. attribute:: scheduled_event_update

        A scheduled event was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`ScheduledEvent` or :class:`Object` with the ID of the event
        which was updated.

        Possible attributes for :class:`AuditLogDiff`:
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.privacy_level`
        - :attr:`~AuditLogDiff.status`
        - :attr:`~AuditLogDiff.entity_type`
        - :attr:`~AuditLogDiff.cover_image`

        .. versionadded:: 2.0

    .. attribute:: scheduled_event_delete

        A scheduled event was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`ScheduledEvent` or :class:`Object` with the ID of the event
        which was deleted.

        Possible attributes for :class:`AuditLogDiff`:
        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.channel`
        - :attr:`~AuditLogDiff.description`
        - :attr:`~AuditLogDiff.privacy_level`
        - :attr:`~AuditLogDiff.status`
        - :attr:`~AuditLogDiff.entity_type`
        - :attr:`~AuditLogDiff.cover_image`

        .. versionadded:: 2.0

    .. attribute:: thread_create

        A thread was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Thread` or :class:`Object` with the ID of the thread which
        was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.archived`
        - :attr:`~AuditLogDiff.locked`
        - :attr:`~AuditLogDiff.auto_archive_duration`
        - :attr:`~AuditLogDiff.invitable`

        .. versionadded:: 2.0

    .. attribute:: thread_update

        A thread was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Thread` or :class:`Object` with the ID of the thread which
        was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.archived`
        - :attr:`~AuditLogDiff.locked`
        - :attr:`~AuditLogDiff.auto_archive_duration`
        - :attr:`~AuditLogDiff.invitable`

        .. versionadded:: 2.0

    .. attribute:: thread_delete

        A thread was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        the :class:`Thread` or :class:`Object` with the ID of the thread which
        was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.archived`
        - :attr:`~AuditLogDiff.locked`
        - :attr:`~AuditLogDiff.auto_archive_duration`
        - :attr:`~AuditLogDiff.invitable`

        .. versionadded:: 2.0

    .. attribute:: app_command_permission_update

        An application command or integrations application command permissions
        were updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`PartialIntegration` for an integrations general permissions,
        :class:`~discord.app_commands.AppCommand` for a specific commands permissions,
        or :class:`Object` with the ID of the command or integration which
        was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an :class:`PartialIntegration` or :class:`Object` with the ID of
        application that command or integration belongs to.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.app_command_permissions`

        .. versionadded:: 2.0

    .. attribute:: automod_rule_create

        An automod rule was created.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`AutoModRule` or :class:`Object` with the ID of the automod
        rule that was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.enabled`
        - :attr:`~AuditLogDiff.event_type`
        - :attr:`~AuditLogDiff.trigger_type`
        - :attr:`~AuditLogDiff.trigger`
        - :attr:`~AuditLogDiff.actions`
        - :attr:`~AuditLogDiff.exempt_roles`
        - :attr:`~AuditLogDiff.exempt_channels`

        .. versionadded:: 2.0

    .. attribute:: automod_rule_update

        An automod rule was updated.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`AutoModRule` or :class:`Object` with the ID of the automod
        rule that was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.enabled`
        - :attr:`~AuditLogDiff.event_type`
        - :attr:`~AuditLogDiff.trigger_type`
        - :attr:`~AuditLogDiff.trigger`
        - :attr:`~AuditLogDiff.actions`
        - :attr:`~AuditLogDiff.exempt_roles`
        - :attr:`~AuditLogDiff.exempt_channels`

        .. versionadded:: 2.0

    .. attribute:: automod_rule_delete

        An automod rule was deleted.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`AutoModRule` or :class:`Object` with the ID of the automod
        rule that was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.enabled`
        - :attr:`~AuditLogDiff.event_type`
        - :attr:`~AuditLogDiff.trigger_type`
        - :attr:`~AuditLogDiff.trigger`
        - :attr:`~AuditLogDiff.actions`
        - :attr:`~AuditLogDiff.exempt_roles`
        - :attr:`~AuditLogDiff.exempt_channels`

        .. versionadded:: 2.0

    .. attribute:: automod_block_message

        An automod rule blocked a message from being sent.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`Member` with the ID of the person who triggered the automod rule.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with 3 attributes:

        - ``automod_rule_name``: The name of the automod rule that was triggered.
        - ``automod_rule_trigger_type``: A :class:`AutoModRuleTriggerType` representation of the rule type that was triggered.
        - ``channel``: The channel in which the automod rule was triggered.

        When this is the action, :attr:`AuditLogEntry.changes` is empty.

        .. versionadded:: 2.0

    .. attribute:: automod_flag_message

        An automod rule flagged a message.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`Member` with the ID of the person who triggered the automod rule.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with 3 attributes:

        - ``automod_rule_name``: The name of the automod rule that was triggered.
        - ``automod_rule_trigger_type``: A :class:`AutoModRuleTriggerType` representation of the rule type that was triggered.
        - ``channel``: The channel in which the automod rule was triggered.

        When this is the action, :attr:`AuditLogEntry.changes` is empty.

        .. versionadded:: 2.1

    .. attribute:: automod_timeout_member

        An automod rule timed-out a member.

        When this is the action, the type of :attr:`~AuditLogEntry.target` is
        a :class:`Member` with the ID of the person who triggered the automod rule.

        When this is the action, the type of :attr:`~AuditLogEntry.extra` is
        set to an unspecified proxy object with 3 attributes:

        - ``automod_rule_name``: The name of the automod rule that was triggered.
        - ``automod_rule_trigger_type``: A :class:`AutoModRuleTriggerType` representation of the rule type that was triggered.
        - ``channel``: The channel in which the automod rule was triggered.

        When this is the action, :attr:`AuditLogEntry.changes` is empty.

        .. versionadded:: 2.1

    .. attribute:: creator_monetization_request_created

        A request to monetize the server was created.

        .. versionadded:: 2.4

    .. attribute:: creator_monetization_terms_accepted

        The terms and conditions for creator monetization were accepted.

        .. versionadded:: 2.4

    .. attribute:: soundboard_sound_create

        A soundboard sound was created.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.volume`

        .. versionadded:: 2.5

    .. attribute:: soundboard_sound_update

        A soundboard sound was updated.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.volume`

        .. versionadded:: 2.5

    .. attribute:: soundboard_sound_delete

        A soundboard sound was deleted.

        Possible attributes for :class:`AuditLogDiff`:

        - :attr:`~AuditLogDiff.name`
        - :attr:`~AuditLogDiff.emoji`
        - :attr:`~AuditLogDiff.volume`

        .. versionadded:: 2.5

.. class:: AuditLogActionCategory

    Represents the category that the :class:`AuditLogAction` belongs to.

    This can be retrieved via :attr:`AuditLogEntry.category`.

    .. attribute:: create

        The action is the creation of something.

    .. attribute:: delete

        The action is the deletion of something.

    .. attribute:: update

        The action is the update of something.

.. class:: TeamMembershipState

    Represents the membership state of a team member retrieved through :func:`Client.application_info`.

    .. versionadded:: 1.3

    .. attribute:: invited

        Represents an invited member.

    .. attribute:: accepted

        Represents a member currently in the team.

.. class:: TeamMemberRole

    Represents the type of role of a team member retrieved through :func:`Client.application_info`.

    .. versionadded:: 2.4

    .. attribute:: admin

        The team member is an admin. This allows them to invite members to the team, access credentials, edit the application,
        and do most things the owner can do. However they cannot do destructive actions.

    .. attribute:: developer

        The team member is a developer. This allows them to access information, like the client secret or public key.
        They can also configure interaction endpoints or reset the bot token. Developers cannot invite anyone to the team
        nor can they do destructive actions.

    .. attribute:: read_only

        The team member is a read-only member. This allows them to access information, but not edit anything.

.. class:: WebhookType

    Represents the type of webhook that can be received.

    .. versionadded:: 1.3

    .. attribute:: incoming

        Represents a webhook that can post messages to channels with a token.

    .. attribute:: channel_follower

        Represents a webhook that is internally managed by Discord, used for following channels.

    .. attribute:: application

        Represents a webhook that is used for interactions or applications.

        .. versionadded:: 2.0

.. class:: ExpireBehaviour

    Represents the behaviour the :class:`Integration` should perform
    when a user's subscription has finished.

    There is an alias for this called ``ExpireBehavior``.

    .. versionadded:: 1.4

    .. attribute:: remove_role

        This will remove the :attr:`StreamIntegration.role` from the user
        when their subscription is finished.

    .. attribute:: kick

        This will kick the user when their subscription is finished.

.. class:: DefaultAvatar

    Represents the default avatar of a Discord :class:`User`

    .. attribute:: blurple

        Represents the default avatar with the colour blurple.
        See also :attr:`Colour.blurple`
    .. attribute:: grey

        Represents the default avatar with the colour grey.
        See also :attr:`Colour.greyple`
    .. attribute:: gray

        An alias for :attr:`grey`.
    .. attribute:: green

        Represents the default avatar with the colour green.
        See also :attr:`Colour.green`
    .. attribute:: orange

        Represents the default avatar with the colour orange.
        See also :attr:`Colour.orange`
    .. attribute:: red

        Represents the default avatar with the colour red.
        See also :attr:`Colour.red`
    .. attribute:: pink

        Represents the default avatar with the colour pink.
        See also :attr:`Colour.pink`

        .. versionadded:: 2.3

.. class:: StickerType

    Represents the type of sticker.

    .. versionadded:: 2.0

    .. attribute:: standard

        Represents a standard sticker that all Nitro users can use.

    .. attribute:: guild

        Represents a custom sticker created in a guild.

.. class:: StickerFormatType

    Represents the type of sticker images.

    .. versionadded:: 1.6

    .. attribute:: png

        Represents a sticker with a png image.

    .. attribute:: apng

        Represents a sticker with an apng image.

    .. attribute:: lottie

        Represents a sticker with a lottie image.

    .. attribute:: gif

        Represents a sticker with a gif image.

        .. versionadded:: 2.2

.. class:: InviteTarget

    Represents the invite type for voice channel invites.

    .. versionadded:: 2.0

    .. attribute:: unknown

        The invite doesn't target anyone or anything.

    .. attribute:: stream

        A stream invite that targets a user.

    .. attribute:: embedded_application

        A stream invite that targets an embedded application.

.. class:: VideoQualityMode

    Represents the camera video quality mode for voice channel participants.

    .. versionadded:: 2.0

    .. attribute:: auto

        Represents auto camera video quality.

    .. attribute:: full

        Represents full camera video quality.

.. class:: PrivacyLevel

    Represents the privacy level of a stage instance or scheduled event.

    .. versionadded:: 2.0

    .. attribute:: guild_only

       The stage instance or scheduled event is only accessible within the guild.

.. class:: NSFWLevel

    Represents the NSFW level of a guild.

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two NSFW levels are equal.
        .. describe:: x != y

            Checks if two NSFW levels are not equal.
        .. describe:: x > y

            Checks if a NSFW level is higher than another.
        .. describe:: x < y

            Checks if a NSFW level is lower than another.
        .. describe:: x >= y

            Checks if a NSFW level is higher or equal to another.
        .. describe:: x <= y

            Checks if a NSFW level is lower or equal to another.

    .. attribute:: default

        The guild has not been categorised yet.

    .. attribute:: explicit

        The guild contains NSFW content.

    .. attribute:: safe

        The guild does not contain any NSFW content.

    .. attribute:: age_restricted

        The guild may contain NSFW content.

.. class:: Locale

    Supported locales by Discord. Mainly used for application command localisation.

    .. versionadded:: 2.0

    .. attribute:: american_english

        The ``en-US`` locale.

    .. attribute:: british_english

        The ``en-GB`` locale.

    .. attribute:: bulgarian

        The ``bg`` locale.

    .. attribute:: chinese

        The ``zh-CN`` locale.

    .. attribute:: taiwan_chinese

        The ``zh-TW`` locale.

    .. attribute:: croatian

        The ``hr`` locale.

    .. attribute:: czech

        The ``cs`` locale.

    .. attribute:: indonesian

        The ``id`` locale.

        .. versionadded:: 2.2

    .. attribute:: danish

        The ``da`` locale.

    .. attribute:: dutch

        The ``nl`` locale.

    .. attribute:: finnish

        The ``fi`` locale.

    .. attribute:: french

        The ``fr`` locale.

    .. attribute:: german

        The ``de`` locale.

    .. attribute:: greek

        The ``el`` locale.

    .. attribute:: hindi

        The ``hi`` locale.

    .. attribute:: hungarian

        The ``hu`` locale.

    .. attribute:: italian

        The ``it`` locale.

    .. attribute:: japanese

        The ``ja`` locale.

    .. attribute:: korean

        The ``ko`` locale.

    .. attribute:: latin_american_spanish

        The ``es-419`` locale.

        .. versionadded:: 2.4

    .. attribute:: lithuanian

        The ``lt`` locale.

    .. attribute:: norwegian

        The ``no`` locale.

    .. attribute:: polish

        The ``pl`` locale.

    .. attribute:: brazil_portuguese

        The ``pt-BR`` locale.

    .. attribute:: romanian

        The ``ro`` locale.

    .. attribute:: russian

        The ``ru`` locale.

    .. attribute:: spain_spanish

        The ``es-ES`` locale.

    .. attribute:: swedish

        The ``sv-SE`` locale.

    .. attribute:: thai

        The ``th`` locale.

    .. attribute:: turkish

        The ``tr`` locale.

    .. attribute:: ukrainian

        The ``uk`` locale.

    .. attribute:: vietnamese

        The ``vi`` locale.


.. class:: MFALevel

    Represents the Multi-Factor Authentication requirement level of a guild.

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two MFA levels are equal.
        .. describe:: x != y

            Checks if two MFA levels are not equal.
        .. describe:: x > y

            Checks if a MFA level is higher than another.
        .. describe:: x < y

            Checks if a MFA level is lower than another.
        .. describe:: x >= y

            Checks if a MFA level is higher or equal to another.
        .. describe:: x <= y

            Checks if a MFA level is lower or equal to another.

    .. attribute:: disabled

        The guild has no MFA requirement.

    .. attribute:: require_2fa

        The guild requires 2 factor authentication.

.. class:: EntityType

    Represents the type of entity that a scheduled event is for.

    .. versionadded:: 2.0

    .. attribute:: stage_instance

        The scheduled event will occur in a stage instance.

    .. attribute:: voice

        The scheduled event will occur in a voice channel.

    .. attribute:: external

        The scheduled event will occur externally.

.. class:: EventStatus

    Represents the status of an event.

    .. versionadded:: 2.0

    .. attribute:: scheduled

        The event is scheduled.

    .. attribute:: active

        The event is active.

    .. attribute:: completed

        The event has ended.

    .. attribute:: cancelled

        The event has been cancelled.

    .. attribute:: canceled

        An alias for :attr:`cancelled`.

    .. attribute:: ended

        An alias for :attr:`completed`.

.. class:: AutoModRuleTriggerType

    Represents the trigger type of an automod rule.

    .. versionadded:: 2.0

    .. attribute:: keyword

        The rule will trigger when a keyword is mentioned.

    .. attribute:: harmful_link

        The rule will trigger when a harmful link is posted.

    .. attribute:: spam

        The rule will trigger when a spam message is posted.

    .. attribute:: keyword_preset

        The rule will trigger when something triggers based on the set keyword preset types.

    .. attribute:: mention_spam

        The rule will trigger when combined number of role and user mentions
        is greater than the set limit.

    .. attribute:: member_profile

        The rule will trigger when a user's profile contains a keyword.

        .. versionadded:: 2.4

.. class:: AutoModRuleEventType

    Represents the event type of an automod rule.

    .. versionadded:: 2.0

    .. attribute:: message_send

        The rule will trigger when a message is sent.

    .. attribute:: member_update

        The rule will trigger when a member's profile is updated.

        .. versionadded:: 2.4

.. class:: AutoModRuleActionType

    Represents the action type of an automod rule.

    .. versionadded:: 2.0

    .. attribute:: block_message

        The rule will block a message from being sent.

    .. attribute:: send_alert_message

        The rule will send an alert message to a predefined channel.

    .. attribute:: timeout

        The rule will timeout a user.

    .. attribute:: block_member_interactions

        Similar to :attr:`timeout`, except the user will be timed out indefinitely.
        This will request the user to edit it's profile.

        .. versionadded:: 2.4

.. class:: ForumLayoutType

    Represents how a forum's posts are layed out in the client.

    .. versionadded:: 2.2

    .. attribute:: not_set

        No default has been set, so it is up to the client to know how to lay it out.

    .. attribute:: list_view

        Displays posts as a list.

    .. attribute:: gallery_view

        Displays posts as a collection of tiles.


.. class:: ForumOrderType

    Represents how a forum's posts are sorted in the client.

    .. versionadded:: 2.3

    .. attribute:: latest_activity

        Sort forum posts by activity.

    .. attribute:: creation_date

        Sort forum posts by creation time (from most recent to oldest).

.. class:: SelectDefaultValueType

    Represents the default value of a select menu.

    .. versionadded:: 2.4

    .. attribute:: user

        The underlying type of the ID is a user.

    .. attribute:: role

        The underlying type of the ID is a role.

    .. attribute:: channel

        The underlying type of the ID is a channel or thread.


.. class:: SKUType

    Represents the type of a SKU.

    .. versionadded:: 2.4

    .. attribute:: durable

        The SKU is a durable one-time purchase.

    .. attribute:: consumable

        The SKU is a consumable one-time purchase.

    .. attribute:: subscription

        The SKU is a recurring subscription.

    .. attribute:: subscription_group

        The SKU is a system-generated group which is created for each :attr:`SKUType.subscription`.


.. class:: EntitlementType

    Represents the type of an entitlement.

    .. versionadded:: 2.4

    .. attribute:: purchase

        The entitlement was purchased by the user.

    .. attribute:: premium_subscription

        The entitlement is for a nitro subscription.

    .. attribute:: developer_gift

        The entitlement was gifted by the developer.

    .. attribute:: test_mode_purchase

        The entitlement was purchased by a developer in application test mode.

    .. attribute:: free_purchase

        The entitlement was granted, when the SKU was free.

    .. attribute:: user_gift

        The entitlement was gifted by a another user.

    .. attribute:: premium_purchase

        The entitlement was claimed for free by a nitro subscriber.

    .. attribute:: application_subscription

        The entitlement was purchased as an app subscription.


.. class:: EntitlementOwnerType

    Represents the type of an entitlement owner.

    .. versionadded:: 2.4

    .. attribute:: guild

        The entitlement owner is a guild.

    .. attribute:: user

            The entitlement owner is a user.


.. class:: PollLayoutType

    Represents how a poll answers are shown.

    .. versionadded:: 2.4

    .. attribute:: default

        The default layout.


.. class:: InviteType

    Represents the type of an invite.

    .. versionadded:: 2.4

    .. attribute:: guild

        The invite is a guild invite.

    .. attribute:: group_dm

        The invite is a group DM invite.

    .. attribute:: friend

        The invite is a friend invite.


.. class:: ReactionType

    Represents the type of a reaction.

    .. versionadded:: 2.4

    .. attribute:: normal

        A normal reaction.

    .. attribute:: burst

        A burst reaction, also known as a "super reaction".


.. class:: VoiceChannelEffectAnimationType

    Represents the animation type of a voice channel effect.

    .. versionadded:: 2.5

    .. attribute:: premium

        A fun animation, sent by a Nitro subscriber.

    .. attribute:: basic

        The standard animation.


.. class:: SubscriptionStatus

    Represents the status of an subscription.

    .. versionadded:: 2.5

    .. attribute:: active

        The subscription is active.

    .. attribute:: ending

        The subscription is active but will not renew.

    .. attribute:: inactive

        The subscription is inactive and not being charged.


.. class:: MessageReferenceType

    Represents the type of a message reference.

    .. versionadded:: 2.5

    .. attribute:: reply

        A message reply.

    .. attribute:: forward

        A forwarded message.

    .. attribute:: default

        An alias for :attr:`.reply`.

.. _discord-api-audit-logs:

Audit Log Data
----------------

Working with :meth:`Guild.audit_logs` is a complicated process with a lot of machinery
involved. The library attempts to make it easy to use and friendly. In order to accomplish
this goal, it must make use of a couple of data classes that aid in this goal.

AuditLogEntry
~~~~~~~~~~~~~~~

.. attributetable:: AuditLogEntry

.. autoclass:: AuditLogEntry
    :members:

AuditLogChanges
~~~~~~~~~~~~~~~~~

.. attributetable:: AuditLogChanges

.. class:: AuditLogChanges

    An audit log change set.

    .. attribute:: before

        The old value. The attribute has the type of :class:`AuditLogDiff`.

        Depending on the :class:`AuditLogActionCategory` retrieved by
        :attr:`~AuditLogEntry.category`\, the data retrieved by this
        attribute differs:

        +----------------------------------------+---------------------------------------------------+
        |                Category                |                    Description                    |
        +----------------------------------------+---------------------------------------------------+
        | :attr:`~AuditLogActionCategory.create` | All attributes are set to ``None``.               |
        +----------------------------------------+---------------------------------------------------+
        | :attr:`~AuditLogActionCategory.delete` | All attributes are set the value before deletion. |
        +----------------------------------------+---------------------------------------------------+
        | :attr:`~AuditLogActionCategory.update` | All attributes are set the value before updating. |
        +----------------------------------------+---------------------------------------------------+
        | ``None``                               | No attributes are set.                            |
        +----------------------------------------+---------------------------------------------------+

    .. attribute:: after

        The new value. The attribute has the type of :class:`AuditLogDiff`.

        Depending on the :class:`AuditLogActionCategory` retrieved by
        :attr:`~AuditLogEntry.category`\, the data retrieved by this
        attribute differs:

        +----------------------------------------+--------------------------------------------------+
        |                Category                |                   Description                    |
        +----------------------------------------+--------------------------------------------------+
        | :attr:`~AuditLogActionCategory.create` | All attributes are set to the created value      |
        +----------------------------------------+--------------------------------------------------+
        | :attr:`~AuditLogActionCategory.delete` | All attributes are set to ``None``               |
        +----------------------------------------+--------------------------------------------------+
        | :attr:`~AuditLogActionCategory.update` | All attributes are set the value after updating. |
        +----------------------------------------+--------------------------------------------------+
        | ``None``                               | No attributes are set.                           |
        +----------------------------------------+--------------------------------------------------+

AuditLogDiff
~~~~~~~~~~~~~

.. attributetable:: AuditLogDiff

.. class:: AuditLogDiff

    Represents an audit log "change" object. A change object has dynamic
    attributes that depend on the type of action being done. Certain actions
    map to certain attributes being set.

    Note that accessing an attribute that does not match the specified action
    will lead to an attribute error.

    To get a list of attributes that have been set, you can iterate over
    them. To see a list of all possible attributes that could be set based
    on the action being done, check the documentation for :class:`AuditLogAction`,
    otherwise check the documentation below for all attributes that are possible.

    .. container:: operations

        .. describe:: iter(diff)

            Returns an iterator over (attribute, value) tuple of this diff.

    .. attribute:: name

        A name of something.

        :type: :class:`str`

    .. attribute:: guild

        The guild of something.

        :type: :class:`Guild`

    .. attribute:: icon

        A guild's or role's icon. See also :attr:`Guild.icon` or :attr:`Role.icon`.

        :type: :class:`Asset`

    .. attribute:: splash

        The guild's invite splash. See also :attr:`Guild.splash`.

        :type: :class:`Asset`

    .. attribute:: discovery_splash

        The guild's discovery splash. See also :attr:`Guild.discovery_splash`.

        :type: :class:`Asset`

    .. attribute:: banner

        The guild's banner. See also :attr:`Guild.banner`.

        :type: :class:`Asset`

    .. attribute:: owner

        The guild's owner. See also :attr:`Guild.owner`

        :type: Union[:class:`Member`, :class:`User`]

    .. attribute:: afk_channel

        The guild's AFK channel.

        If this could not be found, then it falls back to a :class:`Object`
        with the ID being set.

        See :attr:`Guild.afk_channel`.

        :type: Union[:class:`VoiceChannel`, :class:`Object`]

    .. attribute:: system_channel

        The guild's system channel.

        If this could not be found, then it falls back to a :class:`Object`
        with the ID being set.

        See :attr:`Guild.system_channel`.

        :type: Union[:class:`TextChannel`, :class:`Object`]


    .. attribute:: rules_channel

        The guild's rules channel.

        If this could not be found then it falls back to a :class:`Object`
        with the ID being set.

        See :attr:`Guild.rules_channel`.

        :type: Union[:class:`TextChannel`, :class:`Object`]


    .. attribute:: public_updates_channel

        The guild's public updates channel.

        If this could not be found then it falls back to a :class:`Object`
        with the ID being set.

        See :attr:`Guild.public_updates_channel`.

        :type: Union[:class:`TextChannel`, :class:`Object`]

    .. attribute:: afk_timeout

        The guild's AFK timeout. See :attr:`Guild.afk_timeout`.

        :type: :class:`int`

    .. attribute:: mfa_level

        The guild's MFA level. See :attr:`Guild.mfa_level`.

        :type: :class:`MFALevel`

    .. attribute:: widget_enabled

        The guild's widget has been enabled or disabled.

        :type: :class:`bool`

    .. attribute:: widget_channel

        The widget's channel.

        If this could not be found then it falls back to a :class:`Object`
        with the ID being set.

        :type: Union[:class:`TextChannel`, :class:`Object`]

    .. attribute:: verification_level

        The guild's verification level.

        See also :attr:`Guild.verification_level`.

        :type: :class:`VerificationLevel`

    .. attribute:: default_notifications

        The guild's default notification level.

        See also :attr:`Guild.default_notifications`.

        :type: :class:`NotificationLevel`

    .. attribute:: explicit_content_filter

        The guild's content filter.

        See also :attr:`Guild.explicit_content_filter`.

        :type: :class:`ContentFilter`

    .. attribute:: vanity_url_code

        The guild's vanity URL.

        See also :meth:`Guild.vanity_invite` and :meth:`Guild.edit`.

        :type: :class:`str`

    .. attribute:: position

        The position of a :class:`Role` or :class:`abc.GuildChannel`.

        :type: :class:`int`

    .. attribute:: type

        The type of channel, sticker, webhook or integration.

        :type: Union[:class:`ChannelType`, :class:`StickerType`, :class:`WebhookType`, :class:`str`]

    .. attribute:: topic

        The topic of a :class:`TextChannel` or :class:`StageChannel`.

        See also :attr:`TextChannel.topic` or :attr:`StageChannel.topic`.

        :type: :class:`str`

    .. attribute:: bitrate

        The bitrate of a :class:`VoiceChannel`.

        See also :attr:`VoiceChannel.bitrate`.

        :type: :class:`int`

    .. attribute:: overwrites

        A list of permission overwrite tuples that represents a target and a
        :class:`PermissionOverwrite` for said target.

        The first element is the object being targeted, which can either
        be a :class:`Member` or :class:`User` or :class:`Role`. If this object
        is not found then it is a :class:`Object` with an ID being filled and
        a ``type`` attribute set to either ``'role'`` or ``'member'`` to help
        decide what type of ID it is.

        :type: List[Tuple[target, :class:`PermissionOverwrite`]]

    .. attribute:: privacy_level

        The privacy level of the stage instance or scheduled event

        :type: :class:`PrivacyLevel`

    .. attribute:: roles

        A list of roles being added or removed from a member.

        If a role is not found then it is a :class:`Object` with the ID and name being
        filled in.

        :type: List[Union[:class:`Role`, :class:`Object`]]

    .. attribute:: nick

        The nickname of a member.

        See also :attr:`Member.nick`

        :type: Optional[:class:`str`]

    .. attribute:: deaf

        Whether the member is being server deafened.

        See also :attr:`VoiceState.deaf`.

        :type: :class:`bool`

    .. attribute:: mute

        Whether the member is being server muted.

        See also :attr:`VoiceState.mute`.

        :type: :class:`bool`

    .. attribute:: permissions

        The permissions of a role.

        See also :attr:`Role.permissions`.

        :type: :class:`Permissions`

    .. attribute:: colour
                   color

        The colour of a role.

        See also :attr:`Role.colour`

        :type: :class:`Colour`

    .. attribute:: hoist

        Whether the role is being hoisted or not.

        See also :attr:`Role.hoist`

        :type: :class:`bool`

    .. attribute:: mentionable

        Whether the role is mentionable or not.

        See also :attr:`Role.mentionable`

        :type: :class:`bool`

    .. attribute:: code

        The invite's code.

        See also :attr:`Invite.code`

        :type: :class:`str`

    .. attribute:: channel

        A guild channel.

        If the channel is not found then it is a :class:`Object` with the ID
        being set. In some cases the channel name is also set.

        :type: Union[:class:`abc.GuildChannel`, :class:`Object`]

    .. attribute:: inviter

        The user who created the invite.

        See also :attr:`Invite.inviter`.

        :type: Optional[:class:`User`]

    .. attribute:: max_uses

        The invite's max uses.

        See also :attr:`Invite.max_uses`.

        :type: :class:`int`

    .. attribute:: uses

        The invite's current uses.

        See also :attr:`Invite.uses`.

        :type: :class:`int`

    .. attribute:: max_age

        The invite's max age in seconds.

        See also :attr:`Invite.max_age`.

        :type: :class:`int`

    .. attribute:: temporary

        If the invite is a temporary invite.

        See also :attr:`Invite.temporary`.

        :type: :class:`bool`

    .. attribute:: allow
                   deny

        The permissions being allowed or denied.

        :type: :class:`Permissions`

    .. attribute:: id

        The ID of the object being changed.

        :type: :class:`int`

    .. attribute:: avatar

        The avatar of a member.

        See also :attr:`User.avatar`.

        :type: :class:`Asset`

    .. attribute:: slowmode_delay

        The number of seconds members have to wait before
        sending another message in the channel.

        See also :attr:`TextChannel.slowmode_delay`.

        :type: :class:`int`

    .. attribute:: rtc_region

        The region for the voice channel’s voice communication.
        A value of ``None`` indicates automatic voice region detection.

        See also :attr:`VoiceChannel.rtc_region`.

        :type: :class:`str`

    .. attribute:: video_quality_mode

        The camera video quality for the voice channel's participants.

        See also :attr:`VoiceChannel.video_quality_mode`.

        :type: :class:`VideoQualityMode`

    .. attribute:: format_type

        The format type of a sticker being changed.

        See also :attr:`GuildSticker.format`

        :type: :class:`StickerFormatType`

    .. attribute:: emoji

        The emoji which represents one of the following:

        * :attr:`GuildSticker.emoji`
        * :attr:`SoundboardSound.emoji`

        :type: Union[:class:`str`, :class:`PartialEmoji`]

    .. attribute:: unicode_emoji

        The unicode emoji that is used as an icon for the role being changed.

        See also :attr:`Role.unicode_emoji`.

        :type: :class:`str`

    .. attribute:: description

        The description of a guild, a sticker, or a scheduled event.

        See also :attr:`Guild.description`, :attr:`GuildSticker.description`, or
        :attr:`ScheduledEvent.description`.

        :type: :class:`str`

    .. attribute:: available

        The availability of one of the following being changed:

        * :attr:`GuildSticker.available`
        * :attr:`SoundboardSound.available`

        :type: :class:`bool`

    .. attribute:: archived

        The thread is now archived.

        :type: :class:`bool`

    .. attribute:: locked

        The thread is being locked or unlocked.

        :type: :class:`bool`

    .. attribute:: auto_archive_duration

        The thread's auto archive duration being changed.

        See also :attr:`Thread.auto_archive_duration`

        :type: :class:`int`

    .. attribute:: default_auto_archive_duration

        The default auto archive duration for newly created threads being changed.

        :type: :class:`int`

    .. attribute:: invitable

        Whether non-moderators can add users to this private thread.

        :type: :class:`bool`

    .. attribute:: timed_out_until

        Whether the user is timed out, and if so until when.

        :type: Optional[:class:`datetime.datetime`]

    .. attribute:: enable_emoticons

        Integration emoticons were enabled or disabled.

        See also :attr:`StreamIntegration.enable_emoticons`

        :type: :class:`bool`

    .. attribute:: expire_behaviour
                   expire_behavior

        The behaviour of expiring subscribers changed.

        See also :attr:`StreamIntegration.expire_behaviour`

        :type: :class:`ExpireBehaviour`

    .. attribute:: expire_grace_period

        The grace period before expiring subscribers changed.

        See also :attr:`StreamIntegration.expire_grace_period`

        :type: :class:`int`

    .. attribute:: preferred_locale

        The preferred locale for the guild changed.

        See also :attr:`Guild.preferred_locale`

        :type: :class:`Locale`

    .. attribute:: prune_delete_days

        The number of days after which inactive and role-unassigned members are kicked has been changed.

        :type: :class:`int`

    .. attribute:: status

        The status of the scheduled event.

        :type: :class:`EventStatus`

    .. attribute:: entity_type

        The type of entity this scheduled event is for.

        :type: :class:`EntityType`

    .. attribute:: cover_image

        The scheduled event's cover image.

        See also :attr:`ScheduledEvent.cover_image`.

        :type: :class:`Asset`

    .. attribute:: app_command_permissions

        List of permissions for the app command.

        :type: List[:class:`~discord.app_commands.AppCommandPermissions`]

    .. attribute:: enabled

        Whether the automod rule is active or not.

        :type: :class:`bool`

    .. attribute:: event_type

        The event type for triggering the automod rule.

        :type: :class:`AutoModRuleEventType`

    .. attribute:: trigger_type

        The trigger type for the automod rule.

        :type: :class:`AutoModRuleTriggerType`

    .. attribute:: trigger

        The trigger for the automod rule.

        .. note ::

            The :attr:`~AutoModTrigger.type` of the trigger may be incorrect.
            Some attributes such as :attr:`~AutoModTrigger.keyword_filter`, :attr:`~AutoModTrigger.regex_patterns`,
            and :attr:`~AutoModTrigger.allow_list` will only have the added or removed values.

        :type: :class:`AutoModTrigger`

    .. attribute:: actions

        The actions to take when an automod rule is triggered.

        :type: List[AutoModRuleAction]

    .. attribute:: exempt_roles

        The list of roles that are exempt from the automod rule.

        :type: List[Union[:class:`Role`, :class:`Object`]]

    .. attribute:: exempt_channels

        The list of channels or threads that are exempt from the automod rule.

        :type: List[:class:`abc.GuildChannel`, :class:`Thread`, :class:`Object`]

    .. attribute:: premium_progress_bar_enabled

        The guild’s display setting to show boost progress bar.

        :type: :class:`bool`

    .. attribute:: system_channel_flags

        The guild’s system channel settings.

        See also :attr:`Guild.system_channel_flags`

        :type: :class:`SystemChannelFlags`

    .. attribute:: nsfw

        Whether the channel is marked as “not safe for work” or “age restricted”.

        :type: :class:`bool`

    .. attribute:: user_limit

        The channel’s limit for number of members that can be in a voice or stage channel.

        See also :attr:`VoiceChannel.user_limit` and :attr:`StageChannel.user_limit`

        :type: :class:`int`

    .. attribute:: flags

        The channel flags associated with this thread or forum post.

        See also :attr:`ForumChannel.flags` and :attr:`Thread.flags`

        :type: :class:`ChannelFlags`

    .. attribute:: default_thread_slowmode_delay

        The default slowmode delay for threads created in this text channel or forum.

        See also :attr:`TextChannel.default_thread_slowmode_delay` and :attr:`ForumChannel.default_thread_slowmode_delay`

        :type: :class:`int`

    .. attribute:: applied_tags

        The applied tags of a forum post.

        See also :attr:`Thread.applied_tags`

        :type: List[Union[:class:`ForumTag`, :class:`Object`]]

    .. attribute:: available_tags

        The available tags of a forum.

        See also :attr:`ForumChannel.available_tags`

        :type: Sequence[:class:`ForumTag`]

    .. attribute:: default_reaction_emoji

        The default_reaction_emoji for forum posts.

        See also :attr:`ForumChannel.default_reaction_emoji`

        :type: Optional[:class:`PartialEmoji`]

    .. attribute:: user

        The user that represents the uploader of a soundboard sound.

        See also :attr:`SoundboardSound.user`

        :type: Union[:class:`Member`, :class:`User`]

    .. attribute:: volume

        The volume of a soundboard sound.

        See also :attr:`SoundboardSound.volume`

        :type: :class:`float`

.. this is currently missing the following keys: reason and application_id
   I'm not sure how to port these

Webhook Support
------------------

discord.py offers support for creating, editing, and executing webhooks through the :class:`Webhook` class.

Webhook
~~~~~~~~~

.. attributetable:: Webhook

.. autoclass:: Webhook()
    :members:
    :inherited-members:

WebhookMessage
~~~~~~~~~~~~~~~~

.. attributetable:: WebhookMessage

.. autoclass:: WebhookMessage()
    :members:
    :inherited-members:

SyncWebhook
~~~~~~~~~~~~

.. attributetable:: SyncWebhook

.. autoclass:: SyncWebhook()
    :members:
    :inherited-members:

SyncWebhookMessage
~~~~~~~~~~~~~~~~~~~

.. attributetable:: SyncWebhookMessage

.. autoclass:: SyncWebhookMessage()
    :members:

.. _discord_api_abcs:

Abstract Base Classes
-----------------------

An :term:`abstract base class` (also known as an ``abc``) is a class that models can inherit
to get their behaviour. **Abstract base classes should not be instantiated**.
They are mainly there for usage with :func:`isinstance` and :func:`issubclass`\.

This library has a module related to abstract base classes, in which all the ABCs are subclasses of
:class:`typing.Protocol`.

Snowflake
~~~~~~~~~~

.. attributetable:: discord.abc.Snowflake

.. autoclass:: discord.abc.Snowflake()
    :members:

User
~~~~~

.. attributetable:: discord.abc.User

.. autoclass:: discord.abc.User()
    :members:

PrivateChannel
~~~~~~~~~~~~~~~

.. attributetable:: discord.abc.PrivateChannel

.. autoclass:: discord.abc.PrivateChannel()
    :members:

GuildChannel
~~~~~~~~~~~~~

.. attributetable:: discord.abc.GuildChannel

.. autoclass:: discord.abc.GuildChannel()
    :members:

Messageable
~~~~~~~~~~~~

.. attributetable:: discord.abc.Messageable

.. autoclass:: discord.abc.Messageable()
    :members:
    :exclude-members: typing

    .. automethod:: discord.abc.Messageable.typing
        :async-with:

Connectable
~~~~~~~~~~~~

.. attributetable:: discord.abc.Connectable

.. autoclass:: discord.abc.Connectable()
    :members:

.. _discord_api_models:

Discord Models
---------------

Models are classes that are received from Discord and are not meant to be created by
the user of the library.

.. danger::

    The classes listed below are **not intended to be created by users** and are also
    **read-only**.

    For example, this means that you should not make your own :class:`User` instances
    nor should you modify the :class:`User` instance yourself.

    If you want to get one of these model classes instances they'd have to be through
    the cache, and a common way of doing so is through the :func:`utils.find` function
    or attributes of model classes that you receive from the events specified in the
    :ref:`discord-api-events`.

.. note::

    Nearly all classes here have :ref:`py:slots` defined which means that it is
    impossible to have dynamic attributes to the data classes.


ClientUser
~~~~~~~~~~~~

.. attributetable:: ClientUser

.. autoclass:: ClientUser()
    :members:
    :inherited-members:

User
~~~~~

.. attributetable:: User

.. autoclass:: User()
    :members:
    :inherited-members:
    :exclude-members: typing

    .. automethod:: typing
        :async-with:

AutoMod
~~~~~~~

.. attributetable:: AutoModRule

.. autoclass:: AutoModRule()
    :members:

.. attributetable:: AutoModAction

.. autoclass:: AutoModAction()
    :members:

Attachment
~~~~~~~~~~~

.. attributetable:: Attachment

.. autoclass:: Attachment()
    :members:

Asset
~~~~~

.. attributetable:: Asset

.. autoclass:: Asset()
    :members:
    :inherited-members:

Message
~~~~~~~

.. attributetable:: Message

.. autoclass:: Message()
    :members:
    :inherited-members:

DeletedReferencedMessage
~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: DeletedReferencedMessage

.. autoclass:: DeletedReferencedMessage()
    :members:


Reaction
~~~~~~~~~

.. attributetable:: Reaction

.. autoclass:: Reaction()
    :members:

Guild
~~~~~~

.. attributetable:: Guild

.. autoclass:: Guild()
    :members:

.. class:: BanEntry

    A namedtuple which represents a ban returned from :meth:`~Guild.bans`.

    .. attribute:: reason

        The reason this user was banned.

        :type: Optional[:class:`str`]
    .. attribute:: user

        The :class:`User` that was banned.

        :type: :class:`User`

.. class:: BulkBanResult

    A namedtuple which represents the result returned from :meth:`~Guild.bulk_ban`.

    .. versionadded:: 2.4

    .. attribute:: banned

        The list of users that were banned. The inner :class:`Object` of the list
        has the :attr:`Object.type` set to :class:`User`.

        :type: List[:class:`Object`]
    .. attribute:: failed

        The list of users that could not be banned. The inner :class:`Object` of the list
        has the :attr:`Object.type` set to :class:`User`.

        :type: List[:class:`Object`]

GuildPreview
~~~~~~~~~~~~

.. attributetable:: GuildPreview

.. autoclass:: GuildPreview
    :members:

ScheduledEvent
~~~~~~~~~~~~~~

.. attributetable:: ScheduledEvent

.. autoclass:: ScheduledEvent()
    :members:


Integration
~~~~~~~~~~~~

.. attributetable:: Integration

.. autoclass:: Integration()
    :members:

.. attributetable:: IntegrationAccount

.. autoclass:: IntegrationAccount()
    :members:

.. attributetable:: BotIntegration

.. autoclass:: BotIntegration()
    :members:

.. attributetable:: IntegrationApplication

.. autoclass:: IntegrationApplication()
    :members:

.. attributetable:: StreamIntegration

.. autoclass:: StreamIntegration()
    :members:

.. attributetable:: PartialIntegration

.. autoclass:: PartialIntegration()
    :members:

Member
~~~~~~

.. attributetable:: Member

.. autoclass:: Member()
    :members:
    :inherited-members:
    :exclude-members: typing

    .. automethod:: typing
        :async-with:

Spotify
~~~~~~~~

.. attributetable:: Spotify

.. autoclass:: Spotify()
    :members:

VoiceState
~~~~~~~~~~~

.. attributetable:: VoiceState

.. autoclass:: VoiceState()
    :members:

Emoji
~~~~~

.. attributetable:: Emoji

.. autoclass:: Emoji()
    :members:
    :inherited-members:

PartialEmoji
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: PartialEmoji

.. autoclass:: PartialEmoji()
    :members:
    :inherited-members:

Role
~~~~~

.. attributetable:: Role

.. autoclass:: Role()
    :members:

RoleTags
~~~~~~~~~~

.. attributetable:: RoleTags

.. autoclass:: RoleTags()
    :members:

PartialMessageable
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: PartialMessageable

.. autoclass:: PartialMessageable()
    :members:
    :inherited-members:

TextChannel
~~~~~~~~~~~~

.. attributetable:: TextChannel

.. autoclass:: TextChannel()
    :members:
    :inherited-members:
    :exclude-members: typing

    .. automethod:: typing
        :async-with:

ForumChannel
~~~~~~~~~~~~~

.. attributetable:: ForumChannel

.. autoclass:: ForumChannel()
    :members:
    :inherited-members:

Thread
~~~~~~~~

.. attributetable:: Thread

.. autoclass:: Thread()
    :members:
    :inherited-members:
    :exclude-members: typing

    .. automethod:: typing
        :async-with:

ThreadMember
~~~~~~~~~~~~~

.. attributetable:: ThreadMember

.. autoclass:: ThreadMember()
    :members:

VoiceChannel
~~~~~~~~~~~~~

.. attributetable:: VoiceChannel

.. autoclass:: VoiceChannel()
    :members:
    :inherited-members:

.. attributetable:: VoiceChannelEffect

.. autoclass:: VoiceChannelEffect()
    :members:
    :inherited-members:

.. class:: VoiceChannelEffectAnimation

    A namedtuple which represents a voice channel effect animation.

    .. versionadded:: 2.5

    .. attribute:: id

        The ID of the animation.

        :type: :class:`int`
    .. attribute:: type

        The type of the animation.

        :type: :class:`VoiceChannelEffectAnimationType`

.. attributetable:: VoiceChannelSoundEffect

.. autoclass:: VoiceChannelSoundEffect()
    :members:
    :inherited-members:

StageChannel
~~~~~~~~~~~~~

.. attributetable:: StageChannel

.. autoclass:: StageChannel()
    :members:
    :inherited-members:


StageInstance
~~~~~~~~~~~~~~

.. attributetable:: StageInstance

.. autoclass:: StageInstance()
    :members:

CategoryChannel
~~~~~~~~~~~~~~~~~

.. attributetable:: CategoryChannel

.. autoclass:: CategoryChannel()
    :members:
    :inherited-members:

DMChannel
~~~~~~~~~

.. attributetable:: DMChannel

.. autoclass:: DMChannel()
    :members:
    :inherited-members:
    :exclude-members: typing

    .. automethod:: typing
        :async-with:

GroupChannel
~~~~~~~~~~~~

.. attributetable:: GroupChannel

.. autoclass:: GroupChannel()
    :members:
    :inherited-members:
    :exclude-members: typing

    .. automethod:: typing
        :async-with:

PartialInviteGuild
~~~~~~~~~~~~~~~~~~~

.. attributetable:: PartialInviteGuild

.. autoclass:: PartialInviteGuild()
    :members:

PartialInviteChannel
~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: PartialInviteChannel

.. autoclass:: PartialInviteChannel()
    :members:

Invite
~~~~~~~

.. attributetable:: Invite

.. autoclass:: Invite()
    :members:

Template
~~~~~~~~~

.. attributetable:: Template

.. autoclass:: Template()
    :members:

WelcomeScreen
~~~~~~~~~~~~~~~

.. attributetable:: WelcomeScreen

.. autoclass:: WelcomeScreen()
    :members:

WelcomeChannel
~~~~~~~~~~~~~~~

.. attributetable:: WelcomeChannel

.. autoclass:: WelcomeChannel()
    :members:

WidgetChannel
~~~~~~~~~~~~~~~

.. attributetable:: WidgetChannel

.. autoclass:: WidgetChannel()
    :members:

WidgetMember
~~~~~~~~~~~~~

.. attributetable:: WidgetMember

.. autoclass:: WidgetMember()
    :members:
    :inherited-members:

Widget
~~~~~~~

.. attributetable:: Widget

.. autoclass:: Widget()
    :members:

StickerPack
~~~~~~~~~~~~~

.. attributetable:: StickerPack

.. autoclass:: StickerPack()
    :members:

StickerItem
~~~~~~~~~~~~~

.. attributetable:: StickerItem

.. autoclass:: StickerItem()
    :members:

Sticker
~~~~~~~~~~~~~~~

.. attributetable:: Sticker

.. autoclass:: Sticker()
    :members:

StandardSticker
~~~~~~~~~~~~~~~~

.. attributetable:: StandardSticker

.. autoclass:: StandardSticker()
    :members:

GuildSticker
~~~~~~~~~~~~~

.. attributetable:: GuildSticker

.. autoclass:: GuildSticker()
    :members:

BaseSoundboardSound
~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: BaseSoundboardSound

.. autoclass:: BaseSoundboardSound()
    :members:

SoundboardDefaultSound
~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: SoundboardDefaultSound

.. autoclass:: SoundboardDefaultSound()
    :members:

SoundboardSound
~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: SoundboardSound

.. autoclass:: SoundboardSound()
    :members:

ShardInfo
~~~~~~~~~~~

.. attributetable:: ShardInfo

.. autoclass:: ShardInfo()
    :members:

SessionStartLimits
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: SessionStartLimits

.. autoclass:: SessionStartLimits()
    :members:

SKU
~~~~~~~~~~~

.. attributetable:: SKU

.. autoclass:: SKU()
    :members:

Entitlement
~~~~~~~~~~~

.. attributetable:: Entitlement

.. autoclass:: Entitlement()
    :members:

Subscription
~~~~~~~~~~~~

.. attributetable:: Subscription

.. autoclass:: Subscription()
    :members:

RawMessageDeleteEvent
~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawMessageDeleteEvent

.. autoclass:: RawMessageDeleteEvent()
    :members:

RawBulkMessageDeleteEvent
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawBulkMessageDeleteEvent

.. autoclass:: RawBulkMessageDeleteEvent()
    :members:

RawMessageUpdateEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawMessageUpdateEvent

.. autoclass:: RawMessageUpdateEvent()
    :members:

RawReactionActionEvent
~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawReactionActionEvent

.. autoclass:: RawReactionActionEvent()
    :members:

RawReactionClearEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawReactionClearEvent

.. autoclass:: RawReactionClearEvent()
    :members:

RawReactionClearEmojiEvent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawReactionClearEmojiEvent

.. autoclass:: RawReactionClearEmojiEvent()
    :members:

RawIntegrationDeleteEvent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawIntegrationDeleteEvent

.. autoclass:: RawIntegrationDeleteEvent()
    :members:

RawThreadUpdateEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawThreadUpdateEvent

.. autoclass:: RawThreadUpdateEvent()
    :members:

RawThreadMembersUpdate
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawThreadMembersUpdate

.. autoclass:: RawThreadMembersUpdate()
    :members:

RawThreadDeleteEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawThreadDeleteEvent

.. autoclass:: RawThreadDeleteEvent()
    :members:

RawTypingEvent
~~~~~~~~~~~~~~~~

.. attributetable:: RawTypingEvent

.. autoclass:: RawTypingEvent()
    :members:

RawMemberRemoveEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawMemberRemoveEvent

.. autoclass:: RawMemberRemoveEvent()
    :members:

RawAppCommandPermissionsUpdateEvent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawAppCommandPermissionsUpdateEvent

.. autoclass:: RawAppCommandPermissionsUpdateEvent()
    :members:

RawPollVoteActionEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawPollVoteActionEvent

.. autoclass:: RawPollVoteActionEvent()
    :members:

RawPresenceUpdateEvent
~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RawPresenceUpdateEvent

.. autoclass:: RawPresenceUpdateEvent()
    :members:

PartialWebhookGuild
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: PartialWebhookGuild

.. autoclass:: PartialWebhookGuild()
    :members:

PartialWebhookChannel
~~~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: PartialWebhookChannel

.. autoclass:: PartialWebhookChannel()
    :members:

PollAnswer
~~~~~~~~~~

.. attributetable:: PollAnswer

.. autoclass:: PollAnswer()
    :members:

.. _discord_api_data:

MessageSnapshot
~~~~~~~~~~~~~~~~~

.. attributetable:: MessageSnapshot

.. autoclass:: MessageSnapshot
    :members:

ClientStatus
~~~~~~~~~~~~

.. attributetable:: ClientStatus

.. autoclass:: ClientStatus()
    :members:

Data Classes
--------------

Some classes are just there to be data containers, this lists them.

Unlike :ref:`models <discord_api_models>` you are allowed to create
most of these yourself, even if they can also be used to hold attributes.

Nearly all classes here have :ref:`py:slots` defined which means that it is
impossible to have dynamic attributes to the data classes.

The only exception to this rule is :class:`Object`, which is made with
dynamic attributes in mind.


Object
~~~~~~~

.. attributetable:: Object

.. autoclass:: Object
    :members:

Embed
~~~~~~

.. attributetable:: Embed

.. autoclass:: Embed
    :members:

AllowedMentions
~~~~~~~~~~~~~~~~~

.. attributetable:: AllowedMentions

.. autoclass:: AllowedMentions
    :members:

MessageReference
~~~~~~~~~~~~~~~~~

.. attributetable:: MessageReference

.. autoclass:: MessageReference
    :members:

PartialMessage
~~~~~~~~~~~~~~~~~

.. attributetable:: PartialMessage

.. autoclass:: PartialMessage
    :members:

MessageApplication
~~~~~~~~~~~~~~~~~~~

.. attributetable:: MessageApplication

.. autoclass:: MessageApplication
    :members:

RoleSubscriptionInfo
~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: RoleSubscriptionInfo

.. autoclass:: RoleSubscriptionInfo
    :members:

PurchaseNotification
~~~~~~~~~~~~~~~~~~~~~

.. attributetable:: PurchaseNotification

.. autoclass:: PurchaseNotification()
    :members:

GuildProductPurchase
+++++++++++++++++++++

.. attributetable:: GuildProductPurchase

.. autoclass:: GuildProductPurchase()
    :members:

Intents
~~~~~~~~~~

.. attributetable:: Intents

.. autoclass:: Intents
    :members:

MemberCacheFlags
~~~~~~~~~~~~~~~~~~

.. attributetable:: MemberCacheFlags

.. autoclass:: MemberCacheFlags
    :members:

ApplicationFlags
~~~~~~~~~~~~~~~~~

.. attributetable:: ApplicationFlags

.. autoclass:: ApplicationFlags
    :members:

ChannelFlags
~~~~~~~~~~~~~~

.. attributetable:: ChannelFlags

.. autoclass:: ChannelFlags
    :members:

AutoModPresets
~~~~~~~~~~~~~~

.. attributetable:: AutoModPresets

.. autoclass:: AutoModPresets
    :members:

AutoModRuleAction
~~~~~~~~~~~~~~~~~

.. attributetable:: AutoModRuleAction

.. autoclass:: AutoModRuleAction
    :members:

AutoModTrigger
~~~~~~~~~~~~~~

.. attributetable:: AutoModTrigger

.. autoclass:: AutoModTrigger
    :members:

File
~~~~~

.. attributetable:: File

.. autoclass:: File
    :members:

Colour
~~~~~~

.. attributetable:: Colour

.. autoclass:: Colour
    :members:

BaseActivity
~~~~~~~~~~~~~~

.. attributetable:: BaseActivity

.. autoclass:: BaseActivity
    :members:

Activity
~~~~~~~~~

.. attributetable:: Activity

.. autoclass:: Activity
    :members:

Game
~~~~~

.. attributetable:: Game

.. autoclass:: Game
    :members:

Streaming
~~~~~~~~~~~

.. attributetable:: Streaming

.. autoclass:: Streaming
    :members:

CustomActivity
~~~~~~~~~~~~~~~

.. attributetable:: CustomActivity

.. autoclass:: CustomActivity
    :members:

Permissions
~~~~~~~~~~~~

.. attributetable:: Permissions

.. autoclass:: Permissions
    :members:

PermissionOverwrite
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: PermissionOverwrite

.. autoclass:: PermissionOverwrite
    :members:

SystemChannelFlags
~~~~~~~~~~~~~~~~~~~~

.. attributetable:: SystemChannelFlags

.. autoclass:: SystemChannelFlags
    :members:

MessageFlags
~~~~~~~~~~~~

.. attributetable:: MessageFlags

.. autoclass:: MessageFlags
    :members:

PublicUserFlags
~~~~~~~~~~~~~~~

.. attributetable:: PublicUserFlags

.. autoclass:: PublicUserFlags
    :members:

MemberFlags
~~~~~~~~~~~~

.. attributetable:: MemberFlags

.. autoclass:: MemberFlags
    :members:

AttachmentFlags
~~~~~~~~~~~~~~~~

.. attributetable:: AttachmentFlags

.. autoclass:: AttachmentFlags
    :members:

RoleFlags
~~~~~~~~~~

.. attributetable:: RoleFlags

.. autoclass:: RoleFlags
    :members:

SKUFlags
~~~~~~~~~~~

.. attributetable:: SKUFlags

.. autoclass:: SKUFlags()
    :members:

EmbedFlags
~~~~~~~~~~

.. attributetable:: EmbedFlags

.. autoclass:: EmbedFlags()
    :members:

ForumTag
~~~~~~~~~

.. attributetable:: ForumTag

.. autoclass:: ForumTag
    :members:

Poll
~~~~

.. attributetable:: Poll

.. autoclass:: Poll
    :members:

PollMedia
~~~~~~~~~

.. attributetable:: PollMedia

.. autoclass:: PollMedia
    :members:

CallMessage
~~~~~~~~~~~~~~~~~~~

.. attributetable:: CallMessage

.. autoclass:: CallMessage()
    :members:


Exceptions
------------

The following exceptions are thrown by the library.

.. autoexception:: DiscordException

.. autoexception:: ClientException

.. autoexception:: LoginFailure

.. autoexception:: HTTPException
    :members:

.. autoexception:: RateLimited
    :members:

.. autoexception:: Forbidden

.. autoexception:: NotFound

.. autoexception:: DiscordServerError

.. autoexception:: InvalidData

.. autoexception:: GatewayNotFound

.. autoexception:: ConnectionClosed

.. autoexception:: PrivilegedIntentsRequired

.. autoexception:: InteractionResponded

.. autoexception:: MissingApplicationID

.. autoexception:: discord.opus.OpusError

.. autoexception:: discord.opus.OpusNotLoaded

Exception Hierarchy
~~~~~~~~~~~~~~~~~~~~~

.. exception_hierarchy::

    - :exc:`Exception`
        - :exc:`DiscordException`
            - :exc:`ClientException`
                - :exc:`InvalidData`
                - :exc:`LoginFailure`
                - :exc:`ConnectionClosed`
                - :exc:`PrivilegedIntentsRequired`
                - :exc:`InteractionResponded`
                - :exc:`MissingApplicationID`
            - :exc:`GatewayNotFound`
            - :exc:`HTTPException`
                - :exc:`Forbidden`
                - :exc:`NotFound`
                - :exc:`DiscordServerError`
                - :exc:`app_commands.CommandSyncFailure`
            - :exc:`RateLimited`
