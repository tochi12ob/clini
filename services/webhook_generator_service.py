import re
from typing import Optional, Dict, Any
from integration.athena_health_client import (
    check_availability,
    book_appointment,
    search_patients,
    get_patient_insurance,
    create_appointment,
    update_patient,
    cancel_appointment,
    create_patient
)
from datetime import datetime

# Helper functions from integration/webhook_tools.py (copy as needed)
def normalize_phone_number(phone: str) -> str:
    if not phone:
        return ""
    if any(word in phone.lower() for word in ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "zero"]):
        number_words = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
        phone_digits = ""
        words = phone.lower().replace("-", " ").split()
        for word in words:
            if word in number_words:
                phone_digits += number_words[word]
        if len(phone_digits) >= 10:
            return phone_digits
    return ''.join(filter(str.isdigit, phone))

def extract_patient_name(name: str):
    if not name:
        return None, None
    parts = name.strip().split()
    if len(parts) < 2:
        return parts[0], None
    return parts[0], ' '.join(parts[1:])

class WebhookGeneratorService:
    """
    Service class implementing all webhook business logic for appointments, patients, insurance, info, and more.
    Logic is adapted from integration/webhook_tools.py endpoint handlers for programmatic use.
    """
    def __init__(self, public_api_domain=None):
        self.public_api_domain = public_api_domain or "https://clini-v7ur.onrender.com"

    # --- Appointment Logic ---
    def check_availability(self, request: Any) -> Dict[str, Any]:
        clinic_id = getattr(request, 'clinic_id', None)
        provider = getattr(request, 'provider', 'athena')
        patient_name = getattr(request, 'patient_name', None)
        patient_phone = getattr(request, 'patient_phone', None)
        patient_dob = getattr(request, 'date_of_birth', None)
        # Pre-check patient existence if name provided
        patient_check_result = None
        if patient_name:
            patient_check_result = self.pre_check_patient(request)
        # Route to appropriate provider (only Athena supported here)
        start_date = getattr(request, 'date', 'tomorrow')
        department_id = getattr(request, 'department_id', '1')
        service_type = getattr(request, 'service_type', None)
        result = check_availability(
            department_id=department_id,
            start_date=start_date,
            end_date=start_date,
            limit=5
        )
        slots = []
        for apt in result.get("appointments", [])[:5]:
            slot_time = apt.get("starttime", "")
            slot_date = apt.get("date", start_date)
            provider_name = apt.get("providername", "Available provider")
            appointment_id = str(apt.get("appointmentid"))
            slots.append({
                "time": slot_time,
                "date": slot_date,
                "provider": provider_name,
                "appointment_id": appointment_id,
                "system": "athena"
            })
        available = bool(slots)
        response = {
            "success": result.get("success", False),
            "available": available,
            "slots": slots,
            "date_checked": start_date,
            "provider": provider
        }
        if patient_check_result and patient_name:
            response["patient_status"] = patient_check_result
        return response

    def book_appointment(self, request: Any) -> Dict[str, Any]:
        first_name, last_name = extract_patient_name(getattr(request, 'patient_name', ''))
        patient_phone = getattr(request, 'patient_phone', None)
        appointment_id = getattr(request, 'appointment_id', None)
        date = getattr(request, 'date', None)
        time = getattr(request, 'time', None)
        service_type = getattr(request, 'service_type', None)
        # Search for patient
        if first_name and last_name:
            normalized_phone = normalize_phone_number(patient_phone)
            search_result = search_patients(first_name=first_name, last_name=last_name, phone=normalized_phone)
            if not (search_result.get("success") and search_result.get("patients")):
                search_result = search_patients(first_name=first_name, last_name=last_name)
            if search_result.get("success") and search_result.get("patients"):
                patient_id = search_result["patients"][0].get("patientid")
            else:
                return {
                    "success": False,
                    "message": "I couldn't find your patient record. Would you like me to register you as a new patient?",
                    "action_needed": "new_patient_registration",
                    "suggestion": "I can help you register as a new patient if you'd like to proceed."
                }
        else:
            return {
                "success": False,
                "message": "I need your full name to book the appointment",
                "missing_info": ["patient_name"]
            }
        # Book the appointment
        if appointment_id:
            appointment_type_id = "2"
            reason = service_type or "Office Visit"
            result = book_appointment(
                appointment_id=appointment_id,
                patient_id=patient_id,
                appointment_type_id=appointment_type_id,
                reason=reason
            )
        elif date and time:
            return {
                "success": False,
                "message": "I need to check availability first to get the appointment slot ID",
                "action_needed": "check_availability",
                "missing_info": ["appointment_id"],
                "suggestion": "Please let me check the availability again to get the correct appointment slot"
            }
        else:
            return {
                "success": False,
                "message": "I need your appointment date and time to book the appointment",
                "missing_info": ["date", "time"]
            }
        if result.get("success"):
            return {
                "success": True,
                "message": f"Perfect! Your {service_type or 'appointment'} appointment has been booked successfully!",
                "confirmation_number": appointment_id,
                "details": f"{service_type or 'Appointment'} on {date} at {time}",
                "appointment_type": "Office Visit",
                "provider": "athena",
                "next_steps": "You should receive a confirmation call or email. Please arrive 15 minutes early."
            }
        else:
            error_message = result.get("error", "The time slot may no longer be available")
            return {
                "success": False,
                "message": f"I'm sorry, I couldn't book that appointment. {error_message}",
                "reason": error_message,
                "provider": "athena",
                "suggestion": "Would you like me to check for other available times?"
            }

    def pre_check_patient(self, request: Any) -> Dict[str, Any]:
        patient_name = getattr(request, 'patient_name', None)
        patient_phone = getattr(request, 'patient_phone', None)
        if not patient_name:
            return {
                "exists": False,
                "message": "I'll need your full name to check our records.",
                "action_needed": "get_patient_name"
            }
        first_name, last_name = extract_patient_name(patient_name)
        if not first_name or not last_name:
            return {
                "exists": False,
                "message": f"I need your full name to check our records. I have '{patient_name}' - could you provide your first and last name?",
                "action_needed": "get_full_name"
            }
        normalized_phone = normalize_phone_number(patient_phone) if patient_phone else None
        search_result = None
        if normalized_phone and len(normalized_phone) >= 10:
            search_result = search_patients(first_name=first_name, last_name=last_name, phone=normalized_phone)
        if not (search_result and search_result.get("success") and search_result.get("patients")):
            search_result = search_patients(first_name=first_name, last_name=last_name)
        if search_result.get("success") and search_result.get("patients"):
            patient = search_result["patients"][0]
            patient_id = patient.get("patientid")
            return {
                "exists": True,
                "patient_id": patient_id,
                "patient_info": patient,
                "message": "I found your record in our system. Let me check what appointments are available for you.",
                "action_needed": "proceed_with_scheduling",
                "search_method": "exact_match"
            }
        else:
            return {
                "exists": False,
                "message": "I couldn't find your record. Would you like to register as a new patient?",
                "action_needed": "register_new_patient"
            }

    def register_patient(self, request: Any) -> Dict[str, Any]:
        patient_name = getattr(request, 'patient_name', None)
        patient_phone = getattr(request, 'patient_phone', None)
        date_of_birth = getattr(request, 'date_of_birth', None)
        email = getattr(request, 'email', None)
        address = getattr(request, 'address', None)
        city = getattr(request, 'city', None)
        state = getattr(request, 'state', None)
        zip_code = getattr(request, 'zip_code', None)
        emergency_contact_name = getattr(request, 'emergency_contact_name', None)
        emergency_contact_phone = getattr(request, 'emergency_contact_phone', None)
        department_id = getattr(request, 'department_id', "1")  # Extract department_id, default to '1'
        # Split name
        first_name, last_name = extract_patient_name(patient_name)
        # Normalize phone
        normalized_phone = normalize_phone_number(patient_phone)
        # Reformat date_of_birth to mm/dd/yyyy if needed
        if date_of_birth and "-" in date_of_birth:
            try:
                parts = date_of_birth.split("-")
                if len(parts) == 3:
                    date_of_birth = f"{parts[1]}/{parts[2]}/{parts[0]}"
            except Exception:
                pass
        # Validate phone number
        if not normalized_phone or len(normalized_phone) < 10:
            return {
                "success": False,
                "message": "That phone number doesn't look right. Could you repeat it, digit by digit?",
                "validation_error": "phone",
                "needs_clarification": True,
                "current_data": {
                    "name": patient_name,
                    "phone_attempt": patient_phone
                }
            }
        # Validate email (simple check)
        if email and ("@" not in email or "." not in email):
            return {
                "success": False,
                "message": "That email address doesn't sound quite right. Could you spell it out for me?",
                "validation_error": "email",
                "needs_clarification": True,
                "current_email": email
            }
        # Check required fields
        if not first_name or not last_name or not normalized_phone or not date_of_birth:
            return {
                "success": False,
                "message": "Missing required patient information.",
                "validation_error": "required_fields"
            }
        # Actually create the patient in the system
        try:
            result = create_patient(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                phone=normalized_phone,
                email=email,
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                emergency_contact_name=emergency_contact_name,
                emergency_contact_phone=emergency_contact_phone,
                department_id=department_id  # Pass department_id to create_patient
            )
            # Handle result type (dict expected)
            if isinstance(result, dict):
                if result.get("success") and result.get("patient_id"):
                    return {
                        "success": True,
                        "patient_id": result["patient_id"],
                        "message": f"Patient {patient_name} registered successfully."
                    }
                else:
                    return {
                        "success": False,
                        "message": result.get("message", "Failed to register patient."),
                        "error": result.get("error", "Unknown error")
                    }
            elif isinstance(result, list):
                return {
                    "success": False,
                    "message": f"Unexpected list response from patient registration. See 'details' for more info.",
                    "error": "Patient registration returned a list instead of a dict.",
                    "details": result
                }
            else:
                # If result is a dict with error details from Athena, surface them
                if isinstance(result, dict) and result.get("error") == "Athena API returned a list instead of a dict." and "details" in result:
                    return {
                        "success": False,
                        "message": result.get("message", "Athena API returned a list instead of a dict."),
                        "error": result.get("error"),
                        "details": result.get("details")
                    }
                return {
                    "success": False,
                    "message": "Unexpected response from patient registration.",
                    "error": str(result)
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"An error occurred while registering the patient: {str(e)}",
                "error": str(e)
            }

    def verify_patient(self, request: Any) -> Dict[str, Any]:
        patient_name = getattr(request, 'patient_name', None)
        patient_phone = getattr(request, 'patient_phone', None)
        date_of_birth = getattr(request, 'date_of_birth', None)
        first_name, last_name = extract_patient_name(patient_name)
        normalized_phone = normalize_phone_number(patient_phone)
        result = search_patients(
            first_name=first_name,
            last_name=last_name,
            phone=normalized_phone,
            date_of_birth=date_of_birth,
            limit=1
        )
        if result.get("success") and result.get("patients"):
            patient = result["patients"][0]
            return {
                "verified": True,
                "message": f"I found your record, {first_name}",
                "patient_id": patient.get("patientid"),
                "has_insurance_on_file": True,  # Simplified
                "last_visit": patient.get("lastappointmentdate"),
                "provider": "athena"
            }
        else:
            return {
                "verified": False,
                "message": "I couldn't find your patient record",
                "suggestion": "You may need to register as a new patient",
                "provider": "athena"
            }

    def verify_insurance(self, request: Any) -> Dict[str, Any]:
        patient_name = getattr(request, 'patient_name', None)
        insurance_provider = getattr(request, 'insurance_provider', None)
        first_name, last_name = extract_patient_name(patient_name)
        search_result = search_patients(first_name=first_name, last_name=last_name)
        if search_result.get("success") and search_result.get("patients"):
            patient_id = search_result["patients"][0].get("patientid")
            insurance_result = get_patient_insurance(patient_id)
            if insurance_result.get("success"):
                insurances = insurance_result.get("insurances", [])
                if insurance_provider:
                    for ins in insurances:
                        insurance_name = ins.get("insurancename", "").lower()
                        if insurance_provider.lower() in insurance_name or insurance_name in insurance_provider.lower():
                            return {
                                "success": True,
                                "message": f"Yes, I see you have {ins.get('insurancename')} on file. You should be all set for your appointment!",
                                "insurance_verified": True,
                                "copay_info": ins.get("copay"),
                                "coverage_active": True,
                                "insurance_details": ins
                            }
                    return {
                        "success": True,
                        "message": f"I see you have {', '.join([ins.get('insurancename', '') for ins in insurances])} on file, but you mentioned {insurance_provider}. Have you changed insurance recently?",
                        "insurance_mismatch": True,
                        "current_insurance": [ins.get('insurancename') for ins in insurances],
                        "mentioned_insurance": insurance_provider,
                        "action_needed": "update_insurance"
                    }
                else:
                    return {
                        "success": True,
                        "message": "I see you have insurance on file.",
                        "insurance_verified": True,
                        "current_insurance": [ins.get('insurancename') for ins in insurances]
                    }
            else:
                return {
                    "success": False,
                    "message": "I'm having trouble accessing your insurance information right now. Let me transfer you to someone who can help verify your coverage.",
                    "error": insurance_result.get("error", "Unknown error")
                }
        else:
            return {
                "success": False,
                "message": "I couldn't find your patient record to verify insurance.",
                "action_needed": "register_new_patient"
            }

    def get_practice_info(self, request: Any) -> Dict[str, Any]:
        info_type = getattr(request, 'info_type', 'general')
        specific_service = getattr(request, 'specific_service', None)
        clinic_info = {
            "name": "Our Medical Practice",
            "phone": "(555) 123-4567",
            "address": "123 Medical Center Dr, Suite 100",
            "hours": {
                "monday": "8:00 AM - 5:00 PM",
                "tuesday": "8:00 AM - 5:00 PM",
                "wednesday": "8:00 AM - 5:00 PM",
                "thursday": "8:00 AM - 5:00 PM",
                "friday": "8:00 AM - 5:00 PM",
                "saturday": "9:00 AM - 2:00 PM",
                "sunday": "Closed"
            },
            "services": ["General Check-ups", "Preventive Care", "Chronic Disease Management", "Vaccinations", "Lab Work"],
            "insurance_accepted": ["Blue Cross Blue Shield", "Aetna", "Cigna", "UnitedHealth", "Medicare", "Medicaid"]
        }
        if info_type == "hours":
            today = datetime.now().strftime("%A").lower()
            return {
                "success": True,
                "message": f"Today we're open {clinic_info['hours'][today]}. Would you like our full weekly schedule?",
                "hours_today": clinic_info['hours'][today],
                "full_schedule": "\n".join([f"{day.title()}: {hours}" for day, hours in clinic_info['hours'].items()]),
                "current_day": today.title()
            }
        elif info_type == "location":
            return {
                "success": True,
                "message": f"We're located at {clinic_info['address']}. Our phone number is {clinic_info['phone']}. Would you like directions?",
                "address": clinic_info['address'],
                "phone": clinic_info['phone'],
                "parking_info": "Free parking is available in our lot",
                "directions_available": True
            }
        elif info_type == "services":
            if specific_service:
                available = specific_service in clinic_info['services']
                return {
                    "success": True,
                    "message": f"Yes, we do offer {specific_service}! Would you like to schedule an appointment for this service?" if available else f"I'm sorry, we don't offer {specific_service}.",
                    "service_available": available,
                    "requested_service": specific_service,
                    "booking_available": available
                }
            return {
                "success": True,
                "message": f"We offer: {', '.join(clinic_info['services'])}",
                "services": clinic_info['services']
            }
        else:
            return {
                "success": True,
                "message": f"Welcome to {clinic_info['name']}! How can I help you today?",
                "info": clinic_info
            }

    def handle_emergency(self, request: Any) -> Dict[str, Any]:
        urgency_level = getattr(request, 'urgency_level', 'unknown')
        symptoms = getattr(request, 'symptoms', '')
        patient_name = getattr(request, 'patient_name', 'caller')
        critical_keywords = [
            "chest pain", "can't breathe", "unconscious", "stroke",
            "severe bleeding", "heart attack", "overdose", "choking",
            "suicide", "not breathing", "cardiac arrest", "anaphylaxis"
        ]
        symptoms_lower = symptoms.lower()
        if any(keyword in symptoms_lower for keyword in critical_keywords):
            return {
                "success": True,
                "message": "This sounds like a medical emergency. I'm going to help you contact 911 immediately. Please stay on the line and don't hang up.",
                "action": "emergency_911",
                "transfer_to": "911",
                "priority": "critical",
                "symptoms_reported": symptoms,
                "emergency_protocol": True
            }
        elif urgency_level in ["high", "urgent", "critical"]:
            return {
                "success": True,
                "message": f"I understand this is urgent, {patient_name}. Let me get you to our clinical staff right away. Please hold while I transfer you.",
                "action": "urgent_transfer",
                "transfer_to": "clinical_staff",
                "priority": "urgent",
                "wait_time_estimate": "2-3 minutes"
            }
        else:
            return {
                "success": True,
                "message": "I understand this is concerning. Let me see if we have any same-day appointments available or if there's another way we can help you today.",
                "action": "schedule_urgent",
                "priority": "same_day",
                "offer_nurse_line": True
            }

    def process_spelled_name(self, request: Any) -> Dict[str, Any]:
        spelled_name = getattr(request, 'spelled_name', '').strip()
        context = getattr(request, 'context', 'search')
        original_name = getattr(request, 'original_name', '')
        if not spelled_name:
            return {
                "success": False,
                "message": "I didn't catch the spelling. Could you spell your name again, letter by letter?",
                "action_needed": "repeat_spelling"
            }
        processed_name = spelled_name.replace("Last name", "").replace("last name", "").replace("First name", "").replace("first name", "")
        if "-" in processed_name:
            words = processed_name.split()
            processed_words = []
            for word in words:
                if "-" in word:
                    clean_word = word.replace("-", "").replace(" ", "")
                    processed_words.append(clean_word.title())
                else:
                    processed_words.append(word.title())
            processed_name = " ".join(processed_words)
        else:
            processed_name = processed_name.title()
        processed_name = " ".join(processed_name.split())
        if context == "search":
            first_name, last_name = extract_patient_name(processed_name)
            if first_name and last_name:
                search_result = search_patients(first_name=first_name, last_name=last_name)
                if search_result.get("success") and search_result.get("patients"):
                    patient = search_result["patients"][0]
                    return {
                        "success": True,
                        "patient_found": True,
                        "patient_id": patient.get("patientid"),
                        "patient_info": patient,
                        "processed_name": processed_name,
                        "message": f"Great! I have {processed_name} - thank you for spelling that out, {first_name}! I found your record! Let me check what appointments are available for you.",
                        "action_needed": "proceed_with_scheduling"
                    }
                else:
                    return {
                        "success": True,
                        "patient_found": False,
                        "processed_name": processed_name,
                        "message": f"I don't see you in our system yet. I'll get you registered first, then we can schedule your appointment.",
                        "action_needed": "proceed_with_registration",
                        "next_step": "get_phone_number"
                    }
            else:
                return {
                    "success": False,
                    "processed_name": processed_name,
                    "message": "I need your full name to search for your record.",
                    "action_needed": "get_full_name"
                }
        else:
            return {
                "success": True,
                "processed_name": processed_name,
                "message": f"Thank you for spelling your name, {processed_name}."
            }

    def clarify_intent(self, request: Any) -> Dict[str, Any]:
        unclear_input = getattr(request, 'unclear_input', '')
        context = getattr(request, 'conversation_context', None)
        previous_attempts = getattr(request, 'previous_attempts', 0)
        patient_name = getattr(request, 'patient_name', None)
        if previous_attempts >= 2:
            return {
                "success": True,
                "message": "I want to make sure I help you properly. Let me connect you with someone from our front desk who can assist you.",
                "action": "escalate_to_human",
                "reason": "multiple_clarification_attempts",
                "transfer_to": "front_desk"
            }
        input_lower = unclear_input.lower()
        detected_keywords = []
        appointment_keywords = ["appointment", "schedule", "book", "cancel", "reschedule", "change", "visit", "see doctor"]
        if any(keyword in input_lower for keyword in appointment_keywords):
            detected_keywords.append("appointment")
        info_keywords = ["hours", "location", "address", "phone", "services", "insurance", "cost", "price"]
        if any(keyword in input_lower for keyword in info_keywords):
            detected_keywords.append("information")
        urgent_keywords = ["urgent", "emergency", "pain", "hurt", "sick", "help", "asap"]
        if any(keyword in input_lower for keyword in urgent_keywords):
            detected_keywords.append("urgent")
        return {
            "success": True,
            "message": f"For medical questions and requests{', ' + patient_name if patient_name else ''}, I can help you with:",
            "clarification_options": [
                "Scheduling an appointment with your provider",
                "Getting transferred to a nurse",
                "General questions about our services"
            ],
            "note": "For specific medical advice, you'll need to speak with a healthcare provider",
            "context": "medical_inquiry"
        }

    def conversation_recovery(self, request: Any) -> Dict[str, Any]:
        error_type = getattr(request, 'error_type', 'unclear_intent')
        last_input = getattr(request, 'last_user_input', '')
        stage = getattr(request, 'conversation_stage', 'unknown')
        retry_count = getattr(request, 'retry_count', 0)
        if retry_count >= 3:
            return {
                "success": True,
                "message": "I want to make sure you get the help you need. Let me connect you with someone from our team who can assist you directly.",
                "action": "escalate_to_human",
                "reason": "multiple_recovery_attempts",
                "priority": "normal"
            }
        return {
            "success": True,
            "message": "Welcome! I'm here to help you with appointments and practice information. What brings you in today?",
            "action": "gentle_restart",
            "stage": stage,
            "open_ended_prompt": True
        }

    def check_office_status(self, request: Any) -> Dict[str, Any]:
        check_time = getattr(request, 'check_time', None)
        clinic_info = {
            "name": "Our Medical Practice",
            "phone": "(555) 123-4567",
            "emergency_phone": "(555) 123-4568",
            "hours": {
                "monday": "8:00 AM - 5:00 PM",
                "tuesday": "8:00 AM - 5:00 PM",
                "wednesday": "8:00 AM - 5:00 PM",
                "thursday": "8:00 AM - 5:00 PM",
                "friday": "8:00 AM - 5:00 PM",
                "saturday": "9:00 AM - 2:00 PM",
                "sunday": "Closed"
            }
        }
        current_time = None
        if check_time:
            try:
                current_time = datetime.strptime(check_time, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    current_time = datetime.strptime(check_time, "%H:%M")
                    today = datetime.now().date()
                    current_time = datetime.combine(today, current_time.time())
                except ValueError:
                    pass
        if not current_time:
            current_time = datetime.now()
        current_day = current_time.strftime("%A").lower()
        hours_today = clinic_info["hours"].get(current_day, "Closed")
        is_open = False
        if hours_today != "Closed":
            open_time, close_time = hours_today.split("-")
            open_time = datetime.strptime(open_time.strip(), "%I:%M %p").time()
            close_time = datetime.strptime(close_time.strip(), "%I:%M %p").time()
            now_time = current_time.time()
            is_open = open_time <= now_time <= close_time
        return {
            "success": True,
            "message": f"Yes, Our Medical Practice is currently open! We close at {hours_today.split('-')[1].strip()}. How can I help you today?" if is_open else f"Sorry, we're currently closed. Our hours today are {hours_today}.",
            "office_open": is_open,
            "current_time": current_time.strftime("%I:%M %p"),
            "hours_today": hours_today,
            "closing_info": f"We close at {hours_today.split('-')[1].strip()}" if is_open else None,
            "can_schedule": is_open,
            "can_take_calls": is_open,
            "clinic_name": clinic_info["name"],
            "phone": clinic_info["phone"]
        }

    def check_holiday_hours(self, request: Any) -> Dict[str, Any]:
        date_to_check = getattr(request, 'date', None)
        clinic_info = {
            "holiday_hours": {},
            "special_hours": {}
        }
        holiday_hours = clinic_info.get("holiday_hours", {})
        special_hours = clinic_info.get("special_hours", {})
        if date_to_check:
            special_schedule = holiday_hours.get(date_to_check) or special_hours.get(date_to_check)
            if special_schedule:
                return {
                    "success": True,
                    "message": f"We have special hours on {date_to_check}: {special_schedule}",
                    "has_special_hours": True,
                    "date": date_to_check,
                    "special_hours": special_schedule,
                    "is_holiday": True
                }
            else:
                return {
                    "success": True,
                    "message": f"We're following our regular schedule on {date_to_check}. Would you like me to tell you our regular hours?",
                    "has_special_hours": False,
                    "date": date_to_check,
                    "follows_regular_schedule": True
                }
        else:
            return {
                "success": False,
                "message": "Please provide a date to check for holiday hours."
            }

    def generate_webhook_config(self, clinic_id, ehr, epic_creds=None, athena_creds=None):
        NGROK_URL = getattr(self, 'public_api_domain', None) or "https://clini-v7ur.onrender.com"
        base_url = f"{NGROK_URL}/api/tools"
        # Only output the four specified webhooks, with exact schemas
        def make_properties(properties_list):
            props = {}
            required = []
            for prop in properties_list:
                prop_copy = dict(prop)
                name = prop_copy.pop("id")
                # Remove fields not valid in OpenAPI/JSON Schema
                prop_copy.pop("value_type", None)
                prop_copy.pop("dynamic_variable", None)
                prop_copy.pop("constant_value", None)
                req = prop_copy.pop("required", False)
                props[name] = prop_copy
                if req:
                    required.append(name)
            return props, required
        dummy_param_schema = {
            "properties": {
                "dummy_param": {
                    "type": "string",
                    "description": "This is a required placeholder due to API schema constraints. It is not used."
                }
            },
            "required": []
        }
        return [
            {
                "name": "search-patients",
                "description": "Getting more information about a patient using their details ",
                "type": "webhook",
                "api_schema": {
                    "url": f"{base_url}/search-patients",
                    "method": "POST",
                    "path_params_schema": dummy_param_schema,
                    "query_params_schema": dummy_param_schema,
                    "request_body_schema": (lambda: (
                        lambda props, req: {
                            "type": "object",
                            "description": "Details to use to make requests to this webhook",
                            "properties": props,
                            "required": req
                        }
                    )(*make_properties([
                        {"id": "practice_id", "type": "string", "description": "The practice ID ", "required": True},
                        {"id": "phone_number", "type": "string", "description": "The phone number of the patient ", "required": True},
                        {"id": "date_of_birth", "type": "string", "description": "The date of birth of the patient ", "required": True},
                        {"id": "first_name", "type": "string", "description": "The first name of the patient ", "required": False},
                        {"id": "last_name", "type": "string", "description": "The last name of the patient ", "required": True}
                    ]))
                    )(),
                    "request_headers": {},
                    "auth_connection": None
                },
                "response_timeout_secs": 20,
                "dynamic_variables": {"dynamic_variable_placeholders": {}}
            },
            {
                "name": "create_appointment_slot",
                "description": "To create an appointment slot for a patient ",
                "type": "webhook",
                "api_schema": {
                    "url": f"{base_url}/create-appointment-slot",
                    "method": "POST",
                    "path_params_schema": dummy_param_schema,
                    "query_params_schema": dummy_param_schema,
                    "request_body_schema": (lambda: (
                        lambda props, req: {
                            "type": "object",
                            "description": "The details to ask from the patient ",
                            "properties": props,
                            "required": req
                        }
                    )(*make_properties([
                        {"id": "practice_id", "type": "string", "description": "The practice ID of the clinic", "required": True},
                        {"id": "start_time", "type": "string", "description": "The start time of the appointment ", "required": True},
                        {"id": "provider_id", "type": "string", "description": "The ID of the provider ", "required": True},
                        {"id": "appointment_type_id", "type": "string", "description": "The appopintment type id ", "required": True},
                        {"id": "appointment_date", "type": "string", "description": "The appointment ", "required": True},
                        {"id": "department_id", "type": "string", "description": "the department id ", "required": False}
                    ]))
                    )(),
                    "request_headers": {},
                    "auth_connection": None
                },
                "response_timeout_secs": 20,
                "dynamic_variables": {"dynamic_variable_placeholders": {}}
            },
            {
                "name": "get_patient_details",
                "description": "Get detailed patient information by patient_id.",
                "type": "webhook",
                "api_schema": {
                    "url": f"{base_url}/get-patient-details",
                    "method": "POST",
                    "path_params_schema": dummy_param_schema,
                    "query_params_schema": dummy_param_schema,
                    "request_body_schema": (lambda: (
                        lambda props, req: {
                            "type": "object",
                            "description": "Collect the id of the patient ",
                            "properties": props,
                            "required": req
                        }
                    )(*make_properties([
                        {"id": "patient_id", "type": "string", "description": "The patient ID ", "required": False}
                    ]))
                    )(),
                    "request_headers": {},
                    "auth_connection": None
                },
                "response_timeout_secs": 20,
                "dynamic_variables": {"dynamic_variable_placeholders": {}}
            },
            {
                "name": "register_patient",
                "description": "Register a new patient ",
                "type": "webhook",
                "api_schema": {
                    "url": f"{base_url}/register-patient",
                    "method": "POST",
                    "path_params_schema": dummy_param_schema,
                    "query_params_schema": dummy_param_schema,
                    "request_body_schema": (lambda: (
                        lambda props, req: {
                            "type": "object",
                            "description": "Collect patient name and phone number ",
                            "properties": props,
                            "required": req
                        }
                    )(*make_properties([
                        {"id": "patient_phone", "type": "string", "description": "the phone number of the patient ", "required": True},
                        {"id": "patient_name", "type": "string", "description": "the patients full name ", "required": True},
                        {"id": "email", "type": "string", "description": "The email of the patient ", "required": True},
                        {"id": "date_of_birth", "type": "string", "description": "the date of birth of the patient ", "required": True},
                        {"id": "department_id", "type": "string", "description": "the department the patient is trying to register under ", "required": True}
                    ]))
                    )(),
                    "request_headers": {},
                    "auth_connection": None
                },
                "response_timeout_secs": 20,
                "dynamic_variables": {"dynamic_variable_placeholders": {}}
            }
        ] 