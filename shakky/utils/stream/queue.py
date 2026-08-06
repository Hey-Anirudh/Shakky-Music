import asyncio
from typing import Union

from shakky.misc import db
from shakky.utils.formatters import check_duration, seconds_to_min
from config import autoclean, time_to_seconds


async def put_queue(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    user_id,
    stream,
    forceplay: Union[bool, str] = None,
):
    """Queue helper (compat shim) delegating to the canonical stream.put_queue."""
    from shakky.utils.stream.stream import put_queue as _canonical
    return await _canonical(
        chat_id,
        original_chat_id,
        file,
        title,
        duration,
        user,
        vidid,
        user_id,
        stream,
        forceplay=forceplay,
    )
