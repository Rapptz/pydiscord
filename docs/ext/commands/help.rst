.. currentmodule:: discord

.. _ext_commands_help:

The Help Command
===================

Using The Help Command
-------------------------

There is a help command made for you. It walks through your commands and formats them like
``<Command Name> Description``. Commands are then sorted into categories by their Cog. By default, your commands will be
in ``No Category``, which is always at the bottom of the commands list.

Here is a simple example of the default behaviour:

::

    An example bot to showcase the discord.ext.commands extension module.

    There are a number of utility commands being showcased here.

    MyCoolCog:
      cool   Says if a user is cool.
    No Category:
      add    Adds two numbers together.
      choose Chooses between multiple choices.
      help   Shows this message
      joined Says when a member joined.
      repeat Repeats a message multiple times.
      roll   Rolls a dice in NdN format.

    Type !help command for more info on a command.
    You can also type !help category for more info on a category.

You may want to send help if the user doesn't use a command correctly. Here is an example of how to do this:

.. code-block:: python3
    :caption: sos.py
    :emphasize-lines: 8, 10, 18

    from discord.ext import commands

    bot = commands.Bot(command_prefix='!', description="Nothing to worry about here.")

    @bot.command()
    async def sos(ctx, what: str = None):
        """Send Help!"""
        if not what:
            return await ctx.send_help(sos)
        await ctx.send('Sending help for {0}!'.format(what))
        await ctx.send_help(what)

    class MyCoolCog(commands.Cog):
        """It's OK, we saved the damsel."""

        @commands.command()
        async def damsel(self, ctx):
            """There's a damsel in distress!"""
            await ctx.send_help(self)  # TODO not sure about this change

    bot.add_cog(MyCoolCog())

:meth:`~.commands.Context.send_help` allows you to specify a :class:`~.commands.Command`, :class:`~commands.Cog`, or
even a regular string.

Let's take a look at this code step by step:

1. In the command ``sos``, there is a parameter called ``what``.
    - If the parameter is not passed, it will send help for itself a :meth:`~.commands.Command` instance.
    - If the parameter is passed, it will attempt to send help for a matching cog name or command.
      - Doing ``!sos damsel`` would invoke :meth:`~.commands.HelpCommand.send_command_help` with ``command`` being
        ``damsel``, and send the help for it.

2. In the cog ``MyCoolCog``, there is a docstring provided for help commands.

3. In the command ``damsel``, it will send help for the cog called ``MyCoolCog``.
    - This would send the docstring of ``MyCoolCog``, and its commands.

    ::

        It's OK, we saved the damsel.

        Commands:
          damsel There's a damsel in distress!

        Type !help command for more info on a command.
        You can also type !help category for more info on a category.

Replacing The Help Command
-----------------------------

If you don't like the default help command, you can replace the normal help command by setting
:attr:`~commands.Bot.help_command` to a subclass of :class:`~.commands.HelpCommand` or ``None`` to remove it.

Here is an example of an alternative help command you can set, :class:`~.commands.MinimalHelpCommand`

.. code-block:: python3
    :caption: mini_help_bot.py
    :emphasize-lines: 5

    from discord.ext import commands

    description = """Hey! I am your local test bot."""
    bot = commands.Bot(command_prefix='!', description=description,
                       help_command=commands.MinimalHelpCommand())

By default, the help command appears in ``No Category``, which can seem like a bit of a nuisance when categorising
commands. One way of doing this is by setting the :attr:`~.commands.DefaultHelpCommand.no_category`, an attribute also
found on :attr:`~.commands.MinimalHelpCommand`.

.. code-block:: python3
    :emphasize-lines: 4

    from discord.ext import commands

    bot = commands.Bot(command_prefix='!', description="There is no saviour.",
                       help_command=commands.DefaultHelpCommand(no_category='Help Me!'))

You can also set the :class:`~commands.Cog` of a help command, simply by setting :attr:`~commands.HelpCommand.cog`.
However, if you plan on having the ability to reload or disable extensions containing cogs, just setting it isn't wise
idea.

To counter this, you could set the new help command to default, during the teardown of an extension.

