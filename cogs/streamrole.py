from copy import deepcopy
import os
import os.path
import discord
from discord.ext import commands
from discord.utils import find
from discord.utils import get
import sqlite3
from .utils.dataIO import dataIO
from .utils import checks, chat_formatting as cf
from .utils.chat_formatting import escape_mass_mentions
from .utils import checks
from collections import defaultdict
from string import ascii_letters
from random import choice
import re
import aiohttp
import asyncio
import logging
import json
import sqlite3
import os.path
#Todo: 1. Regex edit spaces out of names 2. Add way to remove members from database 3. remove previous entry when adding duplicate 4. Let users add themselves (with many checks)

default_settings = {
    "enabled": False,
    "role": None,
    "only": None,
    "add": True,
    "remove": True,
    "list": True
}


class StreamRole:

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.settings_path = "data/streamrole/settings.json"
        self.settings = dataIO.load_json(self.settings_path)

    @commands.group(pass_context=True, no_pm=True, name="streamroleset")
    @checks.admin_or_permissions(manage_server=True)
    async def _streamroleset(self, ctx: commands.Context):
        """Sets StreamRole settings."""

        server = ctx.message.server
        if server.id not in self.settings:
            self.settings[server.id] = deepcopy(default_settings)
            dataIO.save_json(self.settings_path, self.settings)
        if "only" not in self.settings[server.id]:
            self.settings[server.id]["only"] = None
            dataIO.save_json(self.settings_path, self.settings)
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @_streamroleset.command(pass_context=True, no_pm=True, name="toggle")
    @checks.admin_or_permissions(manage_server=True)
    async def _toggle(self, ctx: commands.Context):
        """Toggles StreamRole on/off."""

        await self.bot.type()

        server = ctx.message.server
        if (not self.settings[server.id]["enabled"] and
                self.settings[server.id]["role"] is None):
            await self.bot.reply(cf.warning(
                "You need to set the role before turning on StreamRole."
                " Use `{}streamroleset role`".format(ctx.prefix)))
            return

        self.settings[server.id][
            "enabled"] = not self.settings[server.id]["enabled"]
        if self.settings[server.id]["enabled"]:
            await self.bot.reply(
                cf.info("StreamRole is now enabled."))
        else:
            await self.bot.reply(
                cf.info("StreamRole is now disabled."))
        dataIO.save_json(self.settings_path, self.settings)

    @_streamroleset.command(pass_context=True, no_pm=True, name="only")
    @checks.admin_or_permissions(manage_server=True)
    async def _only(self, ctx: commands.Context, role: discord.Role):
        """Sets the role from which to update streamers.

        Only members with this role will be given the streaming
        role when streaming. Set to '@everyone' to reset it."""

        await self.bot.type()

        server = ctx.message.server
        if role.id == server.id:
            self.settings[server.id]["only"] = None
        else:
            self.settings[server.id]["only"] = role.id
        dataIO.save_json(self.settings_path, self.settings)

        await self.bot.reply(
            cf.info("Only members with the role `{}` will be given the "
                    "streaming role now. Set it to `@everyone` to "
                    "reset it.".format(role.name)))

    @_streamroleset.command(pass_context=True, no_pm=True, name="add")
    @checks.admin_or_permissions(manage_server=True)
    async def _add(self, ctx: commands.Context, stream: str, stream2: str = None, stream3: str = None, stream4: str = None):
        """Toggles StreamRole on/off."""
        conn = sqlite3.connect("streaminfo.db")
        if stream2 is not None:
            stream = stream + " " + stream2
        if stream3 is not None:
            stream = stream + " " +  stream3
        if stream4 is not None:
            stream = stream + " " +  stream4
        disName, strName = stream.split(",")
        disName = disName.replace('-', '').replace('_','')
        cursour = conn.cursor()
        sql = "INSERT OR IGNORE INTO streams VALUES (?, ?)"
        conn.execute(sql, [(disName), (strName)])
        await self.bot.reply(cf.info("Discord name " + disName + "has been added with stream name " + strName))
        conn.commit()
        conn.close()


    @_streamroleset.command(pass_context=True, no_pm=True, name="remove")
    @checks.admin_or_permissions(manage_server=True)
    async def _remove(self, ctx: commands.Context, stream: str, stream2: str = None, stream3: str = None, stream4: str = None):
        """Toggles StreamRole on/off."""
        conn = sqlite3.connect("streaminfo.db")
        if stream2 is not None:
            stream = stream + " " +  stream2
        if stream3 is not None:
            stream = stream + " " +  stream3
        if stream4 is not None:
            stream = stream + " " +  stream4
        disName, strName = stream.split(",")
        disName = disName.replace('-', '').replace('_','')
        cursour = conn.cursor()
        sql = "DELETE FROM streams WHERE strName = ?"
        conn.execute(sql, [(strName)])
        await self.bot.reply(cf.info(strName + " removed from DB "))
        conn.commit()
        conn.close()

    @_streamroleset.command(pass_context=True, no_pm=True, name="list")
    @checks.admin_or_permissions(manage_server=True)
    async def _list(self, ctx: commands.Context, stream: str):
        """Toggles StreamRole on/off."""
        conn = sqlite3.connect("streaminfo.db")
        conn.text_factory = str
        cursor = conn.cursor()
        #d = " "
        #n = 2
        #stream = d.join(stream.split(d, n)[:n])
        sql = "SELECT * FROM streams"
        cursor.execute(sql)
        data3 = cursor.fetchall()
        await self.bot.reply(cf.info(data3))
        conn.commit()
        conn.close()

    @_streamroleset.command(pass_context=True, no_pm=True, name="role")
    @checks.admin_or_permissions(manage_server=True)
    async def _role(self, ctx: commands.Context, role: discord.Role):
        """Sets the role that StreamRole assigns to
        members that are streaming.
        """

        await self.bot.type()

        server = ctx.message.server
        self.settings[server.id]["role"] = role.id
        dataIO.save_json(self.settings_path, self.settings)

        await self.bot.reply(
            cf.info("Any member who is streaming will now be given the "
                    "role `{}`. Ensure you also toggle the cog on with "
                    "`{}streamroleset toggle`.".format(role.name, ctx.prefix)))

    async def stream_listener(self, before: discord.Member,
                              after: discord.Member):
    
        conn = sqlite3.connect("streaminfo.db")
        conn.text_factory = str
        cursor = conn.cursor()
        sql = "SELECT * FROM streams where disName=?"
        memVar = str(before)
        memVar = memVar.replace('-', '').replace('_','')
        cursor.execute(sql,[(memVar)])
        data2 = cursor.fetchall()
        #print(data2[0][0])
        #print(data2[0][1])
        strName = data2[0][1]
        url = "https://mixer.com/api/v1/channels/" + strName
        #print(url)
        if before.server.id not in self.settings:
            self.settings[before.server.id] = deepcopy(default_settings)
            dataIO.save_json(self.settings_path, self.settings)
        elif "only" not in self.settings[before.server.id]:
            self.settings[before.server.id]["only"] = None
            dataIO.save_json(self.settings_path, self.settings)
    
        server_settings = self.settings[before.server.id]
        if server_settings["enabled"] and server_settings["role"] is not None:
            streamer_role = find(lambda m: m.id == server_settings["role"],
                                 before.server.roles)
            only_role = find(lambda l: l.id == server_settings["only"],
                             before.server.roles)
            if streamer_role is None:
                return
    
            # is streaming
            if (after.game is not None and
                    streamer_role not in after.roles):
                if (only_role is None or only_role in after.roles):
                    async with aiohttp.get(url) as r:
                        data = await r.json(encoding='utf-8')
                    if r.status == 200:
                        if data["online"] is True:
                            try:
                                await self.bot.add_roles(after, streamer_role)
                            except discord.Forbidden:
                                 print("StreamRole: forbidden error\n""Server: {}, Role: {}, Member: {}".format( before.server.id, streamer_role.id, after.id))
                        else:
                            await self.bot.remove_roles(after, streamer_role)
    
                    elif r.status == 404:
                        raise StreamNotFound()
                    else:
                        raise APIError()
            # is not
            elif ((after.game is None) and
                  streamer_role in after.roles):
                    async with aiohttp.get(url) as r:
                        data = await r.json(encoding='utf-8')
                    if r.status == 200:
                        if data["online"] is True:
                            try:
                                await self.bot.add_roles(after, streamer_role)
                            except discord.Forbidden:
                                 print("StreamRole: forbidden error\n""Server: {}, Role: {}, Member: {}".format( before.server.id, streamer_role.id, after.id))
                        else:
                            await self.bot.remove_roles(after, streamer_role)
    
                    elif r.status == 404:
                        raise StreamNotFound()
                    else:
                        raise APIError()
    
    
def check_folders():
    if not os.path.exists("data/streamrole"):
        print("Creating data/streamrole directory...")
        os.makedirs("data/streamrole")


def check_files():
    f = "data/streamrole/settings.json"
    if not dataIO.is_valid_json(f):
        print("Creating data/streamrole/settings.json...")
        dataIO.save_json(f, {})

def setup(bot: commands.Bot):
    check_folders()
    check_files()
    n = StreamRole(bot)
    bot.add_listener(n.stream_listener, "on_member_update")

    bot.add_cog(n)
