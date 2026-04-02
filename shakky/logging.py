import logging

import sys

# Windows-safe stdout wrapper to avoid UnicodeEncodeError
class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # If the stream is a console, it might fail on certain characters
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                # Fallback: encode and decode with replace to drop/replace bad chars
                safe_msg = msg.encode(sys.stdout.encoding or 'ascii', errors='backslashreplace').decode(sys.stdout.encoding or 'ascii')
                stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        logging.FileHandler("log.txt", encoding='utf-8'),
        SafeStreamHandler(),
    ],
)

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
# pytgcalls removed — bot streams to WebApp only


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
