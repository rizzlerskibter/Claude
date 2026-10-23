import base64
import aiohttp
import discord
from discord.ext import commands
from . import state as S

def _h(json=True):
    import base64 as _b64
    props = _b64.b64encode(b'{"os":"Windows","browser":"Chrome","device":"","system_locale":"en-US","browser_user_agent":"' + S.USER_AGENT.encode()[:80] + b'","browser_version":"132.0.0.0","os_version":"10","referrer":"","referring_domain":"","referrer_current":"","referring_domain_current":"","release_channel":"stable","client_build_number":360032,"client_event_source":null}').decode()
    h = {'Authorization': S._get_token(), 'User-Agent': S.USER_AGENT, 'X-Super-Properties': props, 'X-Discord-Locale': 'en-US', 'X-Discord-Timezone': 'America/New_York', 'Origin': 'https://discord.com', 'Referer': 'https://discord.com/channels/@me'}
    if json:
        h['Content-Type'] = 'application/json'
    return h

async def _fetch_image_b64(url: str):
    headers = {'User-Agent': S.USER_AGENT, 'Accept': 'image/*,*/*;q=0.8'}
    if 'discord' in url:
        headers['Authorization'] = S.TOKEN
        headers['Referer'] = 'https://discord.com/'
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers) as r:
                if r.status != 200:
                    return (None, f'fetch failed ({r.status})')
                data = await r.read()
                if not data:
                    return (None, 'empty image')
                if len(data) > 10 * 1024 * 1024:
                    return (None, 'image too large (max 10MB)')
                ct = (r.headers.get("content-type") or 'image/png').split(';')[0].strip()
                if ct not in ('image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'):
                    if data[:3] == b'\xff\xd8\xff':
                        ct = 'image/jpeg'
                    elif data[:8] == b'\x89PNG\r\n\x1a\n':
                        ct = 'image/png'
                    elif data[:6] in (b'GIF87a', b'GIF89a'):
                        ct = 'image/gif'
                    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
                        ct = 'image/webp'
                    else:
                        ct = 'image/png'
                b64 = f'data:{ct};base64,' + base64.b64encode(data).decode()
                return (b64, None)
    except Exception as e:
        return (None, str(e))

async def _patch_me(payload: dict):
    import asyncio as _aio
    try:
        async with aiohttp.ClientSession() as s:
            for attempt in range(3):
                async with s.patch('https://discord.com/api/v9/users/@me', headers=_h(), json=payload) as r:
                    text = await r.text()
                    if r.status == 429:
                        try:
                            wait = float((await r.json()).get('retry_after', 2))
                        except Exception:
                            wait = 2.0 + attempt
                        await _aio.sleep(min(wait, 15))
                        continue
                    return (r.status in (200, 201, 204), r.status, text)
            return (False, 429, 'rate limited')
    except Exception as e:
        return (False, 0, str(e))

