import discord
from discord.ext import commands
from . import state as S
from .antid import jitter, delay, batch_delay, on_rate_limit

class SettingsCog(commands.Cog, name='settings'):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setprefix', brief='Change global prefix')
    async def setprefix(self, ctx, new: str=''):
        if not new:
            return await S.safe_edit(ctx.message, S.ui_err('usage: setprefix <prefix>'))
        S.PREFIX = new
        S._live_prefix[0] = new
        cfg = S.load_config()
        cfg['prefix'] = new
        S.save_config(cfg)
        await S.safe_edit(ctx.message, S.ui_ok(f'prefix → `{new}`'))

    @commands.command(name='serverprefix', brief='Per-server prefix')
    @commands.guild_only()
    async def serverprefix(self, ctx, prefix: str=''):
        if not prefix:
            return await S.safe_edit(ctx.message, S.ui_err('usage: serverprefix <prefix>'))
        S._server_prefixes[str(ctx.guild.id)] = prefix
        await S.safe_edit(ctx.message, S.ui_ok(f'server prefix → `{prefix}`'))

    @commands.command(name='clearprefix', brief='Clear per-server prefix')
    @commands.guild_only()
    async def clearprefix(self, ctx):
        S._server_prefixes.pop(str(ctx.guild.id), None)
        await S.safe_edit(ctx.message, S.ui_ok('server prefix cleared'))

    @commands.command(name='setcooldown', brief='Set per-command cooldown')
    async def setcooldown(self, ctx, seconds: float=0, cmd: str=''):
        if not cmd:
            return await S.safe_edit(ctx.message, S.ui_err('usage: setcooldown <seconds> <command>'))
        S._cooldowns[cmd.lower()] = seconds
        await S.safe_edit(ctx.message, S.ui_ok(f'cooldown `{cmd}` → {seconds}s'))

    @commands.group(name='alias', invoke_without_command=True, brief='Manage aliases')
    async def alias(self, ctx):
        await S.safe_edit(ctx.message, S.ui_info('alias add/remove/list/clear'))

    @alias.command(name='add')
    async def alias_add(self, ctx, alias: str='', cmd: str=''):
        if not alias or not cmd:
            return await S.safe_edit(ctx.message, S.ui_err('usage: alias add <alias> <cmd>'))
        S._aliases[alias] = cmd
        await S.safe_edit(ctx.message, S.ui_ok(f'alias `{alias}` → `{cmd}`'))

    @alias.command(name='remove')
    async def alias_remove(self, ctx, alias: str=''):
        S._aliases.pop(alias, None)
        await S.safe_edit(ctx.message, S.ui_ok(f'alias `{alias}` removed'))

    @alias.command(name='list')
    async def alias_list(self, ctx):
        rows = [f'  {S.GREY}*{S.RESET} `{k}` → `{v}`' for k, v in S._aliases.items()]
        await S.safe_edit(ctx.message, S._paginate('aliases', '', rows) if rows else S.ui_info('no aliases'))

    @alias.command(name='clear')
    async def alias_clear(self, ctx):
        S._aliases.clear()
        await S.safe_edit(ctx.message, S.ui_ok('aliases cleared'))

    @commands.command(name='disable', brief='Disable a command')
    async def disable(self, ctx, cmd: str=''):
        if not cmd:
            return await S.safe_edit(ctx.message, S.ui_err('usage: disable <command>'))
        S._cmd_disabled.add(cmd.lower())
        c = self.bot.get_command(cmd)
        if c:
            c.enabled = False
        await S.safe_edit(ctx.message, S.ui_ok(f'`{cmd}` disabled'))

    @commands.command(name='enable', brief='Enable a command')
    async def enable(self, ctx, cmd: str=''):
        if not cmd:
            return await S.safe_edit(ctx.message, S.ui_err('usage: enable <command>'))
        S._cmd_disabled.discard(cmd.lower())
        c = self.bot.get_command(cmd)
        if c:
            c.enabled = True
        await S.safe_edit(ctx.message, S.ui_ok(f'`{cmd}` enabled'))

    @commands.command(name='antid', brief='Anti-detection tuning')
    async def antid(self, ctx, key: str='', value: str=''):
        from .antid import CFG
        if key == 'set' and value:
            parts = value.split()
            if len(parts) >= 2 and parts[0] in CFG:
                try:
                    CFG[parts[0]] = float(parts[1])
                except ValueError:
                    pass
        if key and key in CFG and value:
            try:
                CFG[key] = float(value)
                return await S.safe_edit(ctx.message, S.ui_ok(f'antid.{key} → {CFG[key]}'))
            except ValueError:
                return await S.safe_edit(ctx.message, S.ui_err('value must be a number'))
        rows = [f'  {S.DIM}{k}{S.RESET}  {v}' for k, v in CFG.items()]
        rows += ['', f'  {S.DIM}antid <key> <value>  to tune{S.RESET}']
        await S.safe_edit(ctx.message, S.ui_box('anti-detection', rows))

    @commands.command(name='settings', brief='Show settings status')
    async def settings_status(self, ctx):
        await S.safe_edit(ctx.message, S.ui_box('settings', [f'  {S.DIM}prefix{S.RESET}           `{S.PREFIX}`', f'  {S.DIM}aliases{S.RESET}          {len(S._aliases)}', f'  {S.DIM}disabled cmds{S.RESET}    {len(S._cmd_disabled)}', f'  {S.DIM}per-cmd cooldowns{S.RESET} {len(S._cooldowns)}', f'  {S.DIM}server prefixes{S.RESET}  {len(S._server_prefixes)}']))

    @commands.command(name='stealthdelete', aliases=['stealth'], brief='Toggle auto-delete of command messages')
    async def stealthdelete(self, ctx, toggle: str=''):
        if toggle:
            S.STEALTH_DELETE = toggle.lower() not in ('off', 'disable', 'false', '0')
        else:
            S.STEALTH_DELETE = not getattr(S, 'STEALTH_DELETE', True)
        cfg = S.load_config()
        cfg['stealth_delete'] = S.STEALTH_DELETE
        S.save_config(cfg)
        await S.safe_edit(ctx.message, S.ui_ok(f"stealth delete → {('on' if S.STEALTH_DELETE else 'off')}"))

    @commands.command(name='stealthdelay', brief='Set stealth delete delay in seconds')
    async def stealthdelay(self, ctx, seconds: float=5):
        S.STEALTH_DELETE_SECONDS = max(0.5, float(seconds))
        cfg = S.load_config()
        cfg['stealth_delete_seconds'] = S.STEALTH_DELETE_SECONDS
        S.save_config(cfg)
        await S.safe_edit(ctx.message, S.ui_ok(f'stealth delay → {S.STEALTH_DELETE_SECONDS}s'))

    @commands.command(name='setcaptcha', aliases=['captchakey', 'setcap'])
    async def setcaptcha(self, ctx, provider: str = '', *, key: str = ''):
        providers = {
            '2captcha': '2captcha', '2cap': '2captcha', 'twocaptcha': '2captcha',
            'rucaptcha': 'rucaptcha',
            'solvecaptcha': 'solvecaptcha', 'solve': 'solvecaptcha',
            'capmonster': 'capmonster', 'capmonstercloud': 'capmonster',
            'anticaptcha': 'anticaptcha', 'anti': 'anticaptcha',
            'capsolver': 'capsolver',
            'nextcaptcha': 'nextcaptcha', 'next': 'nextcaptcha',
            'yescaptcha': 'yescaptcha', 'yes': 'yescaptcha',
            'captchapi': 'captchapi', 'capi': 'captchapi',
            'nopecha': 'nopecha',
            'nonecap': 'nonecap', 'none': 'nonecap', 'nc': 'nonecap',
            'deathbycaptcha': 'deathbycaptcha', 'dbc': 'deathbycaptcha',
        }
        if not provider and not key:
            cur_p = getattr(S, 'CAPTCHA_PROVIDER', '') or '2captcha'
            cur_k = getattr(S, 'CAPTCHA_API_KEY', '') or ''
            masked = (cur_k[:4] + '…' + cur_k[-4:]) if len(cur_k) > 8 else ('set' if cur_k else 'none')
            rows = [
                '  provider  %s' % cur_p,
                '  key       %s' % masked,
                '  .setcaptcha <provider> <api_key>',
                '  providers: 2captcha, rucaptcha, solvecaptcha,',
                '             capmonster, anticaptcha, capsolver,',
                '             yescaptcha, captchapi, nextcaptcha,',
                '             nonecap (1.3k free), nopecha, deathbycaptcha',
            ]
            return await S.safe_edit(ctx.message, S.ui_box('captcha', rows))
        # allow: setcaptcha <key>  OR  setcaptcha <provider> <key>
        p = (provider or '').strip().lower()
        k = (key or '').strip()
        if p and not k and p not in providers and len(p) > 12:
            k = p
            p = getattr(S, 'CAPTCHA_PROVIDER', '') or '2captcha'
        elif p in providers:
            p = providers[p]
        elif p and p not in providers and not k:
            k = provider.strip()
            p = getattr(S, 'CAPTCHA_PROVIDER', '') or '2captcha'
        else:
            p = providers.get(p, p or '2captcha')
        if not k:
            return await S.safe_edit(ctx.message, S.ui_err('usage: setcaptcha <provider> <api_key>'))
        if k.startswith('nc_live_') and (not p or p == '2captcha'):
            p = 'nonecap'
        if hasattr(S, 'set_captcha'):
            S.set_captcha(k, p)
        else:
            S.CAPTCHA_API_KEY = k
            S.CAPTCHA_PROVIDER = p
        masked = k[:4] + '…' + k[-4:] if len(k) > 8 else 'set'
        await S.safe_edit(ctx.message, S.ui_ok('captcha → %s · key %s' % (p, masked)))
        try:
            await ctx.message.delete()
        except Exception:
            pass

    @commands.command(name='clearcaptcha', aliases=['captchaoff'])
    async def clearcaptcha(self, ctx):
        if hasattr(S, 'set_captcha'):
            S.set_captcha('', getattr(S, 'CAPTCHA_PROVIDER', '2captcha'))
        else:
            S.CAPTCHA_API_KEY = ''
        await S.safe_edit(ctx.message, S.ui_ok('captcha key cleared'))

    @commands.command(name='captcha', aliases=['captchastatus'])
    async def captcha_status(self, ctx):
        cur_p = getattr(S, 'CAPTCHA_PROVIDER', '') or '2captcha'
        cur_k = getattr(S, 'CAPTCHA_API_KEY', '') or ''
        masked = (cur_k[:4] + '…' + cur_k[-4:]) if len(cur_k) > 8 else ('set' if cur_k else 'none')
        await S.safe_edit(ctx.message, S.ui_ok('provider=%s key=%s' % (cur_p, masked)))


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))
