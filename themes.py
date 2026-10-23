from __future__ import annotations
import asyncio
import json
import os
import random
from copy import deepcopy
from datetime import datetime
from typing import Optional
import discord
from discord.ext import commands
from . import state as S
ESC = '\x1b'
RESET = f'{ESC}[0m'

def _c(*codes: int) -> str:
    return f"{ESC}[{';'.join((str(c) for c in codes))}m"
_BG: dict[str, str] = {'bg_dark_blue': _c(40), 'bg_orange': _c(41), 'bg_marble_blue': _c(42), 'bg_grey_turquoise': _c(43), 'bg_grey': _c(44), 'bg_indigo': _c(45), 'bg_light_grey': _c(46), 'bg_white': _c(47)}
_FG: dict[str, str] = {'black': _c(30), 'red': _c(31), 'green': _c(32), 'yellow': _c(33), 'blue': _c(34), 'magenta': _c(35), 'cyan': _c(36), 'white': _c(37), 'bright_black': _c(90), 'bright_red': _c(91), 'bright_green': _c(92), 'bright_yellow': _c(93), 'bright_blue': _c(94), 'bright_magenta': _c(95), 'bright_cyan': _c(96), 'bright_white': _c(97), 'dim_white': _c(2, 37), 'dim_cyan': _c(2, 36), 'dim_green': _c(2, 32), 'dim_red': _c(2, 31), 'dim_yellow': _c(2, 33), 'dim_blue': _c(2, 34), 'dim_magenta': _c(2, 35), 'bold_white': _c(1, 37), 'bold_cyan': _c(1, 36), 'bold_green': _c(1, 32), 'bold_red': _c(1, 31), 'bold_yellow': _c(1, 33), 'bold_blue': _c(1, 34), 'bold_magenta': _c(1, 35)}
VALID_SLOTS = ('accent', 'secondary', 'label', 'dim', 'ok', 'warn', 'error', 'info', 'separator', 'header', 'brand', 'bg')
VALID_BG_SLOTS = tuple(_BG.keys())
_SWATCH = '███'
_BUILTIN: dict[str, dict] = {'default': {'accent': 'magenta', 'secondary': 'cyan', 'label': 'dim_white', 'dim': 'dim_white', 'ok': 'green', 'warn': 'yellow', 'error': 'red', 'info': 'cyan', 'separator': 'black', 'header': 'bold_magenta', 'brand': 'bold_magenta', 'desc': 'wilt default - magenta & cyan'}, 'midnight': {'accent': 'blue', 'secondary': 'bright_blue', 'label': 'dim_white', 'dim': 'bright_black', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_blue', 'separator': 'bright_black', 'header': 'bold_blue', 'brand': 'bold_blue', 'desc': 'deep blue night vibes'}, 'forest': {'accent': 'green', 'secondary': 'bright_green', 'label': 'dim_white', 'dim': 'dim_green', 'ok': 'bright_green', 'warn': 'yellow', 'error': 'red', 'info': 'green', 'separator': 'bright_black', 'header': 'bold_green', 'brand': 'bold_green', 'desc': 'lush green terminal'}, 'crimson': {'accent': 'red', 'secondary': 'bright_red', 'label': 'dim_white', 'dim': 'dim_red', 'ok': 'green', 'warn': 'yellow', 'error': 'bright_red', 'info': 'red', 'separator': 'bright_black', 'header': 'bold_red', 'brand': 'bold_red', 'desc': 'blood-red terminal'}, 'ocean': {'accent': 'cyan', 'secondary': 'bright_cyan', 'label': 'dim_white', 'dim': 'dim_cyan', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_cyan', 'separator': 'bright_black', 'header': 'bold_cyan', 'brand': 'bold_cyan', 'desc': 'cool ocean blues'}, 'sunset': {'accent': 'bright_yellow', 'secondary': 'bright_red', 'label': 'dim_white', 'dim': 'dim_yellow', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'yellow', 'separator': 'bright_black', 'header': 'bold_yellow', 'brand': 'bold_yellow', 'desc': 'warm sunset tones'}, 'arctic': {'accent': 'bright_white', 'secondary': 'bright_cyan', 'label': 'dim_white', 'dim': 'dim_white', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_white', 'separator': 'bright_black', 'header': 'bold_white', 'brand': 'bold_white', 'desc': 'ice-cold white & cyan'}, 'neon': {'accent': 'bright_magenta', 'secondary': 'bright_cyan', 'label': 'bright_white', 'dim': 'dim_white', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_cyan', 'separator': 'bright_magenta', 'header': 'bold_magenta', 'brand': 'bold_magenta', 'desc': 'electric neon glow'}, 'void': {'accent': 'bright_black', 'secondary': 'dim_white', 'label': 'dim_white', 'dim': 'bright_black', 'ok': 'green', 'warn': 'yellow', 'error': 'red', 'info': 'dim_white', 'separator': 'bright_black', 'header': 'white', 'brand': 'white', 'desc': 'minimal dark monochrome'}, 'gold': {'accent': 'yellow', 'secondary': 'bright_yellow', 'label': 'dim_white', 'dim': 'dim_yellow', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'yellow', 'separator': 'bright_black', 'header': 'bold_yellow', 'brand': 'bold_yellow', 'desc': 'rich golden terminal'}, 'hacker': {'accent': 'bright_green', 'secondary': 'green', 'label': 'dim_green', 'dim': 'dim_green', 'ok': 'bright_green', 'warn': 'yellow', 'error': 'red', 'info': 'green', 'separator': 'bright_black', 'header': 'bold_green', 'brand': 'bold_green', 'desc': 'matrix hacker green'}, 'sakura': {'accent': 'bright_magenta', 'secondary': 'magenta', 'label': 'dim_white', 'dim': 'dim_magenta', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_magenta', 'separator': 'bright_black', 'header': 'bold_magenta', 'brand': 'bold_magenta', 'desc': 'soft pink blossom'}, 'ember': {'accent': 'bright_red', 'secondary': 'bright_yellow', 'label': 'dim_white', 'dim': 'dim_red', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_red', 'separator': 'bright_black', 'header': 'bold_red', 'brand': 'bold_red', 'desc': 'burning ember red & orange'}, 'stealth': {'accent': 'dim_white', 'secondary': 'white', 'label': 'bright_black', 'dim': 'bright_black', 'ok': 'dim_green', 'warn': 'dim_yellow', 'error': 'dim_red', 'info': 'dim_white', 'separator': 'bright_black', 'header': 'white', 'brand': 'dim_white', 'desc': 'near-invisible stealth mode'}, 'cyberpunk': {'accent': 'bright_yellow', 'secondary': 'bright_magenta', 'label': 'bright_cyan', 'dim': 'dim_white', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_magenta', 'separator': 'bright_black', 'header': 'bold_yellow', 'brand': 'bold_yellow', 'desc': 'cyberpunk yellow & magenta'}, 'dracula': {'accent': 'magenta', 'secondary': 'cyan', 'label': 'dim_white', 'dim': 'bright_black', 'ok': 'green', 'warn': 'yellow', 'error': 'red', 'info': 'cyan', 'separator': 'bright_black', 'header': 'bold_magenta', 'brand': 'bold_magenta', 'desc': 'dracula colour scheme'}, 'monokai': {'accent': 'bright_yellow', 'secondary': 'bright_green', 'label': 'dim_white', 'dim': 'bright_black', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_cyan', 'separator': 'bright_black', 'header': 'bold_yellow', 'brand': 'bold_yellow', 'desc': 'monokai editor theme'}, 'nord': {'accent': 'bright_blue', 'secondary': 'bright_cyan', 'label': 'dim_white', 'dim': 'bright_black', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_blue', 'separator': 'bright_black', 'header': 'bold_blue', 'brand': 'bold_blue', 'desc': 'nord arctic palette'}, 'solarized': {'accent': 'cyan', 'secondary': 'blue', 'label': 'dim_white', 'dim': 'bright_black', 'ok': 'green', 'warn': 'yellow', 'error': 'red', 'info': 'cyan', 'separator': 'bright_black', 'header': 'bold_cyan', 'brand': 'bold_cyan', 'desc': 'solarized classic'}, 'pastel': {'accent': 'magenta', 'secondary': 'bright_blue', 'label': 'dim_white', 'dim': 'dim_white', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_magenta', 'separator': 'bright_black', 'header': 'bold_magenta', 'brand': 'bold_magenta', 'desc': 'soft pastel palette'}, 'matrix': {'accent': 'bright_green', 'secondary': 'green', 'label': 'dim_green', 'dim': 'dim_green', 'ok': 'bright_green', 'warn': 'yellow', 'error': 'red', 'info': 'green', 'separator': 'bright_black', 'header': 'bold_green', 'brand': 'bold_green', 'bg': 'bg_dark_blue', 'desc': 'matrix - green on dark blue bg'}, 'retro': {'accent': 'bright_yellow', 'secondary': 'bright_white', 'label': 'dim_white', 'dim': 'dim_white', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_white', 'separator': 'bright_black', 'header': 'bold_yellow', 'brand': 'bold_yellow', 'bg': 'bg_indigo', 'desc': 'retro amber on indigo bg'}, 'terminal': {'accent': 'bright_white', 'secondary': 'bright_green', 'label': 'dim_white', 'dim': 'dim_white', 'ok': 'bright_green', 'warn': 'bright_yellow', 'error': 'bright_red', 'info': 'bright_white', 'separator': 'bright_black', 'header': 'bold_white', 'brand': 'bold_white', 'bg': 'bg_grey', 'desc': 'classic terminal white on grey bg'}}
_DATA_FILE = 'themes.json'
_DEFAULT_NAME = 'default'

def _load_data() -> dict:
    try:
        if os.path.exists(_DATA_FILE):
            with open(_DATA_FILE, encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {'active': _DEFAULT_NAME, 'custom': {}}

def _save_data(data: dict):
    try:
        with open(_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f'[themes] save error: {e}')

def _all_themes(custom: dict) -> dict:
    merged = dict(_BUILTIN)
    merged.update(custom)
    return merged

def _resolve(name: str, custom: dict) -> Optional[dict]:
    return _all_themes(custom).get(name.lower())

def _colour(val: str) -> str:
    return _FG.get(val) or _BG.get(val) or _FG['dim_white']

def _bg_colour(theme: dict) -> str:
    bg = theme.get("bg", "")
    return _BG.get(bg, '') if bg else ''

def _apply_to_state(theme: dict):
    S.GREEN = _colour(theme.get("ok", "green"))
    S.RED = _colour(theme.get("error", "red"))
    S.YELLOW = _colour(theme.get("warn", "yellow"))
    S.CYAN = _colour(theme.get("info", "cyan"))
    S.BRAND = _colour(theme.get("brand", "bold_magenta"))
    S.DIM = _colour(theme.get("dim", "dim_white"))
    S.DARK = _colour(theme.get("separator", "black"))
    S.GREY = _colour(theme.get("label", "dim_white"))
    S.RESET = RESET
    try:
        S.CYAN2 = _colour(theme.get("secondary", "cyan"))
    except Exception:
        pass
    S.BG = _bg_colour(theme)
    _patch_ui(theme)

def _patch_ui(theme: dict):
    ok_c = _colour(theme.get("ok", "green"))
    err_c = _colour(theme.get("error", "red"))
    warn_c = _colour(theme.get("warn", "yellow"))
    info_c = _colour(theme.get("info", "cyan"))
    acc_c = _colour(theme.get("accent", "magenta"))
    dim = _colour(theme.get("dim", "dim_white"))
    brand = _colour(theme.get("brand", "bold_magenta"))

    def _blk(line: str) -> str:
        t = line if len(line) <= 1900 else line[:1897] + '...'
        return f'```ansi\n{t}\n```'
    bg = _bg_colour(theme)

    def _ansi_block_themed(lines) -> str:
        parts = ['' if l is None or not str(l).strip() else str(l) for l in lines or []]
        body = '\n'.join(parts).strip('\n')
        if bg:
            body = '\n'.join((bg + l + RESET if l.strip() else l for l in body.split('\n')))
        raw = f'```ansi\n{body}\n```'
        return raw if len(raw) <= 1900 else raw[:1897] + '```'
    S.ui_ok = lambda msg: _blk(f'{ok_c}ok{RESET}  {dim}{msg}{RESET}')
    S.ui_err = lambda msg: _blk(f'{err_c}err{RESET}  {dim}{msg}{RESET}')
    S.ui_warn = lambda msg: _blk(f'{warn_c}!{RESET}  {dim}{msg}{RESET}')
    S.ui_info = lambda msg: _blk(f'{info_c}|{RESET}  {dim}{msg}{RESET}')

    def _ui_box_themed(title: str, rows=None, footer: str='') -> str:
        ls = [f'{brand}{title}{RESET}']
        for r in rows or []:
            ls.append(f'{dim}{str(r).lstrip()}{RESET}')
        if footer:
            ls += ['', f'{dim}{footer}{RESET}']
        return _ansi_block_themed(ls)
    S.ui_box = _ui_box_themed

    def _paginate_themed(title: str, subtitle: str, rows: list, per_page: int=20) -> str:
        header = f'{acc_c}{title}{RESET}'
        if subtitle:
            header += f'  {dim}{subtitle}{RESET}'
        ls = [header, '']
        for r in rows[:per_page]:
            ls.append(f'{dim}{str(r)}{RESET}')
        if len(rows) > per_page:
            ls += ['', f'{dim}... and {len(rows) - per_page} more{RESET}']
        raw = _ansi_block_themed(ls)
        return raw if len(raw) <= 1900 else raw[:1897] + '```'
    S._paginate = _paginate_themed

def _palette(theme: dict) -> str:
    slots = ('accent', 'secondary', 'ok', 'warn', 'error', 'info', 'header')
    parts = [f"{_colour(theme.get(s, 'dim_white'))}{_SWATCH}{RESET}" for s in slots]
    bg = _bg_colour(theme)
    if bg:
        parts.append(f'{bg}  bg  {RESET}')
    return '  '.join(parts)

def _theme_card(name: str, theme: dict, active: str) -> str:
    hdr = _colour(theme.get("header", "bold_magenta"))
    acc = _colour(theme.get("accent", "magenta"))
    dim = _colour(theme.get("dim", "dim_white"))
    ok = _colour(theme.get("ok", "green"))
    warn = _colour(theme.get("warn", "yellow"))
    err = _colour(theme.get("error", "red"))
    info = _colour(theme.get("info", "cyan"))
    sec = _colour(theme.get("secondary", "cyan"))
    mark = f'  {ok}✓ active{RESET}' if name == active else ''
    desc = theme.get("desc", "")
    lines = [f'{hdr}{name}{RESET}{mark}', f'{dim}{desc}{RESET}' if desc else None, f'{dim}palette{RESET}  {_palette(theme)}', f'{dim}slots  {RESET}  {ok}ok{RESET}  {warn}warn{RESET}  {err}err{RESET}  {info}info{RESET}  {acc}accent{RESET}  {sec}secondary{RESET}']
    return '\n'.join((l for l in lines if l is not None))

def _truncate(s: str, limit: int=1990) -> str:
    return s if len(s) <= limit else s[:limit - 3] + '```'

class ThemesCog(commands.Cog, name='themes'):

    def __init__(self, bot):
        self.bot = bot
        self._data = _load_data()
        _apply_to_state(self._active_theme())

    def _save(self):
        _save_data(self._data)

    def _custom(self) -> dict:
        return self._data.setdefault('custom', {})

    def _active_name(self) -> str:
        return self._data.get('active', _DEFAULT_NAME)

    def _all(self) -> dict:
        return _all_themes(self._custom())

    def _active_theme(self) -> dict:
        return _resolve(self._active_name(), self._custom()) or _BUILTIN[_DEFAULT_NAME]

    def _get(self, name: str) -> Optional[dict]:
        return _resolve(name.lower(), self._custom())

    def _apply(self, name: str):
        self._data['active'] = name
        self._save()
        _apply_to_state(self._active_theme())

    @staticmethod
    def _pad(labels: list) -> int:
        return max((len(l) for l in labels), default=0) + 2

    @commands.command(name='theme', brief='Show active theme or apply one  .theme [name]')
    async def theme_cmd(self, ctx, name: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not name:
            t = self._active_theme()
            aname = self._active_name()
            hdr = _colour(t.get("header", "bold_magenta"))
            acc = _colour(t.get("accent", "magenta"))
            dim = _colour(t.get("dim", "dim_white"))
            sep = _colour(t.get("separator", "black"))
            lbl = _colour(t.get("label", "dim_white"))
            lines = [f'{hdr}active theme: {acc}{aname}{RESET}', f'{dim}{t.get("desc", "")}{RESET}', '', f'{dim}palette{RESET}  {_palette(t)}', '']
            for slot in VALID_SLOTS:
                val = t.get(slot, '-')
                c = _colour(val)
                lines.append(f'{lbl}{slot:<12}{RESET}  {sep}|{RESET}  {c}{_SWATCH}  {val}{RESET}')
            pfx = S.PREFIX
            lines += ['', f'{dim}{pfx}themes  |  {pfx}theme <name>  |  {pfx}themecustom{RESET}']
            return await S.safe_send(ctx.channel, _truncate(f'```ansi\n' + '\n'.join(lines) + '\n```'))
        name = name.lower()
        t = self._get(name)
        if t is None:
            return await S.safe_send(ctx.channel, S.ui_err(f"theme '{name}' not found - .themes to list"))
        self._apply(name)
        acc = _colour(t.get("accent", "magenta"))
        await S.safe_send(ctx.channel, S.ui_ok(f'theme → {acc}{name}{RESET}  {t.get("desc", "")}'))

    @commands.command(name='themes', brief='List all themes with palette previews')
    async def themes_list(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        all_t = self._all()
        active = self._active_name()
        custom_k = set(self._custom().keys())
        pfx = S.PREFIX
        header = f'```ansi\n\x1b[1;37mthemes\x1b[0m  \x1b[2;37m{len(all_t)} total  |  {len(_BUILTIN)} built-in  |  {len(custom_k)} custom\x1b[0m\n\x1b[2;37m{pfx}theme <name> to apply  |  active: \x1b[0m\x1b[1;35m{active}\x1b[0m\n```'
        await S.safe_send(ctx.channel, header)
        await asyncio.sleep(0.2)
        names = list(all_t.keys())
        pages: list[list[str]] = []
        batch: list[str] = []
        blen = 0
        for n in names:
            t = all_t[n]
            tag = ' [custom]' if n in custom_k else ''
            card = _theme_card(n + tag, t, active)
            cl = len(card) + 2
            if batch and blen + cl > 1750:
                pages.append(batch)
                batch = []
                blen = 0
            batch.append(card)
            blen += cl
        if batch:
            pages.append(batch)
        for i, page in enumerate(pages):
            body = '\n\n'.join(page)
            out = _truncate(f'```ansi\n{body}\n```')
            await S.safe_send(ctx.channel, out)
            if i < len(pages) - 1:
                await asyncio.sleep(0.4)

    @commands.command(name='themepreview', aliases=['tp'], brief='Preview theme without applying  .themepreview <name>')
    async def themepreview(self, ctx, name: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not name:
            return await S.safe_send(ctx.channel, S.ui_err('usage: themepreview <name>'))
        t = self._get(name.lower())
        if t is None:
            return await S.safe_send(ctx.channel, S.ui_err(f"theme '{name}' not found"))
        hdr = _colour(t.get("header", "bold_magenta"))
        acc = _colour(t.get("accent", "magenta"))
        dim = _colour(t.get("dim", "dim_white"))
        ok = _colour(t.get("ok", "green"))
        warn = _colour(t.get("warn", "yellow"))
        err = _colour(t.get("error", "red"))
        info = _colour(t.get("info", "cyan"))
        sec = _colour(t.get("secondary", "cyan"))
        sep = _colour(t.get("separator", "black"))
        lbl = _colour(t.get("label", "dim_white"))
        lines = [f'{hdr}preview: {acc}{name.lower()}{RESET}', f'{dim}{t.get("desc", "custom theme")}{RESET}', '', f'{dim}palette{RESET}  {_palette(t)}', '', f'{ok}ok{RESET}      {dim}operation succeeded{RESET}', f'{warn}warn{RESET}    {dim}something to watch{RESET}', f'{err}error{RESET}   {dim}something went wrong{RESET}', f'{info}info{RESET}    {dim}neutral information{RESET}', f'{acc}accent{RESET}  {dim}primary highlight{RESET}', f'{sec}second{RESET}  {dim}secondary highlight{RESET}', '', f'{lbl}Label      {sep}|{RESET}  {sec}value{RESET}', f'{lbl}Status     {sep}|{RESET}  {ok}running{RESET}', f'{lbl}Uptime     {sep}|{RESET}  {acc}12h 34m{RESET}']
        await S.safe_send(ctx.channel, _truncate(f'```ansi\n' + '\n'.join(lines) + '\n```'))

    @commands.command(name='themetest', aliases=['themetoggle'], brief='Full ANSI showcase of active theme')
    async def themetest(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        t = self._active_theme()
        name = self._active_name()
        hdr = _colour(t.get("header", "bold_magenta"))
        acc = _colour(t.get("accent", "magenta"))
        dim = _colour(t.get("dim", "dim_white"))
        ok = _colour(t.get("ok", "green"))
        warn = _colour(t.get("warn", "yellow"))
        err = _colour(t.get("error", "red"))
        info = _colour(t.get("info", "cyan"))
        sec = _colour(t.get("secondary", "cyan"))
        sep = _colour(t.get("separator", "black"))
        lbl = _colour(t.get("label", "dim_white"))
        brand = _colour(t.get("brand", "bold_magenta"))
        lines = [f'{brand}wilt selfbot{RESET}  {dim}v3.0.x{RESET}', f'{lbl}Status     {sep}|{RESET}  {ok}online{RESET}', f'{lbl}Uptime     {sep}|{RESET}  {acc}12h 34m 56s{RESET}', f'{lbl}Ping       {sep}|{RESET}  {sec}42ms{RESET}', f'{lbl}Prefix     {sep}|{RESET}  {acc}{S.PREFIX}{RESET}', '', f'{ok}ok{RESET}     operation succeeded', f'{warn}warn{RESET}   rate limit approaching', f'{err}error{RESET}  token invalid', f'{info}info{RESET}   fetching quest data', '', _palette(t), '']
        for slot in VALID_SLOTS:
            val = t.get(slot, '-')
            c = _colour(val)
            lines.append(f'{lbl}{slot:<12}{RESET}  {c}{_SWATCH}  {val}{RESET}')
        await S.safe_send(ctx.channel, _truncate(f'```ansi\n' + '\n'.join(lines) + '\n```'))

    @commands.command(name='themecolours', aliases=['themecolors', 'tcolours', 'tcolors'], brief='List all valid colour names with swatches')
    async def themecolours(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        bold = '\x1b[1;37m'
        lines = [f'{bold}valid colour names{RESET}', '']
        for name, esc in sorted(_FG.items()):
            lines.append(f'{esc}{_SWATCH}  {name}{RESET}')
        body = '\n'.join(lines)
        out = f'```ansi\n{body}\n```'
        if len(out) <= 1990:
            return await S.safe_send(ctx.channel, out)
        half = len(lines) // 2
        for chunk in (lines[:half], lines[half:]):
            await S.safe_send(ctx.channel, f'```ansi\n' + '\n'.join(chunk) + '\n```')
            await asyncio.sleep(0.3)

    @commands.command(name='themecustom', aliases=['tc'], brief='Create / edit a custom theme  .themecustom <name> slot=colour ...')
    async def themecustom(self, ctx, name: str='', *, pairs: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        pfx = S.PREFIX
        if not name:
            return await ctx.channel.send(S.ui_info(f"usage: {pfx}themecustom <name> slot=colour ...\nslots: {' '.join(VALID_SLOTS)}\nrun {pfx}themecolours to see all colours"))
        name = name.lower()
        if name in _BUILTIN:
            return await S.safe_send(ctx.channel, S.ui_err(f"'{name}' is built-in - pick a different name"))
        base = deepcopy(self._custom().get(name) or dict(_BUILTIN[_DEFAULT_NAME]))
        base.pop('desc', None)
        errs: list[str] = []
        applied = 0
        for token in (pairs or '').split():
            if '=' not in token:
                errs.append(f"skip '{token}' (no '=')")
                continue
            slot, val = token.split('=', 1)
            slot = slot.strip().lower()
            val = val.strip().lower()
            if slot not in VALID_SLOTS:
                errs.append(f"unknown slot '{slot}'")
                continue
            if val not in _FG:
                errs.append(f"unknown colour '{val}'")
                continue
            base[slot] = val
            applied += 1
        base['desc'] = f'custom: {name}'
        self._custom()[name] = base
        self._save()
        acc = _colour(base.get("accent", "magenta"))
        msg = f"theme '{acc}{name}{RESET}' saved - {applied} slot(s) set"
        if errs:
            msg += '\nwarnings: ' + '  '.join(errs)
        await S.safe_send(ctx.channel, S.ui_ok(msg))

    @commands.command(name='themeimport', brief='Import a theme from JSON  .themeimport <json>')
    async def themeimport(self, ctx, *, raw: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not raw:
            return await S.safe_send(ctx.channel, S.ui_err('usage: themeimport <json>'))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return await S.safe_send(ctx.channel, S.ui_err(f'invalid JSON: {e}'))
        if not isinstance(data, dict):
            return await S.safe_send(ctx.channel, S.ui_err('expected a JSON object'))
        name = str(data.pop('name', 'imported')).lower().replace(' ', '_')
        if name in _BUILTIN:
            name += '_custom'
        bad: list[str] = []
        clean: dict = {}
        for k, v in data.items():
            if k == 'desc':
                clean['desc'] = str(v)
                continue
            if k not in VALID_SLOTS:
                bad.append(k)
                continue
            if v not in _FG:
                bad.append(f'{k}={v}')
                continue
            clean[k] = v
        if not any((k in clean for k in VALID_SLOTS)):
            return await S.safe_send(ctx.channel, S.ui_err('no valid slots in JSON'))
        self._custom()[name] = clean
        self._save()
        acc = _colour(clean.get("accent", "magenta"))
        msg = f"imported '{acc}{name}{RESET}'"
        if bad:
            msg += f"  (skipped: {', '.join(bad)})"
        await S.safe_send(ctx.channel, S.ui_ok(msg))

    @commands.command(name='themeexport', aliases=['te'], brief='Export a theme as JSON  .themeexport [name]')
    async def themeexport(self, ctx, name: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        tname = name.lower() if name else self._active_name()
        t = self._get(tname)
        if t is None:
            return await S.safe_send(ctx.channel, S.ui_err(f"theme '{tname}' not found"))
        raw = json.dumps({'name': tname, **t}, indent=2)
        out = f'```json\n{raw}\n```'
        if len(out) > 1990:
            out = f'```json\n{raw[:1980]}\n... (truncated)\n```'
        await S.safe_send(ctx.channel, out)

    @commands.command(name='themereset', brief='Reset to default theme')
    async def themereset(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        self._apply(_DEFAULT_NAME)
        await S.safe_send(ctx.channel, S.ui_ok('theme reset to default'))

    @commands.command(name='themesave', brief='Snapshot active theme  .themesave <name>')
    async def themesave(self, ctx, name: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not name:
            return await S.safe_send(ctx.channel, S.ui_err('usage: themesave <name>'))
        name = name.lower()
        if name in _BUILTIN:
            return await S.safe_send(ctx.channel, S.ui_err(f"'{name}' is built-in - pick another name"))
        snap = deepcopy(self._active_theme())
        snap['desc'] = f'saved from {self._active_name()}'
        self._custom()[name] = snap
        self._save()
        acc = _colour(snap.get("accent", "magenta"))
        await S.safe_send(ctx.channel, S.ui_ok(f"saved active theme as '{acc}{name}{RESET}'"))

    @commands.command(name='themedelete', aliases=['tdelete', 'td'], brief='Delete a custom theme  .themedelete <name>')
    async def themedelete(self, ctx, name: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not name:
            return await S.safe_send(ctx.channel, S.ui_err('usage: themedelete <name>'))
        name = name.lower()
        if name in _BUILTIN:
            return await S.safe_send(ctx.channel, S.ui_err(f"cannot delete built-in '{name}'"))
        if name not in self._custom():
            return await S.safe_send(ctx.channel, S.ui_err(f"custom theme '{name}' not found"))
        del self._custom()[name]
        if self._active_name() == name:
            self._apply(_DEFAULT_NAME)
        else:
            self._save()
        await S.safe_send(ctx.channel, S.ui_ok(f"deleted theme '{name}'"))

    @commands.command(name='themeinfo', aliases=['tinfo'], brief='Full slot table for any theme  .themeinfo [name]')
    async def themeinfo(self, ctx, name: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        tname = name.lower() if name else self._active_name()
        t = self._get(tname)
        if t is None:
            return await S.safe_send(ctx.channel, S.ui_err(f"theme '{tname}' not found"))
        hdr = _colour(t.get("header", "bold_magenta"))
        acc = _colour(t.get("accent", "magenta"))
        dim = _colour(t.get("dim", "dim_white"))
        sep = _colour(t.get("separator", "black"))
        lbl = _colour(t.get("label", "dim_white"))
        tag = 'custom' if tname in self._custom() else 'built-in'
        lines = [f'{hdr}theme info: {acc}{tname}{RESET}  {dim}[{tag}]{RESET}', f'{dim}{t.get("desc", "")}{RESET}', '', f'{dim}palette{RESET}  {_palette(t)}', '']
        for slot in VALID_SLOTS:
            val = t.get(slot, '-')
            c = _colour(val)
            lines.append(f'{lbl}{slot:<12}{RESET}  {sep}|{RESET}  {c}{_SWATCH}  {val}{RESET}')
        await S.safe_send(ctx.channel, _truncate(f'```ansi\n' + '\n'.join(lines) + '\n```'))

    @commands.command(name='themecopy', aliases=['tcopy'], brief='Copy a theme to a new name  .themecopy <src> <dst>')
    async def themecopy(self, ctx, src: str='', dst: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not src or not dst:
            return await S.safe_send(ctx.channel, S.ui_err('usage: themecopy <src> <dst>'))
        src = src.lower()
        dst = dst.lower()
        t = self._get(src)
        if t is None:
            return await S.safe_send(ctx.channel, S.ui_err(f"theme '{src}' not found"))
        if dst in _BUILTIN:
            return await S.safe_send(ctx.channel, S.ui_err(f"'{dst}' is a built-in name"))
        copy = deepcopy(t)
        copy['desc'] = f'copy of {src}'
        self._custom()[dst] = copy
        self._save()
        acc = _colour(copy.get("accent", "magenta"))
        await S.safe_send(ctx.channel, S.ui_ok(f"copied '{src}' → '{acc}{dst}{RESET}'"))

    @commands.command(name='themerand', aliases=['themereload'], brief='Apply a random built-in theme')
    async def themerand(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        pick = random.choice(list(_BUILTIN.keys()))
        self._apply(pick)
        t = _BUILTIN[pick]
        acc = _colour(t.get("accent", "magenta"))
        await S.safe_send(ctx.channel, S.ui_ok(f'random theme → {acc}{pick}{RESET}  {t.get("desc", "")}'))

    @commands.command(name='themegradient', aliases=['tgrad'], brief='One-line palette strip for every built-in theme')
    async def themegradient(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        lines = []
        for name, t in _BUILTIN.items():
            acc = _colour(t.get("accent", "magenta"))
            pal = _palette(t)
            desc = t.get("desc", "")
            lines.append(f'{acc}{name:<14}{RESET}  {pal}  \x1b[2;37m{desc}\x1b[0m')
        for i in range(0, len(lines), 10):
            chunk = lines[i:i + 10]
            out = f'```ansi\n' + '\n'.join(chunk) + '\n```'
            await S.safe_send(ctx.channel, out)
            if i + 10 < len(lines):
                await asyncio.sleep(0.35)

    @commands.command(name='themebg', aliases=['tbg'], brief='Set background colour for active theme  .themebg <bg_name|off>')
    async def themebg(self, ctx, bg: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        pfx = S.PREFIX
        if not bg:
            t = self._active_theme()
            cur = t.get("bg", "")
            bg_c = _BG.get(cur, '')
            rows = [f"  current   {bg_c}{cur or 'none'}{RESET}", '', '  valid background names:'] + [f'    {_BG[n]}  {n}  {RESET}' for n in sorted(_BG.keys())]
            hdr = _colour(t.get("header", "bold_magenta"))
            out = f'```ansi\n{hdr}background slot{RESET}\n' + '\n'.join(rows) + '\n```'
            return await S.safe_send(ctx.channel, _truncate(out))
        if bg.lower() in ('off', 'none', 'clear', 'remove'):
            t = self._active_theme()
            t.pop('bg', None)
            aname = self._active_name()
            if aname in self._custom():
                self._custom()[aname] = t
            self._save()
            _apply_to_state(t)
            return await S.safe_send(ctx.channel, S.ui_ok('background removed from active theme'))
        bg = bg.lower()
        if bg not in _BG:
            valid = '  '.join(sorted(_BG.keys()))
            return await S.safe_send(ctx.channel, S.ui_err(f"unknown bg '{bg}'\nvalid: {valid}"))
        aname = self._active_name()
        if aname in _BUILTIN:
            t = deepcopy(_BUILTIN[aname])
            t['bg'] = bg
            t['desc'] = f'{aname} + {bg}'
            new_name = f'{aname}_bg'
            self._custom()[new_name] = t
            self._data['active'] = new_name
        else:
            t = self._active_theme()
            t['bg'] = bg
            self._custom()[aname] = t
        self._save()
        _apply_to_state(self._active_theme())
        bg_c = _BG[bg]
        await ctx.channel.send(S.ui_ok(f"background → {bg_c}  {bg}  {RESET} on theme '{self._active_name()}'"))

    @commands.command(name='themeapply', aliases=['ta'], brief='Apply a theme by name  .themeapply <name>')
    async def themeapply(self, ctx, name: str=''):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not name:
            return await S.safe_send(ctx.channel, S.ui_err('usage: themeapply <name>'))
        name = name.lower()
        t = self._get(name)
        if t is None:
            return await S.safe_send(ctx.channel, S.ui_err(f"theme '{name}' not found - .themes to list"))
        self._apply(name)
        acc = _colour(t.get("accent", "magenta"))
        await S.safe_send(ctx.channel, S.ui_ok(f'theme applied: {acc}{name}{RESET}  {t.get("desc", "")}'))

async def setup(bot):
    await bot.add_cog(ThemesCog(bot))
