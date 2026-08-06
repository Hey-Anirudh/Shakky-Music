# api/run.py
# Launch the Shakky Music fetch API:  python -m api.run
# (or:  uvicorn api.main:app --host 0.0.0.0 --port 8300)

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [api] %(message)s",
)

from . import config  # noqa: E402


def main():
    import uvicorn

    print(
        f"\n  Shakky Music Fetch API\n"
        f"  listening on {config.API_HOST}:{config.API_PORT}\n"
        f"  cookies: {config.COOKIES_FILE or 'NONE (public)'}\n"
        f"  data dir: {config.DATA_DIR}\n"
        "  -------------------------------\n"
        f"  GET /api/search?q=...           search tracks\n"
        f"  GET /api/track?id_or_url        full metadata + formats\n"
        f"  GET /api/media/{{vidid}}          stream audio (Range-aware)\n"
        f"  GET /api/download/{{vidid}}       download file\n"
        f"  GET /api/playlist?url=...       playlist tracks\n"
        f"  GET /api/thumb/{{vidid}}          thumbnail image\n"
        f"  GET /api/health\n"
    )
    uvicorn.run(
        "api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
        log_level="warning",
    )


if __name__ == "__main__":
    sys.exit(main())
