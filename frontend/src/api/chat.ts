import { api } from "./client";
import type { ApiEnvelope } from "./client";

export interface ChatContext {
  fund_code?: string;
  fund_name?: string;
  sector_id?: string;
  sector_name?: string;
  web_search?: boolean;
}

export interface ChatRequest {
  session_id?: string;
  message: string;
  context?: ChatContext;
}

export type ChatEvent =
  | { type: "token"; content: string }
  | { type: "session_id"; content: string }
  | { type: "tool_result"; content: string }
  | { type: "error"; content: string }
  | { type: "done" };

/**
 * Send a chat message and receive SSE stream.
 * Returns an async generator of ChatEvent.
 */
export async function* chatStream(
  req: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch("/api/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });

  if (!response.ok) {
    yield { type: "error", content: `HTTP ${response.status}` };
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    yield { type: "error", content: "无法读取响应流" };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(trimmed.slice(6));
          yield data as ChatEvent;
        } catch {
          // skip malformed JSON
        }
      }
    }
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") return;
    yield { type: "error", content: "流读取中断" };
  }
}

export async function destroySession(
  sessionId: string,
): Promise<ApiEnvelope<null>> {
  return api.delete(`chat/${sessionId}`).json();
}
