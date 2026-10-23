
from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path

import discord
from discord.ext import commands

from . import state as S

_ROOT = Path(__file__).resolve().parents[1]
_INSULT_PATHS = [
    _ROOT / "data" / "insults.txt",
    _ROOT / "insults.txt",
    Path("data/insults.txt"),
    Path("insults.txt"),
]

_BUILTIN = {
    "basic": [
        "ur nothing but a loser",
        "stay in ur lane",
        "levels to this",
        "ur washed",
        "fold or log",
        "mid asf",
        "no presence",
        "soft asf",
        "ur my jr",
        "keep watching",
    ],
    "short": [
        "L", "ratio", "skill issue", "cope", "seethe", "bozo", "npc", "bot", "ez", "next",
    ],
}


class PackCog(commands.Cog, name="pack"):
    def __init__(self, bot):
        self.bot = bot
        self._lines = []
        self._sent = set()
        self._task = None
        self._target_id = None
        self._channel_id = None
        self._flags = {
            "hashtag": True,
            "single": True,
            "ladder": False,
            "rand_ladder": False,
            "rand_hashtag": False,
            "manual": False,
            "mention": True,
            "fast": True,
        }
        self._sentences = 0
        self._rl_until = 0.0
        self._fails = 0
        self._load()

    def _load(self):
        lines = []
        for p in _INSULT_PATHS:
            try:
                if not p.is_file():
                    continue
                for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    s = ln.strip()
                    if not s:
                        continue
                    # allow lines that are the insult itself; only skip pure comment markers
                    if s.startswith("# ") and len(s) < 4:
                        continue
                    if s.startswith("#") and not s.startswith("# "):
                        # file comment
                        if len(s) < 3:
                            continue
                    # strip leading "# " if present so we re-add at send time
                    if s.startswith("# "):
                        s = s[2:].strip()
                    elif s.startswith("#"):
                        s = s[1:].strip()
                    if s:
                        lines.append(s)
                if lines:
                    print("[pack] loaded %d lines from %s" % (len(lines), p))
                    break
            except Exception as e:
                print("[pack] load %s: %s" % (p, e))
        for v in _BUILTIN.values():
            lines.extend(v)
        seen = set()
        out = []
        for x in lines:
            k = x.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(x)
        self._lines = out or list(_BUILTIN["basic"])
        print("[pack] pool size %d" % len(self._lines))

    def cog_unload(self):
        self._stop()

    def _pool(self):
        return list(self._lines) if self._lines else list(_BUILTIN["basic"])

    def _pick(self, n=1, allow_repeat=False):
        pool = self._pool()
        if not pool:
            return ["mid"]
        if not allow_repeat:
            avail = [x for x in pool if x not in self._sent]
            if len(avail) < max(n, 1):
                self._sent.clear()
                avail = list(pool)
            pool = avail
        n = max(1, min(int(n), 25))
        if n >= len(pool):
            chosen = list(pool)
            random.shuffle(chosen)
            if not allow_repeat:
                self._sent.update(chosen)
            return chosen or ["mid"]
        chosen = random.sample(pool, n)
        if not allow_repeat:
            self._sent.update(chosen)
        return chosen

    async def _sleep_rl(self):
        now = time.time()
        if self._rl_until > now:
            await asyncio.sleep(self._rl_until - now)

    async def _send(self, channel, content, reply_to=None):
        await self._sleep_rl()
        try:
            if reply_to is not None:
                return await reply_to.reply(content, mention_author=False)
            return await channel.send(content)
        except discord.HTTPException as e:
            if e.status == 429:
                ra = float(getattr(e, "retry_after", None) or 0.25)
                ra = max(0.05, min(ra, 8.0))
                self._rl_until = time.time() + ra
                await asyncio.sleep(ra)
                try:
                    if reply_to is not None:
                        return await reply_to.reply(content, mention_author=False)
                    return await channel.send(content)
                except Exception:
                    self._fails += 1
                    return None
            if e.status in (403, 404):
                print("[pack] channel error %s — stop" % e.status)
                self._stop()
                return None
            self._fails += 1
            return None
        except Exception:
            self._fails += 1
            return None

    def _format_block(self, lines, mention):
        use_ladder = bool(self._flags.get("ladder")) or (
            bool(self._flags.get("rand_ladder")) and random.choice([True, False])
        )
        parts = []
        if use_ladder:
            line = lines[0] if lines else ""
            for w in (line or "").split():
                parts.append("# " + w)
            body = "\n".join(parts) if parts else "# ..."
        else:
            for line in lines:
                t = (line or "").strip()
                if not t:
                    continue
                if t.startswith("#"):
                    t = t.lstrip("#").strip()
                parts.append("# " + t)
            body = "\n".join(parts) if parts else "# ..."
        if mention and self._flags.get("mention", True):
            if len(body) + len(mention) + 1 < 1900:
                body = body + " " + mention
            else:
                body = (mention + "\n" + body)[:1897] + "..."
        return body

    def _stop(self):
        self._target_id = None
        self._channel_id = None
        t = self._task
        self._task = None
        if t and not t.done():
            t.cancel()
        self._sent.clear()
        self._sentences = 0
        self._fails = 0

    async def _loop(self, channel, target, *, all_mode=False, delay=0.0):
        mention = target.mention
        tid = target.id
        try:
            while self._target_id == tid:
                if self._fails >= 40:
                    print("[pack] too many send fails — stop")
                    break
                # concurrent wave — 10x throughput vs single serial send
                wave = 12 if all_mode or self._flags.get("fast") else 8
                bodies = []
                for _ in range(wave):
                    lines = self._pick(1, allow_repeat=True)
                    if self._flags.get("manual") and random.random() > 0.12:
                        bodies.append(self._format_block(lines, ""))
                    else:
                        bodies.append(self._format_block(lines, mention))
                results = await asyncio.gather(
                    *[self._send(channel, b) for b in bodies],
                    return_exceptions=True,
                )
                ok = 0
                for r in results:
                    if r is not None and not isinstance(r, Exception):
                        ok += 1
                if ok:
                    self._fails = 0
                else:
                    self._fails += 1
                    await asyncio.sleep(0.05)
                if self._target_id != tid:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("[pack] loop: %s" % e)
        finally:
            if self._target_id == tid:
                self._stop()

    def _parse_flags(self, args):
        flags = {
            "hashtag": True,
            "single": True,
            "ladder": False,
            "rand_ladder": False,
            "rand_hashtag": False,
            "manual": False,
            "mention": True,
            "fast": True,
        }
        rest = []
        for a in args:
            al = a.lower()
            if a == "#" or al in ("hash", "hashtag"):
                flags["hashtag"] = True
            elif al in ("s", "single"):
                flags["single"] = True
            elif al in ("l", "ladder"):
                flags["single"] = True
                flags["ladder"] = True
            elif al in ("r", "rl"):
                flags["single"] = True
                flags["rand_ladder"] = True
            elif al in ("rh",):
                flags["rand_hashtag"] = True
            elif al in ("mn", "manual"):
                flags["manual"] = True
            elif al in ("fast", "f"):
                flags["fast"] = True
            elif al in ("slow",):
                flags["fast"] = False
            elif al in ("nomention", "nm"):
                flags["mention"] = False
            else:
                rest.append(a)
        return flags, rest

    async def _resolve_user(self, ctx, token):
        token = (token or "").strip()
        if not token:
            return None
        # mention
        if token.startswith("<@") and token.endswith(">"):
            digits = "".join(c for c in token if c.isdigit())
            if digits:
                try:
                    return await self.bot.fetch_user(int(digits))
                except Exception:
                    pass
        try:
            return await commands.UserConverter().convert(ctx, token)
        except Exception:
            pass
        try:
            return await self.bot.fetch_user(int(token))
        except Exception:
            return None

    @commands.command(name="pack", aliases=["chatpack", "cpk", "pc"])
    async def pack_cmd(self, ctx, *args):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not args:
            return await S.safe_send(ctx.channel, S.ui_err("pack [#|s|l|r|rh|mn|fast] @user"))
        flags, rest = self._parse_flags(list(args))
        if not rest:
            return await S.safe_send(ctx.channel, S.ui_err("mention a user"))
        target = await self._resolve_user(ctx, rest[0])
        if target is None:
            return await S.safe_send(ctx.channel, S.ui_err("user not found"))
        if target.id == getattr(self.bot.user, "id", 0):
            return await S.safe_send(ctx.channel, S.ui_err("not on yourself"))

        self._stop()
        flags["hashtag"] = True
        flags["mention"] = flags.get("mention", True)
        flags["fast"] = True
        self._flags = flags
        self._target_id = target.id
        self._channel_id = ctx.channel.id
        self._fails = 0
        self._task = asyncio.create_task(
            self._loop(ctx.channel, target, all_mode=False, delay=0.0)
        )
        await S.safe_send(
            ctx.channel,
            S.ui_ok("packing %s · lines=%d · .packstop" % (target, len(self._lines))),
        )

    @commands.command(name="packall", aliases=["pall", "packspam"])
    async def packall(self, ctx, *args):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not args:
            return await S.safe_send(ctx.channel, S.ui_err("packall [fast|#|s|l] @user"))
        flags, rest = self._parse_flags(list(args))
        flags["hashtag"] = True
        flags["fast"] = True
        flags["mention"] = True
        if not rest:
            return await S.safe_send(ctx.channel, S.ui_err("mention a user"))
        target = await self._resolve_user(ctx, rest[0])
        if target is None:
            return await S.safe_send(ctx.channel, S.ui_err("user not found"))
        if target.id == getattr(self.bot.user, "id", 0):
            return await S.safe_send(ctx.channel, S.ui_err("not on yourself"))

        self._stop()
        self._flags = flags
        self._target_id = target.id
        self._channel_id = ctx.channel.id
        self._sent.clear()
        self._fails = 0
        self._task = asyncio.create_task(
            self._loop(ctx.channel, target, all_mode=True, delay=0.0)
        )
        await S.safe_send(
            ctx.channel,
            S.ui_ok(
                "packall on %s · %d lines · .packstop"
                % (target, len(self._lines))
            ),
        )

    @commands.command(name="packstop", aliases=["spc", "spack", "pstop"])
    async def packstop(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not self._task or self._task.done():
            return await S.safe_send(ctx.channel, S.ui_warn("not packing"))
        self._stop()
        await S.safe_send(ctx.channel, S.ui_ok("pack stopped"))

    @commands.command(name="packone", aliases=["p1"])
    async def packone(self, ctx, *args):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        flags, rest = self._parse_flags(list(args))
        target = None
        if rest:
            target = await self._resolve_user(ctx, rest[0])
        line = self._pick(1, allow_repeat=True)[0]
        body = "# " + line.lstrip("# ").strip()
        if target is not None:
            body = body + " " + target.mention
        await S.safe_send(ctx.channel, body)

    @commands.command(name="packlist", aliases=["packs"])
    async def packlist(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await S.safe_send(
            ctx.channel,
            S.ui_ok("insults lines: %d · builtins: %s" % (len(self._lines), ", ".join(_BUILTIN.keys()))),
        )

    @commands.command(name="packreload")
    async def packreload(self, ctx):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        self._load()
        await S.safe_send(ctx.channel, S.ui_ok("reloaded · %d lines" % len(self._lines)))

    @commands.command(name="packburst", aliases=["pb"])
    async def packburst(self, ctx, *args):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        n = 12
        target = None
        for a in args:
            if a.isdigit():
                n = max(1, min(int(a), 64))
            else:
                u = await self._resolve_user(ctx, a)
                if u:
                    target = u
        lines = self._pick(n, allow_repeat=True)
        bodies = []
        for line in lines:
            body = "# " + line.lstrip("# ").strip()
            if target is not None:
                body = body + " " + target.mention
            bodies.append(body)
        await asyncio.gather(*[self._send(ctx.channel, b) for b in bodies], return_exceptions=True)


async def setup(bot):
    if "pack" in bot.cogs:
        await bot.remove_cog("pack")
    await bot.add_cog(PackCog(bot))
