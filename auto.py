import asyncio
import time
import urllib.parse
import aiohttp
import discord
from discord.ext import commands
from . import state as S
from .antid import jitter

def _get_token(bot=None) -> str:
    return S._get_token(bot)

def _emoji_encode(emoji: str) -> str:
    em = (emoji or '').strip()
    if not em:
        return ''
    if em.startswith('<') and em.endswith('>') and (':' in em):
        parts = em.strip('<>').split(':')
        if len(parts) >= 3:
            em = f'{parts[-2]}:{parts[-1]}'
    return urllib.parse.quote(em, safe='')
_react_rl: dict[int, float] = {}

async def _react(message: discord.Message, emoji: str, *, burst: bool=False) -> bool:
    ch_id = getattr(message.channel, 'id', 0)
    unlock = _react_rl.get(ch_id, 0.0)
    now = time.time()
    if unlock > now:
        wait = unlock - now
        if wait > 30:
            print(f'[auto] react rate-limited for {wait:.0f}s on channel {ch_id}, skipping')
            return False
        await asyncio.sleep(wait)
    if burst:
        ok, retry = await _put_reaction_rl(message, emoji, burst=True)
        if retry:
            _react_rl[ch_id] = time.time() + retry
            return False
        if ok:
            return True
    ok, retry = await _put_reaction_rl(message, emoji, burst=False)
    if retry:
        _react_rl[ch_id] = time.time() + retry
        return False
    if ok:
        return True
    try:
        await message.add_reaction(emoji)
        return True
    except discord.HTTPException as e:
        if e.status == 429:
            ra = getattr(e, 'retry_after', 5.0) or 5.0
            _react_rl[ch_id] = time.time() + float(ra)
            print(f'[auto] add_reaction 429 - backing off {ra:.1f}s')
        else:
            print(f'[auto] add_reaction: {e}')
        return False
    except Exception as e:
        print(f'[auto] add_reaction fallback: {e}')
        return False

async def _put_reaction_rl(message: discord.Message, emoji: str, *, burst: bool=False) -> tuple:
    token = _get_token()
    if not token:
        print('[auto] put_reaction: no token available')
        return (False, 0.0)
    em_enc = _emoji_encode(emoji)
    if not em_enc:
        return (False, 0.0)
    typ = 1 if burst else 0
    base = f'https://discord.com/api/v9/channels/{message.channel.id}/messages/{message.id}/reactions/{em_enc}/@me'
    urls = [f'{base}?type={typ}', base]
    headers = {'Authorization': str(token).strip(), 'User-Agent': getattr(S, 'USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.8059.80 Safari/537.36')}
    try:
        async with aiohttp.ClientSession() as sess:
            for url in urls:
                try:
                    async with sess.put(url, headers=headers, data=b'') as r:
                        if r.status in (200, 201, 204):
                            return (True, 0.0)
                        if r.status == 429:
                            try:
                                data = await r.json(content_type=None)
                                ra = float(data.get('retry_after', 5.0))
                            except Exception:
                                ra = 5.0
                            print(f'[auto] put_reaction 429 retry_after={ra:.1f}s')
                            return (False, max(0.5, ra))
                        body = ''
                        try:
                            body = await r.text()
                        except Exception:
                            pass
                        print(f'[auto] put_reaction HTTP {r.status}: {body[:120]}')
                        if r.status not in (400, 401):
                            return (False, 0.0)
                        continue
                except Exception as e:
                    print(f'[auto] put_reaction req: {e}')
                    continue
    except Exception as e:
        print(f'[auto] put_reaction session: {e}')
    return (False, 0.0)

def _parse_mode(s: str):
    t = (s or '').lower().strip()
    if t in ('super', 's', 'burst', 'sr', 'nitro'):
        return 'super'
    if t in ('regular', 'r', 'normal', 'n', 'reg'):
        return 'regular'
    return None

def _parse_user(s: str):
    t = (s or '').strip()
    if t.startswith('<@') and t.endswith('>'):
        t = t[2:-1].lstrip('!')
    if t.isdigit() and len(t) >= 15:
        return int(t)
    return None

