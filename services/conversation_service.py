import httpx
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from models import Call, Clinic, CallStatus  # Added CallStatus import
from sqlalchemy import desc
from database import db_manager  # Import your database manager

load_dotenv()

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1/convai/conversations"
        self.agents_base_url = "https://api.elevenlabs.io/v1/convai/agents"
        self.headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def get_conversations_by_agent(self, agent_id: str, limit: int = 50, page: int = 1, cursor: str = None) -> Dict[str, Any]:
        """
        Get all conversations for a specific agent from ElevenLabs API
        """
        try:
            logger.info(f"Fetching conversations for agent {agent_id} with params: page_size={limit}")
            
            # Build query parameters
            params = {
                "agent_id": agent_id,
                "page_size": min(limit, 100),  # ElevenLabs max is 100
                "summary_mode": "include"  # Include transcript summaries
            }
            
            if cursor:
                params["cursor"] = cursor
            
            # Fetch conversations from ElevenLabs
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                elevenlabs_data = response.json()
            
            logger.info(f"ElevenLabs returned {len(elevenlabs_data.get('conversations', []))} conversations")
            
            conversations = elevenlabs_data.get("conversations", [])
            
            # Enrich conversations with data from our database
            enriched_conversations = []
            
            try:
                with db_manager.create_session_context() as session:
                    # Find the clinic with this agent_id for context
                    clinic = session.query(Clinic).filter(Clinic.elevenlabs_agent_id == agent_id).first()
                    
                    for conversation in conversations:
                        try:
                            conversation_id = conversation.get("conversation_id")
                            
                            # Try to find matching call in our database
                            call = None
                            if conversation_id:
                                call = session.query(Call).filter(Call.conversation_id == conversation_id).first()
                            
                            # Add database info if available
                            if call:
                                conversation['call_id'] = call.id
                                conversation['caller_phone'] = call.from_number
                                conversation['call_type'] = call.call_type.value if call.call_type else None
                                conversation['db_created_at'] = call.created_at.isoformat() if call.created_at else None
                                conversation['patient_id'] = call.patient_id
                                conversation['appointment_id'] = call.appointment_id
                            
                            # Add clinic info
                            if clinic:
                                conversation['clinic_name'] = clinic.name
                                conversation['clinic_id'] = clinic.id
                            
                            enriched_conversations.append(conversation)
                            
                        except Exception as conv_error:
                            logger.warning(f"Error enriching conversation {conversation.get('conversation_id')}: {str(conv_error)}")
                            # Add the conversation without enrichment
                            enriched_conversations.append(conversation)
                            
            except Exception as db_error:
                logger.warning(f"Database enrichment failed: {str(db_error)}")
                # Return conversations without database enrichment
                enriched_conversations = conversations
            
            logger.info(f"Successfully enriched {len(enriched_conversations)} conversations")
            
            return {
                "conversations": enriched_conversations,
                "total": len(enriched_conversations),  # ElevenLabs doesn't provide total count
                "has_more": elevenlabs_data.get("has_more", False),
                "next_cursor": elevenlabs_data.get("next_cursor"),
                "page": page,
                "size": limit,
                "agent_id": agent_id
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching conversations for agent {agent_id}: {e.response.status_code} - {e.response.text}")
            return {
                "conversations": [],
                "total": 0,
                "has_more": False,
                "next_cursor": None,
                "page": page,
                "size": limit,
                "agent_id": agent_id,
                "error": f"HTTP {e.response.status_code}: {e.response.text}"
            }
        except Exception as e:
            logger.error(f"Error fetching conversations for agent {agent_id}: {str(e)}")
            return {
                "conversations": [],
                "total": 0,
                "has_more": False,
                "next_cursor": None,
                "page": page,
                "size": limit,
                "agent_id": agent_id,
                "error": str(e)
            }
    
    async def get_conversation_details(self, conversation_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific conversation
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/{conversation_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching conversation {conversation_id}: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching conversation {conversation_id}: {str(e)}")
            raise
    
    async def get_conversations_by_agent_simple(self, agent_id: str, limit: int = 50, cursor: str = None) -> Dict[str, Any]:
        """
        Simple version without database enrichment for debugging
        """
        try:
            logger.info(f"Fetching conversations for agent {agent_id} (simple version)")
            
            params = {
                "agent_id": agent_id,
                "page_size": min(limit, 100),
                "summary_mode": "include"
            }
            
            if cursor:
                params["cursor"] = cursor
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    headers=self.headers,
                    params=params
                )
                response.raise_for_status()
                elevenlabs_data = response.json()
            
            logger.info(f"Successfully fetched {len(elevenlabs_data.get('conversations', []))} conversations")
            
            return {
                "conversations": elevenlabs_data.get("conversations", []),
                "has_more": elevenlabs_data.get("has_more", False),
                "next_cursor": elevenlabs_data.get("next_cursor"),
                "agent_id": agent_id
            }
            
        except Exception as e:
            logger.error(f"Error in simple fetch for agent {agent_id}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    async def get_conversations_by_agent_paginated(self, agent_id: str, cursor: str = None, page_size: int = 30) -> Dict[str, Any]:
        """
        Get conversations with cursor-based pagination (ElevenLabs native pagination)
        """
        return await self.get_conversations_by_agent(agent_id, limit=page_size, cursor=cursor)
    
    async def get_agent_details(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent details from ElevenLabs
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.agents_base_url}/{agent_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching agent {agent_id}: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching agent {agent_id}: {str(e)}")
            raise
    
    def format_transcript(self, transcript_data: List[Dict[str, Any]]) -> str:
        """
        Format transcript data into a readable string
        """
        formatted_lines = []
        for entry in transcript_data:
            role = entry.get("role", "unknown").upper()
            message = entry.get("message", "")
            time_in_call = entry.get("time_in_call_secs", 0)
            
            # Format time as mm:ss
            minutes = int(time_in_call // 60)
            seconds = int(time_in_call % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            formatted_lines.append(f"[{time_str}] {role}: {message}")
        
        return "\n".join(formatted_lines)
    
    def store_conversation_id(self, call_id: int, conversation_id: str) -> bool:
        """
        Store the ElevenLabs conversation ID for a call
        """
        try:
            with db_manager.create_session_context() as session:
                call = session.query(Call).filter(Call.id == call_id).first()
                if call:
                    call.conversation_id = conversation_id
                    # session.commit() is handled by the context manager
                    return True
                return False
        except Exception as e:
            logger.error(f"Error storing conversation ID: {str(e)}")
            return False
    
    async def sync_conversation_details(self, conversation_id: str, call_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Sync conversation details from ElevenLabs and optionally update our database
        """
        try:
            # Get conversation details from ElevenLabs
            conversation_data = await self.get_conversation_details(conversation_id)
            
            # If we don't have a call_id, try to find the call by conversation_id
            if not call_id:
                with db_manager.create_session_context() as session:
                    call = session.query(Call).filter(Call.conversation_id == conversation_id).first()
                    if call:
                        call_id = call.id
            
            # Update the call record if we have one
            if call_id:
                with db_manager.create_session_context() as session:
                    call = session.query(Call).filter(Call.id == call_id).first()
                    if call:
                        # Update transcript if available
                        if conversation_data.get("transcript"):
                            transcript_text = self.format_transcript(conversation_data["transcript"])
                            call.transcript = transcript_text
                        
                        # Update duration
                        if conversation_data.get("metadata", {}).get("call_duration_secs"):
                            call.duration_seconds = conversation_data["metadata"]["call_duration_secs"]
                        
                        # Update status
                        status_mapping = {
                            "done": CallStatus.COMPLETED,
                            "failed": CallStatus.FAILED,
                            "in-progress": CallStatus.IN_PROGRESS,
                            "processing": CallStatus.IN_PROGRESS
                        }
                        if conversation_data.get("status") in status_mapping:
                            call.status = status_mapping[conversation_data["status"]]
                        
                        # session.commit() is handled by the context manager
            
            return conversation_data
        except Exception as e:
            logger.error(f"Error syncing conversation {conversation_id}: {str(e)}")
            raise


# Create a singleton instance
conversation_service = ConversationService()