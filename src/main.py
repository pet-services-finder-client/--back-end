from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware

from src.admin.auth import AdminAuth
from src.api.v1.router import api_router
from src.core.config import settings
from src.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    yield
    print("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Required by sqladmin to store login state in a cookie
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_PREFIX) 


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


admin = Admin(
    app,
    engine,
    authentication_backend=AdminAuth(secret_key=settings.SECRET_KEY),
    base_url="/admin",
    title="Pawly Admin",
)

# Register admin views
##deliberately at the end, rather than at the top of the file. Why: to avoid circular imports.
from src.admin.views import AnimalTypeAdmin,UserAdmin 
admin.add_view(UserAdmin)
admin.add_view(AnimalTypeAdmin)
