import json, os, time, re, math
from collections import defaultdict
import aiohttp
ESC = '\x1b'
RESET = f'{ESC}[0m'
GREY = f'{ESC}[2;37m'
WHITE = f'{ESC}[1;37m'
CYAN = f'{ESC}[36m'
GREEN = f'{ESC}[32m'
RED = f'{ESC}[31m'
YELLOW = f'{ESC}[33m'
BLUE = f'{ESC}[34m'
DIM = f'{ESC}[2m'
DARK = f'{ESC}[30m'
BOLD = f'{ESC}[1m'
CYAN2 = f'{ESC}[0;36m'
WHITE2 = f'{ESC}[0;37m'
BLUE2 = f'{ESC}[0;34m'
BRAND = f'{ESC}[0;35m{ESC}[1m{ESC}[4m'
BOT = None
TOKEN = ''
BOT_TOKEN = ''
BOT_CLIENT = None
PREFIX = '.'
STEALTH_DELETE = True
GROQ_API_KEY = ''
OPENAI_API_KEY = ''
WHISPER_API_URL = ''
WHISPER_API_KEY = ''
STEALTH_DELETE_SECONDS = 5
DISCORD_MSG_LIMIT = 2000
CUSTOM_STATUS_TEXT = None
VERSION = '3.7.2'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9262 Chrome/155.0.8059.80 Electron/36.0.0 Safari/537.36'
CHROME_VERSION = '155.0.8059.80'
try:
    from utils.gateway import encode_super_properties as _enc_xsp
    X_SUPER_PROPERTIES = _enc_xsp()
except Exception:
    X_SUPER_PROPERTIES = 'eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiRGlzY29yZCBDbGllbnQiLCJkZXZpY2UiOiIiLCJzeXN0ZW1fbG9jYWxlIjoiZW4tVVMiLCJoYXNfY2xpZW50X21vZHMiOmZhbHNlLCJicm93c2VyX3VzZXJfYWdlbnQiOiJNb3ppbGxhLzUuMCAoV2luZG93cyBOVCAxMC4wOyBXaW42NDsgeDY0KSBBcHBsZVdlYktpdC81MzcuMzYgKEtIVE1MLCBsaWtlIEdlY2tvKSBkaXNjb3JkLzEuMC45MjYyIENocm9tZS8xNTUuMC44MDU5LjgwIEVsZWN0cm9uLzM2LjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMS4wLjkyNjIiLCJjbGllbnRfdmVyc2lvbiI6IjEuMC45MjYyIiwib3NfdmVyc2lvbiI6IjEwLjAuMjI2MzEiLCJvc19hcmNoIjoieDY0IiwiYXBwX2FyY2giOiJ4NjQiLCJyZWZlcnJlciI6IiIsInJlZmVycmluZ19kb21haW4iOiIiLCJyZWZlcnJlcl9jdXJyZW50IjoiIiwicmVmZXJyaW5nX2RvbWFpbl9jdXJyZW50IjoiIiwicmVsZWFzZV9jaGFubmVsIjoic3RhYmxlIiwiY2xpZW50X2J1aWxkX251bWJlciI6MzY1MjA2LCJjbGllbnRfZXZlbnRfc291cmNlIjpudWxsfQ=='


def restore_loggers():
    try:
        cfg = load_config()
        raw = cfg.get("loggers") if isinstance(cfg, dict) else None
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k in loggers and isinstance(v, dict):
                    loggers[k].update(v)
    except Exception:
        pass

