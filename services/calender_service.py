"""
Calendar Service for Clinic AI Assistant
Handles appointment scheduling, availability checking, and calendar integrations
Now supports both Google Calendar and Calendly integrations with full webhook support
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
from sqlalchemy.orm import Session
from models import Appointment, Clinic, Patient, AppointmentStatus
from schemas import AppointmentCreate, AppointmentUpdate, TimeSlot
import os
from zoneinfo import ZoneInfo
import httpx
import asyncio

logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self):
        self.google_service = None
        self.default_timezone = "America/New_York"
        self.calendly_base_url = "https://api.calendly.com"
    
    def initialize_google_calendar(self, credentials_json: str) -> bool:
        """Initialize Google Calendar API service"""
        try:
            creds = Credentials.from_authorized_user_info(eval(credentials_json))
            self.google_service = build('calendar', 'v3', credentials=creds)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar: {e}")
            return False
    
    def _get_calendly_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for Calendly API requests"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_available_slots(
        self, 
        clinic_id: int, 
        date: datetime.date,
        duration_minutes: int = 30,
        db: Session = None
    ) -> List[TimeSlot]:
        """Get available appointment slots for a specific date"""
        try:
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                return []
            
            # Check if clinic has Calendly integration
            if hasattr(clinic, 'calendly_access_token') and clinic.calendly_access_token:
                return self._get_calendly_available_slots(clinic, date, duration_minutes)
            else:
                # Fallback to local availability calculation
                return self._get_local_available_slots(clinic, date, duration_minutes, db)
            
        except Exception as e:
            logger.error(f"Error getting available slots: {e}")
            return []
    
    def _get_calendly_available_slots(
        self,
        clinic: Clinic,
        date: datetime.date,
        duration_minutes: int
    ) -> List[TimeSlot]:
        """Get available slots from Calendly"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self._async_get_calendly_slots(clinic, date, duration_minutes)
            )
            return result
        except Exception as e:
            logger.error(f"Error getting Calendly slots: {e}")
            return []
    
    async def _async_get_calendly_slots(
        self,
        clinic: Clinic,
        date: datetime.date,
        duration_minutes: int
    ) -> List[TimeSlot]:
        """Async method to get Calendly available slots"""
        available_slots = []
        
        try:
            async with httpx.AsyncClient() as client:
                # Get user info to get event types
                user_response = await client.get(
                    f"{self.calendly_base_url}/users/me",
                    headers=self._get_calendly_headers(clinic.calendly_access_token)
                )
                
                if user_response.status_code != 200:
                    logger.error(f"Failed to get Calendly user info: {user_response.text}")
                    return []
                
                user_data = user_response.json()
                user_uri = user_data["resource"]["uri"]
                
                # Get event types
                event_types_response = await client.get(
                    f"{self.calendly_base_url}/event_types",
                    headers=self._get_calendly_headers(clinic.calendly_access_token),
                    params={"user": user_uri, "active": "true"}
                )
                
                if event_types_response.status_code != 200:
                    logger.error(f"Failed to get Calendly event types: {event_types_response.text}")
                    return []
                
                event_types = event_types_response.json().get("collection", [])
                
                # Find matching event type by duration
                matching_event_type = None
                for event_type in event_types:
                    if event_type.get("duration") == duration_minutes:
                        matching_event_type = event_type
                        break
                
                if not matching_event_type and event_types:
                    # Use first active event type as fallback
                    matching_event_type = event_types[0]
                
                if not matching_event_type:
                    return []
                
                # Get available times for the event type
                start_time = datetime.combine(date, time.min)
                end_time = datetime.combine(date, time.max)
                
                availability_response = await client.get(
                    f"{self.calendly_base_url}/event_type_available_times",
                    headers=self._get_calendly_headers(clinic.calendly_access_token),
                    params={
                        "event_type": matching_event_type["uri"],
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat()
                    }
                )
                
                if availability_response.status_code == 200:
                    slots_data = availability_response.json().get("collection", [])
                    for slot in slots_data:
                        start = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
                        end = datetime.fromisoformat(slot["end_time"].replace("Z", "+00:00"))
                        available_slots.append(TimeSlot(
                            start_time=start,
                            end_time=end,
                            is_available=True
                        ))
                
        except Exception as e:
            logger.error(f"Error in async Calendly slots retrieval: {e}")
        
        return available_slots
    
    def _get_local_available_slots(
        self,
        clinic: Clinic,
        date: datetime.date,
        duration_minutes: int,
        db: Session
    ) -> List[TimeSlot]:
        """Get available slots using local database (original logic)"""
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
            Appointment.clinic_id == clinic.id,
            Appointment.appointment_datetime >= datetime.combine(date, time.min),
            Appointment.appointment_datetime < datetime.combine(date + timedelta(days=1), time.min),
            Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])
        ).all()
        
        # Remove booked slots
        booked_times = [apt.appointment_datetime for apt in existing_appointments]
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
    
    def book_appointment(
        self, 
        appointment_data: AppointmentCreate, 
        db: Session
    ) -> Optional[Appointment]:
        """Book a new appointment"""
        try:
            # Get clinic to check integration type
            clinic = db.query(Clinic).filter(Clinic.id == appointment_data.clinic_id).first()
            if not clinic:
                logger.error(f"Clinic {appointment_data.clinic_id} not found")
                return None
            
            # Check if slot is still available
            existing = db.query(Appointment).filter(
                Appointment.clinic_id == appointment_data.clinic_id,
                Appointment.appointment_datetime == appointment_data.appointment_datetime,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])
            ).first()
            
            if existing:
                logger.warning(f"Slot {appointment_data.appointment_datetime} already booked")
                return None
            
            # Create appointment
            appointment = Appointment(
                clinic_id=appointment_data.clinic_id,
                patient_id=appointment_data.patient_id,
                appointment_datetime=appointment_data.appointment_datetime,
                duration_minutes=appointment_data.duration_minutes or 30,
                appointment_type=appointment_data.appointment_type or "consultation",
                status=AppointmentStatus.SCHEDULED,
                notes=appointment_data.notes
            )
            
            db.add(appointment)
            db.commit()
            db.refresh(appointment)
            
            # Sync with calendar service
            if hasattr(clinic, 'calendly_access_token') and clinic.calendly_access_token:
                # For Calendly, we'll create an invitee booking
                self._create_calendly_booking(appointment, clinic, db)
            elif self.google_service:
                # Sync with Google Calendar if available
                self._sync_to_google_calendar(appointment, db)
            
            logger.info(f"Appointment booked: {appointment.id}")
            return appointment
            
        except Exception as e:
            logger.error(f"Error booking appointment: {e}")
            db.rollback()
            return None
    
    def _create_calendly_booking(self, appointment: Appointment, clinic: Clinic, db: Session):
        """Create a booking in Calendly (note: Calendly API doesn't directly support creating bookings)"""
        try:
            # Calendly doesn't allow direct booking creation via API
            # Instead, we'll store the Calendly scheduling link in the appointment
            # The actual booking happens through Calendly's web interface
            
            # We can store a reference that this appointment is pending Calendly confirmation
            appointment.external_system = "calendly"
            appointment.notes = (appointment.notes or "") + "\n[Pending Calendly confirmation]"
            db.commit()
            
            logger.info(f"Appointment {appointment.id} marked for Calendly sync")
            
        except Exception as e:
            logger.error(f"Error creating Calendly booking: {e}")
    
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
                Appointment.appointment_datetime == new_datetime,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]),
                Appointment.id != appointment_id
            ).first()
            
            if conflict:
                return False
            
            old_datetime = appointment.appointment_datetime
            appointment.appointment_datetime = new_datetime
            appointment.status = AppointmentStatus.RESCHEDULED
            
            # Handle Calendly rescheduling
            if appointment.external_system == "calendly":
                clinic = db.query(Clinic).filter(Clinic.id == appointment.clinic_id).first()
                if clinic and clinic.calendly_access_token:
                    # Note: Calendly API doesn't support direct rescheduling
                    # This would typically require cancelling and rebooking
                    appointment.notes = (appointment.notes or "") + f"\n[Rescheduled from {old_datetime} - requires Calendly update]"
            
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
            
            appointment.status = AppointmentStatus.CANCELLED
            
            # Handle Calendly cancellation
            if appointment.external_system == "calendly":
                clinic = db.query(Clinic).filter(Clinic.id == appointment.clinic_id).first()
                if clinic and clinic.calendly_access_token and appointment.calendly_invitee_uri:
                    # This would be handled by the Calendly service in practice
                    appointment.notes = (appointment.notes or "") + f"\n[Cancelled via system at {datetime.now()}]"
            
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
                Appointment.appointment_datetime >= start_date,
                Appointment.appointment_datetime <= end_date,
                Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED])
            ).order_by(Appointment.appointment_datetime).all()
            
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
                'summary': f'Appointment - {patient.first_name} {patient.last_name}' if patient else "Patient Appointment",
                'description': f'Clinic: {clinic.name if clinic else "Unknown"}\nNotes: {appointment.notes or ""}',
                'start': {
                    'dateTime': appointment.appointment_datetime.isoformat(),
                    'timeZone': self.default_timezone,
                },
                'end': {
                    'dateTime': (appointment.appointment_datetime + timedelta(minutes=appointment.duration_minutes)).isoformat(),
                    'timeZone': self.default_timezone,
                },
            }
            
            created_event = self.google_service.events().insert(
                calendarId='primary', 
                body=event
            ).execute()
            
            # Store Google event ID for future updates
            appointment.external_id = created_event['id']
            appointment.external_system = "google"
            db.commit()
            
        except Exception as e:
            logger.error(f"Error syncing to Google Calendar: {e}")
    
    def _update_google_calendar_event(self, appointment: Appointment, db: Session):
        """Update Google Calendar event"""
        try:
            if not self.google_service or not appointment.external_id or appointment.external_system != "google":
                return
            
            clinic = db.query(Clinic).filter(Clinic.id == appointment.clinic_id).first()
            patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
            
            event = {
                'summary': f'Appointment - {patient.first_name} {patient.last_name}' if patient else "Patient Appointment",
                'description': f'Clinic: {clinic.name if clinic else "Unknown"}\nNotes: {appointment.notes or ""}',
                'start': {
                    'dateTime': appointment.appointment_datetime.isoformat(),
                    'timeZone': self.default_timezone,
                },
                'end': {
                    'dateTime': (appointment.appointment_datetime + timedelta(minutes=appointment.duration_minutes)).isoformat(),
                    'timeZone': self.default_timezone,
                },
            }
            
            self.google_service.events().update(
                calendarId='primary',
                eventId=appointment.external_id,
                body=event
            ).execute()
            
        except Exception as e:
            logger.error(f"Error updating Google Calendar event: {e}")
    
    def _delete_google_calendar_event(self, appointment: Appointment, db: Session):
        """Delete Google Calendar event"""
        try:
            if not self.google_service or not appointment.external_id or appointment.external_system != "google":
                return
            
            self.google_service.events().delete(
                calendarId='primary',
                eventId=appointment.external_id
            ).execute()
            
        except Exception as e:
            logger.error(f"Error deleting Google Calendar event: {e}")

# Global instance
calendar_service = CalendarService()