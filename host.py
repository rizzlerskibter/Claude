import asyncio
import json
import os
from pathlib import Path
import discord
from discord.ext import commands
from . import state as S
_HOST_FILE = Path('hosted_tokens.json')

def _load_tokens() -> list:
    try:
        if _HOST_FILE.exists():
            data = json.loads(_HOST_FILE.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return [str(t).strip() for t in data if str(t).strip()]
    except Exception as e:
        print(f'[host] load failed: {e}')
    return []

def _save_tokens(tokens: list) -> None:
    try:
        _HOST_FILE.write_text(json.dumps(list(tokens), indent=2), encoding='utf-8')
    except Exception as e:
        print(f'[host] save failed: {e}')

def _mask(token: str) -> str:
    t = token or ''
    if len(t) < 16:
        return '***'
    return f'{t[:12]}...{t[-6:]}'

def _ensure_list():
    if not hasattr(S, 'HOSTED_TOKENS') or S.HOSTED_TOKENS is None:
        S.HOSTED_TOKENS = []
    if not isinstance(S.HOSTED_TOKENS, list):
        S.HOSTED_TOKENS = list(S.HOSTED_TOKENS)

class HostCog(commands.Cog, name='host'):

    def __init__(self, bot):
        self.bot = bot
        _ensure_list()
        try:
            cfg = S.load_config() if hasattr(S, 'load_config') else {}
            S.HOST_PUBLIC = bool(cfg.get('host_public', False))
        except Exception:
            S.HOST_PUBLIC = False
        if not S.HOSTED_TOKENS:
            loaded = _load_tokens()
            if loaded:
                S.HOSTED_TOKENS.extend(loaded)
                print(f'[host] loaded {len(loaded)} token(s) from {_HOST_FILE}')

    def _sync(self):
        _ensure_list()
        seen = set()
        clean = []
        for t in S.HOSTED_TOKENS:
            t = str(t).strip()
            if t and t not in seen:
                seen.add(t)
                clean.append(t)
        S.HOSTED_TOKENS[:] = clean
        _save_tokens(S.HOSTED_TOKENS)

    @commands.command(name='hostadd', aliases=['htadd'], brief='Add hosted token(s)')
    async def hostadd(self, ctx, *, tokens: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        added = []
        raw = (tokens or '').strip()
        if not raw:
            return await S.safe_send(ctx.channel, S.ui_err('usage: hostadd <token|file:path>'))
        if raw.lower().startswith('file:'):
            path = raw[5:].strip().strip('"\'')
            if not os.path.exists(path):
                return await S.safe_send(ctx.channel, S.ui_err('file not found'))
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and (not line.startswith('#')):
                        added.append(line)
        else:
            for part in raw.replace(',', ' ').replace('\n', ' ').split():
                part = part.strip().strip('"\'')
                if part:
                    added.append(part)
        if not added:
            return await S.safe_send(ctx.channel, S.ui_err('no tokens found'))
        _ensure_list()
        before = len(S.HOSTED_TOKENS)
        for t in added:
            if t not in S.HOSTED_TOKENS:
                S.HOSTED_TOKENS.append(t)
        self._sync()
        return await S.safe_send(ctx.channel, S.ui_ok(f'added {len(S.HOSTED_TOKENS) - before} | total {len(S.HOSTED_TOKENS)}'))

    @commands.command(name='hostlist', aliases=['htlist'], brief='List hosted tokens')
    async def hostlist(self, ctx):
        _ensure_list()
        if not S.HOSTED_TOKENS:
            return await S.safe_edit(ctx.message, S.ui_info('no hosted tokens'))
        rows = [f'  {S.GREY}{i}{S.RESET}  {_mask(t)}' for i, t in enumerate(S.HOSTED_TOKENS)]
        return await S.safe_edit(ctx.message, S._paginate('hosted tokens', f'{len(rows)} saved', rows))

    @commands.command(name='hostremove', aliases=['htrm', 'hostdel'], brief='Remove hosted token by index')
    async def hostremove(self, ctx, index: str=''):
        _ensure_list()
        try:
            i = int(index)
        except Exception:
            return await S.safe_edit(ctx.message, S.ui_err('usage: hostremove <index>'))
        if i < 0 or i >= len(S.HOSTED_TOKENS):
            return await S.safe_edit(ctx.message, S.ui_err('index out of range'))
        S.HOSTED_TOKENS.pop(i)
        self._sync()
        return await S.safe_edit(ctx.message, S.ui_ok(f'removed #{i} | total {len(S.HOSTED_TOKENS)}'))

    @commands.command(name='hostclear', aliases=['htclear'], brief='Clear all hosted tokens')
    async def hostclear(self, ctx):
        _ensure_list()
        S.HOSTED_TOKENS.clear()
        self._sync()
        return await S.safe_edit(ctx.message, S.ui_ok('hosted tokens cleared'))

    @commands.command(name='host', aliases=['ht'], brief='Status, or host <token> in DM to join')
    async def host(self, ctx, *, maybe_token: str=''):
        tok = (maybe_token or '').strip().strip('`')
        if tok and len(tok) > 50 and ('.' in tok or len(tok) > 60):
            return await self.hostme(ctx, token=tok)
        _ensure_list()
        pub = bool(getattr(S, 'HOST_PUBLIC', False))
        return await S.safe_edit(ctx.message, S.ui_box('host', [f'  {S.DIM}tokens{S.RESET}   {len(S.HOSTED_TOKENS)}', f'  {S.DIM}public{S.RESET}  {pub}', f'  {S.DIM}file{S.RESET}     {_HOST_FILE}', f"  {S.DIM}prefix{S.RESET}   {getattr(S, 'PREFIX', '.')}", f'  {S.DIM}cmds{S.RESET}    hostme | hostadd | hoststart | hoststop | hostpublic', f'  {S.DIM}users{S.RESET}   DM: .host <token>  or  .hostme <token>']))

    @commands.command(name='hostcheck', aliases=['htcheck'], brief='Validate hosted tokens (lightweight)')
    async def hostcheck(self, ctx):
        _ensure_list()
        if not S.HOSTED_TOKENS:
            return await S.safe_edit(ctx.message, S.ui_info('no tokens'))
        import aiohttp
        await S.safe_edit(ctx.message, S.ui_info(f'checking {len(S.HOSTED_TOKENS)}...'))
        ok = bad = 0
        async with aiohttp.ClientSession() as s:
            for t in list(S.HOSTED_TOKENS):
                try:
                    async with s.get('https://discord.com/api/v9/users/@me', headers={'Authorization': t, 'User-Agent': 'Mozilla/5.0'}, timeout=aiohttp.ClientTimeout(total=10)) as r:
                        if r.status == 200:
                            ok += 1
                        else:
                            bad += 1
                except Exception:
                    bad += 1
                await asyncio.sleep(0.35)
        return await S.safe_edit(ctx.message, S.ui_ok(f'valid {ok} | invalid/fail {bad}'))

    @commands.command(name='admin', brief='Show admin status')
    async def admin(self, ctx):
        is_admin = ctx.author.id in getattr(S, '_admins', set()) or ctx.author.id == getattr(S, 'OWNER_ID', 0)
        await S.safe_edit(ctx.message, S.ui_ok(f'admin: {is_admin}'))

    @commands.command(name='dmhost', aliases=['hostdm'], brief='Info: users can DM token if public host enabled')
    async def dmhost(self, ctx):
        pub = bool(getattr(S, 'HOST_PUBLIC', False))
        await S.safe_edit(ctx.message, S.ui_box('dm host', [f'  public submissions: {pub}', f"  users DM you: {getattr(S, 'PREFIX', '.')}hostadd <token>", f'  or plain DM: host <token> (when public on)', f'  note: this only stores tokens for YOUR mass/host tools', f'  it does NOT give them a free running selfbot instance']))

    @commands.command(name='hostpublic', brief='hostpublic on/off - allow others to submit tokens in DMs')
    async def hostpublic(self, ctx, mode: str=''):
        m = (mode or '').lower()
        if m in ('on', '1', 'true', 'yes'):
            S.HOST_PUBLIC = True
            msg = 'public token submit ON (DMs)'
        elif m in ('off', '0', 'false', 'no'):
            S.HOST_PUBLIC = False
            msg = 'public token submit OFF'
        else:
            msg = f"public={bool(getattr(S, 'HOST_PUBLIC', False))} | usage: hostpublic on|off"
        try:
            cfg = S.load_config() if hasattr(S, 'load_config') else {}
            cfg['host_public'] = bool(getattr(S, 'HOST_PUBLIC', False))
            if hasattr(S, 'save_config'):
                S.save_config(cfg)
        except Exception:
            pass
        await S.safe_edit(ctx.message, S.ui_ok(msg))

    @commands.Cog.listener()
    async def on_message(self, message):
        if not getattr(S, 'HOST_PUBLIC', False):
            return
        if message.guild is not None:
            return
        if message.author.bot:
            return
        if message.author.id == getattr(self.bot.user, 'id', None):
            return
        content = (message.content or '').strip()
        if not content:
            return
        token = None
        low = content.lower()
        for pref in ('hostadd ', 'host ', 'htadd ', 'hostme ', 'token '):
            if low.startswith(pref):
                token = content[len(pref):].strip().strip('`').strip('"').strip("'")
                break
        if token is None:
            parts = content.split('.')
            if len(parts) >= 3 and len(content) > 50 and (' ' not in content.strip()):
                token = content.strip().strip('`')
        if not token or len(token) < 50:
            return
        try:
            if token == getattr(getattr(self.bot, 'http', None), 'token', None):
                await message.channel.send(S.ui_err('that is the host token - send your own'))
                return
        except Exception:
            pass
        _ensure_list()
        if token not in S.HOSTED_TOKENS:
            S.HOSTED_TOKENS.append(token)
            self._sync()
            note = 'token stored'
        else:
            note = 'already stored'
        try:
            await message.channel.send(S.ui_ok(f'{note} | starting...'))
            from utils import host_runner
            msg = await host_runner.start_token(token, prefix=getattr(S, 'PREFIX', '.'))
            await message.channel.send(S.ui_ok(msg))
        except Exception as e:
            await message.channel.send(S.ui_err(str(e)[:150]))

    @commands.command(name='hoststart', aliases=['htstart', 'hostlive'], brief='Start live clients for hosted tokens')
    async def hoststart(self, ctx, index: str='all'):
        from utils import host_runner
        _ensure_list()
        if not S.HOSTED_TOKENS:
            return await S.safe_edit(ctx.message, S.ui_err('no hosted tokens - hostadd first'))
        await S.safe_edit(ctx.message, S.ui_info('starting live clients...'))
        prefix = getattr(S, 'PREFIX', '.')
        started = []
        if index.lower() in ('all', '*'):
            targets = list(S.HOSTED_TOKENS)
        else:
            try:
                i = int(index)
                targets = [S.HOSTED_TOKENS[i]]
            except Exception:
                return await S.safe_edit(ctx.message, S.ui_err('usage: hoststart all | hoststart <index>'))
        for tok in targets:
            msg = await host_runner.start_token(tok, prefix=prefix)
            started.append(msg)
            await asyncio.sleep(2.0)
        return await S.safe_edit(ctx.message, S.ui_ok(' | '.join(started)[:1800]))

    @commands.command(name='hoststop', aliases=['htstop'], brief='Stop live hosted clients')
    async def hoststop(self, ctx, index: str='all'):
        from utils import host_runner
        _ensure_list()
        if index.lower() in ('all', '*'):
            msg = await host_runner.stop_all()
        else:
            try:
                i = int(index)
                tok = S.HOSTED_TOKENS[i]
            except Exception:
                return await S.safe_edit(ctx.message, S.ui_err('usage: hoststop all | hoststop <index>'))
            msg = await host_runner.stop_token(tok)
        return await S.safe_edit(ctx.message, S.ui_ok(msg))

    @commands.command(name='hostrun', aliases=['htlive', 'hoststatus'], brief='List live hosted clients')
    async def hostrun(self, ctx):
        from utils import host_runner
        rows = host_runner.status()
        if not rows:
            return await S.safe_edit(ctx.message, S.ui_info('no live hosted clients'))
        return await S.safe_edit(ctx.message, S.ui_box('live hosts', [f'  {r}' for r in rows]))

    @commands.command(name='hostme', aliases=['hhost'], brief='DM: submit your token to run on this host')
    async def hostme(self, ctx, *, token: str=''):
        token = (token or '').strip().strip('`').strip('"').strip("'")
        if not token or len(token) < 50:
            return await S.safe_send(ctx.channel, S.ui_err('usage: hostme <token>  (DM only)'))
        if ctx.guild is not None:
            return await S.safe_send(ctx.channel, S.ui_err('DM only - open a DM with the host account'))
        if not getattr(S, 'HOST_PUBLIC', False) and ctx.author.id != getattr(self.bot.user, 'id', None):
            owner = getattr(S, 'OWNER_ID', 0)
            if ctx.author.id != owner and ctx.author.id != getattr(self.bot.user, 'id', 0):
                return await S.safe_send(ctx.channel, S.ui_err('public host is off - host owner must .hostpublic on'))
        try:
            if token == getattr(getattr(self.bot, 'http', None), 'token', None):
                return await S.safe_send(ctx.channel, S.ui_err('that is the host token - use your own'))
        except Exception:
            pass
        _ensure_list()
        if token not in S.HOSTED_TOKENS:
            S.HOSTED_TOKENS.append(token)
            self._sync()
            stored = 'stored'
        else:
            stored = 'already stored'
        await S.safe_send(ctx.channel, S.ui_ok(f'{stored} | starting live client...'))
        try:
            from utils import host_runner
            prefix = getattr(S, 'PREFIX', '.')
            msg = await host_runner.start_token(token, prefix=prefix)
            await S.safe_send(ctx.channel, S.ui_ok(msg))
        except Exception as e:
            await S.safe_send(ctx.channel, S.ui_err(f'start failed: {e}'))

async def setup(bot):
    await bot.add_cog(HostCog(bot))
