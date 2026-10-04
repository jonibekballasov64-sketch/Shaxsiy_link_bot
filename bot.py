import asyncio
import os
import sqlite3
import secrets

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DB_PATH = "posts.db"

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS files (
            code TEXT PRIMARY KEY,
            chat_id INTEGER,
            message_id INTEGER,
            title TEXT
        )"""
    )
    conn.commit()
    conn.close()


def save_file(code, chat_id, message_id, title):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO files (code, chat_id, message_id, title) VALUES (?,?,?,?)",
        (code, chat_id, message_id, title),
    )
    conn.commit()
    conn.close()


def get_file(code):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT chat_id, message_id, title FROM files WHERE code=?", (code,)
    ).fetchone()
    conn.close()
    return row


def parse_names(text: str):
    # ✳️ belgisi bo'yicha ajratamiz; har bir bo'lak bitta sarlavha hisoblanadi
    parts = text.split("✳️")
    blocks = []
    for part in parts:
        cleaned = part.strip()
        if cleaned:
            blocks.append(cleaned)
    return blocks


class NewPost(StatesGroup):
    waiting_names = State()
    waiting_files = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    args = command.args
    if args:
        row = get_file(args)
        if not row:
            await message.answer("❌ Havola topilmadi yoki eskirgan.")
            return
        chat_id, message_id, title = row
        try:
            await bot.copy_message(
                chat_id=message.from_user.id,
                from_chat_id=chat_id,
                message_id=message_id,
            )
        except Exception as e:
            await message.answer(f"❌ Xatolik: {e}")
        return

    if is_admin(message.from_user.id):
        await message.answer(
            "Salom, Admin!\n\n"
            "/newpost — yangi post yaratish\n"
            "/cancel — jarayonni bekor qilish"
        )
    else:
        await message.answer("Salom! Bu bot orqali materiallarni yuklab olasiz.")


@dp.message(Command("newpost"))
async def cmd_newpost(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(NewPost.waiting_names)
    await message.answer(
        "Materiallar nomlarini yuboring.\n\n"
        "Har bir nomni ✳️ belgisi bilan boshlang, masalan:\n\n"
        "✳️5-sinf ona tili darsligi\n📤 PDF shaklda\n"
        "✳️6-sinf ona tili darsligi\n📤 PDF shaklda"
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")


@dp.message(NewPost.waiting_names)
async def names_received(message: Message, state: FSMContext):
    names = parse_names(message.text)
    if not names:
        await message.answer(
            "Kamida bitta nom yuboring, har birini ✳️ belgisi bilan boshlang."
        )
        return
    await state.update_data(names=names, index=0, items=[])
    await state.set_state(NewPost.waiting_files)
    preview = "\n".join(f"{i+1}. {n.splitlines()[0]}" for i, n in enumerate(names))
    await message.answer(
        f"✅ {len(names)} ta nom qabul qilindi:\n\n{preview}\n\n"
        f"1-fayl: «{names[0].splitlines()[0]}»\nKanaldan shu faylni forward qiling."
    )


@dp.message(NewPost.waiting_files, F.forward_from_chat)
async def file_received(message: Message, state: FSMContext):
    data = await state.get_data()
    names, idx, items = data["names"], data["index"], data["items"]

    if CHANNEL_ID and message.forward_from_chat.id != CHANNEL_ID:
        await message.answer("⚠️ Bu fayl belgilangan kanaldan emas, qayta forward qiling.")
        return

    title = names[idx]
    code = secrets.token_hex(4)
    save_file(code, message.forward_from_chat.id, message.forward_from_message_id, title)
    items.append((title, code))
    idx += 1

    if idx < len(names):
        await state.update_data(index=idx, items=items)
        await message.answer(
            f"✅ Saqlandi.\n\n{idx + 1}-fayl: «{names[idx].splitlines()[0]}»\n"
            f"Kanaldan shu faylni forward qiling."
        )
    else:
        bot_user = await bot.get_me()
        lines = ["📚 Yangi materiallar:\n"]
        for t, c in items:
            lines.append(f"{t}\nhttps://t.me/{bot_user.username}?start={c}\n")
        text = "\n".join(lines)
        await state.clear()

        # Avtomatik kanalga joylash
        try:
            await bot.send_message(CHANNEL_ID, text)
            await message.answer("🎉 Post tayyor va kanalga avtomatik joylandi ✅")
        except Exception as e:
            await message.answer(
                f"⚠️ Kanalga joylay olmadim ({e}).\n\n"
                f"Quyidagi matnni qo'lda joylang:\n\n{text}"
            )


@dp.message(NewPost.waiting_files)
async def file_received_wrong(message: Message):
    await message.answer("Iltimos, faylni kanaldan forward qiling (matn emas).")


async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi, polling boshlandi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
