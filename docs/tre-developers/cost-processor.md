# Cost Processor and Cost Collection

This document describes the design of TRE cost data collection: how cost data is
persisted, how it is refreshed, and how the TRE API serves cost reports from it.

For the user-facing description of the cost APIs and their limitations, see
[Cost Reporting](../azure-tre-overview/cost-reporting.md).

## Motivation

TRE cost reports are generated from [Azure Cost Management](https://learn.microsoft.com/azure/cost-management-billing/).
Querying Cost Management directly on every API request has two problems:

- **Throttling** – the Cost Management Query API rate-limits frequent callers
  (HTTP 429). Several admins/owners viewing cost reports, or reports that are
  split into multiple sub-queries, can exhaust the quota and cause errors and
  delays on the request path.
- **Limited history** – the Query API only returns roughly the last 13 months of
  data, so it cannot answer long-range questions (for example multi-year
  workspace spend).

The design collects cost data into a durable Cosmos DB collection and serves
reports from it, so Cost Management is queried on a schedule in the background
rather than synchronously per request.

## Components

```text
                +------------------+     scheduled query     +---------------------+
                |  Cost Processor  |  ---------------------->  | Azure Cost Mgmt API |
                |  (Function app)  |                           +---------------------+
                +------------------+
                         |  POST /internal/costs/refresh (managed identity)
                         v
                +------------------+     read/write            +---------------------+
                |     TRE API      |  <---------------------->  |  Cost collection    |
                | /costs endpoints |    (sole writer)          |  (Cosmos DB)        |
                +------------------+                           +---------------------+
                         ^
                         |  GET /costs, /workspaces/{id}/costs (cache-first)
                         |
                   Admins / Owners
```

- **Cost Processor** – a Python Azure Function app with timer triggers. On each
  run it asks the TRE API to refresh a period; it does not talk to Cosmos or hold
  cost business logic itself. It runs on the shared **core processing** App
  Service Plan (`plan-airlock-<tre_id>`), alongside the Airlock Processor.
- **TRE API** – owns the cost collection and is its **only** writer. It exposes an
  internal, managed-identity-authenticated refresh endpoint used by the Cost
  Processor, and serves the existing `/costs` endpoints cache-first from the
  collection.
- **Cost collection (Cosmos DB)** – a durable collection storing collected cost
  rows at daily granularity, designed to also hold budgets and manual
  adjustments in future (discriminated by an item-type field).

### Why the API is the sole writer

Routing all writes (both the collector and any future manual amendments) through
the API keeps validation and business rules in one place. Planned features such
as marking up/amending cost data and tracking spend against soft/hard budgets
depend on this single-writer discipline to keep the collection consistent.

### Managed identity authentication

The Cost Processor authenticates to the API with a user-assigned managed
identity. During core deployment Terraform creates the identity, and the API is
told the identity's **client id** (via an app setting). The processor uses the
identity to request an app-only token for the API's own audience, and the
internal refresh endpoint authorises the call by matching the token's client id
against that configured value.

This deliberately does **not** use a Microsoft Graph *application role
assignment*. Assigning an app role requires `AppRoleAssignment.ReadWrite.All`
Graph permission, and in many tenants the automated deployment identity is not
(and cannot be) granted Graph write permissions — app registrations are staged
separately by an Entra administrator. Authorising by client id keeps all Graph
operations out of the core Terraform deployment: **no additional Graph
permissions are required to deploy the Cost Processor.**

## Refresh cadence and latency

Cost Management data settles slowly: usage typically appears 8–24 hours after
consumption and continues to be re-rated for a day or two, so figures lag actual
usage by roughly **24–48 hours**. This latency is imposed by Azure and cannot be
reduced by querying more frequently — polling faster returns identical numbers
and only increases throttling risk.

The Cost Processor therefore uses a tiered, latency-aware schedule:

| Data segment | Volatility | Cadence |
| --- | --- | --- |
| Current month | Still settling | Every ~6 hours (`0 0 */6 * * *`) |
| Just-closed previous month | Settling | Daily sweep (`0 30 2 * * *`) until finalised |
| Older, completed months | Immutable | Daily backfill sweep (`0 0 4 * * *`), collected once then retained |

The three timers run on a single-worker plan, so their default schedules are
staggered (current-month on the hour, previous-month at 02:30, backfill at 04:00)
to avoid three concurrent Cost Management sweeps competing on the one worker. The
backfill also has a wall-clock budget (`COST_PROCESSOR_BACKFILL_MAX_RUNTIME_SECONDS`,
default 30 minutes; `0` disables it) so a run that keeps getting throttled stops
and resumes on its next schedule rather than tying up the worker indefinitely.

Completed months are marked final and never re-queried, so multi-year reports are
served almost entirely from the collection; only the current month is refreshed,
and only by the background processor. Schedules and the prior-month look-back
window are exposed as app settings.

## Read path

`GET /api/costs` and `GET /api/workspaces/{id}/costs` resolve each (split)
sub-period from the cost collection first, but **only finalised** (immutable,
completed-month) periods are served from it. Still-settling periods — the current
month / month-to-date — are always resolved with a live Cost Management query
(bounded by the short in-memory cache) so reports never return stale current-month
figures. If a requested finalised period has not yet been collected, the API
falls back to a single live query and persists the result, so the endpoints
remain correct on a cold start while avoiding Cost Management on the common path.

## Out of scope / future work

The Cost Processor Function app, the cost collection and its repository, the
internal managed-identity refresh endpoint, and the API read-through are
implemented. Remaining future work:

- Budgets (soft/hard) and spend tracking, and manual cost mark-up/adjustments.
- Near-real-time expensive-resource controls (Azure Budgets/alerts, per-hour price
  display at provisioning, auto-shutdown) — cost reporting is too slow for this.
