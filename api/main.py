# api/main.py
# FastAPI service exposing yt-dlp fetching: search, metadata, direct-stream
# playback (Range-capable) and file downloads — all cookie-aware.

import logging
import mimetypes
import os
import time

import aiohttp
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from . import config
from . import ytdlp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [api] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("api.main")
APP_STARTED = time.time()

app = FastAPI(title="Shakky Music Fetch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.ALLOWED_ORIGINS if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_HTTP = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/")
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "shakky-api",
        "cookies": bool(config.COOKIES_FILE),
        "cookies_file": config.COOKIES_FILE,
        "uptime": round(time.time() - APP_STARTED, 1),
    }


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
@app.get("/api/search")
async def search(q: str = Query(..., min_length=1), limit: int = Query(12, ge=1, le=50)):
    try:
        return {"status": "ok", "query": q, "results": await ytdlp.search(q, limit)}
    except Exception as e:
        LOGGER.warning("search failed: %s", e)
        raise HTTPException(502, f"search failed: {e}")


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
@app.get("/api/track")
async def track(url: str):
    try:
        return {"status": "ok", "data": await ytdlp.metadata(url.strip())}
    except Exception as e:
        raise HTTPException(502, f"metadata failed: {e}")


@app.get("/api/track/{raw_id}")
async def track_by_id(raw_id: str):
    if not raw_id or len(raw_id) > 60:
        raise HTTPException(400, "bad id")
    try:
        return {"status": "ok", "data": await ytdlp.metadata(raw_id)}
    except Exception as e:
        raise HTTPException(502, f"metadata failed: {e}")


# ---------------------------------------------------------------------------
# Direct resolved URL (for the bot's stream-first VC playback)
# ---------------------------------------------------------------------------
@app.get("/api/url/{vidid}")
async def api_url(vidid: str):
    """Return the freshly-resolved bestaudio URL + http_headers the bot can
    hand straight to the VC engine. Cache-aware on the API side."""
    if not vidid or len(vidid) > 40:
        raise HTTPException(400, "bad video id")
    try:
        data = await ytdlp.stream(vidid)
    except Exception as e:
        raise HTTPException(502, f"resolve failed: {e}")
    if not data.get("url"):
        raise HTTPException(502, "could not resolve a playable URL")
    return {"status": "ok", "url": data["url"], "ext": data.get("ext", "m4a"),
            "headers": data.get("headers", {})}


# ---------------------------------------------------------------------------
# Locate / ensure a downloaded file on disk (super-fast for the bot, no bytes
# transfer — the API and bot share the same filesystem by default).
# ---------------------------------------------------------------------------
@app.get("/api/locate/{video_id}")
async def api_locate(video_id: str, format: str = Query("m4a")):
    """Ensure the track is downloaded to disk and return its absolute path.
    The bot can then feed this path directly to the VC engine."""
    if not video_id or len(video_id) > 40:
        raise HTTPException(400, "bad video id")
    try:
        path, ext, title = await ytdlp.download(video_id, format, False, None)
    except Exception as e:
        raise HTTPException(502, f"locate failed: {e}")
    if not path or not os.path.isfile(path):
        raise HTTPException(502, "file not produced")
    return {"status": "ok", "path": path, "ext": ext or format, "title": title}


# ---------------------------------------------------------------------------
# Playlist
# ---------------------------------------------------------------------------
@app.get("/api/playlist")
async def playlist(url: str, limit: int = Query(None, ge=1, le=300)):
    try:
        return {"status": "ok", "data": await ytdlp.playlist(url.strip(), limit)}
    except Exception as e:
        raise HTTPException(502, f"playlist failed: {e}")


