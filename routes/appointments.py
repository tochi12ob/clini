"""
Calendar Routes for Clinic AI Assistant
Handles appointment scheduling, availability, and calendar management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timedelta
from database import get_db
from services.calender_service import calendar_service
from schemas import (
    AppointmentCreate, 
    AppointmentUpdate, 
    AppointmentResponse,
    TimeSlot,
    AvailabilityRequest,
    AppointmentReschedule
)
from models import Appointment

router = APIRouter()

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
        raise HTTPException(status_code=500, detail=f"Error checking calendar sync status: {str(e)}")

@router.post("/clinics/{clinic_id}/calendar-sync")
async def setup_calendar_sync(
    clinic_id: int,
    credentials: dict,
    db: Session = Depends(get_db)
):
    """Setup Google Calendar synchronization for a clinic"""
    try:
        success = calendar_service.initialize_google_calendar(str(credentials))
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to initialize Google Calendar integration"
            )
        
        return {
            "success": True,
            "message": "Google Calendar integration enabled successfully",
            "clinic_id": clinic_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting up calendar sync: {str(e)}")

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
            # Join with Patient table to search by phone
            from models import Patient
            query = query.join(Patient).filter(Patient.phone == patient_phone)
        
        if date_from:
            query = query.filter(Appointment.date_time >= datetime.combine(date_from, datetime.min.time()))
        
        if date_to:
            query = query.filter(Appointment.date_time <= datetime.combine(date_to, datetime.max.time()))
        
        if status:
            query = query.filter(Appointment.status == status)
        
        appointments = query.order_by(Appointment.date_time.desc()).limit(50).all()
        
        return {
            "appointments": [
                {
                    "id": apt.id,
                    "patient_id": apt.patient_id,
                    "date_time": apt.date_time.isoformat(),
                    "duration_minutes": apt.duration_minutes,
                    "appointment_type": apt.appointment_type,
                    "status": apt.status,
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
                "date_time": appointment.date_time.isoformat(),
                "duration_minutes": appointment.duration_minutes,
                "appointment_type": appointment.appointment_type,
                "status": appointment.status,
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
                    "date_time": apt.date_time.isoformat(),
                    "duration_minutes": apt.duration_minutes,
                    "appointment_type": apt.appointment_type,
                    "status": apt.status,
                    "notes": apt.notes,
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
            "date_time": appointment.date_time.isoformat(),
            "duration_minutes": appointment.duration_minutes,
            "appointment_type": appointment.appointment_type,
            "status": appointment.status,
            "notes": appointment.notes,
            "created_at": appointment.created_at.isoformat() if appointment.created_at else None,
            "updated_at": appointment.updated_at.isoformat() if appointment.updated_at else None,
            "cancelled_at": appointment.cancelled_at.isoformat() if appointment.cancelled_at else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving appointment details: {str(e)}")

@router.get("/clinics/{clinic_id}/calendar-sync")
async def get_calendar_sync_status(
    clinic_id: int,
    db: Session = Depends(get_db)
):
    """Get calendar synchronization status for a clinic"""
    try:
        # This would check if Google Calendar is configured for the clinic
        sync_enabled = calendar_service.google_service is not None
        
        return {
            "clinic_id": clinic_id,
            "google_calendar_enabled": sync_enabled,
            "sync_status": "active" if sync_enabled else "disabled"
        }
        
    except Exception as e:
        print("not authorized")