class ProfileCog(commands.Cog, name='profile'):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setbanner', brief='Set profile banner by URL or attachment')
    async def setbanner(self, ctx, url: str=''):
        if not url and ctx.message.attachments:
            att = ctx.message.attachments[0]
            url = getattr(att, 'url', None) or ''
        if not url:
            return await S.safe_edit(ctx.message, S.ui_err('usage: setbanner <image_url>  (or attach an image)'))
        b64, err = await _fetch_image_b64(url)
        if err:
            return await S.safe_edit(ctx.message, S.ui_err(err))
        ok, status, body = await _patch_me({'banner': b64})
        if ok:
            await S.safe_edit(ctx.message, S.ui_ok('banner updated'))
        else:
            msg = body[:160] if body else ''
            if status == 403:
                msg = '403 - banner requires Nitro or change is on cooldown'
            await S.safe_edit(ctx.message, S.ui_err(f'failed ({status}) {msg}'))

    @commands.command(name='setavatar', aliases=['setpfp'], brief='Set avatar by URL or attachment')
    async def setavatar(self, ctx, url: str=''):
        if not url and ctx.message.attachments:
            att = ctx.message.attachments[0]
            url = getattr(att, 'url', None) or ''
        if not url:
            return await S.safe_edit(ctx.message, S.ui_err('usage: setavatar <image_url>  (or attach an image)'))
        b64, err = await _fetch_image_b64(url)
        if err:
            return await S.safe_edit(ctx.message, S.ui_err(err))
        ok, status, body = await _patch_me({'avatar': b64})
        if ok:
            return await S.safe_edit(ctx.message, S.ui_ok('avatar updated'))
        try:
            raw = base64.b64decode(b64.split(',', 1)[1])
            await self.bot.user.edit(avatar=raw)
            return await S.safe_edit(ctx.message, S.ui_ok('avatar updated'))
        except Exception as e:
            msg = (body or str(e))[:160]
            if status == 403:
                msg = '403 - avatar change blocked (cooldown, captcha, or image rejected)'
            await S.safe_edit(ctx.message, S.ui_err(f'failed ({status}) {msg}'))

    @commands.command(name='clearavatar', brief='Reset avatar to default')
    async def clearavatar(self, ctx):
        ok, status, body = await _patch_me({'avatar': None})
        if ok:
            await S.safe_edit(ctx.message, S.ui_ok('avatar cleared'))
        else:
            await S.safe_edit(ctx.message, S.ui_err(f'failed ({status}) {body[:120]}'))

    @commands.command(name='clearbanner', brief='Reset banner')
    async def clearbanner(self, ctx):
        ok, status, body = await _patch_me({'banner': None})
        if ok:
            await S.safe_edit(ctx.message, S.ui_ok('banner cleared'))
        else:
            await S.safe_edit(ctx.message, S.ui_err(f'failed ({status}) {body[:120]}'))

    @commands.command(name='setusername', brief='Change username')
    async def setusername(self, ctx, *, name: str=''):
        if not name:
            return await S.safe_edit(ctx.message, S.ui_err('usage: setusername <name>'))
        ok, status, body = await _patch_me({'username': name})
        if ok:
            await S.safe_edit(ctx.message, S.ui_ok(f'username → {name}'))
            return
        try:
            await self.bot.user.edit(username=name)
            await S.safe_edit(ctx.message, S.ui_ok(f'username → {name}'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(f'failed ({status}) {body[:120] or e}'))

    @commands.command(name='accountbackup', brief='Backup account info to file')
    async def accountbackup(self, ctx):
        import json, os
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get('https://discord.com/api/v9/users/@me', headers=_h(False)) as r:
                    data = await r.json() if r.status == 200 else {}
            os.makedirs('exports', exist_ok=True)
            path = f'exports/account_{data.get("id", "unknown")}.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            await S.safe_edit(ctx.message, S.ui_ok(f'backup saved → {path}'))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)))

    @commands.command(name='myprofile', brief='Show your own profile')
    async def myprofile(self, ctx):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get('https://discord.com/api/v9/users/@me', headers=_h(False)) as r:
                    u = await r.json() if r.status == 200 else {}
            await S.safe_edit(ctx.message, S.ui_box('my profile', [f'  {S.DIM}username{S.RESET}  {u.get("username", "?")}', f'  {S.DIM}id{S.RESET}        {u.get("id", "?")}', f'  {S.DIM}nitro{S.RESET}     {bool(u.get("premium_type"))}', f'  {S.DIM}email{S.RESET}     {u.get("email", "hidden")}', f'  {S.DIM}phone{S.RESET}     {bool(u.get("phone"))}', f'  {S.DIM}mfa{S.RESET}       {bool(u.get("mfa_enabled"))}']))
        except Exception as e:
            await S.safe_edit(ctx.message, S.ui_err(str(e)))

async def setup(bot):
    await bot.add_cog(ProfileCog(bot))
