import time
import asyncio, time, re as _re, aiohttp, discord
from collections import defaultdict
from discord.ext import commands
from . import state as S
from .antid import jitter
import aiohttp
_enabled = False
_log_ch: int = 0
_ch_del_times: dict = defaultdict(list)
_member_del_times: dict = defaultdict(list)
NUKE_THRESHOLD = 5
NUKE_WINDOW = 10
MEMBER_LOSS_THRESHOLD = 20
MEMBER_LOSS_WINDOW = 60
DANGER_PATTERNS = [_re.compile(p, _re.I) for p in ['child\\s*porn', '\\bcsam\\b', '\\bcp\\s+server\\b', 'loli\\s*porn', 'shota\\s*porn', 'gore\\s*server', '\\bsnuff\\b', 'animal\\s+abuse', 'zoophilia\\s+server', 'drug\\s+market', '\\bhitman\\b', 'terror', 'ddos\\s+server', 'rat\\s+server', 'malware\\s+server', 'raid\\s+server']]
SCAM_PATTERNS = [_re.compile(p, _re.I) for p in ['free\\s+nitro', 'discord\\.gift/[a-zA-Z0-9]{16,}', 'claim\\s+your\\s+(prize|reward|gift)', 'your\\s+account\\s+(has been|is being)\\s+(suspend|terminat|ban)', 'verify\\s+your\\s+account.*http']]

async def _alert(bot, msg: str):
    if _log_ch:
        ch = bot.get_channel(_log_ch)
        if ch:
            try:
                await ch.send(S.ui_warn(f'[protect] {msg}'))
            except Exception:
                pass
    print(f'[protect] {msg}')

class ProtectCog(commands.Cog, name='protect'):

    def __init__(self, bot):
        self.bot = bot

    @commands.group(name='protect', invoke_without_command=True, brief='Account protection')
    async def protect(self, ctx):
        await S.safe_edit(ctx.message, S.ui_box('protect', [f'  {S.DIM}enabled{S.RESET}      {_enabled}', f"  {S.DIM}log channel{S.RESET}  {_log_ch or 'not set'}", f'  {S.DIM}nuke{S.RESET}         {NUKE_THRESHOLD} ch / {NUKE_WINDOW}s', f'  {S.DIM}member loss{S.RESET}  {MEMBER_LOSS_THRESHOLD} / {MEMBER_LOSS_WINDOW}s']))

    @protect.command(name='on')
    async def protect_on(self, ctx):
        global _enabled
        _enabled = True
        await S.safe_edit(ctx.message, S.ui_ok('account protection → on'))

    @protect.command(name='off')
    async def protect_off(self, ctx):
        global _enabled
        _enabled = False
        await S.safe_edit(ctx.message, S.ui_ok('account protection → off'))

    @protect.command(name='logch')
    async def protect_logch(self, ctx, ch: discord.TextChannel=None):
        global _log_ch
        _log_ch = ch.id if ch else 0
        await S.safe_edit(ctx.message, S.ui_ok(f"log → {ch or 'none'}"))

    @protect.command(name='sweep')
    async def protect_sweep(self, ctx):
        left = 0
        for g in self.bot.guilds:
            text = (str(g.name) + ' ' + str(g.description or '')).lower()
            if any((p.search(text) for p in DANGER_PATTERNS)):
                try:
                    await g.leave()
                    left += 1
                except Exception:
                    pass
                await asyncio.sleep(jitter(0.5))
        await S.safe_edit(ctx.message, S.ui_ok(f'swept - left {left} dangerous server(s)'))

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        if not _enabled:
            return
        text = (str(after.name or '') + ' ' + str(after.description or '')).lower()
        if any((p.search(text) for p in DANGER_PATTERNS)):
            await _alert(self.bot, f"leaving '{after.name}' - danger pattern matched")
            try:
                await after.leave()
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if not _enabled:
            return
        gid = channel.guild.id if channel.guild else None
        if not gid:
            return
        now = time.time()
        times = _ch_del_times[gid]
        times.append(now)
        _ch_del_times[gid] = [t for t in times if now - t < NUKE_WINDOW]
        if len(_ch_del_times[gid]) >= NUKE_THRESHOLD:
            _ch_del_times[gid].clear()
            await _alert(self.bot, f'nuke detected in {channel.guild.name} - leaving')
            try:
                await channel.guild.leave()
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not _enabled:
            return
        gid = member.guild.id
        now = time.time()
        times = _member_del_times[gid]
        times.append(now)
        _member_del_times[gid] = [t for t in times if now - t < MEMBER_LOSS_WINDOW]
        if len(_member_del_times[gid]) >= MEMBER_LOSS_THRESHOLD:
            _member_del_times[gid].clear()
            await _alert(self.bot, f'mass member loss in {member.guild.name} - leaving')
            try:
                await member.guild.leave()
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if not _enabled:
            return
        if message.guild:
            return
        if not self.bot.user or message.author.id == self.bot.user.id:
            return
        content = message.content or ''
        for pat in SCAM_PATTERNS:
            if pat.search(content):
                await _alert(self.bot, f'scam DM from {message.author}: matched pattern')
                break

    @commands.command(name='accountguard', brief='Alias for protect on')
    async def accountguard(self, ctx):
        S._protect_enabled = True
        await S.safe_edit(ctx.message, S.ui_ok('account guard enabled'))

async def setup(bot):
    await bot.add_cog(ProtectCog(bot))