def _parse_react_args(raw: str):
    parts = (raw or '').split()
    emoji = ''
    mode = 'regular'
    user_id = None
    for p in parts:
        m = _parse_mode(p)
        if m is not None:
            mode = m
            continue
        uid = _parse_user(p)
        if uid is not None:
            user_id = uid
            continue
        if not emoji:
            emoji = p
    return (emoji, mode, user_id)

def _parse_multireact_args(raw: str):
    parts = (raw or '').split()
    emojis = []
    mode = 'regular'
    user_id = None
    for p in parts:
        m = _parse_mode(p)
        if m is not None:
            mode = m
            continue
        uid = _parse_user(p)
        if uid is not None:
            user_id = uid
            continue
        emojis.append(p)
    return (emojis, mode, user_id)

def _ar_get_global():
    g = S.AUTO_RESPONSES.get("react") or {}
    em = g.get("global")
    return {'emoji': em, 'mode': g.get("global_mode", "regular")} if em else None

def _ar_set(user_id, emoji: str, mode: str):
    if user_id is None:
        S.AUTO_RESPONSES.setdefault('react', {})['global'] = emoji
        S.AUTO_RESPONSES['react']['global_mode'] = mode
    else:
        if not isinstance(S._autoreact_users, dict):
            S._autoreact_users = {}
        S._autoreact_users[user_id] = {'emoji': emoji, 'mode': mode}

def _ar_clear(user_id):
    if user_id is None:
        S.AUTO_RESPONSES.pop('react', None)
        if isinstance(S._autoreact_users, dict):
            S._autoreact_users.clear()
    elif isinstance(S._autoreact_users, dict):
        S._autoreact_users.pop(user_id, None)

def _mr_bucket() -> dict:
    old = S.AUTO_RESPONSES.pop('multireact', None)
    if old and isinstance(old, dict) and old.get("emojis"):
        bucket = S.AUTO_RESPONSES.setdefault('multireact_users', {})
        uid = old.get("user_id")
        key = str(uid) if uid is not None else '__self__'
        bucket.setdefault(key, {'emojis': old['emojis'], 'mode': old.get("mode", "regular"), 'user_id': uid})
    return S.AUTO_RESPONSES.setdefault('multireact_users', {})

def _mr_set(user_id, emojis: list, mode: str):
    bucket = _mr_bucket()
    key = str(user_id) if user_id is not None else '__self__'
    bucket[key] = {'emojis': emojis, 'mode': mode, 'user_id': user_id}

def _mr_clear(user_id):
    bucket = _mr_bucket()
    if user_id is None:
        bucket.clear()
    else:
        bucket.pop(str(user_id), None)

