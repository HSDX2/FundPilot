import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { AppLayout } from "@/components/AppLayout";
import { ApiKeyPage } from "@/pages/ApiKeyPage";
import { Dashboard } from "@/pages/Dashboard";
import { FundList } from "@/pages/funds/FundList";
import { FundDetail } from "@/pages/funds/FundDetail";
import { SectorRank } from "@/pages/sectors/SectorRank";
import { SectorDetail } from "@/pages/sectors/SectorDetail";
import { ReportList } from "@/pages/analysis/ReportList";
import { ReportDetail } from "@/pages/analysis/ReportDetail";
import { AdviceList } from "@/pages/analysis/AdviceList";
import { Sentiment } from "@/pages/analysis/Sentiment";
import { NewsSentiment } from "@/pages/analysis/NewsSentiment";
import { Recommend } from "@/pages/analysis/Recommend";
import { NewsList } from "@/pages/news/NewsList";
import { CollectDashboard } from "@/pages/collect/CollectDashboard";
import { CollectLogs } from "@/pages/collect/CollectLogs";
import { CollectSettings } from "@/pages/collect/CollectSettings";
import { AIProviders } from "@/pages/settings/AIProviders";
import { Watchlist } from "@/pages/watchlist/Watchlist";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1 },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN}>
        <BrowserRouter>
          <Routes>
            <Route path="/api-key" element={<ApiKeyPage />} />
            <Route element={<AppLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="funds" element={<FundList />} />
              <Route path="funds/:code" element={<FundDetail />} />
              <Route path="sectors" element={<SectorRank />} />
              <Route path="sectors/:id" element={<SectorDetail />} />
              <Route path="analysis/reports" element={<ReportList />} />
              <Route path="analysis/reports/:id" element={<ReportDetail />} />
              <Route path="analysis/news-sentiment" element={<NewsSentiment />} />
              <Route path="analysis/advice" element={<AdviceList />} />
              <Route path="analysis/sentiment" element={<Sentiment />} />
              <Route path="analysis/recommend" element={<Recommend />} />
              <Route path="news" element={<NewsList />} />
              <Route path="collect" element={<CollectDashboard />} />
              <Route path="collect/logs" element={<CollectLogs />} />
              <Route path="collect/settings" element={<CollectSettings />} />
              <Route path="watchlist" element={<Watchlist />} />
              <Route path="settings/ai" element={<AIProviders />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
