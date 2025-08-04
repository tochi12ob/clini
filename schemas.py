from dataclasses import field
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum

# Enums matching the database models
class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"

class CallStatus(str, Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"

class CallType(str, Enum):
    INBOUND = "inbound"
    OUTBOUND_REMINDER = "outbound_reminder"
    OUTBOUND_FOLLOWUP = "outbound_followup"
    OUTBOUND_NOSHOW = "outbound_noshow"
    OUTBOUND_CONFIRMATION = "outbound_confirmation"

class StaffRole(str, Enum):
    ADMIN = "admin"
    RECEPTIONIST = "receptionist"
    DOCTOR = "doctor"
    NURSE = "nurse"
    MANAGER = "manager"

class InsuranceStatus(str, Enum):
    VERIFIED = "verified"
    PENDING = "pending"
    REJECTED = "rejected"
    NOT_CHECKED = "not_checked"

# AI Service Enums
class ConversationIntent(str, Enum):
    APPOINTMENT_BOOKING = "APPOINTMENT_BOOKING"
    APPOINTMENT_RESCHEDULE = "APPOINTMENT_RESCHEDULE"
    APPOINTMENT_CANCEL = "APPOINTMENT_CANCEL"
    APPOINTMENT_INQUIRY = "APPOINTMENT_INQUIRY"
    CLINIC_INFO = "CLINIC_INFO"
    INSURANCE_INQUIRY = "INSURANCE_INQUIRY"
    EMERGENCY = "EMERGENCY"
    GENERAL_QUESTION = "GENERAL_QUESTION"
    GREETING = "GREETING"
    OTHER = "OTHER"
    ERROR = "ERROR"

# Base schema classes
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True
        use_enum_values = True

# Clinic Schemas
class ClinicBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=10)
    business_hours: Optional[Dict[str, Any]] = None
    timezone: str = Field(default="UTC", max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    
    @validator('phone')
    def validate_phone(cls, v):
        # Remove common phone formatting
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) < 10:
            raise ValueError('Phone number must have at least 10 digits')
        return v

class ClinicCreate(ClinicBase):
    ai_voice_id: Optional[str] = Field(None, max_length=100)
    ai_personality: Optional[str] = None
    greeting_message: Optional[str] = None
    area_code: Optional[str] = Field(None, max_length=3, description="Preferred area code for phone number (e.g., '212' for NYC)")

class ClinicUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=10)
    business_hours: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    ai_voice_id: Optional[str] = Field(None, max_length=100)
    ai_personality: Optional[str] = None
    greeting_message: Optional[str] = None
    area_code: Optional[str] = Field(None, max_length=3, description="Preferred area code for phone number")
    is_active: Optional[bool] = None

class ClinicResponse(ClinicBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

# Patient Schemas
class PatientBase(BaseSchema):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=10)
    preferred_contact_method: str = Field(default="phone", max_length=20)
    preferred_language: str = Field(default="en", max_length=10)

class PatientCreate(PatientBase):
    clinic_id: int
    insurance_provider: Optional[str] = Field(None, max_length=255)
    insurance_id: Optional[str] = Field(None, max_length=100)
    insurance_group: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

class PatientUpdate(BaseSchema):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    email: Optional[EmailStr] = None
    date_of_birth: Optional[datetime] = None
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    zip_code: Optional[str] = Field(None, max_length=10)
    insurance_provider: Optional[str] = Field(None, max_length=255)
    insurance_id: Optional[str] = Field(None, max_length=100)
    insurance_group: Optional[str] = Field(None, max_length=100)
    insurance_status: Optional[InsuranceStatus] = None
    preferred_contact_method: Optional[str] = Field(None, max_length=20)
    preferred_language: Optional[str] = Field(None, max_length=10)
    notes: Optional[str] = None
    is_active: Optional[bool] = None

class PatientResponse(PatientBase):
    id: int
    clinic_id: int
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    insurance_group: Optional[str] = None
    insurance_status: InsuranceStatus
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

# Staff Schemas
class StaffBase(BaseSchema):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=20)
    role: StaffRole
    schedule: Optional[Dict[str, Any]] = None

class StaffCreate(StaffBase):
    clinic_id: int
    permissions: Optional[Dict[str, Any]] = None

class StaffUpdate(BaseSchema):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    role: Optional[StaffRole] = None
    permissions: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class StaffResponse(StaffBase):
    id: int
    clinic_id: int
    permissions: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

