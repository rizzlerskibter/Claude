import asyncio
import discord
from discord.ext import commands
from . import state as S
try:
    import wavelink
    HAS_WAVELINK = True
except Exception:
    HAS_WAVELINK = False
try:
    import yt_dlp
    HAS_YTDL = True
except Exception:
    HAS_YTDL = False
YTDL_OPTS = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True, 'default_search': 'ytsearch', 'source_address': '0.0.0.0'}

class MusicCog(commands.Cog, name='music'):

    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self._node_ready = False

    async def cog_load(self):
        if not HAS_WAVELINK:
            print('[music] wavelink not installed - using yt-dlp path if available')
            return
        try:
            host = getattr(S, 'LAVALINK_HOST', 'lavalink.jirayu.net')
            port = int(getattr(S, 'LAVALINK_PORT', 13592))
            password = getattr(S, 'LAVALINK_PASSWORD', 'youshallnotpass')
            node = wavelink.Node(uri=f'http://{host}:{port}', password=password)
            await wavelink.Pool.connect(nodes=[node], client=self.bot, cache_capacity=50)
            self._node_ready = True
            print('[music] lavalink connected')
        except Exception as e:
            print(f'[music] lavalink skip: {e}')

    async def _ensure_vc(self, ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await S.safe_edit(ctx.message, S.ui_err('join a voice channel first'))
            return None
        ch = ctx.author.voice.channel
        vc = ctx.guild.voice_client
        try:
            if vc and getattr(vc, 'is_connected', lambda: True)():
                if vc.channel.id != ch.id:
                    await vc.move_to(ch)
                return vc
            return await ch.connect(reconnect=True)
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:120]))
            return None

    def _ytdl_entry(self, query: str):
        with yt_dlp.YoutubeDL(YTDL_OPTS) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            url = info.get("url")
            title = info.get("title") or query
            return (url, title)

    @commands.command(name='mplay', aliases=['playmusic', 'ytplay'], brief='Play audio in VC')
    async def mplay(self, ctx, *, query: str):
        await S.safe_edit(ctx.message, S.ui_info('loading...'))
        if HAS_WAVELINK and self._node_ready:
            try:
                player = await self._ensure_vc(ctx)
                if player is None:
                    return
                tracks = await wavelink.Playable.search(query)
                if not tracks:
                    return await S.safe_edit(ctx.message, S.ui_err('no tracks'))
                track = tracks[0] if not isinstance(tracks, wavelink.Playlist) else tracks.tracks[0]
                if getattr(player, 'playing', False):
                    self.queues.setdefault(ctx.guild.id, []).append(track)
                    return await S.safe_edit(ctx.message, S.ui_ok(f'queued {track}'))
                await player.play(track)
                return await S.safe_edit(ctx.message, S.ui_ok(f'playing {track}'))
            except Exception as e:
                await S.safe_edit(ctx.message, S.ui_err(f'wavelink: {e}')[:150])
                return
        if not HAS_YTDL:
            return await S.safe_edit(ctx.message, S.ui_err('install yt-dlp + PyNaCl + ffmpeg for music (or wavelink+lavalink)'))
        vc = await self._ensure_vc(ctx)
        if vc is None:
            return
        try:
            url, title = await asyncio.to_thread(self._ytdl_entry, query)
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err(str(e)[:120]))
        try:
            if vc.is_playing():
                vc.stop()
            source = discord.FFmpegPCMAudio(url, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-vn')
            vc.play(source)
            await S.safe_edit(ctx.message, S.ui_ok(f'playing {title[:80]}'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:140]))

    @commands.command(name='mstop', brief='Stop playback')
    async def mstop(self, ctx):
        vc = ctx.guild.voice_client
        self.queues[ctx.guild.id] = []
        if vc:
            try:
                if HAS_WAVELINK and hasattr(vc, 'stop'):
                    await vc.stop()
                elif vc.is_playing():
                    vc.stop()
            except Exception:
                pass
        await S.safe_edit(ctx.message, S.ui_ok('stopped'))

    @commands.command(name='mskip', brief='Skip / stop current')
    async def mskip(self, ctx):
        await self.mstop(ctx)

    @commands.command(name='mleave', brief='Leave voice')
    async def mleave(self, ctx):
        if ctx.guild.voice_client:
            try:
                await ctx.guild.voice_client.disconnect(force=True)
            except Exception:
                await ctx.guild.voice_client.disconnect()
        await S.safe_edit(ctx.message, S.ui_ok('left'))

    @commands.command(name='mvol', brief='Volume 0-100 (wavelink only)')
    async def mvol(self, ctx, vol: int=50):
        vc = ctx.guild.voice_client
        if not vc or not HAS_WAVELINK:
            return await S.safe_edit(ctx.message, S.ui_err('volume needs wavelink player'))
        vol = max(0, min(100, vol))
        try:
            await vc.set_volume(vol)
            await S.safe_edit(ctx.message, S.ui_ok(f'vol {vol}'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)[:100]))

async def setup(bot):
    await bot.add_cog(MusicCog(bot))
