import sqlite3
from datetime import datetime
import random
import string

def get_db():
    conn = sqlite3.connect('shop.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # Таблица товаров
    cur.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article TEXT UNIQUE,
        name TEXT NOT NULL,
        category TEXT,
        price INTEGER NOT NULL,
        discount INTEGER DEFAULT 0,
        final_price INTEGER,
        stock INTEGER DEFAULT 0,
        photo_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица заказов
    cur.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        items TEXT,  -- JSON строка с товарами
        total_amount INTEGER,
        status TEXT DEFAULT 'ожидает_оплаты',
        delivery_cost INTEGER DEFAULT 0,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица пользователей
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def generate_article():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def add_product(name, category, price, discount, stock, photo_path=None):
    conn = get_db()
    cur = conn.cursor()
    article = generate_article()
    final_price = int(price * (100 - discount) / 100) if discount > 0 else price
    
    cur.execute('''
    INSERT INTO products (article, name, category, price, discount, final_price, stock, photo_path)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (article, name, category, price, discount, final_price, stock, photo_path))
    
    conn.commit()
    conn.close()
    return article

def get_product(article):
    conn = get_db()
    cur = conn.cursor()
    product = cur.execute('SELECT * FROM products WHERE article = ?', (article,)).fetchone()
    conn.close()
    return product

def search_products(query):
    conn = get_db()
    cur = conn.cursor()
    products = cur.execute('''
    SELECT * FROM products 
    WHERE name LIKE ? OR category LIKE ? OR article LIKE ?
    LIMIT 20
    ''', (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
    conn.close()
    return products

def get_products_by_category(category):
    conn = get_db()
    cur = conn.cursor()
    products = cur.execute('''
    SELECT * FROM products WHERE category LIKE ? ORDER BY name
    ''', (f'{category}%',)).fetchall()
    conn.close()
    return products

def get_all_categories():
    conn = get_db()
    cur = conn.cursor()
    categories = cur.execute('''
    SELECT DISTINCT category FROM products WHERE category IS NOT NULL
    ''').fetchall()
    conn.close()
    return [cat[0] for cat in categories]

def update_product(article, field, value):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f'UPDATE products SET {field} = ? WHERE article = ?', (value, article))
    conn.commit()
    conn.close()

def update_discount(article, discount):
    conn = get_db()
    cur = conn.cursor()
    product = get_product(article)
    final_price = int(product['price'] * (100 - discount) / 100) if discount > 0 else product['price']
    cur.execute('UPDATE products SET discount = ?, final_price = ? WHERE article = ?', (discount, final_price, article))
    conn.commit()
    conn.close()

def delete_product(article):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM products WHERE article = ?', (article,))
    conn.commit()
    conn.close()

def create_order(user_id, username, items, total_amount):
    conn = get_db()
    cur = conn.cursor()
    import json
    cur.execute('''
    INSERT INTO orders (user_id, username, items, total_amount, status)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, json.dumps(items), total_amount, 'ожидает_оплаты'))
    
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_orders(status=None):
    conn = get_db()
    cur = conn.cursor()
    if status:
        orders = cur.execute('SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC', (status,)).fetchall()
    else:
        orders = cur.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()
    return orders

def update_order_status(order_id, status, comment=None):
    conn = get_db()
    cur = conn.cursor()
    if comment:
        cur.execute('UPDATE orders SET status = ?, comment = ? WHERE id = ?', (status, comment, order_id))
    else:
        cur.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

def get_order(order_id):
    conn = get_db()
    cur = conn.cursor()
    order = cur.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    conn.close()
    return order

def get_stats():
    conn = get_db()
    cur = conn.cursor()
    total_products = cur.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    total_orders = cur.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    today_orders = cur.execute('''
    SELECT COUNT(*) FROM orders 
    WHERE DATE(created_at) = DATE('now')
    ''').fetchone()[0]
    conn.close()
    return total_products, total_orders, today_orders

def register_user(user_id, username, first_name, last_name=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
    VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()