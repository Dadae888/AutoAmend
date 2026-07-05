from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from db import get_session
from mistral_client import MistralError, complete
from status import get_or_create_device

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class CompleteRequest(BaseModel):
    device_id: str
    system: str
    messages: list[ChatMessage]
    temperature: float = 0.3
    max_tokens: int = 700
    json_mode: bool = False
    billable: bool = True


@router.post("/api/llm/complete")
async def llm_complete(body: CompleteRequest, session: Session = Depends(get_session)) -> dict:
    device = get_or_create_device(session, body.device_id)

    if body.billable and not device.is_subscribed and device.free_used >= settings.free_quota:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "quota_exceeded",
                "free_used": device.free_used,
                "free_quota": settings.free_quota,
            },
        )

    try:
        content = await complete(
            system=body.system,
            messages=[m.model_dump() for m in body.messages],
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            json_mode=body.json_mode,
        )
    except MistralError as exc:
        raise HTTPException(status_code=502, detail=f"Mistral call failed: {exc}") from exc

    if body.billable and not device.is_subscribed:
        device.free_used += 1
        session.commit()

    return {
        "content": content,
        "free_used": device.free_used,
        "free_quota": settings.free_quota,
        "subscribed": device.is_subscribed,
    }
