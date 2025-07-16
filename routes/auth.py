"""
Authentication Routes for Clinic AI Assistant
Handles login, registration, token validation, and access control
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel, EmailStr
from datetime import timedelta

from database import get_db
from services.auth_service import auth_service
from models import Clinic, Staff
from enum import Enum

# Import StaffRole enum - adjust import based on your models file structure
from models import StaffRole

router = APIRouter()
security = HTTPBearer()

# Pydantic models for request/response
class ClinicLoginRequest(BaseModel):
    email: EmailStr
    password: str

class StaffLoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterClinicRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str
    website: Optional[str] = None
    address: Optional[str] = None
    area_code: Optional[str] = None

class RegisterStaffRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str  # Will be converted to StaffRole enum
    password: str
    permissions: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_type: str
    expires_in: int

class ClinicResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    website: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    
    class Config:
        orm_mode = True

class VerifyClinicEmailRequest(BaseModel):
    clinic_id: int
    otp: str

# Dependency functions
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user from JWT token
    Used by other routes that require authentication
    """
    token = credentials.credentials
    return auth_service.verify_token(token)

def require_clinic_access(current_user: Dict[str, Any], clinic_id: int, db: Session):
    """
    Dependency to ensure current user has access to specified clinic
    Raises HTTPException if access is denied
    """
    if not auth_service.has_clinic_access(current_user, clinic_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this clinic"
        )

def get_current_clinic(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Clinic:
    """Get current authenticated clinic"""
    if current_user.get("user_type") != "clinic":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clinic access required"
        )
    
    clinic = auth_service.get_clinic_by_id(db, current_user.get("user_id"))
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    return clinic

# Routes
@router.post("/login/clinic", response_model=TokenResponse)
async def login_clinic(
    login_data: ClinicLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate clinic and return access token
    - **email**: Clinic email address
    - **password**: Clinic password
    """
    clinic = auth_service.authenticate_clinic(db, login_data.email, login_data.password)
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_clinic_token(clinic)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_type="clinic",
        expires_in=auth_service.access_token_expire_minutes * 60
    )

@router.post("/login/staff", response_model=TokenResponse)
async def login_staff(
    login_data: StaffLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate staff member and return access token
    - **email**: Staff email address
    - **password**: Staff password
    """
    staff = auth_service.authenticate_staff(db, login_data.email, login_data.password)
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_staff_token(staff)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer", 
        user_type="staff",
        expires_in=auth_service.access_token_expire_minutes * 60
    )

