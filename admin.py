from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS, DATA_DIR, SHOP_NAME
from database import *
import os
import json
from datetime import datetime

# === СОСТОЯНИЯ ДЛЯ ДОБАВЛЕНИЯ ТОВАРА ===
class AddProductStates(StatesGroup):
    name = State()
    category = State()
    price = State()
    discount = State()
    stock = State()
    photo = State()

# === СОСТОЯНИЯ ДЛЯ РЕДАКТИРОВАНИЯ ===
class EditProductStates(StatesGroup):
    article = State()
    field = State()
    value = State()

# === АДМИН-МЕНЮ ===
async def show_admin_menu(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔️ Доступ запрещен")
        return
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add"),
        InlineKeyboardButton("✏️ Редактировать", callback_data="admin_edit"),
        InlineKeyboardButton("📦 Заказы", callback_data="admin_orders"),
        InlineKeyboardButton("🔥 Скидка на категорию", callback_data="admin_category_discount"),
        InlineKeyboardButton("📥 Импорт Excel", callback_data="admin_import"),
        InlineKeyboardButton("📤 Экспорт базы", callback_data="admin_export")
    )
    await message.answer(f"🔐 Админ-панель\n{SHOP_NAME}", reply_markup=kb)

# === СТАТИСТИКА ===
async def show_stats(callback: types.CallbackQuery):
    total_products, total_orders, today_orders = get_stats()
    
    # Последние 5 заказов
    orders = get_orders()
    recent = orders[:5]
    recent_text = ""
    for order in recent:
        recent_text += f"#{order['id']} | {order['username']} | {order['status']} | {order['total_amount']}₽\n"
    
    text = f"""
📊 СТАТИСТИКА МАГАЗИНА

🛍 Товаров: {total_products}
📦 Заказов всего: {total_orders}
📦 Заказов сегодня: {today_orders}

📋 Последние 5 заказов:
{recent_text or 'Нет заказов'}
    """
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("◀️ Назад", callback_data="admin_back")
    ))

# === ДОБАВЛЕНИЕ ТОВАРА ===
async def start_add_product(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.answer("📝 Введите НАЗВАНИЕ товара:")
    await AddProductStates.name.set()
    await callback.answer()

async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("📂 Введите КАТЕГОРИЮ (например: Игрушки/Лабубу/Коллекционные):")
    await AddProductStates.category.set()

async def process_category(message: types.Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("💰 Введите ЦЕНУ товара (число):")
    await AddProductStates.price.set()

async def process_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
        await state.update_data(price=price)
        await message.answer("🏷️ Введите СКИДКУ в % (0 - если нет):")
        await AddProductStates.discount.set()
    except ValueError:
        await message.answer("❌ Введите число! Попробуйте еще раз:")

async def process_discount(message: types.Message, state: FSMContext):
    try:
        discount = int(message.text)
        if discount < 0 or discount > 100:
            await message.answer("❌ Скидка должна быть от 0 до 100. Введите заново:")
            return
        await state.update_data(discount=discount)
        await message.answer("📦 Введите КОЛИЧЕСТВО товара на складе:")
        await AddProductStates.stock.set()
    except ValueError:
        await message.answer("❌ Введите число! Попробуйте еще раз:")

async def process_stock(message: types.Message, state: FSMContext):
    try:
        stock = int(message.text)
        await state.update_data(stock=stock)
        await message.answer("🖼️ Отправьте ФОТО товара (или нажмите /skip чтобы пропустить):")
        await AddProductStates.photo.set()
    except ValueError:
        await message.answer("❌ Введите число! Попробуйте еще раз:")

async def process_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Если есть фото - сохраняем
    photo_path = None
    if message.photo:
        file_id = message.photo[-1].file_id
        file = await message.bot.get_file(file_id)
        article = generate_article()
        photo_path = f"{DATA_DIR}/{article}.jpg"
        await message.bot.download_file(file.file_path, photo_path)
    
    # Сохраняем товар
    article = add_product(
        name=data['name'],
        category=data['category'],
        price=data['price'],
        discount=data['discount'],
        stock=data['stock'],
        photo_path=photo_path
    )
    
    # Формируем ответ
    final_price = data['price'] if data['discount'] == 0 else int(data['price'] * (100 - data['discount']) / 100)
    text = f"""
✅ Товар добавлен!

🧸 {data['name']}
📂 {data['category']}
💰 Цена: {final_price} ₽
{f'🔥 Скидка: {data["discount"]}%' if data["discount"] > 0 else ''}
📦 В наличии: {data['stock']} шт.
📌 Артикул: {article}
"""
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("➕ Добавить еще", callback_data="admin_add"),
        InlineKeyboardButton("◀️ В админку", callback_data="admin_back")
    )
    
    if photo_path:
        await message.answer_photo(open(photo_path, 'rb'), caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)
    
    await state.finish()

async def skip_photo(message: types.Message, state: FSMContext):
    if message.text == "/skip":
        data = await state.get_data()
        article = add_product(
            name=data['name'],
            category=data['category'],
            price=data['price'],
            discount=data['discount'],
            stock=data['stock'],
            photo_path=None
        )
        await message.answer(f"✅ Товар добавлен без фото!\nАртикул: {article}")
        await state.finish()
        await show_admin_menu(message)

# === РЕДАКТИРОВАНИЕ ТОВАРА ===
async def start_edit_product(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.answer("🔍 Введите АРТИКУЛ или НАЗВАНИЕ товара для поиска:")
    await EditProductStates.article.set()
    await callback.answer()

async def search_for_edit(message: types.Message, state: FSMContext):
    query = message.text
    products = search_products(query)
    
    if not products:
        await message.answer("❌ Товары не найдены. Попробуйте другой запрос:")
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        kb.add(InlineKeyboardButton(
            f"{p['name']} ({p['article']}) - {p['final_price']}₽",
            callback_data=f"edit_select_{p['article']}"
        ))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="admin_back"))
    
    await message.answer(f"🔍 Найдено {len(products)} товаров. Выберите для редактирования:", reply_markup=kb)
    await state.finish()

