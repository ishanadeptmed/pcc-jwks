from fastapi import FastAPI
# from fastapi.middleware.openssl import SessionMiddleware # Simulates the Starlette session middleware
from starlette.middleware.sessions import SessionMiddleware
from app.routes import router as fhir_router

app = FastAPI(title="My SMART on FHIR Application")

# Add the session middleware. 
# "secret-key" is used to encrypt the cookie. Change this to a random string in production!
app.add_middleware(SessionMiddleware, secret_key="your-super-secret-encryption-key")

@app.get("/")
async def root():
    return {"status": "Application is running", "modes": ["/launch", "/callback"]}

# Include your routes after the middleware is configured
app.include_router(fhir_router)