@router.post("/register/clinic", response_model=ClinicResponse)
async def register_clinic(
    registration_data: RegisterClinicRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new clinic
    - **name**: Clinic name
    - **email**: Clinic email address (must be unique)
    - **phone**: Clinic phone number (must be unique)
    - **password**: Clinic password
    - **website**: Optional clinic website URL
    - **address**: Optional clinic address
    """
    clinic_data = registration_data.dict(exclude={"password"})
    
    try:
        clinic = auth_service.register_clinic(db, clinic_data, registration_data.password)
        return ClinicResponse(
            id=clinic.id,
            name=clinic.name,
            email=clinic.email,
            phone=clinic.phone,
            website=clinic.website,
            address=clinic.address,
            is_active=clinic.is_active
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.get("/me")
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user information
    """
    user_type = current_user.get("user_type")
    user_id = current_user.get("user_id")
    
    if user_type == "clinic":
        clinic = auth_service.get_clinic_by_id(db, user_id)
        if not clinic:
            raise HTTPException(status_code=404, detail="Clinic not found")
        
        return {
            "user_type": "clinic",
            "id": clinic.id,
            "name": clinic.name,
            "email": clinic.email,
            "phone": clinic.phone,
            "website": clinic.website,
            "address": clinic.address,
            "is_active": clinic.is_active
        }
    
    elif user_type == "staff":
        staff = auth_service.get_staff_by_id(db, user_id)
        if not staff:
            raise HTTPException(status_code=404, detail="Staff not found")
        
        return {
            "user_type": "staff",
            "id": staff.id,
            "email": staff.email,
            "first_name": staff.first_name,
            "last_name": staff.last_name,
            "clinic_id": staff.clinic_id,
            "role": staff.role.value if staff.role else None,
            "is_active": staff.is_active
        }
    
    raise HTTPException(status_code=400, detail="Invalid user type")

@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change current user's password
    - **old_password**: Current password
    - **new_password**: New password
    """
    success = auth_service.change_password(
        db,
        current_user.get("user_id"),
        current_user.get("user_type"),
        password_data.old_password,
        password_data.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change failed. Check your current password."
        )
    
    return {"message": "Password changed successfully"}

@router.post("/register/staff/{clinic_id}")
async def register_staff(
    clinic_id: int,
    registration_data: RegisterStaffRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a new staff member for a clinic
    Only clinic owners or authorized staff can register new staff
    - **clinic_id**: ID of the clinic to add staff to
    - **first_name**: Staff first name
    - **last_name**: Staff last name
    - **email**: Staff email (must be unique)
    - **role**: Staff role (admin, doctor, nurse, receptionist, etc.)
    - **password**: Staff password
    """
    # Check if user has access to this clinic
    require_clinic_access(current_user, clinic_id, db)
    
    # Additional check: only clinic owners or admin staff can register new staff
    if current_user.get("user_type") == "staff":
        current_staff = auth_service.get_staff_by_id(db, current_user.get("user_id"))
        if not current_staff or current_staff.role.value not in ["admin", "manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to register staff"
            )
    
    staff_data = registration_data.dict(exclude={"password"})
    
    try:
        # Convert role string to enum - you'll need to adjust this based on your StaffRole enum
        staff_data["role"] = StaffRole(registration_data.role)
        
        staff = auth_service.register_staff(db, staff_data, registration_data.password, clinic_id)
        
        return {
            "id": staff.id,
            "first_name": staff.first_name,
            "last_name": staff.last_name,
            "email": staff.email,
            "role": staff.role.value if staff.role else None,
            "clinic_id": staff.clinic_id,
            "is_active": staff.is_active
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Staff registration failed: {str(e)}"
        )

@router.post("/verify-token")
async def verify_token(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Verify if the provided token is valid
    Returns user information if token is valid
    """
    return {
        "valid": True,
        "user_type": current_user.get("user_type"),
        "user_id": current_user.get("user_id"),
        "expires_at": current_user.get("exp")
    }

@router.post("/logout")
async def logout():
    """
    Logout user (client-side token removal)
    Since JWT tokens are stateless, actual logout happens on client side
    """
    return {"message": "Logged out successfully. Please remove the token from client storage."}

@router.post("/verify-clinic-email")
async def verify_clinic_email(
    request: VerifyClinicEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Verify a clinic's email using the OTP code.
    - **clinic_id**: Clinic ID
    - **otp**: One-time password
    """
    success = auth_service.verify_clinic_email(db, request.clinic_id, request.otp)
    if success:
        return {"success": True, "message": "Email verified successfully."}
    else:
        raise HTTPException(status_code=400, detail="Invalid OTP or clinic ID.")

# Access control helper routes
@router.get("/clinic/{clinic_id}/access-check")
async def check_clinic_access(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user has access to specified clinic
    Useful for frontend authorization checks
    """
    has_access = auth_service.has_clinic_access(current_user, clinic_id, db)
    
    return {
        "clinic_id": clinic_id,
        "has_access": has_access,
        "user_type": current_user.get("user_type"),
        "user_id": current_user.get("user_id")
    }

@router.get("/clinic/{clinic_id}/setup-status")
async def get_clinic_setup_status(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the setup status for a clinic's Twilio and ElevenLabs integrations
    """
    # Check if user has access to this clinic
    require_clinic_access(current_user, clinic_id, db)
    
    try:
        clinic = auth_service.get_clinic_by_id(db, clinic_id)
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinic not found"
            )
        
        setup_results = getattr(clinic, 'setup_results', {})
        
        return {
            "clinic_id": clinic_id,
            "clinic_name": clinic.name,
            "twilio_phone_number": getattr(clinic, 'twilio_phone_number', None),
            "twilio_phone_sid": getattr(clinic, 'twilio_phone_sid', None),
            "elevenlabs_agent_id": getattr(clinic, 'elevenlabs_agent_id', None),
            "elevenlabs_agent_name": getattr(clinic, 'elevenlabs_agent_name', None),
            "setup_results": setup_results,
            "setup_complete": bool(
                getattr(clinic, 'twilio_phone_number', None) and 
                getattr(clinic, 'elevenlabs_agent_id', None)
            )
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get setup status: {str(e)}"
        )

@router.post("/clinic/{clinic_id}/retry-setup")
async def retry_clinic_setup(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retry failed setup steps for a clinic's integrations
    """
    # Check if user has access to this clinic
    require_clinic_access(current_user, clinic_id, db)
    
    try:
        clinic = auth_service.get_clinic_by_id(db, clinic_id)
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinic not found"
            )
        
        # Import setup service
        from services.setup_service import clinic_setup_service
        
        # Retry setup
        retry_results = clinic_setup_service.retry_failed_setup(clinic, db)
        
        return {
            "clinic_id": clinic_id,
            "clinic_name": clinic.name,
            "retry_results": retry_results,
            "message": "Setup retry completed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry setup: {str(e)}"
        )

@router.get("/clinics")
async def list_registered_clinics(db: Session = Depends(get_db)):
    """
    Get a list of all registered clinics and their details (id, name, phone, email, address, twilio phone number, agent ID and name).
    """
    clinics = db.query(Clinic).all()
    result = []
    for clinic in clinics:
        result.append({
            "id": clinic.id,
            "name": clinic.name,
            "phone": clinic.phone,
            "email": clinic.email,
            "address": clinic.address,
            "twilio_phone_number": clinic.twilio_phone_number,
            "agent_id": clinic.elevenlabs_agent_id,
            "agent_name": clinic.elevenlabs_agent_name
        })
    return result