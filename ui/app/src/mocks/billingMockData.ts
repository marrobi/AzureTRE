// Deterministic-but-realistic mock data for the Billing & Budget demo.
// No network calls; everything lives in memory so the demo feels live.

import {
  EnforcementLevel,
  FundingMode,
  WorkspaceBudget,
  WorkspaceServiceCost,
} from "../models/billing";

const CURRENCY = "GBP";

// Generate a smooth-ish daily spend series that sums close to `total`.
const buildDailySpend = (total: number, days = 30): { date: string; cost: number }[] => {
  const points: { date: string; cost: number }[] = [];
  const today = new Date("2026-06-30T00:00:00Z");
  // weight later days slightly higher to look like ramping usage
  const weights = Array.from({ length: days }, (_, i) => 0.5 + (i / days));
  const weightSum = weights.reduce((a, b) => a + b, 0);
  for (let i = 0; i < days; i++) {
    const d = new Date(today);
    d.setUTCDate(today.getUTCDate() - (days - 1 - i));
    const base = (total * weights[i]) / weightSum;
    // gentle deterministic wobble
    const wobble = 1 + 0.15 * Math.sin(i * 1.3);
    points.push({
      date: d.toISOString().slice(0, 10),
      cost: Math.round(base * wobble * 100) / 100,
    });
  }
  return points;
};

const shortRef = (seed: string): string =>
  `TRE-${seed.toUpperCase().slice(0, 4)}-${(
    Array.from(seed).reduce((a, c) => a + c.charCodeAt(0), 0) % 9000 + 1000
  ).toString()}`;

// Total number of mock workspaces (a few curated + the rest generated) to
// exercise UI at the scale of a large programme (~300 workspaces).
export const TOTAL_WORKSPACES = 300;

const round2 = (n: number): number => Math.round(n * 100) / 100;