def load_config() -> dict:
    try:
        if os.path.exists('config.json'):
            with open('config.json', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_config(cfg: dict) -> None:
    try:
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f'[state] save_config: {e}')
_aliases: dict = {}
_cooldowns: dict = {}
_cooldown_last: dict = {}
_cmd_disabled: set = set()
_global_cooldown: float = 0.0
_server_prefixes: dict = {}
_user_blacklist: set = set()
_user_whitelist: set = set()
_role_restrict: set = set()
_perm_allow: dict = {}
_perm_block: set = set()
_perm_channel: dict = {}
_perm_server: dict = {}
_admins: set = set()
_devs: set = set()
afk = {'enabled': False, 'message': '', 'expires_at': 0, 'since': 0, 'emergency': False, 'dm_only': False, 'cooldown': 30, 'blacklist': set(), 'whitelist': set(), 'custom_replies': {}, 'per_server': {}, 'ping_counter': {}, 'last_reply': {}}
filters = {'spam': {'enabled': False, 'threshold': 5, 'window': 5, 'history': {}}, 'duplicate': {'enabled': False, 'window': 30, 'history': {}}, 'link': {'enabled': False, 'whitelist': set()}, 'invite': {'enabled': False}, 'attachment': {'enabled': False}, 'nsfw': {'enabled': False, 'keywords': set()}, 'mention_spam': {'enabled': False, 'threshold': 5}, 'mass_ping': {'enabled': False}, 'scam': {'enabled': False}, 'bot': {'enabled': False}, 'webhook': {'enabled': False}, 'auto_purge': {'enabled': False, 'keep': 50}, 'log_channel': None, 'actions_log': []}
loggers = {k: {'enabled': False, 'channel': None} for k in ('message', 'deleted', 'edited', 'reaction', 'mention', 'dm', 'joins', 'leaves')}
SNIPER_ENABLED = True
_snipe_cache: dict = {}
_editsnipe_cache: dict = {}
_vsniper_list: list = []
_vsniper_task = None
import os as _os
CAPTCHA_API_KEY = (_os.environ.get("CAPTCHA_API_KEY") or _os.environ.get("TWOCAPTCHA_API_KEY") or _os.environ.get("CAPMONSTER_API_KEY") or _os.environ.get("NONECAP_KEY") or _os.environ.get("NONECAP_API_KEY") or '').strip()
CAPTCHA_PROVIDER = (_os.environ.get("CAPTCHA_PROVIDER") or '2captcha').strip().lower()

def restore_captcha():
    global CAPTCHA_API_KEY, CAPTCHA_PROVIDER
    try:
        cfg = load_config()
        if not isinstance(cfg, dict):
            return
        k = (cfg.get("captcha_api_key") or cfg.get("CAPTCHA_API_KEY") or "").strip()
        p = (cfg.get("captcha_provider") or cfg.get("CAPTCHA_PROVIDER") or "").strip().lower()
        if k:
            CAPTCHA_API_KEY = k
        if p:
            CAPTCHA_PROVIDER = p
    except Exception:
        pass

def set_captcha(key: str, provider: str = ""):
    global CAPTCHA_API_KEY, CAPTCHA_PROVIDER
    CAPTCHA_API_KEY = (key or "").strip()
    if provider:
        CAPTCHA_PROVIDER = provider.strip().lower()
    elif CAPTCHA_API_KEY.startswith("nc_live_"):
        CAPTCHA_PROVIDER = "nonecap"
    try:
        cfg = load_config()
        if not isinstance(cfg, dict):
            cfg = {}
        cfg["captcha_api_key"] = CAPTCHA_API_KEY
        cfg["captcha_provider"] = CAPTCHA_PROVIDER or "2captcha"
        save_config(cfg)
    except Exception as e:
        print("[state] set_captcha save:", e)


