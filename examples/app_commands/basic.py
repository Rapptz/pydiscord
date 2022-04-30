from typing import Optional

import discord
from discord import app_commands

MY_GUILD = discord.Object(id=0)  # replace with your guild id


class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents, application_id: int):
        super().__init__(intents=intents, application_id=application_id)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store it and work with it.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


intents = discord.Intents.default()

# In order to use a basic synchronization of the app commands in the setup_hook,
# you have replace the 0 with your bots application_id you find in the developer portal.
client = MyClient(intents=intents, application_id=0)


@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')


@client.tree.command()
async def hello(interaction: discord.Interaction):
    """Says hello!"""
    await interaction.response.send_message(f'Hi, {interaction.user.mention}')


@client.tree.command()
@app_commands.describe(
    first_value='The first value you want to add something to',
    second_value='The value you want to add to the first value',
)
async def add(interaction: discord.Interaction, first_value: int, second_value: int):
    """Adds two numbers together."""
    await interaction.response.send_message(f'{first_value} + {second_value} = {first_value + second_value}')


# To make an argument optional, you can either give it a supported default argument
# or you can mark it as Optional from the typing library. This example does both.
@client.tree.command()
@app_commands.describe(member='The member you want to get the joined date from, defaults to the user who uses the command')
async def joined(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    """Says when a member joined."""
    # If no member is explicitly provided then we use the command user here
    member = member or interaction.user

    await interaction.response.send_message(f'{member} joined in {member.joined_at}')


# A Context Menu is an app that can be run on a member or on a message by rightclicking.
# It always takes an interaction as its first parameter and a Member, Message or Union of both as its second parameter.

# This context menu only works for members
@client.tree.context_menu(name='Joindate')
async def show_join_date(interaction: discord.Interaction, member: discord.Member):
    # We're sending this message as ephemeral, so only the command user can see it
    await interaction.response.send_message(f'{member} joined in {member.joined_at}', ephemeral=True)


# This context menu only works for messages
@client.tree.context_menu(name='Wrong channel')
async def wrong_channel(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.send_message(f'{message.author.mention} To talk about this, please move to #off-topic')


client.run('token')
