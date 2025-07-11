"""
Calendar Service for Clinic AI Assistant
Handles appointment scheduling, availability checking, and calendar integrations
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
from sqlalchemy.orm import Session
from models import Appointment, Clinic, Patient
from schemas import AppointmentCreate, AppointmentUpdate, TimeSlot
import os
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self):
        self.google_service = None
        self.default_timezone = "America/New_York"
    
    def initialize_google_calendar(self, credentials_json: str) -> bool:
        """Initialize Google Calendar API service"""
        try:
            creds = Credentials.from_authorized_user_info(eval(credentials_json))
            self.google_service = build('calendar', 'v3', credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar: {e}")
            return False
    
    def get_available_slots(
        self, 
        clinic_id: int, 
        date: datetime.date,
        duration_minutes: int = 30,
        db: Session = None
    ) -> List[TimeSlot]:
        """Get available appointment slots for a specific date"""
        try:
            # Get clinic working hours
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                return []
            
            # Default working hours (can be stored in clinic settings)
            start_hour = getattr(clinic, 'start_hour', 9)  # 9 AM
            end_hour = getattr(clinic, 'end_hour', 17)    # 5 PM
            
            # Generate all possible slots
            all_slots = []
            start_time = datetime.combine(date, time(start_hour, 0))
            end_time = datetime.combine(date, time(end_hour, 0))
            
            current_time = start_time
            while current_time + timedelta(minutes=duration_minutes) <= end_time:
                all_slots.append(current_time)
                current_time += timedelta(minutes=duration_minutes)
            
            # Get existing appointments for the date
            existing_appointments = db.query(Appointment).filter(
                Appointment.clinic_id == clinic_id,
                Appointment.date_time >= datetime.combine(date, time.min),
                Appointment.date_time < datetime.combine(date + timedelta(days=1), time.min),
                Appointment.status.in_(['scheduled', 'confirmed'])
            ).all()
            
            # Remove booked slots
            booked_times = [apt.date_time for apt in existing_appointments]
            available_slots = []
            
            for slot_time in all_slots:
                is_available = True
                for booked_time in booked_times:
                    if abs((slot_time - booked_time).total_seconds()) < duration_minutes * 60:
                        is_available = False
                        break
                
                if is_available:
                    available_slots.append(TimeSlot(
                        start_time=slot_time,
                        end_time=slot_time + timedelta(minutes=duration_minutes),
                        is_available=True
                    ))
            
            return available_slots
            
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return []
    
    def book_appointment(
        self, 
        appointment_data: AppointmentCreate, 
        db: Session
    ) -> Optional[Appointment]:
        """Book a new appointment"""
        try:
            # Check if slot is still available
            existing = db.query(Appointment).filter(
                Appointment.clinic_id == appointment_data.clinic_id,
                Appointment.date_time == appointment_data.date_time,
                Appointment.status.in_(['scheduled', 'confirmed'])
            ).first()
            
            if existing:
                logger.warning(f"Slot {appointment_data.date_time} already booked")
                return None
            
            # Create appointment
            appointment = Appointment(
                clinic_id=appointment_data.clinic_id,
                patient_id=appointment_data.patient_id,
                date_time=appointment_data.date_time,
                duration_minutes=appointment_data.duration_minutes or 30,
                appointment_type=appointment_data.appointment_type or "consultation",
                status="scheduled",
                notes=appointment_data.notes
            )
            
            db.add(appointment)
            db.commit()
            db.refresh(appointment)
            
            # Sync with Google Calendar if available
            if self.google_service:
                self._sync_to_google_calendar(appointment, db)
            
            logger.info(f"Appointment booked: {appointment.id}")
            return appointment
            
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            db.rollback()
            return None
    
    def reschedule_appointment(
        self,
        appointment_id: int,
        new_datetime: datetime,
        db: Session
    ) -> bool:
        """Reschedule an existing appointment"""
        try:
            appointment = db.query(Appointment).filter(
                Appointment.id == appointment_id
            ).first()
            
            if not appointment:
                return False
            
            # Check if new slot is available
            conflict = db.query(Appointment).filter(
                Appointment.clinic_id == appointment.clinic_id,
                Appointment.date_time == new_datetime,
                Appointment.status.in_(['scheduled', 'confirmed']),
                Appointment.id != appointment_id
            ).first()
            
            if conflict:
                return False
            
            old_datetime = appointment.date_time
            appointment.date_time = new_datetime
            appointment.status = "rescheduled"
            
            db.commit()
            
            # Update Google Calendar if available
            if self.google_service:
                self._update_google_calendar_event(appointment, db)
            
            logger.info(f"Appointment {appointment_id} rescheduled from {old_datetime} to {new_datetime}")
            return True
            
        except Exception as e:
            logger.error(f"Error rescheduling appointment: {e}")
            db.rollback()
            return False
    
    def cancel_appointment(self, appointment_id: int, db: Session) -> bool:
        """Cancel an appointment"""
        try:
            appointment = db.query(Appointment).filter(
                Appointment.id == appointment_id
            ).first()
            
            if not appointment:
                return False
            
            appointment.status = "cancelled"
            appointment.cancelled_at = datetime.now()
            
            db.commit()
            
            # Remove from Google Calendar if available
            if self.google_service:
                self._delete_google_calendar_event(appointment, db)
            
            logger.info(f"Appointment {appointment_id} cancelled")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling appointment: {e}")
            db.rollback()
            return False
    
    def get_upcoming_appointments(
        self, 
        clinic_id: int, 
        days_ahead: int = 7,
        db: Session = None
    ) -> List[Appointment]:
        """Get upcoming appointments for a clinic"""
        try:
            start_date = datetime.now()
            end_date = start_date + timedelta(days=days_ahead)
            
            appointments = db.query(Appointment).filter(
                Appointment.clinic_id == clinic_id,
                Appointment.date_time >= start_date,
                Appointment.date_time <= end_date,
                Appointment.status.in_(['scheduled', 'confirmed'])
            ).order_by(Appointment.date_time).all()
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting upcoming appointments: {e}")
            return []
    
    def _sync_to_google_calendar(self, appointment: Appointment, db: Session):
        """Sync appointment to Google Calendar"""
        try:
            if not self.google_service:
                return
            
            clinic = db.query(Clinic).filter(Clinic.id == appointment.clinic_id).first()
            patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
            
            event = {
                'summary': f'Appointment - {patient.name if patient else "Patient"}',
                'description': f'Clinic: {clinic.name if clinic else "Unknown"}\nNotes: {appointment.notes or ""}',
                'start': {
                    'dateTime': appointment.date_time.isoformat(),
                    'timeZone': self.default_timezone,
                },
                'end': {
                    'dateTime': (appointment.date_time + timedelta(minutes=appointment.duration_minutes)).isoformat(),
                    'timeZone': self.default_timezone,
                },
            }
            
            created_event = self.google_service.events().insert(
                calendarId='primary', 
                body=event
            ).execute()
            
            appointment.google_event_id = created_event['id']
            db.commit()
            
        except Exception as e:
            logger.error(f"Error syncing to Google Calendar: {e}")
    
    def _update_google_calendar_event(self, appointment: Appointment, db: Session):
        """Update Google Calendar event"""
        try:
            if not self.google_service or not appointment.google_event_id:
                return
            
            clinic = db.query(Clinic).filter(Clinic.id == appointment.clinic_id).first()
            patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
            
            event = {
                'summary': f'Appointment - {patient.name if patient else "Patient"}',
                'description': f'Clinic: {clinic.name if clinic else "Unknown"}\nNotes: {appointment.notes or ""}',
                'start': {
                    'dateTime': appointment.date_time.isoformat(),
                    'timeZone': self.default_timezone,
                },
                'end': {
                    'dateTime': (appointment.date_time + timedelta(minutes=appointment.duration_minutes)).isoformat(),
                    'timeZone': self.default_timezone,
                },
            }
            
            self.google_service.events().update(
                calendarId='primary',
                eventId=appointment.google_event_id,
                body=event
            ).execute()
            
        except Exception as e:
            logger.error(f"Error updating Google Calendar event: {e}")
    
    def _delete_google_calendar_event(self, appointment: Appointment, db: Session):
        """Delete Google Calendar event"""
        try:
            if not self.google_service or not appointment.google_event_id:
                return
            
            self.google_service.events().delete(
                calendarId='primary',
                eventId=appointment.google_event_id
            ).execute()
            
        except Exception as e:
            logger.error(f"Error deleting Google Calendar event: {e}")

# Global instance
calendar_service = CalendarService()