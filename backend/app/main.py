from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.endpoints import router as api_router
from app.config.settings import settings
import uvicorn

app = FastAPI(
    title="PhoneERP API",
    description="AI-powered PhoneERP application backend to extract action cards from phone audio transcripts.",
    version="1.0.0"
)

# CORS setup
origins = settings.CORS_ORIGINS

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

# Register routes
app.include_router(api_router)
app.include_router(telegram_router)
app.include_router(twilio_whatsapp_router)
app.include_router(access_router)
app.include_router(staff_router)
app.include_router(public_router)
app.include_router(auth_router)
app.include_router(invites_router)

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
