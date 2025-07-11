from fastapi import APIRouter, Request, HTTPException
import logging
from integration import athena_health_client
from integration import webhook_tools  # Import the static endpoints router

router = APIRouter(prefix="/api/tools", tags=["webhook-tools"])
logger = logging.getLogger(__name__)

# Include all static endpoints from integration/webhook_tools.py
router.include_router(webhook_tools.router)

@router.api_route("/athena/{clinic_id}/{function_name}", methods=["GET", "POST"])
async def athena_dynamic_webhook(clinic_id: str, function_name: str, request: Request):
    """
    Dynamic Athena webhook endpoint. Accepts both GET and POST for compatibility, but POST is preferred.
    """
    if request.method == "GET":
        return {"message": "GET received. This endpoint is intended for POST with a JSON body. Please use POST for production webhooks.", "clinic_id": clinic_id, "function_name": function_name}
    try:
        body = await request.json()
        func = getattr(athena_health_client, function_name, None)
        if not func:
            raise HTTPException(status_code=404, detail=f"Athena function '{function_name}' not found.")
        # Support both sync and async Athena functions
        if callable(func):
            if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # async function
                result = await func(**body)
            else:
                result = func(**body)
            return result
        else:
            raise HTTPException(status_code=500, detail=f"Attribute '{function_name}' is not callable.")
    except Exception as e:
        logger.exception("Error in Athena dynamic webhook")
        raise HTTPException(status_code=500, detail=str(e))

@router.api_route("/epic/{clinic_id}/webhook", methods=["GET", "POST"])
async def epic_dynamic_webhook(clinic_id: str, request: Request):
    """
    Dynamic Epic webhook endpoint. Accepts both GET and POST for compatibility, but POST is preferred.
    """
    if request.method == "GET":
        return {"message": "GET received. This endpoint is intended for POST with a JSON body. Please use POST for production webhooks.", "clinic_id": clinic_id}
    try:
        body = await request.json()
        # TODO: Dispatch to the correct Epic function based on body['resource'] and body['action']
        return {"message": "Epic webhook received", "clinic_id": clinic_id, "body": body}
    except Exception as e:
        logger.exception("Error in Epic dynamic webhook")
        raise HTTPException(status_code=500, detail=str(e)) 