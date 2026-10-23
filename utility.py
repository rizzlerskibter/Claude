import asyncio, discord
from discord.ext import commands
from . import state as S
from .antid import jitter
_typing_tasks: dict = {}

async def _typing_loop(channel_id: int, token: str, user_agent: str):
    import aiohttp, random
    url = f'https://discord.com/api/v9/channels/{channel_id}/typing'
    h = {'Authorization': token, 'User-Agent': user_agent}
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                async with s.post(url, headers=h) as r:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f'[typing] {e}')
            interval = jitter(8.0)
            if random.random() < 0.08:
                interval += random.uniform(4.0, 12.0)
            await asyncio.sleep(interval)

class UtilityCog(commands.Cog, name='utility'):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='typing', brief='Start typing indicator')
    async def typing_start(self, ctx):
        cid = ctx.channel.id
        if cid in _typing_tasks and (not _typing_tasks[cid].done()):
            return await S.safe_edit(ctx.message, S.ui_info('already typing here'))
        await ctx.message.delete()
        _typing_tasks[cid] = asyncio.create_task(_typing_loop(cid, S.TOKEN, S.USER_AGENT))

    @commands.command(name='typingstop', brief='Stop typing indicator')
    async def typing_stop(self, ctx):
        t = _typing_tasks.pop(ctx.channel.id, None)
        if t and (not t.done()):
            t.cancel()
        await S.safe_edit(ctx.message, S.ui_ok('typing stopped'))

    @commands.command(name='uwuify', brief='UwU-ify text')
    async def uwuify(self, ctx, *, text: str=''):
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: uwuify <text>'))
        result = text.replace('r', 'w').replace('R', 'W').replace('l', 'w').replace('L', 'W')
        await S.safe_edit(ctx.message, result)

    @commands.command(name='owoify', brief='OwO-ify text')
    async def owoify(self, ctx, *, text: str=''):
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: owoify <text>'))
        result = text.replace('r', 'w').replace('l', 'w').replace('R', 'W').replace('L', 'W')
        await S.safe_edit(ctx.message, result + ' owo')

    @commands.command(name='mock', brief='Mock text')
    async def mock(self, ctx, *, text: str=''):
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: mock <text>'))
        result = ''.join((c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(text)))
        await S.safe_edit(ctx.message, result)

    @commands.command(name='reverse', brief='Reverse text')
    async def reverse(self, ctx, *, text: str=''):
        await S.safe_edit(ctx.message, text[::-1] if text else '')

    @commands.command(name='clap', brief='Clap between words')
    async def clap(self, ctx, *, text: str=''):
        await S.safe_edit(ctx.message, ' 👏 '.join(text.split()) if text else '')

    @commands.command(name='aesthetic', brief='Aesthetic text')
    async def aesthetic(self, ctx, *, text: str=''):
        result = ' '.join(text) if text else ''
        await S.safe_edit(ctx.message, result)

    @commands.command(name='ghostping', brief='Ghost ping a user')
    async def ghostping(self, ctx, user: discord.User=None):
        if not user:
            return await S.safe_edit(ctx.message, S.ui_err('usage: ghostping <@user>'))
        await ctx.message.delete()
        m = await ctx.channel.send(user.mention)
        await asyncio.sleep(0.4)
        await m.delete()

    @commands.command(name='trl', aliases=['translatecmd'], brief='Translate text')
    async def translate(self, ctx, lang: str='en', *, text: str=''):
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: translate <lang> <text>'))
        try:
            from deep_translator import GoogleTranslator
            result = GoogleTranslator(source='auto', target=lang).translate(text)
            await S.safe_edit(ctx.message, f'```\n{result}\n```')
        except ImportError:
            await S.safe_edit(ctx.message, S.ui_err('deep-translator not installed'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)))

    @commands.command(name='pin', brief='Pin the replied-to message')
    @commands.guild_only()
    async def pin(self, ctx):
        ref = ctx.message.reference
        if not ref:
            return await S.safe_edit(ctx.message, S.ui_err('reply to a message to pin it'))
        try:
            msg = await ctx.channel.fetch_message(ref.message_id)
            await msg.pin()
            await S.safe_edit(ctx.message, S.ui_ok('message pinned'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)))

    @commands.command(name='unpin', brief='Unpin the replied-to message')
    @commands.guild_only()
    async def unpin(self, ctx):
        ref = ctx.message.reference
        if not ref:
            return await S.safe_edit(ctx.message, S.ui_err('reply to a message to unpin it'))
        try:
            msg = await ctx.channel.fetch_message(ref.message_id)
            await msg.unpin()
            await S.safe_edit(ctx.message, S.ui_ok('message unpinned'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)))

    @commands.command(name='animatetype', brief='Animate text character by character')
    async def animatetype(self, ctx, *, text: str=''):
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: animatetype <text>'))
        import asyncio
        for i in range(1, len(text) + 1):
            await S.safe_edit(ctx.message, text[:i])
            await asyncio.sleep(jitter(0.08))

    @commands.command(name='ragebait', brief='Post a random ragebait message')
    async def ragebait(self, ctx):
        import random
        baits = ['pineapple on pizza is actually good', 'tabs are objectively better than spaces', 'the moon landing was faked', 'anime is better than cartoons', 'cats are better than dogs', 'mint chocolate chip is the worst flavor', 'water is wet', 'a hot dog is a sandwich']
        await S.safe_edit(ctx.message, random.choice(baits))

    @commands.command(name='therapy', brief='Send a supportive message')
    async def therapy(self, ctx):
        import random
        messages = ['you got this 💪', "take a deep breath. you're doing great.", 'one step at a time ✨', "it's okay to rest. progress is not linear.", 'you are not your mistakes.', 'your feelings are valid.', 'tomorrow is a new day 🌅']
        await S.safe_edit(ctx.message, random.choice(messages))

    async def _start_bg(self):
        if not getattr(self, '_need_bg', False):
            return
        self._need_bg = False

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            await self._start_bg()
        except Exception:
            pass

    def cog_unload(self):
        for t in _typing_tasks.values():
            if t and (not t.done()):
                t.cancel()
        _typing_tasks.clear()

    @commands.command(name='ts', aliases=['transcribe', 'vtts', 'voicets'], brief='Transcribe a replied voice message')
    async def ts(self, ctx):
        import aiohttp, os, tempfile, asyncio
        ref = ctx.message.reference
        if not ref or not ref.message_id:
            return await S.safe_edit(ctx.message, S.ui_err('reply to a voice message with .ts'))
        try:
            msg = ref.resolved
            if msg is None:
                msg = await ctx.channel.fetch_message(ref.message_id)
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err(f'could not fetch message: {e}'))
        if msg is None:
            return await S.safe_edit(ctx.message, S.ui_err('could not resolve replied message'))

        is_voice = False
        try:
            flags = getattr(msg, 'flags', None)
            if flags is not None and getattr(flags, 'voice', False):
                is_voice = True
            elif flags is not None and int(getattr(flags, 'value', 0)) & (1 << 13):
                is_voice = True
        except Exception:
            pass

        att = None
        for a in (msg.attachments or []):
            ct = (getattr(a, 'content_type', None) or '').lower()
            name = (getattr(a, 'filename', '') or '').lower()
            dur = getattr(a, 'duration', None) or getattr(a, 'duration_secs', None)
            if ct.startswith('audio/') or name.endswith(('.ogg', '.opus', '.mp3', '.wav', '.m4a', '.webm')) or dur is not None:
                att = a
                break
        if att is None and msg.attachments:
            att = msg.attachments[0]
        if att is None:
            return await S.safe_edit(ctx.message, S.ui_err('no audio attachment on that message'))

        await S.safe_edit(ctx.message, S.ui_info('transcribing…'))
        tmpdir = tempfile.mkdtemp(prefix='wilt_ts_')
        src_path = os.path.join(tmpdir, 'voice.ogg')
        wav_path = os.path.join(tmpdir, 'voice.wav')
        try:
            await att.save(src_path)
        except Exception:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(att.url) as r:
                        data = await r.read()
                with open(src_path, 'wb') as f:
                    f.write(data)
            except Exception as e:
                return await S.safe_edit(ctx.message, S.ui_err(f'download failed: {e}'))

        async def run_ffmpeg():
            try:
                proc = await asyncio.create_subprocess_exec(
                    'ffmpeg', '-y', '-i', src_path, '-ar', '16000', '-ac', '1', wav_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.wait(), timeout=60)
                return proc.returncode == 0 and os.path.exists(wav_path)
            except Exception:
                return False

        has_wav = await run_ffmpeg()
        upload_path = wav_path if has_wav else src_path
        upload_name = 'voice.wav' if has_wav else 'voice.ogg'
        content_type = 'audio/wav' if has_wav else 'audio/ogg'

        text = None
        backend = None
        errors = []

        groq_key = (getattr(S, 'GROQ_API_KEY', '') or os.environ.get('GROQ_API_KEY') or '').strip()
        oai_key = (getattr(S, 'OPENAI_API_KEY', '') or os.environ.get('OPENAI_API_KEY') or '').strip()
        custom_url = (getattr(S, 'WHISPER_API_URL', '') or os.environ.get('WHISPER_API_URL') or '').strip()
        custom_key = (getattr(S, 'WHISPER_API_KEY', '') or os.environ.get('WHISPER_API_KEY') or '').strip()

        async def whisper_post(url, key, model, path, fname, ctype):
            import io
            with open(path, 'rb') as fh:
                blob = fh.read()
            form = aiohttp.FormData()
            form.add_field('file', io.BytesIO(blob), filename=fname, content_type=ctype)
            form.add_field('model', model)
            form.add_field('response_format', 'json')
            headers = {}
            if key:
                headers['Authorization'] = f'Bearer {key}'
            timeout = aiohttp.ClientTimeout(total=90)
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.post(url, data=form, headers=headers) as r:
                    body = await r.text()
                    if r.status >= 400:
                        raise RuntimeError(f'{r.status}: {body[:160]}')
                    import json as _json
                    try:
                        data = _json.loads(body)
                    except Exception:
                        return body.strip()
                    return (data.get('text') or data.get('transcript') or '').strip()

        if custom_url and not text:
            try:
                text = await whisper_post(
                    custom_url.rstrip('/') + ('' if custom_url.endswith('transcriptions') else '/audio/transcriptions'),
                    custom_key, 'whisper-1', upload_path, upload_name, content_type,
                )
                backend = 'custom'
            except Exception as e:
                errors.append(f'custom:{e}')

        if groq_key and not text:
            try:
                text = await whisper_post(
                    'https://api.groq.com/openai/v1/audio/transcriptions',
                    groq_key, 'whisper-large-v3-turbo', upload_path, upload_name, content_type,
                )
                backend = 'groq'
            except Exception as e:
                errors.append(f'groq:{e}')

        if oai_key and not text:
            try:
                text = await whisper_post(
                    'https://api.openai.com/v1/audio/transcriptions',
                    oai_key, 'whisper-1', upload_path, upload_name, content_type,
                )
                backend = 'openai'
            except Exception as e:
                errors.append(f'openai:{e}')

        if not text:
            try:
                import speech_recognition as sr
                if not has_wav:
                    has_wav = await run_ffmpeg()
                if has_wav:
                    def _google():
                        r = sr.Recognizer()
                        with sr.AudioFile(wav_path) as source:
                            audio = r.record(source)
                        return r.recognize_google(audio)
                    text = await asyncio.get_event_loop().run_in_executor(None, _google)
                    backend = 'google'
            except Exception as e:
                errors.append(f'google:{e}')

        try:
            for p in (src_path, wav_path):
                if os.path.exists(p):
                    os.remove(p)
            os.rmdir(tmpdir)
        except Exception:
            pass

        if not text:
            hint = (
                'set GROQ_API_KEY (free) or OPENAI_API_KEY in .env\n'
                '  optional: pip install SpeechRecognition for offline-ish google fallback'
            )
            detail = errors[0] if errors else 'no backend'
            return await S.safe_edit(ctx.message, S.ui_err(f'transcribe failed ({detail})\n  {hint}'))

        author = getattr(getattr(msg, 'author', None), 'name', '?')
        dur = getattr(att, 'duration', None) or getattr(att, 'duration_secs', None)
        rows = [
            f'  {S.DIM}from{S.RESET}   {author}',
            f'  {S.DIM}engine{S.RESET} {backend}',
        ]
        if dur:
            rows.append(f'  {S.DIM}dur{S.RESET}    {float(dur):.1f}s')
        rows.append('')
        for i in range(0, len(text), 180):
            rows.append(f'  {text[i:i+180]}')
        await S.safe_edit(ctx.message, S.ui_box('transcript', rows))

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))
