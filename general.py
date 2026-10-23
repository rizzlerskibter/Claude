import asyncio, time, discord
from discord.ext import commands
from . import state as S
from .antid import delay, on_rate_limit, jitter

class GeneralCog(commands.Cog, name='general'):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='stats', brief='Account stats')
    async def stats(self, ctx):
        u = ctx.author
        rows = [f'  {S.DIM}tag{S.RESET}      {u}', f'  {S.DIM}id{S.RESET}       {u.id}', f'  {S.DIM}guilds{S.RESET}   {len(self.bot.guilds)}', f'  {S.DIM}latency{S.RESET}  {round(self.bot.latency * 1000)}ms']
        await S.safe_edit(ctx.message, S.ui_box('wilt stats', rows))

    @commands.command(name='clrmsgs', aliases=['clr'], brief='Delete your own messages')
    async def purge(self, ctx, amount: int=10):
        setattr(ctx, '_wilt_skip_delete', True)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        deleted = 0
        async for msg in ctx.channel.history(limit=200):
            if msg.author.id == self.bot.user.id and deleted < amount:
                try:
                    await msg.delete()
                    deleted += 1
                    await delay(0.3, 0.9)
                except Exception as e:
                    if '429' in str(e):
                        await on_rate_limit(5.0)
        conf = await S.safe_send(ctx.channel, S.ui_ok(f'deleted {deleted} message(s)'))
        await asyncio.sleep(3)
        try:
            await conf.delete()
        except Exception:
            pass

    @commands.command(name='snipe', brief='Show last deleted message')
    async def snipe(self, ctx):
        entry = S._snipe_cache.get(ctx.channel.id)
        if not entry:
            return await S.safe_edit(ctx.message, S.ui_info('nothing to snipe'))
        rows = [f'  {S.DIM}author{S.RESET}  {entry.get("author", "?")}', f'  {S.DIM}content{S.RESET} {entry.get("content", "")[:200]}']
        await S.safe_edit(ctx.message, S.ui_box('snipe', rows))

    @commands.command(name='hypesquad', brief='Set or leave HypeSquad house')
    async def hypesquad(self, ctx, house: str=''):
        import aiohttp
        house = (house or '').lower().strip()
        if house in ('leave', 'quit', 'none', 'off', 'remove', 'exit'):
            h = {'Authorization': S._get_token(), 'Content-Type': 'application/json', 'User-Agent': S.USER_AGENT}
            async with aiohttp.ClientSession() as s:
                async with s.delete('https://discord.com/api/v9/hypesquad/online', headers=h) as r:
                    if r.status in (200, 204):
                        await S.safe_edit(ctx.message, S.ui_ok('HypeSquad left'))
                    else:
                        body = await r.text()
                        await S.safe_edit(ctx.message, S.ui_err(f'leave failed ({r.status}) {body[:80]}'))
            return
        houses = {'bravery': 1, 'brilliance': 2, 'balance': 3, '1': 1, '2': 2, '3': 3}
        hid = houses.get(house)
        if not hid:
            return await S.safe_edit(ctx.message, S.ui_err('usage: hypesquad <bravery|brilliance|balance|leave>'))
        h = {'Authorization': S._get_token(), 'Content-Type': 'application/json', 'User-Agent': S.USER_AGENT}
        async with aiohttp.ClientSession() as s:
            async with s.post('https://discord.com/api/v9/hypesquad/online', headers=h, json={'house_id': hid}) as r:
                if r.status in (200, 204):
                    names = {1: 'Bravery', 2: 'Brilliance', 3: 'Balance'}
                    await S.safe_edit(ctx.message, S.ui_ok(f'HypeSquad → {names.get(hid, house)}'))
                else:
                    body = await r.text()
                    await S.safe_edit(ctx.message, S.ui_err(f'failed ({r.status}) {body[:80]}'))

    @commands.command(name='firstmessage', aliases=['fm'], brief='Jump to first message')
    async def firstmessage(self, ctx):
        async for msg in ctx.channel.history(limit=1, oldest_first=True):
            await S.safe_edit(ctx.message, msg.jump_url)

    @commands.command(name='say', brief='Send a message as yourself')
    async def say(self, ctx, *, text: str=''):
        await ctx.message.delete()
        if text:
            await S.safe_send(ctx.channel, text)

    @commands.command(name='copycat', brief='Repeat the last message in channel')
    async def copycat(self, ctx):
        async for msg in ctx.channel.history(limit=5):
            if msg.id != ctx.message.id and msg.content:
                await S.safe_edit(ctx.message, msg.content)
                return
        await S.safe_edit(ctx.message, S.ui_err('nothing to copy'))

    @commands.command(name='spam', brief='Spam message N times (main + hosted tokens)')
    async def spam(self, ctx, n: int=5, *, text: str=''):
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: spam <count> <text>'))
        try:
            n = int(n)
        except (TypeError, ValueError):
            return await S.safe_edit(ctx.message, S.ui_err('usage: spam <count> <text>'))
        n = max(1, min(n, 5000))
        channel_id = str(ctx.channel.id)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        import aiohttp
        import asyncio as _a
        tokens = []
        main = S._get_token(self.bot)
        if main:
            tokens.append(main)
        for t in list(getattr(S, 'HOSTED_TOKENS', []) or []):
            t = str(t).strip()
            if t and t not in tokens:
                tokens.append(t)
        if not tokens:
            return await S.safe_send(ctx.channel, S.ui_err('no token'))
        ua = getattr(S, 'USER_AGENT', 'Mozilla/5.0')
        sent = 0
        retries = 0
        url = f'https://discord.com/api/v9/channels/{channel_id}/messages'
        lock = _a.Lock()
        stop = False

        async def _send_one(session, token, content):
            nonlocal sent, retries, stop
            if stop:
                return False
            headers = {'Authorization': token, 'Content-Type': 'application/json', 'User-Agent': ua}
            while not stop:
                try:
                    async with session.post(url, headers=headers, json={'content': content}) as r:
                        if r.status in (200, 201):
                            async with lock:
                                if sent >= n:
                                    stop = True
                                    return False
                                sent += 1
                                if sent >= n:
                                    stop = True
                            return True
                        if r.status == 429:
                            try:
                                data = await r.json()
                                ra = float(data.get('retry_after', 0.35) or 0.35)
                            except Exception:
                                ra = 0.35
                            async with lock:
                                retries += 1
                            await _a.sleep(max(0.05, ra))
                            continue
                        # other errors — brief pause then retry same unit
                        async with lock:
                            retries += 1
                        await _a.sleep(0.15)
                        continue
                except Exception:
                    async with lock:
                        retries += 1
                    await _a.sleep(0.2)
                    continue
            return False

        connector = aiohttp.TCPConnector(limit=0, limit_per_host=0, force_close=False)
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=12, sock_read=20)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            while sent < n and not stop:
                need = n - sent
                wave = max(16, min(96, max(need, len(tokens) * 8)))
                batch_n = min(need, wave)
                tasks = []
                for i in range(batch_n):
                    token = tokens[(sent + i) % len(tokens)]
                    tasks.append(_send_one(session, token, text))
                await _a.gather(*tasks, return_exceptions=True)
                if sent < n and not stop:
                    await _a.sleep(0)
        conf = await ctx.channel.send(S.ui_ok(f'spam done | sent {sent}/{n} | tokens {len(tokens)} | retries {retries}'))
        await _a.sleep(2)
        try:
            await conf.delete()
        except Exception:
            pass

    @commands.command(name='spamstop', brief='Spam stop hint')
    async def spamstop(self, ctx):
        await S.safe_edit(ctx.message, S.ui_info('spam runs to completion — no mid-stop flag'))

    @commands.command(name='hostspam', aliases=['hspam'], brief='Spam only with hosted tokens')
    async def hostspam(self, ctx, n: int=5, *, text: str=''):
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: hostspam <count> <text>'))
        try:
            n = int(n)
        except (TypeError, ValueError):
            return await S.safe_edit(ctx.message, S.ui_err('usage: hostspam <count> <text>'))
        n = max(1, min(n, 5000))
        tokens = [str(t).strip() for t in getattr(S, 'HOSTED_TOKENS', []) or [] if str(t).strip()]
        if not tokens:
            return await S.safe_edit(ctx.message, S.ui_err('no hosted tokens - .hostadd <token>'))
        channel_id = str(ctx.channel.id)
        try:
            await ctx.message.delete()
        except Exception:
            pass
        import aiohttp
        import asyncio as _a
        ua = getattr(S, 'USER_AGENT', 'Mozilla/5.0')
        url = f'https://discord.com/api/v9/channels/{channel_id}/messages'
        sent = 0
        retries = 0
        lock = _a.Lock()
        stop = False

        async def _send_one(session, token, content):
            nonlocal sent, retries, stop
            if stop:
                return False
            headers = {'Authorization': token, 'Content-Type': 'application/json', 'User-Agent': ua}
            while not stop:
                try:
                    async with session.post(url, headers=headers, json={'content': content}) as r:
                        if r.status in (200, 201):
                            async with lock:
                                if sent >= n:
                                    stop = True
                                    return False
                                sent += 1
                                if sent >= n:
                                    stop = True
                            return True
                        if r.status == 429:
                            try:
                                data = await r.json()
                                ra = float(data.get('retry_after', 0.35) or 0.35)
                            except Exception:
                                ra = 0.35
                            async with lock:
                                retries += 1
                            await _a.sleep(max(0.05, ra))
                            continue
                        async with lock:
                            retries += 1
                        await _a.sleep(0.15)
                        continue
                except Exception:
                    async with lock:
                        retries += 1
                    await _a.sleep(0.2)
                    continue
            return False

        connector = aiohttp.TCPConnector(limit=0, limit_per_host=0, force_close=False)
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=12, sock_read=20)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            while sent < n and not stop:
                need = n - sent
                wave = max(16, min(96, max(need, len(tokens) * 8)))
                batch_n = min(need, wave)
                tasks = []
                for i in range(batch_n):
                    token = tokens[(sent + i) % len(tokens)]
                    tasks.append(_send_one(session, token, text))
                await _a.gather(*tasks, return_exceptions=True)
                if sent < n and not stop:
                    await _a.sleep(0)
        conf = await ctx.channel.send(S.ui_ok(f'hostspam done | sent {sent}/{n} | hosts {len(tokens)} | retries {retries}'))
        await _a.sleep(2)
        try:
            await conf.delete()
        except Exception:
            pass


    @commands.command(name='ping', brief='Latency')
    async def ping(self, ctx):
        ms = round(self.bot.latency * 1000)
        await S.safe_edit(ctx.message, S.ui_ok(f'pong · {ms}ms'))

    @commands.command(name='info', brief='Bot info')
    async def info(self, ctx):
        await S.safe_edit(ctx.message, S.ui_box('wilt', [f'  {S.DIM}version{S.RESET}  {S.VERSION}', f'  {S.DIM}lib{S.RESET}      discord.py-self', f'  {S.DIM}guilds{S.RESET}   {len(self.bot.guilds)}', f'  {S.DIM}latency{S.RESET}  {round(self.bot.latency * 1000)}ms']))

    @commands.command(name='banner', brief='Show user banner')
    async def banner(self, ctx, user: discord.User = None):
        u = user or ctx.author
        try:
            u = await self.bot.fetch_user(u.id)
        except Exception:
            pass
        b = getattr(u, 'banner', None)
        if b is None:
            return await S.safe_edit(ctx.message, S.ui_err('no banner'))
        await S.safe_edit(ctx.message, str(b.url))

    @commands.command(name='purgeall', brief='Delete ALL your messages in channel')
    async def purgeall(self, ctx):
        await ctx.message.delete()
        import asyncio as _a
        deleted = 0
        async for msg in ctx.channel.history(limit=1000):
            if msg.author.id == self.bot.user.id:
                try:
                    await msg.delete()
                    deleted += 1
                except Exception:
                    pass
                await _a.sleep(0.3)
        m = await S.safe_send(ctx.channel, S.ui_ok(f'deleted {deleted}'))
        await _a.sleep(3)
        try:
            await m.delete()
        except Exception:
            pass

    @commands.command(name='readlog', brief="Show the bot's log file tail")
    async def readlog(self, ctx, n: int=10):
        import os
        lf = getattr(S, 'LOG_FILE', 'wilt.log')
        if not os.path.exists(lf):
            return await S.safe_edit(ctx.message, S.ui_err('no log file'))
        with open(lf, 'r', errors='replace') as f:
            lines = f.readlines()
        tail = ''.join(lines[-n:])[-1900:]
        nl = chr(10)
        await S.safe_edit(ctx.message, f'```{nl}{tail}{nl}```')

    @commands.command(name='sniper', brief='Toggle nitro/giveaway sniper')
    async def sniper(self, ctx, sub: str='', toggle: str=''):
        if sub == 'nitro':
            S._nitrosniper_enabled = toggle.lower() not in ('off', 'disable') if toggle else not S._nitrosniper_enabled
            return await S.safe_edit(ctx.message, S.ui_ok(f"nitro sniper → {('on' if S._nitrosniper_enabled else 'off')}"))
        if sub == 'giveaway':
            S._giveaway_enabled = toggle.lower() not in ('off', 'disable') if toggle else not getattr(S, '_giveaway_enabled', False)
            return await S.safe_edit(ctx.message, S.ui_ok(f"giveaway sniper → {('on' if S._giveaway_enabled else 'off')}"))
        await S.safe_edit(ctx.message, S.ui_box('snipers', [f'  {S.DIM}nitro{S.RESET}    {S._nitrosniper_enabled}', f"  {S.DIM}giveaway{S.RESET} {getattr(S, '_giveaway_enabled', False)}"]))

    @commands.command(name='report', brief='Report user/message via Discord reporting API')
    async def report(self, ctx, user: discord.User=None, reason: str='spam'):
        if user is None and ctx.message.mentions:
            user = ctx.message.mentions[0]
        if user is None and ctx.message.reference is None:
            return await S.safe_edit(ctx.message, S.ui_err('usage: report <@user> [spam|harassment|scam]  OR reply to a message'))
        key = (reason or 'spam').lower()
        # message-report breadcrumbs (V3)
        msg_paths = {
            'spam': ('98', [7, 98]),
            'harassment': ('101', [7, 76, 101]),
            'hate': ('107', [7, 76, 107]),
            'scam': ('167', [7, 80, 121, 167]),
            'illegal': ('108', [7, 86, 108]),
            'other': ('97', [7, 97]),
        }
        variant, crumbs = msg_paths.get(key, msg_paths['spam'])
        token = S._get_token(self.bot)
        try:
            headers = S.api_headers()
        except Exception:
            headers = {'Authorization': token, 'Content-Type': 'application/json', 'User-Agent': getattr(S, 'USER_AGENT', 'Mozilla/5.0')}
        headers['Content-Type'] = 'application/json'
        import aiohttp
        tried = []
        ok = False
        # 1) if reply → report that message
        ref = ctx.message.reference
        msg_id = getattr(ref, 'message_id', None) if ref else None
        ch_id = ctx.channel.id
        if msg_id:
            payload = {
                'version': '1.0',
                'variant': str(variant),
                'language': 'en',
                'breadcrumbs': crumbs,
                'elements': {},
                'channel_id': str(ch_id),
                'message_id': str(msg_id),
                'name': 'message',
            }
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.post('https://discord.com/api/v9/reporting/message', headers=headers, json=payload) as r:
                        tried.append(f'message:{r.status}')
                        if r.status in (200, 201, 204):
                            ok = True
            except Exception as e:
                tried.append(f'message-err:{e}')
        # 2) user profile report
        if user is not None and not ok:
            user_payload = {
                'version': '1.0',
                'variant': '3',
                'language': 'en',
                'breadcrumbs': [1],
                'elements': {},
                'name': 'user',
                'user_id': str(user.id),
            }
            for url in (
                'https://discord.com/api/v9/reporting/user',
            ):
                try:
                    async with aiohttp.ClientSession() as s:
                        async with s.post(url, headers=headers, json=user_payload if 'reporting' in url else {'reason': 1, 'version': '1.0'}) as r:
                            tried.append(f'{url.split("/")[-1]}:{r.status}')
                            if r.status in (200, 201, 204):
                                ok = True
                                break
                            if r.status == 429:
                                return await S.safe_edit(ctx.message, S.ui_err('rate limited'))
                except Exception as e:
                    tried.append(str(e)[:40])
        if ok:
            who = user or f'msg:{msg_id}'
            await S.safe_edit(ctx.message, S.ui_ok(f'reported {who} ({key})'))
        else:
            await S.safe_edit(ctx.message, S.ui_err(f'report failed ({", ".join(tried)[:80]})'))

    @commands.command(name='serverjoin', aliases=['sjoin', 'joinguild', 'acceptinvite'], brief='Join server via invite/vanity')
    async def serverjoin(self, ctx, invite: str=''):
        import aiohttp, re as _re
        from uuid import uuid4
        if not invite:
            return await S.safe_edit(ctx.message, S.ui_err('usage: serverjoin <invite|vanity|discord.gg/...>'))
        code = invite.strip()
        for p in (
            'https://discord.gg/', 'http://discord.gg/', 'discord.gg/',
            'https://discord.com/invite/', 'http://discord.com/invite/',
            'https://discordapp.com/invite/', 'discord.com/invite/',
        ):
            if code.lower().startswith(p):
                code = code[len(p):]
                break
        code = code.split('?')[0].split('/')[0].strip()
        if not code or not _re.match(r'^[A-Za-z0-9-]+$', code):
            return await S.safe_edit(ctx.message, S.ui_err('invalid invite code'))
        token = S._get_token()
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json',
            'User-Agent': S.USER_AGENT,
            'X-Discord-Locale': 'en-US',
            'X-Debug-Options': 'bugReporterEnabled',
            'Origin': 'https://discord.com',
            'Referer': 'https://discord.com/channels/@me',
        }
        try:
            from utils.gateway import default_headers
            headers = default_headers(token)
            headers['Authorization'] = token
        except Exception:
            if getattr(S, 'X_SUPER_PROPERTIES', ''):
                headers['X-Super-Properties'] = S.X_SUPER_PROPERTIES

        body = {'session_id': uuid4().hex[:32]}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f'https://discord.com/api/v9/invites/{code}?with_counts=true&with_expiration=true',
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as r:
                    inv = await r.json(content_type=None)
                    if r.status == 404 or inv.get('code') in (10006, 10007):
                        return await S.safe_edit(ctx.message, S.ui_err('invite invalid or expired'))
                    if r.status != 200:
                        return await S.safe_edit(ctx.message, S.ui_err(f'invite lookup {r.status}'))
                gname = (inv.get('guild') or {}).get('name', '?')
                gid = (inv.get('guild') or {}).get('id', '?')
                await S.safe_edit(ctx.message, S.ui_info(f'joining {gname}…'))
                async with s.post(
                    f'https://discord.com/api/v9/invites/{code}',
                    headers=headers,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r2:
                    data = await r2.json(content_type=None)
                    status = r2.status
                if status in (200, 201, 204):
                    return await S.safe_edit(ctx.message, S.ui_ok(f'joined {gname} (`{gid}`)'))
                if status == 400 and isinstance(data, dict) and data.get('captcha_key'):
                    sitekey = data.get('captcha_sitekey') or ''
                    rqtoken = data.get('captcha_rqtoken') or ''
                    session_id = data.get('captcha_session_id') or ''
                    rqdata = data.get('captcha_rqdata') or ''
                    await S.safe_edit(ctx.message, S.ui_info('captcha required — solving…'))
                    try:
                        from .sniper import _solve_hcaptcha
                        page = f'https://discord.com/invite/{code}'
                        solved = await _solve_hcaptcha(
                            sitekey,
                            page,
                            rqdata=rqdata or '',
                            enterprise=True,
                            user_agent=headers.get('User-Agent') or S.USER_AGENT,
                        )
                    except Exception as e:
                        solved = None
                        print(f'[serverjoin] captcha import/solve: {e}')
                    if not solved:
                        return await S.safe_edit(
                            ctx.message,
                            S.ui_err('captcha unsolved — .setcaptcha nonecap <nc_live_…> then retry'),
                        )
                    headers2 = dict(headers)
                    try:
                        from utils.gateway import default_headers
                        headers2.update(default_headers(token))
                        headers2['Authorization'] = token
                    except Exception:
                        pass
                    headers2['X-Captcha-Key'] = solved
                    if rqtoken:
                        headers2['X-Captcha-Rqtoken'] = rqtoken
                    if session_id:
                        headers2['X-Captcha-Session-Id'] = session_id
                    body2 = dict(body)
                    async with s.post(
                        f'https://discord.com/api/v9/invites/{code}',
                        headers=headers2,
                        json=body2,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as r3:
                        data3 = await r3.json(content_type=None)
                        if r3.status in (200, 201, 204):
                            return await S.safe_edit(ctx.message, S.ui_ok(f'joined {gname} (captcha ok)'))
                        # one soft retry with fresh solve if invalid-response
                        err_s = str(data3)
                        if r3.status == 400 and 'invalid-response' in err_s:
                            await S.safe_edit(ctx.message, S.ui_info('captcha rejected — solving again…'))
                            sitekey2 = (data3.get('captcha_sitekey') if isinstance(data3, dict) else None) or sitekey
                            rqtoken2 = (data3.get('captcha_rqtoken') if isinstance(data3, dict) else None) or rqtoken
                            session2 = (data3.get('captcha_session_id') if isinstance(data3, dict) else None) or session_id
                            rqdata2 = (data3.get('captcha_rqdata') if isinstance(data3, dict) else None) or rqdata
                            solved2 = await _solve_hcaptcha(
                                sitekey2, page, rqdata=rqdata2 or '', enterprise=True,
                                user_agent=headers2.get('User-Agent') or S.USER_AGENT,
                            )
                            if solved2:
                                headers2['X-Captcha-Key'] = solved2
                                if rqtoken2:
                                    headers2['X-Captcha-Rqtoken'] = rqtoken2
                                if session2:
                                    headers2['X-Captcha-Session-Id'] = session2
                                async with s.post(
                                    f'https://discord.com/api/v9/invites/{code}',
                                    headers=headers2,
                                    json=body2,
                                    timeout=aiohttp.ClientTimeout(total=30),
                                ) as r4:
                                    data4 = await r4.json(content_type=None)
                                    if r4.status in (200, 201, 204):
                                        return await S.safe_edit(ctx.message, S.ui_ok(f'joined {gname} (captcha ok)'))
                                    return await S.safe_edit(ctx.message, S.ui_err(f'join after captcha failed {r4.status}: {str(data4)[:140]}'))
                        return await S.safe_edit(ctx.message, S.ui_err(f'join after captcha failed {r3.status}: {str(data3)[:140]}'))
                if status == 429:
                    return await S.safe_edit(ctx.message, S.ui_err('rate limited — wait and retry'))
                msg = ''
                if isinstance(data, dict):
                    msg = data.get('message') or str(data.get('code', '')) or str(data)[:100]
                return await S.safe_edit(ctx.message, S.ui_err(f'join failed {status}: {msg}'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(f'serverjoin: {e}'))

    @commands.command(name='bypass', aliases=['byp', 'linkbypass', 'keybypass'], brief='Bypass ad/key system URLs')
    async def bypass(self, ctx, *, url: str=''):
        import aiohttp, re as _re, urllib.parse
        if not url:
            return await S.safe_edit(
                ctx.message,
                S.ui_box('bypass', [
                    '  .bypass <url>',
                    '  supports: linkvertise, work.ink, lootlabs,',
                    '            boost.ink, rekonise, sub2unlock,',
                    '            adfoc, mboost, bit.ly, pastes,',
                    '            + multi-API + redirect resolve',
                ]),
            )
        url = url.strip().strip('<>')
        if not url.startswith('http'):
            url = 'https://' + url
        await S.safe_edit(ctx.message, S.ui_info('resolving…'))
        results = []
        tried = []

        async def try_bypass_vip(session, u):
            try:
                async with session.get(
                    'https://api.bypass.vip/bypass',
                    params={'url': u},
                    timeout=aiohttp.ClientTimeout(total=25),
                ) as r:
                    data = await r.json(content_type=None)
                if isinstance(data, dict) and data.get('status') == 'success' and data.get('result'):
                    return data['result']
                if isinstance(data, dict) and data.get('result'):
                    return data['result']
            except Exception as e:
                tried.append(f'vip:{type(e).__name__}')
            return None

        async def try_redirect_chain(session, u, max_hops=12):
            cur = u
            seen = set()
            for _ in range(max_hops):
                if cur in seen:
                    break
                seen.add(cur)
                try:
                    async with session.get(
                        cur,
                        allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=15),
                        headers={'User-Agent': S.USER_AGENT},
                    ) as r:
                        if r.status in (301, 302, 303, 307, 308):
                            loc = r.headers.get('Location') or r.headers.get('location')
                            if not loc:
                                break
                            cur = urllib.parse.urljoin(cur, loc)
                            continue
                        text = await r.text()
                        for pat in (
                            r'(?:destination|target|url|redirect|href)\s*[:=]\s*["\'](https?://[^"\']+)',
                            r'window\.location(?:\.href)?\s*=\s*["\'](https?://[^"\']+)',
                            r'<meta[^>]+url=(https?://[^"\'>\s]+)',
                        ):
                            m = _re.search(pat, text, _re.I)
                            if m:
                                nxt = m.group(1)
                                if 'linkvertise' not in nxt and 'work.ink' not in nxt and 'loot' not in nxt.lower():
                                    return nxt
                                cur = nxt
                                break
                        else:
                            return cur if r.status == 200 else None
                except Exception as e:
                    tried.append(f'redir:{type(e).__name__}')
                    break
            return cur if cur != u else None

        def linkvertise_lol(u):
            try:
                p = urllib.parse.urlparse(u)
                host = (p.netloc or '').lower()
                if 'linkvertise' in host or 'link-to' in host:
                    new_host = host.replace('linkvertise.com', 'linkvertise.lol').replace('link-to.net', 'linkvertise.lol')
                    if new_host != host:
                        return urllib.parse.urlunparse((p.scheme or 'https', new_host, p.path, p.params, p.query, p.fragment))
            except Exception:
                pass
            return None

        def is_ad_host(u):
            h = (urllib.parse.urlparse(u).netloc or '').lower()
            keys = (
                'linkvertise', 'work.ink', 'workink', 'lootlabs', 'loot-link', 'lootlinks',
                'boost.ink', 'mboost', 'bst.gg', 'booo.st', 'rekonise', 'sub2unlock',
                'sub4unlock', 'social-unlock', 'socialwolvez', 'adfoc', 'admaven',
                'cuty.io', 'cety.io', 'lockr', 'paster.so', 'paster.gg',
            )
            return any(k in h for k in keys)

        try:
            async with aiohttp.ClientSession() as s:
                out = await try_bypass_vip(s, url)
                if out:
                    results.append(('bypass.vip', out))
                lol = linkvertise_lol(url)
                if lol:
                    out2 = await try_bypass_vip(s, lol)
                    if out2:
                        results.append(('linkvertise.lol', out2))
                    else:
                        chain = await try_redirect_chain(s, lol)
                        if chain and chain != lol:
                            results.append(('linkvertise.lol-chain', chain))
                if not results:
                    chain = await try_redirect_chain(s, url)
                    if chain and chain != url and not is_ad_host(chain):
                        results.append(('redirect', chain))
                    elif chain and chain != url:
                        out3 = await try_bypass_vip(s, chain)
                        if out3:
                            results.append(('vip-after-redir', out3))
                if not results:
                    try:
                        async with s.get(
                            'https://bypass.vip/api/bypass',
                            params={'url': url},
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as r:
                            data = await r.json(content_type=None)
                        if isinstance(data, dict) and (data.get('result') or data.get('destination')):
                            results.append(('bypass.vip-alt', data.get('result') or data.get('destination')))
                    except Exception as e:
                        tried.append(f'vip2:{type(e).__name__}')
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err(f'bypass: {e}'))

        if not results:
            hint = ', '.join(tried[:4]) if tried else 'unsupported or dead link'
            return await S.safe_edit(ctx.message, S.ui_err(f'could not bypass ({hint})'))
        best = results[0][1]
        rows = [f'  {S.DIM}src{S.RESET}   {url[:80]}', f'  {S.DIM}out{S.RESET}   {best}']
        if len(results) > 1:
            rows.append(f'  {S.DIM}alts{S.RESET}  {len(results) - 1} more')
        await S.safe_edit(ctx.message, S.ui_box('bypass', rows))

async def setup(bot):
    await bot.add_cog(GeneralCog(bot))
