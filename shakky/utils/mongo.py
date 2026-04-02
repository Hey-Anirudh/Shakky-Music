"""**                                                                      
────────────────────────────────────────────────────────────────────────
     ____.  _____ ______________   ____.___  _________
    |    | /  _  \\______   \   \ /   /|   |/   _____/
    |    |/  /_\  \|       _/\   Y   / |   |\_____  \ 
/\__|    /    |    \    |   \ \     /  |   |/        \
\________\____|__  /____|_  /  \___/   |___/_______  /
                 \/       \/                       \/ 
────────────────────────────────────────────────────────────────────────**"""







from typing import Dict, Union

from motor.motor_asyncio import AsyncIOMotorClient as MongoCli

from config import MONGO_DB_URI

mongo = MongoCli(MONGO_DB_URI)
db = mongo.Ani

coupledb = db.couple


afkdb = db.afk

nightmodedb = db.nightmode

notesdb = db.notes

filtersdb = db.filters
contributorsdb = db.contributors

async def add_contributor(user_id: int):
    """Add or increment contribution count for a user"""
    await contributorsdb.update_one(
        {"user_id": user_id},
        {"$inc": {"count": 1}},
        upsert=True
    )

async def get_top_contributors(limit: int = 10):
    """Get the list of top contributors"""
    cursor = contributorsdb.find().sort("count", -1).limit(limit)
    return await cursor.to_list(length=limit)
    lovers = await coupledb.find_one({"chat_id": cid})
    if lovers:
        lovers = lovers["couple"]
    else:
        lovers = {}
    return lovers

async def _get_image(cid: int):
    lovers = await coupledb.find_one({"chat_id": cid})
    if lovers:
        lovers = lovers["img"]
    else:
        lovers = {}
    return lovers

async def get_couple(cid: int, date: str):
    lovers = await _get_lovers(cid)
    if date in lovers:
        return lovers[date]
    else:
        return False


async def save_couple(cid: int, date: str, couple: dict, img: str):
    lovers = await _get_lovers(cid)
    lovers[date] = couple
    await coupledb.update_one(
        {"chat_id": cid},
        {"$set": {"couple": lovers, "img": img}},
        upsert=True,
    )
