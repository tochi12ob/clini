"""
Agent Setup Routes for Clinic AI Assistant
Handles ElevenLabs agent management and outbound call endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Body, Request, Depends
import logging

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import os

from database import get_db
from services.agent_setup_service import agent_setup_service
from routes.auth import get_current_user, get_current_clinic
from models import CallType, CallStatus, Clinic, Call, KnowledgeBase
import requests
from routes.webhook_generator_routes import router as webhook_gen_router

router = APIRouter(prefix="/agent-setup", tags=["Agent Setup"])

# Pydantic models for request/response
class CreateAgentRequest(BaseModel):
    agent_name: Optional[str] = Field(None, description="Custom name for the agent")

class OutboundCallRequest(BaseModel):
    to_number: str = Field(..., description="Phone number to call")

class ImportPhoneNumberRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number to import")
    label: str = Field(..., description="Label for the phone number")
    twilio_sid: str = Field(..., description="Twilio Account SID")
    twilio_token: str = Field(..., description="Twilio Auth Token")

class UpdateAgentConfigRequest(BaseModel):
    agent_name: Optional[str] = Field(None, description="New agent name")
    ai_voice_id: Optional[str] = Field(None, description="New AI voice ID")
    ai_personality: Optional[str] = Field(None, description="New AI personality")
    greeting_message: Optional[str] = Field(None, description="New greeting message")

class AgentInfoResponse(BaseModel):
    clinic_id: int
    clinic_name: str
    agent_id: str
    agent_name: str
    twilio_phone_number: Optional[str]
    twilio_phone_sid: Optional[str]
    ai_voice_id: Optional[str]
    ai_personality: Optional[str]
    greeting_message: Optional[str]

class OutboundCallResponse(BaseModel):
    call_id: int
    conversation_id: Optional[str]
    call_sid: Optional[str]
    status: str
    from_number: str
    to_number: str
    call_type: str

class TwilioNumberResponse(BaseModel):
    clinic_id: int
    clinic_name: str
    twilio_phone_number: Optional[str]
    twilio_phone_sid: Optional[str]

class DocumentUploadResponse(BaseModel):
    document_id: Optional[str] = None
    file_name: str
    clinic_id: int
    knowledge_base_id: Optional[str] = None
    agent_id: Optional[str] = None
    status: str

class CallStatusResponse(BaseModel):
    call_id: int
    status: str
    call_type: str
    from_number: str
    to_number: str
    duration_seconds: Optional[int]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    twilio_call_sid: Optional[str]
    outcome: Optional[str]
    handoff_to_human: bool
    patient_satisfaction: Optional[int]

class CallListResponse(BaseModel):
    calls: List[CallStatusResponse]
    total_count: int
    limit: int
    offset: int

class KnowledgeBaseTextRequest(BaseModel):
    text: str = Field(..., description="Text content to add to the knowledge base")
    name: Optional[str] = Field(None, description="Optional name for the document")

# Routes
@router.get("/clinic/{clinic_id}/agent-info", response_model=AgentInfoResponse)
async def get_clinic_agent_info(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get ElevenLabs agent information for a clinic
    - **clinic_id**: ID of the clinic
    """
    # Check if user has access to this clinic
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    elif current_user.get("user_type") == "staff":
        # Staff members can access their clinic's agent info
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    agent_info = agent_setup_service.get_clinic_agent_info(db, clinic_id)
    if not agent_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found for this clinic"
        )
    
    return AgentInfoResponse(**agent_info)

