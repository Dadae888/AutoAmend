from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_session
from ..models import Device

router = APIRouter()


def get_or_create_device(session: Session, device_id: str) -> Device:
    device = session.get(Device, device_id)
    if device is None:
        device = Device(device_id=device_id)
        session.add(device)
        session.commit()
        session.refresh(device)
    return device


@router.get("/api/status")
def get_status(device_id: str, session: Session = Depends(get_session)) -> dict:
    device = get_or_create_device(session, device_id)
    return {
        "free_used": device.free_used,
        "free_quota": settings.free_quota,
        "subscribed": device.is_subscribed,
    }
