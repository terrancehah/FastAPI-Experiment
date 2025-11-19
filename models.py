from pydantic import BaseModel
from typing import Optional

# ----------------------
# Pydantic Model
# ----------------------
class CustomerInfo(BaseModel):
    name: str
    gender: str
    occupation: str
    occupation_field: str
    income: float
    age: int
    insurance_type: Optional[str] = None
    insurance_coverage: Optional[float] = None