@router.post("/clinic/{clinic_id}/create-agent", response_model=AgentInfoResponse)
async def create_agent_for_clinic(
    clinic_id: int,
    request: CreateAgentRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create an ElevenLabs agent for a clinic
    - **clinic_id**: ID of the clinic
    - **agent_name**: Optional custom name for the agent
    """
    # Check if user has access to this clinic
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    elif current_user.get("user_type") == "staff":
        # Staff members can create agents for their clinic
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    agent_info = agent_setup_service.create_agent_for_clinic(
        db, 
        clinic_id, 
        request.agent_name
    )
    
    if not agent_info:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent"
        )
    
    return AgentInfoResponse(**agent_info)

@router.get("/clinic/{clinic_id}/twilio-number", response_model=TwilioNumberResponse)
async def get_clinic_twilio_number(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the Twilio phone number for a clinic
    - **clinic_id**: ID of the clinic
    """
    # Check if user has access to this clinic
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    elif current_user.get("user_type") == "staff":
        # Staff members can access their clinic's Twilio number
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    # Get clinic information
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return TwilioNumberResponse(
        clinic_id=clinic.id,
        clinic_name=clinic.name,
        twilio_phone_number=clinic.twilio_phone_number,
        twilio_phone_sid=clinic.twilio_phone_sid
    )

@router.get("/my-clinic/twilio-number", response_model=TwilioNumberResponse)
async def get_my_clinic_twilio_number(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the Twilio phone number for the current user's clinic
    """
    # Get clinic ID based on user type
    if current_user.get("user_type") == "clinic":
        clinic_id = current_user.get("user_id")
    elif current_user.get("user_type") == "staff":
        clinic_id = current_user.get("clinic_id")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    # Get clinic information
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return TwilioNumberResponse(
        clinic_id=clinic.id,
        clinic_name=clinic.name,
        twilio_phone_number=clinic.twilio_phone_number,
        twilio_phone_sid=clinic.twilio_phone_sid
    )

@router.post("/clinic/{clinic_id}/outbound-call", response_model=OutboundCallResponse)
async def make_outbound_call(
    clinic_id: int,
    request: OutboundCallRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Make an outbound call using the clinic's ElevenLabs agent
    - **clinic_id**: ID of the clinic
    - **to_number**: Phone number to call
    """
    # Check if user has access to this clinic
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    elif current_user.get("user_type") == "staff":
        # Staff members can make outbound calls for their clinic
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    call_result = await agent_setup_service.make_outbound_call(
        db=db,
        clinic_id=clinic_id,
        to_number=request.to_number
    )
    
    if not call_result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate outbound call"
        )
    
    return OutboundCallResponse(**call_result)

@router.post("/my-clinic/outbound-call", response_model=OutboundCallResponse)
async def make_outbound_call_my_clinic(
    request: OutboundCallRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Make an outbound call using the current user's clinic's ElevenLabs agent
    - **to_number**: Phone number to call
    """
    # Get clinic ID based on user type
    if current_user.get("user_type") == "clinic":
        clinic_id = current_user.get("user_id")
    elif current_user.get("user_type") == "staff":
        clinic_id = current_user.get("clinic_id")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    call_result = await agent_setup_service.make_outbound_call(
        db=db,
        clinic_id=clinic_id,
        to_number=request.to_number
    )
    
    if not call_result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate outbound call"
        )
    
    return OutboundCallResponse(**call_result)

@router.get("/call/{call_id}/status", response_model=CallStatusResponse)
async def get_call_status(
    call_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the status of a specific call
    - **call_id**: ID of the call
    """
    call_status = agent_setup_service.get_call_status(db, call_id)
    if not call_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    # Check if user has access to this call's clinic
    call = db.query(Call).filter(Call.id == call_id).first()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != call.clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this call"
            )
    elif current_user.get("user_type") == "staff":
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != call.clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this call"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    return CallStatusResponse(**call_status)

@router.get("/clinic/{clinic_id}/calls", response_model=CallListResponse)
async def list_clinic_calls(
    clinic_id: int,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of calls to return"),
    offset: int = Query(0, ge=0, description="Number of calls to skip"),
    call_type: Optional[CallType] = Query(None, description="Filter by call type"),
    status: Optional[CallStatus] = Query(None, description="Filter by call status"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List calls for a clinic with optional filtering
    - **clinic_id**: ID of the clinic
    - **limit**: Maximum number of calls to return (1-100)
    - **offset**: Number of calls to skip
    - **call_type**: Optional filter by call type
    - **status**: Optional filter by call status
    """
    # Check if user has access to this clinic
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    elif current_user.get("user_type") == "staff":
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    calls = agent_setup_service.list_clinic_calls(
        db=db,
        clinic_id=clinic_id,
        limit=limit,
        offset=offset,
        call_type=call_type,
        status=status
    )
    
    # Get total count for pagination
    total_query = db.query(Call).filter(Call.clinic_id == clinic_id)
    if call_type:
        total_query = total_query.filter(Call.call_type == call_type)
    if status:
        total_query = total_query.filter(Call.status == status)
    total_count = total_query.count()
    
    return CallListResponse(
        calls=[CallStatusResponse(**call) for call in calls],
        total_count=total_count,
        limit=limit,
        offset=offset
    )

@router.put("/clinic/{clinic_id}/agent-config", response_model=AgentInfoResponse)
async def update_agent_configuration(
    clinic_id: int,
    request: UpdateAgentConfigRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update agent configuration for a clinic
    - **clinic_id**: ID of the clinic
    - **agent_name**: Optional new agent name
    - **ai_voice_id**: Optional new AI voice ID
    - **ai_personality**: Optional new AI personality
    - **greeting_message**: Optional new greeting message
    """
    # Check if user has access to this clinic
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    elif current_user.get("user_type") == "staff":
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    agent_info = agent_setup_service.update_agent_configuration(
        db=db,
        clinic_id=clinic_id,
        agent_name=request.agent_name,
        ai_voice_id=request.ai_voice_id,
        ai_personality=request.ai_personality,
        greeting_message=request.greeting_message
    )
    
    if not agent_info:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent configuration"
        )
    
    return AgentInfoResponse(**agent_info)

@router.patch("/clinic/{clinic_id}/agent-config/full")
async def update_full_agent_config(
    clinic_id: int,
    config: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fully update an agent's configuration (all fields supported by ElevenLabs PATCH API).
    - **clinic_id**: ID of the clinic
    - **config**: Full config dict to PATCH
    """
    # Access check
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this clinic")
    elif current_user.get("user_type") == "staff":
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this clinic")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid user type")
    agent_info = agent_setup_service.get_clinic_agent_info(db, clinic_id)
    if not agent_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found for this clinic")
    result = agent_setup_service.update_agent_full_config(agent_info['agent_id'], config)
    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])
    return result

@router.patch("/clinic/{clinic_id}/agent-config/data-collection")
async def update_agent_data_collection(
    clinic_id: int,
    data_collection: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update data collection settings (analytics, transcript, etc.) for an agent.
    - **clinic_id**: ID of the clinic
    - **data_collection**: Dict for the 'data_collection' field
    """
    # Access check
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this clinic")
    elif current_user.get("user_type") == "staff":
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this clinic")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid user type")
    agent_info = agent_setup_service.get_clinic_agent_info(db, clinic_id)
    if not agent_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found for this clinic")
    result = agent_setup_service.update_agent_data_collection(agent_info['agent_id'], data_collection)
    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])
    return result