// Deterministic PRNG (mulberry32) so every caller of buildMockBudgets() gets
// identical data — the billing context, mock workspaces and cost reports must agree.
const seededRandom = (seed: number): (() => number) => {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

const CONDITIONS = [
  "Cardiovascular", "Type 2 Diabetes", "Asthma", "Stroke", "Dementia",
  "Breast Cancer", "Prostate Cancer", "Mental Health", "Obesity", "Osteoarthritis",
  "Chronic Kidney Disease", "Liver Disease", "COPD", "Maternal Health", "Paediatric Health",
  "Vaccine Response", "Infectious Disease", "Nutrition", "Sleep Disorders", "Vision Health",
  "Hypertension", "Alzheimer's", "Parkinson's", "Multiple Sclerosis", "Epilepsy",
  "Inflammatory Bowel", "Rheumatoid Arthritis", "Lung Cancer", "Colorectal Cancer", "Melanoma",
  "Bone Health", "Hearing Loss", "Allergy", "Autoimmune", "Rare Disease",
];

const STUDY_TYPES = [
  "Cohort", "Genomics", "Imaging", "Biomarker", "Registry",
  "Trial Analysis", "Data Linkage", "Screening", "Surveillance", "Modelling",
];

const SERVICE_NAMES = [
  "Virtual Desktops", "Azure Machine Learning", "Azure AI Foundry", "Azure Databricks",
];

const SURNAMES = [
  "patel", "khan", "okafor", "evans", "ahmed", "nguyen", "thompson", "brown",
  "williams", "singh", "kaur", "jones", "wilson", "clarke", "obrien", "murray",
  "hughes", "lewis", "walsh", "ali",
];

const email = (n: number): string =>
  `${SURNAMES[n % SURNAMES.length]}${(n % 90) + 10}@contoso.org`;

// Build a deterministic list of unique workspace names (no numeric suffixes) by
// combining a condition with a study type and shuffling stably.
const buildUniqueNames = (count: number): string[] => {
  const combos: string[] = [];
  for (const c of CONDITIONS) {
    for (const t of STUDY_TYPES) {
      combos.push(`${c} ${t}`);
    }
  }
  const rand = seededRandom(987654321);
  for (let i = combos.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [combos[i], combos[j]] = [combos[j], combos[i]];
  }
  return combos.slice(0, count);
};

// Generate a single deterministic workspace budget for index i.
const generateWorkspace = (i: number, name: string): WorkspaceBudget => {
  const rand = seededRandom(i * 2654435761);
  const id = `ws-${String(i).padStart(3, "0")}`;

  const allocated = [2000, 3000, 4000, 5000, 8000, 10000][Math.floor(rand() * 6)];
  const ratio = 0.1 + rand() * 1.2; // spread of statuses incl. some over-budget
  const consumed = round2(allocated * Math.min(ratio, 1.3));
  const fundingMode: FundingMode = rand() < 0.5 ? "soft" : "paid";
  const enforcement: EnforcementLevel = (["notify", "block", "stop"] as const)[
    Math.floor(rand() * 3)
  ];

  const serviceCount = 1 + Math.floor(rand() * 3);
  const services: WorkspaceServiceCost[] = [];
  let remaining = consumed;
  for (let s = 0; s < serviceCount; s++) {
    const svcName = SERVICE_NAMES[Math.floor(rand() * SERVICE_NAMES.length)];
    const isLast = s === serviceCount - 1;
    const share = isLast ? remaining : round2(remaining * (0.3 + rand() * 0.4));
    remaining = round2(remaining - share);

    const urCount = Math.floor(rand() * 3); // 0..2 user resources
    const userResources = [];
    let svcCost = round2(share * 0.2);
    let urRemaining = round2(share - svcCost);
    if (urCount === 0) {
      svcCost = share; // no user resources — all cost on the service
      urRemaining = 0;
    }
    for (let u = 0; u < urCount; u++) {
      const isLastU = u === urCount - 1;
      const c = isLastU ? urRemaining : round2(urRemaining * (0.4 + rand() * 0.3));
      urRemaining = round2(urRemaining - c);
      userResources.push({
        id: `${id}-ur-${s}-${u}`,
        name: ["Linux Analysis VM", "Windows Analysis VM", "GPU Compute VM", "ML Compute Instance"][
          Math.floor(rand() * 4)
        ],
        owner: email(i + s + u),
        cost: c,
      });
    }
    services.push({ id: `${id}-svc-${s}`, name: svcName, cost: round2(svcCost), userResources });
  }

  return {
    workspaceId: id,
    workspaceName: name,
    currency: CURRENCY,
    fundingMode,
    allocated,
    consumed,
    enforcement,
    thresholds: [50, 80, 100],
    paymentReference: shortRef(id),
    dailySpend: buildDailySpend(consumed),
    allocationHistory: [{ date: "2026-01-01", amount: allocated }],
    serviceBreakdown: [],
    services,
    topUps: [],
    audit: [
      {
        timestamp: "2026-06-01T09:00:00Z",
        actor: "tre-admin@contoso.org",
        action: "Budget created",
        detail: `Initial allocation £${allocated.toLocaleString()} (${fundingMode} mode)`,
      },
    ],
  };
};


export const buildMockBudgets = (): WorkspaceBudget[] => {
  const budgets: WorkspaceBudget[] = [
    {
      workspaceId: "ws-genomics",
      workspaceName: "Cancer Genomics",
      currency: CURRENCY,
      fundingMode: "soft",
      allocated: 5000,
      consumed: 2150.42,
      enforcement: "notify",
      thresholds: [50, 80, 100],
      paymentReference: shortRef("genomics"),
      dailySpend: buildDailySpend(2150.42),
      allocationHistory: [{ date: "2026-01-01", amount: 5000 }],
      serviceBreakdown: [],
      services: [
        {
          id: "svc-gen-guac",
          name: "Virtual Desktops",
          cost: 240.1,
          userResources: [
            { id: "ur-gen-1", name: "Genomic Pipeline VM (Linux)", owner: "j.patel@contoso.org", cost: 540.0 },
            { id: "ur-gen-2", name: "Variant Analysis VM (Windows)", owner: "s.khan@contoso.org", cost: 400.0 },
          ],
        },
        {
          id: "svc-gen-aml",
          name: "Azure AI Foundry",
          cost: 360.2,
          userResources: [
            { id: "ur-gen-3", name: "AI Foundry Compute Instance", owner: "a.okafor@contoso.org", cost: 610.12 },
          ],
        },
      ],
      topUps: [],
      audit: [
        {
          timestamp: "2026-06-01T09:00:00Z",
          actor: "tre-admin@contoso.org",
          action: "Budget created",
          detail: "Initial allocation £5,000 (soft mode)",
        },
      ],
    },
    {
      workspaceId: "ws-imaging",
      workspaceName: "Cardiac Imaging",
      currency: CURRENCY,
      fundingMode: "paid",
      allocated: 8000,
      consumed: 6890.73,
      enforcement: "block",
      thresholds: [50, 80, 100],
      paymentReference: shortRef("imaging"),
      dailySpend: buildDailySpend(6890.73),
      allocationHistory: [
        { date: "2026-01-01", amount: 5000 },
        { date: "2026-06-11", amount: 8000 },
      ],
      serviceBreakdown: [],
      services: [
        {
          id: "svc-img-guac",
          name: "Virtual Desktops",
          cost: 260.0,
          userResources: [
            { id: "ur-img-1", name: "Cardiac MRI GPU VM", owner: "dr.evans@contoso.org", cost: 2100.33 },
            { id: "ur-img-2", name: "Image Annotation VM (Windows)", owner: "r.ahmed@contoso.org", cost: 1560.0 },
          ],
        },
        {
          id: "svc-img-aml",
          name: "Azure Machine Learning",
          cost: 410.4,
          userResources: [
            { id: "ur-img-3", name: "Deep Learning Training Cluster", owner: "l.nguyen@contoso.org", cost: 2560.0 },
          ],
        },
      ],
      topUps: [
        {
          id: "tu-1",
          amount: 3000,
          method: "bank",
          reference: shortRef("imaging"),
          status: "reconciled",
          requestedBy: "dr.evans@contoso.org",
          requestedDate: "2026-06-10T11:20:00Z",
          reconciledBy: "finance@contoso.org",
          reconciledDate: "2026-06-11T08:05:00Z",
          note: "Additional GPU capacity for cardiac MRI cohort",
        },
        {
          id: "tu-2",
          amount: 2000,
          reference: shortRef("imaging-bt"),
          status: "awaiting_payment",
          requestedBy: "dr.evans@contoso.org",
          requestedDate: "2026-06-29T09:15:00Z",
          note: "Bank transfer for Q3 imaging analysis — awaiting Finance reconciliation",
        },
      ],
      audit: [
        {
          timestamp: "2026-05-20T09:00:00Z",
          actor: "tre-admin@contoso.org",
          action: "Budget created",
          detail: "Initial allocation £5,000 (paid mode)",
        },
        {
          timestamp: "2026-06-11T08:05:00Z",
          actor: "finance@contoso.org",
          action: "Top-up reconciled",
          detail: "+£3,000 via bank transfer (ref reconciled)",
        },
      ],
    },
    {
      workspaceId: "ws-climate",
      workspaceName: "Dementia & Ageing Cohort",
      currency: CURRENCY,
      fundingMode: "paid",
      allocated: 4000,
      consumed: 4320.18,
      enforcement: "stop",
      thresholds: [50, 80, 100],
      paymentReference: shortRef("climate"),
      dailySpend: buildDailySpend(4320.18),
      allocationHistory: [{ date: "2026-01-01", amount: 4000 }],
      serviceBreakdown: [],
      services: [
        {
          id: "svc-cli-hpc",
          name: "Azure Machine Learning",
          cost: 510.0,
          userResources: [
            { id: "ur-cli-1", name: "Cohort Linkage Compute Cluster", owner: "m.thompson@contoso.org", cost: 3010.0 },
          ],
        },
        {
          id: "svc-cli-guac",
          name: "Virtual Desktops",
          cost: 320.18,
          userResources: [
            { id: "ur-cli-2", name: "Linux Analysis VM", owner: "p.brown@contoso.org", cost: 480.0 },
          ],
        },
      ],
      topUps: [],
      audit: [
        {
          timestamp: "2026-05-15T09:00:00Z",
          actor: "tre-admin@contoso.org",
          action: "Budget created",
          detail: "Initial allocation £4,000 (paid mode)",
        },
        {
          timestamp: "2026-06-28T14:30:00Z",
          actor: "system",
          action: "Enforcement triggered",
          detail: "Budget exhausted — workspace stopped (enforcement: stop)",
        },
      ],
    },
    {
      workspaceId: "ws-social",
      workspaceName: "Population Health Analytics",
      currency: CURRENCY,
      fundingMode: "soft",
      allocated: 3000,
      consumed: 760.5,
      enforcement: "notify",
      thresholds: [50, 80, 100],
      paymentReference: shortRef("social"),
      dailySpend: buildDailySpend(760.5),
      allocationHistory: [{ date: "2026-01-01", amount: 3000 }],
      serviceBreakdown: [],
      services: [
        {
          id: "svc-soc-guac",
          name: "Virtual Desktops",
          cost: 160.5,
          userResources: [
            { id: "ur-soc-1", name: "Linux Analysis VM", owner: "h.williams@contoso.org", cost: 410.0 },
          ],
        },
        {
          id: "svc-soc-dbx",
          name: "Azure Databricks",
          cost: 190.0,
          userResources: [],
        },
      ],
      topUps: [],
      audit: [
        {
          timestamp: "2026-06-05T09:00:00Z",
          actor: "tre-admin@contoso.org",
          action: "Budget created",
          detail: "Initial allocation £3,000 (soft mode)",
        },
      ],
    },
  ];

  // Append procedurally-generated workspaces so the UI is exercised at scale.
  const curatedCount = budgets.length;
  const generatedNames = buildUniqueNames(TOTAL_WORKSPACES);
  for (let i = curatedCount + 1; i <= TOTAL_WORKSPACES; i++) {
    budgets.push(
      generateWorkspace(i, generatedNames[i - curatedCount - 1] ?? `Research Study ${i}`),
    );
  }

  // Derive the per-service breakdown (service cost + its user resources) used by charts.
  budgets.forEach((b) => {
    b.serviceBreakdown = b.services.map((s) => ({
      name: s.name,
      cost: s.cost + s.userResources.reduce((sum, ur) => sum + ur.cost, 0),
    }));
  });

  return budgets;
};

export const DEMO_USERS = {
  admin: "tre-admin@contoso.org",
  owner: "owner@contoso.org",
  finance: "finance@contoso.org",
};
