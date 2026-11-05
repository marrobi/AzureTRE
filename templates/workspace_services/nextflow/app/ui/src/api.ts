export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body: unknown,
  ) {
    super(message);
  }
}

// Mutating requests carry a custom header, which cross-site forms cannot send without a CORS preflight.
const MUTATION_HEADERS = { "X-Requested-With": "nfportal" };

async function request<T>(method: string, url: string, body?: BodyInit, json = true): Promise<T> {
  const headers: Record<string, string> = method === "GET" ? {} : { ...MUTATION_HEADERS };
  if (body !== undefined && json) headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetch(url, { method, headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError("Could not reach the portal. Check your connection and reload the page.", 0, null);
  }
  if (response.status === 401) {
    // The session expired: sign in again and come back to the current page.
    window.location.assign(`/auth/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    throw new ApiError("Signing you in again…", 401, null);
  }
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "";
    throw new ApiError(detail || `Request failed (${response.status})`, response.status, payload);
  }
  return payload as T;
}

export const api = {
  get: <T>(url: string) => request<T>("GET", url),
  post: <T>(url: string, body?: unknown) =>
    request<T>("POST", url, body === undefined ? undefined : JSON.stringify(body)),
  delete: <T>(url: string) => request<T>("DELETE", url),
  upload: <T>(url: string, form: FormData) => request<T>("POST", url, form, false),
};

export const fileUrl = (container: string, name: string, download = false) =>
  `/files/${container}/${name.split("/").map(encodeURIComponent).join("/")}${download ? "?download=true" : ""}`;
