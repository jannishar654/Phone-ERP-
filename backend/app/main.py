from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.endpoints import router as api_router
from app.config.settings import settings
import uvicorn
import logging
import uuid

from fastapi.responses import JSONResponse

app = FastAPI(
    title="PhoneERP API",
    description="AI-powered PhoneERP application backend to extract action cards from phone audio transcripts.",
    version="1.0.0"
)

logger = logging.getLogger(__name__)

from fastapi import Request

# CORS setup
origins = settings.CORS_ORIGINS

@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    path = request.url.path
    try:
        response = await call_next(request)
    except Exception as exc:
        if not path.startswith("/customer"):
            raise
        request_id = uuid.uuid4().hex[:12]
        logger.exception(
            "Customer portal request failed request_id=%s path=%s error_type=%s",
            request_id,
            path,
            type(exc).__name__,
        )
        response = JSONResponse(
            status_code=503,
            content={
                "detail": "Customer portal is temporarily unavailable. Please retry.",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )
    if (
        path.startswith("/orders")
        or path.startswith("/action-cards")
        or path.startswith("/staff/orders")
        or path.startswith("/customer")
        or path.startswith("/owner-notifications")
    ):
        response.headers["Cache-Control"] = "no-store"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routes.telegram import router as telegram_router
from app.routes.twilio_whatsapp import router as twilio_whatsapp_router
from app.routes.access import router as access_router
from app.routes.staff import router as staff_router
from app.routes.public import router as public_router
from app.routes.auth import router as auth_router
from app.routes.invites import router as invites_router
from app.routes.customer import router as customer_router
from app.routes.customer_requests import router as customer_requests_router
from app.routes.owner_notifications import router as owner_notifications_router
from app.routes.meta_whatsapp import router as meta_whatsapp_router

# Register routes
app.include_router(api_router)
app.include_router(telegram_router)
app.include_router(twilio_whatsapp_router)
app.include_router(access_router)
app.include_router(staff_router)
app.include_router(public_router)
app.include_router(auth_router)
app.include_router(invites_router)
app.include_router(customer_router)
app.include_router(customer_requests_router)
app.include_router(owner_notifications_router)
app.include_router(meta_whatsapp_router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the PhoneERP Backend.",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )
