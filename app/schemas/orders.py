from pydantic import BaseModel, Field
from typing import Literal, Optional


class CreateOrderRequest(BaseModel):
    item_id: int | None = Field(default=None, description="ID товара, для доната можно передать null")
    payment_method: Literal[36, 44] | None = Field(default=None, description="36=Card RF, 44=SBP QR; опционально для YooKassa")
    tg_id: int | None = None
    email: str | None = None
    ip: str | None = None
    amount_minor: int | None = Field(default=None, description="Сумма в копейках для доната/override")
    

class CreateOrderResponse(BaseModel):
    order_id: int | None = None
    payment_url: Optional[str] = None  # <-- ИСПРАВЛЕНО: теперь может быть None
