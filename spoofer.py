
import asyncio
import base64
import json
import time

import discord
from discord.ext import commands

from . import state as S

PLATFORM_PRESETS = {
    "desktop": {
        "os": "Windows", "browser": "Discord Client", "device": "",
        "label": "Windows Desktop",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9262 Chrome/155.0.0.0 Electron/36.0.0 Safari/537.36",
        "browser_version": "1.0.9262", "os_version": "10.0.22631",
        "client_build_number": 630444, "release_channel": "stable",
    },
    "windows": {
        "os": "Windows", "browser": "Discord Client", "device": "",
        "label": "Windows Desktop",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9262 Chrome/155.0.0.0 Electron/36.0.0 Safari/537.36",
        "browser_version": "1.0.9262", "os_version": "10.0.22631",
        "client_build_number": 630444, "release_channel": "stable",
    },
    "macos": {
        "os": "Mac OS X", "browser": "Discord Client", "device": "",
        "label": "macOS Desktop",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9262 Chrome/155.0.0.0 Electron/36.0.0 Safari/537.36",
        "browser_version": "1.0.9262", "os_version": "14.5.0",
        "client_build_number": 630444, "release_channel": "stable",
    },
    "linux": {
        "os": "Linux", "browser": "Discord Client", "device": "",
        "label": "Linux Desktop",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9262 Chrome/155.0.0.0 Electron/36.0.0 Safari/537.36",
        "browser_version": "1.0.9262", "os_version": "6.8.0",
        "client_build_number": 630444, "release_channel": "stable",
    },
    "web": {
        "os": "Windows", "browser": "Discord Web", "device": "",
        "label": "Web",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
        "browser_version": "155.0.0.0", "os_version": "10",
        "client_build_number": 630444, "release_channel": "stable",
    },
    "browser": {
        "os": "Windows", "browser": "Discord Web", "device": "",
        "label": "Web",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
        "browser_version": "155.0.0.0", "os_version": "10",
        "client_build_number": 630444, "release_channel": "stable",
    },
    "mobile": {
        "os": "Android", "browser": "Discord Android", "device": "Pixel 8",
        "label": "Android",
        "system_locale": "en-US",
        "browser_user_agent": "Discord-Android/349.9;ROM:14;Device:Pixel 8",
        "browser_version": "349.9", "os_version": "14",
        "client_build_number": 349009, "release_channel": "stable",
    },
    "android": {
        "os": "Android", "browser": "Discord Android", "device": "Pixel 8",
        "label": "Android",
        "system_locale": "en-US",
        "browser_user_agent": "Discord-Android/349.9;ROM:14;Device:Pixel 8",
        "browser_version": "349.9", "os_version": "14",
        "client_build_number": 349009, "release_channel": "stable",
    },
    "phone": {
        "os": "Android", "browser": "Discord Android", "device": "Pixel 8",
        "label": "Phone",
        "system_locale": "en-US",
        "browser_user_agent": "Discord-Android/349.9;ROM:14;Device:Pixel 8",
        "browser_version": "349.9", "os_version": "14",
        "client_build_number": 349009, "release_channel": "stable",
    },
    "ios": {
        "os": "iOS", "browser": "Discord iOS", "device": "iPhone16,2",
        "label": "iOS",
        "system_locale": "en-US",
        "browser_user_agent": "Discord/349.0 CFNetwork/1490 Darwin/23.6.0",
        "browser_version": "349.0", "os_version": "18.0",
        "client_build_number": 349000, "release_channel": "stable",
    },
    "iphone": {
        "os": "iOS", "browser": "Discord iOS", "device": "iPhone16,2",
        "label": "iPhone",
        "system_locale": "en-US",
        "browser_user_agent": "Discord/349.0 CFNetwork/1490 Darwin/23.6.0",
        "browser_version": "349.0", "os_version": "18.0",
        "client_build_number": 349000, "release_channel": "stable",
    },
    "ipad": {
        "os": "iOS", "browser": "Discord iOS", "device": "iPad13,4",
        "label": "iPad",
        "system_locale": "en-US",
        "browser_user_agent": "Discord/349.0 CFNetwork/1490 Darwin/23.6.0",
        "browser_version": "349.0", "os_version": "18.0",
        "client_build_number": 349000, "release_channel": "stable",
    },
    "vr": {
        "os": "Console", "browser": "Discord VR", "device": "Meta Quest 3",
        "label": "Discord VR",
        "system_locale": "en-US",
        "browser_user_agent": "DiscordVR/23.7.91",
        "browser_version": "23.7.91", "os_version": "10.0.45",
        "client_build_number": 230791, "release_channel": "stable",
    },
    "quest": {
        "os": "Console", "browser": "Discord VR", "device": "Meta Quest 3",
        "label": "Meta Quest",
        "system_locale": "en-US",
        "browser_user_agent": "DiscordVR/23.7.91",
        "browser_version": "23.7.91", "os_version": "10.0.45",
        "client_build_number": 230791, "release_channel": "stable",
    },
    "quest2": {
        "os": "Console", "browser": "Discord VR", "device": "Meta Quest 2",
        "label": "Meta Quest 2",
        "system_locale": "en-US",
        "browser_user_agent": "DiscordVR/23.7.91",
        "browser_version": "23.7.91", "os_version": "10.0.45",
        "client_build_number": 230791, "release_channel": "stable",
    },
    "quest3": {
        "os": "Console", "browser": "Discord VR", "device": "Meta Quest 3",
        "label": "Meta Quest 3",
        "system_locale": "en-US",
        "browser_user_agent": "DiscordVR/23.7.91",
        "browser_version": "23.7.91", "os_version": "10.0.45",
        "client_build_number": 230791, "release_channel": "stable",
    },
    "xbox": {
        "os": "Console", "browser": "Discord Embedded", "device": "Xbox Series X",
        "label": "Xbox",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Xbox; Xbox Series X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2486.0 Safari/537.36 Edge/13.10586",
        "browser_version": "", "os_version": "",
        "client_build_number": 1, "release_channel": "stable",
    },
    "playstation": {
        "os": "Console", "browser": "Discord Embedded", "device": "PlayStation 5",
        "label": "PlayStation",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (PlayStation 5 3.11) AppleWebKit/605.1.15 (KHTML, like Gecko)",
        "browser_version": "", "os_version": "",
        "client_build_number": 1, "release_channel": "stable",
    },
    "ps": {
        "os": "Console", "browser": "Discord Embedded", "device": "PlayStation 5",
        "label": "PlayStation",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (PlayStation 5 3.11) AppleWebKit/605.1.15 (KHTML, like Gecko)",
        "browser_version": "", "os_version": "",
        "client_build_number": 1, "release_channel": "stable",
    },
    "console": {
        "os": "Console", "browser": "Discord Embedded", "device": "Xbox Series X",
        "label": "Console",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Xbox; Xbox Series X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2486.0 Safari/537.36 Edge/13.10586",
        "browser_version": "", "os_version": "",
        "client_build_number": 1, "release_channel": "stable",
    },
}

