from __future__ import annotations

import asyncio
import logging
import os
import re
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import urlparse

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import load_dotenv

from storage import Store

logger = logging.getLogger("legalstart")
MAX_ANSWER = 800
WEBHOOK_PATH = "/telegram/webhook"
WELCOME = """Добро пожаловать!

«Цифровой конструктор подготовки клиента к первой встрече с адвокатом»

Проект помогает структурировать информацию о ситуации и подготовиться к встрече с адвокатом.

Выберите необходимый раздел:"""
ABOUT = """О ПРОЕКТЕ

«Цифровой конструктор подготовки клиента к первой встрече с адвокатом» — инструмент предварительной структуризации информации.

Он помогает последовательно описать обстоятельства ситуации, основные вопросы и другую важную информацию. Бот не оказывает юридическую консультацию."""
HOW = """КАК ЭТО РАБОТАЕТ

1. Познакомьтесь с проектом.
2. Начните заполнение заявки.
3. Ответьте на четыре вопроса.
4. Проверьте ответы и при необходимости измените их.
5. Нажмите «Отправить заявку».

Заявка сохранится в базе. Если подключён администратор, бот отправит ему уведомление.

Можно вернуться к заполнению через /start. Команда /cancel удаляет незавершённую анкету."""
FAQ = """ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ

Это юридическая консультация?
Нет. Бот помогает подготовить и структурировать информацию.

Можно ли изменить ответы?
Да. На экране проверки выберите нужный вопрос.

Можно ли продолжить позже?
Да. Прогресс хранится в базе, нажмите «Заполнить заявку» или отправьте /start.

Можно ли прикрепить документы?
Эта версия принимает текст. Перечислите документы словами; отправлять файлы не нужно.

Что происходит после отправки?
Заявка сохраняется. При настроенном чате администратора ему отправляется уведомление."""
INTRO = """ЗАПОЛНЕНИЕ ЗАЯВКИ

Предоставляйте только необходимую информацию. Не указывайте пароли, паспортные данные и другие секретные сведения. Для демонстрации используйте вымышленные ситуации.

Каждый ответ — до 800 символов. Отмена: /cancel."""
QUESTIONS = [
    "Кратко опишите ситуацию, с которой вы столкнулись.",
    "Какой основной вопрос вы хотели бы обсудить на встрече с адвокатом?",
    "Укажите дополнительные обстоятельства, которые могут иметь значение для вашей ситуации.",
    "Есть ли документы или другие материалы, относящиеся к ситуации? Перечислите их словами. Если нет — напишите «Нет».",
]
LABELS = ["Ситуация", "Основной вопрос", "Дополнительные обстоятельства", "Документы"]
IMAGES = {
    "welcome": "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?auto=format&fit=crop&w=1200&q=80",
    "about": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?auto=format&fit=crop&w=1200&q=80",
    "how": "https://images.unsplash.com/photo-1556761175-b413da4baf72?auto=format&fit=crop&w=1200&q=80",
    "application": "https://images.unsplash.com/photo-1456324504439-367cee3b3c32?auto=format&fit=crop&w=1200&q=80",
}