@router.get("/clinic/{clinic_id}/setup-status")
async def get_clinic_setup_status(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the setup status for a clinic's agent
    - **clinic_id**: ID of the clinic
    """
    # Check if user has access to this clinic
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    elif current_user.get("user_type") == "staff":
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return {
        "clinic_id": clinic.id,
        "clinic_name": clinic.name,
        "agent_configured": bool(clinic.elevenlabs_agent_id),
        "agent_id": clinic.elevenlabs_agent_id,
        "agent_name": clinic.elevenlabs_agent_name,
        "twilio_configured": bool(clinic.twilio_phone_number),
        "twilio_phone_number": clinic.twilio_phone_number,
        "twilio_phone_sid": clinic.twilio_phone_sid,
        "ai_voice_configured": bool(clinic.ai_voice_id),
        "ai_voice_id": clinic.ai_voice_id,
        "ai_personality_configured": bool(clinic.ai_personality),
        "greeting_message_configured": bool(clinic.greeting_message),
        "knowledge_base_configured": bool(clinic.knowledge_base_id),
        "knowledge_base_id": clinic.knowledge_base_id,
        "ready_for_outbound_calls": bool(
            clinic.elevenlabs_agent_id and 
            clinic.twilio_phone_number and 
            clinic.ai_voice_id
        )
    }

# Knowledge Base Routes
@router.get("/my-clinic/knowledge-base/status")
async def get_my_clinic_knowledge_base_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the knowledge base status for the current user's clinic
    """
    # Get clinic ID based on user type
    if current_user.get("user_type") == "clinic":
        clinic_id = current_user.get("user_id")
    elif current_user.get("user_type") == "staff":
        clinic_id = current_user.get("clinic_id")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    return {
        "clinic_id": clinic.id,
        "clinic_name": clinic.name,
        "knowledge_base_id": clinic.knowledge_base_id,
        "knowledge_base_configured": bool(clinic.knowledge_base_id),
        "agent_id": clinic.elevenlabs_agent_id,
        "agent_configured": bool(clinic.elevenlabs_agent_id)
    }

@router.post("/my-clinic/import-phone-number")
async def import_phone_number_to_elevenlabs(
    request: ImportPhoneNumberRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import a Twilio phone number to ElevenLabs for the current user's clinic
    - **phone_number**: Phone number to import
    - **label**: Label for the phone number
    - **twilio_sid**: Twilio Account SID
    - **twilio_token**: Twilio Auth Token
    """
    # Get clinic ID based on user type
    if current_user.get("user_type") == "clinic":
        clinic_id = current_user.get("user_id")
    elif current_user.get("user_type") == "staff":
        clinic_id = current_user.get("clinic_id")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    # Import the phone number to ElevenLabs
    phone_id = await agent_setup_service.import_phone_number_to_elevenlabs(
        phone_number=request.phone_number,
        label=request.label,
        twilio_sid=request.twilio_sid,
        twilio_token=request.twilio_token
    )
    
    if not phone_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import phone number to ElevenLabs"
        )
    
    # If the clinic has an agent, try to link the phone number to it
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if clinic and clinic.elevenlabs_agent_id:
        linked = await agent_setup_service.link_phone_to_agent(
            agent_id=clinic.elevenlabs_agent_id,
            phone_number=request.phone_number
        )
        if linked:
            logger.info(f"Successfully linked phone {request.phone_number} to agent {clinic.elevenlabs_agent_id}")
    
    return {
        "success": True,
        "phone_id": phone_id,
        "phone_number": request.phone_number,
        "clinic_id": clinic_id,
        "message": "Phone number imported successfully"
    }

@router.post("/my-clinic/knowledge-base/upload", response_model=DocumentUploadResponse)
async def upload_document_to_knowledge_base(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a document to the current user's clinic's knowledge base
    - **file**: Document file to upload (PDF, DOC, DOCX, TXT)
    """
    # Get clinic ID based on user type
    if current_user.get("user_type") == "clinic":
        clinic_id = current_user.get("user_id")
    elif current_user.get("user_type") == "staff":
        clinic_id = current_user.get("clinic_id")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    # Validate file type
    allowed_extensions = ['.pdf', '.doc', '.docx', '.txt']
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not supported. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Save uploaded file temporarily
    import tempfile
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name
    
    try:
        # Upload document to knowledge base
        upload_result = await agent_setup_service.upload_document_to_knowledge_base(
            db=db,
            clinic_id=clinic_id,
            file_path=temp_file_path
        )
        
        if not upload_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload document to knowledge base"
            )
        
        return DocumentUploadResponse(**upload_result)
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path) 

