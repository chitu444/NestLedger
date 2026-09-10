# Resident quotation fix

## What changed
- Resident work-order cards now always expose **View quotes** while a request is open, even when the cached work-order list does not contain a quote count.
- Opening quotations now performs a fresh `GET /api/work-orders/<id>/quotes` request instead of trusting a stale or empty cached quote array.
- The quotation endpoint eagerly loads vendor details, so the resident receives vendor name, service, contact, amount, note, and status in the same response.
- The modal renders cached data immediately when available, then replaces it with the fresh server response.
- An explicit empty state is shown when there are genuinely no quotations, and API errors are shown inside the modal instead of silently failing.

## Expected resident flow
Vendor submits quote -> quote is stored -> resident opens the request -> **View quotes** -> fresh quotation request -> vendor quote appears.