# ---------------------------------------------------------------------------
# Proxied stream (Range-capable) — ideal for the WebApp player
# ---------------------------------------------------------------------------
@app.get("/api/media/{vidid}")
async def api_media(vidid: str, request: Request):
    """Resolve the best direct audio URL and proxy it through this server.
    Supports Range requests so browsers can seek. Two-phase: open the upstream
    once to read its real status/headers, then re-open and stream the body."""
    if not vidid or len(vidid) > 40:
        raise HTTPException(400, "bad video id")

    try:
        data = await ytdlp.stream(vidid)
    except Exception as e:
        raise HTTPException(502, f"resolve failed: {e}")

    upstream = data["url"]
    media_type = mimetypes.guess_type(f"a.{data.get('ext') or 'm4a'}")[0] or "audio/mpeg"
    range_header = request.headers.get("range")

    def upstream_headers():
        return {"Range": range_header} if range_header else {}

    # Phase 1: read the upstream headers + status without consuming the body.
    async with aiohttp.ClientSession() as probe:
        async with probe.get(upstream, headers=upstream_headers()) as r0:
            status = r0.status
            clen = r0.headers.get("Content-Length")
            crange = r0.headers.get("Content-Range")
            rct = r0.headers.get("Content-Type")
            if rct and (rct.startswith("audio/") or rct.startswith("video/")):
                media_type = rct

    resp_headers = {"Content-Type": media_type, "Accept-Ranges": "bytes"}
    if clen:
        resp_headers["Content-Length"] = clen
    if crange:
        resp_headers["Content-Range"] = crange

    async def _gen():
        async with aiohttp.ClientSession() as sess:
            async with sess.get(upstream, headers=upstream_headers()) as resp:
                async for chunk in resp.content.iter_chunked(256 * 1024):
                    yield chunk

    return StreamingResponse(_gen(), status_code=status, headers=resp_headers)


# ---------------------------------------------------------------------------
# Download to disk (attachment) + local-file serve
# ---------------------------------------------------------------------------
@app.get("/api/download/{vidid}")
async def api_download(
    vidid: str,
    format: str = Query("m4a"),
    video: bool = Query(False),
    quality: int = Query(None, ge=144, le=2160),
):
    """Download the track to disk via yt-dlp and return it as an attachment."""
    if not vidid or len(vidid) > 40:
        raise HTTPException(400, "bad video id")
    try:
        path, ext, title = await ytdlp.download(vidid, format, video, quality)
    except Exception as e:
        raise HTTPException(502, f"download failed: {e}")
    if not path or not os.path.isfile(path):
        raise HTTPException(502, "download produced no file")

    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    filename = f"{vidid}.{ext or 'm4a'}"
    return FileResponse(path, media_type=media_type, filename=filename,
                        content_disposition_type="attachment")


@app.get("/api/audio/{vidid}")
async def api_audio(vidid: str):
    """Serve a previously downloaded file for playback (no re-download)."""
    if not vidid or len(vidid) > 40:
        raise HTTPException(400, "bad video id")
    path = None
    for ext in ("m4a", "mp3", "opus", "webm"):
        cand = os.path.join(config.DOWNLOADS_DIR, f"{vidid}.{ext}")
        if os.path.isfile(cand):
            path = cand
            break
    if not path:
        raise HTTPException(404, "not downloaded yet — call /api/download first")
    media_type = mimetypes.guess_type(path)[0] or "audio/mpeg"
    return FileResponse(path, media_type=media_type)


# ---------------------------------------------------------------------------
# Thumbnail (fetched once, cached to disk)
# ---------------------------------------------------------------------------
@app.get("/api/thumb/{vidid}")
async def api_thumb(vidid: str):
    if not vidid or len(vidid) > 40:
        raise HTTPException(400, "bad video id")
    safe = vidid.replace("/", "_")
    path = os.path.join(config.THUMBS_DIR, f"{safe}.jpg")
    if not os.path.isfile(path):
        fetched = False
        async with aiohttp.ClientSession() as sess:
            for size in ("maxresdefault", "hqdefault"):
                url = f"https://i.ytimg.com/vi/{vidid}/{size}.jpg"
                async with sess.get(url, headers=_HTTP) as resp:
                    if resp.status == 200:
                        body = await resp.read()
                        with open(path, "wb") as fh:
                            fh.write(body)
                        fetched = True
                        break
        if not fetched:
            raise HTTPException(404, "thumbnail not found")
    return FileResponse(path, media_type="image/jpeg")