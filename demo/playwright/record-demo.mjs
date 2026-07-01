// Combined demo recording — Workspace Billing & Budgets, with on-screen
// transition cards between the Billing Admin/Finance and Workspace Owner parts.
// Full real TRE UI in mock mode. Serve the mock build at BASE_URL first:
//   npm run build:mock && npx vite preview --port 4173 --host 127.0.0.1
//   BASE_URL=http://127.0.0.1:4173 node record-demo.mjs
import { chromium } from "playwright";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.BASE_URL || "http://127.0.0.1:4173";
const OUT_DIR = path.join(__dirname, "demo-video");
const SIZE = { width: 1440, height: 900 };
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

async function hover(page, locator, ms = 800) {
  const el = locator.first();
  await el.scrollIntoViewIfNeeded().catch(() => {});
  await el.hover().catch(() => {});
  await pause(ms);
}

// Full-screen transition card injected over the page.
async function card(page, title, subtitle = "", ms = 2600) {
  await page.evaluate(
    ({ title, subtitle }) => {
      const d = document.createElement("div");
      d.id = "__demo_card";
      d.style.cssText =
        "position:fixed;inset:0;z-index:2147483647;background:linear-gradient(135deg,#0b2440,#1b3a5f);color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'Segoe UI',system-ui,sans-serif;opacity:0;transition:opacity .35s ease;";
      d.innerHTML =
        `<div style="font-size:50px;font-weight:600;letter-spacing:.5px;">${title}</div>` +
        (subtitle
          ? `<div style="font-size:24px;opacity:.8;margin-top:14px;max-width:60%;text-align:center;line-height:1.4;">${subtitle}</div>`
          : "");
      document.body.appendChild(d);
      requestAnimationFrame(() => (d.style.opacity = "1"));
    },
    { title, subtitle },
  );
  await pause(ms);
  await page.evaluate(() => {
    const d = document.getElementById("__demo_card");
    if (d) d.style.opacity = "0";
  });
  await pause(400);
  await page.evaluate(() => document.getElementById("__demo_card")?.remove());
}

async function openImagingBudget(page) {
  await page.waitForSelector("text=Billing & Budgets");
  await pause(1000);
  const search = page.getByPlaceholder("Search by workspace name or ID...");
  await search.fill("Cardiac Imaging");
  await pause(600);
  await page.getByTestId("ws-link-ws-imaging").click();
  await page.waitForSelector("text=Cardiac Imaging");
  await pause(1100);
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: SIZE,
    recordVideo: { dir: OUT_DIR, size: SIZE },
  });
  const page = await context.newPage();

  // ---- Intro ----
  await page.goto(`${BASE_URL}/billing?role=admin`, { waitUntil: "networkidle" });
  await card(
    page,
    "Workspace Billing & Budgets",
    "Allocate, track, top-up and enforce per-workspace budgets in Azure TRE",
    3000,
  );

  // ======================= PART 1: BILLING ADMIN =======================
  await card(
    page,
    "Billing Admin",
    "Programme-wide budgets, governance and oversight",
  );
  await page.waitForSelector("text=Billing & Budgets");
  await pause(1400);

  // Filter the all-workspaces dashboard
  await page.getByText("All statuses").click();
  await pause(500);
  await page.getByRole("option", { name: "Approaching limit" }).click();
  await pause(1400);
  await page.getByText("Approaching limit").first().click().catch(() => {});
  await page.getByRole("option", { name: "All statuses" }).click().catch(() => {});
  await pause(600);

  // Drill into a paid workspace — governance (funding mode + enforcement)
  await openImagingBudget(page);
  await hover(page, page.getByText("Spend over time"), 1500);
  await page.getByRole("tab", { name: /Budget & enforcement/i }).click();
  await pause(1100);
  await hover(page, page.getByTestId("funding-mode-toggle"), 1300);
  await hover(page, page.getByTestId("enforcement-choice"), 1400);

  // ======================= PART 2: FINANCE =======================
  await card(
    page,
    "Finance",
    "Separation of duties — reconcile bank-transfer payments",
  );
  await page.goto(`${BASE_URL}/billing?role=finance`, { waitUntil: "networkidle" });
  await openImagingBudget(page);
  await page.getByRole("tab", { name: /Top-ups/i }).click();
  await pause(1100);
  await hover(page, page.getByText(/Outstanding invoices/i), 1300);
  await hover(page, page.getByTestId("reconcile-topup"), 1100);
  await page.getByTestId("reconcile-topup").click();
  await pause(1300);
  await page.getByRole("tab", { name: /Overview/i }).click();
  await pause(900);
  await hover(page, page.getByText("Spend over time"), 1600);

  // ======================= PART 3: WORKSPACE OWNER =======================
  await card(
    page,
    "Workspace Owner",
    "Self-service budget management within a single workspace",
  );
  await page.goto(`${BASE_URL}/workspaces/ws-imaging?role=owner`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("text=Cardiac Imaging");
  await pause(1300);
  await hover(page, page.getByRole("link", { name: "Budget" }), 900);
  await page.getByRole("link", { name: "Budget" }).first().click();
  await pause(1300);
  await hover(page, page.getByText("Spend over time"), 1600);

  // Paid top-up: request invoice -> pay online
  await page.getByRole("tab", { name: /Top-ups/i }).click();
  await pause(1000);
  await page.getByTestId("request-invoice").click();
  await pause(1100);
  await hover(page, page.getByTestId("payment-reference"), 1600);
  await page.getByTestId("pay-online").first().click();
  await pause(1200);
  await page.getByRole("tab", { name: /Overview/i }).click();
  await pause(900);
  await hover(page, page.getByText("Spend over time"), 1700);

  // Audit trail
  await page.getByRole("tab", { name: /Audit log/i }).click();
  await pause(1600);

  await card(page, "Thank you", "Workspace Billing & Budgets — Azure TRE", 2600);

  await context.close();
  await browser.close();
  console.log(`Combined video written to ${OUT_DIR}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
