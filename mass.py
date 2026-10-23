import asyncio
import os
import discord
from discord.ext import commands
from . import state as S
from .antid import batch_delay, shuffled, on_rate_limit, delay

def _safe_int(val, default=1, lo=1, hi=None):
    try:
        n = int(val)
    except (TypeError, ValueError):
        n = default
    n = max(lo, n)
    if hi is not None:
        n = min(n, hi)
    return n

class MassCog(commands.Cog, name='mass'):

    def __init__(self, bot):
        self.bot = bot
        self._dm_task = None
        self._abort = asyncio.Event()

    def _reset_abort(self):
        self._abort = asyncio.Event()

    @commands.command(name='massban', brief='Mass ban users')
    @commands.guild_only()
    async def massban(self, ctx, *members: discord.Member):
        if not members:
            return await S.safe_edit(ctx.message, S.ui_err('provide users to ban'))
        await S.safe_edit(ctx.message, S.ui_info(f'banning {len(members)}...'))
        done = 0
        for i, m in enumerate(shuffled(members)):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.ban(m, reason='massban')
                done += 1
            except Exception as e:
                if '429' in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f'banned {done}/{len(members)}'))

    @commands.command(name='masskick', brief='Mass kick users')
    @commands.guild_only()
    async def masskick(self, ctx, *members: discord.Member):
        if not members:
            return await S.safe_edit(ctx.message, S.ui_err('provide users to kick'))
        await S.safe_edit(ctx.message, S.ui_info(f'kicking {len(members)}...'))
        done = 0
        for i, m in enumerate(shuffled(members)):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.kick(m, reason='masskick')
                done += 1
            except Exception as e:
                if '429' in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f'kicked {done}/{len(members)}'))

    @commands.command(name='massrole', brief='Add role to many users')
    @commands.guild_only()
    async def massrole(self, ctx, role: discord.Role=None, *members: discord.Member):
        if not role:
            return await S.safe_edit(ctx.message, S.ui_err('usage: massrole <@role> <@users...>'))
        if members:
            targets = list(members)
        else:
            targets = [m for m in ctx.guild.members if not m.bot]
            if len(targets) > 100:
                return await S.safe_edit(ctx.message, S.ui_err(f'{len(targets)} members - pass users explicitly or use smaller scope'))
        done = 0
        for i, m in enumerate(shuffled(targets)):
            if self._abort.is_set():
                break
            try:
                await m.add_roles(role)
                done += 1
            except Exception as e:
                if '429' in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await S.safe_edit(ctx.message, S.ui_ok(f'added {role.name} to {done} members'))

    @commands.command(name='massunrole', brief='Remove role from many users')
    @commands.guild_only()
    async def massunrole(self, ctx, role: discord.Role=None, *members: discord.Member):
        if not role:
            return await S.safe_edit(ctx.message, S.ui_err('usage: massunrole <@role> <@users...>'))
        if members:
            targets = list(members)
        else:
            targets = [m for m in ctx.guild.members if role in m.roles]
            if len(targets) > 100:
                return await S.safe_edit(ctx.message, S.ui_err(f'{len(targets)} members with role - pass users explicitly'))
        done = 0
        for i, m in enumerate(shuffled(targets)):
            if self._abort.is_set():
                break
            try:
                await m.remove_roles(role)
                done += 1
            except Exception as e:
                if '429' in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await S.safe_edit(ctx.message, S.ui_ok(f'removed {role.name} from {done} members'))

    @commands.command(name='massch', brief='Create N text channels')
    @commands.guild_only()
    async def massch(self, ctx, name: str='channel', n: int=5):
        n = _safe_int(n, 5, 1, 25)
        await S.safe_edit(ctx.message, S.ui_info(f'creating {n} channels...'))
        done = 0
        for i in range(n):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.create_text_channel(f'{name}-{i + 1}')
                done += 1
            except Exception as e:
                if '429' in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await S.safe_edit(ctx.message, S.ui_ok(f'created {done}/{n} channels'))

    @commands.command(name='masscat', brief='Create N categories in server')
    @commands.guild_only()
    async def masscat(self, ctx, name: str='Category', n: int=5):
        n = _safe_int(n, 5, 1, 20)
        await ctx.message.delete()
        done = 0
        for i in range(n):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.create_category(f'{name}-{i + 1}' if n > 1 else name)
                done += 1
            except Exception as e:
                if '429' in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f'created {done}/{n} categories'))

    @commands.command(name='massrolecreate', brief='Create N roles in server')
    @commands.guild_only()
    async def massrolecreate(self, ctx, name: str='Role', n: int=5):
        n = _safe_int(n, 5, 1, 50)
        await ctx.message.delete()
        done = 0
        for i in range(n):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.create_role(name=f'{name}-{i + 1}' if n > 1 else name)
                done += 1
            except Exception as e:
                if '429' in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f'created {done}/{n} roles'))

    @commands.command(name='massvc', brief='Create N voice channels')
    @commands.guild_only()
    async def massvc(self, ctx, name: str='VC', n: int=5):
        n = _safe_int(n, 5, 1, 50)
        await ctx.message.delete()
        done = 0
        for i in range(n):
            if self._abort.is_set():
                break
            try:
                await ctx.guild.create_voice_channel(f'{name}-{i + 1}' if n > 1 else name)
                done += 1
            except Exception as e:
                if '429' in str(e):
                    await on_rate_limit(5.0)
            await batch_delay(i + 1)
        await ctx.channel.send(S.ui_ok(f'created {done}/{n} VCs'))

    @commands.command(name='massreact', brief='React to last N messages with emoji')
    async def massreact(self, ctx, emoji: str='', limit: int=10):
        if not emoji:
            return await S.safe_edit(ctx.message, S.ui_err('usage: massreact <emoji> [limit]'))
        limit = _safe_int(limit, 10, 1, 50)
        await ctx.message.delete()
        done = 0
        async for msg in ctx.channel.history(limit=limit):
            if self._abort.is_set():
                break
            try:
                await msg.add_reaction(emoji)
                done += 1
            except Exception:
                pass
            await asyncio.sleep(0)
        conf = await ctx.channel.send(S.ui_ok(f'reacted to {done}'))
        await asyncio.sleep(3)
        try:
            await conf.delete()
        except Exception:
            pass

    @commands.command(name='massdelete', brief='Delete your own last N messages')
    async def massdelete(self, ctx, n: int=10):
        n = _safe_int(n, 10, 1, 200)
        await ctx.message.delete()
        deleted = 0
        async for msg in ctx.channel.history(limit=n * 3):
            if self._abort.is_set():
                break
            if msg.author.id == self.bot.user.id:
                try:
                    await msg.delete()
                    deleted += 1
                except Exception:
                    pass
                await asyncio.sleep(0)
                if deleted >= n:
                    break
        conf = await ctx.channel.send(S.ui_ok(f'deleted {deleted}'))
        await asyncio.sleep(3)
        try:
            await conf.delete()
        except Exception:
            pass

    async def _collect_dm_targets(self, scope: str='dms'):
        scope = (scope or 'dms').lower().strip()
        targets = []
        seen = set()
        if scope in ('dms', 'dm', 'all', 'both', 'everyone'):
            for ch in self.bot.private_channels:
                if not isinstance(ch, discord.DMChannel):
                    continue
                recip = getattr(ch, 'recipient', None)
                uid = recip.id if recip else None
                if uid and uid in seen:
                    continue
                if uid:
                    seen.add(uid)
                targets.append((str(recip) if recip else str(ch.id), ch, 'channel'))
        if scope in ('friends', 'friend', 'both', 'all'):
            friends = []
            try:
                rels = getattr(self.bot, 'friends', None) or getattr(self.bot, 'relationships', None)
                if rels is not None:
                    for r in list(rels):
                        try:
                            t = getattr(r, 'type', None)
                            if t is not None and int(t) != 1:
                                continue
                            u = getattr(r, 'user', None) or r
                            if u and getattr(u, 'id', None):
                                friends.append(u)
                        except Exception:
                            pass
            except Exception:
                pass
            if not friends:
                try:
                    import aiohttp
                    token = S._get_token(self.bot)
                    async with aiohttp.ClientSession() as s:
                        async with s.get('https://discord.com/api/v9/users/@me/relationships', headers={'Authorization': token, 'User-Agent': S.USER_AGENT}) as r:
                            if r.status == 200:
                                data = await r.json()
                                for item in data or []:
                                    if int(item.get('type', 0)) != 1:
                                        continue
                                    u = item.get("user") or {}
                                    uid = u.get("id")
                                    if uid:

                                        class _U:
                                            pass
                                        uu = _U()
                                        uu.id = int(uid)
                                        uu.name = u.get("username") or uid
                                        friends.append(uu)
                except Exception as e:
                    print(f'[massdm] friends fetch: {e}')
            for u in friends:
                uid = int(u.id)
                if uid in seen:
                    continue
                seen.add(uid)
                existing = None
                for ch in self.bot.private_channels:
                    if isinstance(ch, discord.DMChannel) and getattr(getattr(ch, 'recipient', None), 'id', None) == uid:
                        existing = ch
                        break
                if existing:
                    targets.append((str(getattr(u, 'name', uid)), existing, 'channel'))
                else:
                    targets.append((str(getattr(u, 'name', uid)), uid, 'user'))
        return targets

    async def _send_one_dm(self, target, text, session, headers):
        label, obj, mode = target
        try:
            if mode == 'channel':
                await obj.send(text)
                return True
            uid = str(obj)
            async with session.post('https://discord.com/api/v9/users/@me/channels', headers=headers, json={'recipient_id': uid}) as r:
                if r.status == 429:
                    await on_rate_limit(4.0)
                    return False
                if r.status not in (200, 201):
                    return False
                data = await r.json()
                cid = data.get("id")
            if not cid:
                return False
            async with session.post(f'https://discord.com/api/v9/channels/{cid}/messages', headers=headers, json={'content': text}) as r2:
                if r2.status == 429:
                    await on_rate_limit(4.0)
                    return False
                return r2.status in (200, 201)
        except Exception:
            return False

    async def _run_massdm(self, targets, text, status_msg, delay_s: float=0.85):
        sent = failed = 0
        token = S._get_token(self.bot)
        headers = {'Authorization': token, 'Content-Type': 'application/json', 'User-Agent': getattr(S, 'USER_AGENT', 'Mozilla/5.0')}
        import aiohttp
        async with aiohttp.ClientSession() as session:
            for i, target in enumerate(targets):
                if self._abort.is_set():
                    break
                ok = await self._send_one_dm(target, text, session, headers)
                if ok:
                    sent += 1
                else:
                    failed += 1
                if status_msg and i % 3 == 0:
                    try:
                        await status_msg.edit(content=S.ui_info(f'DMing... {sent}/{len(targets)}  fail {failed}'))
                    except Exception:
                        pass
                await delay(max(0.35, delay_s * 0.75), delay_s * 1.25)
        if status_msg:
            try:
                await status_msg.edit(content=S.ui_ok(f'massdm done - sent {sent}/{len(targets)}  fail {failed}'))
            except Exception:
                pass

    @commands.command(name='massdm', brief='Mass DM - scope: dms | friends | both')
    async def massdm(self, ctx, scope: str='dms', *, text: str=''):
        scopes = {'dms', 'dm', 'friends', 'friend', 'both', 'all', 'everyone'}
        if scope.lower() not in scopes:
            text = f'{scope} {text}'.strip() if text else scope
            scope = 'dms'
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: massdm [dms|friends|both] <message>'))
        if self._dm_task and (not self._dm_task.done()):
            return await S.safe_edit(ctx.message, S.ui_err('massdm running - stopdm'))
        targets = await self._collect_dm_targets(scope)
        if not targets:
            return await S.safe_edit(ctx.message, S.ui_err(f'no targets for scope `{scope}`'))
        try:
            await ctx.message.delete()
        except Exception:
            pass
        self._reset_abort()
        status = await ctx.channel.send(S.ui_info(f'massdm `{scope}` → {len(targets)} targets (stopdm to abort)'))
        self._dm_task = asyncio.create_task(self._run_massdm(targets, text, status, delay_s=0.85))

    @commands.command(name='massdmfast', brief='Faster massdm (shorter delay)')
    async def massdmfast(self, ctx, scope: str='dms', *, text: str=''):
        scopes = {'dms', 'dm', 'friends', 'friend', 'both', 'all', 'everyone'}
        if scope.lower() not in scopes:
            text = f'{scope} {text}'.strip() if text else scope
            scope = 'dms'
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: massdmfast [dms|friends|both] <msg>'))
        if self._dm_task and (not self._dm_task.done()):
            return await S.safe_edit(ctx.message, S.ui_err('massdm running - stopdm'))
        targets = await self._collect_dm_targets(scope)
        if not targets:
            return await S.safe_edit(ctx.message, S.ui_err(f'no targets for `{scope}`'))
        try:
            await ctx.message.delete()
        except Exception:
            pass
        self._reset_abort()
        status = await ctx.channel.send(S.ui_info(f'massdmfast `{scope}` → {len(targets)} (stopdm to abort)'))
        self._dm_task = asyncio.create_task(self._run_massdm(targets, text, status, delay_s=0.45))

    @commands.command(name='stopdm', brief='Stop running mass DM')
    async def stopdm(self, ctx):
        self._abort.set()
        if self._dm_task and (not self._dm_task.done()):
            self._dm_task.cancel()
            try:
                await self._dm_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dm_task = None
            await S.safe_edit(ctx.message, S.ui_ok('massdm aborted'))
        else:
            await S.safe_edit(ctx.message, S.ui_info('no massdm running'))

    @commands.command(name='stopmass', brief='Abort any running mass action')
    async def stopmass(self, ctx):
        self._abort.set()
        if self._dm_task and (not self._dm_task.done()):
            self._dm_task.cancel()
            try:
                await self._dm_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dm_task = None
        await S.safe_edit(ctx.message, S.ui_ok('mass abort signal sent'))

    @commands.command(name='dmstats', brief='Show DM channel stats')
    async def dmstats(self, ctx):
        dms = [c for c in self.bot.private_channels if isinstance(c, discord.DMChannel)]
        friends_n = 0
        try:
            targets = await self._collect_dm_targets('friends')
            friends_n = len(targets)
        except Exception:
            pass
        await S.safe_edit(ctx.message, S.ui_box('dm stats', [f'  {S.DIM}open DMs{S.RESET}  {len(dms)}', f'  {S.DIM}friends{S.RESET}   {friends_n}', f"  {S.DIM}massdm{S.RESET}    {('running' if self._dm_task and (not self._dm_task.done()) else 'idle')}"]))

    @commands.command(name='massdmfile', brief='Mass DM IDs from file')
    async def massdmfile(self, ctx, filepath: str='', *, text: str=''):
        if not filepath or not text:
            return await S.safe_edit(ctx.message, S.ui_err('usage: massdmfile <path> <msg>'))
        if not os.path.exists(filepath):
            return await S.safe_edit(ctx.message, S.ui_err('file not found'))
        with open(filepath, encoding='utf-8') as f:
            ids = [l.strip() for l in f if l.strip().isdigit()]
        if not ids:
            return await S.safe_edit(ctx.message, S.ui_err('no valid user ids in file'))
        await ctx.message.delete()
        self._reset_abort()
        h = {'Authorization': S._get_token(), 'Content-Type': 'application/json', 'User-Agent': S.USER_AGENT}
        done = 0
        import aiohttp
        async with aiohttp.ClientSession() as s:
            for uid in ids:
                if self._abort.is_set():
                    break
                try:
                    async with s.post('https://discord.com/api/v9/users/@me/channels', headers=h, json={'recipient_id': uid}) as r:
                        if r.status == 200:
                            cid = (await r.json()).get("id")
                            if cid:
                                async with s.post(f'https://discord.com/api/v9/channels/{cid}/messages', headers=h, json={'content': text}) as r2:
                                    if r2.status in (200, 201):
                                        done += 1
                    if r.status == 429:
                        await on_rate_limit(5.0)
                except Exception:
                    pass
                await delay(0.5, 0.9)
        await ctx.channel.send(S.ui_ok(f'sent to {done}/{len(ids)}'))

    @commands.command(name='massfriend', brief='Mass add friends from ID file')
    async def massfriend(self, ctx, filepath: str=''):
        if not filepath or not os.path.exists(filepath):
            return await S.safe_edit(ctx.message, S.ui_err('usage: massfriend <file>'))
        with open(filepath, encoding='utf-8') as f:
            ids = [l.strip() for l in f if l.strip().isdigit()]
        if not ids:
            return await S.safe_edit(ctx.message, S.ui_err('no valid user ids in file'))
        await ctx.message.delete()
        self._reset_abort()
        h = {'Authorization': S._get_token(), 'Content-Type': 'application/json', 'User-Agent': S.USER_AGENT}
        done = 0
        import aiohttp
        async with aiohttp.ClientSession() as s:
            for uid in ids:
                if self._abort.is_set():
                    break
                try:
                    async with s.put(f'https://discord.com/api/v9/users/@me/relationships/{uid}', headers=h, json={'type': 1}) as r:
                        if r.status in (200, 201, 204):
                            done += 1
                        if r.status == 429:
                            await on_rate_limit(5.0)
                except Exception:
                    pass
                await asyncio.sleep(1.5)
        await ctx.channel.send(S.ui_ok(f'sent {done}/{len(ids)}'))

    @commands.command(name='massjoin', brief='Join server with hosted tokens')
    async def massjoin(self, ctx, invite: str='', count: int=1):
        from uuid import uuid4
        import aiohttp
        if not invite:
            return await S.safe_edit(ctx.message, S.ui_err('usage: massjoin <invite> [count]'))
        invite = invite.replace('https://discord.gg/', '').replace('https://discord.gg/', '').replace('discord.gg/', '').replace('https://discord.com/invite/', '').strip('/')
        tokens = list(getattr(S, 'HOSTED_TOKENS', []) or [])[:_safe_int(count, 1, 1, 50)]
        if not tokens:
            return await S.safe_edit(ctx.message, S.ui_err('no hosted tokens in S.HOSTED_TOKENS'))
        await ctx.message.delete()
        self._reset_abort()
        done = 0
        async with aiohttp.ClientSession() as s:
            for tk in tokens:
                if self._abort.is_set():
                    break
                try:
                    async with s.post(f'https://discord.com/api/v9/invites/{invite}', headers={'Authorization': tk, 'Content-Type': 'application/json', 'User-Agent': S.USER_AGENT}, json={'session_id': str(uuid4())[:12]}) as r:
                        if r.status in (200, 204):
                            done += 1
                        if r.status == 429:
                            await on_rate_limit(5.0)
                except Exception:
                    pass
                await asyncio.sleep(1.5)
        await ctx.channel.send(S.ui_ok(f'joined {done}/{len(tokens)}'))

    @commands.command(name='massleave', brief='Leave a server with all hosted tokens')
    async def massleave(self, ctx, guild_id: str=''):
        import aiohttp
        if not guild_id:
            return await S.safe_edit(ctx.message, S.ui_err('usage: massleave <guild_id>'))
        tokens = list(getattr(S, 'HOSTED_TOKENS', []) or [])
        if not tokens:
            return await S.safe_edit(ctx.message, S.ui_err('no hosted tokens'))
        await ctx.message.delete()
        self._reset_abort()
        done = 0
        async with aiohttp.ClientSession() as s:
            for tk in tokens:
                if self._abort.is_set():
                    break
                try:
                    async with s.delete(f'https://discord.com/api/v9/users/@me/guilds/{guild_id}', headers={'Authorization': tk, 'User-Agent': S.USER_AGENT}) as r:
                        if r.status in (200, 204):
                            done += 1
                        if r.status == 429:
                            await on_rate_limit(5.0)
                except Exception:
                    pass
                await asyncio.sleep(1.0)
        await ctx.channel.send(S.ui_ok(f'left {done}/{len(tokens)}'))

    @commands.command(name='massreport', brief='Mass report users/servers with hosted tokens')
    async def massreport(self, ctx, mode: str='help', reason: str='spam', *, targets: str=''):
        import aiohttp
        reason_map = {'spam': 1, 'illegal': 3, 'harassment': 4, 'malware': 5, 'selfharm': 6, 'other': 1}
        mode = (mode or 'help').lower()
        if mode in ('help', '?', 'h'):
            return await S.safe_edit(ctx.message, S.ui_box('massreport', [f'  {S.DIM}user{S.RESET}    massreport user <reason> <@u|id|file:path>', f'  {S.DIM}server{S.RESET}  massreport server <reason> <guild_id|invite|here>', f'  {S.DIM}reasons{S.RESET} spam illegal harassment malware selfharm other', f'  {S.DIM}tokens{S.RESET}  uses hosted tokens (.hostlist) then main token']))
        if mode in reason_map and (not targets):
            targets = (reason + ' ' + targets).strip()
            reason = mode
            mode = 'user'
        elif mode in reason_map:
            targets = f'{reason} {targets}'.strip()
            reason = mode
            mode = 'user'
        key = (reason or 'spam').lower()
        reason_type = reason_map.get(key, 1)
        tokens = list(getattr(S, 'HOSTED_TOKENS', []) or [])
        main = S._get_token(self.bot)
        if main and main not in tokens:
            tokens.append(main)
        tokens = [t for t in tokens if t]
        if not tokens:
            return await S.safe_edit(ctx.message, S.ui_err('no tokens - add with .hostadd <token>'))
        ua = getattr(S, 'USER_AGENT', 'Mozilla/5.0')
        self._reset_abort()

        async def _report_user(session, token, uid):
            headers = {'Authorization': token, 'Content-Type': 'application/json', 'User-Agent': ua}
            payload_user = {
                'version': '1.0', 'variant': '3', 'language': 'en',
                'breadcrumbs': [1], 'elements': {}, 'name': 'user', 'user_id': str(uid),
            }
            for url in (
                'https://discord.com/api/v9/reporting/user',
                f'https://discord.com/api/v9/users/{uid}/report',
            ):
                try:
                    body = payload_user if 'reporting' in url else {'reason': 1, 'version': '1.0'}
                    async with session.post(url, headers=headers, json=body) as r:
                        if r.status in (200, 201, 204):
                            return True
                        if r.status == 429:
                            try:
                                await on_rate_limit(float((await r.json()).get('retry_after', 3)))
                            except Exception:
                                await on_rate_limit(5.0)
                except Exception:
                    continue
            return False

        async def _report_guild(session, token, guild_id):
            headers = {'Authorization': token, 'Content-Type': 'application/json', 'User-Agent': ua}
            payloads = [{'guild_id': str(guild_id), 'reason': reason_type, 'version': '1.0'}, {'guild_id': str(guild_id), 'channel_id': None, 'message_id': None, 'reason': reason_type}]
            urls = ['https://discord.com/api/v9/reporting/guild', f'https://discord.com/api/v9/guilds/{guild_id}/report']
            for url in urls:
                for body in payloads:
                    try:
                        async with session.post(url, headers=headers, json=body) as r:
                            if r.status in (200, 201, 204):
                                return True
                            if r.status == 429:
                                try:
                                    data = await r.json()
                                    await on_rate_limit(float(data.get('retry_after', 5)))
                                except Exception:
                                    await on_rate_limit(5.0)
                    except Exception:
                        continue
            return False
        if mode in ('user', 'users', 'u'):
            user_ids = []
            raw = (targets or '').strip()
            if raw.lower().startswith('file:'):
                path = raw[5:].strip()
                if not os.path.exists(path):
                    return await S.safe_edit(ctx.message, S.ui_err('file not found'))
                with open(path, encoding='utf-8') as f:
                    user_ids = [l.strip() for l in f if l.strip().isdigit()]
            else:
                for m in ctx.message.mentions:
                    user_ids.append(str(m.id))
                for tok in raw.split():
                    tok = tok.strip('<@!>')
                    if tok.isdigit():
                        user_ids.append(tok)
            user_ids = list(dict.fromkeys(user_ids))
            if not user_ids:
                return await S.safe_edit(ctx.message, S.ui_err('usage: massreport user <reason> <@users|ids|file:path>'))
            await S.safe_edit(ctx.message, S.ui_info(f'reporting {len(user_ids)} user(s) × {len(tokens)} token(s)...'))
            done = 0
            total = len(user_ids) * len(tokens)
            async with aiohttp.ClientSession() as s:
                for uid in user_ids:
                    if self._abort.is_set():
                        break
                    for tk in tokens:
                        if self._abort.is_set():
                            break
                        if await _report_user(s, tk, uid):
                            done += 1
                        await delay(0.45, 0.9)
            return await S.safe_edit(ctx.message, S.ui_ok(f'user reports ok {done}/{total} ({key})'))
        if mode in ('server', 'guild', 's'):
            raw = (targets or '').strip()
            guild_id = None
            if not raw or raw.lower() in ('here', 'this'):
                if ctx.guild:
                    guild_id = str(ctx.guild.id)
            elif raw.isdigit():
                guild_id = raw
            else:
                code = raw.split('/')[-1].split('?')[0].strip()
                try:
                    inv = await self.bot.fetch_invite(code)
                    guild_id = str(getattr(getattr(inv, 'guild', None), 'id', '') or '')
                except Exception as e:
                    return await S.safe_edit(ctx.message, S.ui_err(f'invite resolve failed: {e}'))
            if not guild_id:
                return await S.safe_edit(ctx.message, S.ui_err('usage: massreport server <reason> <guild_id|invite|here>'))
            await S.safe_edit(ctx.message, S.ui_info(f'reporting guild {guild_id} × {len(tokens)} token(s)...'))
            done = 0
            async with aiohttp.ClientSession() as s:
                for tk in tokens:
                    if self._abort.is_set():
                        break
                    if await _report_guild(s, tk, guild_id):
                        done += 1
                    await delay(0.6, 1.2)
            return await S.safe_edit(ctx.message, S.ui_ok(f'server reports ok {done}/{len(tokens)} ({key})'))
        return await S.safe_edit(ctx.message, S.ui_err('mode: user | server | help'))

    def cog_unload(self):
        t = getattr(self, '_dm_task', None)
        if t and (not t.done()):
            t.cancel()

async def setup(bot):
    await bot.add_cog(MassCog(bot))
