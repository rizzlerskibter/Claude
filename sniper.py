import asyncio, time, re, aiohttp, discord
from discord.ext import commands
from . import state as S
from .antid import jitter
_GIFT_RE = re.compile('(?:discord\\.gift/|discordapp\\.com/gifts/|discord\\.com/gifts/)([a-zA-Z0-9]+)', re.I)

async def _capmonster_style(session, create_url, result_url, key, sitekey, page_url, task_type='HCaptchaTaskProxyless'):
    create_body = {
        'clientKey': key,
        'task': {
            'type': task_type,
            'websiteURL': page_url,
            'websiteKey': sitekey,
        },
    }
    async with session.post(create_url, json=create_body) as r:
        data = await r.json(content_type=None)
    if data.get('errorId'):
        print(f'[nitrosnipe] create {create_url}: {data}')
        return None
    task_id = data.get('taskId')
    if not task_id:
        print(f'[nitrosnipe] no taskId: {data}')
        return None
    for _ in range(40):
        await asyncio.sleep(4)
        async with session.post(result_url, json={'clientKey': key, 'taskId': task_id}) as r:
            res = await r.json(content_type=None)
        if res.get('status') == 'ready':
            sol = res.get('solution') or {}
            return sol.get('gRecaptchaResponse') or sol.get('token') or sol.get('respKey')
        if res.get('errorId'):
            print(f'[nitrosnipe] result err: {res}')
            return None
    return None


