import { api } from "./client";
import type { ApiEnvelope, PaginatedData } from "./client";
import type { NewsArticle } from "./news";

/** Matches backend AnalysisReportResponse schema */
export interface AnalysisReport {
  id: string;
  date: string;
  report_type: string;
  category: string | null;
  sector_id: string | null;
  sector_name: string | null;
  content: Record<string, unknown>;
  ai_model: string | null;
  created_at: string;
}

/** Matches backend FundAdviceResponse schema */
export interface FundAdvice {
  id: string;
  fund_id: string;
  fund_code: string | null;
  fund_name: string | null;
  date: string;
  action: string;
  reason: Record<string, unknown>;
  confidence: number | null;
  ai_model: string | null;
  created_at: string;
}

/** Matches backend MarketSentimentResponse schema */
export interface MarketSentiment {
  id: string;
  date: string;
  limit_up_count: number | null;
  limit_down_count: number | null;
  limit_up_broken_count: number | null;
  consecutive_limit_up_count: number | null;
  north_bound_net_inflow: number | null;
  margin_balance_sse: number | null;
  margin_balance_szse: number | null;
  lhb_stock_count: number | null;
  advance_count: number | null;
  decline_count: number | null;
  market_total_cap: number | null;
  composite_sentiment_score: number | null;
  extra: Record<string, unknown> | null;
  created_at: string;
}

export async function listReports(params: {
  report_type?: string;
  category?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}): Promise<ApiEnvelope<PaginatedData<AnalysisReport>>> {
  const searchParams = new URLSearchParams();
  if (params.report_type) searchParams.set("report_type", params.report_type);
  if (params.category) searchParams.set("category", params.category);
  if (params.start_date) searchParams.set("start_date", params.start_date);
  if (params.end_date) searchParams.set("end_date", params.end_date);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  return api.get(`analysis/reports?${searchParams}`).json();
}

export async function getLatestReport(
  report_type?: string,
): Promise<ApiEnvelope<AnalysisReport | null>> {
  return api.get(
    `analysis/reports/latest?report_type=${report_type ?? "daily"}`,
  ).json();
}

export async function getReport(
  id: string,
): Promise<ApiEnvelope<AnalysisReport>> {
  return api.get(`analysis/reports/${id}`).json();
}

export async function generateReport(body: {
  sector_id: string;
  report_type: string;
}): Promise<ApiEnvelope<AnalysisReport>> {
  return api.post("analysis/reports/generate", { json: body }).json();
}

export async function generateAllReports(body: {
  report_type: string;
  limit: number;
  category?: string;
  sector_ids?: string[];
}): Promise<ApiEnvelope<{ items: AnalysisReport[]; total: number }>> {
  return api.post("analysis/reports/generate-all", { json: body }).json();
}

export async function deleteReport(
  id: string,
): Promise<ApiEnvelope<null>> {
  return api.delete(`analysis/reports/${id}`).json();
}

export async function batchDeleteReports(
  ids: string[],
): Promise<ApiEnvelope<{ deleted: number }>> {
  return api.post("analysis/reports/batch-delete", { json: { ids } }).json();
}

export async function analyzeNewsSentiment(body: {
  limit?: number;
  force?: boolean;
  start_date?: string;
  end_date?: string;
}): Promise<ApiEnvelope<{ status: string; message: string }>> {
  return api.post("analysis/news/sentiment", { json: body }).json();
}

export async function getSentimentTaskStatus(): Promise<
  ApiEnvelope<{ running: boolean; task_name: string; started_at: string | null }>
> {
  return api.get("analysis/news/sentiment/status").json();
}

export async function reanalyzeNewsSentiment(
  newsId: string,
): Promise<ApiEnvelope<NewsArticle>> {
  return api.post(`analysis/news/${newsId}/sentiment`).json();
}

export async function listAdvice(params: {
  action?: string;
  fund_code?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}): Promise<ApiEnvelope<PaginatedData<FundAdvice>>> {
  const searchParams = new URLSearchParams();
  if (params.action) searchParams.set("action", params.action);
  if (params.fund_code) searchParams.set("fund_code", params.fund_code);
  if (params.start_date) searchParams.set("start_date", params.start_date);
  if (params.end_date) searchParams.set("end_date", params.end_date);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  return api.get(`analysis/advice?${searchParams}`).json();
}

export async function getAdvice(
  id: string,
): Promise<ApiEnvelope<FundAdvice>> {
  return api.get(`analysis/advice/${id}`).json();
}

export async function generateAdvice(body: {
  fund_id: string;
}): Promise<ApiEnvelope<FundAdvice>> {
  return api.post("analysis/advice/generate", { json: body }).json();
}

export async function generateBatchAdvice(body: {
  fund_ids: string[];
}): Promise<ApiEnvelope<{ items: FundAdvice[]; total: number }>> {
  return api.post("analysis/advice/generate-batch", { json: body }).json();
}

export async function listSentiment(params: {
  page?: number;
  page_size?: number;
}): Promise<ApiEnvelope<PaginatedData<MarketSentiment>>> {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  return api.get(`analysis/sentiment?${searchParams}`).json();
}

export async function getLatestSentiment(): Promise<
  ApiEnvelope<MarketSentiment | null>
> {
  return api.get("analysis/sentiment/latest").json();
}

export async function clearSentiment(): Promise<
  ApiEnvelope<{ deleted: number }>
> {
  return api.delete("analysis/sentiment").json();
}