_POOL = {"last": None, "forced_props": None, "key": "desktop", "sessions": []}
_STATS = {"identifies": 0, "reconnects": 0}
_COG = [None]


def _full_props(preset):
    p = dict(preset)
    p.pop("label", None)
    p.setdefault("referrer", "")
    p.setdefault("referring_domain", "")
    p.setdefault("referrer_current", "")
    p.setdefault("referring_domain_current", "")
    p.setdefault("client_event_source", None)
    p.setdefault("has_client_mods", False)
    p.setdefault("client_app_state", "focused")
    return p


_props_from_preset = _full_props


def _arm(key):
    key = (key or "desktop").lower().strip()
    aliases = {
        "pc": "desktop", "win": "desktop", "mac": "macos", "chrome": "web",
        "phone": "mobile", "iphone": "ios", "q3": "quest3", "q2": "quest2",
        "ps5": "playstation", "ps4": "playstation",
    }
    key = aliases.get(key, key)
    preset = PLATFORM_PRESETS.get(key)
    if not preset:
        return None, None
    props = _full_props(preset)
    _POOL["last"] = preset
    _POOL["forced_props"] = props
    _POOL["key"] = key
    try:
        from discord.gateway import DiscordWebSocket as WS
        WS._wilt_fixed_props = props
    except Exception:
        pass
    return key, props


def _inject(data):
    if not isinstance(data, dict) or data.get("op") not in (2, "2"):
        return data
    props = _POOL.get("forced_props")
    if not props:
        return data
    d = dict(data.get("d") or {})
    d["properties"] = dict(props)
    d["client_properties"] = dict(props)
    out = dict(data)
    out["d"] = d
    _STATS["identifies"] += 1
    print(
        "[spoofer] IDENTIFY → browser=%s os=%s device=%s"
        % (props.get("browser"), props.get("os"), props.get("device") or "-")
    )
    return out


