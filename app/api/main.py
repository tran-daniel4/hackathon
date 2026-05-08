from dotenv import load_dotenv

load_dotenv()  # must run before other imports so env vars are set when modules initialize

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.session import engine
from cache.redis import close_pool
from core.config import settings
from endpoints.auth import router as auth_router
from endpoints.analyze import router as analyze_router
from endpoints.repos import router as repos_router
from endpoints.teams import router as teams_router
from endpoints.profiles import router as profiles_router

@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()
    await close_pool()

app = FastAPI(title="Agentic System Diagrammer API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(analyze_router)
app.include_router(repos_router)
app.include_router(teams_router)
app.include_router(profiles_router)

@app.get("/health")
def health():
    return {"status": "ok"}
