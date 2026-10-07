"""Offline checks: no real token, Telegram requests or personal data."""
import tempfile
import unittest
import ssl
from pathlib import Path
from datetime import datetime, timezone

from aiohttp.test_utils import TestClient, TestServer
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.methods import (AnswerCallbackQuery, DeleteWebhook, GetMe,
                             SendMessage, SendPhoto, SetWebhook)
from aiogram.types import Chat, Message, Update, User
from sqlalchemy import select

from bot import (ABOUT, FAQ, HOW, WELCOME, MAX_ANSWER, Notifier, Settings,
                 build_dispatcher, main_menu, webhook_app, WEBHOOK_PATH)
from storage import Store, applications, events, postgres_ssl_context

TOKEN = "123456:OFFLINE_TEST_TOKEN_NOT_REAL"
USER = {"id": 42, "is_bot": False, "first_name": "Тест", "username": "test_user"}


class DatabaseTLSChecks(unittest.TestCase):
    def test_supabase_root_is_trusted_with_hostname_verification(self):
        certificate = (Path(__file__).parent / "certs" / "supabase-prod-ca-2021.crt").read_text()
        root = ssl.PEM_cert_to_DER_cert(certificate)
        for host in ("aws-0-eu-central-1.pooler.supabase.com", "db.example.supabase.co"):
            context = postgres_ssl_context(host)
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertIn(root, context.get_ca_certs(binary_form=True))

    def test_other_database_hosts_use_only_system_trust(self):
        baseline = ssl.create_default_context().get_ca_certs(binary_form=True)
        for host in ("database.example.com", "pooler.supabase.com.attacker.example", None):
            context = postgres_ssl_context(host)
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertEqual(context.get_ca_certs(binary_form=True), baseline)


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent = []
        self.fail_admin_once = False
        self.expired_callback_once = False

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        self.sent.append(method)
        if isinstance(method, GetMe):
            return User(id=123456, is_bot=True, first_name="Offline", username="offline_test_bot")
        if isinstance(method, (SetWebhook, DeleteWebhook, AnswerCallbackQuery)):
            if isinstance(method, AnswerCallbackQuery) and self.expired_callback_once:
                self.expired_callback_once = False
                raise TelegramBadRequest(method=method, message="query is too old")
            return True
        if isinstance(method, (SendMessage, SendPhoto)):
            if isinstance(method, SendMessage) and method.chat_id == 99 and self.fail_admin_once:
                self.fail_admin_once = False
                raise TelegramForbiddenError(method=method, message="offline simulated failure")
            content = getattr(method, "text", None) or getattr(method, "caption", None) or ""
            assert len(content) <= (1024 if isinstance(method, SendPhoto) else 4096)
            return Message(message_id=len(self.sent), date=datetime.now(timezone.utc),
                           chat=Chat(id=int(method.chat_id), type="private"), text=content)
        raise AssertionError("Unexpected API call: " + type(method).__name__)

    async def stream_content(self, url, **kwargs):
        raise AssertionError("No downloads in offline checks")
        yield b""


