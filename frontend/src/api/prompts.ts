import { api } from "./client";
import type { ApiEnvelope } from "./client";

export interface PromptItem {
  key: string;
  label: string;
  default_text: string;
  custom_text: string | null;
}

export interface PromptListData {
  items: PromptItem[];
}

export async function listPrompts(): Promise<ApiEnvelope<PromptListData>> {
  return api.get("admin/prompts").json();
}

export async function savePrompt(
  promptKey: string,
  promptText: string,
): Promise<ApiEnvelope<null>> {
  return api.put(`admin/prompts/${promptKey}`, {
    json: { prompt_text: promptText },
  }).json();
}

export async function resetPrompt(
  promptKey: string,
): Promise<ApiEnvelope<null>> {
  return api.delete(`admin/prompts/${promptKey}`).json();
}
