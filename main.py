"""ASGI entrypoint for BIM Guard FastAPI Gateway."""

import uvicorn

from app.logging_config import configure_logging
from app.main import app

if __name__ == "__main__":
    configure_logging()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_config=None)
