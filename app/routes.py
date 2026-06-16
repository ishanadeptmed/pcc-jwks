from collections import UserList
import json 
import os 
import tempfile
import requests

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="templates")

CLIENT_ID = "your-sandbox-client-id"
REDIRECT_URI = "http://localhost:8000/callback"

@router.get("/launch")
async def launch(request: Request, iss: str, launch: str = None):
    """
    Step 1: The Launch. We save the EHR state inside the user's encrypted session cookie.
    """
    smart_config_url = f"{iss.rstrip('/')}/.well-known/smart-configuration"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(smart_config_url)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch SMART configuration")
        config = response.json()
        
    auth_url = config.get("authorization_endpoint")
    token_url = config.get("token_endpoint")
    
    # SUCCESS: Storing parameters securely inside this specific user's browser cookie session
    request.session["token_url"] = token_url
    request.session["fhir_url"] = iss

    scopes = "launch patient/Patient.read patient/Observation.read openid profile"
    redirect_target = (
        f"{auth_url}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&scope={scopes}&launch={launch}&aud={iss}"
    )
    return RedirectResponse(url=redirect_target)


@router.get("/callback")
async def callback(
    request: Request,
    code: Optional[str] = None, 
    error: Optional[str] = None, 
    error_description: Optional[str] = None
):
    """
    Step 2: The Callback. We retrieve the endpoints from the user's session cookie.
    """
    if error or not code:
        desc = error_description or "No code returned from EHR."
        raise HTTPException(status_code=400, detail=f"EHR Error ({error}): {desc}")
        
    # SUCCESS: Fetching details from this specific user's session
    token_url = request.session.get("token_url")
    fhir_base_url = request.session.get("fhir_url")
    
    if not token_url or not fhir_base_url:
        raise HTTPException(status_code=400,detail=f"Session missing! token_url: {token_url}, fhir_url: {fhir_base_url}.")
        
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID
    }
    
    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=payload)
        if token_response.status_code != 200:
            raise HTTPException(status_code=400,detail=f"Token exchange failed with status {token_response.status_code}. Response: {token_response.text}")
            
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        patient_id = tokens.get("patient") 

        # Optional: Save these into the session too if you need to build other pages later
        request.session["access_token"] = access_token
        request.session["patient_id"] = patient_id

        headers = {"Authorization": f"Bearer {access_token}"}

        # Query Patient Demographics
        patient_data_resp = await client.get(f"{fhir_base_url}/Patient/{patient_id}", headers=headers)
        if patient_data_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Patient demographics")
        patient_json = patient_data_resp.json()

        # Query Observations
        obs_url = f"{fhir_base_url}/Observation?patient={patient_id}&category=vital-signs,laboratory"
        obs_resp = await client.get(obs_url, headers=headers)
        obs_json = obs_resp.json().get("entry", []) if obs_resp.status_code == 200 else []

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "patient": patient_json, 
            "observations": obs_json
        }
    )


@router.get("/fetch-patient/{patient_id}")
def fetch_and_save_patient_data(patient_id: str):

    #1.taking base User
    FHIR_BASE_URL = "https://lforms-smart-fhir.nlm.nih.gov/v/r4/fhir"

    #As we want everything what a patient has base + patient_id + $everything 
    fhir_url = f"{FHIR_BASE_URL}/Patient/{patient_id}/$everything"

    #2.getting data
    try:
        response = requests.get(fhir_url, timeout=10)

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"FHIR server returned error {response.status_code}: {response.text}",
            )
        patient_bundle = response.json()

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to the FHIR server: {str(e)}",
        )
    
    #3.saving the file to temp

    try:
        temp_dir = tempfile.gettempdir()
        file_name = f"patient_{patient_id}_data.json"
        file_path = os.path.join(temp_dir, file_name)

        # Write the JSON data with pretty print indentation
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(patient_bundle, f, indent=4)

    except IOError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to write data to disk: {str(e)}"
        )
    
    # 4. Return success metadata
    return {
        "status": "success",
        "message": f"Patient data successfully cached locally",
        "saved_at_path": file_path,
        "resource_count": len(patient_bundle.get("entry", [])),
    }
