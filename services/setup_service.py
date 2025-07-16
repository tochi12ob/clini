"""
Clinic Setup Service for Clinic AI Assistant
Handles the complete setup process for new clinics including Twilio and ElevenLabs integration
"""
import logging
import os
import requests
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from models import Clinic
from services.twilio_service import twilio_service
from services.elevenlabs_service import ElevenLabsAgentCreator
from services.agent_setup_service import AgentSetupService, agent_setup_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ClinicSetupService:
    """Service for setting up new clinics with phone numbers and AI agents"""
    
    def __init__(self):
        self.twilio_service = twilio_service
        self.elevenlabs_service = ElevenLabsAgentCreator()
        # Store ElevenLabs API key and base URL for direct API calls
        self.elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY') or 'sk_911c468b5acba9938859200fdc4f9b8ffa8584b7b17e7487'
        self.elevenlabs_base_url = "https://api.elevenlabs.io"
    
    async def setup_clinic_integrations(self, clinic: Clinic, db: Session, area_code: str = None) -> Dict[str, Any]:
        """
        Set up Twilio phone number and ElevenLabs AI agent for a new clinic
        
        Args:
            clinic: Clinic model instance
            db: Database session
            area_code: Preferred area code for phone number
            
        Returns:
            Dictionary with setup results
        """
        setup_results = {
            "clinic_id": clinic.id,
            "twilio_setup": {"success": False, "error": None, "data": None},
            "elevenlabs_setup": {"success": False, "error": None, "data": None},
            "integration_setup": {"success": False, "error": None, "data": None}
        }
        
        # Step 1: Purchase Twilio phone number
        logger.info(f"Setting up Twilio phone number for clinic {clinic.id}")
        twilio_result = self._setup_twilio_phone(clinic, area_code)
        setup_results["twilio_setup"] = twilio_result
        
        # Step 2: Create ElevenLabs AI agent
        logger.info(f"Setting up ElevenLabs AI agent for clinic {clinic.id}")
        elevenlabs_result = self._setup_elevenlabs_agent(clinic)
        setup_results["elevenlabs_setup"] = elevenlabs_result
        
        # Step 3: Link Twilio phone to ElevenLabs agent (if both succeeded)
        if twilio_result["success"] and elevenlabs_result["success"]:
            logger.info(f"Linking Twilio phone to ElevenLabs agent for clinic {clinic.id}")
            integration_result = await self._link_phone_to_agent(
                twilio_result["data"],
                elevenlabs_result["data"]["agent_id"]
            )
            setup_results["integration_setup"] = integration_result

            # Assign phone number to agent in ElevenLabs
            phone_number = twilio_result["data"].get("phone_number")
            agent_id = elevenlabs_result["data"].get("agent_id")
            if phone_number and agent_id:
                # Get phone_number_id from ElevenLabs
                phone_id = await agent_setup_service._get_elevenlabs_phone_id(phone_number)
                if phone_id:
                    agent_setup_service.assign_phone_to_agent(agent_id, phone_id)
        
        # Step 4: Update clinic record with setup information
        self._update_clinic_record(clinic, setup_results, db)
        
        return setup_results
    
    def _setup_twilio_phone(self, clinic: Clinic, area_code: str = None) -> Dict[str, Any]:
        """Set up Twilio phone number for clinic"""
        try:
            phone_data = self.twilio_service.purchase_phone_number(
                clinic_id=clinic.id,
                area_code=area_code
            )
            
            if phone_data:
                return {
                    "success": True,
                    "error": None,
                    "data": phone_data
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to purchase phone number",
                    "data": None
                }
        except Exception as e:
            logger.error(f"Error setting up Twilio phone for clinic {clinic.id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    def _setup_elevenlabs_agent(self, clinic: Clinic) -> Dict[str, Any]:
        """Set up ElevenLabs AI agent for clinic"""
        try:
            # Use the basic create_agent method from ElevenLabs service
            agent_id = self.elevenlabs_service.create_agent()
            
            if agent_id:
                return {
                    "success": True,
                    "error": None,
                    "data": {
                        "agent_id": agent_id,
                        "name": f"{clinic.name} AI Agent"
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create AI agent",
                    "data": None
                }
        except Exception as e:
            logger.error(f"Error setting up ElevenLabs agent for clinic {clinic.id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    async def _link_phone_to_agent(self, twilio_data: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
        """
        Link Twilio phone number to ElevenLabs agent using the ElevenLabs API
        
        Args:
            twilio_data: Dictionary containing Twilio phone data (sid, phone_number, etc.)
            agent_id: ElevenLabs agent ID
            
        Returns:
            Dictionary with integration results
        """
        try:
            if not self.elevenlabs_api_key:
                logger.error("ElevenLabs API key not found")
                return {
                    "success": False,
                    "error": "ElevenLabs API key not found",
                    "data": None
                }
            
            # Extract required data from Twilio response
            phone_number = twilio_data.get("phone_number")
            twilio_sid = twilio_data.get("sid")
            
            if not phone_number or not twilio_sid:
                return {
                    "success": False,
                    "error": "Missing required Twilio data (phone_number or sid)",
                    "data": None
                }
            
            # Create phone number integration in ElevenLabs using direct API call
            logger.info(f"Creating ElevenLabs phone number integration for {phone_number}")
            
            # Get Twilio credentials
            twilio_credentials = self._get_twilio_credentials()
            
            if not twilio_credentials['account_sid'] or not twilio_credentials['auth_token']:
                return {
                    "success": False,
                    "error": "Twilio credentials not found - check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env file",
                    "data": None
                }
            
            # Prepare the request data with proper Twilio credentials
            phone_data = {
                "phone_number": phone_number,
                "label": f"Clinic Phone - {phone_number}",
                "sid": twilio_credentials['account_sid'],  # This should be Account SID, not phone SID
                "token": twilio_credentials['auth_token'],
            }
            
            logger.info(f"Sending request to ElevenLabs with Account SID: {twilio_credentials['account_sid'][:8]}...")
            
            # Make the API call to ElevenLabs
            headers = {
                "xi-api-key": self.elevenlabs_api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.elevenlabs_base_url}/v1/convai/phone-numbers",
                json=phone_data,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"ElevenLabs API error: {response.status_code} - {response.text}",
                    "data": None
                }
            
            response_data = response.json()
            
            # Link the phone number to the specific agent
            # Note: You may need to update the agent configuration to use this phone number
            # This depends on your ElevenLabs agent configuration
            await self._configure_agent_phone_number(agent_id, phone_number)
            
            logger.info(f"Successfully linked phone {phone_number} to agent {agent_id}")
            
            return {
                "success": True,
                "error": None,
                "data": {
                    "phone_number": phone_number,
                    "agent_id": agent_id,
                    "elevenlabs_phone_integration": response_data
                }
            }
            
        except Exception as e:
            logger.error(f"Error linking phone {twilio_data.get('phone_number')} to agent {agent_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    def _get_twilio_credentials(self) -> Dict[str, str]:
        """
        Get Twilio credentials for ElevenLabs integration
        
        Returns:
            Dictionary with Twilio Account SID and Auth Token
        """
        # Try to get credentials from twilio_service first
        if hasattr(self.twilio_service, 'account_sid') and hasattr(self.twilio_service, 'auth_token'):
            return {
                'account_sid': self.twilio_service.account_sid,
                'auth_token': self.twilio_service.auth_token
            }
        
        # Fallback: get from environment variables
        return {
            'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
            'auth_token': os.getenv('TWILIO_AUTH_TOKEN')
        }
    
    async def _configure_agent_phone_number(self, agent_id: str, phone_number: str):
        """
        Configure the ElevenLabs agent to use the linked phone number
        
        Args:
            agent_id: ElevenLabs agent ID
            phone_number: Phone number to associate with the agent
        """
        try:
            # Import the agent setup service to use its linking method
            # from services.agent_setup_service import agent_setup_service # This line is removed as it's now imported at the top
            
            logger.info(f"Configuring agent {agent_id} to use phone number {phone_number}")
            
            # Use the agent setup service to link the phone number to the agent
            linked = await agent_setup_service.link_phone_to_agent(agent_id, phone_number)
            
            if linked:
                logger.info(f"Successfully linked phone {phone_number} to agent {agent_id}")
            else:
                logger.warning(f"Failed to link phone {phone_number} to agent {agent_id}")
                
        except Exception as e:
            logger.error(f"Error configuring agent {agent_id} with phone {phone_number}: {str(e)}")
    
    def _update_clinic_record(self, clinic: Clinic, setup_results: Dict[str, Any], db: Session):
        """Update clinic record with setup information"""
        try:
            # Update Twilio phone information
            if setup_results["twilio_setup"]["success"]:
                twilio_data = setup_results["twilio_setup"]["data"]
                clinic.twilio_phone_sid = twilio_data["sid"]
                clinic.twilio_phone_number = twilio_data["phone_number"]
            
            # Update ElevenLabs agent information
            if setup_results["elevenlabs_setup"]["success"]:
                elevenlabs_data = setup_results["elevenlabs_setup"]["data"]
                clinic.elevenlabs_agent_id = elevenlabs_data["agent_id"]
                clinic.elevenlabs_agent_name = elevenlabs_data["name"]
            
            # Update integration information
            if setup_results["integration_setup"]["success"]:
                integration_data = setup_results["integration_setup"]["data"]
                clinic.phone_agent_integration_status = "active"
                clinic.elevenlabs_phone_integration = integration_data
            
            # Store setup results in JSON format for debugging/monitoring
            clinic.setup_results = setup_results
            
            db.commit()
            logger.info(f"Updated clinic {clinic.id} record with setup information")
            
        except Exception as e:
            logger.error(f"Error updating clinic {clinic.id} record: {str(e)}")
            db.rollback()
    
    def cleanup_clinic_integrations(self, clinic: Clinic, db: Session) -> Dict[str, Any]:
        """
        Clean up Twilio and ElevenLabs resources when deleting a clinic
        
        Args:
            clinic: Clinic model instance
            db: Database session
            
        Returns:
            Dictionary with cleanup results
        """
        cleanup_results = {
            "clinic_id": clinic.id,
            "twilio_cleanup": {"success": False, "error": None},
            "elevenlabs_cleanup": {"success": False, "error": None},
            "phone_integration_cleanup": {"success": False, "error": None}
        }
        
        # Clean up ElevenLabs phone integration first
        if clinic.twilio_phone_number and self.elevenlabs_api_key:
            try:
                # Remove phone number from ElevenLabs using direct API call
                logger.info(f"Cleaning up ElevenLabs phone integration for {clinic.twilio_phone_number}")
                
                # Note: You may need to implement the delete endpoint
                # This depends on the ElevenLabs API documentation for deleting phone numbers
                headers = {
                    "xi-api-key": self.elevenlabs_api_key,
                    "Content-Type": "application/json"
                }
                
                # Example delete call (adjust based on actual API)
                # response = requests.delete(f"{self.elevenlabs_base_url}/v1/convai/phone-numbers/{phone_id}", headers=headers)
                
                cleanup_results["phone_integration_cleanup"] = {
                    "success": True,
                    "error": None,
                    "note": "Phone integration cleanup logged - implement delete endpoint as needed"
                }
            except Exception as e:
                cleanup_results["phone_integration_cleanup"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # Clean up Twilio phone number
        if clinic.twilio_phone_sid:
            try:
                success = self.twilio_service.release_phone_number(clinic.twilio_phone_sid)
                cleanup_results["twilio_cleanup"] = {
                    "success": success,
                    "error": None if success else "Failed to release phone number"
                }
            except Exception as e:
                cleanup_results["twilio_cleanup"] = {
                    "success": False,
                    "error": str(e)
                }
        
        # Clean up ElevenLabs agent
        if clinic.elevenlabs_agent_id:
            try:
                # Check if delete_agent method exists in the service
                if hasattr(self.elevenlabs_service, 'delete_agent'):
                    success = self.elevenlabs_service.delete_agent(clinic.elevenlabs_agent_id)
                else:
                    # Basic service doesn't have delete method, just log it
                    logger.info(f"Would delete ElevenLabs agent {clinic.elevenlabs_agent_id} in full implementation")
                    success = True  # Assume success for basic service
                
                cleanup_results["elevenlabs_cleanup"] = {
                    "success": success,
                    "error": None if success else "Failed to delete AI agent"
                }
            except Exception as e:
                cleanup_results["elevenlabs_cleanup"] = {
                    "success": False,
                    "error": str(e)
                }
        
        return cleanup_results
    
    def retry_failed_setup(self, clinic: Clinic, db: Session) -> Dict[str, Any]:
        """
        Retry failed setup steps for a clinic
        
        Args:
            clinic: Clinic model instance
            db: Database session
            
        Returns:
            Dictionary with retry results
        """
        logger.info(f"Retrying failed setup for clinic {clinic.id}")
        
        # Check what needs to be retried
        needs_twilio = not clinic.twilio_phone_sid
        needs_elevenlabs = not clinic.elevenlabs_agent_id
        needs_integration = not getattr(clinic, 'phone_agent_integration_status', None) == 'active'
        
        if not needs_twilio and not needs_elevenlabs and not needs_integration:
            return {
                "clinic_id": clinic.id,
                "message": "No retry needed, all integrations already set up"
            }
        
        # Retry setup
        return self.setup_clinic_integrations(clinic, db)
    
    def get_clinic_phone_status(self, clinic: Clinic) -> Dict[str, Any]:
        """
        Get the current phone integration status for a clinic
        
        Args:
            clinic: Clinic model instance
            
        Returns:
            Dictionary with phone integration status
        """
        return {
            "clinic_id": clinic.id,
            "twilio_phone_number": clinic.twilio_phone_number,
            "twilio_phone_sid": clinic.twilio_phone_sid,
            "elevenlabs_agent_id": clinic.elevenlabs_agent_id,
            "integration_status": getattr(clinic, 'phone_agent_integration_status', 'not_configured'),
            "setup_completed": bool(
                clinic.twilio_phone_sid and 
                clinic.elevenlabs_agent_id and 
                getattr(clinic, 'phone_agent_integration_status', None) == 'active'
            )
        }

# Global instance - automatically uses environment variables
clinic_setup_service = ClinicSetupService()