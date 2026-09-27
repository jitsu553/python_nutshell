from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db, get_current_user
from app.auth.models import User
from .schemas import CreateTicketRequest, TicketResponse, UpdateTicketStatusRequest
from .service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketResponse)
def create_ticket(
    body: CreateTicketRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketResponse:
    return TicketService(db).create_ticket(current_user, body)


@router.get("", response_model=list[TicketResponse])
def list_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TicketService(db).list_tickets(current_user)


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketResponse:
    return TicketService(db).get_ticket_or_404(ticket_id, current_user)


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: int,
    body: UpdateTicketStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TicketResponse:
    return TicketService(db).update_status(ticket_id, current_user, body.status)