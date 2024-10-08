from types import NoneType
from typing import Optional
import discord
from discord.ui import View, Select
from discord import (
    Color,
    Embed,
    Guild,
    Interaction,
    Member,
    Permissions,
    SelectOption,
    TextChannel,
    User,
    VoiceChannel,
    app_commands,
)
from discord.ext import commands
from main import (
    MY_GUILD,
    CustomBot,
    IsAllreadyRegistered,
    NotInRegister,
    RegisterOnly,
    changeElo,
    changeNick,
    cur,
    listAllChannels,
    setElo,
)


async def addLobby(guild: discord.Guild) -> None:
    lobvc = await guild.create_voice_channel("lobby")
    cur.execute(
        f"""
        INSERT INTO channels(id, type) VALUES ({lobvc.id}, 'lobby')
        """
    )


class test(View):
    def __init__(
        self,
        bot: commands.Bot,
        ch: VoiceChannel,
        timeout: float | NoneType = 180,
    ):
        super().__init__(timeout=timeout)
        self.select = Select(
            placeholder="Select a player",
            max_values=1,
            min_values=1,
            options=[
                SelectOption(
                    label=(member.nick or member.display_name or member.name),
                    value=str(member.id),
                )
                for member in ch.members
            ],
        )
        self.bot = bot
        self.ch = ch
        self.select.callback = self.test
        self.add_item(self.select)

    async def test(self, interaction: Interaction):
        if (
            interaction.message is None
            or self.bot.user is None
        ):
            return
        await interaction.message.delete()
        print(self.ch.members)
        self.select.options = [
            SelectOption(
                label=(member.nick or member.display_name or member.name),
                value=str(member.id),
            )
            for member in self.ch.members
        ]
        if type(interaction.channel) is not VoiceChannel and type(interaction.channel) is not TextChannel:
            return
        await interaction.channel.send(view=self)


