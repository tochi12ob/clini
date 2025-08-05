"""
Admin routes for Clinic AI Assistant
Handles admin-only endpoints for managing clinics and their knowledge bases
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import logging

from database import get_db
from routes.auth import get_current_user
from models import Clinic
from services.agent_setup_service import agent_setup_service
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/clinics/knowledge-base")
async def get_all_clinics_knowledge_base(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db),
    include_documents: bool = Query(True, description="Include document details from ElevenLabs")
):
    """
    Get all clinics with their knowledge base information from ElevenLabs.
    Admin only endpoint.
    
    Returns:
        List of clinics with their knowledge base documents fetched directly from ElevenLabs API
    """
    # Check if user is admin
    if current_user.get("user_type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        # Get all clinics from database
        clinics = db.query(Clinic).filter(Clinic.is_active == True).all()
        
        results = []
        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        elevenlabs_base_url = "https://api.elevenlabs.io/v1"
        
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        
        for clinic in clinics:
            clinic_data = {
                "clinic_id": clinic.id,
                "clinic_name": clinic.name,
                "phone": clinic.phone,
                "agent_id": clinic.elevenlabs_agent_id,
                "knowledge_base_id": clinic.knowledge_base_id,
                "knowledge_base_documents": []
            }
            
            # If clinic has a knowledge base ID and we want to include documents
            if clinic.knowledge_base_id and include_documents:
                try:
                    # Fetch knowledge base documents from ElevenLabs
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"{elevenlabs_base_url}/convai/knowledge-base/{clinic.knowledge_base_id}",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            kb_data = response.json()
                            
                            # Get documents list if available
                            documents_response = await client.get(
                                f"{elevenlabs_base_url}/convai/knowledge-base/{clinic.knowledge_base_id}/documents",
                                headers=headers
                            )
                            
                            if documents_response.status_code == 200:
                                documents = documents_response.json()
                                clinic_data["knowledge_base_documents"] = documents
                            else:
                                clinic_data["knowledge_base_documents"] = []
                                clinic_data["documents_error"] = f"Failed to fetch documents: {documents_response.status_code}"
                            
                            # Add knowledge base metadata
                            clinic_data["knowledge_base_metadata"] = kb_data
                        else:
                            clinic_data["knowledge_base_error"] = f"Failed to fetch KB: {response.status_code}"
                            
                except Exception as e:
                    logger.error(f"Error fetching knowledge base for clinic {clinic.id}: {str(e)}")
                    clinic_data["knowledge_base_error"] = str(e)
            
            results.append(clinic_data)
        
        return {
            "total_clinics": len(results),
            "clinics": results
        }
        
    except Exception as e:
        logger.error(f"Error fetching clinics knowledge base data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch knowledge base data: {str(e)}"
        )


@router.get("/clinic/{clinic_id}/knowledge-base")
async def get_clinic_knowledge_base(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get knowledge base information for a specific clinic from ElevenLabs.
    Admin only endpoint.
    
    Args:
        clinic_id: ID of the clinic
        
    Returns:
        Clinic information with knowledge base documents from ElevenLabs
    """
    # Check if user is admin
    if current_user.get("user_type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Get clinic from database
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    result = {
        "clinic_id": clinic.id,
        "clinic_name": clinic.name,
        "phone": clinic.phone,
        "agent_id": clinic.elevenlabs_agent_id,
        "knowledge_base_id": clinic.knowledge_base_id,
        "knowledge_base_documents": [],
        "knowledge_base_metadata": None
    }
    
    if not clinic.knowledge_base_id:
        result["message"] = "Clinic has no knowledge base configured"
        return result
    
    try:
        elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        elevenlabs_base_url = "https://api.elevenlabs.io/v1"
        
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # Fetch knowledge base metadata
            kb_response = await client.get(
                f"{elevenlabs_base_url}/convai/knowledge-base/{clinic.knowledge_base_id}",
                headers=headers
            )
            
            if kb_response.status_code == 200:
                result["knowledge_base_metadata"] = kb_response.json()
            else:
                result["knowledge_base_error"] = f"Failed to fetch KB metadata: {kb_response.status_code}"
            
            # Fetch documents
            docs_response = await client.get(
                f"{elevenlabs_base_url}/convai/knowledge-base/{clinic.knowledge_base_id}/documents",
                headers=headers
            )
            
            if docs_response.status_code == 200:
                result["knowledge_base_documents"] = docs_response.json()
            else:
                result["documents_error"] = f"Failed to fetch documents: {docs_response.status_code}"
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching knowledge base for clinic {clinic_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch knowledge base data: {str(e)}"
        )


@router.get("/clinics/knowledge-base-details")
async def get_all_clinics_knowledge_base_details(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all clinics with their knowledge base details stored in the knowledge_base_id column.
    Admin only endpoint.
    
    Returns:
        List of clinics with their names and parsed knowledge base data
    """
    # Check if user is admin
    if current_user.get("user_type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        # Get all clinics from database
        clinics = db.query(Clinic).filter(Clinic.is_active == True).all()
        
        results = []
        
        for clinic in clinics:
            clinic_kb_data = {
                "clinic_id": clinic.id,
                "clinic_name": clinic.name,
                "phone": clinic.phone,
                "email": clinic.email,
                "agent_id": clinic.elevenlabs_agent_id,
                "knowledge_base_documents": []
            }
            
            # Parse the knowledge_base_id JSON data
            if clinic.knowledge_base_id:
                try:
                    import json
                    kb_data = json.loads(clinic.knowledge_base_id)
                    
                    # Check if it's a list of documents
                    if isinstance(kb_data, list):
                        clinic_kb_data["knowledge_base_documents"] = kb_data
                        clinic_kb_data["total_documents"] = len(kb_data)
                        
                        # Extract summary information
                        doc_summaries = []
                        for doc in kb_data:
                            if isinstance(doc, dict):
                                doc_summary = {
                                    "document_id": doc.get("document_id"),
                                    "file_name": doc.get("file_name"),
                                    "status": doc.get("status"),
                                    "knowledge_base_id": doc.get("knowledge_base_id"),
                                    "uploaded_at": doc.get("elevenlabs_response", {}).get("created_at") if doc.get("elevenlabs_response") else None
                                }
                                doc_summaries.append(doc_summary)
                        
                        clinic_kb_data["documents_summary"] = doc_summaries
                    else:
                        # Handle old format (single document)
                        clinic_kb_data["knowledge_base_documents"] = [kb_data] if kb_data else []
                        clinic_kb_data["total_documents"] = 1 if kb_data else 0
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse knowledge_base_id for clinic {clinic.id}: {str(e)}")
                    clinic_kb_data["parse_error"] = "Failed to parse knowledge base data"
                    clinic_kb_data["raw_data"] = clinic.knowledge_base_id[:100] + "..." if len(clinic.knowledge_base_id) > 100 else clinic.knowledge_base_id
            else:
                clinic_kb_data["total_documents"] = 0
                clinic_kb_data["message"] = "No knowledge base documents uploaded"
            
            results.append(clinic_kb_data)
        
        # Sort by clinic name
        results.sort(key=lambda x: x["clinic_name"])
        
        return {
            "total_clinics": len(results),
            "clinics_with_knowledge_base": len([c for c in results if c.get("total_documents", 0) > 0]),
            "total_documents": sum(c.get("total_documents", 0) for c in results),
            "clinics": results
        }
        
    except Exception as e:
        logger.error(f"Error fetching clinics knowledge base details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch knowledge base details: {str(e)}"
        )


@router.get("/clinic/{clinic_id}/knowledge-base-details")
async def get_clinic_knowledge_base_details(
    clinic_id: int,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed knowledge base information for a specific clinic from the knowledge_base_id column.
    Admin only endpoint.
    
    Args:
        clinic_id: ID of the clinic
        
    Returns:
        Clinic information with parsed knowledge base data
    """
    # Check if user is admin
    if current_user.get("user_type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Get clinic from database
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clinic not found"
        )
    
    result = {
        "clinic_id": clinic.id,
        "clinic_name": clinic.name,
        "phone": clinic.phone,
        "email": clinic.email,
        "agent_id": clinic.elevenlabs_agent_id,
        "agent_name": clinic.elevenlabs_agent_name,
        "knowledge_base_documents": [],
        "raw_knowledge_base_id": None
    }
    
    if clinic.knowledge_base_id:
        try:
            import json
            # Store raw data for debugging
            result["raw_knowledge_base_id"] = clinic.knowledge_base_id
            
            kb_data = json.loads(clinic.knowledge_base_id)
            
            if isinstance(kb_data, list):
                result["knowledge_base_documents"] = kb_data
                result["total_documents"] = len(kb_data)
                
                # Provide detailed analysis of each document
                for i, doc in enumerate(kb_data):
                    if isinstance(doc, dict):
                        # Extract ElevenLabs response details if available
                        if "elevenlabs_response" in doc and doc["elevenlabs_response"]:
                            el_response = doc["elevenlabs_response"]
                            doc["_parsed_details"] = {
                                "index": i,
                                "has_elevenlabs_response": True,
                                "elevenlabs_id": el_response.get("id"),
                                "created_at": el_response.get("created_at"),
                                "file_size": el_response.get("file_size"),
                                "mime_type": el_response.get("mime_type")
                            }
                        else:
                            doc["_parsed_details"] = {
                                "index": i,
                                "has_elevenlabs_response": False
                            }
            else:
                # Handle old format
                result["knowledge_base_documents"] = [kb_data] if kb_data else []
                result["total_documents"] = 1 if kb_data else 0
                result["format_type"] = "legacy_single_document"
                
        except json.JSONDecodeError as e:
            result["parse_error"] = f"Failed to parse JSON: {str(e)}"
            result["raw_data_preview"] = clinic.knowledge_base_id[:500] + "..." if len(clinic.knowledge_base_id) > 500 else clinic.knowledge_base_id
    else:
        result["total_documents"] = 0
        result["message"] = "No knowledge base documents uploaded"
    
    return result


@router.get("/knowledge-base/summary")
async def get_knowledge_base_summary(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a summary of knowledge base usage across all clinics.
    Admin only endpoint.
    
    Returns:
        Summary statistics of knowledge base usage
    """
    # Check if user is admin
    if current_user.get("user_type") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        # Get all clinics
        clinics = db.query(Clinic).filter(Clinic.is_active == True).all()
        
        total_clinics = len(clinics)
        clinics_with_kb = len([c for c in clinics if c.knowledge_base_id])
        clinics_with_agent = len([c for c in clinics if c.elevenlabs_agent_id])
        
        return {
            "total_clinics": total_clinics,
            "clinics_with_knowledge_base": clinics_with_kb,
            "clinics_with_agent": clinics_with_agent,
            "kb_adoption_rate": f"{(clinics_with_kb / total_clinics * 100):.1f}%" if total_clinics > 0 else "0%",
            "agent_adoption_rate": f"{(clinics_with_agent / total_clinics * 100):.1f}%" if total_clinics > 0 else "0%"
        }
        
    except Exception as e:
        logger.error(f"Error generating knowledge base summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )