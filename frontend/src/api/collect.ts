import { api } from "./client";
import type { ApiEnvelope, PaginatedData } from "./client";

export interface CollectorStatus {
  collector_name: string;
  display_name: string;
  status: string;
  progress: number;
  total: number;
  message: string;
  started_at: string | null;
}

/** Matches backend ScheduleConfig schema */
export interface ScheduleConfig {
  /** 激活时间窗口开始，如 "08:00" */
  active_start_time: string | null;
  /** 激活时间窗口结束，如 "15:00" */
  active_end_time: string | null;
  /** 定时模式：interval（间隔执行）/ specific_time（指定时刻） */
  mode: "interval" | "specific_time";
  /** 间隔分钟数（mode=interval 时生效），如 60 表示每60分钟 */
  interval_minutes: number | null;
  /** 指定执行时刻（mode=specific_time 时生效），如 "12:00:00" */
  specific_time: string | null;
  /** 星期维度，1=周一 … 7=周日，如 [1,2,3,4,5] 表示工作日 */
  weekdays: number[] | null;
  /** 月日期维度，如 [1,15] 表示每月 1 号和 15 号 */
  month_days: number[] | null;
}

/** Matches backend OtherConfigUpdate schema */
export interface OtherConfig {
  /** 基金类型（fund_list）：etf / stock / mixed / index */
  fund_type?: string | null;
  /** 新闻源（news）：eastmoney / jin10 / cls / wallstreetcn */
  sources?: string[] | null;
  /** 数据起始日期，格式 YYYY-MM-DD */
  start_date?: string | null;
  /** 数据结束日期 */
  end_date?: string | null;
  /** AI 并发数（news_sentiment），默认 3，最大 10 */
  sentiment_concurrency?: number | null;
  /** 单次分析条数上限（news_sentiment），默认 50，最大 1000 */
  sentiment_limit?: number | null;
  /** 多进程并发数（fund_nav_history），默认 8，最大 12 */
  worker_count?: number | null;
  /** 是否只补抽无历史数据板块（sector_batch_history） */
  sector_new_only?: boolean | null;
  /** 是否只补抽无历史数据基金（fund_nav_history） */
  new_only?: boolean | null;
  /** 是否补充中单/散户资金流向细分（sector_batch_daily） */
  backfill_mf_detail?: boolean | null;
}

export interface CollectorSetting {
  id: string;
  collector_name: string;
  display_name: string | null;
  description: string | null;
  interval_seconds: number;
  is_active: boolean;
  schedule_config: ScheduleConfig | null;
  other_config: OtherConfig | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface CollectLog {
  id: string;
  collector_name: string;
  display_name: string;
  status: string;
  records_added: number;
  records_updated: number;
  error_message: string | null;
  duration_ms: number | null;
  started_at: string;
  finished_at: string | null;
}

export interface TriggerResult {
  collector_name: string;
  records_added: number;
  records_updated: number;
  errors: string[];
}

export async function triggerCollect(
  collector: string,
  sources?: string[],
  start_date?: string,
  fund_type?: string,
  backfill_mf_detail?: boolean,
): Promise<ApiEnvelope<TriggerResult>> {
  return api.post("collect/trigger", {
    json: { collector, sources, start_date, fund_type, backfill_mf_detail },
  }).json();
}

export async function getCollectStatus(): Promise<
  ApiEnvelope<{ items: CollectorStatus[] }>
> {
  return api.get("collect/status").json();
}

export async function stopCollect(
  name: string,
): Promise<ApiEnvelope<{ collector_name: string; stopped: boolean }>> {
  return api.post(`collect/stop/${name}`).json();
}

export async function getCollectLogs(params: {
  collector?: string;
  page?: number;
  page_size?: number;
}): Promise<ApiEnvelope<PaginatedData<CollectLog>>> {
  const searchParams = new URLSearchParams();
  if (params.collector) searchParams.set("collector", params.collector);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  return api.get(`collect/logs?${searchParams}`).json();
}

export async function getCollectSettings(): Promise<
  ApiEnvelope<{ items: CollectorSetting[] }>
> {
  return api.get("collect/settings").json();
}

export async function updateCollectSetting(
  name: string,
  body: { interval_seconds?: number; is_active?: boolean },
): Promise<ApiEnvelope<CollectorSetting>> {
  return api.put(`collect/settings/${name}`, { json: body }).json();
}

export async function updateCollectSchedule(
  name: string,
  body: Partial<ScheduleConfig>,
): Promise<ApiEnvelope<CollectorSetting>> {
  return api.put(`collect/settings/${name}/schedule`, { json: body }).json();
}

export async function updateCollectOtherConfig(
  name: string,
  body: Partial<OtherConfig>,
): Promise<ApiEnvelope<CollectorSetting>> {
  return api.put(`collect/settings/${name}/other-config`, { json: body }).json();
}

export async function clearCollectLogs(): Promise<
  ApiEnvelope<{ deleted: number }>
> {
  return api.delete("collect/logs").json();
}
