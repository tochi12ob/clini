from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Numeric, JSON, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()

# Enums for status fields
class AppointmentStatus(enum.Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"

class CallStatus(enum.Enum):
    INITIATED = "initiated"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BUSY = "busy"
    NO_ANSWER = "no_answer"

class CallType(enum.Enum):
    INBOUND = "inbound"
    OUTBOUND_REMINDER = "outbound_reminder"
    OUTBOUND_FOLLOWUP = "outbound_followup"
    OUTBOUND_NOSHOW = "outbound_noshow"
    OUTBOUND_CONFIRMATION = "outbound_confirmation"

class StaffRole(enum.Enum):
    ADMIN = "admin"
    RECEPTIONIST = "receptionist"
    DOCTOR = "doctor"
    NURSE = "nurse"
    MANAGER = "manager"

class InsuranceStatus(enum.Enum):
    VERIFIED = "verified"
    PENDING = "pending"
    REJECTED = "rejected"
    NOT_CHECKED = "not_checked"


class Clinic(Base):
    __tablename__ = "clinics"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False, unique=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(10), nullable=True)
    password_hash = Column(String(255), nullable=False)
    # Business settings
    business_hours = Column(JSON, nullable=True)  # Store hours as JSON
    timezone = Column(String(50), default="UTC")
    website = Column(String(255), nullable=True)
    
    # AI Assistant settings
    ai_voice_id = Column(String(100), nullable=True)  # ElevenLabs voice ID
    ai_personality = Column(Text, nullable=True)  # Custom personality prompt
    greeting_message = Column(Text, nullable=True)
    
    # Integration settings
    calendar_integration = Column(JSON, nullable=True)  # Google Calendar, etc.
    twilio_phone_sid = Column(String(100), nullable=True)
    twilio_phone_number = Column(String(20), nullable=True)  # The actual phone number
    elevenlabs_agent_id = Column(String(100), nullable=True)  # ElevenLabs agent ID
    elevenlabs_agent_name = Column(String(255), nullable=True)  # ElevenLabs agent name
    knowledge_base_id = Column(String(100), nullable=True)  # ElevenLabs knowledge base ID
    setup_results = Column(JSON, nullable=True)  # Store setup results for debugging
    
    # Calendly integration fields
    calendly_access_token = Column(String(500), nullable=True)
    calendly_refresh_token = Column(String(500), nullable=True)
    calendly_user_uri = Column(String(255), nullable=True)
    calendly_organization_uri = Column(String(255), nullable=True)
    calendly_webhook_signing_key = Column(String(255), nullable=True)
    calendly_connected_at = Column(DateTime(timezone=True), nullable=True)
    calendly_sync_enabled = Column(Boolean, default=False)
    
    # Status and timestamps
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Email verification fields
    email_verification_code = Column(String(10), nullable=True)
    email_verified = Column(Boolean, default=False)
    
    # Relationships
    patients = relationship("Patient", back_populates="clinic")
    appointments = relationship("Appointment", back_populates="clinic")
    staff = relationship("Staff", back_populates="clinic")
    calls = relationship("Call", back_populates="clinic")
    knowledge_base = relationship("KnowledgeBase", back_populates="clinic")
    insurance_plans = relationship("InsurancePlan", back_populates="clinic")


class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    
    # Personal information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(255), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    
    # Address
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(10), nullable=True)
    
    # Insurance information
    insurance_provider = Column(String(255), nullable=True)
    insurance_id = Column(String(100), nullable=True)
    insurance_group = Column(String(100), nullable=True)
    insurance_status = Column(Enum(InsuranceStatus), default=InsuranceStatus.NOT_CHECKED)
    
    # Patient preferences
    preferred_contact_method = Column(String(20), default="phone")  # phone, email, sms
    preferred_language = Column(String(10), default="en")
    notes = Column(Text, nullable=True)
    
    # Status and timestamps
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    clinic = relationship("Clinic", back_populates="patients")
    appointments = relationship("Appointment", back_populates="patient")
    calls = relationship("Call", back_populates="patient")


class Staff(Base):
    __tablename__ = "staff"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    
    # Personal information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    # Role and permissions
    role = Column(Enum(StaffRole), nullable=False)
    permissions = Column(JSON, nullable=True)  # Custom permissions
    
    # Schedule information
    schedule = Column(JSON, nullable=True)  # Working hours/days
    
    # Status and timestamps
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    clinic = relationship("Clinic", back_populates="staff")
    appointments = relationship("Appointment", back_populates="staff_member")


