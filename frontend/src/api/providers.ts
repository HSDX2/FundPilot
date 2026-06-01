import { api } from "./client";
import type { ApiEnvelope } from "./client";

export interface AIProviderItem {
  id: string;
  name: string;
  provider_type: string;
  api_key: string | null;
  api_base_url: string;
  model_name: string;
  is_active: boolean;
  web_search_enabled: boolean;
  reasoning_enabled: boolean;
  extra_config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export async function listProviders(params?: {
  provider_type?: string;
}): Promise<ApiEnvelope<{ items: AIProviderItem[]; total: number }>> {
  const searchParams = params?.provider_type
    ? `?provider_type=${params.provider_type}`
    : "";
  return api.get(`admin/ai-providers${searchParams}`).json();
}

export async function getActiveProvider(): Promise<
  ApiEnvelope<AIProviderItem | null>
> {
  return api.get("admin/ai-providers/active").json();
}

export async function getProvider(
  id: string,
): Promise<ApiEnvelope<AIProviderItem>> {
  return api.get(`admin/ai-providers/${id}`).json();
}

export async function createProvider(body: {
  name: string;
  provider_type: string;
  api_key: string | null;
  api_base_url: string;
  model_name: string;
  extra_config?: Record<string, unknown>;
}): Promise<ApiEnvelope<AIProviderItem>> {
  return api.post("admin/ai-providers", { json: body }).json();
}

export async function updateProvider(
  id: string,
  body: Record<string, unknown>,
): Promise<ApiEnvelope<AIProviderItem>> {
  return api.put(`admin/ai-providers/${id}`, { json: body }).json();
}

export async function deleteProvider(
  id: string,
): Promise<ApiEnvelope<null>> {
  return api.delete(`admin/ai-providers/${id}`).json();
}

export async function activateProvider(
  id: string,
): Promise<ApiEnvelope<AIProviderItem>> {
  return api.post(`admin/ai-providers/${id}/activate`).json();
}

export async function testProviderConnection(
  id: string,
): Promise<ApiEnvelope<{ success: boolean; reply?: string; error?: string }>> {
  return api.post(`admin/ai-providers/${id}/test`).json();
}
