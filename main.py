import os
import json
from fastapi import FastAPI, HTTPException, Query
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Optional: Load JWKS from file
JWKS_FILE = os.getenv("JWKS_FILE", "jwks.json")

# PCC Sandbox OAuth Endpoints
AUTH_URL = "https://preview.pointclickcare.com/auth/oauth/v2/authorize"
TOKEN_URL = "https://preview.pointclickcare.com/auth/oauth/v2/token"

app = FastAPI(title="PCC Sandbox Integration")


def load_jwks():
    """
    Load JWKS from jwks.json file.
    """
    try:
        with open(JWKS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "abc123",
                    "use": "sig",
                    "alg": "RS384",
                    "n": "YOUR_MODULUS_HERE",
                    "e": "AQAB"
                }
            ]
        }


@app.get("/")
def home():
    pcc_login_url = (
        f"{AUTH_URL}?"
        f"response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=api"
    )

    return {
        "message": "Welcome to your PCC Integration App",
        "login_url": pcc_login_url,
        "jwks_url": f"{REDIRECT_URI.rsplit('/callback', 1)[0]}/.well-known/jwks.json"
    }


@app.get("/.well-known/jwks.json")
def get_jwks():
    """
    Public endpoint PCC will use to retrieve your public key.
    """
    return load_jwks()


@app.get("/callback")
def callback(
    code: str = Query(None),
    error: str = Query(None)
):
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"PCC Login Error: {error}"
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Authorization code missing from redirect."
        )

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        response = requests.post(
            TOKEN_URL,
            data=payload,
            headers=headers,
            timeout=30
        )

        response_data = response.json()

        if response.status_code != 200:
            return {
                "status": "Failed to exchange token",
                "pcc_error": response_data
            }

        return {
            "status": "Successfully authenticated",
            "access_token": response_data.get("access_token"),
            "refresh_token": response_data.get("refresh_token"),
            "expires_in_seconds": response_data.get("expires_in")
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )