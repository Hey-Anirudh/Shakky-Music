import os
import shutil
import asyncio
import logging

LOGGER = logging.getLogger(__name__)

# Paths to clean periodically
CLEAN_DIRECTORIES = ["downloads"]

async def start_cleaning():
    """Background task to clean up downloaded files every 30 minutes."""
    # Delay first run a bit after startup
    await asyncio.sleep(60)
    while True:
        try:
            # Wait 30 minutes (1800 seconds)
            await asyncio.sleep(1800)
            
            LOGGER.info("Starting periodic cleanup of downloads folder...")
            
            for directory in CLEAN_DIRECTORIES:
                if not os.path.exists(directory):
                    continue
                
                # List items in directory
                for item in os.listdir(directory):
                    item_path = os.path.join(directory, item)
                    
                    # Safety check: don't delete .gitkeep or similar
                    if item.startswith("."):
                        continue
                        
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                            # LOGGER.debug(f"Deleted file: {item_path}")
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                            # LOGGER.debug(f"Deleted directory: {item_path}")
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
    """Immediately runs the cleanup routine once."""
    for directory in CLEAN_DIRECTORIES:
        if os.path.exists(directory):
            for item in os.listdir(directory):
                if item.startswith("."): continue
                item_path = os.path.join(directory, item)
                try:
                    if os.path.isfile(item_path): os.unlink(item_path)
                    elif os.path.isdir(item_path): shutil.rmtree(item_path)
                except: pass
