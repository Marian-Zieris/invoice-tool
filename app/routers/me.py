from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import get_current_customer
from app.models import Customer
from app.utils import api_success

router = APIRouter(prefix="/me", tags=["me"])


class CategoriesUpdate(BaseModel):
    categories: List[str] = Field(min_length=1)


def _profile_payload(customer: Customer) -> dict:
    return {
        "id": customer.id,
        "email": customer.email,
        "category_rules": customer.category_rules,
    }


@router.get("")
def get_my_profile(current_customer: Customer = Depends(get_current_customer)):
    """Vlastní profil přihlášeného zákazníka - na rozdíl od /customers je bez admin klíče."""
    return api_success(_profile_payload(current_customer), "Profile fetched successfully.")


@router.patch("/categories")
def update_my_categories(
    payload: CategoriesUpdate,
    db: Session = Depends(get_db),
    current_customer: Customer = Depends(get_current_customer),
):
    """Zákazník si sám spravuje vlastní kategorie položek - je to jeho vlastní účetní třídění,
    ne něco, co by za něj měl uhodnout admin při zakládání účtu."""
    current_customer.category_rules = {**current_customer.category_rules, "categories": payload.categories}
    db.commit()
    db.refresh(current_customer)
    return api_success(_profile_payload(current_customer), "Categories updated successfully.")
