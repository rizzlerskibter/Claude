import asyncio
import discord
from discord.ext import commands
from . import state as S

class ClearDMCog(commands.Cog, name='cleardm'):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='cleardm', aliases=['purgedm', 'dmclear'], brief='Delete your messages in this DM/channel')
    async def cleardm(self, ctx, limit: int=50):
        limit = max(1, min(int(limit or 50), 200))
        await S.safe_edit(ctx.message, S.ui_info(f'clearing up to {limit}...'))
        deleted = 0
        try:
            async for msg in ctx.channel.history(limit=limit):
                if msg.author.id != self.bot.user.id:
                    continue
                try:
                    await msg.delete()
                    deleted += 1
                    await asyncio.sleep(0.35)
                except Exception:
                    await asyncio.sleep(0.5)
        except Exception as e:
            return await ctx.channel.send(S.ui_err(str(e)[:100]))
        try:
            await ctx.channel.send(S.ui_ok(f'deleted {deleted}'), delete_after=5)
        except Exception:
            pass

async def setup(bot):
    await bot.add_cog(ClearDMCog(bot))
