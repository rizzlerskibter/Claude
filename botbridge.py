import asyncio
import discord
from discord.ext import commands
from . import state as S
try:
    from discord import app_commands
except Exception:
    app_commands = None

class BotBridge:

    def __init__(self):
        self.client = None
        self.tree = None
        self.task = None
        self.ready = asyncio.Event()
        self.user = None
        self._selfbot = None

    async def _handle_user_host(self, channel, author, token: str):
        token = (token or '').strip().strip('`"\'')
        if not token or len(token) < 50:
            await channel.send('usage: host <your_user_token>')
            return
        try:
            from cogs import state as S
            from utils import host_runner
            if not hasattr(S, 'HOSTED_TOKENS') or S.HOSTED_TOKENS is None:
                S.HOSTED_TOKENS = []
            if token not in S.HOSTED_TOKENS:
                S.HOSTED_TOKENS.append(token)
                try:
                    from pathlib import Path as P
                    import json
                    P('hosted_tokens.json').write_text(json.dumps(S.HOSTED_TOKENS, indent=2))
                except Exception:
                    pass
                note = 'stored'
            else:
                note = 'already stored'
            await channel.send(f'`ok` {note} | starting live selfbot...')
            prefix = getattr(S, 'PREFIX', '.')
            msg = await host_runner.start_token(token, prefix=prefix)
            await channel.send(f'`ok` {msg}')
        except Exception as e:
            await channel.send(f'`err` {e}')

    def bind_selfbot(self, bot):
        self._selfbot = bot

    def _quests_cog(self):
        if not self._selfbot:
            return None
        return self._selfbot.get_cog('quests')

    async def start(self, token: str) -> str:
        await self.stop()
        intents = discord.Intents.default()
        try:
            intents.message_content = True
            intents.members = True
            intents.guilds = True
        except Exception:
            pass
        client = discord.Client(intents=intents)
        tree = None
        bridge_self = self

        @client.event
        async def on_message(message):
            if not message.author:
                return
            if message.author.bot:
                return
            if any((c.user and message.author.id == c.user.id for c in getattr(BRIDGE, '_clients', []) if c and c.user)):
                return
            content = (message.content or '').strip()
            if not content:
                return
            low = content.lower()
            token = None
            for pref in ('-host ', '.host ', 'host '):
                if low.startswith(pref):
                    token = content[len(pref):].strip().strip('`"\'')
                    break
            if token is None and message.guild is None and (len(content) > 50) and (content.count('.') >= 2) and (' ' not in content):
                token = content.strip().strip('`')
            if not token:
                return
            if message.guild is not None and (not low.startswith(('-host', '.host', 'host '))):
                return
            await bridge_self._handle_user_host(message.channel, message.author, token)
        if app_commands is not None:
            tree = app_commands.CommandTree(client)
        bridge = self

        @client.event
        async def on_ready():
            bridge.user = client.user
            bridge.ready.set()
            print(f'[botbridge] online as {client.user} ({client.user.id})')
            if tree is not None:
                try:
                    await tree.sync()
                    print('[botbridge] slash commands synced (global)')
                except Exception as e:
                    print(f'[botbridge] slash sync: {e}')
        if tree is not None and app_commands is not None:

            @tree.command(name='ping', description='Latency check')
            async def slash_ping(interaction: discord.Interaction):
                ms = round(client.latency * 1000)
                await interaction.response.send_message(f'pong | {ms}ms', ephemeral=True)

            @tree.command(name='info', description='Wilt bot bridge info')
            async def slash_info(interaction: discord.Interaction):
                await interaction.response.send_message(f'wilt bot bridge v{S.VERSION}\napp: {client.user}\nguilds: {len(client.guilds)}', ephemeral=True)

            @tree.command(name='echo', description='Echo text')
            @app_commands.describe(text='Text to echo')
            async def slash_echo(interaction: discord.Interaction, text: str):
                await interaction.response.send_message(text[:1900])

            @tree.command(name='server', description='Server info')
            async def slash_server(interaction: discord.Interaction):
                g = interaction.guild
                if not g:
                    return await interaction.response.send_message('guild only', ephemeral=True)
                await interaction.response.send_message(f"**{g.name}**\nid: `{g.id}`\nmembers: {getattr(g, 'member_count', '?')}", ephemeral=True)
            quest_group = app_commands.Group(name='quest', description='Discord quests (via selfbot session)')

            @quest_group.command(name='status', description='Show quest status from selfbot cache')
            async def quest_status(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                cog = bridge._quests_cog()
                if cog is None:
                    return await interaction.followup.send('quests cog not loaded on selfbot', ephemeral=True)
                try:
                    await cog.get_quests()
                except Exception as e:
                    return await interaction.followup.send(f'fetch failed: {e}', ephemeral=True)
                enrolled = available = done = 0
                lines = []
                for q in list(getattr(cog, 'quests', {}).values()):
                    st = getattr(q, 'status', '')
                    if st == 'enrolled':
                        enrolled += 1
                        lines.append(f'* [enrolled] {q.title}')
                    elif st == 'completed':
                        done += 1
                    elif not getattr(q, 'is_expired', False) and getattr(q, 'is_supported', lambda: False)():
                        available += 1
                        lines.append(f'* [available] {q.title}')
                body = f"**quests** total={len(getattr(cog, 'quests', {}))}  enrolled={enrolled}  available={available}  done={done}\n" + ('\n'.join(lines[:15]) if lines else '_none active_')
                await interaction.followup.send(body[:1900], ephemeral=True)

            @quest_group.command(name='refresh', description='Refresh quest list')
            async def quest_refresh(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                cog = bridge._quests_cog()
                if cog is None:
                    return await interaction.followup.send('quests cog not loaded', ephemeral=True)
                ok = await cog.get_quests()
                n = len(getattr(cog, 'quests', {}))
                await interaction.followup.send(f'refreshed | {n} quests' if ok else 'refresh failed', ephemeral=True)

            @quest_group.command(name='enroll', description='Enroll in available supported quests')
            async def quest_enroll(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                cog = bridge._quests_cog()
                if cog is None:
                    return await interaction.followup.send('quests cog not loaded', ephemeral=True)
                try:
                    await cog.get_quests()
                    n = await cog.enroll_all_available()
                except Exception as e:
                    return await interaction.followup.send(f'enroll error: {e}', ephemeral=True)
                await interaction.followup.send(f'enrolled {n} quest(s)', ephemeral=True)

            @quest_group.command(name='start', description='Start quest auto-completer on selfbot')
            async def quest_start(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                cog = bridge._quests_cog()
                if cog is None:
                    return await interaction.followup.send('quests cog not loaded', ephemeral=True)
                try:
                    await cog.get_quests()
                    new_n = await cog.enroll_all_available()
                    cog.auto_complete = True
                    if hasattr(cog, '_start_completer'):
                        cog._start_completer()
                    enrolled = sum((1 for q in cog.quests.values() if q.status == 'enrolled' and (not q.is_expired)))
                except Exception as e:
                    return await interaction.followup.send(f'start error: {e}', ephemeral=True)
                await interaction.followup.send(f'auto-completer on | enrolled {enrolled} | newly {new_n}', ephemeral=True)

            @quest_group.command(name='stop', description='Stop quest auto-completer')
            async def quest_stop(interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                cog = bridge._quests_cog()
                if cog is None:
                    return await interaction.followup.send('quests cog not loaded', ephemeral=True)
                try:
                    if hasattr(cog, '_stop_completer'):
                        cog._stop_completer()
                    cog.auto_complete = False
                except Exception as e:
                    return await interaction.followup.send(f'stop error: {e}', ephemeral=True)
                await interaction.followup.send('auto-completer stopped', ephemeral=True)

            @tree.command(name='host', description='Submit your USER token to run on this host')
            async def slash_host(interaction: discord.Interaction, user_token: str):
                await interaction.response.defer(ephemeral=True)
                try:
                    await self._handle_user_host(interaction.channel, interaction.user, user_token)
                    await interaction.followup.send('submitted - check channel', ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f'error: {e}', ephemeral=True)

            @tree.command(name='hosthelp', description='How to host via this bot')
            async def slash_hosthelp(interaction: discord.Interaction):
                await interaction.response.send_message('DM the bot: `-host YOUR_USER_TOKEN`\nor `/host` with your user token.\nStarts a live selfbot under the host.', ephemeral=True)
            tree.add_command(quest_group)
        self.client = client
        self.tree = tree
        self.ready.clear()
        S.BOT_TOKEN = token
        S.BOT_CLIENT = client

        async def _runner():
            try:
                await client.start(token)
            except Exception as e:
                print(f'[botbridge] stopped: {e}')
            finally:
                self.ready.clear()
        self.task = asyncio.create_task(_runner())
        try:
            await asyncio.wait_for(self.ready.wait(), timeout=25)
        except asyncio.TimeoutError:
            return 'started but not ready within 25s - check token/intents'
        return f'online as {self.user}'

    async def stop(self):
        if self.client is not None:
            try:
                await self.client.close()
            except Exception:
                pass
        if self.task and (not self.task.done()):
            self.task.cancel()
            try:
                await self.task
            except Exception:
                pass
        self.client = None
        self.tree = None
        self.task = None
        self.user = None
        self.ready.clear()
        S.BOT_CLIENT = None

    @property
    def online(self) -> bool:
        return self.client is not None and self.user is not None
BRIDGE = BotBridge()

class BotBridgeCog(commands.Cog, name='botbridge'):

    def __init__(self, bot):
        self.bot = bot
        BRIDGE.bind_selfbot(bot)

    async def cog_unload(self):
        await BRIDGE.stop()

    @commands.command(name='setbottoken', aliases=['bottoken', 'botlogin'], brief='Attach an application bot token')
    async def setbottoken(self, ctx, token: str=''):
        token = (token or '').strip().strip('`"\'')
        if not token or token.lower() in ('status', 'info'):
            online = BRIDGE.online
            return await S.safe_edit(ctx.message, S.ui_box('bot bridge', [f"  {S.DIM}status{S.RESET}  {('online | ' + str(BRIDGE.user) if online else 'offline')}", f"  {S.DIM}token{S.RESET}   {('set' if S.BOT_TOKEN else 'none')}", f'  {S.DIM}usage{S.RESET}   setbottoken <bot_token>', f'  {S.DIM}slash{S.RESET}   /ping /info /echo /server', f'  {S.DIM}quest{S.RESET}   /quest status|refresh|enroll|start|stop', f'  {S.DIM}host{S.RESET}    DM -host <user_token> | /host', f'  {S.DIM}stop{S.RESET}    setbottoken stop']))
        if token.lower() in ('stop', 'off', 'logout', 'clear'):
            await BRIDGE.stop()
            try:
                cfg = S.load_config()
                cfg.pop('bot_token', None)
                S.save_config(cfg)
            except Exception:
                pass
            S.BOT_TOKEN = ''
            try:
                await ctx.message.delete()
            except Exception:
                pass
            return await ctx.channel.send(S.ui_ok('bot bridge stopped'))
        try:
            await ctx.message.delete()
        except Exception:
            pass
        status = await ctx.channel.send(S.ui_info('starting bot bridge...'))
        try:
            msg = await BRIDGE.start(token)
        except Exception as e:
            return await S.safe_edit(status, S.ui_err(f'bot start failed: {e}'))
        try:
            cfg = S.load_config()
            cfg['bot_token'] = token
            S.save_config(cfg)
        except Exception as e:
            print(f'[botbridge] save cfg: {e}')
        await S.safe_edit(status, S.ui_ok(f'bot bridge | {msg}'))

    @commands.command(name='botsync', brief='Re-sync bot slash commands')
    async def botsync(self, ctx, scope: str='global'):
        if not BRIDGE.online or BRIDGE.tree is None:
            return await S.safe_edit(ctx.message, S.ui_err('bot bridge offline - setbottoken first'))
        try:
            if scope.lower() == 'guild' and ctx.guild:
                BRIDGE.tree.copy_global_to(guild=ctx.guild)
                await BRIDGE.tree.sync(guild=ctx.guild)
                return await S.safe_edit(ctx.message, S.ui_ok(f'synced to guild {ctx.guild.id}'))
            await BRIDGE.tree.sync()
            return await S.safe_edit(ctx.message, S.ui_ok('global slash sync requested'))
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err(f'sync failed: {e}'))

    @commands.command(name='botstatus', brief='Application bot bridge status')
    async def botstatus(self, ctx):
        online = BRIDGE.online
        rows = [f'  {S.DIM}online{S.RESET}  {online}', f"  {S.DIM}user{S.RESET}    {(BRIDGE.user if online else '-')}", f'  {S.DIM}guilds{S.RESET}  {(len(BRIDGE.client.guilds) if online else 0)}', f'  {S.DIM}slash{S.RESET}   {BRIDGE.tree is not None}', f'  {S.DIM}quest{S.RESET}   /quest status refresh enroll start stop']
        await S.safe_edit(ctx.message, S.ui_box('bot', rows))

    @commands.command(name='botquest', brief='Quest controls via bot bridge status text')
    async def botquest(self, ctx, action: str='status'):
        cog = self.bot.get_cog('quests')
        if cog is None:
            return await S.safe_edit(ctx.message, S.ui_err('quests cog missing'))
        action = (action or 'status').lower()
        if action == 'refresh':
            ok = await cog.get_quests()
            return await S.safe_edit(ctx.message, S.ui_ok(f'refreshed {len(cog.quests)}') if ok else S.ui_err('fail'))
        if action == 'enroll':
            await cog.get_quests()
            n = await cog.enroll_all_available()
            return await S.safe_edit(ctx.message, S.ui_ok(f'enrolled {n}'))
        if action == 'start':
            await cog.get_quests()
            n = await cog.enroll_all_available()
            cog.auto_complete = True
            if hasattr(cog, '_start_completer'):
                cog._start_completer()
            return await S.safe_edit(ctx.message, S.ui_ok(f'auto on | newly {n}'))
        if action == 'stop':
            if hasattr(cog, '_stop_completer'):
                cog._stop_completer()
            cog.auto_complete = False
            return await S.safe_edit(ctx.message, S.ui_ok('auto off'))
        enrolled = sum((1 for q in cog.quests.values() if q.status == 'enrolled'))
        available = sum((1 for q in cog.quests.values() if q.status not in ('enrolled', 'completed') and (not q.is_expired) and q.is_supported()))
        return await S.safe_edit(ctx.message, S.ui_box('bot quest', [f'  {S.DIM}total{S.RESET}     {len(cog.quests)}', f'  {S.DIM}enrolled{S.RESET}  {enrolled}', f'  {S.DIM}available{S.RESET} {available}', f"  {S.DIM}auto{S.RESET}      {getattr(cog, 'auto_complete', False)}"]))

async def setup(bot):
    await bot.add_cog(BotBridgeCog(bot))
    try:
        cfg = S.load_config()
        tok = (cfg.get("bot_token") or '').strip()
        if tok:
            _bridge_task = asyncio.create_task(BRIDGE.start(tok))
            print('[botbridge] auto-start from config.json')
    except Exception as e:
        print(f'[botbridge] auto-start skip: {e}')
