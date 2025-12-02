"""
Rebekko Attendance System - FastAPI Server

A professional web application for managing and analyzing school attendance data.
This FastAPI server serves static files and provides API endpoints for future features.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

# Initialize FastAPI app
app = FastAPI(
    title="Rebekko Attendance System",
    description="Sistema web per la gestione e l'analisi delle presenze scolastiche",
    version="1.0.0"
)

# CORS middleware (for development and Google OAuth)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """
    Serve the main application page
    """
    return FileResponse('static/index.html')


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    """
    return {"status": "healthy", "service": "rebekko-attendance"}


# Future API endpoints will go here
# Example:
# @app.get("/api/courses")
# async def get_courses():
#     return {"courses": [...]}


if __name__ == "__main__":
    import uvicorn

    # Get port from environment variable (Render sets this)
    port = int(os.environ.get("PORT", 8080))

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=True  # Auto-reload on code changes (development only)
    )
