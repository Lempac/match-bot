import random
from typing import cast
import discord
from discord.ui import View, Select
from discord import (
    Attachment,
    Guild,
    Interaction,
    Member,
    SelectOption,
    StageChannel,
    TextChannel,
    VoiceChannel,
    VoiceState,
    app_commands,
)
from discord.ext import commands
from cogs.base import syncRanks
from main import changeElo, changeNick, cur, listAllChannels


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
    constRewardElo: int = cur.execute("SELECT points_per_game FROM config").fetchone()[
        0
    ]
    constFreeMul: int = cur.execute("SELECT free_multiplier FROM config").fetchone()[
        0
    ]
    constPremMul: int = cur.execute("SELECT premium_multiplier FROM config").fetchone()[
        0
    ]
    if type(interaction.guild) is Guild:
        for player in wonPlayers:
            insPlayer = interaction.guild.get_member(player[0])
            if type(insPlayer) is Member:
                changeElo(
                    player[0],
                    constRewardElo * constPremMul if insPlayer.premium_since else constRewardElo * constFreeMul,
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
    syncRanks()


class Game(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ) -> None:
        if type(after.channel) is StageChannel:
            return
        if before.channel is not None and before.channel.name.startswith("game#"):
            game = int(before.channel.name.split("#")[-1])
            data: list[tuple[int]] = cur.execute(
                f"SELECT teamleader1, teamleader2 FROM games WHERE id = {game}"
            ).fetchone()
            if member.id == data[0] or member.id == data[1]:
                await removePlayers(member.guild, game)
            else:
                return
            cur.execute(
                f"UPDATE games SET state = 'voided' WHERE id = {game} AND state = 'playing'"
            )
            cur.connection.commit()
            await before.channel.delete()
        if after.channel is not None and (
            (
                (after.channel.id in listAllChannels("lobby"))
                and cur.execute(
                    f"SELECT id FROM users WHERE id = {member.id}"
                ).fetchone()
                is None
            )
            or (
                after.channel.name.startswith("game#")
                and (
                    cur.execute(
                        f"SELECT id FROM users WHERE id = {member.id}"
                    ).fetchone()
                    is None
                    or isIngame(member.id) != int(after.channel.name.split("#")[-1])
                )
            )
        ):
            await member.move_to(before.channel)

        if (
            after.channel is None
            or len(after.channel.members)
            != cur.execute("SELECT max_player FROM config").fetchone()[0]
            or not after.channel.id in listAllChannels("lobby")
        ):
            return
        players = after.channel.members
        lead1, lead2 = random.sample(players, 2)
        cur.execute(
            f"""INSERT INTO games(teamleader1, teamleader2) VALUES (
                {lead1.id},
                {lead2.id}
            )"""
        )
        cur.connection.commit()
        currentGameNumber: int = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
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
        await vc1.send("Use: `/pick` `username` for adding person to your team")

    @app_commands.command(description="Swap player in team...")
    @app_commands.guild_only
    async def swap(self, interaction: Interaction, who: Member, to: Member):
        return await interaction.response.send_message("Work in progress...", ephemeral=True)

    @app_commands.command(description="Select player...")
    @app_commands.guild_only
    async def pick(self, interaction: Interaction, player: Member):
        user = interaction.user
        gameID = isIngame(user.id)
        if gameID == -1:
            return await interaction.response.send_message(
                "Your not ingame...", ephemeral=True
            )
        teamlead1, teamlead2 = cast(
            tuple[int, int],
            cur.execute(
                f"SELECT teamleader1, teamleader2 FROM games JOIN teams ON teams.game = games.id WHERE games.id = {gameID}"
            ).fetchone(),
        )
        if player == teamlead1 or player == teamlead2:
            return await interaction.response.send_message(
                "This person is all ready a team leader in the game..."
            )
        players: list[tuple[int, int]] = cur.execute(
            f"SELECT id, player FROM teams WHERE game = {gameID}"
        ).fetchall()
        if (
            len(players)
            == cur.execute("SELECT max_player FROM config").fetchone()[0] * 2
        ):
            return await interaction.response.send_message(
                "Game all ready has max players...", ephemeral=True
            )
        teamCount1, teamCount2 = 0, 0
        for playerInTeam in players:
            if player.id == playerInTeam[1]:
                return await interaction.response.send_message(
                    "Already in team...", ephemeral=True
                )
            teamCount1 += 1 if playerInTeam[0] == 1 else 0
            teamCount2 += 1 if playerInTeam[0] == 2 else 0
        if user.id == teamlead1:
            if teamCount1 > teamCount2:
                return await interaction.response.send_message(
                    "Waiting for other team...", ephemeral=True
                )
            else:
                if type(user) is not Member or user.voice is None:
                    return await interaction.response.send_message(
                        "How???", ephemeral=True
                    )
                cur.execute(
                    f"INSERT INTO teams(id, game, player) VALUES (1, {gameID}, {player.id})"
                )
                cur.connection.commit()
                await player.move_to(user.voice.channel)
                await interaction.response.send_message("Done...", ephemeral=True)
                await cast(
                    VoiceChannel,
                    discord.utils.find(
                        lambda ch: ch.name == f"game#team2#{gameID}",
                        user.guild.voice_channels,
                    ),
                ).send("Team 2 leader `/pick` now...")

        elif user.id == teamlead2:
            if teamCount2 >= teamCount1:
                return await interaction.response.send_message(
                    "Waiting for other team...", ephemeral=True
                )
            else:
                if type(user) is not Member or user.voice is None:
                    return await interaction.response.send_message(
                        "How???", ephemeral=True
                    )
                cur.execute(
                    f"INSERT INTO teams(id, game, player) VALUES (2, {gameID}, {player.id})"
                )
                cur.connection.commit()
                await player.move_to(user.voice.channel)
                await interaction.response.send_message("Done...", ephemeral=True)
                await cast(
                    VoiceChannel,
                    discord.utils.find(
                        lambda ch: ch.name == f"game#team1#{gameID}",
                        user.guild.voice_channels,
                    ),
                ).send("Team 1 leader `/pick` now...")
        else:
            await interaction.response.send_message(
                "Your not a games teamleader...", ephemeral=True
            )

    @app_commands.command(description="Voids your current game...")
    @app_commands.guild_only
    async def void(self, interaction: Interaction):
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

    @app_commands.command(
        description="Submit current game with screenshot of results..."
    )
    @app_commands.describe(gamescreenshot="Screenshot of game result...")
    @app_commands.guild_only
    async def score(self, interaction: Interaction, gamescreenshot: Attachment) -> None:
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
        
        channelid: set[int] = (set([x.id for x in interaction.guild.text_channels]) & set(listAllChannels("score")))
        if len(channelid) == 0:
            return 
        else:
            channelid: int = channelid[0]
        res = discord.Embed(title= "Team 1 won:" if data[0] == interaction.user.id else "Team 2 won:")
        res.set_image(gamescreenshot.url)
        interaction.guild.get_channel(channelid).send(embed=res)


async def setup(bot: commands.Bot):
    await bot.add_cog(Game(bot))


async def teardown(bot: commands.Bot):
    print("Game unloaded!")
