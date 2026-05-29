import { api } from "./client";
import type { ApiEnvelope, PaginatedData } from "./client";

export interface RecommendItem {
  type: "fund" | "sector";
  action: "buy" | "add" | "watch" | "stop";
  target_id: string;
  target_name: string;
  target_code: string | null;
  confidence: number;
  reason_summary: string;
  reason_detail: Record<string, unknown> | null;
  risk_warning: string | null;
}

/** 历史推荐记录（带 DB 字段） */
export interface RecommendRecord {
  id: string;
  date: string;
  mode: string;
  type: string;
  action: string;
  target_name: string;
  target_code: string | null;
  confidence: number;
  reason_summary: string;
  reason_detail: Record<string, unknown> | null;
  risk_warning: string | null;
}

export async function getTopPicks(params: {
  limit?: number;
  category?: string;
}): Promise<ApiEnvelope<{ items: RecommendItem[]; total: number }>> {
  return api.post("recommend/top-picks", { json: params }).json();
}

export async function getDipBuy(params: {
  limit?: number;
  max_drawdown?: number;
  min_consecutive_days?: number;
}): Promise<ApiEnvelope<{ items: RecommendItem[]; total: number }>> {
  return api.post("recommend/dip-buy", { json: params }).json();
}

export async function getRecommendHistory(params: {
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  mode?: string;
}): Promise<ApiEnvelope<PaginatedData<RecommendRecord>>> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  if (params.start_date) searchParams.set("start_date", params.start_date);
  if (params.end_date) searchParams.set("end_date", params.end_date);
  if (params.mode) searchParams.set("mode", params.mode);
  return api.get(`recommend/history?${searchParams}`).json();
}

export async function deleteRecommendHistory(
  ids: string[],
): Promise<ApiEnvelope<{ deleted: number }>> {
  return api.delete(`recommend/history?ids=${ids.join(",")}`).json();
}
