import asyncio
import os
import html as html_lib

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_ID = os.getenv("CHANNEL_ID")  # masalan -1001234567890 yoki @kanal_username

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def parse_names(text: str):
    parts = text.split("✳️")
    blocks = []
    for part in parts:
        cleaned = part.strip()
        if cleaned:
            blocks.append(cleaned)
    return blocks


def parse_links(text: str):
    links = [line.strip() for line in text.split("\n") if line.strip()]
    return links


class NewPost(StatesGroup):
    waiting_names = State()
    waiting_links = State()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "Salom, Admin!\n\n"
            "/newpost — yangi post yaratish\n"
            "/cancel — jarayonni bekor qilish"
        )
    else:
        await message.answer("Salom!")


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

    await state.update_data(names=names)
    await state.set_state(NewPost.waiting_links)

    preview = "\n".join(f"{i+1}. {n.splitlines()[0]}" for i, n in enumerate(names))
    await message.answer(
        f"✅ {len(names)} ta nom qabul qilindi:\n\n{preview}\n\n"
        f"Endi shu {len(names)} ta nomga mos fayl linklarini yuboring.\n"
        f"Har bir linkni YANGI QATORDA, nomlar bilan BIR XIL TARTIBDA yozing.\n\n"
        f"Masalan:\nhttps://t.me/kanal_username/101\nhttps://t.me/kanal_username/102"
    )


@dp.message(NewPost.waiting_links)
async def links_received(message: Message, state: FSMContext):
    data = await state.get_data()
    names = data["names"]
    links = parse_links(message.text)

    if len(links) != len(names):
        await message.answer(
            f"⚠️ Nomlar soni ({len(names)}) va linklar soni ({len(links)}) mos kelmadi.\n"
            f"Iltimos, {len(names)} ta linkni, har birini yangi qatorda, qayta yuboring."
        )
        return

    lines = ["📚 Yangi materiallar:\n"]
    for name_block, link in zip(names, links):
        parts = name_block.splitlines()
        title = html_lib.escape(parts[0])
        rest = "\n".join(parts[1:])
        entry = f'<a href="{link}">{title}</a>'
        if rest:
            entry += f"\n{rest}"
        lines.append(entry)

    text = "\n\n".join(lines)
    await state.clear()

    try:
        await bot.send_message(CHANNEL_ID, text, disable_web_page_preview=True)
        await message.answer("🎉 Post tayyor va kanalga avtomatik joylandi ✅")
    except Exception as e:
        await message.answer(
            f"⚠️ Kanalga joylay olmadim ({e}).\n\n"
            f"Quyidagi matnni qo'lda joylang:\n\n{text}"
        )


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi, polling boshlandi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
