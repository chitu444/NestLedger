# NestLedger Foundation Architecture

## Frontend
- `js/core/state.js` owns session state and client-side permissions.
- `js/core/api.js` is the single request gateway: auth headers, short GET cache, in-flight deduplication, timeout and normalized errors.
- `js/core/router.js` owns URL/page navigation and browser history.
- `js/app.js` remains the page/component layer for the current release; page renderers can be split into `pages/` incrementally without changing the router/API contract.

Navigation now uses direct route lookup and updates the active page without rebuilding the entire application shell on every click.

## Backend
- `utils/auth.py` centralizes safe JWT identity -> user resolution.
- `services/finance.py` and `services/operations.py` keep reusable database aggregates outside HTTP route handlers.
- `utils/audit.py` records important state changes.
- `models/audit_log.py` persists audit events.
- Performance indexes are applied additively at startup for high-frequency filters.

## Request lifecycle

`UI -> Router -> Page -> API gateway -> Flask route -> service/query -> database`

Authentication and authorization are checked again on the server; client permissions are only for presentation and navigation.

## Work-order lifecycle

`open -> accepted -> in_progress -> completed`

A vendor may withdraw from `accepted` or `in_progress`, returning the order to `open`. A resident may cancel only an `open` request. Terminal states cannot be reopened through the generic status endpoint.
