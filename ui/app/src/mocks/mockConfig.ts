// Mock mode lets the full TRE UI run locally with no Entra ID login and no API,
// using in-memory mock data. Enable with the VITE_MOCK=true environment variable
// (e.g. `npm run start:mock`). This is a developer/demo aid only.
export const isMockMode = (): boolean =>
  (import.meta as any).env?.VITE_MOCK === "true";
