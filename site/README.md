# Сайт LegalStart

Исходники лендинга из LegalStart-source.zip: React 19, TypeScript, Vite 7, Tailwind CSS 4 и Lucide. Отдельного backend или базы данных у сайта нет. Кнопки ведут во внешние мессенджеры.

## Локальный запуск

Нужен Node.js 24 и npm. Из этой папки:

```text
npm ci
npm run dev
```

## Сборка

```text
npm run build
```

Результат — папка `dist`, включая главную страницу и страницы `/privacy`, `/terms`. Файлы сборки и `node_modules` не нужно добавлять в GitHub.

## Netlify

Подключите репозиторий `GriGkos/LegalStart`. Корневой `netlify.toml` уже задаёт папку сайта `site`, команду `npm run build`, публикацию `dist` относительно папки сайта и Node.js 24.

Если сайт уже был размещён через Netlify Drop, его можно продолжать обновлять вручную, загружая новую папку `dist`, либо подключить GitHub для автоматических сборок.

## Ссылки на ботов

Username Telegram находится в `src/config.ts`, константа `TELEGRAM_BOT_USERNAME`. Сейчас это `ADVOKAT_PROJECTBOT`; проверьте, что это username нужного бота. Ссылка MAX пока пустая (`MAX_BOT_URL`).

В `index.html` и `scripts/static-routes.mjs` остаётся адрес прежнего размещения для метаданных. После получения нового адреса его можно заменить.

Telegram-бот находится в корне репозитория и размещается отдельно на Render. Настройки Netlify не меняют его запуск.
