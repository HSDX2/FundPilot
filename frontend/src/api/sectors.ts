import { api } from "./client";
import type { ApiEnvelope, PaginatedData } from "./client";

/** Matches backend SectorDetailResponse schema */
export interface SectorItem {
  id: string;
  code: string | null;
  name: string;
  category: string;
  description: string | null;
  /** 最新收盘价 */
  price: string | null;
  /** 涨跌幅（%） */
  change_pct: string | null;
  /** 成交量（手） */
  volume: number | null;
  /** 实时估算 { price, change_pct, volume } */
  realtime: { price: string | null; change_pct: string | null; volume: number | null } | null;
}

/** Matches backend SectorRankItem schema */
export interface SectorRankItem {
  sector_id: string;
  sector_name: string;
  category: string;
  price: string | null;
  change_pct: string | null;
  realtime_price: string | null;
  realtime_change_pct: string | null;
  timestamp: string | null;
}

/** Matches backend SectorSnapshotResponse schema */
export interface SectorSnapshot {
  id: string;
  sector_id: string;
  price: number;
  open: number | null;
  high: number | null;
  low: number | null;
  change_pct: number | null;
  volume: number | null;
  turnover: number | null;
  timestamp: string;
  /** 实时估算数据（THS） */
  realtime?: {
    price: number | null;
    change_pct: number | null;
    volume: number | null;
  } | null;
}

/** Matches backend SectorMoneyFlowResponse schema */
export interface MoneyFlowItem {
  id: string;
  sector_id: string;
  date: string;
  main_force_net_inflow: number | null;
  retail_net_inflow: number | null;
  middle_net_inflow: number | null;
}

export async function searchSectors(params: {
  page?: number;
  page_size?: number;
  category?: string;
  name?: string;
}): Promise<ApiEnvelope<PaginatedData<SectorItem>>> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  if (params.category) searchParams.set("category", params.category);
  if (params.name) searchParams.set("name", params.name);
  return api.get(`sectors?${searchParams}`).json();
}

export async function getSectorDetail(
  id: string,
): Promise<ApiEnvelope<SectorItem>> {
  return api.get(`sectors/${id}`).json();
}

export async function getSectorRank(params?: {
  category?: string;
  page?: number;
  page_size?: number;
  sort_by?: string;
  watched_only?: boolean;
}): Promise<ApiEnvelope<{ items: SectorRankItem[]; total: number; page: number; page_size: number }>> {
  const searchParams = new URLSearchParams();
  if (params?.category) searchParams.set("category", params.category);
  if (params?.page) searchParams.set("page", String(params.page));
  if (params?.page_size) searchParams.set("page_size", String(params.page_size));
  if (params?.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params?.watched_only) searchParams.set("watched_only", "true");
  const qs = searchParams.toString();
  return api.get(`sectors/rank/current${qs ? `?${qs}` : ""}`).json();
}

export async function getSectorRealtime(
  id: string,
): Promise<ApiEnvelope<SectorSnapshot | null>> {
  return api.get(`sectors/${id}/realtime`).json();
}

export async function getSectorMoneyFlow(
  id: string,
  params?: { start_date?: string; end_date?: string },
): Promise<ApiEnvelope<{ items: MoneyFlowItem[] }>> {
  const searchParams = new URLSearchParams();
  if (params?.start_date) searchParams.set("start_date", params.start_date);
  if (params?.end_date) searchParams.set("end_date", params.end_date);
  const qs = searchParams.toString();
  return api.get(`sectors/${id}/money-flow${qs ? `?${qs}` : ""}`).json();
}

export async function getSectorSnapshots(
  id: string,
  params?: { start_time?: string; end_time?: string },
): Promise<ApiEnvelope<{ items: SectorSnapshot[] }>> {
  const searchParams = new URLSearchParams();
  if (params?.start_time) searchParams.set("start_time", params.start_time);
  if (params?.end_time) searchParams.set("end_time", params.end_time);
  const qs = searchParams.toString();
  return api.get(`sectors/${id}/snapshots${qs ? `?${qs}` : ""}`).json();
}

export interface CollectDataResult {
  added: number;
  updated: number;
  total: number;
}

export async function collectSectorData(
  id: string,
  mode: "all" | "incremental",
  startDate?: string,
  backfillMfDetail?: boolean,
): Promise<ApiEnvelope<CollectDataResult>> {
  const params = new URLSearchParams({ mode });
  if (startDate) params.set("start_date", startDate);
  if (backfillMfDetail !== undefined) {
    params.set("backfill_mf_detail", String(backfillMfDetail));
  }
  return api.post(`sectors/${id}/collect-data?${params.toString()}`).json();
}

/** THS 资金流向排行条目 */
export interface MoneyFlowRankItem {
  id: string | null;
  name: string;
  category: string;
  main_force_net_inflow: number | null;
}

/** 获取板块资金流向排行 */
export async function getSectorMoneyFlowRank(params: {
  period?: string;
  sector_type?: string;
}): Promise<ApiEnvelope<{ items: MoneyFlowRankItem[] }>> {
  const searchParams = new URLSearchParams();
  if (params.period) searchParams.set("period", params.period);
  if (params.sector_type) searchParams.set("sector_type", params.sector_type);
  return api.get(`sectors/money-flow/rank?${searchParams}`).json();
}
