
import asyncio
import json
import time

import discord
from discord.ext import commands

from . import state as S

try:
    from cogs.spoofer import PLATFORM_PRESETS, _full_props, _POOL
except Exception:
    try:
        from .spoofer import PLATFORM_PRESETS, _full_props, _POOL
    except Exception:
        PLATFORM_PRESETS = {}
        def _full_props(p):
            d = dict(p) if isinstance(p, dict) else {}
            d.pop("label", None)
            return d
        _POOL = {}

_satellites = []


def _token(bot):
    t = getattr(getattr(bot, "http", None), "token", None)
    if not t:
        http = getattr(bot, "http", None)
        t = getattr(http, "_token", None) if http else None
    if not t:
        import os
        t = os.environ.get("TOKEN") or os.environ.get("DISCORD_TOKEN")
    if not t:
        t = getattr(S, "TOKEN", None)
    return t


def _props_for(key):
    preset = PLATFORM_PRESETS.get(key)
    if not preset:
        return None
    if callable(globals().get("_full_props")):
        try:
            return _full_props(preset)
        except Exception:
            pass
    d = dict(preset)
    d.pop("label", None)
    d.setdefault("referrer", "")
    d.setdefault("referring_domain", "")
    d.setdefault("client_event_source", None)
    d.setdefault("has_client_mods", False)
    return d


async def _run_satellite(token, props, label, stop_event):
    try:
        import websockets
    except Exception as e:
        print("[multispoof] websockets missing:", e)
        return
    url = "wss://gateway.discord.gg/?v=9&encoding=json"
    ua = props.get("browser_user_agent") or "Discord-Android/349.9"
    backoff = 1.0
    while not stop_event.is_set():
        try:
            async with websockets.connect(
                url,
                additional_headers={
                    "User-Agent": ua,
                    "Origin": "https://discord.com",
                },
                open_timeout=20,
                close_timeout=5,
                max_size=8 * 1024 * 1024,
            ) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=15)
                hello = json.loads(raw)
                if hello.get("op") != 10:
                    await asyncio.sleep(2)
                    continue
                interval = float(hello.get("d", {}).get("heartbeat_interval", 41250)) / 1000.0
                browser = str(props.get("browser") or "")
                is_mobile = browser in ("Discord Android", "Discord iOS")
                is_vr = browser == "Discord VR"
                caps = 16381
                identify = {
                    "op": 2,
                    "d": {
                        "token": token,
                        "capabilities": caps,
                        "properties": props,
                        "compress": False,
                        "presence": {
                            "status": "online",
                            "since": 0,
                            "activities": [],
                            "afk": False,
                        },
                        "client_state": {
                            "guild_versions": {},
                            "highest_last_message_id": "0",
                            "read_state_version": 0,
                            "user_guild_settings_version": -1,
                            "user_settings_version": -1,
                            "private_channels_version": "0",
                            "api_code_version": 0,
                        },
                    },
                }
                await ws.send(json.dumps(identify))
                print(
                    "[multispoof] satellite IDENTIFY %s browser=%s device=%s"
                    % (label, props.get("browser"), props.get("device") or "-")
                )
                backoff = 1.0
                last_hb = time.time()
                while not stop_event.is_set():
                    timeout = max(1.0, interval - (time.time() - last_hb))
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        await ws.send(json.dumps({"op": 1, "d": None}))
                        last_hb = time.time()
                        continue
                    data = json.loads(msg)
                    op = data.get("op")
                    t = data.get("t")
                    if op == 10:
                        interval = float(data.get("d", {}).get("heartbeat_interval", 41250)) / 1000.0
                    elif op == 1:
                        await ws.send(json.dumps({"op": 1, "d": None}))
                        last_hb = time.time()
                    elif op == 7:
                        print("[multispoof] %s reconnect requested" % label)
                        break
                    elif op == 9:
                        print("[multispoof] %s invalid session" % label)
                        await asyncio.sleep(2)
                        break
                    elif t == "READY":
                        print("[multispoof] %s READY" % label)
                    elif t == "SESSIONS_REPLACE":
                        sessions = data.get("d") or []
                        clients = [
                            (s.get("client_info") or {}).get("client")
                            for s in sessions
                            if isinstance(s, dict)
                        ]
                        print("[multispoof] %s sessions %s" % (label, clients))
                    if time.time() - last_hb >= interval * 0.9:
                        await ws.send(json.dumps({"op": 1, "d": None}))
                        last_hb = time.time()
        except asyncio.CancelledError:
            return
        except Exception as e:
            if stop_event.is_set():
                return
            print("[multispoof] %s error: %s" % (label, e))
            await asyncio.sleep(backoff)
            backoff = min(backoff * 1.5, 30.0)


