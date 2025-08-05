"""
ElevenLabs webhook routes for conversation events
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Response
from typing import Dict, Any
import logging
from sqlalchemy.orm import Session
from database import get_db
from models import Call, Clinic, CallStatus, CallType
from services.conversation_service import conversation_service
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/elevenlabs", tags=["elevenlabs-webhooks"])

@router.post("/conversation-status")
async def handle_conversation_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle ElevenLabs conversation status webhook
    This webhook is called by ElevenLabs to notify about conversation events
    """
    try:
        # Get the raw body for logging
        body = await request.json()
        logger.info(f"Received ElevenLabs webhook: {json.dumps(body)}")
        
        # Extract key fields
        conversation_id = body.get("conversation_id")
        agent_id = body.get("agent_id")
        status = body.get("status")
        metadata = body.get("metadata", {})
        
        if not conversation_id:
            logger.error("No conversation_id in webhook payload")
            return {"status": "error", "message": "No conversation_id provided"}
        
        # Find the clinic by agent_id
        if agent_id:
            clinic = db.query(Clinic).filter(Clinic.agent_id == agent_id).first()
            if clinic:
                # Try to find an existing call without conversation_id that matches
                # the phone numbers (if provided in metadata)
                caller_phone = metadata.get("caller_id") or metadata.get("from_number")
                
                if caller_phone:
                    # Find the most recent call from this number to this clinic
                    call = db.query(Call).filter(
                        Call.clinic_id == clinic.id,
                        Call.from_number.contains(caller_phone.replace("+", "")),
                        Call.conversation_id.is_(None)
                    ).order_by(Call.created_at.desc()).first()
                    
                    if call:
                        # Update the call with conversation_id
                        call.conversation_id = conversation_id
                        
                        # Update status based on ElevenLabs status
                        status_mapping = {
                            "initiated": CallStatus.INITIATED,
                            "in-progress": CallStatus.IN_PROGRESS,
                            "processing": CallStatus.IN_PROGRESS,
                            "done": CallStatus.COMPLETED,
                            "failed": CallStatus.FAILED
                        }
                        if status in status_mapping:
                            call.status = status_mapping[status]
                        
                        db.commit()
                        logger.info(f"Updated call {call.id} with conversation_id {conversation_id}")
                    else:
                        # Create a new call record for inbound calls
                        new_call = Call(
                            clinic_id=clinic.id,
                            conversation_id=conversation_id,
                            from_number=caller_phone or "Unknown",
                            to_number=clinic.twilio_phone_number or "Unknown",
                            call_type=CallType.INBOUND,
                            status=CallStatus.IN_PROGRESS
                        )
                        db.add(new_call)
                        db.commit()
                        logger.info(f"Created new call record for conversation {conversation_id}")
        
        # If the conversation is done, sync the full details
        if status == "done":
            try:
                await conversation_service.sync_conversation_details(conversation_id)
            except Exception as e:
                logger.error(f"Error syncing conversation details: {str(e)}")
        
        return {"status": "success", "conversation_id": conversation_id}
        
    except Exception as e:
        logger.error(f"Error processing ElevenLabs webhook: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.post("/call-ended")
async def handle_call_ended(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle ElevenLabs call ended webhook
    """
    try:
        body = await request.json()
        logger.info(f"Received call ended webhook: {json.dumps(body)}")
        
        conversation_id = body.get("conversation_id")
        if conversation_id:
            # Sync the final conversation details
            await conversation_service.sync_conversation_details(conversation_id)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error processing call ended webhook: {str(e)}")
        return {"status": "error", "message": str(e)}