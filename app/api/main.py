from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from db.session import engine  # noqa: E402
from cache.redis import close_pool  # noqa: E402



@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()
    await close_pool()


app = FastAPI(title="Agentic System Diagrammer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, # HANDLE THIS LATER
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
