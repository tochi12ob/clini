"""
Enhanced Calendar Routes for Clinic AI Assistant
Full Calendly integration with booking, cancellation, and rescheduling via webhooks
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from pydantic import BaseModel
import os
import httpx
import logging
import json

from database import get_db
from services.calender_service import calendar_service
from services.calendly_service import calendly_service
from routes.auth import get_current_user
from schemas import (
    AppointmentCreate, 
    AppointmentUpdate, 
    AppointmentResponse,
    TimeSlot,
    AvailabilityRequest,
    AppointmentReschedule
)
from models import Appointment, Clinic, AppointmentStatus

router = APIRouter()
logger = logging.getLogger(__name__)

# Calendly OAuth configuration
CALENDLY_CLIENT_ID = os.getenv("CALENDLY_CLIENT_ID")
CALENDLY_CLIENT_SECRET = os.getenv("CALENDLY_CLIENT_SECRET")
CALENDLY_REDIRECT_URI = os.getenv("CALENDLY_REDIRECT_URI", "https://app.clinivocx.com")

# Request models
class CalendlyConnectRequest(BaseModel):
    clinic_id: int
    return_url: Optional[str] = "/dashboard"

class CalendlyEventTypeCreate(BaseModel):
    name: str
    duration: int
    description: Optional[str] = None
    color: Optional[str] = "#1a73e8"

class AppointmentBookingRequest(BaseModel):
    clinic_id: int
    patient_name: str
    patient_email: Optional[str] = None
    patient_phone: Optional[str] = None
    appointment_datetime: datetime
    duration_minutes: int = 30
    appointment_type: Optional[str] = "consultation"
    notes: Optional[str] = None

class AppointmentCancelRequest(BaseModel):
    reason: Optional[str] = None

class AppointmentRescheduleRequest(BaseModel):
    new_datetime: datetime
    reason: Optional[str] = None

# Existing routes (keeping your original functionality)
@router.get("/availability/{clinic_id}")
async def get_availability(
    clinic_id: int,
    date: date = Query(..., description="Date to check availability (YYYY-MM-DD)"),
    duration: int = Query(30, description="Appointment duration in minutes"),
    db: Session = Depends(get_db)
):
    """Get available appointment slots for a specific date"""
    try:
        available_slots = calendar_service.get_available_slots(
            clinic_id=clinic_id,
            date=date,
            duration_minutes=duration,
            db=db
        )
        
        return {
            "clinic_id": clinic_id,
            "date": date.isoformat(),
            "duration_minutes": duration,
            "available_slots": [
                {
                    "start_time": slot.start_time.isoformat(),
                    "end_time": slot.end_time.isoformat(),
                    "is_available": slot.is_available
                } for slot in available_slots
            ],
            "total_slots": len(available_slots)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving availability: {str(e)}")

@router.post("/appointments")
async def book_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db)
):
    """Book a new appointment"""
    try:
        appointment = calendar_service.book_appointment(appointment_data, db)
        
        if not appointment:
            raise HTTPException(
                status_code=409, 
                detail="The requested time slot is no longer available"
            )
        
        return {
            "success": True,
            "message": "Appointment booked successfully",
            "appointment": {
                "id": appointment.id,
                "clinic_id": appointment.clinic_id,
                "patient_id": appointment.patient_id,
                "appointment_datetime": appointment.appointment_datetime.isoformat(),
                "duration_minutes": appointment.duration_minutes,
                "appointment_type": appointment.appointment_type,
                "status": appointment.status.value,
                "notes": appointment.notes
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error booking appointment: {str(e)}")

@router.put("/appointments/{appointment_id}/reschedule")
async def reschedule_appointment(
    appointment_id: int,
    reschedule_data: AppointmentReschedule,
    db: Session = Depends(get_db)
):
    """Reschedule an existing appointment"""
    try:
        success = calendar_service.reschedule_appointment(
            appointment_id=appointment_id,
            new_datetime=reschedule_data.new_datetime,
            db=db
        )
        
        if not success:
            raise HTTPException(
                status_code=409,
                detail="Unable to reschedule - new time slot may not be available or appointment not found"
            )
        
        return {
            "success": True,
            "message": "Appointment rescheduled successfully",
            "appointment_id": appointment_id,
            "new_datetime": reschedule_data.new_datetime.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rescheduling appointment: {str(e)}")

@router.delete("/appointments/{appointment_id}")
async def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    """Cancel an appointment"""
    try:
        success = calendar_service.cancel_appointment(appointment_id, db)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Appointment not found"
            )
        
        return {
            "success": True,
            "message": "Appointment cancelled successfully",
            "appointment_id": appointment_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling appointment: {str(e)}")

@router.get("/appointments/{clinic_id}/upcoming")
async def get_upcoming_appointments(
    clinic_id: int,
    days_ahead: int = Query(7, description="Number of days to look ahead"),
    db: Session = Depends(get_db)
):
    """Get upcoming appointments for a clinic"""
    try:
        appointments = calendar_service.get_upcoming_appointments(
            clinic_id=clinic_id,
            days_ahead=days_ahead,
            db=db
        )
        
        return {
            "clinic_id": clinic_id,
            "days_ahead": days_ahead,
            "appointments": [
                {
                    "id": apt.id,
                    "patient_id": apt.patient_id,
                    "appointment_datetime": apt.appointment_datetime.isoformat(),
                    "duration_minutes": apt.duration_minutes,
                    "appointment_type": apt.appointment_type,
                    "status": apt.status.value,
                    "notes": apt.notes,
                    "external_system": apt.external_system,
                    "calendly_event_uri": apt.calendly_event_uri,
                    "created_at": apt.created_at.isoformat() if apt.created_at else None
                } for apt in appointments
            ],
            "total_appointments": len(appointments)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving upcoming appointments: {str(e)}")

@router.get("/appointments/{appointment_id}")
async def get_appointment_details(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    """Get details of a specific appointment"""
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        return {
            "id": appointment.id,
            "clinic_id": appointment.clinic_id,
            "patient_id": appointment.patient_id,
            "appointment_datetime": appointment.appointment_datetime.isoformat() if appointment.appointment_datetime else None,
            "duration_minutes": appointment.duration_minutes,
            "appointment_type": appointment.appointment_type,
            "status": appointment.status.value if appointment.status else None,
            "notes": appointment.notes,
            "external_system": appointment.external_system,
            "external_id": appointment.external_id,
            "calendly_event_uri": appointment.calendly_event_uri,
            "calendly_invitee_uri": appointment.calendly_invitee_uri,
            "created_at": appointment.created_at.isoformat() if appointment.created_at else None,
            "updated_at": appointment.updated_at.isoformat() if appointment.updated_at else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving appointment details: {str(e)}")

@router.get("/appointments/search")
async def search_appointments(
    clinic_id: int = Query(..., description="Clinic ID"),
    patient_phone: Optional[str] = Query(None, description="Patient phone number"),
    date_from: Optional[date] = Query(None, description="Start date for search"),
    date_to: Optional[date] = Query(None, description="End date for search"),
    status: Optional[str] = Query(None, description="Appointment status"),
    db: Session = Depends(get_db)
):
    """Search appointments with various filters"""
    try:
        query = db.query(Appointment).filter(Appointment.clinic_id == clinic_id)
        
        if patient_phone:
            from models import Patient
            query = query.join(Patient).filter(Patient.phone == patient_phone)
        
        if date_from:
            query = query.filter(Appointment.appointment_datetime >= datetime.combine(date_from, datetime.min.time()))
        
        if date_to:
            query = query.filter(Appointment.appointment_datetime <= datetime.combine(date_to, datetime.max.time()))
        
        if status:
            query = query.filter(Appointment.status == status)
        
        appointments = query.order_by(Appointment.appointment_datetime.desc()).limit(50).all()
        
        return {
            "appointments": [
                {
                    "id": apt.id,
                    "patient_id": apt.patient_id,
                    "appointment_datetime": apt.appointment_datetime.isoformat(),
                    "duration_minutes": apt.duration_minutes,
                    "appointment_type": apt.appointment_type,
                    "status": apt.status.value,
                    "notes": apt.notes
                } for apt in appointments
            ],
            "total_found": len(appointments),
            "search_criteria": {
                "clinic_id": clinic_id,
                "patient_phone": patient_phone,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "status": status
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching appointments: {str(e)}")

@router.get("/clinics/{clinic_id}/calendar-sync")
async def get_calendar_sync_status(
    clinic_id: int,
    db: Session = Depends(get_db)
):
    """Get calendar synchronization status for a clinic"""
    try:
        clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            raise HTTPException(status_code=404, detail="Clinic not found")
        
        google_enabled = calendar_service.google_service is not None
        calendly_enabled = bool(clinic.calendly_access_token)
        
        return {
            "clinic_id": clinic_id,
            "google_calendar_enabled": google_enabled,
            "calendly_enabled": calendly_enabled,
            "calendly_connected_at": clinic.calendly_connected_at.isoformat() if clinic.calendly_connected_at else None,
            "sync_status": "active" if (google_enabled or calendly_enabled) else "disabled"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking calendar sync status: {str(e)}")

# Enhanced Calendly Integration Routes
@router.post("/calendly/connect")
async def connect_calendly(
    request: CalendlyConnectRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate Calendly OAuth connection for a clinic"""
    if current_user.get("user_type") == "clinic" and current_user.get("user_id") != request.clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not CALENDLY_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Calendly OAuth not configured. Please set CALENDLY_CLIENT_ID and CALENDLY_CLIENT_SECRET"
        )
    
    state = f"{request.clinic_id}:{request.return_url}"
    
    auth_url = (
        f"https://auth.calendly.com/oauth/authorize"
        f"?client_id={CALENDLY_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={CALENDLY_REDIRECT_URI}"
        f"&state={state}"
    )
    
    return {"auth_url": auth_url, "message": "Redirect user to auth_url to connect Calendly"}

