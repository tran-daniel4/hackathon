from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from db.session import engine
from cache.redis import close_pool

load_dotenv()



@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()
    await close_pool()


app = FastAPI(title="Agentic System Diagrammer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
