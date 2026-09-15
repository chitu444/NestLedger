# NestLedger Gemini Chatbot

This merge keeps the original NestLedger Flask + PostgreSQL + Vercel architecture.
The chatbot from the second project was integrated into that architecture instead of adding its Express/in-memory server.

## Vercel environment variable

Add this server-side environment variable in Vercel:

- `GEMINI_API_KEY` = your Google Gemini API key

Optional:

- `GEMINI_CHAT_MODEL` = `gemini-2.5-flash` (default)

The key is read only by the Flask backend. It is never placed in frontend JavaScript.

## Endpoint

Authenticated users call:

`POST /api/ai/chat`

The endpoint builds role-scoped context from the existing PostgreSQL/SQLAlchemy models and sends only authorized information to Gemini. Navigation actions are allowlisted before being returned to the browser.

The Express `server.js`, `package.json`, `bun.lock`, and in-memory database from the second project are intentionally not included.