.. code-block:: python3
    :emphasize-lines: 22-23

    from discord.ext import commands


    class Help(commands.Cog):
        """This isn't the right place for help."""

        @commands.command()
        async def sos(self, ctx, what: str = None):
            """Send Help!"""
            if not what:
                return await ctx.send_help(self.sos)
            await ctx.send('Sending help for {0}!'.format(what))
            await ctx.send_help(what)


    def setup(bot):
        help_cog = Help()
        bot.add_cog(help_cog)
        bot.help_command = commands.DefaultHelpCommand(no_category='Help.')
        bot.help_command.cog = help_cog


    def teardown(bot):
        bot.help_command = commands.DefaultHelpCommand()

Here is an example of what you are able to do by subclassing :class:`~.commands.MinimalHelpCommand`:

.. code-block:: python3

    from discord.ext import commands

    class MyHelp(commands.MinimalHelpCommand):
        def __init__(self):
            super().__init__(no_category='Misc')

        def add_bot_commands_formatting(self, commands, heading):
            if commands:
                joined = ', '.join('`{0}`'.format(c.name) for c in commands)
                self.paginator.add_line('Category: [__**%s**__]' % heading)
                self.paginator.add_line(joined)

    bot = commands.Bot(command_prefix='!', help_command=MyHelp())

Writing A Help Command
-------------------------

For this tutorial, we will be using the standard :class:`~.commands.HelpCommand`.


The Help Command Name
~~~~~~~~~~~~~~~~~~~~~

If you would like to use a different name for the help command, there is an option to change it:

.. code-block:: python3

    class MyHelpCommand(commands.HelpCommand):
        def __init__(self):
            super().__init__(command_attrs={'name': 'commands'})

This allows the help command to be called via ``!commands``.


Bot Help
~~~~~~~~

The main help sent when ``!help`` is called, this calls :meth:`~discord.ext.commands.HelpCommand.send_bot_help`.

This is the default implementation:

::

    This is my cool bot made in discord.py!                          ]--- Description

    Help:                                                            ]--- Cog Name
      sos     Send Help!                                             ]--- Cog Command
    No Category:                                                     ]--- No Cog
      add     Adds two numbers together.                             \
      choose  Chooses between multiple choices. This will get cut...  |
      cool    Says if a user is cool.                                 |
      help    Shows this message.                                     |--- No Cog Commands
      joined  Says when a member joined.                              |
      repeat  Repeats a message multiple times.                       |
      roll    Rolls a dice in NdN format.                            /

    Type ?help command for more info on a command.                   \___ Ending Note
    You can also type ?help category for more info on a category.    /

To make it a little easier, it should start off with:

.. code-block:: python3

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot


Description
+++++++++++

By default, the description is set when :class:`commands.Bot` is instantiated, with the
``description`` keyword argument: ``commands.Bot(description='Hey! This is my Cool Bot:tm:')``.

However, it is possible to disregard that, as it is only used in :meth:`~commands.DefaultHelpCommand.send_bot_help`.
This can be done by adding the line ``self.paginator.add_line('My Description!', empty=True)`` to the end of
the function.

In the default help command, the description is added first, then the category and commands are added.
The position of the description is entirely your choice.


Cog Name
++++++++

The cog name is usually determined by :attr:`~commands.Cog.qualified_name` - or ``No Category`` - and is formatted to
be: ``My Cog:`` or ``No Category:``.

In the default help command it is done as so:

.. code-block:: python3
    :emphasize-lines: 1-5

        no_category = '\u200b{0.no_category}:'.format(self)

        def get_category(command, *, no_category=no_category):
            cog = command.cog
            return cog.qualified_name + ':' if cog is not None else no_category

        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        max_size = self.get_max_size(filtered)
        to_iterate = itertools.groupby(filtered, key=get_category)

self.no_category is set to ``No Category:`` when you instantiate :class:`commands.DefaultHelpCommand`, however you can
pass ``no_category='...'`` to the HelpCommand constructor to this. The next local function, ``get_category``
determines :attr:`commands.Command.cog`'s name via :attr:`commands.Cog.qualified_name`.


Command
+++++++