# Appointment Schemas
class AppointmentBase(BaseSchema):
    appointment_datetime: datetime
    duration_minutes: int = Field(default=30, ge=5, le=480)  # 5 min to 8 hours
    appointment_type: Optional[str] = Field(None, max_length=100)
    reason: Optional[str] = None
    special_requirements: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    clinic_id: int
    patient_id: int
    staff_id: Optional[int] = None
    notes: Optional[str] = None
    followup_required: bool = False

class AppointmentUpdate(BaseSchema):
    appointment_datetime: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=5, le=480)
    appointment_type: Optional[str] = Field(None, max_length=100)
    reason: Optional[str] = None
    status: Optional[AppointmentStatus] = None
    staff_id: Optional[int] = None
    notes: Optional[str] = None
    special_requirements: Optional[str] = None
    followup_required: Optional[bool] = None

class AppointmentResponse(AppointmentBase):
    id: int
    clinic_id: int
    patient_id: int
    staff_id: Optional[int] = None
    status: AppointmentStatus
    confirmed_at: Optional[datetime] = None
    confirmation_method: Optional[str] = None
    original_appointment_id: Optional[int] = None
    reschedule_count: int
    notes: Optional[str] = None
    reminder_sent: bool
    reminder_sent_at: Optional[datetime] = None
    followup_required: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

# Call Schemas
class CallBase(BaseSchema):
    from_number: str = Field(..., max_length=20)
    to_number: str = Field(..., max_length=20)
    call_type: CallType

class CallCreate(CallBase):
    clinic_id: int
    patient_id: Optional[int] = None
    appointment_id: Optional[int] = None
    twilio_call_sid: Optional[str] = Field(None, max_length=100)

class CallUpdate(BaseSchema):
    status: Optional[CallStatus] = None
    duration_seconds: Optional[int] = Field(None, ge=0)
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    intent_detected: Optional[str] = Field(None, max_length=100)
    confidence_score: Optional[Decimal] = Field(None, ge=0, le=1)
    outcome: Optional[str] = Field(None, max_length=100)
    handoff_to_human: Optional[bool] = None
    handoff_reason: Optional[str] = Field(None, max_length=255)
    patient_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    call_quality_score: Optional[Decimal] = Field(None, ge=0, le=1)
    recording_url: Optional[str] = Field(None, max_length=500)
    recording_duration: Optional[int] = Field(None, ge=0)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

class CallResponse(CallBase):
    id: int
    clinic_id: int
    patient_id: Optional[int] = None
    appointment_id: Optional[int] = None
    twilio_call_sid: Optional[str] = None
    status: CallStatus
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    intent_detected: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    outcome: Optional[str] = None
    handoff_to_human: bool
    handoff_reason: Optional[str] = None
    patient_satisfaction: Optional[int] = None
    call_quality_score: Optional[Decimal] = None
    recording_url: Optional[str] = None
    recording_duration: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

# Knowledge Base Schemas
class KnowledgeBaseBase(BaseSchema):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    category: Optional[str] = Field(None, max_length=100)
    keywords: Optional[str] = None
    priority: int = Field(default=1, ge=1, le=10)

class KnowledgeBaseCreate(KnowledgeBaseBase):
    clinic_id: int

class KnowledgeBaseUpdate(BaseSchema):
    question: Optional[str] = Field(None, min_length=1)
    answer: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, max_length=100)
    keywords: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None

class KnowledgeBaseResponse(KnowledgeBaseBase):
    id: int
    clinic_id: int
    usage_count: int
    last_used: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

# AI Service Schemas - Missing from original schemas.py
class ConversationContext(BaseSchema):
    call_id: str
    clinic_id: int
    patient_id: Optional[int] = None
    patient_phone: Optional[str] = None
    conversation_start: datetime
    messages: List[Dict[str, Any]] = []
    summary: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

class IntentResult(BaseSchema):
    intent: str
    confidence: float
    entities: Dict[str, Any] = {}

class AIResponse(BaseSchema):
    message: str
    intent: str
    next_action: str
    requires_human: bool = False
    priority: str = "normal"
    confidence: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ConversationRequest(BaseSchema):
    message: str
    clinic_id: int
    call_id: Optional[str] = None
    patient_phone: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class ConversationResponse(BaseSchema):
    message: str
    intent: str
    next_action: str
    requires_human: bool = False
    priority: Optional[str] = "normal"
    confidence: Optional[float] = None
    timestamp: Optional[datetime] = None

