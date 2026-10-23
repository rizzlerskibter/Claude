
import discord
from discord.ext import commands
from . import state as S

async def _log(ch_id, content):
    if not ch_id:
        return
    bot = S.BOT
    if not bot:
        return
    try:
        ch_id = int(ch_id)
    except Exception:
        return
    ch = bot.get_channel(ch_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(ch_id)
        except Exception:
            return
    try:
        await ch.send(content[:1900])
    except Exception:
        pass

NL = chr(10)

class LoggersCog(commands.Cog, name='loggers'):

    def __init__(self, bot):
        self.bot = bot

    def _parse_channel(self, ctx, channel):
        if channel is not None:
            return channel
        if ctx.message.channel_mentions:
            return ctx.message.channel_mentions[0]
        return ctx.channel

    @commands.group(name='logger', invoke_without_command=True, brief='Logger config')
    async def logger(self, ctx):
        rows = [f"  {S.DIM}{k}{S.RESET}  on={v.get('enabled')}  ch={v.get('channel') or '-'}" for k, v in S.loggers.items()]
        rows.append(f"  {S.DIM}types{S.RESET}  " + ", ".join(S.loggers.keys()))
        await S.safe_edit(ctx.message, S.ui_box('loggers', rows))

    @logger.command(name='set', aliases=['channel', 'ch'])
    async def logger_set(self, ctx, log_type: str = '', channel: discord.TextChannel = None):
        log_type = (log_type or '').lower().strip()
        if log_type in ('all', '*'):
            ch = self._parse_channel(ctx, channel)
            for k in S.loggers:
                S.loggers[k]['enabled'] = True
                S.loggers[k]['channel'] = ch.id
            
        try:
            cfg = S.load_config() if hasattr(S, 'load_config') else {}
            if not isinstance(cfg, dict):
                cfg = {}
            cfg['loggers'] = S.loggers
            if hasattr(S, 'save_config'):
                S.save_config(cfg)
        except Exception:
            pass

            return await S.safe_edit(ctx.message, S.ui_ok(f'all loggers → #{ch.name} ({ch.id})'))
        if log_type not in S.loggers:
            return await S.safe_edit(ctx.message, S.ui_err(f'unknown type: {log_type} | {", ".join(S.loggers)}'))
        ch = self._parse_channel(ctx, channel)
        S.loggers[log_type]['enabled'] = True
        S.loggers[log_type]['channel'] = ch.id
        
        try:
            cfg = S.load_config() if hasattr(S, 'load_config') else {}
            if not isinstance(cfg, dict):
                cfg = {}
            cfg['loggers'] = S.loggers
            if hasattr(S, 'save_config'):
                S.save_config(cfg)
        except Exception:
            pass

        await S.safe_edit(ctx.message, S.ui_ok(f'logger {log_type} → #{ch.name} ({ch.id})'))

    @logger.command(name='off')
    async def logger_off(self, ctx, log_type: str = ''):
        log_type = (log_type or '').lower().strip()
        if log_type in ('all', '*'):
            for k in S.loggers:
                S.loggers[k]['enabled'] = False
            return await S.safe_edit(ctx.message, S.ui_ok('all loggers off'))
        if log_type in S.loggers:
            S.loggers[log_type]['enabled'] = False
            await S.safe_edit(ctx.message, S.ui_ok(f'logger {log_type} off'))
        else:
            await S.safe_edit(ctx.message, S.ui_err(f'unknown type: {log_type}'))

    @logger.command(name='here')
    async def logger_here(self, ctx, log_type: str = 'all'):
        await self.logger_set(ctx, log_type or 'all', ctx.channel)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        cfg = S.loggers.get('deleted', {})
        if not cfg.get('enabled') or not cfg.get('channel'):
            return
        if not self.bot.user or message.author.id == self.bot.user.id:
            return
        name = getattr(message.channel, 'name', message.channel.id)
        txt = '```' + NL + f'deleted in #{name}' + NL + f'author: {message.author}' + NL + f"content: {(message.content or '[no text]')[:400]}" + NL + '```'
        await _log(cfg['channel'], txt)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        cfg = S.loggers.get('edited', {})
        if not cfg.get('enabled') or not cfg.get('channel'):
            return
        if not self.bot.user or before.author.id == self.bot.user.id:
            return
        if before.content == after.content:
            return
        name = getattr(before.channel, 'name', before.channel.id)
        txt = '```' + NL + f'edited in #{name}' + NL + f'author: {before.author}' + NL + f'before: {(before.content or "")[:200]}' + NL + f'after:  {(after.content or "")[:200]}' + NL + '```'
        await _log(cfg['channel'], txt)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cfg = S.loggers.get('joins', {})
        if not cfg.get('enabled') or not cfg.get('channel'):
            return
        await _log(cfg['channel'], f'join: {member} ({member.id}) guild={member.guild}')

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        cfg = S.loggers.get('leaves', {})
        if not cfg.get('enabled') or not cfg.get('channel'):
            return
        await _log(cfg['channel'], f'leave: {member} ({member.id}) guild={member.guild}')

    @commands.Cog.listener()
    async def on_message(self, message):
        if not self.bot.user or message.author.id == self.bot.user.id:
            return
        cfg = S.loggers.get('dm', {})
        if cfg.get('enabled') and cfg.get('channel') and isinstance(message.channel, discord.DMChannel):
            await _log(cfg['channel'], f'DM from {message.author}: {(message.content or "")[:300]}')
        cfg = S.loggers.get('mention', {})
        if cfg.get('enabled') and cfg.get('channel') and self.bot.user in (message.mentions or []):
            await _log(cfg['channel'], f'mention in #{getattr(message.channel, "name", "?")}: {message.author}: {(message.content or "")[:300]}')


async def setup(bot):
    if 'loggers' in bot.cogs:
        await bot.remove_cog('loggers')
    await bot.add_cog(LoggersCog(bot))
