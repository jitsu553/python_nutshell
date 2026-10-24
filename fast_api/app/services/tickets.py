from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import User
from app.models.tickets import Ticket
from app.schemas.tickets import CreateTicketRequest


class TicketService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_ticket(self, user: User, body: CreateTicketRequest) -> Ticket:
        ticket = Ticket(user_id=user.id, customer_id=body.customer_id, subject=body.subject, description=body.description)
        self.db.add(ticket)
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket

    async def list_tickets(self, user: User) -> list[Ticket]:
        result = await self.db.scalars(
            select(Ticket).where(Ticket.user_id == user.id).order_by(Ticket.created_at.desc())
        )
        return list(result)

    async def get_ticket_or_404(self, ticket_id: int, user: User) -> Ticket:
        ticket = await self.db.scalar(
            select(Ticket).where(Ticket.id == ticket_id, Ticket.user_id == user.id)
        )
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket

    async def update_status(self, ticket_id: int, user: User, status: str) -> Ticket:
        ticket = await self.get_ticket_or_404(ticket_id, user)
        ticket.status = status
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket

    async def list_for_customer(self, customer_id: int, limit: int = 3, status: str | None = None) -> list[Ticket]:
        query = select(Ticket).where(Ticket.customer_id == customer_id)
        if status:
            query = query.where(Ticket.status == status)
        result = await self.db.scalars(query.order_by(Ticket.created_at.desc()).limit(limit))
        return list(result)

    async def get_any(self, ticket_id: int) -> Ticket | None:
        return await self.db.get(Ticket, ticket_id)

    async def set_status_any(self, ticket_id: int, status: str) -> Ticket | None:
        ticket = await self.db.get(Ticket, ticket_id)
        if ticket is None:
            return None
        ticket.status = status
        await self.db.commit()
        await self.db.refresh(ticket)
        return ticket
