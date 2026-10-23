import asyncio
import time
import discord
from discord.ext import commands
from . import state as S
from .antid import jitter
if not hasattr(S, '_reminders') or S._reminders is None:
    S._reminders = []
if not hasattr(S, '_notify_watch'):
    S._notify_watch = {}
_active_timers: dict[int, list] = {}

def _parse_duration(s: str) -> int:
    s = s.strip().lower()
    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    if s and s[-1] in multipliers:
        try:
            return int(s[:-1]) * multipliers[s[-1]]
        except (ValueError, TypeError):
            pass
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0

class RemindersCog(commands.Cog, name='reminders'):

    def __init__(self, bot):
        self.bot = bot
        self._task = None

    async def cog_load(self):
        self._task = asyncio.create_task(self._check_loop())

    def cog_unload(self):
        if self._task and (not self._task.done()):
            self._task.cancel()
        for tasks in _active_timers.values():
            for t in tasks:
                if not t.done():
                    t.cancel()

    async def _check_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                now = time.time()
                fired = [r for r in S._reminders if now >= r['at']]
                for r in fired:
                    S._reminders.remove(r)
                    ch = self.bot.get_channel(r['channel'])
                    if ch:
                        try:
                            await S.safe_send(ch, S.ui_info(f"⏰ reminder: {r['text']}"))
                        except Exception:
                            pass
            except Exception as e:
                print(f'[reminders] check_loop: {e}')
            await asyncio.sleep(jitter(10.0))

    @commands.command(name='remind', aliases=['reminder'], brief='Set a reminder  .remind 30m do thing')
    async def remind(self, ctx, when: str='', *, text: str='reminder'):
        if not when:
            return await S.safe_edit(ctx.message, S.ui_err('usage: remind <time> <text>  (e.g. remind 30m do thing)'))
        secs = _parse_duration(when)
        if secs <= 0:
            return await S.safe_edit(ctx.message, S.ui_err('invalid time - use e.g. 30s, 5m, 2h, 1d'))
        S._reminders.append({'at': time.time() + secs, 'text': text, 'channel': ctx.channel.id})
        await S.safe_edit(ctx.message, S.ui_ok(f'reminder in {when}: {text}'))

    @commands.command(name='reminders', aliases=['rlist'], brief='List pending reminders')
    async def list_reminders(self, ctx):
        if not S._reminders:
            return await S.safe_edit(ctx.message, S.ui_info('no reminders set'))
        now = time.time()
        rows = [f"  {S.GREY}{i}{S.RESET}  {r['text']}  {S.DIM}(in {int(r['at'] - now)}s){S.RESET}" for i, r in enumerate(S._reminders)]
        await S.safe_edit(ctx.message, S._paginate('reminders', f'{len(rows)} pending', rows))

    @commands.command(name='clearreminders', aliases=['rclr'], brief='Clear all reminders')
    async def clearreminders(self, ctx):
        count = len(S._reminders)
        S._reminders.clear()
        await S.safe_edit(ctx.message, S.ui_ok(f'cleared {count} reminder(s)'))

    @commands.command(name='delremind', aliases=['delr'], brief='Delete reminder by index  .delremind 0')
    async def delremind(self, ctx, index: int=-1):
        if 0 <= index < len(S._reminders):
            removed = S._reminders.pop(index)
            await S.safe_edit(ctx.message, S.ui_ok(f'removed: {removed.get("text", "?")}'))
        else:
            await S.safe_edit(ctx.message, S.ui_err(f'invalid index - use .reminders to see indices (0-{len(S._reminders) - 1})'))

    @commands.command(name='timer', brief='Set a countdown timer  .timer 60 pizza')
    async def timer(self, ctx, when: str='0', *, label: str='Timer'):
        secs = _parse_duration(when)
        if secs <= 0:
            return await S.safe_edit(ctx.message, S.ui_err('usage: timer <duration> [label]  (e.g. timer 90s pizza)'))
        await S.safe_edit(ctx.message, S.ui_ok(f'⏱ {label} - {when}'))

        async def _fire():
            await asyncio.sleep(secs)
            try:
                await S.safe_send(ctx.channel, S.ui_ok(f'⏰ {label} - done! ({when})'))
            except Exception:
                pass
            cid = ctx.channel.id
            tasks = _active_timers.get(cid, [])
            _active_timers[cid] = [t for t in tasks if not t.done()]
        task = asyncio.create_task(_fire())
        _active_timers.setdefault(ctx.channel.id, []).append(task)

    @commands.command(name='timers', brief='List active timers and reminders')
    async def timers(self, ctx):
        now = time.time()
        rows = [f"  {S.GREY}{i}{S.RESET}  {r.get('text', '?')}  {S.DIM}in {max(0, int(r.get('at', 0) - now))}s{S.RESET}" for i, r in enumerate(S._reminders)]
        timer_count = sum((1 for tasks in _active_timers.values() for t in tasks if not t.done()))
        subtitle = f'{len(rows)} reminder(s)  |  {timer_count} active timer(s)'
        await S.safe_edit(ctx.message, S._paginate('timers', subtitle, rows) if rows else S.ui_info(subtitle))

    @commands.command(name='notify', brief='Alert when a user sends a message  .notify @user')
    async def notify(self, ctx, user: discord.User=None):
        if not user:
            return await S.safe_edit(ctx.message, S.ui_err('usage: notify <@user>'))
        S._notify_watch[user.id] = ctx.channel.id
        await S.safe_edit(ctx.message, S.ui_ok(f'watching {user} - notifying here when they send'))

    @commands.command(name='unnotify', aliases=['stopnotify'], brief='Remove a notify watch  .unnotify @user')
    async def unnotify(self, ctx, user: discord.User=None):
        if not user:
            return await S.safe_edit(ctx.message, S.ui_err('usage: unnotify <@user>'))
        removed = S._notify_watch.pop(user.id, None)
        await S.safe_edit(ctx.message, S.ui_ok(f'removed notify watch for {user}') if removed else S.ui_warn(f'no watch set for {user}'))

    @commands.command(name='notifications', aliases=['notiflist'], brief='List notification watches')
    async def notifications(self, ctx):
        watches = S._notify_watch or {}
        rows = [f'  {S.GREY}*{S.RESET} <@{uid}> → <#{cid}>' for uid, cid in watches.items()]
        await S.safe_edit(ctx.message, S._paginate('notifications', f'{len(rows)} active', rows) if rows else S.ui_info('no active notification watches'))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.bot.user or message.author.id == self.bot.user.id:
            return
        watches = S._notify_watch or {}
        if message.author.id not in watches:
            return
        ch_id = watches.pop(message.author.id, None)
        if not ch_id:
            return
        ch = self.bot.get_channel(ch_id)
        if ch:
            try:
                await ch.send(S.ui_info(f"📌 {message.author} sent a message in <#{message.channel.id}>: {message.content[:100] or '[no text]'}"))
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(RemindersCog(bot))
