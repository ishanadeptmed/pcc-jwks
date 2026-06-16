import os
import json
import time
import requests
import jwt
from fastapi import FastAPI, HTTPException
from cryptography.hazmat.primitives import serialization

app = FastAPI(title="PCC Bulk FHIR Integration")

TOKEN_URL = "https://preview.pointclickcare.com/auth/oauth/v2/token"
JWKS_FILE = os.getenv("JWKS_FILE", "jwks.json")
CLIENT_ID = os.getenv("CLIENT_ID")

# -------------------------
# Load JWKS
# -------------------------
def load_jwks():
    with open(JWKS_FILE, "r") as f:
        return json.load(f)

@app.get("/.well-known/jwks.json")
def jwks():
    return load_jwks()

# -------------------------
# Load private key
# -------------------------
def load_private_key():
    with open("private_key.pem", "rb") as f:
        return serialization.load_pem_private_key(
            f.read(),
            password=None
        )

# -------------------------
# Create JWT
# -------------------------
def create_jwt():
    private_key = load_private_key()

    now = int(time.time())

    payload = {
        "iss": CLIENT_ID,
        "sub": CLIENT_ID,
        "aud": TOKEN_URL,
        "exp": now + 300,
        "jti": str(now)
    }

    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS384",
        headers={"kid": "pcc-key-1"}
    )

    return token

# -------------------------
# Get Access Token (FIXED)
# -------------------------
@app.get("/token")
def get_token():
    try:
        client_assertion = create_jwt()

        data = {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.post(TOKEN_URL, data=data, headers=headers)

        # DEBUG (important)
        if response.status_code != 200:
            return {
                "status": "FAILED",
                "code": response.status_code,
                "text": response.text
            }

        return response.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))