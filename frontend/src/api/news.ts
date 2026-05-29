import { api } from "./client";
import type { ApiEnvelope, PaginatedData } from "./client";

/** Matches backend NewsArticleResponse schema */
export interface NewsArticle {
  id: string;
  title: string;
  content: string | null;
  source: string | null;
  url: string | null;
  published_at: string | null;
  sentiment_score: number | null;
  sentiment_detail: Record<string, unknown> | null;
}

export async function searchNews(params: {
  keyword?: string;
  source?: string;
  start?: string;
  end?: string;
  page?: number;
  page_size?: number;
}): Promise<ApiEnvelope<PaginatedData<NewsArticle>>> {
  const searchParams = new URLSearchParams();
  if (params.keyword) searchParams.set("keyword", params.keyword);
  if (params.source) searchParams.set("source", params.source);
  if (params.start) searchParams.set("start", params.start);
  if (params.end) searchParams.set("end", params.end);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  return api.get(`news?${searchParams}`).json();
}

export async function getUnanalyzedCount(params?: {
  start?: string;
  end?: string;
}): Promise<ApiEnvelope<{ count: number }>> {
  const searchParams = new URLSearchParams();
  if (params?.start) searchParams.set("start", params.start);
  if (params?.end) searchParams.set("end", params.end);
  const qs = searchParams.toString();
  return api.get(`news/unanalyzed-count${qs ? `?${qs}` : ""}`).json();
}

export async function getNewsDetail(
  id: string,
): Promise<ApiEnvelope<NewsArticle>> {
  return api.get(`news/${id}`).json();
}