def _stamp(bot, props):
    if not bot or not props:
        return
    try:
        for attr in ("gateway_properties", "_gateway_properties"):
            if hasattr(bot, attr) or True:
                try:
                    setattr(bot, attr, dict(props))
                except Exception:
                    pass
        conn = getattr(bot, "_connection", None)
        if conn is not None:
            for attr in ("_client_properties", "client_properties", "gateway_properties"):
                try:
                    setattr(conn, attr, dict(props))
                except Exception:
                    pass
        http = getattr(bot, "http", None)
        if http is None:
            return
        ua = props.get("browser_user_agent")
        xsp = base64.b64encode(json.dumps(props, separators=(",", ":")).encode()).decode()
        if hasattr(http, "headers") and isinstance(http.headers, dict):
            if ua:
                http.headers["User-Agent"] = ua
            http.headers["X-Super-Properties"] = xsp
        for attr, val in (
            ("_super_properties", props),
            ("super_properties", props),
            ("encoded_super_properties", xsp),
            ("user_agent", ua),
        ):
            if hasattr(http, attr):
                try:
                    setattr(http, attr, val)
                except Exception:
                    pass
    except Exception as e:
        print("[spoofer] stamp:", e)


def _install():
    try:
        from discord.gateway import DiscordWebSocket as WS
    except Exception as e:
        print("[spoofer] no WS:", e)
        return False

    if not getattr(WS, "_wilt_spoof_identify_v4", False):
        orig_identify = getattr(WS, "identify", None)

        async def _identify(self, *a, **k):
            props = _POOL.get("forced_props")
            if props is None:
                if orig_identify is not None:
                    return await orig_identify(self, *a, **k)
                return
            for attr in ("_client_properties", "client_properties"):
                try:
                    setattr(self, attr, dict(props))
                except Exception:
                    pass
            token = getattr(self, "token", None)
            if not token:
                conn = getattr(self, "_connection", None)
                token = getattr(conn, "token", None) if conn else None
            if not token and hasattr(self, "credentials"):
                token = getattr(self.credentials, "token", None)
            if orig_identify is not None:
                return await orig_identify(self, *a, **k)

        try:
            WS.identify = _identify
            WS._wilt_spoof_identify_v4 = True
            print("[spoofer] identify wrapper v4")
        except Exception as e:
            print("[spoofer] identify wrap fail:", e)

    for meth in ("send_as_json", "send_json"):
        flag = "_wilt_spoof_%s_v4" % meth
        if getattr(WS, flag, False):
            continue
        orig = getattr(WS, meth, None)
        if orig is None:
            continue

        def _make(o):
            async def _w(self, data, *a, **k):
                try:
                    data = _inject(data)
                except Exception:
                    pass
                return await o(self, data, *a, **k)

            return _w

        try:
            setattr(WS, meth, _make(orig))
            setattr(WS, flag, True)
            print("[spoofer] patched %s" % meth)
        except Exception as e:
            print("[spoofer] patch %s: %s" % (meth, e))
    return True


def _wipe(bot):
    targets = []
    for name in ("ws", "_connection"):
        o = getattr(bot, name, None)
        if o is not None:
            targets.append(o)
    conn = getattr(bot, "_connection", None)
    if conn is not None:
        for sub in ("ws", "_ws"):
            o = getattr(conn, sub, None)
            if o is not None:
                targets.append(o)
    for o in targets:
        for attr in (
            "session_id", "_session_id", "sequence", "_sequence", "seq",
            "resume_gateway_url", "_resume_gateway_url",
        ):
            if hasattr(o, attr):
                try:
                    setattr(o, attr, None)
                except Exception:
                    pass


