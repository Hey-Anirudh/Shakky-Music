import os
import shutil
import asyncio
import logging
import time
from shakky.misc import db

LOGGER = logging.getLogger(__name__)

# Paths to clean periodically
CLEAN_DIRECTORIES = ["downloads", "playback"]

async def start_cleaning():
    """Background task to clean up downloaded files every 30 minutes."""
    # Delay first run a bit after startup
    await asyncio.sleep(60)
    while True:
        try:
            # Wait 30 minutes (1800 seconds)
            await asyncio.sleep(1800)
            
            LOGGER.info("Starting periodic cleanup (active file protection enabled)...")
            
            # --- Collect all active files from the queue ---
            active_files = set()
            try:
                for chat_id in db:
                    queue = db.get(chat_id, [])
                    for song in queue:
                        file_path = song.get("file")
                        if file_path and isinstance(file_path, str):
                            active_files.add(os.path.abspath(file_path))
            except Exception as e:
                LOGGER.error(f"Error collecting active files for cleanup: {e}")

            now = time.time()
            # Only delete files older than 2 hours (avoid deleting fresh downloads)
            max_age_seconds = 7200 
            
            for directory in CLEAN_DIRECTORIES:
                if not os.path.exists(directory):
                    continue
                
                # List items in directory
                for item in os.listdir(directory):
                    item_path = os.path.abspath(os.path.join(directory, item))
                    
                    # Safety check: don't delete .gitkeep, thumbs folder, etc
                    if item.startswith(".") or item == "thumbs":
                        continue
                        
                    # Skip if currently in use
                    if item_path in active_files:
                        # LOGGER.debug(f"Skipping active file: {item}")
                        continue
                        
                    try:
                        # Skip if file was recently created (within last 2 hours)
                        if os.path.isfile(item_path):
                            if now - os.path.getmtime(item_path) < max_age_seconds:
                                continue
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            # For folders, we check if ANY file inside is active before deleting
                            # Though usually downloads is flat except for thumbs/ which we skip.
                            shutil.rmtree(item_path)
                    except Exception as e:
                        LOGGER.warning(f"Failed to delete {item_path}: {e}")
            
            LOGGER.info("Periodic cleanup completed successfully.")
            
        except asyncio.CancelledError:
            # Task is being stopped
            break
        except Exception as e:
            LOGGER.error(f"Error in background cleanup task: {e}")
            # Wait a bit before retrying if there's an error
            await asyncio.sleep(60)

# Optional: Manual trigger
async def run_cleanup_now():
    """Immediately runs the cleanup routine once, protecting active files."""
    active_files = set()
    try:
        for chat_id in db:
            queue = db.get(chat_id, [])
            for song in queue:
                file_path = song.get("file")
                if file_path and isinstance(file_path, str):
                    active_files.add(os.path.abspath(file_path))
    except Exception as e:
        LOGGER.error(f"Error collecting active files for manual cleanup: {e}")

    for directory in CLEAN_DIRECTORIES:
        if os.path.exists(directory):
            for item in os.listdir(directory):
                if item.startswith(".") or item == "thumbs":
                    continue
                item_path = os.path.abspath(os.path.join(directory, item))
                
                # Skip if currently in use
                if item_path in active_files:
                    continue
                    
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except:
                    pass
