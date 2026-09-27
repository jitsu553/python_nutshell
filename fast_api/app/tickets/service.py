from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.models import User
from .models import Ticket
from .schemas import CreateTicketRequest


class TicketService:
    def __init__(self, db: Session):
        self.db = db

    def create_ticket(self, user: User, body: CreateTicketRequest) -> Ticket:
        ticket = Ticket(user_id=user.id, subject=body.subject, description=body.description)
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def list_tickets(self, user: User) -> list[Ticket]:
        return (
            self.db.query(Ticket)
            .filter(Ticket.user_id == user.id)
            .order_by(Ticket.created_at.desc())
            .all()
        )

    def get_ticket_or_404(self, ticket_id: int, user: User) -> Ticket:
        ticket = (
            self.db.query(Ticket)
            .filter(Ticket.id == ticket_id, Ticket.user_id == user.id)
            .first()
        )
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket

    def update_status(self, ticket_id: int, user: User, status: str) -> Ticket:
        ticket = self.get_ticket_or_404(ticket_id, user)
        ticket.status = status
        self.db.commit()
        self.db.refresh(ticket)
        return ticket