_nitrosniper_enabled = True
_giveaway_enabled = False
_current_platform = 'desktop'
AUTO_RESPONSES: dict = {}
_autoreact_users: dict = {}
_multireact_users: dict = {}
_mimic_dict: dict = {}
_tracked_users: set = set()
_tracking: dict = {}
_autoaddback: bool = False
_notify_watch: dict = {}
_reminders: list = []
ar_rules: list = []
ar_variables: dict = {}
_triggers = {'message': [], 'reaction': [], 'voice': [], 'member': []}
_trigger_fired_counts: dict = {}
nickname = {'enabled': False, 'pattern': '{user}', 'interval': 300, 'history': {}}
meta = {'debug': False, 'dev_mode': False, 'status_watch': {'enabled': False, 'interval': 300, 'last': 0}, 'webhook': None, 'github_repo': None, 'gh_notify_ch': None, 'github_last': None}
_scheduler: list = []
_managed_tasks: dict = {}
_TASK_STORE: dict = {}
_TRIGGER_STORE: dict = {}
_db = None
_db_path = 'database.db'
_pending_interactions: list = []
_buttons_enabled = False
_modals_enabled = False
_spam_tasks: dict = {}
_proxy = None
_plugins: dict = {}
_sessions: list = []
_session_idx = 0
_cache_auto = False
_latency_history: list = []
_session_events: list = []
_rate_limit_events: list = []
_rate_limit: dict = {}
_cmd_queue: list = []
_auto_reconnect = True
_auto_restart = False
_reconnect_count = 0
_protect_enabled = False
_protect_log_ch = 0
_serverguard_enabled = False
_serverguard_keywords: set = {'child porn', 'cp server', 'csam', 'loli porn', 'shota porn', 'gore server', 'snuff', 'animal abuse', 'zoophilia server', 'drug market', 'hitman', 'terrorism', 'mass shooter', 'ddos server', 'rat server', 'malware server'}
_serverguard_log_ch: int = 0
LOGGER_ENABLED = False
LOG_FILE = 'wilt.log'
LASTFM_BASE = 'http://ws.audioscrobbler.com/2.0/'
HOUSE_IDS = {}
HOUSE_NAMES = {}
_agc_state = {'enabled': False, 'block': False, 'leave_msg': '', 'gc_name': '', 'gc_icon_url': None, 'webhook_url': None}
_agc_whitelist: set = set()
_automod = {'enabled': False, 'words': [], 'action': 'delete', 'log_ch': None}
_raidmode = {'enabled': False, 'threshold': 10}
_quarantine = {'enabled': False, 'role_id': None, 'age_days': 7}
_ticket_cfg = {'category_id': None}
_verify_cfg = {'role_id': None}
_speak_lang = None
neko_gif = None
HOSTED_TOKENS: list = []
_host_sessions: list = []
_hosted_clients: list = []
_live_prefix: list = ['.']

def _clip(text: str, limit: int=None) -> str:
    if limit is None:
        limit = 1900
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:max(0, limit - 3)] + '...'

def _ansi_block(lines) -> str:
    parts = []
    for line in lines or []:
        s = '' if line is None else str(line)
        if not s.strip():
            parts.append('')
        else:
            parts.append(s)
    body = '\n'.join(parts).strip('\n')
    return _clip('```ansi\n' + body + '\n```')

def ui_box(title: str, rows=None, footer: str='') -> str:
    lines = [f'\x1b[35m\x1b[1m{title}\x1b[0m']
    for r in rows or []:
        lines.append(f'\x1b[2;37m{str(r).lstrip()}\x1b[0m')
    if footer:
        lines.append('')
        lines.append(f'\x1b[2m{footer}\x1b[0m')
    return _ansi_block(lines)

def _paginate(title: str, subtitle: str, rows: list, per_page: int=15) -> str:
    header = f'\x1b[1;35m{title}\x1b[0m'
    if subtitle:
        header += f'  \x1b[2;37m{subtitle}\x1b[0m'
    lines = [header, '']
    shown = rows[:per_page]
    for r in shown:
        lines.append(f'\x1b[2;37m{str(r)}\x1b[0m')
    if len(rows) > per_page:
        lines.append('')
        lines.append(f'\x1b[2;37m... and {len(rows) - per_page} more\x1b[0m')
    return _clip(_ansi_block(lines))

async def safe_edit(message, content: str, *, delete_after: float=0.0):
    import asyncio as _asyncio
    try:
        await message.edit(content=content)
    except Exception:
        return
    if delete_after and delete_after > 0:
        async def _later():
            try:
                await _asyncio.sleep(delete_after)
                await message.delete()
            except Exception:
                pass
        try:
            _asyncio.create_task(_later())
        except Exception:
            pass

async def safe_send(channel, content: str, *, delete_after: float=0.0):
    import asyncio as _asyncio
    try:
        msg = await channel.send(content)
    except Exception:
        return None
    if delete_after and delete_after > 0 and msg is not None:
        async def _later():
            try:
                await _asyncio.sleep(delete_after)
                await msg.delete()
            except Exception:
                pass
        try:
            _asyncio.create_task(_later())
        except Exception:
            pass
    return msg

def ui_ok(msg) -> str:
    return _ansi_block([f'\x1b[32mok\x1b[0m  \x1b[2;37m{msg}\x1b[0m'])

