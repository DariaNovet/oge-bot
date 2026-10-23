"""
OGE English Tracker — бот для пользователей.
Отзывы только ADMIN_IDS.
На Render Web Service слушает PORT (health check), иначе Deploy failed.
"""

import asyncio
import logging
import os
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_ОТ_BOTFATHER")
ADMIN_IDS = {
    int(x)
    for x in os.getenv("ADMIN_IDS", "123456789").replace(" ", "").split(",")
    if x.isdigit()
}
WEBAPP_URL = os.getenv(
    "WEBAPP_URL",
    "https://darianovet.github.io/oge-english-tracker/",
)
PORT = int(os.getenv("PORT", "10000"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FeedbackState(StatesGroup):
    waiting_text = State()


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Открыть трекер",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ],
            [
                KeyboardButton(text="📖 Инструкция"),
                KeyboardButton(text="💬 Оставить отзыв"),
            ],
            [KeyboardButton(text="ℹ️ О проекте")],
        ],
        resize_keyboard=True,
    )


def feedback_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="feedback_cancel")]
        ]
    )


HELP_TEXT = """
<b>Как пользоваться трекером</b>

1. Нажми <b>«Открыть трекер»</b>.
2. Зарегистрируйся или войди (email + пароль).
3. <b>Задания</b> — группа и вариант, отметь «Верно» / «Неверно».
4. При ошибке укажи причину — она будет в разделе «Ошибки».
5. <b>Главная</b> и <b>Статистика</b> — прогресс (например: 7 из 340).
6. <b>Демоверсия</b> — задания 1–34 отдельно от банка ФИПИ.
7. PDF: в «Статистике» (банк) и в «Демоверсии» (демо).
8. Поиск по коду — по всем группам; точный код открывает задание сразу.
""".strip()


ABOUT_TEXT = """
<b>OGE English Tracker</b>

Трекер подготовки к ОГЭ по английскому: задания, прогресс, ошибки, демо.

Открыть — <b>«Открыть трекер»</b>.
Идеи и баги — <b>«Оставить отзыв»</b>.
""".strip()


async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"Привет, <b>{name}</b>!\n\n"
        "Бот <b>OGE English Tracker</b>.\n"
        "Открой трекер, прочитай инструкцию или оставь отзыв.",
        reply_markup=main_keyboard(),
    )


async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HELP_TEXT, reply_markup=main_keyboard())


async def cmd_app(message: Message, state: FSMContext) -> None:
    await state.clear()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть приложение",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ]
    )
    await message.answer("Нажми кнопку:", reply_markup=kb)


async def btn_help(message: Message, state: FSMContext) -> None:
    await cmd_help(message, state)


async def btn_about(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(ABOUT_TEXT, reply_markup=main_keyboard())


async def feedback_start(message: Message, state: FSMContext) -> None:
    await state.set_state(FeedbackState.waiting_text)
    await message.answer(
        "Напиши отзыв одним сообщением.\nОтмена — кнопка ниже или /cancel.",
        reply_markup=feedback_cancel_keyboard(),
    )


async def feedback_cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Отзыв отменён.", reply_markup=main_keyboard())
    await callback.answer()


async def feedback_cancel_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отзыв отменён.", reply_markup=main_keyboard())


async def feedback_receive(message: Message, state: FSMContext, bot: Bot) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пришли текст или /cancel.")
        return

    await state.clear()
    user = message.from_user
    username = f"@{user.username}" if user.username else "без username"
    admin_text = (
        "<b>Новый отзыв</b>\n\n"
        f"От: {user.full_name} ({username})\n"
        f"ID: <code>{user.id}</code>\n\n"
        f"{text}"
    )

    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
            sent += 1
        except Exception as e:
            logger.warning("Admin %s: %s", admin_id, e)

    if sent:
        await message.answer("Спасибо! Отзыв отправлен.", reply_markup=main_keyboard())
    else:
        await message.answer(
            "Не удалось доставить. Попробуй позже.",
            reply_markup=main_keyboard(),
        )


async def fallback(message: Message, state: FSMContext) -> None:
    if await state.get_state() is not None:
        return
    await message.answer("Выбери кнопку внизу или /help.", reply_markup=main_keyboard())


async def health_handler(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN.startswith("ВСТАВЬ"):
        raise SystemExit("Укажи BOT_TOKEN")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_app, Command("app"))
    dp.message.register(feedback_cancel_cmd, Command("cancel"))

    dp.message.register(btn_help, F.text == "📖 Инструкция")
    dp.message.register(btn_about, F.text == "ℹ️ О проекте")
    dp.message.register(feedback_start, F.text == "💬 Оставить отзыв")

    dp.callback_query.register(feedback_cancel_cb, F.data == "feedback_cancel")

    dp.message.register(
        feedback_receive,
        StateFilter(FeedbackState.waiting_text),
        F.text,
    )
    dp.message.register(fallback)

    # HTTP для Render (чтобы не было Deploy failed)
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("HTTP health on port %s", PORT)

    logger.info("User bot started. ADMIN_IDS=%s", ADMIN_IDS)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
