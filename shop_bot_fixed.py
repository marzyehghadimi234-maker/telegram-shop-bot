import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# ---------- تنظیمات ----------
API_TOKEN = "8234319115:AAHm6v2Ex29RiHJ-1TpXskSeRWwd_AAHJFs"
ADMIN_ID = 8152990398

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# ---------- استیت‌ها (برای مکالمه چند مرحله‌ای) ----------
class AddProduct(StatesGroup):
    name = State()
    price = State()


class Broadcast(StatesGroup):
    text = State()


# ---------- دیتابیس ----------
conn = sqlite3.connect("shop.db")
cursor = conn.cursor()


def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        full_name TEXT,
        username TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price INTEGER NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total_price INTEGER NOT NULL
    )
    """)

    conn.commit()


def seed_products():
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    if count == 0:
        products = [
            ("دوره پایتون مقدماتی", 200000),
            ("دوره ربات تلگرام حرفه‌ای", 350000),
            ("پکیج اتوماسیون کسب‌وکار", 500000),
        ]
        cursor.executemany("INSERT INTO products (name, price) VALUES (?, ?)", products)
        conn.commit()


init_db()
seed_products()


# ---------- ثبت کاربر ----------
def register_user(user: types.User):
    cursor.execute("SELECT id FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute(
            "INSERT INTO users (user_id, full_name, username) VALUES (?, ?, ?)",
            (user.id, user.full_name, user.username)
        )
        conn.commit()


# ---------- کیبوردها ----------
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("🛍 لیست محصولات"))
main_menu.add(KeyboardButton("🛒 سبد خرید"))
main_menu.add(KeyboardButton("📦 ثبت سفارش"))
main_menu.add(KeyboardButton("ℹ️ راهنما"))

admin_menu = ReplyKeyboardMarkup(resize_keyboard=True)
admin_menu.add(KeyboardButton("📦 مدیریت محصولات"))
admin_menu.add(KeyboardButton("🧾 لیست سفارش‌ها"))
admin_menu.add(KeyboardButton("📢 ارسال پیام به همه"))
admin_menu.add(KeyboardButton("🔙 بازگشت"))


def products_keyboard():
    kb = InlineKeyboardMarkup()
    cursor.execute("SELECT id, name, price FROM products")
    for prod_id, name, price in cursor.fetchall():
        kb.add(InlineKeyboardButton(
            f"{name} - {price} تومان",
            callback_data=f"product_{prod_id}"
        ))
    return kb


def product_actions_keyboard(product_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ افزودن به سبد", callback_data=f"add_{product_id}"))
    return kb


def cart_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🗑 خالی کردن سبد", callback_data="clear_cart"))
    return kb


def admin_products_keyboard():
    kb = InlineKeyboardMarkup()
    cursor.execute("SELECT id, name, price FROM products")
    for prod_id, name, price in cursor.fetchall():
        kb.add(InlineKeyboardButton(
            f"❌ حذف: {name} ({price})",
            callback_data=f"delprod_{prod_id}"
        ))
    kb.add(InlineKeyboardButton("➕ افزودن محصول جدید", callback_data="add_product"))
    return kb


# ---------- هندلرهای عمومی ----------

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    register_user(message.from_user)
    text = "سلام 👋\nبه فروشگاه تلگرامی خوش اومدی!\nاز منوی زیر یکی رو انتخاب کن:"
    await message.answer(text, reply_markup=main_menu)


@dp.message_handler(lambda m: m.text == "ℹ️ راهنما")
async def help_message(message: types.Message):
    text = (
        "📌 راهنمای استفاده از ربات:\n\n"
        "🛍 لیست محصولات: دیدن محصولات موجود\n"
        "🛒 سبد خرید: دیدن محصولاتی که انتخاب کردی\n"
        "📦 ثبت سفارش: ثبت نهایی سفارش و ارسال برای ادمین\n\n"
        "برای سوالات بیشتر می‌تونی به پشتیبانی پیام بدی."
    )
    await message.answer(text)


@dp.message_handler(lambda m: m.text == "🛍 لیست محصولات")
async def show_products(message: types.Message):
    kb = products_keyboard()
    await message.answer("🛍 لیست محصولات:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("product_"))
async def product_detail(callback_query: types.CallbackQuery):
    product_id = int(callback_query.data.split("_")[1])
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    if not row:
        await callback_query.message.answer("این محصول پیدا نشد.")
        return

    name, price = row
    kb = product_actions_keyboard(product_id)
    await callback_query.message.answer(
        f"📦 {name}\n💰 قیمت: {price} تومان",
        reply_markup=kb
    )


@dp.callback_query_handler(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    product_id = int(callback_query.data.split("_")[1])

    cursor.execute("INSERT INTO cart (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
    conn.commit()

    await callback_query.answer("به سبد خرید اضافه شد ✅", show_alert=False)


@dp.message_handler(lambda m: m.text == "🛒 سبد خرید")
async def show_cart(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("""
        SELECT products.name, products.price
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id = ?
    """, (user_id,))
    items = cursor.fetchall()

    if not items:
        await message.answer("سبد خریدت خالیه 🧺")
        return

    text = "🛒 سبد خرید:\n\n"
    total = 0
    for name, price in items:
        text += f"- {name} | {price} تومان\n"
        total += price

    text += f"\n💰 مجموع: {total} تومان"
    kb = cart_keyboard()
    await message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "clear_cart")
async def clear_cart(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    conn.commit()
    await callback_query.message.answer("سبد خرید خالی شد 🗑")
    await callback_query.answer()


@dp.message_handler(lambda m: m.text == "📦 ثبت سفارش")
async def create_order(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("""
        SELECT products.name, products.price
        FROM cart
        JOIN products ON cart.product_id = products.id
        WHERE cart.user_id = ?
    """, (user_id,))
    items = cursor.fetchall()

    if not items:
        await message.answer("سبد خریدت خالیه، اول محصول اضافه کن 🧺")
        return

    total = sum(price for _, price in items)

    cursor.execute("INSERT INTO orders (user_id, total_price) VALUES (?, ?)", (user_id, total))
    conn.commit()

    cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    conn.commit()

    text = f"🆕 سفارش جدید!\n\n👤 کاربر: {message.from_user.full_name} (@{message.from_user.username})\n"
    text += "🛒 آیتم‌ها:\n"
    for name, price in items:
        text += f"- {name} | {price} تومان\n"
    text += f"\n💰 مجموع: {total} تومان"

    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        pass

    await message.answer("سفارش ثبت شد ✅\nادمین به زودی باهات تماس می‌گیره.")


# ---------- پنل ادمین ----------
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("شما دسترسی ادمین ندارید.")
        return
    await message.answer("📦 پنل ادمین:", reply_markup=admin_menu)


@dp.message_handler(lambda m: m.text == "🔙 بازگشت")
async def back_to_main(message: types.Message):
    await message.answer("بازگشت به منوی اصلی.", reply_markup=main_menu)


@dp.message_handler(lambda m: m.text == "📦 مدیریت محصولات")
async def admin_manage_products(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    kb = admin_products_keyboard()
    await message.answer("📦 مدیریت محصولات:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("delprod_"))
async def delete_product(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("دسترسی ندارید.", show_alert=True)
        return

    product_id = int(callback_query.data.split("_")[1])
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()

    await callback_query.message.answer("محصول حذف شد ✅")
    kb = admin_products_keyboard()
    await callback_query.message.answer("📦 مدیریت محصولات:", reply_markup=kb)
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "add_product")
async def add_product_start(callback_query: types.CallbackQuery):
    if callback_query.from_user.id != ADMIN_ID:
        await callback_query.answer("دسترسی ندارید.", show_alert=True)
        return

    await callback_query.message.answer("نام محصول جدید را ارسال کن:")
    await AddProduct.name.set()
    await callback_query.answer()


@dp.message_handler(state=AddProduct.name)
async def admin_add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer(f"قیمت محصول «{message.text}» را به تومان ارسال کن:")
    await AddProduct.price.set()


@dp.message_handler(state=AddProduct.price)
async def admin_add_product_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("قیمت باید عدد باشد. دوباره تلاش کن.")
        return

    data = await state.get_data()
    name = data["name"]

    cursor.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, price))
    conn.commit()
    await state.finish()

    await message.answer(f"محصول «{name}» با قیمت {price} تومان اضافه شد ✅")
    kb = admin_products_keyboard()
    await message.answer("📦 مدیریت محصولات:", reply_markup=kb)


# ---------- لیست سفارش‌ها برای ادمین ----------

@dp.message_handler(lambda m: m.text == "🧾 لیست سفارش‌ها")
async def admin_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("""
        SELECT orders.id, orders.user_id, orders.total_price, users.full_name, users.username
        FROM orders
        LEFT JOIN users ON orders.user_id = users.user_id
        ORDER BY orders.id DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()

    if not rows:
        await message.answer("هنوز سفارشی ثبت نشده.")
        return

    text = "🧾 آخرین سفارش‌ها:\n\n"
    for order_id, user_id, total_price, full_name, username in rows:
        text += f"#{order_id} | {full_name} (@{username}) | {total_price} تومان\n"

    await message.answer(text)


# ---------- ارسال پیام به همه کاربران ----------

@dp.message_handler(lambda m: m.text == "📢 ارسال پیام به همه")
async def admin_broadcast_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer("متن پیامی که می‌خوای برای همه کاربران ارسال بشه رو بفرست:")
    await Broadcast.text.set()


@dp.message_handler(state=Broadcast.text)
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    text = message.text
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    sent = 0
    for (user_id,) in users:
        try:
            await bot.send_message(user_id, f"📢 پیام از طرف ادمین:\n\n{text}")
            sent += 1
        except Exception:
            continue

    await state.finish()
    await message.answer(f"پیام برای {sent} کاربر ارسال شد ✅")


# ---------- اجرای ربات ----------
if __name__ == '__main__':
    print("ربات در حال اجراست...")
    executor.start_polling(dp, skip_updates=True)