class Base(commands.Cog):
    def __init__(self, bot: CustomBot) -> None:
        self.bot = bot
    
    setupGroup = app_commands.Group(name="setup", description="Setup up server for usage...", default_permissions=Permissions.elevated(), guild_only=True)
    
    @app_commands.command()
    @app_commands.default_permissions(**dict(Permissions.elevated()))
    async def sync(self, interaction: Interaction) -> None:
        """Sync commands"""
        self.bot.tree.clear_commands(guild=MY_GUILD)
        # if MY_GUILD is not None:
            # self.bot.tree.copy_global_to(guild=MY_GUILD)
        synced = await self.bot.tree.sync(guild=MY_GUILD) 
        await self.bot.tree.sync()
        await interaction.response.send_message(f"Synced {len(synced)} commands globally", ephemeral=True)

    @app_commands.command(description="testing only")
    @app_commands.guild_only
    async def testing(self, interaction: Interaction):
        # print(interaction.guild.me.name)
        gl = self.bot.get_guild(1275578076364800010)
        if gl is None:
            return
        vc = gl.voice_channels[1]
        if vc.name != "lobby":
            return
        # await vc.send(view=test(self.bot, vc))
        mb = gl.get_member(1275577286816694375)
        if mb is None:
            return
        await vc.connect()
        await interaction.response.send_message("Done", ephemeral=True)

    @setupGroup.command()
    async def init(self, interaction: Interaction) -> None:
        if interaction.guild is None:
            return
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
        if not len(
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
        if not len(
            set([x.id for x in interaction.guild.voice_channels])
            & set(listAllChannels("lobby"))
        ):
            await addLobby(interaction.guild)
        cur.connection.commit()
        await interaction.response.send_message("Done...", ephemeral=True)


    @setupGroup.command()
    async def addlobby(
        self, interaction: Interaction
    ) -> None:
        if interaction.guild is None:
            return
        await addLobby(interaction.guild)
        await interaction.response.send_message("Done...")

    @setupGroup.command()
    async def addrank(self, interaction: Interaction) -> None:
        await interaction.response.send_message("Work in progress...", ephemeral=True)

    @setupGroup.command()
    async def setmaxplayers(self, interaction: Interaction, amount: int):
        cur.execute(f"REPLACE INTO config(id, max_player) VALUES (0, {amount})")
        cur.connection.commit()
        await interaction.response.send_message("Done...")

    @setupGroup.command()
    async def setpointspergame(self, interaction: Interaction, amount: int):
        cur.execute(f"REPLACE INTO config(id, points_per_game) VALUES (0, {amount})")
        cur.connection.commit()
        await interaction.response.send_message("Done...")


    @app_commands.command(description="Add or remove elo...")
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
        self,
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
    async def elo_error(
        self, interaction: Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, Exception):
            await interaction.followup.send("Member is not registered...")

    @app_commands.command(description="Registers user for games...")
    @app_commands.describe(name="Username...")
    @NotInRegister.NotInRegister()
    @IsAllreadyRegistered.IsAllreadyRegistered()
    @app_commands.guild_only
    async def register(self, interaction: Interaction, name: str) -> None:
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
        self, interaction: Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, NotInRegister):
            return await interaction.response.send_message(
                "Only in register channel...", ephemeral=True
            )
        if isinstance(error, IsAllreadyRegistered):
            regRole: int = cur.execute(
                f"SELECT id FROM registerRole WHERE guild = {interaction.guild_id}"
            ).fetchone()[0]
            data: tuple[str, int] = cur.execute(
            f"SELECT name, elo FROM users WHERE id = {interaction.user.id}"
            ).fetchone()
            if (
                type(interaction.user) is Member
                and type(interaction.guild) is Guild
                and not interaction.user.get_role(regRole)
            ):
                role = interaction.guild.get_role(regRole)
                if role is not None:
                    await interaction.user.add_roles(role)
            if await changeNick(interaction.user, f"[ {data[1]} ] {data[0]}"):
                await interaction.response.send_message("Done...")
            else: await interaction.response.send_message(
                "Done...but your to cool for nickname change..."
            )
            return await interaction.followup.send(
                "You are all ready registered..."
            )

    @app_commands.command(description="Show player stats...")
    @app_commands.describe(member="Person that registered...")
    async def stats(self, interaction: Interaction, member: Optional[User]) -> None:
        data: tuple[str | None, int | None, int, int, int] = cur.execute(
            f"SELECT users.name, users.elo, COUNT(games.id) AS played, COUNT(won) AS wins, COUNT(games.id) - COUNT(won) AS losses FROM users JOIN teams ON teams.player = users.id LEFT JOIN games ON games.id = teams.game AND games.state != 'voided' WHERE users.id = {(member or interaction.user).id}"
        ).fetchone()
        if data[0] is None:
            return await interaction.response.send_message(
                "Member is not registered..."
            )
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

    @app_commands.command(description="Show leaderboard...")
    async def leaderboard(self, interaction: Interaction) -> None:
        data: list[tuple[int, int, int, int, int]] = cur.execute(
            "SELECT users.id, elo, COUNT(games.id) AS played, COUNT(won) AS wins, COUNT(games.id) - COUNT(won) AS losses FROM users JOIN teams ON teams.player = users.id LEFT JOIN games ON games.id = teams.game AND games.state != 'voided' GROUP BY users.id ORDER BY elo DESC, wins DESC, losses"
        ).fetchmany(5)

        embed = Embed()
        embed.title = "**Top 5 players:**"
        embed.description = "**―――――――――――――――――**\n"
        for i, player in enumerate(data):
            user = self.bot.get_user(player[0])
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

    @app_commands.command(description="Rename your self...")
    @app_commands.guild_only
    @app_commands.describe(name="New nickname...")
    @RegisterOnly.RegisterOnly()
    async def rename(self, interaction: Interaction, name: str):
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
    async def rename_error(
        self, interaction: Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, RegisterOnly):
            return await interaction.response.send_message("Your not registered...")


async def setup(bot: CustomBot):
    await bot.add_cog(Base(bot))


async def teardown(bot: commands.Bot):
    print("Base unloaded!")
