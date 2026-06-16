import os
import json
import time
import base64
import requests
import jwt
from fastapi import FastAPI, HTTPException
from cryptography.hazmat.primitives import serialization

app = FastAPI(title="PCC Bulk FHIR Integration")

TOKEN_URL = "https://connect.pointclickcare.com/fhir/oauth/token"
JWKS_FILE = os.getenv("JWKS_FILE", "jwks.json")
CLIENT_ID = os.getenv("CLIENT_ID")
PRIVATE_KEY_B64 = os.getenv("PRIVATE_KEY_B64")

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
# Load private key (FIXED FOR RENDER)
# -------------------------
def load_private_key():
    if not PRIVATE_KEY_B64:
        raise Exception("Missing PRIVATE_KEY_B64 environment variable")

    key_bytes = base64.b64decode(PRIVATE_KEY_B64)

    return serialization.load_pem_private_key(
        key_bytes,
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
# Get Access Token
# -------------------------
@app.get("/token")
def get_token():
    try:
        client_assertion = create_jwt()

        data = {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": client_assertion,
            "scope": "openid system/*.read system/Group.write"
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.post(TOKEN_URL, data=data, headers=headers)

        if response.status_code != 200:
            return {
                "status": "FAILED",
                "code": response.status_code,
                "text": response.text
            }

        return response.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug-jwt")
def debug_jwt():
    return {
        "client_id": CLIENT_ID,
        "aud": TOKEN_URL,
        "kid": "pcc-key-1"
    }