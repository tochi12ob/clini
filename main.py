from datetime import datetime
from typing import Optional
from fastapi import FastAPI
import uvicorn
from fastapi.responses import JSONResponse, Response
from fastapi import Request, Form
import logging
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import database to ensure it's initialized with the correct DATABASE_URL
import database

# Set up proper logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import routes

from routes.appointments import router as calender_router
from routes.auth import router as clinic_router
from routes.agent_setup_routes import router as agent_setup_router
from routes.webhook_generator_routes import router as webhook_gen_router
from routes.webhook_tools_routes import router as webhook_tools_router

# Initialize FastAPI app
app = FastAPI(
    title="Clinic AI Assistant",
    description="AI-powered clinic management system",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React default port
        "http://localhost:5173",  # Vite default port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        # Add your production URLs here when deploying
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH","DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
app.include_router(calender_router, prefix="/Calender", tags=["calender"])
app.include_router(clinic_router, prefix="/clinic",tags=["clinic-registration"])
app.include_router(agent_setup_router, prefix="/api", tags=["Agent Setup"])
app.include_router(webhook_gen_router, prefix="", tags=["webhook-generator"])
app.include_router(webhook_tools_router, prefix="", tags=["webhook-tools"])

@app.get("/")
async def root():
    return {"message": "Clinic AI Assistant API", "docs": "/docs"}

@app.post("/")
async def handle_root_webhook(
    request: Request,
    CallSid: str = Form(...),
    AccountSid: Optional[str] = Form(None),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(...),
    Direction: Optional[str] = Form(None)
):
    """Handle webhook at root path - TEMPORARY FIX for misconfigured Twilio"""
    logger.info(f"ROOT WEBHOOK (FIX THIS IN TWILIO): CallSid={CallSid}, Status={CallStatus}, From={From}, To={To}")
    
    try:
        # Provide proper TwiML response
        twiml_response = """<?xml version='1.0' encoding='UTF-8'?>
<Response>
    <Say voice="alice">Hello and thank you for calling our clinic. How can I help you today?</Say>
    <Gather input="speech dtmf" action="/api/calls/process-input" method="POST" timeout="10" speechTimeout="auto">
        <Say voice="alice">Please tell me what you need help with, or press any key to speak with our staff.</Say>
    </Gather>
    <Say voice="alice">I didn't hear anything. Let me transfer you to our staff.</Say>
    <Dial>+1234567890</Dial>
</Response>"""
        
        return Response(
            content=twiml_response,
            media_type="application/xml",
            status_code=200,
            headers={
                "Cache-Control": "no-cache",
                "Connection": "close"
            }
        )
    except Exception as e:
        logger.error(f"Root webhook error: {str(e)}")
        # Return fallback TwiML
        fallback_twiml = """<?xml version='1.0' encoding='UTF-8'?>
<Response>
    <Say voice="alice">I'm sorry, we're experiencing technical difficulties. Please try calling back in a few minutes.</Say>
    <Hangup/>
</Response>"""
        
        return Response(
            content=fallback_twiml,
            media_type="application/xml",
            status_code=200
        )

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/status")
async def get_calls_status():
    """Status endpoint for external monitoring"""
    return {
        "status": "operational",
        "service": "calls-api",
        "timestamp": datetime.now().isoformat()
    }

# Add exception handler for better error responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)