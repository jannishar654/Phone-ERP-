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

# Register routes
app.include_router(api_router)

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
