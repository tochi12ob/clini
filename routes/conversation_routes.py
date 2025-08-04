from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from services.conversation_service import conversation_service
from schemas import ConversationDetail, ConversationListResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/conversations",
    tags=["conversations"]
)

@router.get("/agent/{agent_id}", response_model=ConversationListResponse)
async def list_agent_conversations(
    agent_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Items per page")
):
    """
    List all conversations for a specific agent.
    
    Note: The ElevenLabs API doesn't provide a direct endpoint to list conversations by agent,
    so this endpoint returns a placeholder response. You'll need to track conversation IDs
    separately in your application.
    """
    try:
        result = await conversation_service.get_conversations_by_agent(
            agent_id=agent_id,
            limit=size,
            page=page
        )
        return result
    except Exception as e:
        logger.error(f"Error listing conversations for agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_details(conversation_id: str):
    """
    Get detailed information about a specific conversation including transcript,
    metadata, and analysis.
    """
    try:
        conversation = await conversation_service.get_conversation_details(conversation_id)
        return conversation
    except Exception as e:
        logger.error(f"Error fetching conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}/transcript")
async def get_conversation_transcript(conversation_id: str, format: str = Query("text", enum=["text", "json"])):
    """
    Get the transcript of a conversation in either text or JSON format.
    """
    try:
        conversation = await conversation_service.get_conversation_details(conversation_id)
        
        if format == "text":
            # Format transcript as readable text
            transcript_text = conversation_service.format_transcript(conversation.get("transcript", []))
            return {"conversation_id": conversation_id, "transcript": transcript_text}
        else:
            # Return raw transcript data
            return {
                "conversation_id": conversation_id,
                "transcript": conversation.get("transcript", [])
            }
    except Exception as e:
        logger.error(f"Error fetching transcript for conversation {conversation_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agent/{agent_id}/stats")
async def get_agent_conversation_stats(agent_id: str):
    """
    Get conversation statistics for an agent.
    
    Note: This is a placeholder endpoint as ElevenLabs doesn't provide
    conversation statistics directly.
    """
    try:
        # Get agent details first
        agent = await conversation_service.get_agent_details(agent_id)
        
        return {
            "agent_id": agent_id,
            "agent_name": agent.get("name", "Unknown"),
            "stats": {
                "total_conversations": 0,
                "average_duration": 0,
                "total_duration": 0,
                "message": "Statistics not available from ElevenLabs API"
            }
        }
    except Exception as e:
        logger.error(f"Error fetching stats for agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))