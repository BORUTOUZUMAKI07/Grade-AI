from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.core.config import settings, DEV_SECRET
from app.core.logging_config import setup_structured_logging
from app.core.exceptions import DomainException
from app.api.router import api_router
from app.db import models  # noqa: F401  (registers the tables)
from app.db.session import Base, engine

setup_structured_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.ENVIRONMENT == "production" and settings.SECRET_KEY == DEV_SECRET:
        raise RuntimeError("Set SECRET_KEY in the environment before running in production.")
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.PROJECT_NAME, version="2.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/")
async def root_index():
    return {"status": "online", "engine": "FastAPI Cyberpunk Analytics Gateway Router"}

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    return JSONResponse(status_code=exc.status_code, content={"error_code": exc.code, "reason": exc.message}, headers=exc.headers)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Only plain fields: raw exc.errors() can hold exception objects that JSON cannot encode.
    details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error_code": "VALIDATION_FAULT", "details": details})

if __name__ == "__main__":
    import uvicorn
    # Tied directly to your exact folder namespaces definition
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
