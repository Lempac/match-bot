import os
import random
from re import M
import sqlite3
from types import NoneType
from typing import ItemsView, Literal, Optional, Text
import discord
from discord.ext import commands
import discord.ext.commands
from discord.ui import Select
from discord.ui.view import View
from discord import (
    AppCommandType,
    Attachment,
    Client,
    ClientUser,
    Color,
    Embed,
    Emoji,
    Game,
    Guild,
    Intents,
    Interaction,
    Member,
    Permissions,
    Role,
    SelectMenu,
    SelectOption,
    StageChannel,
    TextChannel,
    User,
    VoiceChannel,
    VoiceState,
    app_commands,
)
from discord.utils import MISSING
from dotenv import load_dotenv

import discord.ext

# loads .env file
load_dotenv()


con = sqlite3.connect("db.sqlite")
cur = con.cursor()
# cur.executescript(
# """
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


async def removePlayers(guild: Guild, game: int):
    players: list[tuple[int]] = cur.execute(
        f"SELECT player FROM games JOIN teams ON teams.game = games.id WHERE teams.game = {game}"
    ).fetchall()
    for player in players:
        insPlayer = guild.get_member(player[0])
        if type(insPlayer) is Member:
            await insPlayer.move_to(None)


async def rewardPlayers(interaction: Interaction, game: int, won: int):
    wonPlayers: list[tuple[int]] = cur.execute(
        f"SELECT player FROM games JOIN teams ON teams.game = games.id WHERE teams.game = {game} AND teams.id = {won}"
    ).fetchall()
    losePlayers: list[tuple[int]] = cur.execute(
        f"SELECT player FROM games JOIN teams ON teams.game = games.id WHERE teams.game = {game} AND teams.id = {2 if won == 1 else 1}"
    ).fetchall()
    constRewardElo = int(os.getenv("points_per_game") or 25)
    if type(interaction.guild) is Guild:
        for player in wonPlayers:
            insPlayer = interaction.guild.get_member(player[0])
            if type(insPlayer) is Member:
                changeElo(
                    player[0],
                    constRewardElo * 2 if insPlayer.premium_since else constRewardElo,
                )
                data: tuple[str, int] = cur.execute(
                    f"SELECT name, elo FROM users WHERE id = {player[0]}"
                ).fetchone()
                await changeNick(insPlayer, f"[ {data[1]} ] {data[0]}")
        for player in losePlayers:
            currentElo = cur.execute(
                f"SELECT elo FROM users WHERE id = {player[0]}"
            ).fetchone()
            insPlayer = interaction.guild.get_member(player[0])
            if type(insPlayer) is Member:
                changeElo(
                    player[0], 0 if constRewardElo > currentElo else -constRewardElo
                )
                data: tuple[str, int] = cur.execute(
                    f"SELECT name, elo FROM users WHERE id = {player[0]}"
                ).fetchone()
                await changeNick(insPlayer, f"[ {data[1]} ] {data[0]}")


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


class test(View):
    def __init__(self, members: list[Member], ch : TextChannel, timeout: float | NoneType = 180):
        super().__init__(timeout=timeout)
        self.select = Select(placeholder="Select a player", max_values=1, min_values=1, options=[ SelectOption(label=member.name, value=str(member.id)) for member in members])
        self.members = members
        self.select.callback = self.test
        self.add_item(self.select)
        discord.ui.UserSelect
    async def test(self, interaction: Interaction):
        if interaction.message is None or type(interaction.channel) is not TextChannel or client.user is None:
            return
        await interaction.message.delete()
        self.select.options = [SelectOption(label=member.name, value=str(member.id)) for member in self.members if member.id != self.select.values[0]]
        await interaction.channel.send(view=self)
        
        

@client.event
async def on_ready() -> None:
    if client.user is None:
        return
    await client.change_presence(
        status=discord.Status.online, activity=Game("Thinking...")
    )
    if client.application is None:
        return
    await client.application.edit(description="Valorant match making bot...(Alpha)")
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    cl = client.get_channel(1275578076364800013)
    if type(cl) is not TextChannel:
        return
    await cl.send(view=test(cl.members, cl))
    print("------")