@router.get("/calendly/callback")
async def calendly_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """Handle Calendly OAuth callback"""
    try:
        clinic_id, return_url = state.split(":", 1) if ":" in state else (state, "/dashboard")
        clinic_id = int(clinic_id)
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://auth.calendly.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": CALENDLY_CLIENT_ID,
                    "client_secret": CALENDLY_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": CALENDLY_REDIRECT_URI
                }
            )
            
            if token_response.status_code != 200:
                logger.error(f"Token exchange failed: {token_response.text}")
                raise HTTPException(status_code=400, detail="Failed to exchange code for token")
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            
            user_info = await calendly_service.get_current_user(access_token)
            if not user_info:
                raise HTTPException(status_code=400, detail="Failed to get Calendly user info")
            
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                raise HTTPException(status_code=404, detail="Clinic not found")
            
            clinic.calendly_access_token = access_token
            clinic.calendly_refresh_token = refresh_token
            clinic.calendly_user_uri = user_info["resource"]["uri"]
            clinic.calendly_organization_uri = user_info["resource"]["current_organization"]
            clinic.calendly_connected_at = datetime.utcnow()
            clinic.calendly_sync_enabled = True
            
            webhook_result = await calendly_service.create_webhook_subscription(
                access_token=access_token,
                clinic_id=clinic_id
            )
            
            if webhook_result and "resource" in webhook_result:
                clinic.calendly_webhook_signing_key = webhook_result["resource"].get("signing_key")
            
            db.commit()
            
            return {
                "success": True,
                "message": "Calendly connected successfully",
                "return_url": return_url
            }
            
    except Exception as e:
        logger.error(f"Calendly OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")