async def _solve_hcaptcha(sitekey: str, page_url: str='https://discord.com', rqdata: str='', *, enterprise: bool=False, user_agent: str=''):
    import os
    key = (
        getattr(S, 'CAPTCHA_API_KEY', '')
        or os.environ.get('CAPTCHA_API_KEY')
        or os.environ.get('TWOCAPTCHA_API_KEY')
        or os.environ.get('CAPMONSTER_API_KEY')
        or os.environ.get('ANTICAPTCHA_API_KEY')
        or os.environ.get('CAPSOLVER_API_KEY')
        or os.environ.get('NONECAP_KEY')
        or os.environ.get('NONECAP_API_KEY')
        or os.environ.get('YESCAPTCHA_KEY')
        or os.environ.get('SOLVECAPTCHA_KEY')
        or ''
    ).strip()
    if not key:
        print('[captcha] no CAPTCHA_API_KEY / NONECAP_KEY')
        return None
    provider = (getattr(S, 'CAPTCHA_PROVIDER', '') or os.environ.get('CAPTCHA_PROVIDER') or '').strip().lower()
    if not provider or provider == '2captcha':
        if key.startswith('nc_live_'):
            provider = 'nonecap'
        elif key.startswith('CAP-') or len(key) == 32:
            pass
    if not provider:
        provider = '2captcha'
    ua = user_agent or getattr(S, 'USER_AGENT', '') or (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) discord/1.0.9262 Chrome/155.0.8059.80 Electron/36.0.0 Safari/537.36'
    )
    page_url = page_url or 'https://discord.com'
    try:
        async with aiohttp.ClientSession() as s:
            if provider in ('nonecap', 'none', 'nc'):
                headers = {
                    'Authorization': f'Bearer {key}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                }
                cap_type = 'hcaptcha_enterprise' if (enterprise or rqdata) else 'hcaptcha'
                body = {
                    'type': cap_type,
                    'sitekey': sitekey,
                    'url': page_url,
                }
                if rqdata:
                    body['rqdata'] = rqdata
                if ua:
                    body['user_agent'] = ua
                print(f'[captcha] nonecap type={cap_type} sitekey={sitekey[:12]}… rqdata={bool(rqdata)}')
                async with s.post(
                    'https://api.nonecap.com/v1/solves',
                    headers=headers,
                    params={'wait': 90},
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as r:
                    data = await r.json(content_type=None)
                    status = r.status
                if status == 200 and isinstance(data, dict) and data.get('token'):
                    tok = data.get('token')
                    print(f'[captcha] nonecap solved len={len(tok or "")}')
                    return tok
                if status in (200, 202) and isinstance(data, dict) and data.get('id') and not data.get('token'):
                    sid = data.get('id')
                    for _ in range(45):
                        await asyncio.sleep(2)
                        async with s.get(
                            f'https://api.nonecap.com/v1/solves/{sid}',
                            headers=headers,
                            params={'wait': 90},
                            timeout=aiohttp.ClientTimeout(total=100),
                        ) as r2:
                            res = await r2.json(content_type=None)
                        st = (res or {}).get('status')
                        if (res or {}).get('token') or st == 'solved':
                            tok = (res or {}).get('token')
                            print(f'[captcha] nonecap polled solved len={len(tok or "")}')
                            return tok
                        if st in ('failed', 'cancelled', 'expired'):
                            print(f'[captcha] nonecap {st}: {res}')
                            return None
                print(f'[captcha] nonecap fail status={status} data={str(data)[:200]}')
                return None

            if provider in ('capmonster', 'capmonster.cloud', 'capmonstercloud'):
                task_type = 'HCaptchaTaskProxyless'
                return await _capmonster_style(
                    s, 'https://api.capmonster.cloud/createTask', 'https://api.capmonster.cloud/getTaskResult',
                    key, sitekey, page_url, task_type,
                )
            if provider in ('anticaptcha', 'anti-captcha', 'anti'):
                return await _capmonster_style(
                    s, 'https://api.anti-captcha.com/createTask', 'https://api.anti-captcha.com/getTaskResult',
                    key, sitekey, page_url,
                )
            if provider in ('capsolver',):
                return await _capmonster_style(
                    s, 'https://api.capsolver.com/createTask', 'https://api.capsolver.com/getTaskResult',
                    key, sitekey, page_url,
                )
            if provider in ('nextcaptcha', 'next'):
                return await _capmonster_style(
                    s, 'https://api.nextcaptcha.com/createTask', 'https://api.nextcaptcha.com/getTaskResult',
                    key, sitekey, page_url,
                )
            if provider in ('yescaptcha', 'yes'):
                return await _capmonster_style(
                    s, 'https://api.yescaptcha.com/createTask', 'https://api.yescaptcha.com/getTaskResult',
                    key, sitekey, page_url,
                )
            if provider in ('captchapi', 'capi'):
                return await _capmonster_style(
                    s, 'https://api.captchapi.com/createTask', 'https://api.captchapi.com/getTaskResult',
                    key, sitekey, page_url,
                )
            if provider in ('nopecha',):
                async with s.post('https://api.nopecha.com/token', json={
                    'key': key, 'type': 'hcaptcha', 'sitekey': sitekey, 'url': page_url,
                }) as r:
                    data = await r.json(content_type=None)
                if data.get('data'):
                    return data.get('data')
                print(f'[captcha] nopecha: {data}')
                return None

            host_map = {
                '2captcha': '2captcha.com',
                'rucaptcha': 'rucaptcha.com',
                'solvecaptcha': 'solvecaptcha.com',
                'deathbycaptcha': 'api.dbcapi.me',
            }
            host = host_map.get(provider, '2captcha.com')
            params = {
                'key': key,
                'method': 'hcaptcha',
                'sitekey': sitekey,
                'pageurl': page_url,
                'json': 1,
            }
            if enterprise or rqdata:
                params['enterprise'] = 1
            if rqdata:
                params['data'] = rqdata
            async with s.get(f'https://{host}/in.php', params=params) as r:
                data = await r.json(content_type=None)
            if data.get('status') != 1:
                print(f'[captcha] {host} create: {data}')
                return None
            rid = data.get('request')
            for _ in range(40):
                await asyncio.sleep(5)
                async with s.get(f'https://{host}/res.php', params={'key': key, 'action': 'get', 'id': rid, 'json': 1}) as r:
                    res = await r.json(content_type=None)
                if res.get('status') == 1:
                    return res.get('request')
                if res.get('request') not in ('CAPCHA_NOT_READY', 'CAPTCHA_NOT_READY'):
                    if res.get('status') == 0 and 'NOT_READY' not in str(res.get('request', '')):
                        print(f'[captcha] {host} result: {res}')
                        return None
            return None
    except Exception as e:
        print(f'[captcha] solve error: {e}')
        return None


async def _redeem_nitro(token, code, channel_id, captcha_key=None, captcha_rqtoken=None):
    headers = {'Authorization': token, 'Content-Type': 'application/json', 'User-Agent': getattr(S, 'USER_AGENT', 'Mozilla/5.0')}
    payload = {'channel_id': str(channel_id)}
    if captcha_key:
        payload['captcha_key'] = captcha_key
    if captcha_rqtoken:
        payload['captcha_rqtoken'] = captcha_rqtoken
    async with aiohttp.ClientSession() as s:
        async with s.post(f'https://discord.com/api/v9/entitlements/gift-codes/{code}/redeem', headers=headers, json=payload) as r:
            status = r.status
            try:
                body = await r.text()
            except Exception:
                body = ''
    return (status, body)

class SniperCog(commands.Cog, name='sniper'):

    def __init__(self, bot):
        self.bot = bot
        self._ignore_users: set = set()
        self._ignore_channels: set = set()
        self._seen_codes: set = set()

    @commands.command(name='snipereon', aliases=['sniperon'], brief='Enable sniper')
    async def sniper_on(self, ctx):
        S.SNIPER_ENABLED = True
        await S.safe_edit(ctx.message, S.ui_ok('sniper → on'))

    @commands.command(name='snipereoff', aliases=['sniperoff'], brief='Disable sniper')
    async def sniper_off(self, ctx):
        S.SNIPER_ENABLED = False
        await S.safe_edit(ctx.message, S.ui_ok('sniper → off'))

    @commands.command(name='snipestatus', brief='Sniper status')
    async def snipe_status(self, ctx):
        await S.safe_edit(ctx.message, S.ui_box('sniper', [f'  {S.DIM}enabled{S.RESET}   {S.SNIPER_ENABLED}', f'  {S.DIM}nitro{S.RESET}     {S._nitrosniper_enabled}', f'  {S.DIM}giveaway{S.RESET}  {S._giveaway_enabled}']))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not S.SNIPER_ENABLED:
            return
        if not message or not message.author:
            return
        if self.bot.user and message.author.id == self.bot.user.id:
            return
        if int(message.author.id) in self._ignore_users:
            return
        if message.channel and message.channel.id in self._ignore_channels:
            return
        S._snipe_cache[message.channel.id] = {'author': str(message.author), 'author_id': message.author.id, 'content': message.content or '[no text]', 'time': time.time(), 'attachments': [a.url for a in message.attachments or []], 'embed_count': len(message.embeds or []), 'reactions': [str(r.emoji) for r in message.reactions or []]}

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not S.SNIPER_ENABLED:
            return
        if before.content == after.content:
            return
        S._editsnipe_cache[before.channel.id] = {'author': str(before.author), 'author_id': before.author.id, 'before': before.content or '[no text]', 'after': after.content or '[no text]', 'time': time.time()}

    @commands.Cog.listener()
    async def on_message(self, message):
        if not S._nitrosniper_enabled:
            return
        if not self.bot.user or message.author.id == self.bot.user.id:
            return
        content = message.content or ''
        if 'discord.gift/' not in content and 'discordapp.com/gifts/' not in content and ('discord.com/gifts/' not in content):
            return
        token = S._get_token(self.bot)
        if not token:
            return
        for match in _GIFT_RE.finditer(content):
            code = match.group(1)
            if len(code) < 16:
                continue
            if code in self._seen_codes:
                continue
            self._seen_codes.add(code)
            if len(self._seen_codes) > 500:
                self._seen_codes = set(list(self._seen_codes)[-200:])
            await asyncio.sleep(jitter(0.4))
            try:
                status, body = await _redeem_nitro(token, code, message.channel.id)
            except Exception as e:
                print(f'[nitrosnipe] {e}')
                continue
            captcha_sitekey = None
            captcha_rqtoken = None
            try:
                import json as _json
                data = _json.loads(body) if body else {}
            except Exception:
                data = {}
            if isinstance(data, dict):
                captcha_sitekey = data.get("captcha_sitekey") or data.get("sitekey") or (data.get("captcha_key") if data.get("captcha_service") else None)
                captcha_rqtoken = data.get("captcha_rqtoken")
                if not captcha_sitekey and data.get("captcha_service"):
                    captcha_sitekey = data.get("captcha_session_id") or data.get("captcha_key")
            if status in (400, 403) and (captcha_sitekey or 'captcha' in (body or '').lower()):
                print(f'[nitrosnipe] captcha on `{code}` sitekey={captcha_sitekey}')
                try:
                    await S.safe_send(message.channel, S.ui_warn(f'nitro captcha | solving `{code}`...'))
                except Exception:
                    pass
                sitekey = captcha_sitekey or 'f5561ba9-8f1e-40ca-9b5b-a0b3f719ef34'
                solved = await _solve_hcaptcha(sitekey, 'https://discord.com')
                if solved:
                    try:
                        status, body = await _redeem_nitro(token, code, message.channel.id, captcha_key=solved, captcha_rqtoken=captcha_rqtoken)
                    except Exception as e:
                        print(f'[nitrosnipe] redeem after captcha: {e}')
                        continue
                else:
                    try:
                        await S.safe_send(message.channel, S.ui_err(f'nitro captcha unsolved `{code}` - setcaptcha <provider> <key>  or CAPTCHA_API_KEY in .env'))
                    except Exception:
                        pass
                    continue
            try:
                if status in (200, 201):
                    await S.safe_send(message.channel, S.ui_ok(f'nitro sniped - `{code}`'))
                    print(f'[nitrosnipe] claimed {code}')
                elif status == 429:
                    await S.safe_send(message.channel, S.ui_warn(f'nitro rate limited - `{code}`'))
                elif status in (400, 404):
                    print(f'[nitrosnipe] {status} `{code}` {body[:80]}')
                else:
                    print(f'[nitrosnipe] {status} `{code}` {body[:120]}')
            except Exception:
                pass

    @commands.command(name='snipehistory', aliases=['sh'], brief='Show snipe history')
    async def snipehistory(self, ctx, limit: int=10):
        all_snipes = sorted(S._snipe_cache.values(), key=lambda x: x.get('time', 0), reverse=True)
        rows = [f"  {S.GREY}*{S.RESET} {s['author']}: {s['content'][:60]}" for s in all_snipes[:limit]]
        await S.safe_edit(ctx.message, S._paginate('snipe history', '', rows) if rows else S.ui_info('empty'))

    @commands.command(name='snipestats', brief='Sniper statistics')
    async def snipestats(self, ctx):
        await S.safe_edit(ctx.message, S.ui_box('sniper stats', [f'  {S.DIM}enabled{S.RESET}    {S.SNIPER_ENABLED}', f'  {S.DIM}nitro{S.RESET}      {S._nitrosniper_enabled}', f'  {S.DIM}giveaway{S.RESET}   {S._giveaway_enabled}', f'  {S.DIM}cached{S.RESET}     {len(S._snipe_cache)} channels']))

    @commands.command(name='snipeclearcache', brief='Clear snipe cache')
    async def snipeclearcache(self, ctx):
        S._snipe_cache.clear()
        S._editsnipe_cache.clear()
        await S.safe_edit(ctx.message, S.ui_ok('snipe cache cleared'))

    @commands.command(name='snipeignore', brief='Ignore a user from sniper')
    async def snipeignore(self, ctx, user: discord.User=None):
        if not user:
            return await S.safe_edit(ctx.message, S.ui_err('usage: snipeignore <@user>'))
        self._ignore_users.add(user.id)
        await S.safe_edit(ctx.message, S.ui_ok(f'snipeignore → {user}'))

    @commands.command(name='snipesearch', brief='Search snipe cache')
    async def snipesearch(self, ctx, *, query: str=''):
        if not query:
            return await S.safe_edit(ctx.message, S.ui_err('usage: snipesearch <query>'))
        results = [s for s in S._snipe_cache.values() if query.lower() in s.get("content", "").lower()]
        rows = [f"  {S.GREY}*{S.RESET} {s['author']}: {s['content'][:60]}" for s in results[:20]]
        await S.safe_edit(ctx.message, S._paginate(f'snipe search: {query}', '', rows) if rows else S.ui_info('no results'))

    @commands.command(name='giveaway', brief='Toggle giveaway sniper')
    async def giveaway(self, ctx, toggle: str=''):
        S._giveaway_enabled = toggle.lower() not in ('off', 'disable', 'false') if toggle else not S._giveaway_enabled
        await S.safe_edit(ctx.message, S.ui_ok(f"giveaway sniper → {('on' if S._giveaway_enabled else 'off')}"))

    @commands.command(name='esnipe', aliases=['editsnipe'], brief='Show last edited message')
    async def esnipe(self, ctx):
        entry = S._editsnipe_cache.get(ctx.channel.id)
        if not entry:
            return await S.safe_edit(ctx.message, S.ui_info('nothing to snipe'))
        await S.safe_edit(ctx.message, S.ui_box('edit snipe', [f'  {S.DIM}author{S.RESET}  {entry.get("author", "?")}', f'  {S.DIM}before{S.RESET}  {entry.get("before", "")[:100]}', f'  {S.DIM}after{S.RESET}   {entry.get("after", "")[:100]}']))

    @commands.command(name='editsnipehistory', brief='Show edit snipe history')
    async def editsnipehistory(self, ctx):
        entries = list(S._editsnipe_cache.values())[-20:]
        rows = [f'  {S.GREY}*{S.RESET} {e.get("author", "?")}: {e.get("before", "")[:50]} → {e.get("after", "")[:50]}' for e in entries]
        await S.safe_edit(ctx.message, S._paginate('edit snipe history', '', rows) if rows else S.ui_info('empty'))

    @commands.command(name='snipepage', brief='Page through snipe history  snipepage <n>')
    async def snipepage(self, ctx, page: int=1):
        all_snipes = sorted(S._snipe_cache.values(), key=lambda x: x.get('time', 0), reverse=True)
        per = 5
        start = (page - 1) * per
        end = start + per
        chunk = all_snipes[start:end]
        rows = [f'  {S.GREY}{i + start + 1}{S.RESET} {s.get("author", "?")}: {s.get("content", "")[:60]}' for i, s in enumerate(chunk)]
        await S.safe_edit(ctx.message, S._paginate(f'snipes p{page}', '', rows) if rows else S.ui_info('end'))

    @commands.command(name='snipetimestamp', brief='Show timestamp of last sniped message')
    async def snipetimestamp(self, ctx):
        import time as _t
        entry = S._snipe_cache.get(ctx.channel.id)
        if not entry:
            return await S.safe_edit(ctx.message, S.ui_info('nothing'))
        ts = entry.get('time', 0)
        await S.safe_edit(ctx.message, S.ui_ok(f"sniped at: {_t.strftime('%Y-%m-%d %H:%M:%S', _t.localtime(ts))}"))

    @commands.command(name='snipereactions', brief='Show reactions on last sniped message')
    async def snipereactions(self, ctx):
        entry = S._snipe_cache.get(ctx.channel.id)
        if not entry:
            return await S.safe_edit(ctx.message, S.ui_info('nothing'))
        reactions = entry.get('reactions', [])
        rows = [f'  {S.GREY}*{S.RESET} {r}' for r in reactions]
        await S.safe_edit(ctx.message, S._paginate('snipe reactions', '', rows) if rows else S.ui_info('no reactions'))

    @commands.command(name='snipeembeds', brief='Show embed count on last sniped message')
    async def snipeembeds(self, ctx):
        entry = S._snipe_cache.get(ctx.channel.id)
        if not entry:
            return await S.safe_edit(ctx.message, S.ui_info('nothing'))
        await S.safe_edit(ctx.message, S.ui_ok(f"embeds: {entry.get('embed_count', 0)}"))

    @commands.command(name='snipeattachments', brief='Show attachments on last sniped message')
    async def snipeattachments(self, ctx):
        entry = S._snipe_cache.get(ctx.channel.id)
        if not entry:
            return await S.safe_edit(ctx.message, S.ui_info('nothing'))
        atts = entry.get('attachments', [])
        rows = [f'  {S.GREY}*{S.RESET} {a}' for a in atts]
        await S.safe_edit(ctx.message, S._paginate('attachments', '', rows) if rows else S.ui_info('none'))

    @commands.command(name='snipefilter', brief='Filter snipe cache by keyword')
    async def snipefilter(self, ctx, *, query: str=''):
        if not query:
            return await S.safe_edit(ctx.message, S.ui_err('usage: snipefilter <query>'))
        results = [s for s in S._snipe_cache.values() if query.lower() in s.get("content", "").lower()]
        rows = [f'  {S.GREY}*{S.RESET} {s.get("author", "?")}: {s.get("content", "")[:60]}' for s in results]
        await S.safe_edit(ctx.message, S._paginate(f'filter: {query}', '', rows) if rows else S.ui_info('none'))

    @commands.command(name='snipeclearuser', brief='Clear snipes from a user')
    async def snipeclearuser(self, ctx, user: discord.User=None):
        if not user:
            return await S.safe_edit(ctx.message, S.ui_err('usage: snipeclearuser <@user>'))
        before = len(S._snipe_cache)
        S._snipe_cache = {k: v for k, v in S._snipe_cache.items() if v.get("author_id") != user.id}
        after = len(S._snipe_cache)
        await S.safe_edit(ctx.message, S.ui_ok(f'cleared {before - after} snipes from {user}'))

    @commands.command(name='snipeclearchannel', brief='Clear snipes in current channel')
    async def snipeclearchannel(self, ctx):
        S._snipe_cache.pop(ctx.channel.id, None)
        S._editsnipe_cache.pop(ctx.channel.id, None)
        await S.safe_edit(ctx.message, S.ui_ok('channel snipe cache cleared'))

    @commands.command(name='snipeclearserver', brief='Clear all snipes in server')
    @commands.guild_only()
    async def snipeclearserver(self, ctx):
        ch_ids = {c.id for c in ctx.guild.channels}
        before = len(S._snipe_cache)
        S._snipe_cache = {k: v for k, v in S._snipe_cache.items() if k not in ch_ids}
        await S.safe_edit(ctx.message, S.ui_ok(f'cleared {before - len(S._snipe_cache)} server snipes'))

async def setup(bot):
    await bot.add_cog(SniperCog(bot))
