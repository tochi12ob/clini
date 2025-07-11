"""
Twilio Service for Clinic AI Assistant
Handles phone number purchasing, configuration, and webhook management
"""
import os
import logging
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwilioService:
    """Service for managing Twilio phone numbers and configurations"""
    
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.webhook_base_url = os.getenv("WEBHOOK_BASE_URL", "https://your-domain.com")
        
        if not self.account_sid or not self.auth_token:
            logger.error("Twilio credentials not found in environment variables")
            self.client = None
        else:
            self.client = Client(self.account_sid, self.auth_token)
    
    def purchase_phone_number(self, clinic_id: int, area_code: str = None, country_code: str = "US") -> Optional[Dict[str, Any]]:
        """
        Purchase a new phone number for a clinic
        
        Args:
            clinic_id: ID of the clinic
            area_code: Preferred area code (optional)
            country_code: Country code (default: US)
            
        Returns:
            Dictionary with phone number details or None if failed
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return None
        
        try:
            # Search for available phone numbers
            search_criteria = {
                'voice_enabled': True,
                'sms_enabled': True
            }
            
            if area_code:
                search_criteria['area_code'] = area_code
            
            # Search for available numbers - fix: remove country_code from search_criteria
            # The country_code is passed as the first parameter to available_phone_numbers()
            available_numbers = self.client.available_phone_numbers(country_code).local.list(
                **search_criteria,
                limit=10
            )
            
            if not available_numbers:
                logger.warning(f"No available phone numbers found for area code {area_code}")
                # Try without area code if specific area code search fails
                if area_code:
                    logger.info(f"Retrying without area code for clinic {clinic_id}")
                    available_numbers = self.client.available_phone_numbers(country_code).local.list(
                        voice_enabled=True,
                        sms_enabled=True,
                        limit=10
                    )
                
                if not available_numbers:
                    logger.error(f"No available phone numbers found for country {country_code}")
                    return None
            
            # Purchase the first available number
            number_to_purchase = available_numbers[0]
            
            # Configure webhook URLs
            voice_webhook_url = f"{self.webhook_base_url}/webhooks/twilio/voice/{clinic_id}"
            sms_webhook_url = f"{self.webhook_base_url}/webhooks/twilio/sms/{clinic_id}"
            
            # Purchase the phone number
            purchased_number = self.client.incoming_phone_numbers.create(
                phone_number=number_to_purchase.phone_number,
                voice_url=voice_webhook_url,
                voice_method='POST',
                sms_url=sms_webhook_url,
                sms_method='POST',
                friendly_name=f"Clinic {clinic_id} - AI Assistant"
            )
            
            logger.info(f"Successfully purchased phone number {purchased_number.phone_number} for clinic {clinic_id}")
            
            return {
                "phone_number": purchased_number.phone_number,
                "sid": purchased_number.sid,
                "friendly_name": purchased_number.friendly_name,
                "voice_url": voice_webhook_url,
                "sms_url": sms_webhook_url,
                "capabilities": {
                    "voice": True,
                    "sms": True
                }
            }
            
        except TwilioException as e:
            logger.error(f"Twilio error purchasing phone number for clinic {clinic_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error purchasing phone number for clinic {clinic_id}: {str(e)}")
            return None
    
    def update_phone_number_webhooks(self, phone_sid: str, clinic_id: int) -> bool:
        """
        Update webhook URLs for a phone number
        
        Args:
            phone_sid: Twilio phone number SID
            clinic_id: ID of the clinic
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return False
        
        try:
            voice_webhook_url = f"{self.webhook_base_url}/webhooks/twilio/voice/{clinic_id}"
            sms_webhook_url = f"{self.webhook_base_url}/webhooks/twilio/sms/{clinic_id}"
            
            self.client.incoming_phone_numbers(phone_sid).update(
                voice_url=voice_webhook_url,
                voice_method='POST',
                sms_url=sms_webhook_url,
                sms_method='POST'
            )
            
            logger.info(f"Updated webhooks for phone number {phone_sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Twilio error updating webhooks for {phone_sid}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating webhooks for {phone_sid}: {str(e)}")
            return False
    
    def release_phone_number(self, phone_sid: str) -> bool:
        """
        Release a phone number
        
        Args:
            phone_sid: Twilio phone number SID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return False
        
        try:
            self.client.incoming_phone_numbers(phone_sid).delete()
            logger.info(f"Successfully released phone number {phone_sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Twilio error releasing phone number {phone_sid}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error releasing phone number {phone_sid}: {str(e)}")
            return False
    
    def get_phone_number_details(self, phone_sid: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a phone number
        
        Args:
            phone_sid: Twilio phone number SID
            
        Returns:
            Dictionary with phone number details or None if failed
        """
        if not self.client:
            logger.error("Twilio client not initialized")
            return None
        
        try:
            phone_number = self.client.incoming_phone_numbers(phone_sid).fetch()
            
            return {
                "phone_number": phone_number.phone_number,
                "sid": phone_number.sid,
                "friendly_name": phone_number.friendly_name,
                "voice_url": phone_number.voice_url,
                "sms_url": phone_number.sms_url,
                "capabilities": phone_number.capabilities
            }
            
        except TwilioException as e:
            logger.error(f"Twilio error fetching phone number {phone_sid}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching phone number {phone_sid}: {str(e)}")
            return None

# Global instance
twilio_service = TwilioService()