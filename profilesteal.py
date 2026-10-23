
import asyncio
import base64
import json

import aiohttp
import discord
from discord.ext import commands

from . import state as S


def _headers():
    token = S._get_token()
    props = {
        "os": "Windows",
        "browser": "Discord Client",
        "device": "",
        "system_locale": "en-US",
        "browser_user_agent": getattr(S, "USER_AGENT", "Mozilla/5.0"),
        "browser_version": "1.0.9262",
        "os_version": "10.0.22631",
        "referrer": "",
        "referring_domain": "",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": 630444,
        "client_event_source": None,
    }
    xsp = base64.b64encode(json.dumps(props, separators=(",", ":")).encode()).decode()
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": props["browser_user_agent"],
        "X-Super-Properties": xsp,
        "X-Discord-Locale": "en-US",
        "X-Debug-Options": "bugReporterEnabled",
        "Origin": "https://discord.com",
        "Referer": "https://discord.com/channels/@me",
    }


async def _bytes_to_data_uri(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        ct = "image/jpeg"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        ct = "image/png"
    elif data[:6] in (b"GIF87a", b"GIF89a"):
        ct = "image/gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ct = "image/webp"
    else:
        ct = "image/png"
    return "data:%s;base64,%s" % (ct, base64.b64encode(data).decode())


async def _patch_me(payload: dict):
    try:
        async with aiohttp.ClientSession() as s:
            for attempt in range(3):
                async with s.patch(
                    "https://discord.com/api/v9/users/@me",
                    headers=_headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    text = await r.text()
                    if r.status == 429:
                        try:
                            data = json.loads(text)
                            wait = float(data.get("retry_after", 2))
                        except Exception:
                            wait = 2.0 + attempt
                        await asyncio.sleep(min(wait, 15))
                        continue
                    return r.status, text
            return 429, "rate limited"
    except Exception as e:
        return 0, str(e)


async def _fetch_profile(uid: int):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://discord.com/api/v9/users/%s/profile" % uid,
                headers=_headers(),
                params={"with_mutual_guilds": "false", "with_mutual_friends_count": "false"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as r:
                if r.status != 200:
                    return r.status, None
                return 200, await r.json()
    except Exception as e:
        return 0, None


def _explain(status: int, body: str) -> str:
    b = (body or "").lower()
    if status == 401:
        return "401 unauthorized — token invalid or expired"
    if status == 403:
        if "nitro" in b or "premium" in b:
            return "403 needs Nitro (banner) or feature locked"
        if "captcha" in b:
            return "403 captcha required — try again later from client"
        if "rate" in b or "cooldown" in b:
            return "403 rate limited / cooldown"
        return "403 forbidden — Nitro, cooldown, or blocked by Discord"
    if status == 429:
        return "429 rate limited — wait and retry"
    if status == 400:
        return "400 bad image or payload: %s" % (body or "")[:80]
    return "(%s) %s" % (status, (body or "")[:80])


class ProfileStealCog(commands.Cog, name="profilesteal"):
    def __init__(self, bot):
        self.bot = bot

    def _target(self, ctx, user, user_id):
        if user is not None:
            return user
        if user_id is not None:
            return user_id
        if ctx.message.mentions:
            return ctx.message.mentions[0]
        return None

    async def _fetch_user(self, uid):
        try:
            return await self.bot.fetch_user(int(uid))
        except Exception:
            return None

    @commands.command(name="stealavatar", aliases=["copyavatar", "sa"], brief="Copy avatar from user")
    async def stealavatar(self, ctx, user: discord.User = None, user_id: int = None):
        t = self._target(ctx, user, user_id)
        if t is None:
            return await S.safe_edit(ctx.message, S.ui_err("mention a user or pass id"))
        u = await self._fetch_user(getattr(t, "id", t))
        if u is None:
            return await S.safe_edit(ctx.message, S.ui_err("user not found"))
        if not u.display_avatar:
            return await S.safe_edit(ctx.message, S.ui_err("no avatar"))
        await S.safe_edit(ctx.message, S.ui_info("copying avatar..."))
        try:
            data = await u.display_avatar.read()
            uri = await _bytes_to_data_uri(data)
            status, body = await _patch_me({"avatar": uri})
            if status in (200, 201, 204):
                return await S.safe_edit(ctx.message, S.ui_ok("avatar set from %s" % u))
            return await S.safe_edit(ctx.message, S.ui_err(_explain(status, body)))
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err(str(e)[:120]))

    @commands.command(name="stealbanner", aliases=["copybanner", "sbanner"], brief="Copy banner from user (Nitro)")
    async def stealbanner(self, ctx, user: discord.User = None, user_id: int = None):
        t = self._target(ctx, user, user_id)
        if t is None:
            return await S.safe_edit(ctx.message, S.ui_err("mention a user or pass id"))
        u = await self._fetch_user(getattr(t, "id", t))
        if u is None:
            return await S.safe_edit(ctx.message, S.ui_err("user not found"))
        banner = getattr(u, "banner", None)
        if banner is None:
            # try profile endpoint for banner hash
            st, prof = await _fetch_profile(u.id)
            user_obj = (prof or {}).get("user") or {}
            if not user_obj.get("banner"):
                return await S.safe_edit(ctx.message, S.ui_err("user has no banner"))
            url = "https://cdn.discordapp.com/banners/%s/%s.png?size=1024" % (u.id, user_obj["banner"])
            if str(user_obj["banner"]).startswith("a_"):
                url = url.replace(".png", ".gif")
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(url) as r:
                        if r.status != 200:
                            return await S.safe_edit(ctx.message, S.ui_err("banner download failed"))
                        data = await r.read()
            except Exception as e:
                return await S.safe_edit(ctx.message, S.ui_err(str(e)[:100]))
        else:
            try:
                data = await banner.read()
            except Exception as e:
                return await S.safe_edit(ctx.message, S.ui_err(str(e)[:100]))
        await S.safe_edit(ctx.message, S.ui_info("copying banner..."))
        uri = await _bytes_to_data_uri(data)
        status, body = await _patch_me({"banner": uri})
        if status in (200, 201, 204):
            return await S.safe_edit(ctx.message, S.ui_ok("banner set from %s" % u))
        return await S.safe_edit(ctx.message, S.ui_err(_explain(status, body)))

    @commands.command(name="stealprofile", aliases=["copyprofile", "sp"], brief="Copy avatar+banner+bio")
    async def stealprofile(self, ctx, user: discord.User = None, user_id: int = None):
        t = self._target(ctx, user, user_id)
        if t is None:
            return await S.safe_edit(ctx.message, S.ui_err("mention a user or pass id"))
        u = await self._fetch_user(getattr(t, "id", t))
        if u is None:
            return await S.safe_edit(ctx.message, S.ui_err("user not found"))
        await S.safe_edit(ctx.message, S.ui_info("stealing profile from %s..." % u))
        done = []
        fails = []

        # avatar
        try:
            if u.display_avatar:
                data = await u.display_avatar.read()
                status, body = await _patch_me({"avatar": await _bytes_to_data_uri(data)})
                if status in (200, 201, 204):
                    done.append("avatar")
                else:
                    fails.append("avatar " + _explain(status, body))
                await asyncio.sleep(1.2)
        except Exception as e:
            fails.append("avatar %s" % str(e)[:50])

        # banner
        try:
            data = None
            if getattr(u, "banner", None):
                data = await u.banner.read()
            else:
                st, prof = await _fetch_profile(u.id)
                user_obj = (prof or {}).get("user") or {}
                bh = user_obj.get("banner")
                if bh:
                    url = "https://cdn.discordapp.com/banners/%s/%s.png?size=1024" % (u.id, bh)
                    if str(bh).startswith("a_"):
                        url = url.replace(".png", ".gif")
                    async with aiohttp.ClientSession() as s:
                        async with s.get(url) as r:
                            if r.status == 200:
                                data = await r.read()
            if data:
                status, body = await _patch_me({"banner": await _bytes_to_data_uri(data)})
                if status in (200, 201, 204):
                    done.append("banner")
                else:
                    fails.append("banner " + _explain(status, body))
                await asyncio.sleep(1.2)
        except Exception as e:
            fails.append("banner %s" % str(e)[:50])

        # bio / pronouns from profile endpoint
        try:
            st, prof = await _fetch_profile(u.id)
            if st == 200 and isinstance(prof, dict):
                user_obj = prof.get("user") or {}
                bio = user_obj.get("bio") or prof.get("bio")
                pronouns = user_obj.get("pronouns") or prof.get("pronouns")
                payload = {}
                if bio:
                    payload["bio"] = str(bio)[:190]
                if pronouns:
                    payload["pronouns"] = str(pronouns)[:40]
                if payload:
                    status, body = await _patch_me(payload)
                    if status in (200, 201, 204):
                        done.extend(payload.keys())
                    else:
                        fails.append("bio " + _explain(status, body))
            elif st == 403:
                fails.append("profile fetch 403")
        except Exception as e:
            fails.append("bio %s" % str(e)[:50])

        msg = "from %s · %s" % (u, ", ".join(done) if done else "nothing applied")
        if fails:
            msg += " | fails: " + "; ".join(fails)[:120]
        await S.safe_edit(ctx.message, S.ui_ok(msg) if done else S.ui_err(msg))

    @commands.command(name="pstealstatus", aliases=["takestatus", "copystat"], brief="Copy custom status text")
    async def stealstatus(self, ctx, user: discord.Member = None):
        m = user or (ctx.message.mentions[0] if ctx.message.mentions else None)
        if m is None:
            return await S.safe_edit(ctx.message, S.ui_err("mention a member"))
        text = None
        for a in m.activities or []:
            if int(getattr(getattr(a, "type", None), "value", -1)) == 4:
                text = getattr(a, "state", None) or getattr(a, "name", None)
                break
            if text is None:
                text = getattr(a, "state", None) or getattr(a, "name", None)
        if not text:
            return await S.safe_edit(ctx.message, S.ui_err("no custom status on that member"))
        try:
            S.CUSTOM_STATUS_TEXT = str(text)[:128]
        except Exception:
            pass
        try:
            cog = self.bot.get_cog("rpc")
            if cog and hasattr(cog, "apply_activities"):
                await cog.apply_activities()
        except Exception:
            pass
        await S.safe_edit(ctx.message, S.ui_ok("status → %s" % text[:80]))


async def setup(bot):
    if "profilesteal" in bot.cogs:
        await bot.remove_cog("profilesteal")
    await bot.add_cog(ProfileStealCog(bot))
