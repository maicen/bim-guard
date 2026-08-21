import uvicorn
from app.compat.monsterui import ensure_monsterui_compat

ensure_monsterui_compat()

from app.logging_config import configure_logging
from app.main import app


if __name__ == "__main__":
    configure_logging()
    # log_config=None keeps our timestamped formatters instead of uvicorn's.
    uvicorn.run("app.main:app", host="0.0.0.0", reload=True, log_config=None)
