import asyncio
import datetime
import logging
import os
import sqlite3
import time
import traceback
from typing import Literal
import typing
import aiohttp
import discord
import discord.ext.commands
from discord.ext import commands
from discord import (
    Game,
    Guild,
    Interaction,
    Member,
    app_commands,
)
from dotenv import load_dotenv

import discord.ext

# loads .env file
load_dotenv()


con = sqlite3.connect("db.sqlite")
cur = con.cursor()
# cur.executescript(
# """
#     DROP TABLE IF EXISTS games;
#     DROP TABLE IF EXISTS teams;
# """
# )

print("Creating a database...")
with open("create_database.sql", "r") as sql_file:
    sql_script = sql_file.read()

cur.executescript(sql_script)


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


class CustomBot(commands.Bot):
    client: aiohttp.ClientSession
    _uptime: datetime.datetime = datetime.datetime.now(tz=datetime.UTC)
    _watch: asyncio.Task

    def __init__(self, ext_dir: str, *args: typing.Any, **kwargs: typing.Any) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(
            *args,
            **kwargs,
            command_prefix="kwjefowjef",
            intents=intents,
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        self.ext_dir = ext_dir
        self.synced = False

    async def _cog_watcher(self):
        print("Watching for changes...")
        last = time.time()
        while True:
            extensions: set[str] = set()
            for name, module in self.extensions.items():
                if module.__file__ and os.stat(module.__file__).st_mtime > last:
                    extensions.add(name)
            for ext in extensions:
                try:
                    await self.reload_extension(ext)
                    print(f"Reloaded {ext}")
                except commands.ExtensionError as e:
                    print(f"Failed to reload {ext}: {e}")
            last = time.time()
            await asyncio.sleep(1)

    async def _load_extensions(self) -> None:
        if not os.path.isdir(self.ext_dir):
            self.logger.error(f"Extension directory {self.ext_dir} does not exist.")
            return
        for filename in os.listdir(self.ext_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    await self.load_extension(f"{self.ext_dir}.{filename[:-3]}")
                    self.logger.info(f"Loaded extension {filename[:-3]}")
                except commands.ExtensionError:
                    self.logger.error(
                        f"Failed to load extension {filename[:-3]}\n{traceback.format_exc()}"
                    )

    async def on_error(
        self, event_method: str, *args: typing.Any, **kwargs: typing.Any
    ) -> None:
        self.logger.error(
            f"An error occurred in {event_method}.\n{traceback.format_exc()}"
        )

    async def on_ready(self) -> None:
        if self.user is None:
            return
        await self.change_presence(
            status=discord.Status.online, activity=Game("Thinking...")
        )
        if self.application is None:
            return
        await self.application.edit(description="Valorant match making bot...(Alpha)")
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

    async def setup_hook(self) -> None:
        self.client = aiohttp.ClientSession()
        await self._load_extensions()
        self._watcher = self.loop.create_task(self._cog_watcher())
        if not self.synced:
            guild_id = os.getenv("guild_id")
            if guild_id is not None:
                gl = discord.Object(int(guild_id))
                self.tree.copy_global_to(guild=gl)
                await self.tree.sync(guild=gl)
            self.synced = not self.synced
            self.logger.info("Synced command tree")

    async def close(self) -> None:
        await super().close()
        await self.client.close()

    def run(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        load_dotenv()
        try:
            super().run(str(os.getenv("token")), *args, **kwargs)
        except (discord.LoginFailure, KeyboardInterrupt):
            self.logger.info("Exiting...")
            exit()

    @property
    def user(self) -> discord.ClientUser:
        assert super().user, "Bot is not ready yet"
        return typing.cast(discord.ClientUser, super().user)

    @property
    def uptime(self) -> datetime.timedelta:
        return datetime.datetime.now(datetime.UTC) - self._uptime


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s"
    )
    bot = CustomBot(ext_dir="cogs")
    bot.run()


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


if __name__ == "__main__":
    main()