class MultiSpoofCog(commands.Cog, name="spoofer"):
    def __init__(self, bot):
        self.bot = bot

    async def _stop_all(self):
        global _satellites
        for item in _satellites:
            try:
                item["stop"].set()
                item["task"].cancel()
            except Exception:
                pass
        _satellites = []

    async def _start_multi(self, platforms):
        await getattr(self, "_multi_helper", self)._stop_all()
        token = _token(self.bot)
        if not token:
            raise RuntimeError("no token")
        if not PLATFORM_PRESETS:
            raise RuntimeError("spoofer presets unavailable — load spoofer cog first")
        labels = []
        for key in platforms:
            key = key.lower().strip()
            if key not in PLATFORM_PRESETS:
                continue
            props = _props_for(key)
            if not props:
                continue
            stop = asyncio.Event()
            label = PLATFORM_PRESETS[key].get("label") or key
            task = asyncio.create_task(_run_satellite(token, props, label, stop))
            _satellites.append({"key": key, "label": label, "stop": stop, "task": task})
            labels.append(label)
            await asyncio.sleep(0.4)
        if not labels:
            raise RuntimeError("no valid platforms")
        return labels

    @commands.group(name="multispoof", aliases=["mspoof", "ms"], invoke_without_command=True)
    async def multispoof(self, ctx, *args):
        args = [a for a in args if a]
        if not args:
            return await S.safe_edit(
                ctx.message,
                S.ui_info(
                    "multispoof multi <p1> <p2>... | stop | status | list\n"
                    "example: .multispoof multi vr mobile ios web"
                ),
            )
        sub = args[0].lower()
        if sub in ("stop", "off", "clear"):
            await getattr(self, "_multi_helper", self)._stop_all()
            return await S.safe_edit(ctx.message, S.ui_ok("satellites stopped"))
        if sub in ("status", "info"):
            rows = ["  active %d" % len(_satellites)]
            for s in _satellites:
                done = s["task"].done()
                rows.append("  %s %s" % (s["label"], "dead" if done else "live"))
            return await S.safe_edit(ctx.message, S.ui_box("multispoof", rows))
        if sub == "list":
            keys = sorted(PLATFORM_PRESETS.keys()) if PLATFORM_PRESETS else []
            return await S.safe_edit(
                ctx.message,
                S.ui_ok(", ".join(keys) if keys else "no presets (load spoofer)"),
            )
        if sub == "multi":
            platforms = [a.lower() for a in args[1:]]
            if not platforms:
                platforms = ["vr", "mobile", "ios", "web"]
        else:
            platforms = [a.lower() for a in args]
        bad = [p for p in platforms if p not in PLATFORM_PRESETS]
        if bad and not any(p in PLATFORM_PRESETS for p in platforms):
            return await S.safe_edit(
                ctx.message,
                S.ui_err("unknown %s | .multispoof list" % ", ".join(bad)),
            )
        platforms = [p for p in platforms if p in PLATFORM_PRESETS]
        await S.safe_edit(ctx.message, S.ui_info("starting %d gateways..." % len(platforms)))
        try:
            labels = await getattr(self, "_multi_helper", self)._start_multi(platforms)
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err(str(e)[:160]))
        return await S.safe_edit(
            ctx.message,
            S.ui_ok("live: %s — check Settings → Devices" % ", ".join(labels)),
        )

    @multispoof.command(name="multi")
    async def multi_cmd(self, ctx, *platforms):
        if not platforms:
            platforms = ("vr", "mobile", "ios", "web")
        await self.multispoof(ctx, "multi", *platforms)

    @multispoof.command(name="stop")
    async def stop_cmd(self, ctx):
        await self.multispoof(ctx, "stop")

    @multispoof.command(name="status")
    async def status_cmd(self, ctx):
        await self.multispoof(ctx, "status")

    @multispoof.command(name="list")
    async def list_cmd(self, ctx):
        await self.multispoof(ctx, "list")


async def setup(bot):
    helper = MultiSpoofCog(bot)
    existing = bot.get_cog("spoofer")
    if existing is not None:
        # command group runs with self=SpooferCog — wire helper methods onto it
        existing._multi_helper = helper
        existing._start_multi = helper._start_multi
        existing._stop_all = helper._stop_all
        grp = helper.multispoof
        grp.cog = existing
        if bot.get_command("multispoof") is None:
            bot.add_command(grp)
        # subcommands already children of grp
        print("[multispoof] attached under spoofer category")
        return
    if "spoofer" in bot.cogs:
        await bot.remove_cog("spoofer")
    await bot.add_cog(helper)
    print("[multispoof] loaded as spoofer (spoofer cog missing)")