class UserMenu(View):
    def __init__(
        self,
        vc1: VoiceChannel,
        vc2: VoiceChannel,
        lobby: VoiceChannel,
        game: int,
        timeout: float | None = 180,
    ):
        super().__init__(timeout=timeout)
        self.count = 2
        self.vc1 = vc1
        self.vc2 = vc2
        self.lobby = lobby
        self.game = game
        self.select = Select(placeholder="Select a player", min_values=1, max_values=1, options=[SelectOption(label=member.name, value=str(member.id), emoji=member.default_avatar.url ) for member in self.lobby.members])
        self.select.callback = self.user_select
        self.add_item(self.select)
    async def user_select(
        self, interaction: Interaction
    ) -> None:
        if interaction.guild is None or interaction.message is None:
            return

        if self.count == int(os.getenv("max_player") or 10):
            return await interaction.message.delete()
        await interaction.message.delete()
        self.count += 1
        userMember = interaction.guild.get_member(int(self.select.values[0]))
        if userMember is None:
            return
        if interaction.channel is self.vc1:
            cur.execute(
                f"INSERT INTO teams(id, game, player) VALUES (1, {self.game}, {userMember.id})"
            )
            cur.connection.commit()
            await userMember.move_to(self.vc1)
        elif interaction.channel is self.vc2:
            cur.execute(
                f"INSERT INTO teams(id, game, player) VALUES (2, {self.game}, {userMember.id})"
            )
            cur.connection.commit()
            await userMember.move_to(self.vc2)

        if len(self.lobby.members) != 0:
            return
        
        self.select.options = [SelectOption(label=member.name, value=str(member.id), emoji= member.default_avatar.url ) for member in self.lobby.members]

        if interaction.channel is self.vc1:
            await self.vc2.send("Select a team mate:", view=self)
        elif interaction.channel is self.vc2:
            await self.vc1.send("Select a team mate:", view=self)


