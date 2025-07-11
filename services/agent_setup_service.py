"""
Agent Setup Service for Clinic AI Assistant
Handles ElevenLabs agent configuration and outbound call functionality
"""
import os
import logging
import requests
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from models import Clinic, Call, CallType, CallStatus, KnowledgeBase

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentSetupService:
    """Service for managing ElevenLabs agents and outbound calls"""
    
    def __init__(self):
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"
        
        if not self.elevenlabs_api_key:
            logger.error("ElevenLabs API key not found in environment variables")
            raise ValueError("ElevenLabs API key is required")
        
        self.headers = {
            "Accept": "application/json",
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        
        # Initialize ElevenLabs client
        try:
            self.client = ElevenLabs(api_key=self.elevenlabs_api_key)
        except Exception as e:
            logger.error(f"Failed to initialize ElevenLabs client: {str(e)}")
            self.client = None
    
    def get_clinic_agent_info(self, db: Session, clinic_id: int) -> Optional[Dict[str, Any]]:
        """
        Get ElevenLabs agent information for a clinic
        
        Args:
            db: Database session
            clinic_id: ID of the clinic
            
        Returns:
            Dictionary with agent information or None if not found
        """
        try:
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                logger.error(f"Clinic {clinic_id} not found")
                return None
            
            if not clinic.elevenlabs_agent_id:
                logger.warning(f"Clinic {clinic_id} does not have an ElevenLabs agent configured")
                return None
            
            return {
                "clinic_id": clinic.id,
                "clinic_name": clinic.name,
                "agent_id": clinic.elevenlabs_agent_id,
                "agent_name": clinic.elevenlabs_agent_name,
                "twilio_phone_number": clinic.twilio_phone_number,
                "twilio_phone_sid": clinic.twilio_phone_sid,
                "ai_voice_id": clinic.ai_voice_id,
                "ai_personality": clinic.ai_personality,
                "greeting_message": clinic.greeting_message
            }
            
        except Exception as e:
            logger.error(f"Error getting clinic agent info for clinic {clinic_id}: {str(e)}")
            return None
    
    def create_agent_for_clinic(self, db: Session, clinic_id: int, agent_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Create an ElevenLabs agent for a clinic
        
        Args:
            db: Database session
            clinic_id: ID of the clinic
            agent_name: Optional custom agent name
            
        Returns:
            Dictionary with agent details or None if failed
        """
        try:
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                logger.error(f"Clinic {clinic_id} not found")
                return None
            
            if clinic.elevenlabs_agent_id:
                logger.info(f"Clinic {clinic_id} already has an agent: {clinic.elevenlabs_agent_id}")
                return self.get_clinic_agent_info(db, clinic_id)
            
            # Default agent configuration
            agent_config = {
                "name": agent_name or f"{clinic.name} AI Assistant",
                "conversation_config": {
                    "initial_message": clinic.greeting_message or "Hello, this is your clinic's AI assistant. How can I help you today?",
                    "voice_id": clinic.ai_voice_id,
                    "personality": clinic.ai_personality or "Professional and helpful medical assistant"
                }
            }
            
            # Create the agent
            response = requests.post(
                f"{self.base_url}/convai/agents/create",
                headers=self.headers,
                json=agent_config
            )
            
            if response.status_code in [200, 201]:
                agent_data = response.json()
                agent_id = agent_data.get("agent_id")
                
                # Update clinic with agent information
                clinic.elevenlabs_agent_id = agent_id
                clinic.elevenlabs_agent_name = agent_name or f"{clinic.name} AI Assistant"
                db.commit()
                
                logger.info(f"Successfully created ElevenLabs agent {agent_id} for clinic {clinic_id}")
                
                return {
                    "clinic_id": clinic.id,
                    "clinic_name": clinic.name,
                    "agent_id": agent_id,
                    "agent_name": clinic.elevenlabs_agent_name,
                    "twilio_phone_number": clinic.twilio_phone_number,
                    "twilio_phone_sid": clinic.twilio_phone_sid,
                    "ai_voice_id": clinic.ai_voice_id,
                    "ai_personality": clinic.ai_personality,
                    "greeting_message": clinic.greeting_message
                }
            else:
                logger.error(f"Failed to create ElevenLabs agent. Status: {response.status_code}, Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating agent for clinic {clinic_id}: {str(e)}")
            db.rollback()
            return None
    
    async def make_outbound_call(
        self, 
        db: Session, 
        clinic_id: int, 
        to_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Make an outbound call using ElevenLabs and Twilio
        
        Args:
            db: Database session
            clinic_id: ID of the clinic
            to_number: Phone number to call
            
        Returns:
            Dictionary with call details or None if failed
        """
        try:
            # Get clinic agent information
            agent_info = self.get_clinic_agent_info(db, clinic_id)
            if not agent_info:
                logger.error(f"Cannot make outbound call: clinic {clinic_id} has no agent configured")
                return None
            
            if not agent_info.get("twilio_phone_number"):
                logger.error(f"Cannot make outbound call: clinic {clinic_id} has no Twilio phone number")
                return None
            
            # Create call record in database
            call_record = Call(
                clinic_id=clinic_id,
                from_number=agent_info["twilio_phone_number"],
                to_number=to_number,
                call_type=CallType.OUTBOUND_REMINDER,  # Default call type
                status=CallStatus.INITIATED,
                started_at=None,
                ended_at=None
            )
            db.add(call_record)
            db.flush()  # Get the ID without committing
            
            # First, we need to get the ElevenLabs phone number ID
            # The twilio_phone_sid is the Twilio SID, not the ElevenLabs phone number ID
            elevenlabs_phone_id = await self._get_elevenlabs_phone_id(agent_info["twilio_phone_number"])
            
            if not elevenlabs_phone_id:
                logger.error(f"Cannot make outbound call: phone number {agent_info['twilio_phone_number']} not found in ElevenLabs")
                call_record.status = CallStatus.FAILED
                db.commit()
                return None
            
            # Prepare call data
            call_data = {
                "agent_id": agent_info["agent_id"],
                "agent_phone_number_id": elevenlabs_phone_id,
                "to_number": to_number
            }
            
            # Make the outbound call
            if self.client:
                try:
                    response = self.client.conversational_ai.twilio.outbound_call(**call_data)
                    
                    # Update call record with response data
                    if response and hasattr(response, 'conversation_id'):
                        call_record.twilio_call_sid = getattr(response, 'callSid', None)
                        call_record.status = CallStatus.IN_PROGRESS
                        call_record.started_at = db.query(func.now()).scalar()
                        
                        db.commit()
                        
                        logger.info(f"Successfully initiated outbound call {call_record.id} for clinic {clinic_id}")
                        
                        return {
                            "call_id": call_record.id,
                            "conversation_id": getattr(response, 'conversation_id', None),
                            "call_sid": getattr(response, 'callSid', None),
                            "status": "initiated",
                            "from_number": agent_info["twilio_phone_number"],
                            "to_number": to_number,
                            "call_type": call_record.call_type.value
                        }
                    else:
                        logger.error(f"Invalid response from ElevenLabs outbound call API")
                        call_record.status = CallStatus.FAILED
                        db.commit()
                        return None
                        
                except Exception as e:
                    logger.error(f"ElevenLabs API error making outbound call: {str(e)}")
                    call_record.status = CallStatus.FAILED
                    db.commit()
                    return None
            else:
                logger.error("ElevenLabs client not initialized")
                call_record.status = CallStatus.FAILED
                db.commit()
                return None
                
        except Exception as e:
            logger.error(f"Error making outbound call for clinic {clinic_id}: {str(e)}")
            db.rollback()
            return None
    
    def get_call_status(self, db: Session, call_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the status of a call
        
        Args:
            db: Database session
            call_id: ID of the call
            
        Returns:
            Dictionary with call status or None if not found
        """
        try:
            call = db.query(Call).filter(Call.id == call_id).first()
            if not call:
                logger.error(f"Call {call_id} not found")
                return None
            
            return {
                "call_id": call.id,
                "status": call.status.value,
                "call_type": call.call_type.value,
                "from_number": call.from_number,
                "to_number": call.to_number,
                "duration_seconds": call.duration_seconds,
                "started_at": call.started_at,
                "ended_at": call.ended_at,
                "twilio_call_sid": call.twilio_call_sid,
                "outcome": call.outcome,
                "handoff_to_human": call.handoff_to_human,
                "patient_satisfaction": call.patient_satisfaction
            }
            
        except Exception as e:
            logger.error(f"Error getting call status for call {call_id}: {str(e)}")
            return None
    
    def list_clinic_calls(
        self, 
        db: Session, 
        clinic_id: int, 
        limit: int = 50, 
        offset: int = 0,
        call_type: CallType = None,
        status: CallStatus = None
    ) -> List[Dict[str, Any]]:
        """
        List calls for a clinic with optional filtering
        
        Args:
            db: Database session
            clinic_id: ID of the clinic
            limit: Maximum number of calls to return
            offset: Number of calls to skip
            call_type: Optional filter by call type
            status: Optional filter by call status
            
        Returns:
            List of call dictionaries
        """
        try:
            query = db.query(Call).filter(Call.clinic_id == clinic_id)
            
            if call_type:
                query = query.filter(Call.call_type == call_type)
            
            if status:
                query = query.filter(Call.status == status)
            
            calls = query.order_by(Call.created_at.desc()).offset(offset).limit(limit).all()
            
            return [
                {
                    "call_id": call.id,
                    "status": call.status.value,
                    "call_type": call.call_type.value,
                    "from_number": call.from_number,
                    "to_number": call.to_number,
                    "duration_seconds": call.duration_seconds,
                    "started_at": call.started_at,
                    "ended_at": call.ended_at,
                    "outcome": call.outcome,
                    "handoff_to_human": call.handoff_to_human,
                    "patient_satisfaction": call.patient_satisfaction,
                    "created_at": call.created_at
                }
                for call in calls
            ]
            
        except Exception as e:
            logger.error(f"Error listing calls for clinic {clinic_id}: {str(e)}")
            return []
    
    def get_clinic_twilio_number(self, db: Session, clinic_id: int) -> Optional[str]:
        """
        Get the Twilio phone number for a clinic
        
        Args:
            db: Database session
            clinic_id: ID of the clinic
            
        Returns:
            Twilio phone number string or None if not found
        """
        try:
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                logger.error(f"Clinic {clinic_id} not found")
                return None
            
            return clinic.twilio_phone_number
            
        except Exception as e:
            logger.error(f"Error getting Twilio number for clinic {clinic_id}: {str(e)}")
            return None

    async def upload_document_to_knowledge_base(
        self, 
        db: Session, 
        clinic_id: int, 
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Upload a document to the clinic's knowledge base using ElevenLabs API
        
        Args:
            db: Database session
            clinic_id: ID of the clinic
            file_path: Path to the file to upload
            
        Returns:
            Dictionary with upload details or None if failed
        """
        try:
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                logger.error(f"Clinic {clinic_id} not found")
                return None
            
            if not clinic.elevenlabs_agent_id:
                logger.error(f"Clinic {clinic_id} has no agent configured")
                return None
            
            # Check if agent already has a knowledge base
            existing_kb_id = await self._ensure_agent_knowledge_base(clinic.elevenlabs_agent_id)
            
            # Upload document using the correct ElevenLabs API
            try:
                # Read the file content
                with open(file_path, 'rb') as file:
                    # Determine the correct MIME type based on file extension
                    file_extension = os.path.splitext(file_path)[1].lower()
                    mime_type = {
                        '.pdf': 'application/pdf',
                        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        '.doc': 'application/msword',
                        '.txt': 'text/plain',
                        '.html': 'text/html',
                        '.epub': 'application/epub+zip'
                    }.get(file_extension, 'application/octet-stream')
                    
                    files = {'file': (os.path.basename(file_path), file, mime_type)}
                    
                    # Use the correct endpoint for uploading files to knowledge base
                    response = requests.post(
                        f"{self.base_url}/convai/knowledge-base/file",
                        headers={"xi-api-key": self.elevenlabs_api_key},
                        files=files
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        document_id = response_data.get('id')  # ElevenLabs returns 'id' not 'document_id'
                        
                        # The response should contain the knowledge base ID
                        knowledge_base_id = response_data.get('knowledge_base_id')
                        
                        # If we got a knowledge base ID and the agent doesn't have one, update the agent
                        if knowledge_base_id and not existing_kb_id:
                            try:
                                # Update the agent to use this knowledge base using the correct API structure
                                success = await self._assign_knowledge_base_to_agent(clinic.elevenlabs_agent_id, knowledge_base_id)
                                if success:
                                    logger.info(f"Successfully associated knowledge base {knowledge_base_id} with agent {clinic.elevenlabs_agent_id}")
                                else:
                                    logger.warning(f"Failed to associate knowledge base {knowledge_base_id} with agent {clinic.elevenlabs_agent_id}")
                            except Exception as e:
                                logger.warning(f"Error associating knowledge base with agent: {str(e)}")
                        
                        # Update clinic's knowledge base ID if we have one
                        if knowledge_base_id and not clinic.knowledge_base_id:
                            clinic.knowledge_base_id = knowledge_base_id
                            db.commit()
                            logger.info(f"Updated clinic {clinic_id} knowledge_base_id to {knowledge_base_id}")
                        
                        logger.info(f"Successfully uploaded document for clinic {clinic_id}. Response: {response_data}")
                        
                        return {
                            "document_id": document_id,
                            "file_name": os.path.basename(file_path),
                            "clinic_id": clinic_id,
                            "knowledge_base_id": knowledge_base_id,
                            "agent_id": clinic.elevenlabs_agent_id,
                            "status": "uploaded"
                        }
                    else:
                        logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                        return None
                        
            except Exception as e:
                logger.error(f"ElevenLabs API error uploading document: {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error uploading document for clinic {clinic_id}: {str(e)}")
            return None

    async def create_knowledge_base_from_text(
        self,
        db: Session,
        clinic_id: int,
        text: str,
        name: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a knowledge base document from text for a clinic using ElevenLabs API and assign it to the agent.
        Args:
            db: Database session
            clinic_id: ID of the clinic
            text: Text content to add to the knowledge base
            name: Optional name for the document
        Returns:
            Dictionary with upload details or None if failed
        """
        try:
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                logger.error(f"Clinic {clinic_id} not found")
                return None
            if not clinic.elevenlabs_agent_id:
                logger.error(f"Clinic {clinic_id} has no agent configured")
                return None

            existing_kb_id = await self._ensure_agent_knowledge_base(clinic.elevenlabs_agent_id)

            payload = {"text": text}
            if name:
                payload["name"] = name

            response = requests.post(
                f"{self.base_url}/convai/knowledge-base/text",
                headers={"xi-api-key": self.elevenlabs_api_key, "Content-Type": "application/json"},
                json=payload
            )

            if response.status_code == 200:
                response_data = response.json()
                document_id = response_data.get('id')
                knowledge_base_id = response_data.get('knowledge_base_id') or response_data.get('id')

                # If we got a knowledge base ID and the agent doesn't have one, update the agent
                if knowledge_base_id and not existing_kb_id:
                    try:
                        success = await self._assign_knowledge_base_to_agent(clinic.elevenlabs_agent_id, knowledge_base_id)
                        if success:
                            logger.info(f"Successfully associated knowledge base {knowledge_base_id} with agent {clinic.elevenlabs_agent_id}")
                        else:
                            logger.warning(f"Failed to associate knowledge base {knowledge_base_id} with agent {clinic.elevenlabs_agent_id}")
                    except Exception as e:
                        logger.warning(f"Error associating knowledge base with agent: {str(e)}")

                # Update clinic's knowledge base ID if we have one
                if knowledge_base_id and not clinic.knowledge_base_id:
                    clinic.knowledge_base_id = knowledge_base_id
                    db.commit()
                    logger.info(f"Updated clinic {clinic_id} knowledge_base_id to {knowledge_base_id}")

                logger.info(f"Successfully created knowledge base from text for clinic {clinic_id}. Response: {response_data}")
                return {
                    "document_id": document_id,
                    "clinic_id": clinic_id,
                    "knowledge_base_id": knowledge_base_id,
                    "agent_id": clinic.elevenlabs_agent_id,
                    "status": "uploaded"
                }
            else:
                logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating knowledge base from text for clinic {clinic_id}: {str(e)}")
            return None

    async def _ensure_agent_knowledge_base(self, agent_id: str) -> Optional[str]:
        """
        Ensure the agent has a knowledge base configured
        
        Args:
            agent_id: ElevenLabs agent ID
            
        Returns:
            Knowledge base ID or None if failed
        """
        try:
            # First, try to get the agent's current configuration
            response = requests.get(
                f"{self.base_url}/convai/agents/{agent_id}",
                headers={"xi-api-key": self.elevenlabs_api_key}
            )
            
            if response.status_code == 200:
                agent_data = response.json()
                # Check if agent already has knowledge base configured
                if agent_data.get('knowledge_base_id'):
                    return agent_data['knowledge_base_id']
            
            # If no knowledge base exists, we'll create one when we upload the first file
            # The knowledge base is created automatically when uploading files
            logger.info(f"No existing knowledge base found for agent {agent_id}, will create one with first file upload")
            return None
                
        except Exception as e:
            logger.error(f"Error checking agent knowledge base: {str(e)}")
            return None

    async def _assign_knowledge_base_to_agent(self, agent_id: str, knowledge_base_id: str) -> bool:
        """
        Assign a knowledge base to an agent using the correct ElevenLabs API structure
        
        Args:
            agent_id: ElevenLabs agent ID
            knowledge_base_id: ElevenLabs knowledge base ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            headers = {
                "Accept": "application/json",
                "xi-api-key": self.elevenlabs_api_key,
                "Content-Type": "application/json"
            }
            
            # Get current agent configuration
            get_response = requests.get(
                f"{self.base_url}/convai/agents/{agent_id}",
                headers=headers
            )
            
            if get_response.status_code != 200:
                logger.error(f"Failed to get agent configuration: {get_response.status_code} - {get_response.text}")
                return False
            
            agent_config = get_response.json()
            conversation_config = agent_config.get("conversation_config", {})
            
            # Ensure the agent.prompt structure exists
            if "agent" not in conversation_config:
                conversation_config["agent"] = {}
            if "prompt" not in conversation_config["agent"]:
                conversation_config["agent"]["prompt"] = {}
            
            # Add the knowledge base to the agent's prompt configuration
            # According to ElevenLabs API, knowledge_base should be an array of objects
            knowledge_base_config = {
                "type": "file",
                "name": f"clinic_knowledge_base_{knowledge_base_id}",
                "id": knowledge_base_id,
                "usage_mode": "prompt"
            }
            
            # Initialize knowledge_base array if it doesn't exist
            if "knowledge_base" not in conversation_config["agent"]["prompt"]:
                conversation_config["agent"]["prompt"]["knowledge_base"] = []
            
            # Check if this knowledge base is already assigned
            existing_kb_ids = [kb.get("id") for kb in conversation_config["agent"]["prompt"]["knowledge_base"]]
            if knowledge_base_id not in existing_kb_ids:
                conversation_config["agent"]["prompt"]["knowledge_base"].append(knowledge_base_config)
            
            # Update the agent with the new configuration
            update_data = {
                "conversation_config": conversation_config
            }
            
            update_response = requests.patch(
                f"{self.base_url}/convai/agents/{agent_id}",
                headers=headers,
                json=update_data
            )
            
            if update_response.status_code in [200, 201]:
                logger.info(f"Successfully assigned knowledge base {knowledge_base_id} to agent {agent_id}")
                return True
            else:
                logger.error(f"Failed to assign knowledge base to agent: {update_response.status_code} - {update_response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error assigning knowledge base to agent: {str(e)}")
            return False

    async def _get_elevenlabs_phone_id(self, phone_number: str) -> Optional[str]:
        """
        Get the ElevenLabs phone number ID for a given phone number
        
        Args:
            phone_number: The phone number to look up
            
        Returns:
            ElevenLabs phone number ID or None if not found
        """
        try:
            if not self.client:
                logger.error("ElevenLabs client not initialized")
                return None
            
            # List all phone numbers in ElevenLabs using the SDK
            phone_numbers = self.client.conversational_ai.phone_numbers.list()
            
            # Find the phone number that matches
            for phone in phone_numbers:
                if phone.phone_number == phone_number:
                    return phone.phone_number_id
            
            logger.warning(f"Phone number {phone_number} not found in ElevenLabs phone numbers")
            return None
                
        except Exception as e:
            logger.error(f"Error getting ElevenLabs phone ID for {phone_number}: {str(e)}")
            return None

    async def import_phone_number_to_elevenlabs(
        self, 
        phone_number: str, 
        label: str, 
        twilio_sid: str, 
        twilio_token: str
    ) -> Optional[str]:
        """
        Import a Twilio phone number to ElevenLabs
        
        Args:
            phone_number: The phone number to import
            label: Label for the phone number
            twilio_sid: Twilio Account SID
            twilio_token: Twilio Auth Token
            
        Returns:
            ElevenLabs phone number ID or None if failed
        """
        try:
            if not self.client:
                logger.error("ElevenLabs client not initialized")
                return None
            
            # Import the phone number using the SDK
            from elevenlabs.conversational_ai.phone_numbers import PhoneNumbersCreateRequestBody_Twilio
            
            phone_response = self.client.conversational_ai.phone_numbers.create(
                request=PhoneNumbersCreateRequestBody_Twilio(
                    phone_number=phone_number,
                    label=label,
                    sid=twilio_sid,
                    token=twilio_token,
                )
            )
            
            logger.info(f"Successfully imported phone number {phone_number} to ElevenLabs")
            return phone_response.phone_number_id
            
        except Exception as e:
            logger.error(f"Error importing phone number {phone_number} to ElevenLabs: {str(e)}")
            return None

    async def link_phone_to_agent(self, agent_id: str, phone_number: str) -> bool:
        """
        Link a phone number to an agent
        
        Args:
            agent_id: ElevenLabs agent ID
            phone_number: Phone number to link
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # First, get the ElevenLabs phone number ID
            phone_id = await self._get_elevenlabs_phone_id(phone_number)
            if not phone_id:
                logger.error(f"Cannot link phone {phone_number} to agent {agent_id}: phone not found in ElevenLabs")
                return False
            
            # Update the agent to use this phone number using direct API call
            # The SDK doesn't support phone_number_id parameter, so we use direct API
            headers = {
                "Accept": "application/json",
                "xi-api-key": self.elevenlabs_api_key,
                "Content-Type": "application/json"
            }
            
            # Get current agent configuration
            get_response = requests.get(
                f"{self.base_url}/convai/agents/{agent_id}",
                headers=headers
            )
            
            if get_response.status_code != 200:
                logger.error(f"Failed to get agent {agent_id} configuration: {get_response.status_code}")
                return False
            
            agent_config = get_response.json()
            
            # Update the agent configuration to include the phone number
            update_data = {
                "conversation_config": agent_config.get("conversation_config", {}),
                "phone_number_id": phone_id
            }
            
            # Update the agent
            update_response = requests.patch(
                f"{self.base_url}/convai/agents/{agent_id}",
                headers=headers,
                json=update_data
            )
            
            if update_response.status_code in [200, 201]:
                logger.info(f"Successfully linked phone {phone_number} (ID: {phone_id}) to agent {agent_id}")
                return True
            else:
                logger.error(f"Failed to link phone to agent. Status: {update_response.status_code}, Response: {update_response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error linking phone {phone_number} to agent {agent_id}: {str(e)}")
            return False

    def assign_phone_to_agent(self, agent_id: str, phone_number_id: str) -> bool:
        """
        Assign a phone number to an agent in ElevenLabs.
        """
        headers = {
            "Accept": "application/json",
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        data = {
            "agent_id": agent_id
        }
        response = requests.patch(
            f"{self.base_url}/convai/phone-numbers/{phone_number_id}",
            headers=headers,
            json=data
        )
        if response.status_code in [200, 201]:
            logger.info(f"Successfully assigned phone number {phone_number_id} to agent {agent_id}")
            return True
        else:
            logger.error(f"Failed to assign phone number. Status: {response.status_code}, Response: {response.text}")
            return False

    def update_agent_configuration(
        self, 
        db: Session, 
        clinic_id: int, 
        agent_name: str = None,
        ai_voice_id: str = None,
        ai_personality: str = None,
        greeting_message: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update agent configuration for a clinic
        
        Args:
            db: Database session
            clinic_id: ID of the clinic
            agent_name: New agent name
            ai_voice_id: New AI voice ID
            ai_personality: New AI personality
            greeting_message: New greeting message
            
        Returns:
            Updated agent information or None if failed
        """
        try:
            clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
            if not clinic:
                logger.error(f"Clinic {clinic_id} not found")
                return None
            
            # Update clinic fields
            if agent_name is not None:
                clinic.elevenlabs_agent_name = agent_name
            if ai_voice_id is not None:
                clinic.ai_voice_id = ai_voice_id
            if ai_personality is not None:
                clinic.ai_personality = ai_personality
            if greeting_message is not None:
                clinic.greeting_message = greeting_message
            
            db.commit()
            
            logger.info(f"Successfully updated agent configuration for clinic {clinic_id}")
            
            return self.get_clinic_agent_info(db, clinic_id)
            
        except Exception as e:
            logger.error(f"Error updating agent configuration for clinic {clinic_id}: {str(e)}")
            db.rollback()
            return None

    def update_agent_full_config(self, agent_id: str, config: dict) -> dict:
        """
        Fully update an agent's configuration using the ElevenLabs PATCH API.
        Args:
            agent_id: The ElevenLabs agent ID
            config: The full config dict to PATCH (can include any valid agent fields)
        Returns:
            The updated agent data (dict) or error info
        """
        try:
            response = requests.patch(
                f"{self.base_url}/convai/agents/{agent_id}",
                headers=self.headers,
                json=config
            )
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Failed to update agent config: {response.status_code} - {response.text}")
                return {"error": response.text, "status_code": response.status_code}
        except Exception as e:
            logger.error(f"Exception updating agent config: {str(e)}")
            return {"error": str(e)}

    def update_agent_data_collection(self, agent_id: str, data_collection_config: dict) -> dict:
        """
        Update data collection settings (analytics, transcript, etc.) for an agent.
        Args:
            agent_id: The ElevenLabs agent ID
            data_collection_config: Dict for the 'data_collection' field
        Returns:
            The updated agent data (dict) or error info
        """
        try:
            patch_data = {"data_collection": data_collection_config}
            response = requests.patch(
                f"{self.base_url}/convai/agents/{agent_id}",
                headers=self.headers,
                json=patch_data
            )
            if response.status_code in [200, 201]:
                return response.json()
            else:
                logger.error(f"Failed to update agent data collection: {response.status_code} - {response.text}")
                return {"error": response.text, "status_code": response.status_code}
        except Exception as e:
            logger.error(f"Exception updating agent data collection: {str(e)}")
            return {"error": str(e)}


# Create service instance
agent_setup_service = AgentSetupService() 