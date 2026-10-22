from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Customer
from .schemas import CreateCustomerRequest


class CustomerService:
    def __init__(self, db: Session):
        self.db = db

    def create_customer(self, body: CreateCustomerRequest) -> Customer:
        if self.db.query(Customer).filter(Customer.email == body.email).first():
            raise HTTPException(status_code=409, detail="Customer email already exists")
        customer = Customer(name=body.name, email=body.email, plan=body.plan)
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def get_customer_or_404(self, customer_id: int) -> Customer:
        customer = self.db.get(Customer, customer_id)
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer

    def search(self, query: str, limit: int = 5) -> list[Customer]:
        pattern = f"%{query.strip()}%"
        return (
            self.db.query(Customer)
            .filter(Customer.name.ilike(pattern) | Customer.email.ilike(pattern))
            .order_by(Customer.name)
            .limit(limit)
            .all()
        )