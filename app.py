"""
Rebekko Attendance System - FastAPI Server

A professional web application for managing and analyzing school attendance data.
This FastAPI server serves static files and provides API endpoints for future features.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx

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


@app.get("/oauth-callback")
async def oauth_callback():
    """
    OAuth callback handler - serves the callback page that communicates with parent window
    """
    return FileResponse('static/oauth-callback.html')


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring
    """
    return {"status": "healthy", "service": "rebekko-attendance"}


@app.get("/api/oauth/config")
async def get_oauth_config():
    """
    Get public OAuth configuration (no secrets)
    Frontend uses this to avoid hardcoding client ID
    """
    return {
        "clientId": GOOGLE_CLIENT_ID,
        "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
        "authorizationEndpoint": "https://accounts.google.com/o/oauth2/v2/auth",
        "tokenEndpoint": "https://oauth2.googleapis.com/token",
        "redirectUri": "/oauth-callback",
        "usePKCE": True
    }


# Google OAuth Configuration (server-side only)
# Client ID is public and can be hardcoded
GOOGLE_CLIENT_ID = "572268474022-54j1dba72gm26n00oi42ijrhv3ielep1.apps.googleusercontent.com"
# Client Secret MUST be set as environment variable on Render
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

if not GOOGLE_CLIENT_SECRET:
    print("WARNING: GOOGLE_CLIENT_SECRET environment variable not set. OAuth will not work.")


# Request models for OAuth endpoints
class TokenExchangeRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


@app.post("/api/oauth/token")
async def exchange_oauth_token(request: TokenExchangeRequest):
    """
    Exchange authorization code for access token.
    Client secret is kept secure on the server side.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": request.code,
                    "code_verifier": request.code_verifier,
                    "grant_type": "authorization_code",
                    "redirect_uri": request.redirect_uri
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            if response.status_code != 200:
                error_data = response.json()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_data
                )

            return response.json()

    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"OAuth token exchange failed: {str(e)}")


@app.post("/api/oauth/refresh")
async def refresh_oauth_token(request: TokenRefreshRequest):
    """
    Refresh an expired access token.
    Client secret is kept secure on the server side.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "refresh_token": request.refresh_token,
                    "grant_type": "refresh_token"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            if response.status_code != 200:
                error_data = response.json()
                raise HTTPException(
                    status_code=response.status_code,
                    detail=error_data
                )

            return response.json()

    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"OAuth token refresh failed: {str(e)}")


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
