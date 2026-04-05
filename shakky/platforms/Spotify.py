import re

import spotipy
import asyncio
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
                print(f"FAILED TO INITIALIZE SPOTIFY: {e}")
                self.spotify = None
        else:
            self.spotify = None

    async def valid(self, link: str):
        if not self.spotify:
            return False
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def track(self, link: str):
        if not self.spotify:
            raise Exception("Spotify credentials not configured in config.py")
        
        logger.info(f"Resolving Spotify track: {link}")
        # Run sync spotipy call in a thread to avoid blocking the event loop
        try:
            track = await asyncio.to_thread(self.spotify.track, link)
        except Exception as e:
            logger.error(f"Spotify track resolution failed: {e}")
            raise
            
        info = track["name"]
        for artist in track["artists"]:
            fetched = f' {artist["name"]}'
            if "Various Artists" not in fetched:
                info += fetched
        
        logger.info(f"Searching YouTube for track: {info}")
        results = VideosSearch(info, limit=1)
        search_data = await results.next()
        
        if not search_data.get("result"):
             raise Exception(f"No YouTube result found for: {info}")
             
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
        if not self.spotify:
            raise Exception("Spotify credentials not configured or invalid.")
        
        logger.info(f"Fetching Spotify playlist: {url}")
        try:
            # Run sync spotipy call in a thread
            playlist = await asyncio.to_thread(self.spotify.playlist, url)
        except Exception as e:
            logger.error(f"Spotify playlist fetch failed: {e}")
            raise Exception(f"Spotify API Error: {e}")
        
        playlist_id = playlist["id"]
        results = []
        for item in playlist["tracks"]["items"]:
            music_track = item["track"]
            if not music_track:
                continue
            info = music_track["name"]
            for artist in music_track["artists"]:
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
            
        logger.info(f"Loaded {len(results)} tracks from playlist {playlist_id}")
        return results, playlist_id

    async def album(self, url):
        if not self.spotify:
            raise Exception("Spotify credentials not configured in config.py")
            
        logger.info(f"Fetching Spotify album: {url}")
        try:
            album = await asyncio.to_thread(self.spotify.album, url)
        except Exception as e:
            logger.error(f"Spotify album fetch failed: {e}")
            raise
            
        album_id = album["id"]
        results = []
        for item in album["tracks"]["items"]:
            info = item["name"]
            for artist in item["artists"]:
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
            
        logger.info(f"Loaded {len(results)} tracks from album {album_id}")
        return results, album_id

    async def artist(self, url):
        if not self.spotify:
            raise Exception("Spotify credentials not configured in config.py")
            
        logger.info(f"Fetching Spotify artist: {url}")
        try:
            artistinfo = await asyncio.to_thread(self.spotify.artist, url)
            artisttoptracks = await asyncio.to_thread(self.spotify.artist_top_tracks, url)
        except Exception as e:
            logger.error(f"Spotify artist fetch failed: {e}")
            raise
            
        artist_id = artistinfo["id"]
        results = []
        for item in artisttoptracks["tracks"]:
            info = item["name"]
            for artist in item["artists"]:
                fetched = f' {artist["name"]}'
                if "Various Artists" not in fetched:
                    info += fetched
            results.append(info)
            
        logger.info(f"Loaded {len(results)} top tracks for artist {artist_id}")
        return results, artist_id
