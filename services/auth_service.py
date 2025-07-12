"""
Authentication Service for Clinic AI Assistant
Handles JWT token creation, validation, and clinic access control
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models import Clinic, Staff
import os
from dotenv import load_dotenv
import asyncio
from services.setup_service import clinic_setup_service
import random

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    """Authentication service for clinic management"""
    
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM
        self.access_token_expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def authenticate_clinic(self, db: Session, email: str, password: str) -> Optional[Clinic]:
        """Authenticate clinic by email and password"""
        clinic = db.query(Clinic).filter(Clinic.email == email, Clinic.is_active == True).first()
        if not clinic:
            return None
        
        if hasattr(clinic, 'password_hash') and self.verify_password(password, clinic.password_hash):
            return clinic
        return None
    
    def authenticate_staff(self, db: Session, email: str, password: str) -> Optional[Staff]:
        """Authenticate staff member by email and password"""
        staff = db.query(Staff).filter(Staff.email == email, Staff.is_active == True).first()
        if not staff:
            return None
        
        # Check if staff has password_hash field, if not, staff authentication is not set up
        if hasattr(staff, 'password_hash') and staff.password_hash and self.verify_password(password, staff.password_hash):
            return staff
        return None
    
    def get_clinic_by_id(self, db: Session, clinic_id: int) -> Optional[Clinic]:
        """Get clinic by ID"""
        return db.query(Clinic).filter(Clinic.id == clinic_id, Clinic.is_active == True).first()
    
    def get_staff_by_id(self, db: Session, staff_id: int) -> Optional[Staff]:
        """Get staff by ID"""
        return db.query(Staff).filter(Staff.id == staff_id, Staff.is_active == True).first()
    
    def has_clinic_access(self, current_user: Dict[str, Any], clinic_id: int, db: Session) -> bool:
        """Check if current user has access to specified clinic"""
        user_type = current_user.get("user_type")
        user_id = current_user.get("user_id")
        
        if user_type == "clinic":
            # Clinic owner has access to their own clinic
            return user_id == clinic_id
        
        elif user_type == "staff":
            # Staff has access if they belong to the clinic
            staff = self.get_staff_by_id(db, user_id)
            return staff and staff.clinic_id == clinic_id
        
        return False
    
    def create_clinic_token(self, clinic: Clinic) -> str:
        """Create access token for clinic"""
        token_data = {
            "user_id": clinic.id,
            "user_type": "clinic",
            "email": clinic.email,
            "name": clinic.name
        }
        return self.create_access_token(token_data)
    
    def create_staff_token(self, staff: Staff) -> str:
        """Create access token for staff member"""
        token_data = {
            "user_id": staff.id,
            "user_type": "staff", 
            "email": staff.email,
            "clinic_id": staff.clinic_id,
            "role": staff.role.value if staff.role else "staff",  # Handle Enum role
            "first_name": staff.first_name,
            "last_name": staff.last_name
        }
        return self.create_access_token(token_data)
    
    def register_clinic(self, db: Session, clinic_data: Dict[str, Any], password: str) -> Clinic:
        """Register a new clinic"""
        # Check if clinic with email already exists
        existing_clinic = db.query(Clinic).filter(Clinic.email == clinic_data.get("email")).first()
        if existing_clinic:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clinic with this email address already exists"
            )
        
        # Check if clinic with phone already exists
        existing_clinic_phone = db.query(Clinic).filter(Clinic.phone == clinic_data.get("phone")).first()
        if existing_clinic_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clinic with this phone number already exists"
            )
        
        # Extract area code for setup
        area_code = clinic_data.pop("area_code", None)
        
        # Create new clinic
        hashed_password = self.get_password_hash(password)
        clinic_data["password_hash"] = hashed_password
        
        clinic = Clinic(**clinic_data)
        # Generate OTP
        otp = str(random.randint(100000, 999999))
        clinic.email_verification_code = otp
        clinic.email_verified = False
        db.add(clinic)
        db.commit()
        db.refresh(clinic)
        
        # Trigger async setup of Twilio phone number and ElevenLabs AI agent
        # This runs in the background and won't block the registration response
        try:
            # Use asyncio to run setup in background
            try:
                loop = asyncio.get_event_loop()
                if loop and loop.is_running():
                    # If we're in an async context, create a task
                    asyncio.create_task(self._setup_clinic_integrations_async(clinic, db, area_code))
                else:
                    # If we're in a sync context, run in thread
                    import threading
                    thread = threading.Thread(
                        target=self._setup_clinic_integrations_sync,
                        args=(clinic, db, area_code),
                        daemon=True
                    )
                    thread.start()
            except RuntimeError:
                # No event loop available, run in thread
                import threading
                thread = threading.Thread(
                    target=self._setup_clinic_integrations_sync,
                    args=(clinic, db, area_code),
                    daemon=True
                )
                thread.start()
        except Exception as e:
            # Log error but don't fail registration
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to trigger clinic setup for clinic {clinic.id}: {str(e)}")
        
        return clinic
    
    async def _setup_clinic_integrations_async(self, clinic: Clinic, db: Session, area_code: str = None):
        """Async wrapper for clinic setup"""
        try:
            # Create a new session for the background task
            from database import SessionLocal
            setup_db = SessionLocal()
            try:
                # Refresh the clinic object in the new session
                clinic_in_new_session = setup_db.query(Clinic).filter(Clinic.id == clinic.id).first()
                if clinic_in_new_session:
                    await clinic_setup_service.setup_clinic_integrations(clinic_in_new_session, setup_db, area_code)
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Could not find clinic {clinic.id} in new session")
            finally:
                setup_db.close()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Async clinic setup failed for clinic {clinic.id}: {str(e)}")
    
    def _setup_clinic_integrations_sync(self, clinic: Clinic, db: Session, area_code: str = None):
        """Sync wrapper for clinic setup"""
        try:
            # Create a new session for the background task
            from database import SessionLocal
            import asyncio
            setup_db = SessionLocal()
            try:
                # Refresh the clinic object in the new session
                clinic_in_new_session = setup_db.query(Clinic).filter(Clinic.id == clinic.id).first()
                if clinic_in_new_session:
                    # Run the async setup in a new event loop
                    asyncio.run(clinic_setup_service.setup_clinic_integrations(clinic_in_new_session, setup_db, area_code))
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Could not find clinic {clinic.id} in new session")
            finally:
                setup_db.close()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Sync clinic setup failed for clinic {clinic.id}: {str(e)}")
    
    def register_staff(self, db: Session, staff_data: Dict[str, Any], password: str, clinic_id: int) -> Staff:
        """Register a new staff member"""
        # Check if staff with email already exists
        existing_staff = db.query(Staff).filter(Staff.email == staff_data.get("email")).first()
        if existing_staff:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Staff with this email already exists"
            )
        
        # Verify clinic exists
        clinic = self.get_clinic_by_id(db, clinic_id)
        if not clinic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinic not found"
            )
        
        # Create new staff member
        hashed_password = self.get_password_hash(password)
        staff_data["password_hash"] = hashed_password
        staff_data["clinic_id"] = clinic_id
        
        staff = Staff(**staff_data)
        db.add(staff)
        db.commit()
        db.refresh(staff)
        
        return staff
    
    def change_password(self, db: Session, user_id: int, user_type: str, 
                       old_password: str, new_password: str) -> bool:
        """Change user password"""
        if user_type == "clinic":
            user = self.get_clinic_by_id(db, user_id)
        elif user_type == "staff":
            user = self.get_staff_by_id(db, user_id)
        else:
            return False
        
        if not user or not hasattr(user, 'password_hash'):
            return False
        
        if not self.verify_password(old_password, user.password_hash):
            return False
        
        user.password_hash = self.get_password_hash(new_password)
        db.commit()
        return True

    def verify_clinic_email(self, db: Session, clinic_id: int, otp: str) -> bool:
        clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
        if not clinic or not clinic.email_verification_code:
            return False
        if clinic.email_verification_code == otp:
            clinic.email_verified = True
            clinic.email_verification_code = None
            db.commit()
            return True
        return False

# Global instance
auth_service = AuthService()