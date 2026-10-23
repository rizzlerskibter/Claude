
import asyncio
import os
import shutil
import sys

import discord
from discord.ext import commands

from . import state as S

_YDL_CACHE = {"cmd": None, "mode": None}


def _resolve_ytdlp():
    if _YDL_CACHE["cmd"] is not None:
        return _YDL_CACHE["cmd"], _YDL_CACHE["mode"]
    candidates = []
    for name in ("yt-dlp", "yt_dlp", "youtube-dl"):
        path = shutil.which(name)
        if path:
            candidates.append(([path], "bin"))
    py = sys.executable or "python3"
    candidates.append(([py, "-m", "yt_dlp"], "module"))
    candidates.append(([py, "-m", "youtube_dl"], "module"))
    try:
        import yt_dlp  # noqa: F401
        candidates.insert(0, (None, "api"))
    except Exception:
        pass
    for cmd, mode in candidates:
        if mode == "api":
            _YDL_CACHE["cmd"] = None
            _YDL_CACHE["mode"] = "api"
            return None, "api"
        try:
            # quick probe --version
            import subprocess as sp
            r = sp.run(cmd + ["--version"], capture_output=True, text=True, timeout=8)
            if r.returncode == 0 or (r.stdout or r.stderr):
                _YDL_CACHE["cmd"] = cmd
                _YDL_CACHE["mode"] = mode
                return cmd, mode
        except Exception:
            continue
    return None, None


async def _run_ytdlp(url: str, outtmpl: str, extra: list = None):
    extra = list(extra or [])
    cmd, mode = _resolve_ytdlp()
    os.makedirs("downloads", exist_ok=True)
    if mode == "api":
        def _api():
            import yt_dlp
            opts = {
                "outtmpl": outtmpl,
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
            }
            # map simple flags
            if "-x" in extra:
                opts["format"] = "bestaudio/best"
                opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            elif "-f" in extra:
                try:
                    opts["format"] = extra[extra.index("-f") + 1]
                except Exception:
                    opts["format"] = "best"
            else:
                opts["format"] = "best"
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return 0, ""
        try:
            code, err = await asyncio.to_thread(_api)
            return code, err
        except Exception as e:
            return 1, str(e)
    if not cmd:
        return 127, "yt-dlp not found (install: pip install -U yt-dlp)"
    full = list(cmd) + extra + ["-o", outtmpl, "--no-playlist", url]
    try:
        proc = await asyncio.create_subprocess_exec(
            *full,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        text = (err or out or b"").decode("utf-8", errors="ignore")
        return proc.returncode, text
    except FileNotFoundError:
        return 127, "yt-dlp binary missing"
    except Exception as e:
        return 1, str(e)


class DownloadsCog(commands.Cog, name="downloads"):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ytdlp", aliases=["ydlcheck", "dlcheck"], brief="Check yt-dlp availability")
    async def ytdlp_check(self, ctx):
        _YDL_CACHE["cmd"] = None
        _YDL_CACHE["mode"] = None
        cmd, mode = _resolve_ytdlp()
        if mode == "api":
            return await S.safe_edit(ctx.message, S.ui_ok("yt-dlp via python API"))
        if cmd:
            return await S.safe_edit(ctx.message, S.ui_ok("yt-dlp via %s: %s" % (mode, " ".join(cmd))))
        return await S.safe_edit(ctx.message, S.ui_err("yt-dlp not found — pip install -U yt-dlp"))

    @commands.command(name="download", aliases=["dl"], brief="Download media via yt-dlp")
    async def download(self, ctx, url: str = "", fmt: str = "mp4"):
        if not url:
            return await S.safe_edit(ctx.message, S.ui_err("usage: download <url> [mp4|mp3]"))
        await S.safe_edit(ctx.message, S.ui_info("downloading..."))
        audio = fmt.lower() == "mp3"
        extra = ["-x", "--audio-format", "mp3"] if audio else ["-f", "bv*+ba/best"]
        code, err = await _run_ytdlp(url, "downloads/%(title).80B.%(ext)s", extra)
        if code == 0:
            return await S.safe_edit(ctx.message, S.ui_ok("saved → downloads/"))
        return await S.safe_edit(ctx.message, S.ui_err((err or "failed")[:180]))

    @commands.command(name="yt", aliases=["youtube_dl"], brief="Download YouTube video")
    async def yt(self, ctx, url: str = ""):
        if not url:
            return await S.safe_edit(ctx.message, S.ui_err("usage: yt <url>"))
        await S.safe_edit(ctx.message, S.ui_info("downloading..."))
        code, err = await _run_ytdlp(url, "downloads/%(title).80B.%(ext)s", ["-f", "bv*+ba/best"])
        if code == 0:
            return await S.safe_edit(ctx.message, S.ui_ok("saved → downloads/"))
        return await S.safe_edit(ctx.message, S.ui_err((err or "failed")[:180]))

    @commands.command(name="ytaudio", brief="Download audio as MP3")
    async def ytaudio(self, ctx, url: str = ""):
        if not url:
            return await S.safe_edit(ctx.message, S.ui_err("usage: ytaudio <url>"))
        await S.safe_edit(ctx.message, S.ui_info("downloading audio..."))
        code, err = await _run_ytdlp(
            url,
            "downloads/%(title).80B.%(ext)s",
            ["-x", "--audio-format", "mp3"],
        )
        if code == 0:
            return await S.safe_edit(ctx.message, S.ui_ok("mp3 → downloads/"))
        return await S.safe_edit(ctx.message, S.ui_err((err or "failed")[:180]))

    @commands.command(name="tiktok", aliases=["ttdown"], brief="Download TikTok video")
    async def tiktok(self, ctx, url: str = ""):
        if not url:
            return await S.safe_edit(ctx.message, S.ui_err("usage: tiktok <url>"))
        await S.safe_edit(ctx.message, S.ui_info("downloading tiktok..."))
        code, err = await _run_ytdlp(url, "downloads/%(id)s.%(ext)s", ["--no-check-certificates"])
        if code == 0:
            return await S.safe_edit(ctx.message, S.ui_ok("saved → downloads/"))
        return await S.safe_edit(ctx.message, S.ui_err((err or "failed")[:180]))

    @commands.command(name="ig", aliases=["instagram"], brief="Download Instagram content")
    async def ig(self, ctx, url: str = ""):
        if not url:
            return await S.safe_edit(ctx.message, S.ui_err("usage: ig <url>"))
        await S.safe_edit(ctx.message, S.ui_info("downloading instagram..."))
        code, err = await _run_ytdlp(url, "downloads/%(id)s.%(ext)s", [])
        if code == 0:
            return await S.safe_edit(ctx.message, S.ui_ok("saved → downloads/"))
        return await S.safe_edit(ctx.message, S.ui_err((err or "failed")[:180]))


async def setup(bot):
    if "downloads" in bot.cogs:
        await bot.remove_cog("downloads")
    await bot.add_cog(DownloadsCog(bot))