def message_update(number, text=None, chat_type="private"):
    message = {"message_id": number, "date": 1700000000,
               "chat": {"id": 42, "type": chat_type}, "from": USER}
    if text is not None:
        message["text"] = text
        if text.startswith("/"):
            message["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
    return Update.model_validate({"update_id": number, "message": message})


def callback_update(number, payload):
    return Update.model_validate({"update_id": number, "callback_query": {
        "id": f"cb{number}", "from": USER, "chat_instance": "offline",
        "data": payload, "message": {"message_id": 1, "date": 1700000000,
                                      "chat": {"id": 42, "type": "private"}}}})


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "bot.db")
        self.store = Store(db_path=self.db_path, namespace="telegram:123456")
        await self.store.initialize()
        self.session = FakeSession()
        self.bot = Bot(TOKEN, session=self.session)
        self.settings = Settings(token=TOKEN, images_enabled=False)
        self.dp = build_dispatcher(self.store, self.settings)

    async def asyncTearDown(self):
        await self.store.close()
        await self.bot.session.close()
        self.temp.cleanup()

    async def feed(self, event):
        return await self.dp.feed_update(self.bot, event)

    async def begin(self, update_id=1):
        await self.feed(callback_update(update_id, "application"))
        return await self.store.get_draft(42)

    async def fill(self):
        for number in range(2, 6):
            await self.feed(message_update(number, f"Ответ {number - 1}"))
        return await self.store.get_draft(42)

    async def test_four_questions_review_edit_confirm_and_duplicate(self):
        data = await self.begin()
        data = await self.fill()
        self.assertEqual(data["step"], 4)
        self.assertEqual(await self.store.pending_notifications(), [])
        await self.feed(callback_update(6, "edit:" + data["session_id"] + ":1"))
        await self.feed(message_update(7, "Исправленный вопрос"))
        data = await self.store.get_draft(42)
        self.assertEqual(data["step"], 4)
        self.assertEqual(data["answers"][1], "Исправленный вопрос")
        confirm = callback_update(8, "confirm:" + data["session_id"])
        await self.feed(confirm)
        await self.feed(confirm)
        await self.feed(callback_update(9, "confirm:" + data["session_id"]))
        self.assertIsNone(await self.store.get_draft(42))
        self.assertEqual(len(await self.store.pending_notifications()), 1)

    async def test_retry_of_answer_does_not_advance_twice(self):
        await self.begin()
        event = message_update(2, "Ситуация")
        await self.feed(event)
        await self.feed(event)
        data = await self.store.get_draft(42)
        self.assertEqual(data["step"], 1)
        self.assertEqual(data["answers"], ["Ситуация", "", "", ""])

    async def test_restore_after_restart(self):
        await self.begin()
        await self.feed(message_update(2, "Первый ответ"))
        await self.store.close()
        self.store = Store(db_path=self.db_path, namespace="telegram:123456")
        await self.store.initialize()
        self.dp = build_dispatcher(self.store, self.settings)
        self.assertEqual((await self.store.get_draft(42))["step"], 1)
        await self.feed(message_update(3, "/start criminal"))
        last = [m for m in self.session.sent if isinstance(m, SendMessage)][-1]
        self.assertIn("Шаг 2 из 4", last.text)

    async def test_cancel_stale_buttons_and_user_platform_isolation(self):
        old = await self.begin()
        await self.feed(message_update(2, "/cancel"))
        new = await self.begin(3)
        await self.feed(callback_update(4, "cancel:" + old["session_id"]))
        self.assertEqual((await self.store.get_draft(42))["session_id"], new["session_id"])
        other = Store(db_path=self.db_path, namespace="max")
        try:
            await other.initialize()
            self.assertIsNone(await other.get_draft(42))
            await other.begin(42, "max_user", "MAX", "max:1")
            self.assertEqual((await self.store.get_draft(42))["session_id"], new["session_id"])
        finally:
            await other.close()

    async def test_commands_media_and_long_text_keep_current_step(self):
        await self.begin()
        for number, text in [(2, "/help"), (3, "/unknown"), (4, "X" * (MAX_ANSWER + 1)), (7, "/id")]:
            await self.feed(message_update(number, text))
        await self.feed(message_update(5))
        self.assertEqual((await self.store.get_draft(42))["step"], 0)
        await self.feed(message_update(6, "X" * MAX_ANSWER))
        self.assertEqual((await self.store.get_draft(42))["step"], 1)

    async def test_expired_callback_after_cold_start_still_processes_form(self):
        self.session.expired_callback_once = True
        data = await self.begin()
        self.assertEqual(data["step"], 0)

    async def test_cancel_leaves_no_answers_in_retry_receipts(self):
        await self.begin()
        await self.feed(message_update(2, "UNIQUE_PRIVATE_TEST_ANSWER"))
        await self.feed(message_update(3, "/cancel"))
        async with self.store.engine.connect() as conn:
            receipts = list((await conn.execute(select(events.c.result))).scalars())
        self.assertNotIn("UNIQUE_PRIVATE_TEST_ANSWER", " ".join(receipts))

    async def test_private_chat_only(self):
        await self.feed(message_update(1, "/start", chat_type="group"))
        self.assertEqual(self.session.sent, [])

    async def test_admin_notification_retry_preserves_application(self):
        await self.begin()
        data = await self.fill()
        await self.feed(callback_update(6, "confirm:" + data["session_id"]))
        notifier = Notifier(self.store, self.bot, 99)
        self.session.fail_admin_once = True
        await notifier.deliver()
        self.assertEqual(len(await self.store.pending_notifications()), 1)
        await notifier.deliver()
        self.assertEqual(len(await self.store.pending_notifications()), 0)
        async with self.store.engine.connect() as conn:
            self.assertEqual(len((await conn.execute(select(applications))).all()), 1)

    async def test_menus_and_caption_lengths(self):
        self.assertEqual(sum(len(row) for row in main_menu().inline_keyboard), 4)
        for text in [WELCOME, ABOUT, HOW]:
            self.assertLessEqual(len(text), 1024)
        for number, payload in enumerate(["about", "how", "faq"], start=1):
            await self.feed(callback_update(number, payload))
        self.assertIn(FAQ, [m.text for m in self.session.sent if isinstance(m, SendMessage)])

    async def test_webhook_secret_and_offline_delivery(self):
        settings = Settings(token=TOKEN, mode="webhook", images_enabled=False,
                            webhook_url="https://example.invalid" + WEBHOOK_PATH,
                            webhook_secret="offline-test-secret")
        app = webhook_app(settings, self.store, self.bot, self.dp)
        async with TestClient(TestServer(app)) as client:
            health = await client.get("/health")
            self.assertEqual(health.status, 200)
            body = message_update(100, "/start").model_dump(mode="json", exclude_none=True)
            rejected = await client.post(WEBHOOK_PATH, json=body)
            self.assertEqual(rejected.status, 401)
            accepted = await client.post(WEBHOOK_PATH, json=body,
                headers={"X-Telegram-Bot-Api-Secret-Token": settings.webhook_secret})
            self.assertEqual(accepted.status, 200)
            registered = next(m for m in self.session.sent if isinstance(m, SetWebhook))
            self.assertEqual(registered.secret_token, settings.webhook_secret)
            self.assertEqual(registered.max_connections, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
