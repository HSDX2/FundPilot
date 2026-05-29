import { api } from "./client";
import type { ApiEnvelope, PaginatedData } from "./client";

/** Matches backend FundResponse schema */
export interface FundItem {
  id: string;
  code: string;
  name: string;
  type: string | null;
  company: string | null;
  established_date: string | null;
  scale: number | null;
  fund_manager: string | null;
  latest_price: number | null;
  latest_change_pct: number | null;
  latest_nav_date: string | null;
  latest_nav: number | null;
  latest_nav_change_pct: number | null;
  estimate_nav: number | null;
  estimate_change_pct: number | null;
}

/** Matches backend FundNavResponse schema */
export interface FundNavItem {
  id: string;
  fund_id: string;
  date: string;
  nav: number | null;
  accumulated_nav: number | null;
  daily_change_pct: number | null;
}

/** 实时估值（直接从 AkShare 获取，不走数据库） */
export interface FundEstimate {
  estimate_nav: number | null;
  estimate_change_pct: number | null;
  nav: number | null;
  daily_change_pct: number | null;
  timestamp: string;
}

/** 批量估值响应中单条记录 */
export interface FundEstimateBrief {
  fund_code: string;
  estimate_nav: number | null;
  estimate_change_pct: number | null;
  nav: number | null;
  daily_change_pct: number | null;
  timestamp: string;
}

export async function searchFunds(params: {
  page?: number;
  page_size?: number;
  type?: string;
  company?: string;
  name?: string;
  sort_by?: string;
  sort_order?: string;
  watched_only?: boolean;
}): Promise<ApiEnvelope<PaginatedData<FundItem>>> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  if (params.type) searchParams.set("type", params.type);
  if (params.company) searchParams.set("company", params.company);
  if (params.name) searchParams.set("name", params.name);
  if (params.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params.sort_order) searchParams.set("sort_order", params.sort_order);
  if (params.watched_only) searchParams.set("watched_only", "true");
  return api.get(`funds?${searchParams}`).json();
}

export async function getFundDetail(code: string): Promise<ApiEnvelope<FundItem>> {
  return api.get(`funds/${code}`).json();
}

export async function getFundNav(
  code: string,
  params?: { start_date?: string; end_date?: string },
): Promise<ApiEnvelope<{ items: FundNavItem[] }>> {
  const searchParams = new URLSearchParams();
  if (params?.start_date) searchParams.set("start_date", params.start_date);
  if (params?.end_date) searchParams.set("end_date", params.end_date);
  const qs = searchParams.toString();
  return api.get(`funds/${code}/nav${qs ? `?${qs}` : ""}`).json();
}

export async function getFundEstimate(
  code: string,
): Promise<ApiEnvelope<FundEstimate | null>> {
  return api.get(`funds/${code}/estimate`).json();
}

export async function getBatchEstimates(
  codes: string[],
): Promise<ApiEnvelope<{ items: FundEstimateBrief[] }>> {
  return api.get(`funds/estimates/batch?codes=${codes.join(",")}`).json();
}

export interface CollectDataResult {
  added: number;
  updated: number;
  total: number;
}

export async function collectFundNav(
  code: string,
  mode: "all" | "incremental",
  startDate?: string,
): Promise<ApiEnvelope<CollectDataResult>> {
  return api.post(`funds/${code}/collect-nav`, { json: { mode, start_date: startDate ?? null } }).json();
}