class AutoCog(commands.Cog, name='auto'):

    def __init__(self, bot):
        self.bot = bot
        if not isinstance(getattr(S, '_autoreact_users', None), dict):
            S._autoreact_users = {}
        if not isinstance(getattr(S, 'AUTO_RESPONSES', None), dict):
            S.AUTO_RESPONSES = {}
        if not isinstance(getattr(S, '_mimic_dict', None), dict):
            S._mimic_dict = {}

    def _ar_rows(self) -> list:
        rows = []
        g = _ar_get_global()
        if g:
            rows.append(f"  {S.GREY}*{S.RESET} you  {g['emoji']}  {S.DIM}{g['mode']}{S.RESET}")
        for uid, entry in (S._autoreact_users or {}).items():
            if isinstance(entry, dict):
                rows.append(f'  {S.GREY}*{S.RESET} <@{uid}>  {entry.get("emoji")}  {S.DIM}{entry.get("mode", "regular")}{S.RESET}')
            else:
                rows.append(f'  {S.GREY}*{S.RESET} <@{uid}>  {entry}  {S.DIM}regular{S.RESET}')
        return rows

    def _mr_rows(self) -> list:
        rows = []
        for key, entry in _mr_bucket().items():
            if not isinstance(entry, dict):
                continue
            uid = entry.get("user_id")
            target = 'you' if uid is None else f'<@{uid}>'
            ems = ' '.join(entry.get("emojis") or [])
            mode = entry.get("mode", "regular")
            rows.append(f"  {S.GREY}*{S.RESET} {ems or '-'}  {S.DIM}{mode}{S.RESET}  → {target}")
        return rows

    @commands.command(name='autoreact', brief='Auto-react to messages  .autoreact <emoji> [super|regular] [@user]')
    async def autoreact(self, ctx, *, args: str=''):
        raw = (args or '').strip()
        if not raw:
            rows = self._ar_rows()
            pfx = S.PREFIX
            return await S.safe_edit(ctx.message, S._paginate('autoreact', 'emoji [super|regular] [@user] | clear', rows) if rows else S.ui_info(f'off - {pfx}autoreact <emoji> [super|regular] [@user]'))
        low = raw.lower()
        if low.split()[0] in ('clear', 'off', 'reset', 'disable'):
            rest = raw.split(None, 1)[1] if len(raw.split()) > 1 else ''
            uid = _parse_user(rest) if rest else None
            _ar_clear(uid)
            return await S.safe_edit(ctx.message, S.ui_ok(f'autoreact cleared for <@{uid}>' if uid is not None else 'autoreact cleared'))
        emoji, mode, user_id = _parse_react_args(raw)
        if not emoji:
            return await S.safe_edit(ctx.message, S.ui_err(f'usage: {S.PREFIX}autoreact <emoji> [super|regular] [@user]'))
        _ar_set(user_id, emoji, mode)
        msg = f'autoreact → {emoji} ({mode}) for <@{user_id}>' if user_id is not None else f'autoreact → {emoji} ({mode}) on your messages'
        await S.safe_edit(ctx.message, S.ui_ok(msg))
        try:
            await asyncio.sleep(0.05)
            await _react(ctx.message, emoji, burst=mode == 'super')
        except Exception as e:
            print(f'[auto] autoreact confirm: {e}')

    @commands.command(name='multireact', aliases=['mr'], brief='Multi-react to messages  .multireact <emojis> [super|regular] [@user]')
    async def multireact(self, ctx, *, args: str=''):
        raw = (args or '').strip()
        if not raw:
            rows = self._mr_rows()
            pfx = S.PREFIX
            return await S.safe_edit(ctx.message, S._paginate('multireact', 'emojis [super|regular] [@user] | clear', rows) if rows else S.ui_info(f'off - {pfx}multireact <emoji...> [super|regular] [@user]'))
        low = raw.lower()
        if low.split()[0] in ('clear', 'off', 'reset', 'disable'):
            rest = raw.split(None, 1)[1] if len(raw.split()) > 1 else ''
            uid = _parse_user(rest) if rest else None
            _mr_clear(uid)
            return await S.safe_edit(ctx.message, S.ui_ok(f'multireact cleared for <@{uid}>' if uid is not None else 'multireact cleared'))
        emojis, mode, user_id = _parse_multireact_args(raw)
        if not emojis:
            return await S.safe_edit(ctx.message, S.ui_err(f'usage: {S.PREFIX}multireact <emoji...> [super|regular] [@user]'))
        _mr_set(user_id, emojis, mode)
        target = f'<@{user_id}>' if user_id is not None else 'your messages'
        await S.safe_edit(ctx.message, S.ui_ok(f"multireact → {' '.join(emojis)} ({mode}) → {target}"))
        try:
            await asyncio.sleep(0.05)
            burst = mode == 'super'
            for em in emojis[:5]:
                await _react(ctx.message, em, burst=burst)
                await asyncio.sleep(0.05)
        except Exception as e:
            print(f'[auto] multireact confirm: {e}')

    @commands.command(name='mimic', brief='Mimic a user in this channel  .mimic @user')
    async def mimic(self, ctx, user: discord.User=None):
        if not user:
            return await S.safe_edit(ctx.message, S.ui_err('usage: mimic <@user>'))
        S._mimic_dict[ctx.channel.id] = user.id
        await S.safe_edit(ctx.message, S.ui_ok(f'mimicking {user}'))

    @commands.command(name='unmimic', brief='Stop mimicking in this channel')
    async def unmimic(self, ctx):
        if ctx.channel.id not in S._mimic_dict:
            return await S.safe_edit(ctx.message, S.ui_warn('not mimicking anyone here'))
        S._mimic_dict.pop(ctx.channel.id, None)
        await S.safe_edit(ctx.message, S.ui_ok('mimic stopped'))

    @commands.command(name='stopmimic', brief='Stop all active mimics')
    async def stopmimic(self, ctx):
        count = len(S._mimic_dict)
        S._mimic_dict.clear()
        await S.safe_edit(ctx.message, S.ui_ok(f'all mimics stopped ({count} active)'))

    @commands.command(name='mimiclist', brief='List active mimics')
    async def mimiclist(self, ctx):
        rows = [f'  {S.GREY}*{S.RESET} <#{ch_id}> → <@{uid}>' for ch_id, uid in S._mimic_dict.items()]
        await S.safe_edit(ctx.message, S._paginate('mimics', f'{len(rows)} active', rows) if rows else S.ui_info('no active mimics'))

    @commands.command(name='autoaddback', brief='Toggle auto friend-accept')
    async def autoaddback(self, ctx, toggle: str=''):
        if toggle:
            S._autoaddback = toggle.lower() not in ('off', 'disable', 'false', '0')
        else:
            S._autoaddback = not getattr(S, '_autoaddback', False)
        await S.safe_edit(ctx.message, S.ui_ok(f"autoaddback → {('on' if S._autoaddback else 'off')}"))

    @commands.command(name='nitrosniper', brief='Toggle Nitro link sniper')
    async def nitrosniper(self, ctx, toggle: str=''):
        if toggle:
            S._nitrosniper_enabled = toggle.lower() not in ('off', 'disable', 'false', '0')
        else:
            S._nitrosniper_enabled = not getattr(S, '_nitrosniper_enabled', True)
        await S.safe_edit(ctx.message, S.ui_ok(f"nitro sniper → {('on' if S._nitrosniper_enabled else 'off')}"))

    @commands.command(name='vsniper', brief='Toggle vanity URL sniper')
    async def vsniper(self, ctx, toggle: str=''):
        if not hasattr(S, '_vsniper_enabled'):
            S._vsniper_enabled = False
        if toggle:
            S._vsniper_enabled = toggle.lower() not in ('off', 'disable', 'false', '0')
        else:
            S._vsniper_enabled = not S._vsniper_enabled
        await S.safe_edit(ctx.message, S.ui_ok(f"vsniper → {('on' if S._vsniper_enabled else 'off')}"))

    @commands.command(name='rotatename', brief='Rotate display name every ~2s  .rotatename name1, name2')
    async def rotatename(self, ctx, *, names: str=''):
        if not names or names.lower() in ('off', 'stop', 'clear'):
            t = getattr(self, '_name_rot_task', None)
            if t and (not t.done()):
                t.cancel()
            self._name_rot_task = None
            return await S.safe_edit(ctx.message, S.ui_ok('name rotation stopped'))
        parts = [p.strip() for p in names.replace('|', ',').split(',') if p.strip()]
        if len(parts) < 2:
            return await S.safe_edit(ctx.message, S.ui_err('usage: rotatename name1, name2, name3'))
        t = getattr(self, '_name_rot_task', None)
        if t and (not t.done()):
            t.cancel()

        async def _loop():
            i = 0
            delay = 2.0
            while True:
                try:
                    name = parts[i % len(parts)][:32]
                    try:
                        await self.bot.user.edit(display_name=name)
                    except TypeError:
                        await self.bot.user.edit(username=name)
                    delay = 2.0
                except Exception as e:
                    msg = str(e).lower()
                    print(f'[auto] rotatename: {e}')
                    if '429' in msg or 'rate' in msg or 'too many' in msg:
                        delay = min(delay * 2, 30.0)
                    else:
                        delay = min(max(delay, 0.5), 10.0)
                i += 1
                await asyncio.sleep(delay)
        self._name_rot_task = asyncio.create_task(_loop())
        await S.safe_edit(ctx.message, S.ui_ok(f'rotating display name ~2s ({len(parts)} names, auto-backoff on rate limit)'))

    @commands.command(name='rotateservername', brief='Rotate server name  .rotateservername name1, name2')
    async def rotateservername(self, ctx, *, names: str=''):
        if not ctx.guild:
            return await S.safe_edit(ctx.message, S.ui_err('server only'))
        if not names or names.lower() in ('off', 'stop', 'clear'):
            tasks = getattr(self, '_sname_rot_tasks', {})
            t = tasks.pop(ctx.guild.id, None)
            if t and (not t.done()):
                t.cancel()
            return await S.safe_edit(ctx.message, S.ui_ok('server name rotation stopped'))
        parts = [p.strip() for p in names.replace('|', ',').split(',') if p.strip()]
        parts = [p[:100] for p in parts if len(p) >= 2]
        if len(parts) < 2:
            return await S.safe_edit(ctx.message, S.ui_err('usage: rotateservername name1, name2 (each 2-100 chars)'))
        if not hasattr(self, '_sname_rot_tasks'):
            self._sname_rot_tasks = {}
        old = self._sname_rot_tasks.get(ctx.guild.id)
        if old and (not old.done()):
            old.cancel()
        guild = ctx.guild

        async def _loop():
            i = 0
            delay = 2.0
            while True:
                try:
                    nm = parts[i % len(parts)][:100]
                    if len(nm) < 2:
                        i += 1
                        continue
                    await guild.edit(name=nm)
                    delay = 2.0
                except Exception as e:
                    msg = str(e).lower()
                    print(f'[auto] rotateservername: {e}')
                    if '429' in msg or 'rate' in msg or 'too many' in msg:
                        delay = min(delay * 2, 60.0)
                    else:
                        delay = min(max(delay, 0.5), 15.0)
                i += 1
                await asyncio.sleep(delay)
        self._sname_rot_tasks[guild.id] = asyncio.create_task(_loop())
        await S.safe_edit(ctx.message, S.ui_ok(f'rotating server name ~2s ({len(parts)} names, auto-backoff)'))

    async def _apply_reacts(self, message: discord.Message, *, is_self: bool):
        emoji = mode = None
        entry = (S._autoreact_users or {}).get(message.author.id)
        if isinstance(entry, dict):
            emoji = entry.get("emoji")
            mode = entry.get("mode", "regular")
        elif entry:
            emoji, mode = (entry, 'regular')
        if not emoji and is_self:
            g = _ar_get_global()
            if g:
                emoji = g['emoji']
                mode = g['mode']
        if emoji:
            try:
                gcount = 0
                try:
                    g = message.guild
                    gcount = int(getattr(g, 'member_count', 0) or 0) if g else 0
                except Exception:
                    pass
                delay = 0.08 if gcount < 500 else 0.25 if gcount < 5000 else 0.6
                await asyncio.sleep(delay)
                await _react(message, emoji, burst=mode == 'super')
            except Exception as e:
                print(f'[auto] autoreact: {e}')
        for key, entry in list(_mr_bucket().items()):
            if not isinstance(entry, dict):
                continue
            uid = entry.get("user_id")
            emojis = entry.get("emojis") or []
            burst = entry.get("mode", "regular") == 'super'
            match = is_self if uid is None else message.author.id == uid
            if not match or not emojis:
                continue
            for em in emojis:
                try:
                    await asyncio.sleep(0.05)
                    await _react(message, em, burst=burst)
                except Exception as e:
                    print(f'[auto] multireact: {e}')

    async def _handle_self_message(self, message: discord.Message):
        await self._apply_reacts(message, is_self=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.bot.user:
            return
        me = self.bot.user.id
        if message.author.id == me:
            return
        uid = S._mimic_dict.get(message.channel.id)
        if uid and message.author.id == uid and message.content:
            try:
                await asyncio.sleep(jitter(1.2))
                await S.safe_send(message.channel, message.content)
            except Exception:
                pass
        await self._apply_reacts(message, is_self=False)

    def cog_unload(self):
        t = getattr(self, '_name_rot_task', None)
        if t and (not t.done()):
            t.cancel()
        for t in getattr(self, '_sname_rot_tasks', {}).values():
            if t and (not t.done()):
                t.cancel()

async def setup(bot):
    await bot.add_cog(AutoCog(bot))
