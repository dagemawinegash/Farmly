from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.auth import router as auth_router
from src.api.routes.chat import router as chat_router
from src.api.routes.debug import router as debug_router
from src.api.routes.health import router as health_router
from src.api.routes.profile import router as profile_router
from src.config.settings import get_settings
from src.db.base import Base
from src.db.session import engine
from src.db import models 


settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(debug_router)
