"""
Authentication Routes for Clinic AI Assistant
Handles login, registration, token validation, and access control
"""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel, EmailStr
from datetime import timedelta

from database import get_db
from services.auth_service import auth_service
from models import Clinic, Staff, Admin
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

class AdminRegisterRequest(BaseModel):
    email: EmailStr
    password: str

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

class AthenaCredsModel(BaseModel):
    athena_client_id: str
    athena_client_secret: str
    athena_api_base_url: str
    athena_practice_id: str

class WebhookToolGenRequest(BaseModel):
    clinic_id: str
    ehr: str
    athena_creds: AthenaCredsModel
    epic_creds: Optional[Any] = None

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

@router.post("/register/admin", response_model=TokenResponse)
async def register_admin(
    registration_data: AdminRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new admin
    - **email**: Admin email address (must be unique)
    - **password**: Admin password
    """
    try:
        admin = auth_service.register_admin(db, registration_data.email, registration_data.password)
        access_token = auth_service.create_admin_token(admin)
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user_type="admin",
            expires_in=auth_service.access_token_expire_minutes * 60
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Admin registration failed: {str(e)}"
        )

@router.post("/login/admin", response_model=TokenResponse)
async def login_admin(
    login_data: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate admin and return access token
    - **email**: Admin email address
    - **password**: Admin password
    """
    admin = auth_service.authenticate_admin(db, login_data.email, login_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth_service.create_admin_token(admin)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_type="admin",
        expires_in=auth_service.access_token_expire_minutes * 60
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
    
    elif user_type == "admin":
        admin = auth_service.get_admin_by_id(db, user_id)
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        return {
            "user_type": "admin",
            "id": admin.id,
            "email": admin.email,
            "is_active": admin.is_active
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
