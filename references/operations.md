# Mutations and Operational Controls

## Mutation classes

Common mutations include creating/patching/publishing/ending offers, changing prices or quantities, updating order fulfillment, adding tracking, creating/canceling shipments, issuing refunds, replying to disputes, sending messages, and changing sale settings. Each requires explicit business authorization in production.

Before invoking a mutation:

1. Resolve the exact environment, account, resource IDs, scope, media type, and current revision/precondition.
2. Classify replay safety. `PUT` to a command ID can be idempotent; repeated `POST /sale/product-offers` can create duplicates.
3. Use Allegro's documented `commandId`, operation ID, request ID, or idempotency field. Generate UUIDs once and persist them before sending.
4. Record a sanitized request fingerprint and response correlation data.
5. For asynchronous commands, poll status and task endpoints to a terminal state; HTTP acceptance is not business completion.
6. Never retry an ambiguous non-idempotent timeout without first checking whether Allegro accepted the original operation.

Refunds and other money movement require narrow authorization, persisted idempotency identifiers, exact decimal/currency handling, and a human-visible audit trail.

## Synchronization design

```text
event journal -> deduplicate event -> fetch aggregate -> idempotent upsert
      |                                      |
      +-> durable cursor after commit         +-> periodic list/detail reconciliation
```

- Partition cursors by environment, Client ID, Allegro account, and journal.
- Store raw event ID/type/time, aggregate ID, retrieval time, and processing result.
- Process duplicate and out-of-order delivery safely.
- Detect cursor gaps/retention expiry; pause cursor advancement and reconcile.
- Keep tombstones/status transitions; absence from one page is not proof of deletion.
- Avoid overlapping workers for one account/journal unless cursor ownership is coordinated.

## Rate and concurrency control

Allegro documents a main limit of 9,000 requests per minute per Client ID, with lower endpoint-specific limits and user-level leaky-bucket controls for selected resources.

- Apply global Client-ID and per-user/per-operation concurrency limits.
- On `429`, honor `Retry-After` when present and use bounded exponential backoff with jitter.
- Retry transient `500`, `502`, `503`, and `504` only when the method/replay key makes it safe.
- Treat `400`, `403`, `404`, `409`, `415`, and `422` as contract, authorization, ownership, media-type, conflict, or validation problems; do not blind-retry.
- Cache reference data where freshness allows and use event journals instead of high-frequency list polling.

## HTTP and representation rules

- Send Bearer authorization and the operation's documented `Accept`, commonly `application/vnd.allegro.public.v1+json`.
- For JSON mutations, send the exact documented `Content-Type`; it is not guaranteed to be identical for every resource version.
- Send the registered stable User-Agent.
- Expect nullable fields and additional response properties.
- Use UTC ISO 8601 internally. The UI can display UTC+1/UTC+2, so compare instants rather than wall-clock strings.
- Preserve identifiers as strings and monetary amounts as decimals, never binary floats.

## Error and observability record

Capture without secrets or buyer data: environment, app and account references, method/path template, media type, attempt, latency, status, Allegro error `code`, correlation headers, idempotency/command ID, cursor/window, and asynchronous terminal state.

Return Allegro's `userMessage` only when appropriate; retain developer `message`, field `path`, and `details` in restricted diagnostics.

Official references:

- [Basic conventions, errors, time, pagination, and limits](https://developer.allegro.pl/tutorials/informacje-podstawowe-b21569boAI1)
- [Complete method list](https://developer.allegro.pl/tutorials/lista-metod-rest-api-allegro-yPyaj0wG3C4)
- [Current operation reference](https://developer.allegro.pl/documentation)
