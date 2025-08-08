from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


class ChatRequest(BaseModel):
    name: str
    message: str
    session_id: Optional[str] = None

class User(BaseModel):
    user_id: str
    name: str
    age: Optional[int] = None
    hmo_id: Optional[str] = None
    phone: Optional[str] = None # add validator
    alt_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    gender: Optional[str] = None
    landmark: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    lga: Optional[str] = None

class OrderItemRequest(BaseModel):
    name: str = Field(..., description="Name of the product or drug")
    quantity: int = Field(..., description="Quantity of the product or drug")
    dosage: str = Field(..., description="Dosage of the product or drug, e.g., '500mg'")
    form: str = Field(..., description="Form of the product or drug, e.g., 'tablet', 'syrup', 'ointment'")
    note: Optional[str] = Field(None, description="Additional notes or instructions for the product or drug")

class OrderRequest(BaseModel):
    customer_name: str = Field(..., description="Name of the customer")
    customer_age: int = Field(..., description="Age of the customer")
    customer_gender: str = Field(..., description="Gender of the customer")
    customer_hmo_id: str = Field(..., description="HMO ID of the customer")
    customer_phone: str = Field(..., description="Phone number of the customer")
    customer_email: EmailStr = Field(..., description="Email of the customer")
    customer_address: str = Field(..., description="Address of the customer")
    customer_alt_phone: Optional[str]  = Field(None, description="Alternative phone number of the customer")
    city: str = Field(..., description="City of the customer")
    state: str = Field(..., description="State of the customer")
    fulfilment_mode: str = Field(..., description="Mode of order fulfilment, e.g., 'delivery' or 'pickup'")
    order_items: List[OrderItemRequest] = Field(..., description="List of items in the order, each with name, quantity, dosage, and form")

class ProductQuery(BaseModel):
    user_query: str = Field(..., description="Full user query")
    product_name: Optional[str] = Field(None, description="Name of the drug or product, if applicable.")
    symptom: Optional[str] = Field(None, description="Symptom or condition, if applicable.")
    additional_notes: str = Field(None, description="Extra details or context for the query.")