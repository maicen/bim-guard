"""ASGI entrypoint for BIM Guard FastAPI Gateway."""

import os

import uvicorn

from app.logging_config import configure_logging
from app.main import app

if __name__ == "__main__":
    configure_logging()
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True, log_config=None)
