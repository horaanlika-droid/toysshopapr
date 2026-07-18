import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import BOT_TOKEN, ADMIN_IDS, SHOP_NAME, WELCOME_TEXT, DELIVERY_TEXT
from database import *
from admin import register_admin_handlers
import json

# === НАСТРОЙКА ===
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# === ГЛАВНОЕ МЕНЮ ===
def get_main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("🛍 Каталог"),
        KeyboardButton("🔍 Поиск"),
        KeyboardButton("🛒 Корзина"),
        KeyboardButton("📦 Мои заказы"),
        KeyboardButton("📞 Контакты")
    )
    return kb

# === КОМАНДА /START ===
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Если админ - показываем админ-панель
    if message.from_user.id in ADMIN_IDS:
        from admin import show_admin_menu
        await show_admin_menu(message)
        return
    
    # Приветствие
    text = f"""
{WELCOME_TEXT}

🆔 Ваш ID: {message.from_user.id}

Используйте кнопки ниже для навигации.
"""
    await message.answer(text, reply_markup=get_main_menu())

# === КАТАЛОГ ===
@dp.message_handler(lambda m: m.text == "🛍 Каталог")
async def catalog(message: types.Message):
    categories = get_all_categories()
    if not categories:
        await message.answer("📭 Каталог пока пуст. Загляните позже!")
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        kb.add(InlineKeyboardButton(f"📂 {cat}", callback_data=f"cat_{cat}"))
    kb.add(InlineKeyboardButton("🔍 Поиск", callback_data="search"))
    
    await message.answer("🛍 Выберите категорию:", reply_markup=kb)

# === КАТЕГОРИЯ ===
@dp.callback_query_handler(lambda c: c.data.startswith('cat_'))
async def show_category(callback: types.CallbackQuery):
    category = callback.data.replace('cat_', '')
    products = get_products_by_category(category)
    
    if not products:
        await callback.message.answer("📭 В этой категории пока нет товаров")
        await callback.answer()
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products[:10]:  # Показываем по 10
        discount_text = f" 🔥-{p['discount']}%" if p['discount'] > 0 else ""
        kb.add(InlineKeyboardButton(
            f"{p['name']} - {p['final_price']}₽{discount_text}",
            callback_data=f"product_{p['article']}"
        ))
    
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_catalog"))
    await callback.message.edit_text(f"📂 {category}", reply_markup=kb)
    await callback.answer()

# === ТОВАР ===
@dp.callback_query_handler(lambda c: c.data.startswith('product_'))
async def show_product(callback: types.CallbackQuery):
    article = callback.data.replace('product_', '')
    product = get_product(article)
    
    if not product:
        await callback.answer("❌ Товар не найден")
        return
    
    # Формируем описание
    text = f"""
🧸 {product['name']}
📂 {product['category']}

💰 Цена: <b>{product['final_price']} ₽</b>
"""
    if product['discount'] > 0:
        text += f"<s>Было: {product['price']} ₽</s>\n"
        text += f"🔥 Скидка: {product['discount']}% (экономия {product['price'] - product['final_price']} ₽)\n"
    
    text += f"""
📌 Артикул: {product['article']}
📦 В наличии: {product['stock']} шт.

{DELIVERY_TEXT}
"""
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛒 В корзину", callback_data=f"add_cart_{product['article']}"),
        InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{product['category']}")
    )
    
    if product['photo_path'] and product['photo_path'] != 'None':
        try:
            with open(product['photo_path'], 'rb') as photo:
                await callback.message.answer_photo(photo, caption=text, reply_markup=kb, parse_mode='HTML')
        except:
            await callback.message.answer(text, reply_markup=kb, parse_mode='HTML')
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    
    await callback.answer()

# === КОРЗИНА ===
# Храним корзины в памяти (для упрощения)
carts = {}

@dp.callback_query_handler(lambda c: c.data.startswith('add_cart_'))
async def add_to_cart(callback: types.CallbackQuery):
    article = callback.data.replace('add_cart_', '')
    user_id = callback.from_user.id
    product = get_product(article)
    
    if not product:
        await callback.answer("❌ Товар не найден")
        return
    
    if user_id not in carts:
        carts[user_id] = {}
    
    if article in carts[user_id]:
        carts[user_id][article]['qty'] += 1
    else:
        carts[user_id][article] = {
            'name': product['name'],
            'price': product['final_price'],
            'qty': 1,
            'article': article
        }
    
    await callback.answer(f"✅ {product['name']} добавлен в корзину!", show_alert=True)

@dp.message_handler(lambda m: m.text == "🛒 Корзина")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    cart = carts.get(user_id, {})
    
    if not cart:
        await message.answer("🛒 Корзина пуста")
        return
    
    total = 0
    text = "🛒 ВАША КОРЗИНА:\n\n"
    for article, item in cart.items():
        total += item['price'] * item['qty']
        text += f"• {item['name']} x{item['qty']} = {item['price'] * item['qty']} ₽\n"
    
    text += f"\n💰 Итого: {total} ₽\n"
    text += f"\n{DELIVERY_TEXT}"
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🗑️ Очистить", callback_data="clear_cart"),
        InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")
    )
    
    await message.answer(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "clear_cart")
