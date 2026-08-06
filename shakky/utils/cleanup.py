import os
import shutil
import asyncio
import logging
import time
from shakky.misc import db

LOGGER = logging.getLogger(__name__)

# Paths to clean periodically
CLEAN_DIRECTORIES = ["downloads", "playback"]

# Thumbnail cache lives inside downloads but must be pruned too (older than
# a different age since thumbs are cheap to regenerate).
THUMB_DIRECTORY = "downloads/thumbs"
THUMB_MAX_AGE_HOURS = float(os.getenv("CLEANUP_THUMBS_MAX_AGE", "1"))

# Tuning (override via config)
CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "30"))
CLEANUP_MAX_AGE_HOURS = float(os.getenv("CLEANUP_MAX_AGE_HOURS", "2"))
CLEANUP_FIRST_DELAY_SECONDS = int(os.getenv("CLEANUP_FIRST_DELAY_SECONDS", "60"))

SKIP_ITEMS = {"thumbs", "thumbnails", "thumbs.db", ".gitkeep"}


def _collect_active_files() -> set:
    """Collect every file currently referenced by any chat's queue."""
    active = set()
    try:
        for chat_id in db:
            queue = db.get(chat_id, [])
            for song in queue:
                file_path = song.get("file")
                if file_path and isinstance(file_path, str):
                    active.add(os.path.abspath(file_path))
    except Exception as e:
        LOGGER.error(f"Error collecting active files for cleanup: {e}")
    return active


def _clean_directory(directory: str, active_files: set, max_age_seconds: float) -> int:
    """Delete stale files/dirs in `directory`. Returns count deleted."""
    if not os.path.exists(directory):
        return 0

    deleted = 0
    now = time.time()
    for item in os.listdir(directory):
        if item in SKIP_ITEMS or item.startswith("."):
            continue

        item_path = os.path.abspath(os.path.join(directory, item))
        if item_path in active_files:
            continue

        try:
            if os.path.isfile(item_path):
                if now - os.path.getmtime(item_path) < max_age_seconds:
                    continue
                os.unlink(item_path)
                deleted += 1
            elif os.path.isdir(item_path):
                if now - os.path.getmtime(item_path) < max_age_seconds:
                    continue
                shutil.rmtree(item_path)
                deleted += 1
        except Exception as e:
            LOGGER.warning(f"Failed to delete {item_path}: {e}")
    return deleted


def _run_cleanup_once() -> int:
    """One full cleanup pass. Returns total files deleted."""
    active_files = _collect_active_files()
    max_age_seconds = CLEANUP_MAX_AGE_HOURS * 3600

    total = 0
    for directory in CLEAN_DIRECTORIES:
        total += _clean_directory(directory, active_files, max_age_seconds)
    # Prune the thumbnail cache separately (it is skipped by the main pass)
    if THUMB_DIRECTORY and os.path.isdir(THUMB_DIRECTORY):
        total += _clean_directory(THUMB_DIRECTORY, set(), THUMB_MAX_AGE_HOURS * 3600)
    return total


async def start_cleaning():
    """Background task: clean downloaded files every CLEANUP_INTERVAL_MINUTES.

    First pass runs shortly after startup, then periodically. Files in the
    current queue and files newer than CLEANUP_MAX_AGE_HOURS are protected.
    """
    await asyncio.sleep(CLEANUP_FIRST_DELAY_SECONDS)
    while True:
        try:
            LOGGER.info(
                "Starting cleanup (interval=%sm, max_age=%sh)...",
                CLEANUP_INTERVAL_MINUTES, CLEANUP_MAX_AGE_HOURS,
            )
            deleted = await asyncio.to_thread(_run_cleanup_once)
            LOGGER.info(f"Cleanup completed: {deleted} stale file(s) removed.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            LOGGER.error(f"Error in background cleanup task: {e}")

        try:
            await asyncio.sleep(CLEANUP_INTERVAL_MINUTES * 60)
        except asyncio.CancelledError:
            break


async def run_cleanup_now():
    """Immediately run one cleanup pass, protecting active files."""
    deleted = await asyncio.to_thread(_run_cleanup_once)
    LOGGER.info(f"Manual cleanup removed {deleted} stale file(s).")
    return deleted
