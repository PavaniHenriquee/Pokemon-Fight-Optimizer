// Where the backend lives. Electron (or a frontend/.env file) can override it with VITE_API_URL.
// 127.0.0.1 rather than localhost: on Windows Chromium may try ::1 first, uvicorn binds IPv4.
const envUrl = import.meta.env.VITE_API_URL as string | undefined;

// Set by electron/preload.cjs: the Electron app starts its own backend on a free port
declare global {
  interface Window {
    desktop?: { apiUrl: string | null };
  }
}

export const API_URL = (window.desktop?.apiUrl || envUrl || "http://127.0.0.1:8000").replace(/\/$/, "");
export const WS_URL = `${API_URL.replace(/^http/, "ws")}/ws`;

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

// The backend answers some failures with HTTP 200 and {status: "error"} or {error: "..."}
export async function postJSON<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data?.status === "error" || data?.error) {
    throw new Error(data?.error ?? `${res.status} ${res.statusText}`);
  }
  return data as T;
}
