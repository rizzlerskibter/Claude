import asyncio
import aiohttp
import discord
from discord.ext import commands
from . import state as S
from .antid import jitter

def _h():
    return {'Authorization': S._get_token(), 'Content-Type': 'application/json', 'User-Agent': S.USER_AGENT}

async def _patch_member(guild_id, user_id, data):
    url = f'https://discord.com/api/v9/guilds/{guild_id}/members/{user_id}'
    async with aiohttp.ClientSession() as s:
        async with s.patch(url, headers=_h(), json=data) as r:
            return r.status

class VoiceCog(commands.Cog, name='voice'):

    def __init__(self, bot):
        self.bot = bot
        self._vc247_leaving = set()
        self._vc_lock = asyncio.Lock()
        self._vc247 = False
        self._vc247_ch = None
        self._keep_tasks = {}

    @commands.command(name='vcmute', brief='Server mute a user')
    @commands.guild_only()
    async def vcmute(self, ctx, member: discord.Member=None):
        if not member:
            return await S.safe_edit(ctx.message, S.ui_err('usage: vcmute <@user>'))
        await member.edit(mute=True)
        await S.safe_edit(ctx.message, S.ui_ok(f'muted {member}'))

    @commands.command(name='vcunmute', brief='Server unmute a user')
    @commands.guild_only()
    async def vcunmute(self, ctx, member: discord.Member=None):
        if not member:
            return await S.safe_edit(ctx.message, S.ui_err('usage: vcunmute <@user>'))
        await member.edit(mute=False)
        await S.safe_edit(ctx.message, S.ui_ok(f'unmuted {member}'))

    @commands.command(name='vcdeafen', brief='Server deafen a user')
    @commands.guild_only()
    async def vcdeafen(self, ctx, member: discord.Member=None):
        if not member:
            return await S.safe_edit(ctx.message, S.ui_err('usage: vcdeafen <@user>'))
        await member.edit(deafen=True)
        await S.safe_edit(ctx.message, S.ui_ok(f'deafened {member}'))

    @commands.command(name='vcundeafen', brief='Server undeafen a user')
    @commands.guild_only()
    async def vcundeafen(self, ctx, member: discord.Member=None):
        if not member:
            return await S.safe_edit(ctx.message, S.ui_err('usage: vcundeafen <@user>'))
        await member.edit(deafen=False)
        await S.safe_edit(ctx.message, S.ui_ok(f'undeafened {member}'))

    @commands.command(name='vckick', brief='Kick user from VC')
    @commands.guild_only()
    async def vckick(self, ctx, member: discord.Member=None):
        if not member:
            return await S.safe_edit(ctx.message, S.ui_err('usage: vckick <@user>'))
        await member.move_to(None)
        await S.safe_edit(ctx.message, S.ui_ok(f'kicked {member} from VC'))

    @commands.command(name='vcmove', brief='Move user to voice channel')
    @commands.guild_only()
    async def vcmove(self, ctx, member: discord.Member=None, ch: discord.VoiceChannel=None):
        if not member or not ch:
            return await S.safe_edit(ctx.message, S.ui_err('usage: vcmove <@user> <#channel>'))
        await member.move_to(ch)
        await S.safe_edit(ctx.message, S.ui_ok(f'moved {member} → #{ch.name}'))

    @commands.command(name='vckeep', brief='Keep VC connection alive')
    @commands.guild_only()
    async def vckeep(self, ctx, ch: discord.VoiceChannel=None, action: str='on'):
        if action == 'off' or not ch:
            t = self._keep_tasks.pop(ctx.channel.id, None)
            if t and (not t.done()):
                t.cancel()
            return await S.safe_edit(ctx.message, S.ui_ok('vckeep off'))

        async def _loop(voice_ch=ch):
            while True:
                try:
                    vc = ctx.guild.voice_client
                    if vc is None or not vc.is_connected():
                        await voice_ch.connect(reconnect=True)
                    elif vc.channel and vc.channel.id != voice_ch.id:
                        await vc.move_to(voice_ch)
                except Exception as e:
                    print(f'[voice] vckeep: {e}')
                await asyncio.sleep(jitter(15.0))
        t = self._keep_tasks.get(ctx.channel.id)
        if t and (not t.done()):
            t.cancel()
        try:
            if ctx.guild.voice_client is None:
                await ch.connect(reconnect=True, timeout=15)
            elif ctx.guild.voice_client.channel.id != ch.id:
                await ctx.guild.voice_client.move_to(ch)
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err(f'join failed: {e}'))
        self._keep_tasks[ctx.channel.id] = asyncio.create_task(_loop())
        await S.safe_edit(ctx.message, S.ui_ok(f'vckeep → #{ch.name}'))

    @commands.command(name='selfmute', brief='Toggle self-mute')
    @commands.guild_only()
    async def selfmute(self, ctx):
        if ctx.guild.me.voice:
            muted = not ctx.guild.me.voice.self_mute
            await ctx.guild.change_voice_state(channel=ctx.guild.me.voice.channel, self_mute=muted)
            await S.safe_edit(ctx.message, S.ui_ok(f"self-mute → {('on' if muted else 'off')}"))
        else:
            await S.safe_edit(ctx.message, S.ui_err('not in a voice channel'))

    @commands.command(name='selfdeaf', brief='Toggle self-deaf')
    @commands.guild_only()
    async def selfdeaf(self, ctx):
        if ctx.guild.me.voice:
            deafened = not ctx.guild.me.voice.self_deaf
            await ctx.guild.change_voice_state(channel=ctx.guild.me.voice.channel, self_deaf=deafened)
            await S.safe_edit(ctx.message, S.ui_ok(f"self-deaf → {('on' if deafened else 'off')}"))
        else:
            await S.safe_edit(ctx.message, S.ui_err('not in a voice channel'))

    @commands.command(name='vcjoin', brief='Join a voice channel')
    @commands.guild_only()
    async def vcjoin(self, ctx, channel: discord.VoiceChannel=None):
        if not channel:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
            else:
                return await S.safe_edit(ctx.message, S.ui_err('usage: vcjoin <#channel>'))
        try:
            vc = ctx.guild.voice_client
            if vc is not None and getattr(vc, 'is_connected', lambda: True)():
                if vc.channel and vc.channel.id == channel.id:
                    return await S.safe_edit(ctx.message, S.ui_ok(f'already in #{channel.name}'))
                await vc.move_to(channel)
            else:
                await channel.connect(reconnect=True)
            await S.safe_edit(ctx.message, S.ui_ok(f'joined #{channel.name}'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:120]))

    @commands.command(name='vcleave', brief='Leave voice channel')
    @commands.guild_only()
    async def vcleave(self, ctx):
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect(force=True)
            await S.safe_edit(ctx.message, S.ui_ok('left VC'))
        else:
            await S.safe_edit(ctx.message, S.ui_err('not in a VC'))

    @commands.command(name='vcmoveall', brief='Move all members to a channel')
    @commands.guild_only()
    async def vcmoveall(self, ctx, dest: discord.VoiceChannel=None):
        if not dest:
            return await S.safe_edit(ctx.message, S.ui_err('usage: vcmoveall <#dest>'))
        moved = 0
        for ch in ctx.guild.voice_channels:
            for member in list(ch.members):
                if member.id != self.bot.user.id:
                    try:
                        await member.move_to(dest)
                        moved += 1
                    except Exception:
                        pass
        await S.safe_edit(ctx.message, S.ui_ok(f'moved {moved} members → #{dest.name}'))

    @commands.command(name='vcdiag', brief='Voice channel diagnostics')
    @commands.guild_only()
    async def vcdiag(self, ctx):
        vc = ctx.guild.voice_client
        rows = [f'  {S.DIM}connected{S.RESET}  {vc is not None}', f"  {S.DIM}channel{S.RESET}    {(vc.channel.name if vc else '-')}", f'  {S.DIM}latency{S.RESET}    {round(vc.latency * 1000)}ms' if vc else f'  {S.DIM}latency{S.RESET}    -']
        await S.safe_edit(ctx.message, S.ui_box('vc diag', rows))

    @commands.command(name='selfcamera', brief='Toggle self camera in VC')
    @commands.guild_only()
    async def selfcamera(self, ctx, toggle: str=''):
        if not ctx.guild.me.voice:
            return await S.safe_edit(ctx.message, S.ui_err('not in VC'))
        on = toggle.lower() not in ('off', 'disable') if toggle else not ctx.guild.me.voice.self_video
        await ctx.guild.change_voice_state(channel=ctx.guild.me.voice.channel, self_video=on)
        await S.safe_edit(ctx.message, S.ui_ok(f"camera → {('on' if on else 'off')}"))

    @commands.command(name='selfstream', brief='Toggle self stream in VC')
    @commands.guild_only()
    async def selfstream(self, ctx, toggle: str=''):
        if not ctx.guild.me.voice:
            return await S.safe_edit(ctx.message, S.ui_err('not in VC'))
        on = toggle.lower() not in ('off', 'disable') if toggle else not ctx.guild.me.voice.self_stream
        await ctx.guild.change_voice_state(channel=ctx.guild.me.voice.channel, self_stream=on)
        await S.safe_edit(ctx.message, S.ui_ok(f"stream → {('on' if on else 'off')}"))

    @commands.command(name='vcreconnect', brief='Reconnect to voice channel')
    @commands.guild_only()
    async def vcreconnect(self, ctx):
        if not ctx.guild.me.voice:
            return await S.safe_edit(ctx.message, S.ui_err('not in VC'))
        ch = ctx.guild.me.voice.channel
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect(force=True)
        await ch.connect()
        await S.safe_edit(ctx.message, S.ui_ok(f'reconnected to #{ch.name}'))

    @commands.command(name='vc247', aliases=['voice24', 'stayvc'], brief='Stay in a voice channel (24/7 style)')
    async def vc247(self, ctx, channel: discord.VoiceChannel=None):
        ch = channel
        if ch is None and ctx.author.voice:
            ch = ctx.author.voice.channel
        if ch is None:
            return await ctx.send(S.ui_err('specify a voice channel or join one'), delete_after=8)
        try:
            if ctx.guild.voice_client:
                await ctx.guild.voice_client.move_to(ch)
            else:
                await ch.connect(reconnect=True, timeout=15)
            if not hasattr(self.bot, '_vc247'):
                self.bot._vc247 = {}
            self.bot._vc247[ctx.guild.id] = ch.id
            await ctx.send(S.ui_ok(f'24/7 in {ch.name}'), delete_after=8)
        except Exception as e:
            await ctx.send(S.ui_err(str(e)[:120]), delete_after=10)

    @commands.command(name='vc247off', brief='Disable 24/7 voice stay')
    async def vc247off(self, ctx):
        if hasattr(self.bot, '_vc247'):
            self.bot._vc247.pop(ctx.guild.id, None)
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect(force=True)
        await ctx.send(S.ui_ok('24/7 off'), delete_after=6)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id != getattr(self.bot.user, 'id', None):
            return
        if not hasattr(self.bot, '_vc247'):
            return
        gid = member.guild.id
        want = self.bot._vc247.get(gid)
        if not want:
            return
        if after.channel and after.channel.id == want:
            return
        if getattr(self.bot, '_vc247_lock', None) and self.bot._vc247_lock.get(gid):
            return
        if not hasattr(self.bot, '_vc247_lock'):
            self.bot._vc247_lock = {}
        self.bot._vc247_lock[gid] = True
        try:
            await asyncio.sleep(3)
            ch = member.guild.get_channel(want)
            if ch is None:
                return
            me = member.guild.me
            if me and me.voice and me.voice.channel and (me.voice.channel.id == want):
                return
            vc = member.guild.voice_client
            try:
                if vc and vc.is_connected():
                    await vc.move_to(ch)
                else:
                    await ch.connect(reconnect=True, timeout=15)
            except TypeError:
                await ch.connect()
            except Exception as e:
                print(f'[voice] vc247 rejoin: {e}')
        finally:
            self.bot._vc247_lock[gid] = False

    def cog_unload(self):
        for t in getattr(self, '_keep_tasks', {}).values():
            if t and (not t.done()):
                t.cancel()


    @commands.command(name='vcnoise', aliases=['noise', 'vcblast'], brief='Sound barrier noise in VC')
    @commands.guild_only()
    async def vcnoise(self, ctx, seconds: int = 8):
        seconds = max(1, min(int(seconds or 8), 30))
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await S.safe_edit(ctx.message, S.ui_err('join a vc first'))
        ch = ctx.author.voice.channel
        try:
            vc = ctx.guild.voice_client
            if vc and vc.is_connected():
                await vc.move_to(ch)
            else:
                vc = await ch.connect(reconnect=True, timeout=10)
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err('vc connect: %s' % e))
        await S.safe_edit(ctx.message, S.ui_ok('noise %ds in %s' % (seconds, ch.name)))
        # selfbot cannot stream arbitrary audio without ffmpeg source — pulse speak state
        try:
            for _ in range(max(1, seconds)):
                try:
                    await ctx.guild.change_voice_state(channel=ch, self_mute=False, self_deaf=False)
                except Exception:
                    pass
                await asyncio.sleep(1)
        except Exception as e:
            print('[voice] noise:', e)

    @commands.command(name='vctroll', aliases=['vctrollmove', 'vcbounce'], brief='Move self between two VCs rapidly')
    @commands.guild_only()
    async def vctroll(self, ctx, times: int = 5):
        times = max(1, min(int(times or 5), 20))
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await S.safe_edit(ctx.message, S.ui_err('join a vc first'))
        chs = [c for c in ctx.guild.voice_channels if c.permissions_for(ctx.guild.me).connect] if ctx.guild.me else list(ctx.guild.voice_channels)
        if len(chs) < 2:
            chs = list(ctx.guild.voice_channels)
        if len(chs) < 2:
            return await S.safe_edit(ctx.message, S.ui_err('need 2+ voice channels'))
        await S.safe_edit(ctx.message, S.ui_ok('troll x%d' % times))
        a, b = chs[0], chs[1]
        for i in range(times):
            target = a if i % 2 == 0 else b
            try:
                await ctx.guild.change_voice_state(channel=target)
            except Exception as e:
                print('[voice] troll:', e)
                break
            await asyncio.sleep(0.35)


async def setup(bot):
    await bot.add_cog(VoiceCog(bot))
