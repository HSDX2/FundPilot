import ky from "ky";

const API_KEY_STORAGE_KEY = "fundpilot-api-key";

export function getApiKey(): string | null {
  return localStorage.getItem(API_KEY_STORAGE_KEY);
}

export function setApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE_KEY, key);
}

export function clearApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE_KEY);
}

export const api = ky.create({
  prefix: "/api/v1",
  timeout: 180_000,  // AI 分析最多 3 分钟
  hooks: {
    init: [
      (options) => {
        const key = getApiKey();
        if (key) {
          options.headers = {
            ...(options.headers as Record<string, string>),
            "X-API-Key": key,
          };
        }
      },
    ],
  },
});

export interface ApiEnvelope<T = unknown> {
  success: boolean;
  data: T;
  message: string;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

/** Extract error message from ky HTTPError, falling back to defaultMsg. */
export async function extractErrorMessage(err: unknown, defaultMsg: string): Promise<string> {
  if (err instanceof Response) {
    try {
      const body = await err.clone().json();
      return body?.error?.message ?? defaultMsg;
    } catch { /* fall through */ }
  }
  if (err && typeof err === "object" && "response" in err) {
    const resp = (err as { response: Response }).response;
    try {
      const body = await resp.clone().json();
      return body?.error?.message ?? defaultMsg;
    } catch { /* fall through */ }
  }
  return defaultMsg;
}
