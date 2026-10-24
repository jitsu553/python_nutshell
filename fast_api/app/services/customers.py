from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customers import Customer
from app.schemas.customers import CreateCustomerRequest


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_customer(self, body: CreateCustomerRequest) -> Customer:
        if await self.db.scalar(select(Customer).where(Customer.email == body.email)):
            raise HTTPException(status_code=409, detail="Customer email already exists")
        customer = Customer(name=body.name, email=body.email, plan=body.plan)
        self.db.add(customer)
        await self.db.commit()
        await self.db.refresh(customer)
        return customer

    async def get_customer_or_404(self, customer_id: UUID) -> Customer:
        customer = await self.db.get(Customer, customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer

    async def search(self, query: str, limit: int = 5) -> list[Customer]:
        pattern = f"%{query.strip()}%"
        result = await self.db.scalars(
            select(Customer)
            .where(Customer.name.ilike(pattern) | Customer.email.ilike(pattern))
            .order_by(Customer.name)
            .limit(limit)
        )
        return list(result)