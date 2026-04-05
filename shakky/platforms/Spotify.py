import re

import spotipy
import asyncio
import aiohttp
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython.__future__ import VideosSearch
import logging

logger = logging.getLogger("shakky.spotify")

import config


class SpotifyAPI:
    def __init__(self):
        self.regex = r"^(https:\/\/open.spotify.com\/)(.*)$"
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.client_secret = config.SPOTIFY_CLIENT_SECRET
        if config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET:
            try:
                self.client_credentials_manager = SpotifyClientCredentials(
                    self.client_id, self.client_secret
                )
                self.spotify = spotipy.Spotify(
                    client_credentials_manager=self.client_credentials_manager
                )
            except Exception as e:
                logger.warning(f"FAILED TO INITIALIZE SPOTIFY API (Premium/Credentials issue): {e}")
                self.spotify = None
        else:
            self.spotify = None
        
        self.session = None # Lazy initialized aiohttp session

    async def valid(self, link: str):
        return bool(re.search(self.regex, link))

    async def _get_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            })
        return self.session

    async def _scrape_meta(self, url: str):
        """Scrapes Spotify metadata from the public HTML or embed page."""
        try:
            # 1. Prepare embed URL for cleaner scraping
            resource_id = url.split("/")[-1].split("?")[0]
            resource_type = "playlist"
            if "/track/" in url: resource_type = "track"
            elif "/album/" in url: resource_type = "album"
            elif "/artist/" in url: resource_type = "artist"
            
            embed_url = f"https://open.spotify.com/embed/{resource_type}/{resource_id}"
            
            session = await self._get_session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9"
            }
            
            logger.info(f"Scraping embed URL: {embed_url}")
            async with session.get(embed_url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning(f"Spotify embed fetch failed with status {resp.status}")
                    return None
                html = await resp.text()

            # 2. Extract Tracks and Artists
            results = []
            
            # Pattern for Individual Tracks in the list (JSON format in state)
            # We look for "name":"..." followed by "artists":[...]
            # More robust regex that doesn't strictly depend on "duration" following immediately
            items = re.findall(r'{"name":"([^"]+)","artists":\[(.*?)\],', html)
            
            logger.info(f"Regex found {len(items)} raw matches in embed HTML.")
            
            if items:
                for name, artists_raw in items:
                    artists = re.findall(r'"name":"([^"]+)"', artists_raw)
                    artists = [a for a in artists if "Various Artists" not in a]
                    track_info = f"{name} {' '.join(artists)}".strip()
                    if track_info and track_info not in results:
                        results.append(track_info)
            
            # Fallback Pattern 1: Meta tags for single tracks or titles
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            title = title_match.group(1) if title_match else "Unknown Spotify Content"
            
            if not results:
                if title_match:
                    name = title_match.group(1)
                    # For tracks, og:title is often "Song - Single by Artist" or similar
                    results.append(name.replace(" - Single", "").replace(" album by ", " ").strip())

            # 3. Final cleanup of common HTML residue/artifacts
            results = [re.sub(r'&#[0-9]+;', ' ', r).strip() for r in results]
            
            return {
                "tracks": results,
                "title": title,
                "type": resource_type,
                "id": resource_id
            }
        except Exception as e:
            logger.error(f"Scraper totally failed for {url}: {e}")
            return None

    async def track(self, link: str):
        logger.info(f"Resolving Spotify track: {link}")
        track_name = None
        
        # 1. Try API first
        if self.spotify:
            try:
                track = await asyncio.to_thread(self.spotify.track, link)
                track_name = track["name"]
                for artist in track["artists"]:
                    fetched = f' {artist["name"]}'
                    if "Various Artists" not in fetched:
                        track_name += fetched
            except Exception as e:
                logger.warning(f"Spotify API track resolution failed (possibly 403): {e}. Trying scraper...")

        # 2. Try Scraper Fallback
        if not track_name:
            data = await self._scrape_meta(link)
            if data:
                track_name = data["title"]
                # Clean up title if it contains " - playlist by..."
                if " - playlist by" in track_name:
                    track_name = track_name.split(" - playlist by")[0]
            
        if not track_name:
            raise Exception("Failed to resolve Spotify track (API 403 and Scraper failed).")
            
        logger.info(f"Searching YouTube for track: {track_name}")
        results = VideosSearch(track_name, limit=1)
        search_data = await results.next()
        
        if not search_data.get("result"):
             raise Exception(f"No YouTube result found for: {track_name}")
             
        for result in search_data["result"]:
            ytlink = result["link"]
            title = result["title"]
            vidid = result["id"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        
        track_details = {
            "title": title,
            "link": ytlink,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def playlist(self, url):
        logger.info(f"Fetching Spotify playlist: {url}")
        results = []
        playlist_id = "unknown"

        # 1. Try API first
        if self.spotify:
            try:
                playlist = await asyncio.to_thread(self.spotify.playlist, url)
                playlist_id = playlist["id"]
                for item in playlist["tracks"]["items"]:
                    music_track = item["track"]
                    if not music_track: continue
                    info = music_track["name"]
                    for artist in music_track["artists"]:
                        fetched = f' {artist["name"]}'
                        if "Various Artists" not in fetched:
                            info += fetched
                    results.append(info)
            except Exception as e:
                logger.warning(f"Spotify API playlist fetch failed (possibly 403): {e}. Trying scraper...")

        # 2. Try Scraper Fallback
        if not results:
            data = await self._scrape_meta(url)
            if data and data.get("tracks"):
                results = data["tracks"]
                logger.info(f"Scraper found {len(results)} tracks for playlist.")
            else:
                raise Exception("Failed to fetch playlist items (API 403 and Scraper failed).")
        
        logger.info(f"Loaded {len(results)} tracks from playlist {playlist_id}")
        return results, playlist_id

    async def album(self, url):
        logger.info(f"Fetching Spotify album: {url}")
        results = []
        album_id = "unknown"

        # 1. Try API
        if self.spotify:
            try:
                album = await asyncio.to_thread(self.spotify.album, url)
                album_id = album["id"]
                for item in album["tracks"]["items"]:
                    info = item["name"]
                    for artist in item["artists"]:
                        fetched = f' {artist["name"]}'
                        if "Various Artists" not in fetched:
                            info += fetched
                    results.append(info)
            except Exception as e:
                logger.warning(f"Spotify API album fetch failed: {e}. Trying scraper...")

        # 2. Try Scraper
        if not results:
            data = await self._scrape_meta(url)
            if data and data.get("tracks"):
                results = data["tracks"]
            else:
                 raise Exception("Failed to fetch album items.")
            
        logger.info(f"Loaded {len(results)} tracks from album {album_id}")
        return results, album_id

    async def artist(self, url):
        logger.info(f"Fetching Spotify artist: {url}")
        results = []
        artist_id = "unknown"

        # 1. Try API
        if self.spotify:
            try:
                artistinfo = await asyncio.to_thread(self.spotify.artist, url)
                artisttoptracks = await asyncio.to_thread(self.spotify.artist_top_tracks, url)
                artist_id = artistinfo["id"]
                for item in artisttoptracks["tracks"]:
                    info = item["name"]
                    for artist in item["artists"]:
                        fetched = f' {artist["name"]}'
                        if "Various Artists" not in fetched:
                            info += fetched
                    results.append(info)
            except Exception as e:
                logger.warning(f"Spotify API artist fetch failed: {e}. Trying scraper...")

        # 2. Try Scraper
        if not results:
            data = await self._scrape_meta(url)
            if data and data.get("tracks"):
                 results = data["tracks"]
            else:
                 raise Exception("Failed to fetch artist top tracks.")
            
        logger.info(f"Loaded {len(results)} top tracks for artist {artist_id}")
        return results, artist_id
