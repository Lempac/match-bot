from ast import In
from enum import member
import os
import random
import sqlite3
from typing import Literal, Optional
import discord
from discord.ext import commands
import discord.ext.commands
from discord.ui.view import View
from discord import (
    AppCommandType,
    Attachment,
    ClientUser,
    Color,
    Embed,
    Guild,
    Intents,
    Interaction,
    Member,
    Permissions,
    TextChannel,
    User,
    VoiceChannel,
    VoiceState,
    app_commands,
)
from dotenv import load_dotenv

import discord.ext

# loads .env file
load_dotenv()


con = sqlite3.connect("db.sqlite")
cur = con.cursor()
# cur.executescript(
#     """
#     DROP TABLE IF EXISTS teams;
#     DROP TABLE IF EXISTS games;
# """
# )

print("Creating a database...")
with open("create_database.sql", "r") as sql_file:
    sql_script = sql_file.read()

cur.executescript(sql_script)


async def addLobby(guild: discord.Guild) -> None:
    lobvc = await guild.create_voice_channel("lobby")
    cur.execute(
        f"""
        INSERT INTO channels(id, type) VALUES ({lobvc.id}, 'lobby')
        """
    )


def listAllChannels(type: Literal["lobby", "register"]) -> list[int]:
    return [
        x[0]
        for x in cur.execute(
            f"SELECT id FROM channels WHERE type = '{type}'"
        ).fetchall()
    ]


async def changeNick(member: Member, name: str) -> bool:
    if member.id != member.guild.owner_id:
        await member.edit(nick=name)
        return True
    else:
        return False


def setElo(id: int, amount: int) -> None:
    cur.execute(f"UPDATE users SET elo = {amount} WHERE id = {id}")
    cur.connection.commit()


def changeElo(id: int, amount: int) -> None:
    setElo(
        id, cur.execute(f"SELECT elo FROM users WHERE id = {id}").fetchone()[0] + amount
    )


def isIngame(id: int) -> int:
    data: tuple[int] = cur.execute(
        f"SELECT games.id FROM users JOIN teams ON teams.player = users.id JOIN games ON games.id = teams.game WHERE state = 'playing' AND users.id = {id}"
    ).fetchone()
    return -1 if data == None else data[0]


MY_GUILD = discord.Object(
    id=os.getenv("guild_id") or 0
)  # edit .env to replace with your guild id


class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


client = MyClient(intents=Intents(Intents.default().value | Intents.members.flag))


@client.event
async def on_ready() -> None:
    if type(client.user) is ClientUser:
        print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("------")


class UserMenu(View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select a player",
        min_values=1,
        max_values=1,
    )
    async def user_select(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect
    ) -> None:
        await interaction.response.defer()
        await interaction.followup.send(
            f"You selected {select.values[0]}", ephemeral=True
        )


@client.event
async def on_voice_state_update(
    member: Member, before: VoiceState, after: VoiceState
) -> None:
    if (
        before.channel is not None
        and before.channel.name.startswith("game#")
        and len(before.channel.members) == 0
    ):
        await before.channel.delete()

    if (
        after.channel is None
        or before.channel == after.channel
        or before.channel is not None and len(before.channel.members) >= len(after.channel.members)
        or not after.channel.id in listAllChannels("lobby")
    ):
        return
    players = after.channel.members
    if len(players) < int(os.getenv("max_player") or 10):
        return
    lead1, lead2 = random.sample(players, 2)
    cur.execute(
        f"""INSERT INTO games(teamleader1, teamleader2) VALUES (
            {lead1.id},
            {lead2.id}
        )"""
    )
    cur.connection.commit()
    currentGameNumber = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    cur.execute(
        f"INSERT INTO teams(id, game, player) VALUES (1, {currentGameNumber}, {lead1.id})"
    )
    cur.execute(
        f"INSERT INTO teams(id, game, player) VALUES (2, {currentGameNumber}, {lead2.id})"
    )
    cur.connection.commit()
    vc = await member.guild.create_voice_channel(f"game#{currentGameNumber}")
    for player in players:
        await player.move_to(vc)
    await vc.send("", view=UserMenu())


@client.tree.command(description="Voids your current game...")
@app_commands.guild_only
async def void(interaction: Interaction):
    game = isIngame(interaction.user.id)
    if game != -1:
        await interaction.response.defer()
        cur.execute("UPDATE games SET state = 'voided'")
        players: list[tuple[int]] = cur.execute(
            f"SELECT player FROM games JOIN teams ON teams.game = games.id WHERE teams.game = {game}"
        ).fetchall()
        if type(interaction.guild) is Guild:
            for player in players:
                insPlayer = interaction.guild.get_member(player[0])
                if type(insPlayer) is Member:
                    await insPlayer.move_to(None)
            cur.connection.commit()
            if type(interaction.channel) is TextChannel or type(interaction.channel) is VoiceChannel:
                if interaction.guild.get_channel(interaction.channel.id) is not None:
                    await interaction.followup.send("Done...")
        else:
            await interaction.followup.send("How?")
    else:
        await interaction.response.send_message("No game to void right now...")


@client.tree.command(description="Submit current game with screenshot of results...")
@app_commands.describe(gamescreenshot="Screenshot of game result...")
@app_commands.guild_only
async def score(interaction: Interaction, gamescreenshot: Attachment) -> None:
    if gamescreenshot.content_type not in ["image/png", "image/jpeg"]:
        await interaction.response.send_message(
            "Unknown image type: " + str(gamescreenshot.content_type)
        )
    await interaction.response.send_message("Work in progress...")


