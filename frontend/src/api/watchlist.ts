import { api } from "./client";
import type { ApiEnvelope } from "./client";

export interface WatchedFund {
  id: string;
  fund_id: string;
  fund_code: string;
  fund_name: string;
  fund_type: string | null;
  estimate_nav: number | null;
  estimate_change_pct: number | null;
  holding_amount: number | null;
  added_at: string;
}

export interface WatchedSector {
  id: string;
  sector_id: string;
  sector_name: string;
  sector_category: string;
  price: number | null;
  change_pct: number | null;
  added_at: string;
}

// ── 关注基金 ──

export async function listWatchedFunds(): Promise<
  ApiEnvelope<{ items: WatchedFund[]; total: number }>
> {
  return api.get("watchlist/funds").json();
}

export async function watchFund(fundId: string): Promise<ApiEnvelope<null>> {
  return api.post(`watchlist/funds/${fundId}`).json();
}

export async function unwatchFund(fundId: string): Promise<ApiEnvelope<null>> {
  return api.delete(`watchlist/funds/${fundId}`).json();
}

export async function updateWatchedFund(
  fundId: string,
  body: { holding_amount: number | null },
): Promise<ApiEnvelope<{ holding_amount: number | null }>> {
  return api.put(`watchlist/funds/${fundId}`, { json: body }).json();
}

// ── 关注板块 ──

export async function listWatchedSectors(): Promise<
  ApiEnvelope<{ items: WatchedSector[]; total: number }>
> {
  return api.get("watchlist/sectors").json();
}

export async function watchSector(sectorId: string): Promise<ApiEnvelope<null>> {
  return api.post(`watchlist/sectors/${sectorId}`).json();
}

export async function unwatchSector(sectorId: string): Promise<ApiEnvelope<null>> {
  return api.delete(`watchlist/sectors/${sectorId}`).json();
}