async def select_field_for_edit(callback: types.CallbackQuery, state: FSMContext):
    article = callback.data.replace("edit_select_", "")
    await state.update_data(article=article)
    
    product = get_product(article)
    if not product:
        await callback.answer("❌ Товар не найден")
        return
    
    text = f"""
🧸 {product['name']}
📌 Артикул: {product['article']}
💰 Цена: {product['final_price']}₽
{f'🔥 Скидка: {product["discount"]}%' if product["discount"] > 0 else ''}
📦 В наличии: {product['stock']} шт.
"""
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Цена", callback_data=f"edit_field_price_{article}"),
        InlineKeyboardButton("🏷️ Скидка", callback_data=f"edit_field_discount_{article}"),
        InlineKeyboardButton("📦 Количество", callback_data=f"edit_field_stock_{article}"),
        InlineKeyboardButton("📂 Категория", callback_data=f"edit_field_category_{article}"),
        InlineKeyboardButton("🗑️ Удалить", callback_data=f"edit_delete_{article}"),
        InlineKeyboardButton("◀️ Назад", callback_data="admin_edit")
    )
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

async def edit_field_value(callback: types.CallbackQuery, state: FSMContext):
    _, field, article = callback.data.split("_", 2)
    await state.update_data(article=article, field=field)
    
    field_names = {
        'price': 'новую ЦЕНУ',
        'discount': 'новую СКИДКУ в % (0-100)',
        'stock': 'новое КОЛИЧЕСТВО',
        'category': 'новую КАТЕГОРИЮ'
    }
    
    await callback.message.answer(f"✏️ Введите {field_names.get(field, field)}:")
    await EditProductStates.value.set()
    await callback.answer()

async def process_edit_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    article = data['article']
    field = data['field']
    value = message.text
    
    if field in ['price', 'discount', 'stock']:
        try:
            value = int(value)
            if field == 'discount' and (value < 0 or value > 100):
                await message.answer("❌ Скидка должна быть от 0 до 100. Попробуйте еще раз:")
                return
        except ValueError:
            await message.answer("❌ Введите число! Попробуйте еще раз:")
            return
    
    if field == 'discount':
        update_discount(article, value)
    else:
        update_product(article, field, value)
    
    await message.answer("✅ Товар обновлен!")
    await state.finish()
    await show_admin_menu(message)

async def delete_product_admin(callback: types.CallbackQuery):
    article = callback.data.replace("edit_delete_", "")
    delete_product(article)
    await callback.message.edit_text("✅ Товар удален")
    await callback.answer()

# === ЗАКАЗЫ ===
async def show_orders(callback: types.CallbackQuery):
    await callback.answer()
    
    orders = get_orders(status='ожидает_подтверждения')
    if not orders:
        # Если нет новых, показываем все
        orders = get_orders()[:10]
    
    if not orders:
        await callback.message.answer("📭 Заказов пока нет")
        return
    
    for order in orders[:5]:  # Показываем по 5
        items = json.loads(order['items'])
        items_text = "\n".join([f"• {item['name']} x{item['qty']} = {item['price']}₽" for item in items])
        
        text = f"""
📦 Заказ #{order['id']}
👤 Клиент: @{order['username'] or 'не указан'}
💰 Сумма: {order['total_amount']} ₽
🚚 Доставка: по тарифу курьера
📅 {order['created_at']}

🛍 Товары:
{items_text}

Статус: {order['status']}
"""
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"order_confirm_{order['id']}"),
            InlineKeyboardButton("📞 Уточнить", callback_data=f"order_clarify_{order['id']}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"order_cancel_{order['id']}")
        )
        
        await callback.message.answer(text, reply_markup=kb)
    
    # Кнопка "Показать еще"
    if len(orders) > 5:
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📋 Все заказы", callback_data="admin_all_orders"),
            InlineKeyboardButton("◀️ Назад", callback_data="admin_back")
        )
        await callback.message.answer("📋 Показать еще?", reply_markup=kb)