class IntentClassificationRequest(BaseSchema):
    message: str
    clinic_id: int
    call_id: Optional[str] = None
    patient_phone: Optional[str] = None

class IntentClassificationResponse(BaseSchema):
    intent: str
    confidence: float
    entities: Dict[str, Any]
    message: str

class ConversationSummaryRequest(BaseSchema):
    call_id: str

# Insurance Plan Schemas
class InsurancePlanBase(BaseSchema):
    provider_name: str = Field(..., min_length=1, max_length=255)
    plan_name: Optional[str] = Field(None, max_length=255)
    plan_type: Optional[str] = Field(None, max_length=100)
    copay_amount: Optional[Decimal] = Field(None, ge=0)
    deductible_amount: Optional[Decimal] = Field(None, ge=0)
    coverage_notes: Optional[str] = None
    requires_referral: bool = False
    requires_preauth: bool = False
    verification_notes: Optional[str] = None

class InsurancePlanCreate(InsurancePlanBase):
    clinic_id: int

class InsurancePlanUpdate(BaseSchema):
    provider_name: Optional[str] = Field(None, min_length=1, max_length=255)
    plan_name: Optional[str] = Field(None, max_length=255)
    plan_type: Optional[str] = Field(None, max_length=100)
    copay_amount: Optional[Decimal] = Field(None, ge=0)
    deductible_amount: Optional[Decimal] = Field(None, ge=0)
    coverage_notes: Optional[str] = None
    requires_referral: Optional[bool] = None
    requires_preauth: Optional[bool] = None
    verification_notes: Optional[str] = None
    is_accepted: Optional[bool] = None

class InsurancePlanResponse(InsurancePlanBase):
    id: int
    clinic_id: int
    is_accepted: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

# Call Analytics Schemas
class CallAnalyticsBase(BaseSchema):
    sentiment_score: Optional[Decimal] = Field(None, ge=-1, le=1)
    emotion_detected: Optional[str] = Field(None, max_length=50)
    key_phrases: Optional[List[str]] = None
    topics_discussed: Optional[List[str]] = None
    response_time_avg: Optional[Decimal] = Field(None, ge=0)
    understanding_score: Optional[Decimal] = Field(None, ge=0, le=1)
    resolution_score: Optional[Decimal] = Field(None, ge=0, le=1)
    conversion_achieved: bool = False
    conversion_type: Optional[str] = Field(None, max_length=100)

class CallAnalyticsCreate(CallAnalyticsBase):
    clinic_id: int
    call_id: int

class CallAnalyticsResponse(CallAnalyticsBase):
    id: int
    clinic_id: int
    call_id: int
    analyzed_at: datetime

# System Log Schemas
class SystemLogBase(BaseSchema):
    level: str = Field(..., max_length=20)
    message: str = Field(..., min_length=1)
    component: Optional[str] = Field(None, max_length=100)
    context_data: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = Field(None, max_length=100)
    session_id: Optional[str] = Field(None, max_length=100)

class SystemLogCreate(SystemLogBase):
    clinic_id: Optional[int] = None

class SystemLogResponse(SystemLogBase):
    id: int
    clinic_id: Optional[int] = None
    created_at: datetime

# Calendar Service Schemas
class TimeSlot(BaseSchema):
    start_time: datetime
    end_time: datetime
    is_available: bool = True

class AppointmentReschedule(BaseSchema):
    new_datetime: datetime
    reason: Optional[str] = None

# Aggregated Response Schemas for Complex Queries
class PatientWithAppointments(PatientResponse):
    appointments: List[AppointmentResponse] = []

class ClinicWithStats(ClinicResponse):
    total_patients: int = 0
    total_appointments: int = 0
    total_calls: int = 0
    active_staff: int = 0

class AppointmentWithDetails(AppointmentResponse):
    patient: Optional[PatientResponse] = None
    staff_member: Optional[StaffResponse] = None
    clinic: Optional[ClinicResponse] = None

class CallWithDetails(CallResponse):
    patient: Optional[PatientResponse] = None
    appointment: Optional[AppointmentResponse] = None
    clinic: Optional[ClinicResponse] = None
    analytics: Optional[CallAnalyticsResponse] = None

# Webhook and External API Schemas
class TwilioWebhookData(BaseSchema):
    CallSid: str
    From: str
    To: str
    CallStatus: str
    Direction: str
    Duration: Optional[str] = None
    RecordingUrl: Optional[str] = None
    RecordingDuration: Optional[str] = None