@router.post("/clinic/{clinic_id}/assign-phone-to-agent")
async def assign_phone_to_agent(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assign the clinic's phone number to its agent in ElevenLabs.
    """
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic or not clinic.elevenlabs_agent_id or not clinic.twilio_phone_number:
        raise HTTPException(status_code=400, detail="Clinic, agent, or phone number not found")
    # Get phone_number_id from ElevenLabs
    phone_id = await agent_setup_service._get_elevenlabs_phone_id(clinic.twilio_phone_number)
    if not phone_id:
        raise HTTPException(status_code=404, detail="Phone number not found in ElevenLabs")
    success = agent_setup_service.assign_phone_to_agent(clinic.elevenlabs_agent_id, phone_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to assign phone number to agent")
    return {"success": True, "agent_id": clinic.elevenlabs_agent_id, "phone_number_id": phone_id}

@router.post("/my-clinic/assign-phone-to-agent")
async def assign_my_clinic_phone_to_agent(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assign the current user's clinic's phone number to its agent in ElevenLabs.
    """
    # Get clinic ID based on user type
    if current_user.get("user_type") == "clinic":
        clinic_id = current_user.get("user_id")
    elif current_user.get("user_type") == "staff":
        clinic_id = current_user.get("clinic_id")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic or not clinic.elevenlabs_agent_id or not clinic.twilio_phone_number:
        raise HTTPException(status_code=400, detail="Clinic, agent, or phone number not found")
    # Get phone_number_id from ElevenLabs
    phone_id = await agent_setup_service._get_elevenlabs_phone_id(clinic.twilio_phone_number)
    if not phone_id:
        raise HTTPException(status_code=404, detail="Phone number not found in ElevenLabs")
    success = agent_setup_service.assign_phone_to_agent(clinic.elevenlabs_agent_id, phone_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to assign phone number to agent")
    return {"success": True, "agent_id": clinic.elevenlabs_agent_id, "phone_number_id": phone_id} 

@router.post("/clinic/{clinic_id}/assign-knowledge-base-to-agent")
async def assign_knowledge_base_to_agent(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assign the clinic's knowledge base to its agent in ElevenLabs.
    """
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic or not clinic.elevenlabs_agent_id or not clinic.knowledge_base_id:
        raise HTTPException(status_code=400, detail="Clinic, agent, or knowledge base not found")
    
    # Assign knowledge base to agent
    success = await agent_setup_service._assign_knowledge_base_to_agent(
        clinic.elevenlabs_agent_id, 
        clinic.knowledge_base_id
    )
    
    if success:
        return {"message": f"Successfully assigned knowledge base {clinic.knowledge_base_id} to agent {clinic.elevenlabs_agent_id}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to assign knowledge base to agent") 

@router.post("/my-clinic/assign-knowledge-base-to-agent")
async def assign_my_clinic_knowledge_base_to_agent(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assign the current user's clinic's knowledge base to its agent in ElevenLabs.
    """
    # Get clinic ID based on user type
    if current_user.get("user_type") == "clinic":
        clinic_id = current_user.get("user_id")
    elif current_user.get("user_type") == "staff":
        clinic_id = current_user.get("clinic_id")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )
    
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic or not clinic.elevenlabs_agent_id or not clinic.knowledge_base_id:
        raise HTTPException(status_code=400, detail="Clinic, agent, or knowledge base not found")
    
    # Assign knowledge base to agent
    success = await agent_setup_service._assign_knowledge_base_to_agent(
        clinic.elevenlabs_agent_id, 
        clinic.knowledge_base_id
    )
    
    if success:
        return {"message": f"Successfully assigned knowledge base {clinic.knowledge_base_id} to agent {clinic.elevenlabs_agent_id}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to assign knowledge base to agent") 

@router.post("/clinic/{clinic_id}/knowledge-base/text", response_model=DocumentUploadResponse)
async def create_knowledge_base_from_text(
    clinic_id: int,
    request: KnowledgeBaseTextRequest = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a knowledge base document from text for a clinic's agent in ElevenLabs
    - **clinic_id**: ID of the clinic
    - **text**: Text content to add to the knowledge base
    - **name**: Optional name for the document
    """
    # Check if user has access to this clinic
    if current_user.get("user_type") == "clinic":
        if current_user.get("user_id") != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    elif current_user.get("user_type") == "staff":
        staff_clinic_id = current_user.get("clinic_id")
        if staff_clinic_id != clinic_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this clinic"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user type"
        )

    result = await agent_setup_service.create_knowledge_base_from_text(
        db=db,
        clinic_id=clinic_id,
        text=request.text,
        name=request.name
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create knowledge base from text"
        )
    return DocumentUploadResponse(
        document_id=result.get("document_id"),
        file_name=request.name or "text",
        clinic_id=clinic_id,
        knowledge_base_id=result.get("knowledge_base_id"),
        agent_id=result.get("agent_id"),
        status=result.get("status", "uploaded")
    ) 

@router.post("/agent-setup/auto-update-tools")
async def auto_update_tools(
    clinic_id: str = Body(...),
    ehr: str = Body(...),
    epic_creds: dict = Body(None),
    athena_creds: dict = Body(None),
    db: Session = Depends(get_db)
):
    """
    Generate all webhook configs for the clinic/EHR, update the agent config, and return the webhook tool list.
    """
    NGROK_URL = os.getenv("FORCED_NGROK_URL", "https://b561215328df.ngrok-free.app ")
    from services.webhook_generator_service import WebhookGeneratorService
    service = WebhookGeneratorService(public_api_domain=NGROK_URL)
    epic_creds_dict = epic_creds if epic_creds else None
    athena_creds_dict = None
    if athena_creds:
        athena_creds_dict = {
            "athena_client_id": athena_creds.get("ATHENA_CLIENT_ID"),
            "athena_client_secret": athena_creds.get("ATHENA_CLIENT_SECRET"),
            "athena_api_base_url": athena_creds.get("ATHENA_API_BASE_URL"),
            "athena_practice_id": athena_creds.get("ATHENA_PRACTICE_ID")
        }
    configs = service.generate_webhook_config(clinic_id, ehr, epic_creds=epic_creds_dict, athena_creds=athena_creds_dict)

    # Format each webhook tool with dummy_param in query_params_schema
    formatted = []
    for cfg in configs:
        formatted.append({
            "type": "webhook",
            "name": cfg.get("name", ""),
            "description": cfg.get("description", ""),
            "api_schema": {
                "url": cfg.get("api_schema", {}).get("url", ""),
                "method": "GET",
                "path_params_schema": {},
                "query_params_schema": {
                    "properties": {
                        "dummy_param": {
                            "type": "string",
                            "description": "This is a required placeholder due to API schema constraints. It is not used."
                        }
                    },
                    "required": []
                },
                "request_body_schema": None,
                "request_headers": {},
                "auth_connection": None
            },
            "response_timeout_secs": 20,
            "dynamic_variables": {
                "dynamic_variable_placeholders": {}
            }
        })

    # Fetch agent config
    agent_info = agent_setup_service.get_clinic_agent_info(db, clinic_id)
    if not agent_info:
        raise HTTPException(404, "Agent not found for this clinic")
    agent_config = agent_info.get("agent_config") or agent_info
    # Defensive: ensure nested keys exist
    if "conversation_config" not in agent_config:
        agent_config["conversation_config"] = {}
    if "agent" not in agent_config["conversation_config"]:
        agent_config["conversation_config"]["agent"] = {}
    if "prompt" not in agent_config["conversation_config"]["agent"]:
        agent_config["conversation_config"]["agent"]["prompt"] = {}
    # Update tools
    agent_config["conversation_config"]["agent"]["prompt"]["tools"] = formatted

    # Update agent
    update_resp = requests.post(
        f"{NGROK_URL}/agent-setup/clinic/{clinic_id}/agent-config",
        json={
            "agent_name": agent_config.get("name"),
            "conversation_config": agent_config["conversation_config"]
        }
    )
    if update_resp.status_code != 200:
        raise HTTPException(500, f"Failed to update agent: {update_resp.text}")
    return {"success": True, "webhooks": formatted, "agent": update_resp.json()} 

@router.post("/agent-setup/generate-webhook-tools")
async def generate_webhook_tools(
    clinic_id: str = Body(...),
    ehr: str = Body(...),
    epic_creds: dict = Body(None),
    athena_creds: dict = Body(None)
):
    """
    Generate all webhook tools for the clinic/EHR and return the full conversation_config JSON in the required format (matching the user's working sample exactly, with only the fields shown in the sample for each tool, and no extra keys at the top level).
    """
    NGROK_URL = os.getenv("FORCED_NGROK_URL", "https://b561215328df.ngrok-free.app ")
    from services.webhook_generator_service import WebhookGeneratorService
    service = WebhookGeneratorService(public_api_domain=NGROK_URL)
    epic_creds_dict = epic_creds if epic_creds else None
    athena_creds_dict = None
    if athena_creds:
        athena_creds_dict = {
            "athena_client_id": athena_creds.get("athena_client_id") or athena_creds.get("ATHENA_CLIENT_ID"),
            "athena_client_secret": athena_creds.get("athena_client_secret") or athena_creds.get("ATHENA_CLIENT_SECRET"),
            "athena_api_base_url": athena_creds.get("athena_api_base_url") or athena_creds.get("ATHENA_API_BASE_URL"),
            "athena_practice_id": athena_creds.get("athena_practice_id") or athena_creds.get("ATHENA_PRACTICE_ID")
        }
    configs = service.generate_webhook_config(clinic_id, ehr, epic_creds=epic_creds_dict, athena_creds=athena_creds_dict)

    # Format each webhook tool exactly as in the working sample
    tools = []
    for cfg in configs:
        tools.append({
            "name": cfg.get("name", ""),
            "description": cfg.get("description", ""),
            "response_timeout_secs": 20,
            "type": "webhook",
            "api_schema": {
                "url": cfg.get("api_schema", {}).get("url", ""),
                "method": "GET",
                "path_params_schema": {},
                "query_params_schema": {
                    "properties": {
                        "dummy_param": {
                            "type": "string",
                            "description": "This is a required placeholder due to API schema constraints. It is not used."
                        }
                    },
                    "required": []
                },
                "request_body_schema": None,
                "request_headers": {},
                "auth_connection": None
            },
            "dynamic_variables": {
                "dynamic_variable_placeholders": {}
            }
        })

    # Build the full conversation_config JSON exactly as in the working sample
    conversation_config = {
        "asr": {
            "quality": "high",
            "provider": "elevenlabs",
            "user_input_audio_format": "pcm_8000"
        },
        "turn": {
            "turn_timeout": 7,
            "silence_end_call_timeout": -1,
            "mode": "silence"
        },
        "tts": {
            "model_id": "eleven_turbo_v2",
            "voice_id": "cjVigY5qzO86Huf0OWal",
            "agent_output_audio_format": "pcm_8000",
            "optimize_streaming_latency": 0,
            "stability": 0.5,
            "speed": 1,
            "similarity_boost": 0.8
        },
        "conversation": {
            "text_only": False,
            "max_duration_seconds": 600,
            "client_events": ["conversation_initiation_metadata"]
        },
        "language_presets": {},
        "agent": {
            "first_message": "",
            "language": "en",
            "prompt": {
                "prompt": "",
                "llm": "gpt-4o-mini",
                "temperature": 0,
                "max_tokens": -1,
                "ignore_default_personality": True,
                "rag": {
                    "enabled": False,
                    "embedding_model": "e5_mistral_7b_instruct",
                    "max_vector_distance": 0.6,
                    "max_documents_length": 50000,
                    "max_retrieved_rag_chunks_count": 20
                },
                "tools": tools
            }
        }
    }
    return {
        "conversation_config": conversation_config,
        "metadata": {"created_at_unix_secs": 42}
    } 