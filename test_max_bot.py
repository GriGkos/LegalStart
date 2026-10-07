import os
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import max_bot
from max_bot import Handler, MaxAPI, MaxAPIError, Notifier, Settings, max_ssl_context, webhook_app
from storage import Store


class FakeAPI:
    def __init__(self):
        self.messages = []
        self.acks = []
        self.fail = False

    async def send(self, chat_id, text, keyboard=None):
        if self.fail:
            raise MaxAPIError(503)
        if len(text) > 4000:
            raise AssertionError("MAX message limit exceeded")
        self.messages.append((chat_id, text, keyboard))

    async def acknowledge(self, callback_id, chat_id):
        self.acks.append((callback_id, chat_id))


def message(text, mid, chat_type="dialog", *, user_id=77, chat_id=1234):
    return {"update_type": "message_created", "timestamp": 1,
            "message": {"sender": {"user_id": user_id, "first_name": "Тест", "is_bot": False},
                        "recipient": {"chat_type": chat_type, "chat_id": chat_id},
                        "body": {"mid": mid, "seq": 1, "text": text}}}


def callback(payload, callback_id, chat_type="dialog"):
    event = message("bot message", "bot-message", chat_type)
    event["update_type"] = "message_callback"
    event["callback"] = {"callback_id": callback_id, "timestamp": 1,
                         "payload": payload, "user": event["message"]["sender"]}
    event["message"]["sender"] = {"user_id": 42, "is_bot": True}
    return event


class MaxFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "test.db")
        self.store = Store(db_path=self.db_path, namespace="max:42")
        await self.store.initialize()
        self.api = FakeAPI()
        self.handler = Handler(self.store, self.api)

    async def asyncTearDown(self):
        await self.store.close()
        self.temp.cleanup()

    async def complete_draft(self, answer="Ответ"):
        await self.handler.handle(callback("application", "begin"))
        for i in range(4):
            await self.handler.handle(message(answer, f"answer-{i}"))
        return await self.store.get_draft(77)

    async def test_review_edit_confirm_and_duplicate_delivery(self):
        draft = await self.complete_draft()
        sid = draft["session_id"]
        self.assertEqual(draft["step"], 4)
        self.assertEqual(await self.store.pending_notifications(), [])
        await self.handler.handle(callback(f"edit:{sid}:1", "edit"))
        await self.handler.handle(message("Исправлено", "replacement"))
        await self.handler.handle(callback(f"confirm:{sid}", "confirm"))
        await self.handler.handle(callback(f"confirm:{sid}", "confirm"))
        await self.handler.handle(callback(f"confirm:{sid}", "confirm-new"))
        items = await self.store.pending_notifications()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["answers"], ["Ответ", "Исправлено", "Ответ", "Ответ"])
        self.assertIsNone(await self.store.get_draft(77))

    async def test_failed_reply_retry_does_not_advance_again(self):
        await self.handler.handle(callback("application", "begin"))
        self.api.fail = True
        with self.assertRaises(MaxAPIError):
            await self.handler.handle(message("Первый ответ", "one"))
        self.api.fail = False
        await self.handler.handle(message("Первый ответ", "one"))
        draft = await self.store.get_draft(77)
        self.assertEqual(draft["step"], 1)
        self.assertEqual(draft["answers"], ["Первый ответ", "", "", ""])

    async def test_cancel_and_stale_button_cannot_touch_new_draft(self):
        await self.handler.handle(callback("application", "begin"))
        old_sid = (await self.store.get_draft(77))["session_id"]
        await self.handler.handle(message("/cancel", "cancel"))
        await self.handler.handle(callback("application", "new-begin"))
        new_sid = (await self.store.get_draft(77))["session_id"]
        await self.handler.handle(callback(f"cancel:{old_sid}", "stale"))
        self.assertEqual((await self.store.get_draft(77))["session_id"], new_sid)

    async def test_restart_resumes_and_telegram_namespace_is_separate(self):
        await self.handler.handle(callback("application", "begin"))
        await self.handler.handle(message("Ответ 1", "one"))
        await self.store.close()
        self.store = Store(db_path=self.db_path, namespace="max:42")
        self.handler = Handler(self.store, self.api)
        await self.handler.handle(message("/start", "restart"))
        self.assertIn("Шаг 2 из 4", self.api.messages[-1][1])
        other = Store(db_path=self.db_path, namespace="telegram:42")
        try:
            self.assertIsNone(await other.get_draft(77))
            self.assertEqual(await other.pending_notifications(), [])
        finally:
            await other.close()

    async def test_group_and_channel_callbacks_ignored(self):
        for chat_type in ("chat", "channel"):
            await self.handler.handle(callback("application", "begin", chat_type))
            await self.handler.handle(message("/start", "start", chat_type))
        deleted = callback("application", "deleted")
        deleted["message"] = None
        await self.handler.handle(deleted)
        self.assertEqual(self.api.messages, [])
        self.assertEqual(self.api.acks, [])
        self.assertIsNone(await self.store.get_draft(77))

    async def test_id_distinguishes_chat_from_user(self):
        await self.handler.handle(message("/id", "id"))
        self.assertIn("ID вашего чата MAX: 1234", self.api.messages[-1][1])
        self.assertIn("ID пользователя MAX: 77", self.api.messages[-1][1])

    async def test_media_and_long_answer_do_not_advance(self):
        await self.handler.handle(callback("application", "begin"))
        await self.handler.handle(message(None, "photo"))
        await self.handler.handle(message("я" * 801, "long"))
        missing_id = message("no receipt", "")
        await self.handler.handle(missing_id)
        self.assertEqual((await self.store.get_draft(77))["step"], 0)

    async def test_bot_started_shows_menu(self):
        await self.handler.handle({"update_type": "bot_started", "timestamp": 1,
                                   "chat_id": 1234, "user": {"user_id": 77, "is_bot": False}})
        self.assertIn("Добро пожаловать", self.api.messages[-1][1])

    async def test_notification_failure_then_retry_and_message_length(self):
        draft = await self.complete_draft("я" * 800)
        await self.handler.handle(callback(f"confirm:{draft['session_id']}", "confirm"))
        notifier = Notifier(self.store, self.api, 9876)
        self.api.fail = True
        await notifier.deliver()
        self.assertEqual(len(await self.store.pending_notifications()), 1)
        self.api.fail = False
        await notifier.deliver()
        self.assertEqual(await self.store.pending_notifications(), [])
        self.assertEqual(self.api.messages[-1][0], 9876)
        self.assertIn("Платформа: MAX", self.api.messages[-1][1])

    async def test_authenticated_webhook_and_retry_response(self):
        settings = Settings("dummy", "https://example.org/max/webhook", "secret_1234567890")
        client = TestClient(TestServer(webhook_app(settings, self.handler)))
        await client.start_server()
        try:
            event = callback("application", "begin")
            response = await client.post("/max/webhook", json=event)
            self.assertEqual(response.status, 401)
            self.assertIsNone(await self.store.get_draft(77))
            headers = {"X-Max-Bot-Api-Secret": settings.webhook_secret}
            self.api.fail = True
            response = await client.post("/max/webhook", json=event, headers=headers)
            self.assertEqual(response.status, 503)
            self.api.fail = False
            response = await client.post("/max/webhook", json=event, headers=headers)
            self.assertEqual(response.status, 200)
            response = await client.post("/max/webhook", json=[], headers=headers)
            self.assertEqual(response.status, 400)
            health = await client.get("/health")
            self.assertEqual(await health.json(), {"status": "ok"})
        finally:
            await client.close()


