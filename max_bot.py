"""LegalStart MAX bot, using the official HTTPS API and persistent drafts."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import re
import ssl
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from aiohttp import web
from dotenv import load_dotenv

from bot import ABOUT, FAQ, HOW, INTRO, LABELS, MAX_ANSWER, QUESTIONS, WELCOME
from storage import Store

API_URL = "https://platform-api2.max.ru"
WEBHOOK_PATH = "/max/webhook"
logger = logging.getLogger("legalstart.max")


def max_ssl_context():
    # This additional CA is used only by the MAX API client, never globally.
    context = ssl.create_default_context()
    context.load_verify_locations(str(Path(__file__).parent / "certs" /
                                      "russian-trusted-root-ca.crt"))
    return context


@dataclass(frozen=True)
class Settings:
    token: str
    webhook_url: str
    webhook_secret: str
    admin_chat_id: int = 0
    database_url: str = ""
    db_path: str = "data/max-applications.db"
    port: int = 10000

    @classmethod
    def from_env(cls):
        load_dotenv()
        token = os.getenv("MAX_BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("Укажите MAX_BOT_TOKEN в настройках сервера")
        base = (os.getenv("MAX_WEBHOOK_BASE_URL") or
                os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
        parsed = urlparse(base)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.path or
                parsed.query or parsed.fragment or parsed.username or
                parsed.port not in (None, 443)):
            raise ValueError("MAX_WEBHOOK_BASE_URL: HTTPS-адрес без пути, внешний порт 443")
        secret = os.getenv("MAX_WEBHOOK_SECRET", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", secret):
            raise ValueError("MAX_WEBHOOK_SECRET: 16–256 символов A-Z, a-z, 0-9, _ или -")
        database_url = os.getenv("DATABASE_URL", "").strip()
        if os.getenv("RENDER_EXTERNAL_URL") and not database_url.startswith(
                ("postgres://", "postgresql://", "postgresql+asyncpg://")):
            raise ValueError("На Render нужен PostgreSQL DATABASE_URL; SQLite не сохраняется")
        return cls(token, base + WEBHOOK_PATH, secret,
                   int(os.getenv("MAX_ADMIN_CHAT_ID", "0")), database_url,
                   os.getenv("MAX_DB_PATH", "data/max-applications.db"),
                   int(os.getenv("PORT", "10000")))


class MaxAPIError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(f"MAX API HTTP {status}")


class MaxAPI:
    def __init__(self, token):
        self.session = aiohttp.ClientSession(
            headers={"Authorization": token},
            connector=aiohttp.TCPConnector(ssl=max_ssl_context()),
            timeout=aiohttp.ClientTimeout(total=8))
        self.rate_lock = asyncio.Lock()
        self.last_request = 0.0
        self.last_chat = {}

    async def request(self, method, path, *, params=None, body=None, chat_id=None):
        # Below the global 30 req/s and the two messages/s per-chat limits.
        async with self.rate_lock:
            now = time.monotonic()
            delay = max(0, self.last_request + .06 - now)
            if chat_id is not None:
                delay = max(delay, self.last_chat.get(chat_id, 0) + .6 - now)
            await asyncio.sleep(delay)
            self.last_request = time.monotonic()
            if chat_id is not None:
                self.last_chat[chat_id] = self.last_request
                # Do not retain an unbounded map of inactive chats.
                if len(self.last_chat) > 2000:
                    self.last_chat = {k: v for k, v in self.last_chat.items()
                                      if v > self.last_request - 2}
        async with self.session.request(method, API_URL + path, params=params,
                                        json=body, allow_redirects=False) as response:
            if response.status != 200:
                raise MaxAPIError(response.status)
            data = await response.json()
            if data.get("success") is False:
                raise MaxAPIError(400)
            return data

    async def send(self, chat_id, text, keyboard=None):
        if len(text) > 4000:
            raise ValueError("Сообщение MAX длиннее 4000 символов")
        body = {"text": text}
        if keyboard:
            body["attachments"] = [keyboard]
        return await self.request("POST", "/messages", params={"chat_id": chat_id},
                                  body=body, chat_id=chat_id)

    async def acknowledge(self, callback_id, chat_id):
        try:
            await self.request("POST", "/answers", params={"callback_id": callback_id},
                               body={"notification": "Принято"}, chat_id=chat_id)
        except MaxAPIError as error:
            if error.status not in (400, 404):
                raise
            # A cold start can outlast the callback window. Still handle it.
            logger.info("Callback устарел; продолжаем обработку кнопки")

    async def close(self):
        await self.session.close()


def button(text, payload):
    return {"type": "callback", "text": text, "payload": payload}


def keyboard(rows):
    return {"type": "inline_keyboard", "payload": {"buttons": rows}}


def main_menu():
    return keyboard([
        [button("О проекте", "about"), button("Как это работает", "how")],
        [button("Заполнить заявку", "application")],
        [button("Часто задаваемые вопросы", "faq")],
    ])


def draft_keyboard(data):
    sid = data["session_id"]
    rows = []
    if data["step"] == 4:
        rows.append([button("Отправить заявку", f"confirm:{sid}")])
        rows.extend([button(f"Изменить: {label}", f"edit:{sid}:{i}")]
                    for i, label in enumerate(LABELS))
    rows.append([button("Отменить заявку", f"cancel:{sid}")])
    return keyboard(rows)


class Handler:
    def __init__(self, store, api):
        self.store, self.api = store, api
        self.lock = asyncio.Lock()

    async def show_draft(self, chat_id, data):
        if data["step"] == 4:
            text = "ПРОВЕРЬТЕ ЗАЯВКУ\n\n" + "\n\n".join(
                f"{label}:\n{answer}" for label, answer in zip(LABELS, data["answers"]))
            text += "\n\nПока заявка не отправлена. Нажмите «Отправить заявку» после проверки."
        else:
            step = data["step"]
            text = f"Шаг {step + 1} из 4.\n\n{QUESTIONS[step]}"
            if data["editing"]:
                text += f"\n\nТекущий ответ:\n{data['answers'][step]}\n\nПришлите новый вариант."
        await self.api.send(chat_id, text, draft_keyboard(data))

    async def show_result(self, chat_id, result):
        state = result["state"]
        if state == "draft":
            await self.show_draft(chat_id, result["draft"])
            return
        text = {
            "submitted": f"ЗАЯВКА №{result.get('id')}\n\nВаша заявка сохранена. Благодарим за предоставленную информацию.",
            "canceled": "Незавершённая заявка удалена. Можно начать новую.",
            "stale": "Эта кнопка относится к завершённой или отменённой анкете. Нажмите «Заполнить заявку», чтобы продолжить текущую или начать новую.",
        }.get(state, "Чтобы начать, нажмите «Заполнить заявку».")
        await self.api.send(chat_id, text, main_menu())

    def event_key(self, kind, identifier):
        digest = hashlib.sha256(str(identifier).encode()).hexdigest()
        return f"{self.store.namespace}:{kind}:{digest}"

    async def handle(self, event):
        async with self.lock:
            await self._handle(event)

    async def _handle(self, event):
        kind = event.get("update_type")
        if kind == "bot_started":
            user = event.get("user") or {}
            chat_id = event.get("chat_id")
            payload = "start"
            event_key = None  # Starting the menu does not change a draft.
        elif kind in ("message_created", "message_callback"):
            message = event.get("message") or {}
            recipient = message.get("recipient") or {}
            if recipient.get("chat_type") != "dialog":
                return
            chat_id = recipient.get("chat_id")
            body = message.get("body") or {}
            if kind == "message_callback":
                callback = event.get("callback") or {}
                user = callback.get("user") or {}
                payload = callback.get("payload") or ""
                identifier = callback.get("callback_id")
            else:
                user = message.get("sender") or {}
                payload = body.get("text") or ""
                identifier = body.get("mid")
            if not isinstance(identifier, str) or not identifier:
                return
            event_key = self.event_key(kind, identifier)
        else:
            return
        user_id = user.get("user_id")
        if (type(chat_id) is not int or type(user_id) is not int or
                user_id <= 0 or user.get("is_bot")):
            return
        if not isinstance(payload, str):
            return
        if kind == "message_callback":
            await self.api.acknowledge(identifier, chat_id)
            if payload in ("about", "how", "faq"):
                await self.api.send(chat_id, {"about": ABOUT, "how": HOW, "faq": FAQ}[payload], main_menu())
            elif payload == "application":
                name = user.get("name") or " ".join(
                    str(user.get(field) or "") for field in ("first_name", "last_name")).strip()
                result = await self.store.begin(user_id, (user.get("username") or "")[:128],
                                                name[:256], event_key)
                await self.api.send(chat_id, INTRO)
                await self.show_result(chat_id, result)
            else:
                match = re.fullmatch(r"(confirm|cancel|edit):([0-9a-f]{32})(?::([0-3]))?", payload)
                if not match:
                    return
                action, sid, field = match.groups()
                if (action == "edit") != (field is not None):
                    return
                result = await self.store.action(user_id, sid, action, event_key,
                                                 int(field) if field else None)
                await self.show_result(chat_id, result)
            return
        text = payload.strip()
        command = text.split(maxsplit=1)[0].lower() if text else ""
        if kind == "bot_started" or command == "/start":
            await self.api.send(chat_id, WELCOME, main_menu())
            draft = await self.store.get_draft(user_id)
            if draft:
                await self.show_draft(chat_id, draft)
        elif command == "/id":
            await self.api.send(chat_id, f"ID вашего чата MAX: {chat_id}\nID пользователя MAX: {user_id}\n\nДля MAX_ADMIN_CHAT_ID используйте ID чата из первой строки.")
        elif command == "/help":
            await self.api.send(chat_id, "/start — меню и продолжение анкеты\n/cancel — удалить незавершённую анкету\n/id — ID чата MAX\n/help — помощь", main_menu())
        elif command == "/cancel":
            result = await self.store.action(user_id, None, "cancel", event_key)
            await self.show_result(chat_id, result)
        elif text.startswith("/"):
            await self.api.send(chat_id, "Неизвестная команда. Используйте /start, /help, /id или /cancel.")
        elif not text:
            await self.api.send(chat_id, "Пришлите текстовый ответ. Документы можно перечислить словами.")
        elif len(text) > MAX_ANSWER:
            await self.api.send(chat_id, "Ответ слишком длинный. Сократите его до 800 символов; текущий шаг сохранён.")
        else:
            result = await self.store.answer(user_id, text, event_key)
            await self.show_result(chat_id, result)


class Notifier:
    def __init__(self, store, api, chat_id):
        self.store, self.api, self.chat_id = store, api, chat_id
        self.task = None

    async def deliver(self):
        if not self.chat_id:
            return
        for item in await self.store.pending_notifications():
            text = (f"📩 НОВАЯ ЗАЯВКА №{item['id']}\n\nПлатформа: MAX\n"
                    f"Пользователь: {item['full_name']}\n"
                    f"Username: {item['username'] or 'не указан'}\nID MAX: {item['user_id']}\n\n")
            text += "\n\n━━━━━━━━━━━━\n\n".join(
                f"{label.upper()}:\n{answer}" for label, answer in zip(LABELS, item["answers"]))
            try:
                await self.api.send(self.chat_id, text)
            except (MaxAPIError, aiohttp.ClientError, asyncio.TimeoutError) as error:
                logger.warning("Уведомление %s не доставлено (%s); повторим позже", item["id"], type(error).__name__)
                break
            await self.store.mark_notified(item["id"])

    async def run(self):
        while True:
            try:
                await self.deliver()
            except Exception as error:
                logger.warning("Ошибка уведомлений (%s); повторим позже", type(error).__name__)
            await asyncio.sleep(15)

    async def start(self):
        if self.chat_id:
            self.task = asyncio.create_task(self.run())

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task


def webhook_app(settings, handler):
    app = web.Application(client_max_size=1024 * 1024)

    async def webhook(request):
        secret = request.headers.get("X-Max-Bot-Api-Secret", "")
        if not hmac.compare_digest(secret.encode(), settings.webhook_secret.encode()):
            raise web.HTTPUnauthorized()
        try:
            event = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise web.HTTPBadRequest()
        if not isinstance(event, dict):
            raise web.HTTPBadRequest()
        try:
            # A non-200 response tells MAX to retry. Persisted receipts prevent
            # duplicate steps/submissions if processing succeeded before failure.
            await asyncio.wait_for(handler.handle(event), timeout=25)
        except Exception as error:
            logger.warning("Обработка MAX не завершена (%s); ожидаем повтор", type(error).__name__)
            raise web.HTTPServiceUnavailable()
        return web.json_response({"success": True})

    async def health(request):
        return web.json_response({"status": "ok"})

    app.router.add_post(WEBHOOK_PATH, webhook)
    app.router.add_get("/health", health)
    return app


async def application():
    settings = Settings.from_env()
    api = MaxAPI(settings.token)
    store = None
    try:
        info = await api.request("GET", "/me")
        bot_id = info.get("user_id")
        if type(bot_id) is not int or not info.get("is_bot"):
            raise ValueError("MAX API вернул некорректные сведения о боте")
        store = Store(settings.database_url, settings.db_path, namespace=f"max:{bot_id}")
        await store.initialize()
        handler = Handler(store, api)
        notifier = Notifier(store, api, settings.admin_chat_id)
        app = webhook_app(settings, handler)
        await api.request("POST", "/subscriptions", body={
            "url": settings.webhook_url, "secret": settings.webhook_secret,
            "update_types": ["message_created", "message_callback", "bot_started"],
        })
        await notifier.start()
    except BaseException:
        await api.close()
        if store:
            await store.close()
        raise

    async def cleanup(app):
        await notifier.stop()
        await api.close()
        await store.close()

    app.on_cleanup.append(cleanup)
    logger.info("MAX-бот %s готов к запуску сервера webhook", bot_id)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        web.run_app(application(), host="0.0.0.0", port=int(os.getenv("PORT", "10000")),
                    access_log=None)
    except Exception as error:
        # Avoid printing URLs/passwords, tokens or questionnaire contents.
        logger.error("Не удалось запустить MAX-бота (%s). Проверьте настройки сервиса.", type(error).__name__)
        raise SystemExit(1)