class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    
    # Appointment details
    appointment_datetime = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    appointment_type = Column(String(100), nullable=True)  # consultation, checkup, etc.
    reason = Column(Text, nullable=True)
    
    # Status and confirmation
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.SCHEDULED)
    confirmed_at = Column(DateTime, nullable=True)
    confirmation_method = Column(String(20), nullable=True)  # ai_call, sms, email
    
    # Rescheduling tracking
    original_appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    reschedule_count = Column(Integer, default=0)
    
    # Notes and special requirements
    notes = Column(Text, nullable=True)
    special_requirements = Column(Text, nullable=True)
    
    # External system integration
    external_id = Column(String(255), nullable=True)
    external_system = Column(String(50), nullable=True)  # 'calendly', 'google', 'epic', etc.
    calendly_event_uri = Column(String(255), nullable=True)
    calendly_invitee_uri = Column(String(255), nullable=True)
    
    # Reminder settings
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime, nullable=True)
    followup_required = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    clinic = relationship("Clinic", back_populates="appointments")
    patient = relationship("Patient", back_populates="appointments")
    staff_member = relationship("Staff", back_populates="appointments")
    calls = relationship("Call", back_populates="appointment")
    original_appointment = relationship("Appointment", remote_side=[id])


class Call(Base):
    __tablename__ = "calls"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    
    # Twilio call information
    twilio_call_sid = Column(String(100), nullable=True, unique=True)
    from_number = Column(String(20), nullable=False)
    to_number = Column(String(20), nullable=False)
    
    # ElevenLabs conversation ID
    conversation_id = Column(String(100), nullable=True, unique=True, index=True)
    
    # Call metadata
    call_type = Column(Enum(CallType), nullable=False)
    status = Column(Enum(CallStatus), default=CallStatus.INITIATED)
    duration_seconds = Column(Integer, nullable=True)
    
    # AI conversation data
    transcript = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    intent_detected = Column(String(100), nullable=True)  # appointment, question, complaint
    confidence_score = Column(Numeric(3, 2), nullable=True)  # 0.00 to 1.00
    
    # Call outcome
    outcome = Column(String(100), nullable=True)  # scheduled, rescheduled, cancelled, info_provided
    handoff_to_human = Column(Boolean, default=False)
    handoff_reason = Column(String(255), nullable=True)
    
    # Quality metrics
    patient_satisfaction = Column(Integer, nullable=True)  # 1-5 rating
    call_quality_score = Column(Numeric(3, 2), nullable=True)
    
    # Audio and recording
    recording_url = Column(String(500), nullable=True)
    recording_duration = Column(Integer, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    clinic = relationship("Clinic", back_populates="calls")
    patient = relationship("Patient", back_populates="calls")
    appointment = relationship("Appointment", back_populates="calls")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    
    # Knowledge content
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)  # hours, insurance, services, etc.
    keywords = Column(Text, nullable=True)  # Comma-separated keywords
    
    # AI-related fields
    embedding_vector = Column(Text, nullable=True)  # Stored as JSON string
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    
    # Status and metadata
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)  # Higher number = higher priority
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    clinic = relationship("Clinic", back_populates="knowledge_base")


class InsurancePlan(Base):
    __tablename__ = "insurance_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    
    # Insurance details
    provider_name = Column(String(255), nullable=False)
    plan_name = Column(String(255), nullable=True)
    plan_type = Column(String(100), nullable=True)  # HMO, PPO, etc.
    
    # Coverage details
    copay_amount = Column(Numeric(10, 2), nullable=True)
    deductible_amount = Column(Numeric(10, 2), nullable=True)
    coverage_notes = Column(Text, nullable=True)
    
    # Verification requirements
    requires_referral = Column(Boolean, default=False)
    requires_preauth = Column(Boolean, default=False)
    verification_notes = Column(Text, nullable=True)
    
    # Status
    is_accepted = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    clinic = relationship("Clinic", back_populates="insurance_plans")


class CallAnalytics(Base):
    __tablename__ = "call_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=False)
    
    # Conversation analysis
    sentiment_score = Column(Numeric(3, 2), nullable=True)  # -1.00 to 1.00
    emotion_detected = Column(String(50), nullable=True)  # happy, frustrated, neutral
    key_phrases = Column(JSON, nullable=True)
    topics_discussed = Column(JSON, nullable=True)
    
    # Performance metrics
    response_time_avg = Column(Numeric(5, 2), nullable=True)  # Average AI response time
    understanding_score = Column(Numeric(3, 2), nullable=True)  # How well AI understood
    resolution_score = Column(Numeric(3, 2), nullable=True)  # How well issue was resolved
    
    # Business metrics
    conversion_achieved = Column(Boolean, default=False)  # Did we achieve the goal?
    conversion_type = Column(String(100), nullable=True)  # appointment_booked, question_answered
    
    # Timestamps
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships (no back_populates needed for analytics)
    clinic = relationship("Clinic")
    call = relationship("Call")


class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=True)
    
    # Log details
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    component = Column(String(100), nullable=True)  # voice_service, call_service, etc.
    
    # Context data
    context_data = Column(JSON, nullable=True)
    user_id = Column(String(100), nullable=True)
    session_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    clinic = relationship("Clinic")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())