@router.post("/calendly/disconnect/{clinic_id}")
async def disconnect_calendly(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Disconnect Calendly integration"""
    if current_user.get("user_type") == "clinic" and current_user.get("user_id") != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            raise HTTPException(status_code=404, detail="Clinic not found")
        
        clinic.calendly_access_token = None
        clinic.calendly_refresh_token = None
        clinic.calendly_user_uri = None
        clinic.calendly_organization_uri = None
        clinic.calendly_webhook_signing_key = None
        clinic.calendly_connected_at = None
        clinic.calendly_sync_enabled = False
        
        db.commit()
        
        return {"success": True, "message": "Calendly disconnected successfully"}
        
    except Exception as e:
        logger.error(f"Error disconnecting Calendly: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to disconnect: {str(e)}")

# Enhanced Calendly Webhook Handler
@router.post("/calendly/webhook/{clinic_id}")
async def handle_calendly_webhook(
    clinic_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Enhanced webhook handler for all Calendly events"""
    try:
        # Get raw body for signature verification
        body = await request.body()
        payload = json.loads(body.decode())
        
        # Get clinic and verify webhook signature
        clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic:
            logger.error(f"Webhook received for unknown clinic {clinic_id}")
            return {"status": "ignored", "reason": "clinic not found"}
        
        # Verify webhook signature if signing key is available
        calendly_signature = request.headers.get("Calendly-Webhook-Signature")
        if clinic.calendly_webhook_signing_key and calendly_signature:
            if not calendly_service.verify_webhook_signature(
                body, 
                calendly_signature, 
                clinic.calendly_webhook_signing_key
            ):
                logger.error(f"Invalid webhook signature for clinic {clinic_id}")
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        event_type = payload.get("event")
        logger.info(f"Processing Calendly webhook: {event_type} for clinic {clinic_id}")
        
        # Handle different event types
        if event_type == "invitee.created":
            # New appointment booked
            background_tasks.add_task(
                calendly_service.handle_appointment_booking,
                db=db,
                clinic_id=clinic_id,
                webhook_payload=payload
            )
            
        elif event_type == "invitee.canceled":
            # Appointment cancelled
            background_tasks.add_task(
                calendly_service.handle_appointment_cancellation,
                db=db,
                clinic_id=clinic_id,
                webhook_payload=payload
            )
            
        elif event_type == "invitee_no_show.created":
            # Patient marked as no-show
            background_tasks.add_task(
                calendly_service.handle_no_show,
                db=db,
                clinic_id=clinic_id,
                webhook_payload=payload,
                is_deletion=False
            )
            
        elif event_type == "invitee_no_show.deleted":
            # No-show status removed
            background_tasks.add_task(
                calendly_service.handle_no_show,
                db=db,
                clinic_id=clinic_id,
                webhook_payload=payload,
                is_deletion=True
            )
        
        return {"status": "processed", "event": event_type}
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

# Direct Calendly API Operations
@router.post("/calendly/appointments/{appointment_id}/cancel")
async def cancel_calendly_appointment(
    appointment_id: int,
    cancel_request: AppointmentCancelRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a Calendly appointment directly via API"""
    try:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        # Verify user has access to the clinic
        if current_user.get("user_type") == "clinic" and current_user.get("user_id") != appointment.clinic_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get clinic and verify Calendly integration
        clinic = db.query(Clinic).filter(Clinic.id == appointment.clinic_id).first()
        if not clinic or not clinic.calendly_access_token:
            raise HTTPException(status_code=400, detail="Calendly not connected for this clinic")
        
        # Cancel via Calendly API if it's a Calendly appointment
        if appointment.external_system == "calendly" and appointment.calendly_invitee_uri:
            success = await calendly_service.cancel_calendly_event(
                access_token=clinic.calendly_access_token,
                invitee_uri=appointment.calendly_invitee_uri,
                reason=cancel_request.reason
            )
            
            if not success:
                raise HTTPException(status_code=500, detail="Failed to cancel appointment in Calendly")
        
        # Update local appointment status
        appointment.status = AppointmentStatus.CANCELLED
        appointment.notes = (appointment.notes or "") + f"\nCancelled via API at {datetime.utcnow()}"
        if cancel_request.reason:
            appointment.notes += f"\nReason: {cancel_request.reason}"
        
        db.commit()
        
        return {
            "success": True,
            "message": "Appointment cancelled successfully",
            "appointment_id": appointment_id
        }
        
    except Exception as e:
        logger.error(f"Error cancelling Calendly appointment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel appointment: {str(e)}")

@router.get("/calendly/event-types/{clinic_id}")
async def list_calendly_event_types(
    clinic_id: int,
    active: Optional[bool] = Query(True),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all Calendly event types for a clinic"""
    if current_user.get("user_type") == "clinic" and current_user.get("user_id") != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    
    if not clinic.calendly_access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    event_types = await calendly_service.list_event_types(
        access_token=clinic.calendly_access_token,
        active=active
    )
    
    if event_types is None:
        raise HTTPException(status_code=500, detail="Failed to fetch event types")
    
    return {
        "event_types": event_types,
        "total": len(event_types)
    }

@router.post("/calendly/event-types/{clinic_id}")
async def create_calendly_event_type(
    clinic_id: int,
    event_data: CalendlyEventTypeCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new event type in Calendly"""
    if current_user.get("user_type") == "clinic" and current_user.get("user_id") != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    
    if not clinic.calendly_access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    result = await calendly_service.create_event_type(
        access_token=clinic.calendly_access_token,
        name=event_data.name,
        duration=event_data.duration,
        color=event_data.color,
        description=event_data.description
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create event type")
    
    return result

@router.post("/calendly/sync/{clinic_id}")
async def sync_calendly_appointments(
    clinic_id: int,
    days_ahead: int = Body(30, description="Number of days ahead to sync"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync Calendly appointments with local database"""
    if current_user.get("user_type") == "clinic" and current_user.get("user_id") != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    
    if not clinic.calendly_access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    result = await calendly_service.sync_calendly_events_to_db(
        db=db,
        clinic_id=clinic_id,
        access_token=clinic.calendly_access_token,
        days_ahead=days_ahead
    )
    
    return result

@router.get("/calendly/scheduling-link/{clinic_id}")
async def create_calendly_scheduling_link(
    clinic_id: int,
    event_type_uri: str = Query(..., description="Calendly event type URI"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a single-use Calendly scheduling link"""
    if current_user.get("user_type") == "clinic" and current_user.get("user_id") != clinic_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    
    if not clinic.calendly_access_token:
        raise HTTPException(status_code=400, detail="Calendly not connected")
    
    result = await calendly_service.create_scheduling_link(
        access_token=clinic.calendly_access_token,
        event_type_uri=event_type_uri
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create scheduling link")
    
    return result