@client.event
async def on_voice_state_update(
    member: Member, before: VoiceState, after: VoiceState
) -> None:
    if type(after.channel) is StageChannel:
        return

    if (
        before.channel is not None
        and before.channel.name.startswith("game#")
        and len(before.channel.members) == 0
    ):
        game = int(before.channel.name.split("#")[-1])
        data: list[tuple[int]] = cur.execute(
            f"SELECT teamleader1, teamleader2 FROM games WHERE id = {game}"
        ).fetchone()
        if member.id == data[0] or member.id == data[1]:
            await removePlayers(member.guild, game)
        cur.execute(
            f"UPDATE games SET state = 'voided' WHERE id = {game} AND state = 'playing'"
        )
        cur.connection.commit()
        await before.channel.delete()

    if (
        after.channel is not None
        and after.channel.name.startswith("game#")
        and isIngame(member.id) != int(after.channel.name.split("#")[-1])
    ):
        print(isIngame(member.id))
        await member.move_to(before.channel)

    if (
        after.channel is None
        or before.channel == after.channel
        or before.channel is not None
        and len(before.channel.members) >= len(after.channel.members)
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
    vc1 = await member.guild.create_voice_channel(f"game#team1#{currentGameNumber}")
    vc2 = await member.guild.create_voice_channel(f"game#team2#{currentGameNumber}")
    await lead1.move_to(vc1)
    await lead2.move_to(vc2)
    if type(after.channel) is VoiceChannel and len(after.channel.members) != 0:
        await random.choice([vc1, vc2]).send(
            "Select a team mate:",
            view=UserMenu(vc1, vc2, after.channel, currentGameNumber),
        )


@client.tree.command(description="Voids your current game...")
@app_commands.guild_only
async def void(interaction: Interaction):
    if interaction.guild is None:
        return
    game = isIngame(interaction.user.id)
    if game != -1:
        await interaction.response.defer()
        cur.execute("UPDATE games SET state = 'voided'")
        await removePlayers(interaction.guild, game)
        cur.connection.commit()
        if type(interaction.guild) is Guild and (
            type(interaction.channel) is TextChannel
            or type(interaction.channel) is VoiceChannel
        ):
            if interaction.guild.get_channel(interaction.channel.id) is not None:
                await interaction.followup.send("Done...")
    else:
        await interaction.response.send_message("No game to void right now...")


@client.tree.command(description="Submit current game with screenshot of results...")
@app_commands.describe(gamescreenshot="Screenshot of game result...")
@app_commands.guild_only
async def score(interaction: Interaction, gamescreenshot: Attachment) -> None:
    if interaction.guild is None:
        return
    if gamescreenshot.content_type not in ["image/png", "image/jpeg"]:
        return await interaction.response.send_message(
            "Unknown image type: " + str(gamescreenshot.content_type)
        )
    game = isIngame(interaction.user.id)
    if game == -1:
        return await interaction.response.send_message("You're not in a game...")
    data: tuple[int, int] = cur.execute(
        f"SELECT teamleader1, teamleader2 FROM games WHERE games.id = {game}"
    ).fetchone()
    if data[0] == interaction.user.id:
        cur.execute(
            f"UPDATE games SET state = 'finished', won = 1, score = '{gamescreenshot.url}' WHERE id = {game}"
        )
        await removePlayers(interaction.guild, game)
        await rewardPlayers(interaction, game, 1)
        cur.connection.commit()
    elif data[1] == interaction.user.id:
        cur.execute(
            f"UPDATE games SET state = 'finished', won = 2, score = '{gamescreenshot.url}' WHERE id = {game}"
        )
        await removePlayers(interaction.guild, game)
        await rewardPlayers(interaction, game, 2)
        cur.connection.commit()
    else:
        await interaction.response.send_message("Your not a team leader...")


class RegisterOnly(app_commands.CheckFailure):
    @staticmethod
    def RegisterOnly():
        def pre(interaction: Interaction):
            if (
                cur.execute(
                    f"SELECT id FROM users WHERE id = {interaction.user.id}"
                ).fetchone()
                == None
            ):
                raise RegisterOnly()
            return True

        return app_commands.check(pre)


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
        else await interaction.followup.send(
            "Done...but your to cool for nickname change..."
        )
    )


@elo.error
async def elo_error(interaction: Interaction, error: app_commands.AppCommandError):
    if isinstance(error, Exception):
        await interaction.followup.send("Member is not registered...")


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
    if (
        cur.execute(
            f"SELECT id FROM registerRole WHERE guild = {interaction.guild_id}"
        ).fetchone()
        is None
    ):
        role = await interaction.guild.create_role(name="Registered")
        cur.execute(
            f"INSERT INTO registerRole VALUES ({role.id}, {interaction.guild_id})"
        )
        cur.connection.commit()
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
        cur.connection.commit()
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
    cur.connection.commit()
    if type(interaction.user) is Member and type(interaction.guild) is Guild:
        (
            await interaction.response.send_message("Done...")
            if await changeNick(interaction.user, f"[ 0 ] {name}")
            else await interaction.response.send_message(
                "Done...but your to cool for nickname change..."
            )
        )
        regRole: int = cur.execute(
            f"SELECT id FROM registerRole WHERE guild = {interaction.guild_id}"
        ).fetchone()[0]
        role = interaction.guild.get_role(regRole)
        if role is not None:
            await interaction.user.add_roles(role)


@register.error
async def register_error(
    interaction: Interaction, error: app_commands.AppCommandError
) -> None:
    if isinstance(error, NotInRegister):
        return await interaction.response.send_message(
            "Only in register channel...", ephemeral=True
        )
    if isinstance(error, IsAllreadyRegistered):
        regRole: int = cur.execute(
            f"SELECT id FROM registerRole WHERE guild = {interaction.guild_id}"
        ).fetchone()[0]
        if (
            type(interaction.user) is Member
            and type(interaction.guild) is Guild
            and not interaction.user.get_role(regRole)
        ):
            role = interaction.guild.get_role(regRole)
            if role is not None:
                await interaction.user.add_roles(role)
        return await interaction.response.send_message(
            "You are all ready registered..."
        )