class SpooferCog(commands.Cog, name="spoofer"):
    def __init__(self, bot):
        self.bot = bot
        self._last_props = None
        self._grace = 0.0
        _COG[0] = self
        _install()

    @commands.Cog.listener()
    async def on_ready(self):
        _install()
        props = _POOL.get("forced_props")
        if props:
            _stamp(self.bot, props)
            self._last_props = props

    @commands.Cog.listener()
    async def on_resumed(self):
        if not _POOL.get("forced_props"):
            return
        if time.time() < self._grace:
            return
        print("[spoofer] resumed with spoof — force full identify")
        await self._reconnect()

    @commands.Cog.listener()
    async def on_socket_response(self, data):
        if not isinstance(data, dict):
            return
        if data.get("t") != "SESSIONS_REPLACE":
            return
        sessions = data.get("d") or []
        clients = []
        for s in sessions:
            if not isinstance(s, dict):
                continue
            info = s.get("client_info") or {}
            clients.append(
                "%s/%s" % (info.get("client") or "?", info.get("os") or "?")
            )
        _POOL["sessions"] = clients
        print("[spoofer] SESSIONS_REPLACE → %s" % clients)

    async def _reconnect(self):
        _STATS["reconnects"] += 1
        props = _POOL.get("forced_props")
        if props:
            _stamp(self.bot, props)
        _install()
        _wipe(self.bot)
        self._grace = time.time() + 25
        ws = getattr(self.bot, "ws", None)
        if ws is None:
            conn = getattr(self.bot, "_connection", None)
            ws = getattr(conn, "ws", None) if conn else None
        if ws is not None:
            close = getattr(ws, "close", None)
            if close:
                try:
                    res = close(code=4000)
                    if asyncio.iscoroutine(res):
                        await res
                    print("[spoofer] closed 4000 (no resume)")
                except TypeError:
                    try:
                        res = close()
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as e:
                        print("[spoofer] close:", e)
                except Exception as e:
                    print("[spoofer] close:", e)
        await asyncio.sleep(0.5)
        _wipe(self.bot)
        if props:
            _stamp(self.bot, props)
        _install()

    async def _apply(self, key):
        k, props = _arm(key)
        if not k:
            return False, "unknown: %s | try: %s" % (
                key,
                ", ".join(sorted(PLATFORM_PRESETS.keys())[:14]),
            )
        self._last_props = props
        _stamp(self.bot, props)
        _install()
        await self._reconnect()
        preset = PLATFORM_PRESETS[k]
        return True, "%s | browser=%s os=%s device=%s" % (
            preset.get("label"),
            props.get("browser"),
            props.get("os"),
            props.get("device") or "-",
        )

    @commands.command(name="spoof", aliases=["spoofer", "device"])
    async def spoof(self, ctx, platform: str = "", sub: str = ""):
        p = (platform or "").lower().strip()
        if not p or p in ("status", "info"):
            props = _POOL.get("forced_props") or self._last_props or {}
            rows = [
                "  key %s" % (_POOL.get("key") or "-"),
                "  browser %s" % (props.get("browser") or "-"),
                "  os %s" % (props.get("os") or "-"),
                "  device %s" % (props.get("device") or "-"),
                "  identifies %d" % _STATS["identifies"],
                "  reconnects %d" % _STATS["reconnects"],
                "  sessions %s" % (", ".join(_POOL.get("sessions") or ["(wait for event)"])),
            ]
            return await S.safe_edit(ctx.message, S.ui_box("spoof", rows))
        if p == "list":
            return await S.safe_edit(
                ctx.message, S.ui_ok(", ".join(sorted(PLATFORM_PRESETS.keys())))
            )
        if p == "reset":
            p = "desktop"
        ok, msg = await self._apply(p)
        return await S.safe_edit(ctx.message, S.ui_ok(msg) if ok else S.ui_err(msg))

    @commands.command(name="vr", aliases=["spoofvr"])
    async def vr(self, ctx):
        ok, msg = await self._apply("vr")
        await S.safe_edit(ctx.message, S.ui_ok(msg) if ok else S.ui_err(msg))

    @commands.command(name="spoofmobile", aliases=["spoofphone", "spoofandroid"])
    async def spoofmobile(self, ctx):
        ok, msg = await self._apply("mobile")
        await S.safe_edit(ctx.message, S.ui_ok(msg) if ok else S.ui_err(msg))

    @commands.command(name="spoofios")
    async def spoofios(self, ctx):
        ok, msg = await self._apply("ios")
        await S.safe_edit(ctx.message, S.ui_ok(msg) if ok else S.ui_err(msg))

    @commands.command(name="spoofdesktop", aliases=["spoofpc"])
    async def spoofdesktop(self, ctx):
        ok, msg = await self._apply("desktop")
        await S.safe_edit(ctx.message, S.ui_ok(msg) if ok else S.ui_err(msg))

    @commands.command(name="spoofweb")
    async def spoofweb(self, ctx):
        ok, msg = await self._apply("web")
        await S.safe_edit(ctx.message, S.ui_ok(msg) if ok else S.ui_err(msg))

    @commands.command(name="spoofhard")
    async def spoofhard(self, ctx, platform: str = "vr"):
        ok, msg = await self._apply(platform)
        await S.safe_edit(ctx.message, S.ui_ok("HARD " + msg) if ok else S.ui_err(msg))

    @commands.command(name="spoofreset", aliases=["resetspoof"])
    async def spoofreset(self, ctx):
        ok, msg = await self._apply("desktop")
        await S.safe_edit(ctx.message, S.ui_ok("reset → " + msg) if ok else S.ui_err(msg))

    @commands.command(name="spoofstatus", aliases=["spooferdiag"])
    async def spoofstatus(self, ctx):
        await self.spoof(ctx, "status")


async def setup(bot):
    if "spoofer" in bot.cogs:
        await bot.remove_cog("spoofer")
    await bot.add_cog(SpooferCog(bot))
    _install()