# @client.tree.command(description="Start a vote to make new game...")
# @app_commands.guild_only
# async def redo(interaction: Interaction) -> None:
#     game = isIngame(interaction.user.id)
#     if game != -1:
#         await interaction.response.send_message("Work in progress...")
#     else:
#         await interaction.response.send_message("No game to redo right now...")


@client.tree.command(description="Add or remove elo...")
@app_commands.describe(
    option="Option want to do...",
    amount="Amount of elo...",
    member="Member to change...",
)
@app_commands.guild_only
@app_commands.default_permissions(**dict(Permissions.elevated()))
@app_commands.choices(
    option=[
        app_commands.Choice(name="give", value="give"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="set", value="set"),
    ]
)
async def elo(
    interaction: Interaction,
    option: str,
    amount: int,
    member: Member,
) -> None:
    await interaction.response.defer()
    if option == "give":
        changeElo(member.id, amount)
    elif option == "remove":
        changeElo(member.id, -amount)
    elif option == "set":
        setElo(member.id, amount)
    data: tuple[str, int] = cur.execute(
        f"SELECT name, elo FROM users WHERE id = {member.id}"
    ).fetchone()

    (
        await interaction.followup.send("Done...")
        if await changeNick(member, f"[ {data[1]} ] {data[0]}")
        else await interaction.response.send_message(
            "Done...but your to cool for nickname change..."
        )
    )


@client.tree.command(description="Setup up server for usage...")
@app_commands.default_permissions(**dict(Permissions.elevated()))
@app_commands.choices(
    options=[
        app_commands.Choice(name="addlobby", value="addlobby"),
    ]
)
@app_commands.guild_only
async def setup(interaction: Interaction, options: Optional[str]) -> None:
    if interaction.guild is None:
        return
    await interaction.response.defer()

    if options == "addlobby":
        await addLobby(interaction.guild)

    if options is None and not len(
        set([x.id for x in interaction.guild.text_channels])
        & set(listAllChannels("register"))
    ):
        regchannel = await interaction.guild.create_text_channel("register")
        cur.execute(
            f"""
            INSERT INTO channels(id, type) VALUES ({regchannel.id}, 'register')
            """
        )
    if options is None and not len(
        set([x.id for x in interaction.guild.voice_channels])
        & set(listAllChannels("lobby"))
    ):
        await addLobby(interaction.guild)
    cur.connection.commit()
    await interaction.followup.send("Done...")


class NotInRegister(app_commands.CheckFailure):
    @staticmethod
    def NotInRegister():
        def pre(interaction: Interaction):
            if not interaction.channel_id in listAllChannels("register"):
                raise NotInRegister()
            return True

        return app_commands.check(pre)


class IsAllreadyRegistered(app_commands.CheckFailure):
    @staticmethod
    def IsAllreadyRegistered():
        def pre(interaction: Interaction):
            if (
                cur.execute(
                    f"SELECT id FROM users WHERE id = {interaction.user.id}"
                ).fetchone()
                != None
            ):
                raise IsAllreadyRegistered()
            return True

        return app_commands.check(pre)


@client.tree.command(description="Registers user for games...")
@app_commands.describe(name="Username...")
@NotInRegister.NotInRegister()
@IsAllreadyRegistered.IsAllreadyRegistered()
@app_commands.guild_only
async def register(interaction: Interaction, name: str) -> None:
    cur.execute(
        f"INSERT INTO users(id, name, elo) VALUES ({interaction.user.id}, '{name}', 0)"
    )
    if type(interaction.user) is Member:
        cur.connection.commit()

        (
            await interaction.followup.send("Done...")
            if await changeNick(interaction.user, f"[ 0 ] {name}")
            else await interaction.response.send_message(
                "Done...but your to cool for nickname change..."
            )
        )


@register.error
async def register_error(
    interaction: Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, NotInRegister):
        return await interaction.response.send_message(
            "Only in register channel...", ephemeral=True
        )
    if isinstance(error, IsAllreadyRegistered):
        return await interaction.response.send_message(
            "You are all ready registered..."
        )


@client.tree.command(description="Show player stats...")
@app_commands.describe(member="Person that registered...")
@app_commands.check(
    lambda x: cur.execute(f"SELECT id FROM users WHERE id = {x.user.id}") != ()
)
@app_commands.guild_only
async def stats(interaction: Interaction, member: Optional[Member]) -> None:
    # if member is None and type(interaction.user) is Member:
    #     member = interaction.user
    #     data = cur.execute(
    #         f"SELECT name, elo, count(players) AS played, count(won) AS wins, COUNT(players) - COUNT(won) AS losses FROM users JOIN games ON users.id = games.players WHERE id = {member.id}"
    #     ).fetchone()
    #     await interaction.response.send_message(data)
    # embed = Embed()
    # embed.description = f"- {data[1]}\n- {data[2]} \n- ɢᴀᴍᴇꜱ ᴘʟᴀʏᴇᴅ \n- ᴡɪɴꜱ\n- ʟᴏꜱꜱᴇꜱ"
    # embed.set_author(name="STATS")
    # embed.color = Color(0x00bfff)
    # await interaction.followup.send(embed=embed)
    await interaction.response.send_message("Work in progress...")


@client.tree.command(description="Show leaderboard...")
async def leaderboard(interaction: Interaction) -> None:
    # data: list[tuple[str, int, int, int, int]] = cur.execute(
    #     "SELECT name, elo, played, won, lost FROM users JOIN teams ON teams.player = users.id JOIN games ON games.id = teams.game"
    # ).fetchmany(5)

    # embed = Embed()
    # embed.title = "Top 5 players:"
    # for player in data:
    #     for field in player:
    #         embed.add_field(name=)
    await interaction.response.send_message("Work in progress...")


if __name__ == "__main__":
    token = os.getenv("token")
    if type(token) is str:
        client.run(token)
