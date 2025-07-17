from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
from services.webhook_generator_service import WebhookGeneratorService
from routes.auth import get_current_user
from fastapi import Depends

router = APIRouter(prefix="/api/webhook-generator", tags=["webhook-generator"])

class EpicCredsModel(BaseModel):
    epic_client_id: str
    epic_client_secret: str
    epic_fhir_base_url: str
    epic_redirect_uri: Optional[str] = "http://localhost:8000/callback"

class AthenaCredsModel(BaseModel):
    athena_client_id: str
    athena_client_secret: str
    athena_api_base_url: str
    athena_practice_id: str

class WebhookGenRequest(BaseModel):
    clinic_id: str
    ehr: Literal["epic", "athena", "both"]
    epic_creds: Optional[EpicCredsModel] = None
    athena_creds: Optional[AthenaCredsModel] = None

class WebhookGenResponse(BaseModel):
    configs: List[dict]

@router.post("/generate", response_model=WebhookGenResponse)
def generate_webhook(request: WebhookGenRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("user_type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    service = WebhookGeneratorService()
    try:
        epic_creds_dict = request.epic_creds.dict() if request.epic_creds else None
        athena_creds_dict = request.athena_creds.dict() if request.athena_creds else None
        if request.ehr in ("epic", "both") and not epic_creds_dict:
            raise HTTPException(status_code=400, detail="Epic credentials are required for Epic webhook generation.")
        if request.ehr in ("athena", "both") and not athena_creds_dict:
            raise HTTPException(status_code=400, detail="Athena credentials are required for Athena webhook generation.")
        configs = service.generate_webhook_config(request.clinic_id, request.ehr, epic_creds=epic_creds_dict, athena_creds=athena_creds_dict)
        return {"configs": configs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 