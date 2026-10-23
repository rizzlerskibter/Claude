
import asyncio
import json
import os
import time

import aiohttp
import discord
from discord.ext import commands

from . import state as S


class BackupCog(commands.Cog, name="backup"):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="backup", invoke_without_command=True, brief="Server backup / restore")
    @commands.guild_only()
    async def backup(self, ctx):
        await S.safe_edit(
            ctx.message,
            S.ui_info("backup server | backup restore <file> | backup list | backup messages [limit]"),
        )

    @backup.command(name="server", aliases=["save", "create"])
    async def backup_server(self, ctx):
        g = ctx.guild
        await S.safe_edit(ctx.message, S.ui_info("backing up..."))
        data = {
            "id": g.id,
            "name": g.name,
            "description": g.description,
            "icon_url": str(g.icon.url) if g.icon else None,
            "afk_channel": g.afk_channel.name if g.afk_channel else None,
            "afk_timeout": g.afk_timeout,
            "verification_level": int(g.verification_level) if g.verification_level is not None else 0,
            "roles": [],
            "categories": [],
            "channels": [],
            "emojis": [],
            "messages": {},
        }
        for r in sorted(g.roles, key=lambda x: x.position):
            if r.is_default():
                continue
            data["roles"].append({
                "name": r.name,
                "color": r.color.value if r.color else 0,
                "hoist": r.hoist,
                "mentionable": r.mentionable,
                "permissions": r.permissions.value,
                "position": r.position,
            })
        cats = {c.id: c for c in g.categories}
        for c in g.categories:
            data["categories"].append({"name": c.name, "position": c.position})
        for c in g.channels:
            entry = {
                "name": c.name,
                "type": str(c.type),
                "position": c.position,
                "category": c.category.name if getattr(c, "category", None) else None,
                "topic": getattr(c, "topic", None),
                "nsfw": getattr(c, "nsfw", False),
                "slowmode_delay": getattr(c, "slowmode_delay", 0),
                "bitrate": getattr(c, "bitrate", None),
                "user_limit": getattr(c, "user_limit", None),
            }
            data["channels"].append(entry)
        for e in g.emojis:
            data["emojis"].append({"name": e.name, "url": str(e.url), "animated": e.animated})
        os.makedirs("backups", exist_ok=True)
        path = "backups/%s_%s.json" % (g.id, int(time.time()))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        await S.safe_edit(ctx.message, S.ui_ok("backed up → %s (%d channels, %d roles)" % (path, len(data["channels"]), len(data["roles"]))))

    @backup.command(name="messages", aliases=["msgs"])
    async def backup_messages(self, ctx, limit: int = 100):
        g = ctx.guild
        limit = max(10, min(int(limit or 100), 500))
        await S.safe_edit(ctx.message, S.ui_info("scraping messages (up to %d / channel)..." % limit))
        data = {"id": g.id, "name": g.name, "messages": {}}
        for ch in g.text_channels:
            try:
                msgs = []
                async for m in ch.history(limit=limit):
                    msgs.append({
                        "id": m.id,
                        "author": str(m.author),
                        "author_id": m.author.id,
                        "content": m.content,
                        "ts": m.created_at.isoformat() if m.created_at else None,
                        "attachments": [a.url for a in m.attachments],
                    })
                if msgs:
                    data["messages"][ch.name] = list(reversed(msgs))
            except Exception as e:
                print("[backup] msgs %s: %s" % (ch.name, e))
            await asyncio.sleep(0.35)
        os.makedirs("backups", exist_ok=True)
        path = "backups/%s_msgs_%s.json" % (g.id, int(time.time()))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        await S.safe_edit(ctx.message, S.ui_ok("messages → %s (%d channels)" % (path, len(data["messages"]))))

    @backup.command(name="list", aliases=["ls"])
    async def backup_list(self, ctx):
        os.makedirs("backups", exist_ok=True)
        files = sorted(f for f in os.listdir("backups") if f.endswith(".json"))
        if not files:
            return await S.safe_edit(ctx.message, S.ui_info("no backups"))
        rows = ["  %s" % f for f in files[-30:]]
        await S.safe_edit(ctx.message, S.ui_box("backups", rows))

    @backup.command(name="restore", aliases=["load", "apply"])
    async def backup_restore(self, ctx, *, file: str = ""):
        if not file:
            return await S.safe_edit(
                ctx.message,
                S.ui_err("usage: backup restore <file.json>  (from backups/ or full path)"),
            )
        path = file.strip().strip("`")
        if not os.path.isfile(path):
            alt = os.path.join("backups", path)
            if os.path.isfile(alt):
                path = alt
            else:
                # fuzzy latest match
                os.makedirs("backups", exist_ok=True)
                hits = [f for f in os.listdir("backups") if path in f and f.endswith(".json")]
                if hits:
                    path = os.path.join("backups", sorted(hits)[-1])
                else:
                    return await S.safe_edit(ctx.message, S.ui_err("file not found: %s" % file))
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return await S.safe_edit(ctx.message, S.ui_err("read failed: %s" % e))

        g = ctx.guild
        await S.safe_edit(ctx.message, S.ui_info("restoring into %s ..." % g.name))
        created_roles = {}
        # roles
        for r in data.get("roles") or []:
            try:
                name = (r.get("name") or "role")[:100]
                existing = discord.utils.get(g.roles, name=name)
                if existing:
                    created_roles[name] = existing
                    continue
                role = await g.create_role(
                    name=name,
                    colour=discord.Colour(r.get("color") or 0),
                    hoist=bool(r.get("hoist")),
                    mentionable=bool(r.get("mentionable")),
                    permissions=discord.Permissions(r.get("permissions") or 0),
                    reason="wilt backup restore",
                )
                created_roles[name] = role
                await asyncio.sleep(0.4)
            except Exception as e:
                print("[backup] role:", e)
        # categories
        cat_map = {}
        for c in data.get("categories") or []:
            try:
                name = (c.get("name") or "category")[:100]
                existing = discord.utils.get(g.categories, name=name)
                if existing:
                    cat_map[name] = existing
                    continue
                cat = await g.create_category(name, reason="wilt backup restore")
                cat_map[name] = cat
                await asyncio.sleep(0.35)
            except Exception as e:
                print("[backup] category:", e)
        # channels
        for ch in data.get("channels") or []:
            try:
                name = (ch.get("name") or "channel")[:100]
                ctype = (ch.get("type") or "text").lower()
                cat = cat_map.get(ch.get("category")) if ch.get("category") else None
                if "voice" in ctype:
                    if discord.utils.get(g.voice_channels, name=name):
                        continue
                    kwargs = {"bitrate": ch.get("bitrate") or 64000, "user_limit": ch.get("user_limit") or 0}
                    await g.create_voice_channel(name, category=cat, reason="wilt backup restore", **{k: v for k, v in kwargs.items() if v})
                elif "stage" in ctype:
                    continue
                elif "category" in ctype:
                    continue
                else:
                    if discord.utils.get(g.text_channels, name=name):
                        continue
                    await g.create_text_channel(
                        name,
                        category=cat,
                        topic=(ch.get("topic") or "")[:1024] or None,
                        nsfw=bool(ch.get("nsfw")),
                        slowmode_delay=int(ch.get("slowmode_delay") or 0),
                        reason="wilt backup restore",
                    )
                await asyncio.sleep(0.4)
            except Exception as e:
                print("[backup] channel:", e)
        # emojis (best-effort)
        for e in (data.get("emojis") or [])[:20]:
            try:
                url = e.get("url")
                name = re.sub(r"[^a-zA-Z0-9_]", "", (e.get("name") or "emoji"))[:32]
                if not url or not name:
                    continue
                if discord.utils.get(g.emojis, name=name):
                    continue
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        img = await resp.read()
                await g.create_custom_emoji(name=name, image=img, reason="wilt backup restore")
                await asyncio.sleep(1.0)
            except Exception as ex:
                print("[backup] emoji:", ex)
        # messages (optional section in same or msgs file)
        msgs = data.get("messages") or {}
        posted = 0
        if msgs:
            await S.safe_edit(ctx.message, S.ui_info("restoring messages..."))
            for ch_name, items in msgs.items():
                ch = discord.utils.get(g.text_channels, name=ch_name)
                if ch is None:
                    continue
                for m in items[-50:]:
                    content = (m.get("content") or "").strip()
                    author = m.get("author") or "?"
                    if not content and not m.get("attachments"):
                        continue
                    body = "**%s**\n%s" % (author, content[:1800])
                    if m.get("attachments"):
                        body += "\n" + "\n".join(m["attachments"][:3])
                    try:
                        await ch.send(body[:1900])
                        posted += 1
                        await asyncio.sleep(0.6)
                    except Exception as e:
                        print("[backup] msg:", e)
                        break
        await S.safe_edit(
            ctx.message,
            S.ui_ok(
                "restore done · roles %d · cats %d · msgs posted %d · file %s"
                % (len(created_roles), len(cat_map), posted, os.path.basename(path))
            ),
        )


async def setup(bot):
    if "backup" in bot.cogs:
        await bot.remove_cog("backup")
    await bot.add_cog(BackupCog(bot))