@dataclass(frozen=True)
class Settings:
    token: str
    admin_chat_id: int = 0
    mode: str = "polling"
    database_url: str = ""
    db_path: str = "data/applications.db"
    webhook_url: str = ""
    webhook_secret: str = ""
    port: int = 10000
    images_enabled: bool = True

    @classmethod
    def from_env(cls):
        load_dotenv()
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("Укажите BOT_TOKEN в .env или настройках сервера")
        mode = os.getenv("BOT_MODE", "polling").strip().lower()
        if mode not in {"polling", "webhook"}:
            raise ValueError("BOT_MODE должен быть polling или webhook")
        base_url = (os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
        secret = os.getenv("WEBHOOK_SECRET", "")
        if mode == "webhook":
            parsed = urlparse(base_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
                raise ValueError("WEBHOOK_BASE_URL должен быть HTTPS-адресом сервиса без пути")
            if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", secret):
                raise ValueError("WEBHOOK_SECRET: 16–256 символов A-Z, a-z, 0-9, _ или -")
        database_url = os.getenv("DATABASE_URL", "").strip()
        if os.getenv("RENDER_EXTERNAL_URL") and not database_url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
            raise ValueError("На Render укажите PostgreSQL DATABASE_URL: локальная SQLite не сохраняется")
        return cls(token=token, admin_chat_id=int(os.getenv("ADMIN_CHAT_ID", "0")),
                   mode=mode, database_url=database_url,
                   db_path=os.getenv("DB_PATH", "data/applications.db"),
                   webhook_url=base_url + WEBHOOK_PATH, webhook_secret=secret,
                   port=int(os.getenv("PORT", "10000")),
                   images_enabled=os.getenv("IMAGES_ENABLED", "true").lower() == "true")


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="О проекте", callback_data="about")
    kb.button(text="Как это работает", callback_data="how")
    kb.button(text="Заполнить заявку", callback_data="application")
    kb.button(text="Часто задаваемые вопросы", callback_data="faq")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def draft_keyboard(data):
    kb = InlineKeyboardBuilder()
    sid = data["session_id"]
    if data["step"] == 4:
        kb.button(text="Отправить заявку", callback_data=f"confirm:{sid}")
        for i, label in enumerate(LABELS):
            kb.button(text=f"Изменить: {label}", callback_data=f"edit:{sid}:{i}")
    kb.button(text="Отменить заявку", callback_data=f"cancel:{sid}")
    kb.adjust(1)
    return kb.as_markup()


async def send_section(message: Message, text: str, image: str | None, settings: Settings):
    if image and settings.images_enabled:
        try:
            await message.answer_photo(photo=IMAGES[image], caption=text, reply_markup=main_menu())
            return
        except TelegramAPIError:
            logger.warning("Изображение %s недоступно, отправляется текст", image)
    await message.answer(text, reply_markup=main_menu())


async def show_draft(message, data):
    if data["step"] == 4:
        text = "ПРОВЕРЬТЕ ЗАЯВКУ\n\n" + "\n\n".join(
            f"{label}:\n{answer}" for label, answer in zip(LABELS, data["answers"]))
        text += "\n\nПока заявка не отправлена. Проверьте ответы и нажмите «Отправить заявку»."
    else:
        step = data["step"]
        text = f"Шаг {step + 1} из 4.\n\n{QUESTIONS[step]}"
        if data["editing"]:
            text += f"\n\nТекущий ответ:\n{data['answers'][step]}\n\nПришлите новый вариант."
    await message.answer(text, reply_markup=draft_keyboard(data))


async def show_result(message, result):
    state = result["state"]
    if state == "draft":
        await show_draft(message, result["draft"])
    elif state == "submitted":
        await message.answer(f"ЗАЯВКА №{result['id']}\n\nВаша заявка сохранена. Благодарим за предоставленную информацию.", reply_markup=main_menu())
    elif state == "canceled":
        await message.answer("Незавершённая заявка удалена. Можно начать новую.", reply_markup=main_menu())
    elif state == "stale":
        await message.answer("Эта кнопка относится к завершённой или отменённой анкете. Нажмите «Заполнить заявку», чтобы продолжить текущую или начать новую.", reply_markup=main_menu())
    else:
        await message.answer("Чтобы начать, нажмите «Заполнить заявку».", reply_markup=main_menu())


def build_dispatcher(store: Store, settings: Settings):
    dp = Dispatcher()
    router = Router()
    # Questionnaire answers are accepted only in private chats.
    router.message.filter(F.chat.type == "private")
    router.callback_query.filter(F.message.chat.type == "private")

    def key(event_update):
        return f"{store.namespace}:{event_update.update_id}"

    @router.message(CommandStart())
    async def start(message: Message):
        await send_section(message, WELCOME, "welcome", settings)
        draft = await store.get_draft(message.from_user.id)
        if draft:
            await message.answer("У вас есть незавершённая анкета. Продолжим:")
            await show_draft(message, draft)

    @router.message(Command("help"))
    async def help_command(message: Message):
        await message.answer("/start — меню и продолжение анкеты\n/cancel — удалить незавершённую анкету\n/id — ID вашего чата\n/help — помощь", reply_markup=main_menu())

    @router.message(Command("id"))
    async def chat_id(message: Message):
        await message.answer(f"ID вашего чата: {message.chat.id}")

    @router.message(Command("cancel"))
    async def cancel(message: Message, event_update: Update):
        result = await store.action(message.from_user.id, None, "cancel", key(event_update))
        await show_result(message, result)

    @router.callback_query()
    async def callback(event: CallbackQuery, event_update: Update):
        if not isinstance(event.message, Message):
            await event.answer("Откройте личный чат с ботом")
            return
        try:
            await event.answer()
        except TelegramBadRequest:
            # Render's cold start can outlast Telegram's callback-answer window.
            # Still process the authenticated button press and send a new message.
            logger.info("Не удалось подтвердить callback, продолжаем обработку кнопки")
        message = event.message
        payload = event.data or ""
        if payload in {"about", "how", "faq"}:
            text = {"about": ABOUT, "how": HOW, "faq": FAQ}[payload]
            await send_section(message, text, payload if payload != "faq" else None, settings)
        elif payload == "application":
            result = await store.begin(event.from_user.id, event.from_user.username,
                                       event.from_user.full_name, key(event_update))
            await message.answer(INTRO)
            if settings.images_enabled:
                try:
                    await message.answer_photo(IMAGES["application"])
                except TelegramAPIError:
                    logger.warning("Изображение анкеты недоступно")
            await show_result(message, result)
        else:
            parts = payload.split(":")
            if len(parts) not in {2, 3} or parts[0] not in {"confirm", "cancel", "edit"}:
                return
            field = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else None
            result = await store.action(event.from_user.id, parts[1], parts[0], key(event_update), field)
            await show_result(message, result)

    @router.message(F.text.startswith("/"))
    async def unknown_command(message: Message):
        await message.answer("Неизвестная команда. Используйте /start, /help, /id или /cancel.")

    @router.message()
    async def answer(message: Message, event_update: Update):
        text = (message.text or "").strip()
        if not text:
            await message.answer("Пришлите текстовый ответ. Документы можно перечислить словами.")
            return
        if len(text) > MAX_ANSWER:
            await message.answer("Ответ слишком длинный. Сократите его до 800 символов; текущий шаг сохранён.")
            return
        result = await store.answer(message.from_user.id, text, key(event_update))
        await show_result(message, result)

    dp.include_router(router)
    return dp


class Notifier:
    def __init__(self, store, bot, chat_id):
        self.store, self.bot, self.chat_id = store, bot, chat_id
        self.task = None

    async def deliver(self):
        if not self.chat_id:
            return
        for item in await self.store.pending_notifications():
            text = (f"📩 НОВАЯ ЗАЯВКА №{item['id']}\n\n"
                    f"Платформа: Telegram\nПользователь: {item['full_name']}\n"
                    f"Username: {item['username'] or 'не указан'}\nID: {item['user_id']}\n\n")
            text += "\n\n━━━━━━━━━━━━\n\n".join(
                f"{label.upper()}:\n{answer}" for label, answer in zip(LABELS, item["answers"]))
            try:
                await self.bot.send_message(self.chat_id, text)
            except TelegramAPIError as error:
                logger.warning("Уведомление по заявке %s не доставлено (%s), повторим позже", item["id"], type(error).__name__)
                break
            await self.store.mark_notified(item["id"])

    async def run(self):
        while True:
            try:
                await self.deliver()
            except Exception as error:
                logger.warning("Ошибка уведомлений (%s), повторим позже", type(error).__name__)
            await asyncio.sleep(15)

    async def start(self):
        if self.chat_id:
            self.task = asyncio.create_task(self.run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task


def webhook_app(settings: Settings, store: Store, bot: Bot, dp: Dispatcher):
    notifier = Notifier(store, bot, settings.admin_chat_id)
    app = web.Application(client_max_size=1024 * 1024)

    async def startup(**kwargs):
        await store.initialize()
        await bot.set_webhook(settings.webhook_url, secret_token=settings.webhook_secret,
                              max_connections=1, allowed_updates=dp.resolve_used_update_types(),
                              drop_pending_updates=False)
        await notifier.start()

    async def shutdown(**kwargs):
        await notifier.stop()

    async def cleanup(application):
        await store.close()

    async def health(request):
        # No bot token or personal data in this response.
        return web.json_response({"status": "ok"})

    dp.startup.register(startup)
    dp.shutdown.register(shutdown)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret,
                         handle_in_background=False).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    app.router.add_get("/health", health)
    app.on_cleanup.append(cleanup)
    return app


async def polling(settings, store, bot, dp):
    notifier = Notifier(store, bot, settings.admin_chat_id)
    try:
        await store.initialize()
        await bot.delete_webhook(drop_pending_updates=False)
        await notifier.start()
        await dp.start_polling(bot, handle_as_tasks=False)
    finally:
        await notifier.stop()
        await bot.session.close()
        await store.close()


def main():
    logging.basicConfig(level=logging.INFO)
    settings = Settings.from_env()
    bot = Bot(settings.token)  # Plain text messages; user input is never parsed as HTML.
    store = Store(settings.database_url, settings.db_path,
                  namespace="telegram:" + str(bot.id))
    dp = build_dispatcher(store, settings)
    if settings.mode == "webhook":
        web.run_app(webhook_app(settings, store, bot, dp), host="0.0.0.0",
                    port=settings.port, access_log=None)
    else:
        asyncio.run(polling(settings, store, bot, dp))


if __name__ == "__main__":
    main()
