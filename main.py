from enum import Enum
import os
from typing import *

from discord import *
from dotenv import load_dotenv, set_key

# loads .env file
load_dotenv()

MY_GUILD = Object(id=os.getenv("guild_id"))  # edit .env to replace with your guild id


class MyClient(Client):
    def __init__(self, *, intents: Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


client = MyClient(intents=Intents.default())


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("------")


@client.event
async def on_voice_state_update(member: Member, before: VoiceState, after: VoiceState):
    if after.channel is None or after.channel.id != int(os.getenv("lobby") or 0):
        return
    players = after.channel.members
    if len(players) < int(os.getenv("max_players") or 10):
        return


@client.tree.command(description="Voids your current game...")
@app_commands.guild_only
async def void(interaction: Interaction):
    await interaction.response.send_message("test")


@client.tree.command(description="Add or remove elo...")
@app_commands.describe(
    option="Option want to do...",
    amount="Amount of elo...",
    member="Member to change...",
)
@app_commands.guild_only
@app_commands.default_permissions(**dict(Permissions.elevated()))
async def elo(
    interaction: Interaction,
    option: Literal["give", "remove"],
    amount: int,
    member: Member,
):
    pass


@client.tree.command(description="Setup up server for usage...")
@app_commands.default_permissions(**dict(Permissions.elevated()))
@app_commands.guild_only
async def setup(interaction: Interaction):
    if os.getenv("lobby") is None:
        pass


@client.tree.command(description="Registers user for games...")
@app_commands.describe(name="Username...")
@app_commands.guild_only
async def register(interaction: Interaction, name: str):
    pass


# To make an argument optional, you can either give it a supported default argument
# or you can mark it as Optional from the typing standard library. This example does both.
# @client.tree.command()
# @app_commands.describe(member='The member you want to get the joined date from; defaults to the user who uses the '
#                               'command')
# async def joined(interaction: Interaction, member: Optional[Member] = None):
#     """Says when a member joined."""
#     # If no member is explicitly provided then we use the command user here
#     member = member or interaction.user
#
#     # The format_dt function formats the date time into a human-readable representation in the official client
#     await interaction.response.send_message(f'{member} joined {utils.format_dt(member.joined_at)}')


# A Context Menu command is an app command that can be run on a member or on a message by
# accessing a menu within the client, usually via right-clicking.
# It always takes an interaction as its first parameter and a Member or Message as its second parameter.

# This context menu command only works on members
# @client.tree.context_menu(name='Show Join Date')
# async def show_join_date(interaction: discord.Interaction, member: discord.Member):
#     # The format_dt function formats the date time into a human-readable representation in the official client
#     await interaction.response.send_message(f'{member} joined at {discord.utils.format_dt(member.joined_at)}')


# This context menu command only works on messages
# @client.tree.context_menu(name='Report to Moderators')
# async def report_message(interaction: discord.Interaction, message: discord.Message):
#     # We're sending this response message with ephemeral=True, so only the command executor can see it
#     await interaction.response.send_message(
#         f'Thanks for reporting this message by {message.author.mention} to our moderators.', ephemeral=True
#     )
#
#     # Handle report by sending it into a log channel
#     log_channel = interaction.guild.get_channel(0)  # replace with your channel id
#
#     embed = discord.Embed(title='Reported Message')
#     if message.content:
#         embed.description = message.content
#
#     embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
#     embed.timestamp = message.created_at
#
#     url_view = discord.ui.View()
#     url_view.add_item(discord.ui.Button(label='Go to Message', style=discord.ButtonStyle.url, url=message.jump_url))
#
#     await log_channel.send(embed=embed, view=url_view)


client.run(os.getenv("token"))