@client.tree.command(description="Show player stats...")
@app_commands.describe(member="Person that registered...")
async def stats(interaction: Interaction, member: Optional[User]) -> None:
    data: tuple[str | None, int | None, int, int, int] = cur.execute(
        f"SELECT users.name, users.elo, COUNT(games.id) AS played, COUNT(won) AS wins, COUNT(games.id) - COUNT(won) AS losses FROM users JOIN teams ON teams.player = users.id LEFT JOIN games ON games.id = teams.game AND games.state != 'voided' WHERE users.id = {(member or interaction.user).id}"
    ).fetchone()
    if data[0] is None:
        return await interaction.response.send_message("Member is not registered...")
    embed = Embed()
    embed.add_field(name="Name", value=data[0])
    embed.add_field(name="Elo", value=data[1])
    embed.add_field(name="Played", value=data[2])
    embed.add_field(name="Wons", value=data[3])
    embed.add_field(name="Losses", value=data[4])
    embed.set_author(name="STATS")
    embed.color = Color(0x00BFFF)
    embed.set_thumbnail(url=(member or interaction.user).display_avatar.url)
    await interaction.response.send_message(embed=embed)


# @stats.error
# async def stats_error(interaction: Interaction, error : app_commands.AppCommandError):
# if isinstance(error, ):


@client.tree.command(description="Show leaderboard...")
async def leaderboard(interaction: Interaction) -> None:
    data: list[tuple[int, int, int, int, int]] = cur.execute(
        "SELECT users.id, elo, COUNT(games.id) AS played, COUNT(won) AS wins, COUNT(games.id) - COUNT(won) AS losses FROM users JOIN teams ON teams.player = users.id LEFT JOIN games ON games.id = teams.game AND games.state != 'voided' GROUP BY users.id ORDER BY elo DESC, wins DESC, losses"
    ).fetchmany(5)

    embed = Embed()
    embed.title = "**Top 5 players:**"
    embed.description = "**―――――――――――――――――**\n"
    for i, player in enumerate(data):
        user = client.get_user(player[0])
        embed.description += (
            f"**{i+1}**.{ user.mention if type(user) is User else player[0]}\n"
        )
        embed.description += f"`Elo: {player[1]}`\n"
        embed.description += f"`Wins: {player[3]}`\n"
        embed.description += "**―――――――――――――――――**\n"
        # embed.add_field(name="Name", value=player[0])
        # embed.add_field(name="Elo", value=player[1])
        # embed.add_field(name="Played", value=player[2])
        # embed.add_field(name="Wins", value=player[3])
        # embed.add_field(name="Losses", value=player[4])
    embed.color = Color(0x00BFFF)
    await interaction.response.send_message(embed=embed)


@client.tree.command(description="Rename your self...")
@app_commands.guild_only
@app_commands.describe(name="New nickname...")
@RegisterOnly.RegisterOnly()
async def rename(interaction: Interaction, name: str):
    await interaction.response.defer()
    data: tuple[int] = cur.execute(
        f"SELECT elo FROM users WHERE id = {interaction.user.id}"
    ).fetchone()
    if type(interaction.user) is Member and await changeNick(
        interaction.user, f"[ {data[0]} ] " + name
    ):
        cur.execute(
            f"UPDATE users SET name = '{name}' WHERE id = {interaction.user.id}"
        )
        cur.connection.commit()
        await interaction.followup.send("Done...")
    else:
        return await interaction.followup.send(
            "But your to cool for nickname change..."
        )


@rename.error
async def rename_error(interaction: Interaction, error: app_commands.AppCommandError):
    if isinstance(error, RegisterOnly):
        return await interaction.response.send_message("Your not registered...")


if __name__ == "__main__":
    token = os.getenv("token")
    if type(token) is str:
        client.run(token)
