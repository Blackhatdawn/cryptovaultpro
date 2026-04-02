import uvicorn
from server import app
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        workers=settings.workers,
        log_level=settings.log_level.lower()
    )
