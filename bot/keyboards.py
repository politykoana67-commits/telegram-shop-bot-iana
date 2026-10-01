from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.utils.texts import load_texts
from app.config import settings


def main_menu_kb(texts: dict, is_admin: bool = False) -> InlineKeyboardMarkup:
    b = texts["main_menu"]["buttons"]
    row1 = [InlineKeyboardButton(text=b["projects"], callback_data="menu:projects")]
    row2 = [InlineKeyboardButton(text=b["purchased"], callback_data="menu:purchased")]
    rows = [row1, row2]

    if settings.show_donate_button:
        rows.append([InlineKeyboardButton(text=b["donate"], callback_data="menu:donate")])

    if is_admin:
        rows.append([InlineKeyboardButton(text=b.get("admin", "Администрирование"), callback_data="menu:admin")])

    if settings.show_contact_button:
        if settings.admin_tg_username:
            rows.append([InlineKeyboardButton(text=b["contact"], url=f"https://t.me/{settings.admin_tg_username.lstrip('@')}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb(cb_data: str = "back:main") -> InlineKeyboardMarkup:
    texts = load_texts()
    kb = [[InlineKeyboardButton(text=texts["buttons"]["back"], callback_data=cb_data)]]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def items_list_kb(items: list, item_type: str, purchased_ids: set = None, page: int = 1, total: int = None, page_size: int = 5) -> InlineKeyboardMarkup:
    texts = load_texts()
    purchased_ids = purchased_ids or set()
    kb = []
    for item in items:
        title = item.title
        if item_type == "digital" and item.id in purchased_ids:
            title = f"{title} (✅ Уже куплено)"
        kb.append([InlineKeyboardButton(text=title, callback_data=f"item:{item.id}:{item_type}:{page}")])

    controls = [InlineKeyboardButton(text=texts["buttons"]["back"], callback_data="back:main")]
    if total is not None:
        if page > 1:
            controls.append(InlineKeyboardButton(text="◀️", callback_data=f"list:{item_type}:{page-1}"))
        if page * page_size < total:
            controls.append(InlineKeyboardButton(text="▶️", callback_data=f"list:{item_type}:{page+1}"))
    if controls:
        kb.append(controls)
    return InlineKeyboardMarkup(inline_keyboard=kb)


def item_card_kb(item_id: int, item_type: str, purchased: bool = False, from_purchased: bool = False, page: int = 1) -> InlineKeyboardMarkup:
    texts = load_texts()
    rows = []
    back_cb = "back:purchased" if from_purchased else f"back:list:{item_type}:{page}"
    if not purchased or item_type == "service":
        rows.append([InlineKeyboardButton(text=texts["buttons"].get("buy", "Купить"), callback_data=f"buy_one:{item_id}")])
    else:
        rows.append([InlineKeyboardButton(text="✅ Уже куплено", callback_data=back_cb)])
    rows.append([InlineKeyboardButton(text=texts["buttons"]["back"], callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_method_kb(item_id: int) -> InlineKeyboardMarkup:
    texts = load_texts()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"buy_direct:{item_id}")],
        [InlineKeyboardButton(text=texts["buttons"]["back"], callback_data="back:main")]
    ])


def main_menu_only_kb() -> InlineKeyboardMarkup:
    texts = load_texts()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts["buttons"]["main_menu"], callback_data="back:main")]
    ])


def payment_link_kb(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=url)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back:main")]
    ])


def donate_amounts_kb() -> InlineKeyboardMarkup:
    amounts = [100, 200, 500, 1000]
    kb = [[InlineKeyboardButton(text=f"{a} ₽", callback_data=f"donate:set:{a}")] for a in amounts]
    kb.append([InlineKeyboardButton(text="💰 Другая сумма", callback_data="donate:custom")])
    kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_menu_kb() -> InlineKeyboardMarkup:
    texts = load_texts()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧾 Создать счёт", callback_data="admin:create_invoice")],
        [InlineKeyboardButton(text=texts["buttons"]["back"], callback_data="back:main")]
    ])
