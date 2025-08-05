"""
Enhanced Calendly Integration Service
Comprehensive appointment management with webhooks and direct API operations
Extends the existing CalendlyService with enhanced functionality
"""
import os
import httpx
import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import json
from fastapi import HTTPException

load_dotenv()

logger = logging.getLogger(__name__)

# Extend the existing CalendlyService class
class CalendlyService:
    """Enhanced service for comprehensive Calendly integration"""
    
    def __init__(self):
        self.base_url = "https://api.calendly.com"
        self.webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "https://your-domain.com")
        
    def _get_headers(self, access_token: str) -> Dict[str, str]:
        """Get headers for Calendly API requests"""
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def verify_webhook_signature(self, payload: bytes, signature: str, signing_key: str) -> bool:
        """Verify Calendly webhook signature for security"""
        try:
            expected_signature = hmac.new(
                signing_key.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            return False
    
    async def get_current_user(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Get current Calendly user information"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers=self._get_headers(access_token)
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting Calendly user: {str(e)}")
            return None
    
    async def get_event_details(self, access_token: str, event_uri: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific event"""
        try:
            # Extract UUID from URI
            event_uuid = event_uri.split('/')[-1]
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/scheduled_events/{event_uuid}",
                    headers=self._get_headers(access_token)
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting event details: {str(e)}")
            return None
    
    async def get_invitee_details(self, access_token: str, event_uri: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about invitees for an event"""
        try:
            # Extract UUID from URI
            event_uuid = event_uri.split('/')[-1]
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/scheduled_events/{event_uuid}/invitees",
                    headers=self._get_headers(access_token)
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting invitee details: {str(e)}")
            return None
    
    async def cancel_calendly_event(
        self,
        access_token: str,
        invitee_uri: str,
        reason: Optional[str] = None
    ) -> bool:
        """Cancel a Calendly event"""
        try:
            # Extract UUID from URI
            invitee_uuid = invitee_uri.split('/')[-1]
            
            cancel_data = {}
            if reason:
                cancel_data["reason"] = reason
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/scheduled_events/{invitee_uuid}/cancellation",
                    headers=self._get_headers(access_token),
                    json=cancel_data
                )
                response.raise_for_status()
                return True
                
        except httpx.HTTPError as e:
            logger.error(f"Error canceling Calendly event: {str(e)}")
            return False
    
    async def create_event_type(
        self, 
        access_token: str,
        name: str,
        duration: int,
        color: str = "#1a73e8",
        description: Optional[str] = None,
        scheduling_url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new event type (appointment slot type) in Calendly"""
        try:
            user_data = await self.get_current_user(access_token)
            if not user_data:
                return None
            
            user_uri = user_data["resource"]["uri"]
            
            event_data = {
                "name": name,
                "duration": duration,
                "color": color,
                "active": True,
                "kind": "solo",
                "scheduling_url": scheduling_url
            }
            
            if description:
                event_data["description"] = description
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/event_types",
                    headers=self._get_headers(access_token),
                    json=event_data
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error creating Calendly event type: {str(e)}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None
    
    async def list_event_types(
        self, 
        access_token: str,
        active: Optional[bool] = True,
        count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """List all event types for the user"""
        try:
            user_data = await self.get_current_user(access_token)
            if not user_data:
                return None
            
            user_uri = user_data["resource"]["uri"]
            
            params = {
                "user": user_uri,
                "count": count
            }
            
            if active is not None:
                params["active"] = str(active).lower()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/event_types",
                    headers=self._get_headers(access_token),
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return data.get("collection", [])
                
        except httpx.HTTPError as e:
            logger.error(f"Error listing Calendly event types: {str(e)}")
            return None
    
    async def get_availability(
        self,
        access_token: str,
        event_type_uri: str,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[List[Dict[str, Any]]]:
        """Get available time slots for a specific event type"""
        try:
            params = {
                "event_type": event_type_uri,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/event_type_available_times",
                    headers=self._get_headers(access_token),
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return data.get("collection", [])
                
        except httpx.HTTPError as e:
            logger.error(f"Error getting Calendly availability: {str(e)}")
            return None
    
    async def create_webhook_subscription(
        self,
        access_token: str,
        clinic_id: int,
        events: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a webhook subscription for Calendly events"""
        if events is None:
            events = [
                "invitee.created",
                "invitee.canceled",
                "invitee_no_show.created",
                "invitee_no_show.deleted"
            ]
        
        try:
            user_data = await self.get_current_user(access_token)
            if not user_data:
                return None
            
            organization_uri = user_data["resource"]["current_organization"]
            
            webhook_data = {
                "url": f"{self.webhook_base_url}/calendar/calendly/webhook/{clinic_id}",
                "events": events,
                "organization": organization_uri,
                "scope": "organization",
                "signing_key": os.urandom(32).hex()
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/webhook_subscriptions",
                    headers=self._get_headers(access_token),
                    json=webhook_data
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error creating Calendly webhook: {str(e)}")
            return None
    
    async def list_scheduled_events(
        self,
        access_token: str,
        min_start_time: Optional[datetime] = None,
        max_start_time: Optional[datetime] = None,
        status: Optional[str] = "active",
        count: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """List scheduled events (appointments)"""
        try:
            user_data = await self.get_current_user(access_token)
            if not user_data:
                return None
            
            user_uri = user_data["resource"]["uri"]
            
            params = {
                "user": user_uri,
                "count": count
            }
            
            if min_start_time:
                params["min_start_time"] = min_start_time.isoformat()
            if max_start_time:
                params["max_start_time"] = max_start_time.isoformat()
            if status:
                params["status"] = status
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/scheduled_events",
                    headers=self._get_headers(access_token),
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                return data.get("collection", [])
                
        except httpx.HTTPError as e:
            logger.error(f"Error listing Calendly events: {str(e)}")
            return None
    
    async def cancel_event(
        self,
        access_token: str,
        event_uri: str,
        reason: Optional[str] = None
    ) -> bool:
        """Cancel a scheduled event"""
        try:
            cancel_data = {}
            if reason:
                cancel_data["reason"] = reason
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{event_uri}/cancellation",
                    headers=self._get_headers(access_token),
                    json=cancel_data
                )
                response.raise_for_status()
                return True
                
        except httpx.HTTPError as e:
            logger.error(f"Error canceling Calendly event: {str(e)}")
            return False
    
    async def create_scheduling_link(
        self,
        access_token: str,
        event_type_uri: str,
        max_event_count: int = 1,
        owner_type: str = "EventType"
    ) -> Optional[Dict[str, Any]]:
        """Create a single-use scheduling link"""
        try:
            link_data = {
                "max_event_count": max_event_count,
                "owner": event_type_uri,
                "owner_type": owner_type
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/scheduling_links",
                    headers=self._get_headers(access_token),
                    json=link_data
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"Error creating scheduling link: {str(e)}")
            return None
    
    def _build_appointment_notes(self, event_data: Dict[str, Any], event: Dict[str, Any]) -> str:
        """Build appointment notes from Calendly data"""
        notes = f"Calendly Event: {event.get('name', 'N/A')}\n"
        notes += f"Event URI: {event.get('uri', 'N/A')}\n"
        
        if event_data.get("name"):
            notes += f"Patient Name: {event_data['name']}\n"
        
        if event_data.get("email"):
            notes += f"Email: {event_data['email']}\n"
        
        if event_data.get("text_reminder_number"):
            notes += f"Phone: {event_data['text_reminder_number']}\n"
        
        # Add any custom questions/answers
        questions_and_responses = event_data.get("questions_and_responses", [])
        if questions_and_responses:
            notes += "\nCustom Questions:\n"
            for qa in questions_and_responses:
                question = qa.get("question", "Unknown question")
                answer = qa.get("answer", "No answer")
                notes += f"- {question}: {answer}\n"
        
        return notes.strip()
    
    async def handle_appointment_booking(
        self,
        db: Session,
        clinic_id: int,
        webhook_payload: Dict[str, Any]
    ) -> Optional[int]:
        """Handle new appointment booking from Calendly webhook"""
        try:
            from models import Appointment, Patient, AppointmentStatus
            
            # Extract event and invitee data
            event_data = webhook_payload.get("payload", {})
            event = event_data.get("event", {})
            
            # Parse datetime
            start_time = datetime.fromisoformat(event.get("start_time", "").replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(event.get("end_time", "").replace("Z", "+00:00"))
            duration_minutes = int((end_time - start_time).total_seconds() / 60)
            
            # Check if appointment already exists
            existing = db.query(Appointment).filter(
                Appointment.calendly_event_uri == event.get("uri")
            ).first()
            
            if existing:
                logger.info(f"Appointment already exists for event {event.get('uri')}")
                return existing.id
            
            # Extract patient information
            invitee_name = event_data.get("name", "Unknown")
            invitee_email = event_data.get("email", "")
            invitee_phone = event_data.get("text_reminder_number", "")
            
            # Parse name
            name_parts = invitee_name.split(" ", 1)
            first_name = name_parts[0] if name_parts else "Unknown"
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            
            # Find or create patient
            patient = None
            if invitee_email:
                patient = db.query(Patient).filter(
                    Patient.clinic_id == clinic_id,
                    Patient.email == invitee_email
                ).first()
            
            if not patient and invitee_phone:
                patient = db.query(Patient).filter(
                    Patient.clinic_id == clinic_id,
                    Patient.phone == invitee_phone
                ).first()
            
            if not patient:
                # Create new patient
                patient = Patient(
                    clinic_id=clinic_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=invitee_email,
                    phone=invitee_phone,
                    preferred_contact_method="email" if invitee_email else "phone"
                )
                db.add(patient)
                db.flush()  # Get the patient ID
            
            # Create appointment
            appointment = Appointment(
                clinic_id=clinic_id,
                patient_id=patient.id,
                appointment_datetime=start_time,
                duration_minutes=duration_minutes,
                appointment_type=event.get("name", "Calendly Appointment"),
                status=AppointmentStatus.CONFIRMED,
                external_id=event.get("uri"),
                external_system="calendly",
                calendly_event_uri=event.get("uri"),
                calendly_invitee_uri=event_data.get("uri"),
                notes=self._build_appointment_notes(event_data, event),
                confirmed_at=datetime.utcnow(),
                confirmation_method="calendly"
            )
            
            db.add(appointment)
            db.commit()
            db.refresh(appointment)
            
            logger.info(f"Created appointment {appointment.id} from Calendly booking")
            return appointment.id
            
        except Exception as e:
            logger.error(f"Error handling appointment booking: {str(e)}")
            db.rollback()
            return None
    
    async def handle_appointment_cancellation(
        self,
        db: Session,
        clinic_id: int,
        webhook_payload: Dict[str, Any]
    ) -> bool:
        """Handle appointment cancellation from Calendly webhook"""
        try:
            from models import Appointment, AppointmentStatus
            
            event_data = webhook_payload.get("payload", {})
            event = event_data.get("event", {})
            cancellation = event_data.get("cancellation", {})
            
            # Find appointment
            appointment = db.query(Appointment).filter(
                Appointment.clinic_id == clinic_id,
                Appointment.calendly_event_uri == event.get("uri")
            ).first()
            
            if not appointment:
                logger.warning(f"Appointment not found for cancelled event {event.get('uri')}")
                return False
            
            # Update appointment status
            appointment.status = AppointmentStatus.CANCELLED
            appointment.notes = (appointment.notes or "") + f"\n\nCancelled via Calendly at {datetime.utcnow()}"
            
            # Add cancellation reason if provided
            if cancellation.get("reason"):
                appointment.notes += f"\nReason: {cancellation['reason']}"
            
            # Add cancellation details
            if cancellation.get("canceled_by"):
                appointment.notes += f"\nCancelled by: {cancellation['canceled_by']}"
            
            db.commit()
            
            logger.info(f"Cancelled appointment {appointment.id} from Calendly webhook")
            return True
            
        except Exception as e:
            logger.error(f"Error handling appointment cancellation: {str(e)}")
            db.rollback()
            return False
    
    async def handle_no_show(
        self,
        db: Session,
        clinic_id: int,
        webhook_payload: Dict[str, Any],
        is_deletion: bool = False
    ) -> bool:
        """Handle no-show events from Calendly webhook"""
        try:
            from models import Appointment, AppointmentStatus
            
            event_data = webhook_payload.get("payload", {})
            invitee_no_show = event_data.get("invitee_no_show", {})
            invitee = invitee_no_show.get("invitee", {})
            
            # Find appointment by invitee URI
            appointment = db.query(Appointment).filter(
                Appointment.clinic_id == clinic_id,
                Appointment.calendly_invitee_uri == invitee.get("uri")
            ).first()
            
            if not appointment:
                logger.warning(f"Appointment not found for no-show event {invitee.get('uri')}")
                return False
            
            if is_deletion:
                # No-show was deleted/unmarked
                appointment.status = AppointmentStatus.COMPLETED
                appointment.notes = (appointment.notes or "") + f"\n\nNo-show unmarked via Calendly at {datetime.utcnow()}"
            else:
                # Mark as no-show
                appointment.status = AppointmentStatus.NO_SHOW
                appointment.notes = (appointment.notes or "") + f"\n\nMarked as no-show via Calendly at {datetime.utcnow()}"
            
            db.commit()
            
            logger.info(f"Updated appointment {appointment.id} no-show status from Calendly webhook")
            return True
            
        except Exception as e:
            logger.error(f"Error handling no-show event: {str(e)}")
            db.rollback()
            return False
    
    async def sync_calendly_events_to_db(
        self,
        db: Session,
        clinic_id: int,
        access_token: str,
        days_ahead: int = 30
    ) -> Dict[str, Any]:
        """Sync Calendly events to the local database"""
        try:
            from models import Appointment, Patient, AppointmentStatus
            from datetime import timezone
            
            # Get events for the next X days
            min_start = datetime.now(timezone.utc)
            max_start = min_start + timedelta(days=days_ahead)
            
            events = await self.list_scheduled_events(
                access_token=access_token,
                min_start_time=min_start,
                max_start_time=max_start
            )
            
            if not events:
                return {"synced": 0, "errors": 0, "message": "No events to sync"}
            
            synced = 0
            errors = 0
            
            for event in events:
                try:
                    # Extract event details
                    start_time = datetime.fromisoformat(event["start_time"].replace("Z", "+00:00"))
                    end_time = datetime.fromisoformat(event["end_time"].replace("Z", "+00:00"))
                    duration = int((end_time - start_time).total_seconds() / 60)
                    
                    # Check if appointment already exists (by external ID)
                    existing = db.query(Appointment).filter(
                        Appointment.clinic_id == clinic_id,
                        Appointment.external_id == event["uri"]
                    ).first()
                    
                    if not existing:
                        # Get invitee details for this event
                        invitee_data = await self.get_invitee_details(access_token, event["uri"])
                        invitees = invitee_data.get("collection", []) if invitee_data else []
                        
                        # Use first invitee or create placeholder patient
                        patient_id = None
                        if invitees:
                            invitee = invitees[0]
                            # Find or create patient
                            patient = db.query(Patient).filter(
                                Patient.clinic_id == clinic_id,
                                Patient.email == invitee.get("email")
                            ).first()
                            
                            if not patient:
                                name_parts = invitee.get("name", "Unknown").split(" ", 1)
                                patient = Patient(
                                    clinic_id=clinic_id,
                                    first_name=name_parts[0],
                                    last_name=name_parts[1] if len(name_parts) > 1 else "",
                                    email=invitee.get("email", ""),
                                    phone="",
                                    preferred_contact_method="email"
                                )
                                db.add(patient)
                                db.flush()
                            
                            patient_id = patient.id
                        
                        # Create new appointment
                        appointment = Appointment(
                            clinic_id=clinic_id,
                            patient_id=patient_id,
                            appointment_datetime=start_time,
                            duration_minutes=duration,
                            appointment_type=event.get("name", "Calendly Appointment"),
                            status=AppointmentStatus.CONFIRMED,
                            external_id=event["uri"],
                            external_system="calendly",
                            calendly_event_uri=event["uri"],
                            notes=f"Calendly event: {event.get('name', 'N/A')}\nSynced from Calendly"
                        )
                        
                        db.add(appointment)
                        synced += 1
                    else:
                        # Update existing appointment
                        existing.appointment_datetime = start_time
                        existing.duration_minutes = duration
                        existing.status = AppointmentStatus.CONFIRMED
                        synced += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing event {event.get('uri', 'unknown')}: {str(e)}")
                    errors += 1
            
            db.commit()
            
            return {
                "synced": synced,
                "errors": errors,
                "total_events": len(events),
                "message": f"Successfully synced {synced} events with {errors} errors"
            }
            
        except Exception as e:
            logger.error(f"Error in sync process: {str(e)}")
            db.rollback()
            return {"synced": 0, "errors": 1, "message": f"Sync failed: {str(e)}"}

# Create singleton instance
calendly_service = CalendlyService()