from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db_session
from app.models import Item, Order, PaymentMethod, User, OrderStatus
from app.schemas.orders import CreateOrderRequest, CreateOrderResponse
from app.services.yookassa import YooKassaClient
from app.config import settings
from app.utils.texts import load_texts

router = APIRouter(prefix="/orders", tags=["orders"]) 


@router.post("/", response_model=CreateOrderResponse)
async def create_order(payload: CreateOrderRequest, db: AsyncSession = Depends(get_db_session)) -> CreateOrderResponse:
    item = None
    if payload.item_id is not None and payload.item_id >= 0:
        item = (await db.execute(select(Item).where(Item.id == payload.item_id))).scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="item not found")

    email = payload.email or (f"{payload.tg_id}@{settings.email_domain}" if payload.tg_id else None)
    if not email:
        raise HTTPException(status_code=400, detail="email or tg_id required")

    # Привяжем заказ к пользователю, если такой TG есть в базе
    user_id = None
    if payload.tg_id is not None:
        existing_user = (await db.execute(select(User).where(User.tg_id == int(payload.tg_id)))).scalar_one_or_none()
        if existing_user:
            user_id = existing_user.id

    is_donation = item is None
    if is_donation:
        # Донаты — не записываем в таблицу orders
        amount_minor = payload.amount_minor or 0
        metadata = {"donation": True, "buyer_tg_id": payload.tg_id}
        templates = load_texts().get("payment", {}).get("description_templates", {})
        description = (templates.get("donation") or "Донат от {buyer}").format(buyer=payload.tg_id or "-")
    else:
        # Create DB order для покупок
        order = Order(
            user_id=user_id,
            item_id=item.id if item else None,
            amount_minor=(payload.amount_minor if payload.amount_minor else (item.price_minor if item else 0)),
            currency="RUB",
            payment_method=PaymentMethod(payload.payment_method) if payload.payment_method is not None else PaymentMethod.CARD_RF,
            status=OrderStatus.CREATED,
            buyer_tg_id=str(payload.tg_id) if payload.tg_id else None,
        )
        
        db.add(order)
        await db.flush()
        amount_minor = order.amount_minor
        metadata = {"paymentId": str(order.id)}
        templates = load_texts().get("payment", {}).get("description_templates", {})
        key = "service" if item.item_type.value == "service" else "digital"
        description = (templates.get(key) or "Оплата: {title} | Заказ {order_id}").format(title=item.title, order_id=order.id)

    # ====== НАЧАЛО ИЗМЕНЕНИЙ ======
    payment_amount_minor = amount_minor if 'amount_minor' in locals() else (order.amount_minor if 'order' in locals() else 0)
    payment_id_str = (str(order.id) if not is_donation else f"donation:{payload.tg_id or 'anon'}")

    # Если сумма 0 — не идем в ЮKassa, а сразу выдаем товар
    if payment_amount_minor == 0:
        if is_donation:
            raise HTTPException(status_code=400, detail="Сумма доната должна быть больше 0")
        
        logger.bind(event="order.free").info(f"Оформление бесплатного заказа {order.id} для item_id={item.id}")
        
        # Обновляем статус заказа. ВАЖНО: Убедитесь, что в вашей модели OrderStatus есть статус PAID.
        # Если он называется иначе (например, COMPLETED или SUCCESS), замените здесь.
        order.status = OrderStatus.PAID 
        await db.commit()
        
        # Возвращаем ответ без ссылки на оплату. 
        # Бот должен проверить payment_url is None и сразу выдать файл пользователю!
        return CreateOrderResponse(order_id=order.id, payment_url=None)
    # ====== КОНЕЦ ИЗМЕНЕНИЙ ======

    logger.bind(event="yk.create_payment.request").info(
        "Готовим платеж в ЮKassa: сумма={amount} ₽",
        amount=f"{payment_amount_minor/100:.2f}",
    )

    client = YooKassaClient()
    try:
        # Маппинг способов оплаты: 36=карта, 44=СБП
        pm_type = None
        if payload.payment_method == PaymentMethod.CARD_RF.value:
            pm_type = "bank_card"
        elif payload.payment_method == PaymentMethod.SBP_QR.value:
            pm_type = "sbp"

        # Для идемпотентности используем UUID, чтобы избежать коллизий при повторных попытках
        import uuid
        idem = str(uuid.uuid4())
        data = await client.create_payment(
            amount_minor=payment_amount_minor,
            description=description,
            payment_id=payment_id_str,
            payment_method_type=pm_type,
            metadata=metadata,
            customer_email=email,
            idempotence_key=idem,
        )
    except Exception as e:
        logger.bind(event="yk.create_payment.error", error=str(e)).error("Ошибка запроса к ЮKassa")
        # Меняем 502 на 400, так как проблема обычно в неверных данных запроса, а не в сервере ЮKassa
        raise HTTPException(status_code=400, detail=f"Ошибка платежной системы: {str(e)}")
    try:
        confirmation = (data or {}).get("confirmation", {})
        payment_url = confirmation.get("confirmation_url")
        logger.bind(event="yk.create_payment.response").info("Ссылка на оплату получена")
        if not payment_url:
            raise HTTPException(status_code=400, detail="YK did not return confirmation_url")
        if not is_donation:
            # Сохраняем id платежа и ссылку для покупок
            try:
                order.fk_order_id = data.get("id")  # type: ignore[arg-type]
            except Exception:
                pass
            order.fk_payment_url = payment_url
            order.status = OrderStatus.PENDING
            await db.commit()
        # Донаты: уведомление админу отправляется ТОЛЬКО по вебхуку YooKassa
        return CreateOrderResponse(order_id=(None if is_donation else order.id), payment_url=payment_url)
    finally:
        await client.close()
