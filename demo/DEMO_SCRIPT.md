# Workspace Billing & Budgets — Demo Script

A guided walkthrough of the Azure TRE **Workspace Billing & Budget** module, running
as a fully-mocked build of the real TRE UI (no login, no API — all data is client-side).

> **Live demo:** https://white-pebble-00a7ab003.7.azurestaticapps.net
> Share freely — it is read-only mock data and resets on every page load.

The demo uses a `?role=` URL parameter to switch persona (mock mode only):
`admin` (TRE Admin), `finance` (Finance / Billing), `owner` (Workspace Owner).

| Persona | Where it lives | Can do |
| --- | --- | --- |
| **TRE Admin** | Top-level **Billing** nav (programme-wide) | Oversee all workspaces, set funding mode & enforcement, re-baseline allocations |
| **Finance** | Top-level **Billing** nav | Reconcile bank-transfer payments (separation of duties) |
| **Workspace Owner** | **Budget** under the workspace left nav | View spend, configure thresholds, request & pay top-ups |

---

## Quick links

| Scene | Link |
| --- | --- |
| Admin — programme billing dashboard | [/billing?role=admin](https://white-pebble-00a7ab003.7.azurestaticapps.net/billing?role=admin) |
| Finance — reconcile payments | [/billing?role=finance](https://white-pebble-00a7ab003.7.azurestaticapps.net/billing?role=finance) |
| Owner — workspace home | [/workspaces/ws-imaging?role=owner](https://white-pebble-00a7ab003.7.azurestaticapps.net/workspaces/ws-imaging?role=owner) |
| Owner — workspace budget (direct) | [/workspaces/ws-imaging/workspace-billing?role=owner](https://white-pebble-00a7ab003.7.azurestaticapps.net/workspaces/ws-imaging/workspace-billing?role=owner) |
| Standalone billing dashboard (no chrome) | [/billing-demo](https://white-pebble-00a7ab003.7.azurestaticapps.net/billing-demo) |

---

## Part 1 — TRE Admin (programme-wide)

**Open:** [/billing?role=admin](https://white-pebble-00a7ab003.7.azurestaticapps.net/billing?role=admin)

**Talk track**
- "Billing is a top-level area, visible only to TRE Admins. It gives a programme-wide
  view across all workspaces — here we have **300** research workspaces."
- Point out the summary cards: **total allocated**, **consumed**, **remaining**.
- Use the **search** box (e.g. type *cancer*) and the **status filter**
  (On track / Approaching limit / Over budget / Stopped) to find at-risk workspaces.
- Sort by **% used** or **Remaining** to triage; note the **paging** for scale.

**Drill into a workspace (governance)**
- Search **Cardiac Imaging** and click it.
- **Overview** tab — gauge (consumed vs allocated) plus *spend over time*. The red
  budget line is a **step function**: it rises on the date each top-up was applied,
  so history isn't retroactively shifted.
- **Budget & enforcement** tab — admin-only governance:
  - **Funding mode**: *Soft* (tracking only, never blocks) vs *Paid* (budget only
    rises after a reconciled payment).
  - **Enforcement severity ladder**: *Notify → Block new provisioning → Stop
    (disable workspace)*.
  - **Amend allocation** — admins re-baseline the official budget (audited).

---

## Part 2 — Finance (separation of duties)

**Open:** [/billing?role=finance](https://white-pebble-00a7ab003.7.azurestaticapps.net/billing?role=finance)

**Talk track**
- "Reconciling payments is a dedicated Finance responsibility — separation of duties
  from the people who request the money."
- Search **Cardiac Imaging** → open it → **Top-ups** tab.
- Show **Outstanding invoices** — there's a £2,000 invoice *awaiting payment* by bank
  transfer.
- As Finance, the **Reconcile bank transfer** button is enabled (Pay-online and
  Request-invoice are disabled). Click **Reconcile bank transfer**.
- Return to **Overview** — the budget line **steps up** by £2,000 on today's date.

---

## Part 3 — Workspace Owner (single workspace)

**Open:** [/workspaces/ws-imaging?role=owner](https://white-pebble-00a7ab003.7.azurestaticapps.net/workspaces/ws-imaging?role=owner)

**Talk track**
- "As a Workspace Owner I'm scoped to my own workspace — no programme-wide Billing
  nav, no Create button. Budget lives under my workspace's left nav."
- Click **Budget** in the workspace nav (or use the
  [direct link](https://white-pebble-00a7ab003.7.azurestaticapps.net/workspaces/ws-imaging/workspace-billing?role=owner)).
- **Overview** — same gauge and stepped spend chart, plus *cost by service*
  (Virtual Desktops, Azure Machine Learning, Azure AI Foundry…).
- Note **Budget & enforcement** governance controls are **read-only** for owners —
  they can't change funding mode/enforcement or re-baseline the allocation.

**Paid top-up flow**
- **Top-ups** tab → **Request invoice** for an amount.
- An invoice is raised with a **payment reference**. Two ways to settle:
  - **Bank transfer** — quote the reference; Finance reconciles on receipt (Part 2).
  - **Pay now (online)** — simulated payment provider; settles instantly.
- Click **Pay now (online)** → return to **Overview** → the budget **steps up**.
- **Audit log** tab — every change (request, payment, reconciliation) is recorded
  with actor, timestamp and reason.

---

## Suggested 3-minute flow

1. **Admin** dashboard → filter to *Approaching limit* → open **Cardiac Imaging** →
   show governance (funding mode + enforcement). *(~60s)*
2. **Finance** → open **Cardiac Imaging** → **Top-ups** → **Reconcile bank transfer**
   → show budget step-up. *(~45s)*
3. **Owner** → **Budget** → **Top-ups** → **Request invoice** → **Pay now (online)**
   → show step-up + **Audit log**. *(~60s)*

---

## Notes

- This is a **mock** of the real TRE UI (`VITE_MOCK=true`). Roles are demo-only via
  `?role=`; in production they come from Microsoft Entra ID (`TREAdmin`,
  `WorkspaceOwner`, and a dedicated Finance role).
- Data resets on every page load; nothing is persisted.
- Re-deploy after changes with `./demo/deploy-mock.sh`.
- Recorded walkthrough: `demo/playwright/demo-video/billing-demo.webm`.