async def handle_order_action(callback: types.CallbackQuery):
    _, action, order_id = callback.data.split("_")
    order_id = int(order_id)
    order = get_order(order_id)
    
    if not order:
        await callback.answer("Заказ не найден")
        return
    
    if action == 'confirm':
        update_order_status(order_id, 'подтвержден')
        text = f"""
✅ Заказ #{order_id} подтвержден!

{SHOP_NAME}
В ближайшее время с вами свяжется курьер для уточнения времени и стоимости доставки.

🚚 Доставка оплачивается отдельно по тарифу курьерской службы при получении.
"""
        await callback.bot.send_message(order['user_id'], text)
        await callback.message.edit_text(f"✅ Заказ #{order_id} подтвержден. Уведомление отправлено клиенту.")
    
    elif action == 'clarify':
        await callback.message.answer(f"✏️ Введите комментарий для клиента по заказу #{order_id}:")
        await callback.message.answer("(Пока не реализовано, используйте /send_msg user_id текст)")
    
    elif action == 'cancel':
        update_order_status(order_id, 'отменен')
        await callback.bot.send_message(order['user_id'], f"❌ Заказ #{order_id} отменен. Если у вас есть вопросы, напишите менеджеру.")
        await callback.message.edit_text(f"❌ Заказ #{order_id} отменен.")
    
    await callback.answer()

# === МАССОВАЯ СКИДКА НА КАТЕГОРИЮ ===
async def start_category_discount(callback: types.CallbackQuery, state: FSMContext):
    categories = get_all_categories()
    if not categories:
        await callback.message.answer("❌ Нет категорий")
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        kb.add(InlineKeyboardButton(cat, callback_data=f"cat_discount_{cat}"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="admin_back"))
    
    await callback.message.edit_text("🔥 Выберите категорию для скидки:", reply_markup=kb)
    await callback.answer()

async def set_category_discount(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.replace("cat_discount_", "")
    await state.update_data(category=category)
    await callback.message.answer(f"Введите скидку в % для категории: {category}")
    await callback.answer()

# === ОБРАБОТЧИКИ ===
def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(show_admin_menu, commands=['admin'])
    dp.register_callback_query_handler(show_admin_menu, lambda c: c.data == 'admin_back')
    
    dp.register_callback_query_handler(show_stats, lambda c: c.data == 'admin_stats')
    dp.register_callback_query_handler(start_add_product, lambda c: c.data == 'admin_add')
    dp.register_callback_query_handler(start_edit_product, lambda c: c.data == 'admin_edit')
    dp.register_callback_query_handler(show_orders, lambda c: c.data == 'admin_orders')
    dp.register_callback_query_handler(start_category_discount, lambda c: c.data == 'admin_category_discount')
    
    # Добавление товара
    dp.register_message_handler(process_name, state=AddProductStates.name)
    dp.register_message_handler(process_category, state=AddProductStates.category)
    dp.register_message_handler(process_price, state=AddProductStates.price)
    dp.register_message_handler(process_discount, state=AddProductStates.discount)
    dp.register_message_handler(process_stock, state=AddProductStates.stock)
    dp.register_message_handler(process_photo, state=AddProductStates.photo, content_types=['photo'])
    dp.register_message_handler(skip_photo, state=AddProductStates.photo, commands=['skip'])
    
    # Редактирование
    dp.register_message_handler(search_for_edit, state=EditProductStates.article)
    dp.register_message_handler(process_edit_value, state=EditProductStates.value)
    dp.register_callback_query_handler(select_field_for_edit, lambda c: c.data.startswith('edit_select_'))
    dp.register_callback_query_handler(edit_field_value, lambda c: c.data.startswith('edit_field_'))
    dp.register_callback_query_handler(delete_product_admin, lambda c: c.data.startswith('edit_delete_'))
    dp.register_callback_query_handler(set_category_discount, lambda c: c.data.startswith('cat_discount_'))
    
    # Заказы
    dp.register_callback_query_handler(handle_order_action, lambda c: c.data.startswith('order_'))