import asyncio
import discord
from discord.ext import commands
from . import state as S

class ServerCloneCog(commands.Cog, name='serverclone'):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='cloneserver', aliases=['copyserver'], brief='Clone roles+channels from current guild to another id')
    async def cloneserver(self, ctx, target_guild_id: int):
        src = ctx.guild
        if src is None:
            return await ctx.send(S.ui_err('use in a server'), delete_after=8)
        dst = self.bot.get_guild(target_guild_id)
        if dst is None:
            return await ctx.send(S.ui_err('target guild not found / not in it'), delete_after=8)
        await ctx.send(S.ui_ok(f'cloning {src.name} → {dst.name} (roles+text channels)...'), delete_after=12)
        role_map = {}
        for role in reversed(src.roles):
            if role.is_default() or role.managed:
                continue
            try:
                nr = await dst.create_role(name=role.name, permissions=role.permissions, colour=role.colour, hoist=role.hoist, mentionable=role.mentionable, reason='wilt cloneserver')
                role_map[role.id] = nr
                await asyncio.sleep(0.6)
            except Exception:
                pass
        cat_map = {}
        for cat in src.categories:
            try:
                nc = await dst.create_category(cat.name, reason='wilt cloneserver')
                cat_map[cat.id] = nc
                await asyncio.sleep(0.6)
            except Exception:
                pass
        for ch in src.text_channels:
            try:
                parent = cat_map.get(getattr(ch.category, 'id', None))
                await dst.create_text_channel(ch.name, category=parent, topic=ch.topic, nsfw=ch.nsfw, slowmode_delay=ch.slowmode_delay, reason='wilt cloneserver')
                await asyncio.sleep(0.7)
            except Exception:
                pass
        await ctx.send(S.ui_ok('clone pass finished'), delete_after=15)

async def setup(bot):
    await bot.add_cog(ServerCloneCog(bot))