class VoiceProcessingRequest(BaseSchema):
    audio_url: Optional[str] = None
    audio_data: Optional[str] = None  # Base64 encoded
    text: Optional[str] = None
    voice_id: Optional[str] = None
    clinic_id: int

class VoiceProcessingResponse(BaseSchema):
    success: bool
    text: Optional[str] = None  # For STT
    audio_url: Optional[str] = None  # For TTS
    error_message: Optional[str] = None
    processing_time: Optional[float] = None

class AIConversationRequest(BaseSchema):
    message: str
    clinic_id: int
    patient_id: Optional[int] = None
    call_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

class AIConversationResponse(BaseSchema):
    response: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    actions: Optional[List[Dict[str, Any]]] = None
    requires_handoff: bool = False
    handoff_reason: Optional[str] = None

# Appointment Scheduling Schemas
class AvailabilityRequest(BaseSchema):
    clinic_id: int
    staff_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    duration_minutes: int = 30

class AvailabilitySlot(BaseSchema):
    start_time: datetime
    end_time: datetime
    staff_id: Optional[int] = None
    staff_name: Optional[str] = None

class AvailabilityResponse(BaseSchema):
    available_slots: List[AvailabilitySlot]
    total_slots: int

class AppointmentBookingRequest(BaseSchema):
    clinic_id: int
    patient_id: int
    staff_id: Optional[int] = None
    appointment_datetime: datetime
    duration_minutes: int = 30
    appointment_type: Optional[str] = None
    reason: Optional[str] = None
    special_requirements: Optional[str] = None
    patient_phone: Optional[str] = None  # For creating new patients on the fly

# Analytics and Reporting Schemas
class CallMetrics(BaseSchema):
    total_calls: int
    successful_calls: int
    failed_calls: int
    average_duration: Optional[float] = None
    average_satisfaction: Optional[float] = None
    handoff_rate: Optional[float] = None

class AppointmentMetrics(BaseSchema):
    total_appointments: int
    confirmed_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    no_show_rate: Optional[float] = None

class ClinicDashboard(BaseSchema):
    clinic: ClinicResponse
    call_metrics: CallMetrics
    appointment_metrics: AppointmentMetrics
    recent_calls: List[CallResponse] = []
    upcoming_appointments: List[AppointmentResponse] = []
    date_range: Dict[str, datetime]

# Additional Call Analytics Schema for enhanced reporting
class CallAnalytics(BaseSchema):
    call_id: str
    clinic_id: int
    duration_seconds: int
    intent_distribution: Dict[str, int]
    sentiment_score: Optional[float] = None
    satisfaction_rating: Optional[int] = None
    resolution_status: str = "pending"
    transcript_summary: Optional[str] = None

# Pagination Schemas
class PaginationParams(BaseSchema):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=50, ge=1, le=100)

class PaginatedResponse(BaseSchema):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int

# Error Response Schemas
class ErrorDetail(BaseSchema):
    field: Optional[str] = None
    message: str
    code: Optional[str] = None

class ErrorResponse(BaseSchema):
    error: str
    details: Optional[List[ErrorDetail]] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# Health Check Schema
class HealthCheckResponse(BaseSchema):
    status: str
    timestamp: datetime
    version: str
    database_connected: bool
    external_services: Dict[str, bool] = {}
    uptime_seconds: Optional[int] = None

# Conversation Schemas for ElevenLabs Integration
class ConversationTranscriptEntry(BaseSchema):
    role: str  # "user" or "agent"
    time_in_call_secs: float
    message: str

class ConversationMetadata(BaseSchema):
    start_time_unix_secs: int
    call_duration_secs: Optional[int] = None

class ConversationAnalysis(BaseSchema):
    sentiment: Optional[str] = None
    topics: Optional[List[str]] = None
    summary: Optional[str] = None
    action_items: Optional[List[str]] = None
    follow_up_required: Optional[bool] = None

class ConversationDetail(BaseSchema):
    agent_id: str
    conversation_id: str
    status: str  # initiated, in-progress, processing, done, failed
    transcript: List[ConversationTranscriptEntry]
    metadata: ConversationMetadata
    has_audio: bool
    has_user_audio: bool
    has_response_audio: bool
    user_id: Optional[str] = None
    analysis: Optional[ConversationAnalysis] = None
    conversation_initiation_client_data: Optional[Dict[str, Any]] = None

class ConversationListResponse(BaseSchema):
    conversations: List[Any]
    total: int
    page: int
    size: int
    agent_id: str
    message: Optional[str] = None