def ui_err(msg) -> str:
    return _ansi_block([f'\x1b[31merr\x1b[0m  \x1b[2;37m{msg}\x1b[0m'])

def ui_info(msg) -> str:
    return _ansi_block([f'\x1b[36m|\x1b[0m  \x1b[2;37m{msg}\x1b[0m'])

def ui_warn(msg) -> str:
    return _ansi_block([f'\x1b[33m!\x1b[0m  \x1b[2;37m{msg}\x1b[0m'])

def load_afk():
    return afk if isinstance(afk, dict) else {'on': False, 'message': 'afk', 'since': 0}

def save_afk(data=None):
    global afk
    if data is not None:
        afk = data
    return afk
HOST_PUBLIC = False
OWNER_ID = 0
SPOOF = {}
RPC = {}
DATA = {}

def _get_token(bot=None) -> str:
    tok = TOKEN or ''
    if tok:
        return tok
    _bot = bot or BOT
    if _bot:
        try:
            return _bot.http.token or ''
        except Exception:
            pass
    return ''

def resolve_prefix(bot=None, message=None) -> str:
    p = PREFIX
    if message is not None:
        try:
            gid = str(getattr(message.guild, 'id', '')) if getattr(message, 'guild', None) else ''
            if gid and gid in _server_prefixes:
                p = _server_prefixes[gid]
        except Exception:
            pass
    return p if isinstance(p, str) and p else '.'

def ensure_prefix() -> str:
    global PREFIX
    if not isinstance(PREFIX, str) or not PREFIX:
        PREFIX = '.'
    return PREFIX

def ensure_filters():
    base = {
        'spam': {'enabled': False, 'threshold': 5, 'window': 5, 'history': {}},
        'duplicate': {'enabled': False, 'window': 30, 'history': {}},
        'link': {'enabled': False, 'whitelist': set()},
        'invite': {'enabled': False},
        'attachment': {'enabled': False},
        'nsfw': {'enabled': False, 'keywords': set()},
        'mention_spam': {'enabled': False, 'threshold': 5},
        'mass_ping': {'enabled': False},
        'scam': {'enabled': False},
        'bot': {'enabled': False},
        'webhook': {'enabled': False},
        'auto_purge': {'enabled': False},
        'actions_log': [],
        'log_channel': None,
    }
    if not isinstance(filters, dict):
        return base
    for k, v in base.items():
        if k not in filters:
            filters[k] = v
        elif isinstance(v, dict) and isinstance(filters[k], dict):
            for kk, vv in v.items():
                filters[k].setdefault(kk, vv)
    return filters


async def rate_sleep(resp=None, default=1.5):
    import asyncio, random
    wait = default
    try:
        if resp is not None:
            if hasattr(resp, 'headers') and resp.headers.get('Retry-After'):
                wait = float(resp.headers.get('Retry-After'))
            elif hasattr(resp, 'status') and resp.status == 429:
                try:
                    body = await resp.json()
                    wait = float(body.get('retry_after', wait))
                except Exception:
                    wait = max(default, 2.0)
    except Exception:
        pass
    wait = min(max(wait, 0.35), 45.0)
    wait *= (1.0 + random.uniform(0.05, 0.25))
    await asyncio.sleep(wait)


def api_headers(token=None):
    tok = token or _get_token()
    try:
        from utils.gateway import default_headers, client_properties, encode_super_properties
        props = client_properties()
        if X_SUPER_PROPERTIES:
            try:
                from utils.gateway import decode_super_properties
                decoded = decode_super_properties(X_SUPER_PROPERTIES)
                if decoded:
                    props.update(decoded)
            except Exception:
                pass
        h = default_headers(tok or '', props)
        if X_SUPER_PROPERTIES:
            h['X-Super-Properties'] = X_SUPER_PROPERTIES
        return h
    except Exception:
        pass
    h = {
        'Authorization': tok or '',
        'Content-Type': 'application/json',
        'User-Agent': USER_AGENT,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://discord.com',
        'Referer': 'https://discord.com/channels/@me',
        'X-Discord-Locale': 'en-US',
        'X-Discord-Timezone': 'America/New_York',
    }
    xsp = (X_SUPER_PROPERTIES or '').strip()
    if xsp:
        h['X-Super-Properties'] = xsp
    return h

