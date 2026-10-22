from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db, get_current_user
from app.auth.models import User
from .schemas import CreateCustomerRequest, CustomerResponse
from .service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerResponse)
def create_customer(
    body: CreateCustomerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return CustomerService(db).create_customer(body)


@router.get("", response_model=list[CustomerResponse])
def search_customers(
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return CustomerService(db).search(q)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return CustomerService(db).get_customer_or_404(customer_id)