async def clear_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in carts:
        carts[user_id] = {}
    await callback.message.edit_text("🛒 Корзина очищена")
    await callback.answer()

# === ОФОРМЛЕНИЕ ЗАКАЗА ===
@dp.callback_query_handler(lambda c: c.data == "checkout")
async def checkout(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cart = carts.get(user_id, {})
    
    if not cart:
        await callback.answer("Корзина пуста!", show_alert=True)
        return    
    # Считаем сумму
    total = 0
    items_list = []
    for article, item in cart.items():
        total += item['price'] * item['qty']
        items_list.append({
            'article': article,
            'name': item['name'],
            'price': item['price'],
            'qty': item['qty']
        })
    
    # Создаем заказ в БД
    order_id = create_order(
        user_id=user_id,
        username=callback.from_user.username,
        items=items_list,
        total_amount=total
    )
    
    # Очищаем корзину
    carts[user_id] = {}
    
    # Текст заказа
    text = f"""
✅ Заказ #{order_id} создан!

Сумма товаров: {total} ₽
{DELIVERY_TEXT}

🔗 ОПЛАТА:
{PAYMENT_LINK}

После оплаты нажмите кнопку ниже.
"""
    
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Я оплатил", callback_data=f"paid_{order_id}")
    )
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# === ОПЛАТА ===
@dp.callback_query_handler(lambda c: c.data.startswith('paid_'))
async def confirm_payment(callback: types.CallbackQuery):
    order_id = int(callback.data.replace('paid_', ''))
    order = get_order(order_id)
    
    if not order:
        await callback.answer("Заказ не найден")
        return
    
    if order['status'] != 'ожидает_оплаты':
        await callback.answer("Этот заказ уже обработан")
        return
    
    # Меняем статус на ожидание подтверждения
    update_order_status(order_id, 'ожидает_подтверждения')
    
    await callback.message.edit_text(f"""
✅ Оплата получена! Заказ #{order_id} передан в обработку.

Ожидайте подтверждения от менеджера (обычно 10-15 минут).

{DELIVERY_TEXT}
""")
    
    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"""
🔔 НОВАЯ ОПЛАТА!
Заказ #{order_id} ожидает подтверждения.
Пользователь: @{callback.from_user.username}
Сумма: {order['total_amount']} ₽
""")
        except:
            pass
    
    await callback.answer()

# === ПОИСК ===
@dp.message_handler(lambda m: m.text == "🔍 Поиск")
async def search_prompt(message: types.Message):
    await message.answer("🔍 Введите название товара для поиска:")

@dp.message_handler(lambda m: m.text and len(m.text) > 2)
async def search_products_handler(message: types.Message):
    # Проверяем, что это не команда
    if message.text.startswith('/'):
        return
    
    products = search_products(message.text)
    
    if not products:
        await message.answer("❌ Товары не найдены. Попробуйте другие ключевые слова.")
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products[:10]:
        discount_text = f" 🔥-{p['discount']}%" if p['discount'] > 0 else ""
        kb.add(InlineKeyboardButton(
            f"{p['name']} - {p['final_price']}₽{discount_text}",
            callback_data=f"product_{p['article']}"
        ))
    
    await message.answer(f"🔍 Найдено {len(products)} товаров:", reply_markup=kb)

# === МОИ ЗАКАЗЫ ===
@dp.message_handler(lambda m: m.text == "📦 Мои заказы")
async def my_orders(message: types.Message):
    orders = get_orders()
    user_orders = [o for o in orders if o['user_id'] == message.from_user.id]
    
    if not user_orders:
        await message.answer("📭 У вас пока нет заказов")
        return
    
    text = "📦 ВАШИ ЗАКАЗЫ:\n\n"
    for order in user_orders[-5:]:  # Последние 5
        status_emoji = {
            'ожидает_оплаты': '⏳',
            'ожидает_подтверждения': '🔄',
            'подтвержден': '✅',
            'отменен': '❌'
        }.get(order['status'], '📌')
        
        text += f"{status_emoji} #{order['id']} | {order['status']} | {order['total_amount']}₽ | {order['created_at'][:10]}\n"
    
    await message.answer(text)

# === КОНТАКТЫ ===
@dp.message_handler(lambda m: m.text == "📞 Контакты")
async def contacts(message: types.Message):
    text = f"""
📞 Контакты {SHOP_NAME}

По всем вопросам обращайтесь к менеджеру:
@support_username

🕐 Режим работы: 10:00 - 21:00
📍 Город: Ваш город
    """
    await message.answer(text)

# === НАЗАД В КАТАЛОГ ===
@dp.callback_query_handler(lambda c: c.data == "back_to_catalog")
async def back_to_catalog(callback: types.CallbackQuery):
    await catalog(callback.message)
    await callback.answer()

# === РЕГИСТРАЦИЯ АДМИН-ХЭНДЛЕРОВ ===
register_admin_handlers(dp)

# === ЗАПУСК ===
if __name__ == '__main__':
    # Инициализация БД
    init_db()
    print(f"✅ {SHOP_NAME} запущен!")
    print(f"👤 Администратор: {ADMIN_IDS[0]}")
    print("🚀 Бот готов к работе!")
    
    executor.start_polling(dp, skip_updates=True)