class MaxConfigurationTests(unittest.TestCase):
    def test_ca_scoped_and_verification_enabled(self):
        context = max_ssl_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertTrue(any(dict(part[0] for part in cert["subject"]).get("commonName") ==
                            "Russian Trusted Root CA" for cert in context.get_ca_certs()))

    def test_render_settings_and_separate_secret(self):
        values = {"MAX_BOT_TOKEN": "dummy", "MAX_WEBHOOK_SECRET": "secret_1234567890",
                  "RENDER_EXTERNAL_URL": "https://max.example.org", "MAX_ADMIN_CHAT_ID": "1234",
                  "DATABASE_URL": "postgresql://dummy:dummy@example.org/db"}
        with patch.dict(os.environ, values, clear=True), patch("max_bot.load_dotenv"):
            settings = Settings.from_env()
            self.assertEqual(settings.webhook_url, "https://max.example.org/max/webhook")
            self.assertEqual(settings.admin_chat_id, 1234)
            with patch.dict(os.environ, {"DATABASE_URL": ""}):
                with self.assertRaises(ValueError):
                    Settings.from_env()
            with patch.dict(os.environ, {"MAX_WEBHOOK_BASE_URL": "https://example.org:8443"}):
                with self.assertRaises(ValueError):
                    Settings.from_env()


class MaxWireTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_json_shape_and_header_authorization(self):
        requests = []

        async def receiver(request):
            requests.append((request.path, dict(request.query), request.headers.get("Authorization"), await request.json()))
            return web.json_response({"success": True})

        app = web.Application()
        app.router.add_post("/{name}", receiver)
        server = TestServer(app)
        await server.start_server()
        api = MaxAPI("dummy-test-token")
        try:
            with patch("max_bot.API_URL", str(server.make_url("")).rstrip("/")):
                await api.send(1234, "Текст", max_bot.main_menu())
                await api.acknowledge("callback-1", 1234)
            path, query, authorization, body = requests[0]
            self.assertEqual(path, "/messages")
            self.assertEqual(query, {"chat_id": "1234"})
            self.assertEqual(authorization, "dummy-test-token")
            self.assertEqual(body["attachments"][0]["type"], "inline_keyboard")
            self.assertEqual(body["attachments"][0]["payload"]["buttons"][1][0]["payload"], "application")
            self.assertNotIn("format", body)
            self.assertEqual(requests[1][1], {"callback_id": "callback-1"})
        finally:
            await api.close()
            await server.close()


if __name__ == "__main__":
    unittest.main()
