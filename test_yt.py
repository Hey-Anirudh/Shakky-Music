import httpx

original_init = httpx.AsyncClient.__init__

def patched_init(self, *args, **kwargs):
    if 'proxies' in kwargs:
        prox = kwargs.pop('proxies')
        if prox is not None:
            kwargs['proxy'] = prox
    original_init(self, *args, **kwargs)

httpx.AsyncClient.__init__ = patched_init

from youtubesearchpython.__future__ import VideosSearch
import asyncio

async def main():
    r = await VideosSearch('Majboor', limit=1).next()
    print(r.get("result", [{}])[0].get("duration"))

asyncio.run(main())
