import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Row, Col, Card, Table, Tag, Spin, Typography, Segmented, Tooltip,
} from "antd";
import {
  SmileOutlined, RiseOutlined, ReadOutlined, DollarOutlined,
  BarChartOutlined, QuestionCircleOutlined, BulbOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { getLatestSentiment, type MarketSentiment } from "@/api/analysis";
import { getSectorRank, getSectorMoneyFlowRank, type SectorRankItem } from "@/api/sectors";
import type { MoneyFlowRankItem } from "@/api/sectors";
import { searchFunds, type FundItem } from "@/api/funds";
import { searchNews, type NewsArticle } from "@/api/news";
import { getRecommendHistory, type RecommendRecord } from "@/api/recommend";
import { SentimentGauge } from "@/components/SentimentGauge";
import dayjs from "dayjs";
import { useState } from "react";

const { Text } = Typography;

function sentimentLabel(score: number): { text: string; color: string } {
  if (score >= 70) return { text: "乐观", color: "#3f8600" };
  if (score >= 50) return { text: "中性偏多", color: "#1890ff" };
  if (score >= 30) return { text: "中性偏空", color: "#faad14" };
  return { text: "悲观", color: "#cf1322" };
}

export function Dashboard() {
  const navigate = useNavigate();
  const [mfPeriod, setMfPeriod] = useState("today");
  const [srCategory, setSrCategory] = useState("industry");
  const mfPagination = useMemo(
    () => ({ pageSize: 15, showSizeChanger: true, pageSizeOptions: ["15", "30", "50"] as const }),
    [],
  );

  const { data: sentiment, isLoading: sentimentLoading } = useQuery({
    queryKey: ["sentiment", "latest"],
    queryFn: async () => {
      const res = await getLatestSentiment();
      return res.success ? res.data : null;
    },
    refetchInterval: 60_000,
  });

  const { data: rank } = useQuery({
    queryKey: ["sectors", "rank", "dashboard", srCategory],
    queryFn: async () => {
      const res = await getSectorRank({ category: srCategory, page_size: 10, sort_by: "realtime_change_pct" });
      return res.success ? res.data.items : [];
    },
    refetchInterval: 60_000,
  });

  const { data: fundRank } = useQuery({
    queryKey: ["funds", "rank", "dashboard"],
    queryFn: async () => {
      const res = await searchFunds({
        page: 1, page_size: 10,
        sort_by: "estimate_change_pct", sort_order: "desc",
      });
      return res.success ? res.data.items : [];
    },
    refetchInterval: 60_000,
  });

  const { data: news } = useQuery({
    queryKey: ["news", "latest"],
    queryFn: async () => {
      const res = await searchNews({ page_size: 10 });
      return res.success ? res.data.items : [];
    },
    refetchInterval: 120_000,
  });

  const { data: moneyFlowRank, isLoading: mfLoading } = useQuery({
    queryKey: ["sectors", "money-flow-rank", mfPeriod],
    queryFn: async () => {
      const res = await getSectorMoneyFlowRank({ period: mfPeriod });
      return res.success ? res.data.items : [];
    },
    refetchInterval: 60_000,
  });

  const { data: recommends } = useQuery({
    queryKey: ["recommend", "history", "dashboard"],
    queryFn: async () => {
      const res = await getRecommendHistory({ mode: "top_picks", page_size: 6 });
      return res.success ? res.data.items : [];
    },
    refetchInterval: 600_000,
  });

  const score = (sentiment as MarketSentiment | null)?.composite_sentiment_score ?? 50;
  const sl = sentimentLabel(score);

  const sectorColumns = [
    {
      title: "#", key: "idx", width: 36,
      render: (_: unknown, __: unknown, i: number) => i + 1,
    },
    {
      title: "板块", dataIndex: "sector_name", key: "sector_name", ellipsis: true,
      render: (v: string, r: SectorRankItem) => (
        <a onClick={() => navigate(`/sectors/${r.sector_id}`)}>{v}</a>
      ),
    },
    {
      title: "实时涨跌幅",
      dataIndex: "realtime_change_pct",
      key: "realtime_change_pct",
      width: 110,
      align: "right" as const,
      render: (_: unknown, r: SectorRankItem) => {
        const v = r.realtime_change_pct ?? r.change_pct;
        if (v == null) return "-";
        const n = parseFloat(v);
        return (
          <Text style={{ color: n >= 0 ? "#cf1322" : "#3f8600" }}>
            {n >= 0 ? "+" : ""}{n.toFixed(2)}%
          </Text>
        );
      },
    },
  ];

  const fundColumns = [
    { title: "代码", dataIndex: "code", key: "code", width: 80 },
    {
      title: "名称", dataIndex: "name", key: "name", ellipsis: true,
      render: (v: string, r: FundItem) => (
        <a onClick={() => navigate(`/funds/${r.code}`)}>{v}</a>
      ),
    },
    {
      title: "估算涨跌",
      key: "estimate_pct",
      width: 100,
      align: "right" as const,
      render: (_: unknown, r: FundItem) => {
        const pct = r.estimate_change_pct;
        if (pct == null) return "-";
        const n = Number(pct);
        const color = n >= 0 ? "#cf1322" : "#3f8600";
        return (
          <Text style={{ color, fontWeight: 500 }}>
            {n >= 0 ? "+" : ""}{n.toFixed(2)}%
          </Text>
        );
      },
    },
  ];

  const recColumns = [
    {
      title: "名称", key: "name", ellipsis: true,
      render: (_: unknown, r: RecommendRecord) => (
        <a onClick={() => {
          if (r.type === "fund" && r.target_code && /^\d/.test(r.target_code)) {
            navigate(`/funds/${r.target_code}`);
          } else if (r.target_code?.includes("-")) {
            navigate(`/sectors/${r.target_code}`);
          }
        }}>
          {r.target_name}
        </a>
      ),
    },
    {
      title: "类型", dataIndex: "type", key: "type", width: 60,
      render: (v: string) => (
        <Tag color={v === "fund" ? "blue" : "purple"} style={{ margin: 0 }}>
          {v === "fund" ? "基金" : "板块"}
        </Tag>
      ),
    },
    {
      title: "操作",
      key: "action",
      width: 60,
      render: (_: unknown, r: RecommendRecord) => {
        const ac: Record<string, { c: string; l: string }> = {
          buy: { c: "#cf1322", l: "推荐" },
          add: { c: "#cf1322", l: "加仓" },
          watch: { c: "#faad14", l: "观望" },
          stop: { c: "#3f8600", l: "止损" },
        };
        const a = ac[r.action] ?? { c: "default", l: r.action };
        return <Tag color={a.c} style={{ margin: 0 }}>{a.l}</Tag>;
      },
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 55,
      align: "right" as const,
      render: (v: number) => (
        <Text style={{ color: v >= 60 ? "#cf1322" : "#faad14", fontSize: 12 }}>{v}</Text>
      ),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>
        <RiseOutlined /> 投资看板
      </h2>

      <Row gutter={[16, 16]}>
        {/* Market Sentiment Gauge */}
        <Col xs={24} md={12}>
          <Card
            title={<span><SmileOutlined /> 市场情绪</span>}
            extra={
              <Tooltip
                title={
                  <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                    <div><b>综合评分 = 10 个因子加权</b></div>
                    <div>• 涨停比率 (15%) / 跌停比率 (10%, 反向) / 炸板率 (10%, 反向)</div>
                    <div>• 北向资金 (15%) / 融资余额 (10%) / 龙虎榜 (10%)</div>
                    <div>• 涨跌家数 (10%) / 主力资金 (10%)</div>
                    <div>• 总市值 (5%) / PE 分位 (5%)</div>
                    <div style={{ marginTop: 6, color: "#bbb" }}>
                      ⚠️ 涨跌家数/主力/龙虎榜接口不稳定
                    </div>
                  </div>
                }
                styles={{ root: { maxWidth: 360 } }}
              >
                <QuestionCircleOutlined style={{ color: "#999", cursor: "pointer" }} />
              </Tooltip>
            }
            loading={sentimentLoading}
          >
            {sentiment ? (
              <>
                <SentimentGauge score={score} height={260} />
                <div style={{ textAlign: "center", marginTop: 8 }}>
                  <Tag color={sl.color} style={{ fontSize: 16, padding: "4px 16px" }}>
                    {sl.text} ({score.toFixed(0)})
                  </Tag>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {dayjs((sentiment as MarketSentiment).date).format("YYYY-MM-DD")}
                    </Text>
                  </div>
                </div>
              </>
            ) : (
              <div style={{ textAlign: "center", padding: 40 }}>
                <Text type="secondary">暂无情绪数据</Text>
              </div>
            )}
          </Card>
        </Col>

        {/* AI 综合推荐 */}
        <Col xs={24} md={12}>
          <Card
            title={<span><BulbOutlined /> AI 综合推荐</span>}
            extra={<a onClick={() => navigate("/analysis/recommend")}>查看更多</a>}
          >
            {recommends && recommends.length > 0 ? (
              <Table
                columns={recColumns}
                dataSource={recommends}
                rowKey="id"
                size="small"
                pagination={false}
                showHeader={false}
              />
            ) : (
              <div style={{ textAlign: "center", padding: 20 }}>
                <Text type="secondary">暂无推荐</Text>
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* Sector Rank */}
        <Col xs={24} md={12}>
          <Card
            title={<span><RiseOutlined /> 板块排行</span>}
            extra={<a onClick={() => navigate("/sectors")}>查看更多</a>}
          >
            <Segmented
              size="small"
              value={srCategory}
              onChange={setSrCategory}
              options={[
                { value: "industry", label: "行业" },
                { value: "concept", label: "概念" },
              ]}
              style={{ marginBottom: 12 }}
            />
            <Table
              columns={sectorColumns}
              dataSource={rank ?? []}
              rowKey="sector_id"
              size="small"
              pagination={false}
              loading={!rank}
            />
          </Card>
        </Col>

        {/* Fund Rank */}
        <Col xs={24} md={12}>
          <Card
            title={<span><BarChartOutlined /> 基金排行</span>}
            extra={<a onClick={() => navigate("/funds")}>查看更多</a>}
          >
            <Table
              columns={fundColumns}
              dataSource={fundRank ?? []}
              rowKey="id"
              size="small"
              pagination={false}
              loading={!fundRank}
            />
          </Card>
        </Col>
      </Row>

      {/* News + Money Flow */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* Latest News */}
        <Col xs={24} md={12}>
          <Card
            title={<span><ReadOutlined /> 最新资讯</span>}
            extra={<a onClick={() => navigate("/news")}>查看更多</a>}
          >
            {news ? (
              <div style={{ display: "flex", flexDirection: "column" }}>
                {news.map((item: NewsArticle) => (
                  <div
                    key={item.id}
                    style={{
                      padding: "6px 0",
                      borderBottom: "1px solid #f5f5f5",
                      cursor: item.url ? "pointer" : "default",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                    onClick={() => item.url && window.open(item.url, "_blank")}
                  >
                    <Text ellipsis style={{ flex: 1, fontSize: 13 }}>
                      {item.title}
                    </Text>
                    {item.sentiment_score != null && (
                      <Tag
                        color={
                          item.sentiment_score >= 60 ? "#cf1322"
                          : item.sentiment_score >= 20 ? "#faad14"
                          : item.sentiment_score > -20 ? "default"
                          : item.sentiment_score > -60 ? "blue"
                          : "purple"
                        }
                        style={{ flexShrink: 0, margin: 0, fontSize: 11 }}
                      >
                        {item.sentiment_score >= 60 ? "利好"
                          : item.sentiment_score >= 20 ? "偏多"
                          : item.sentiment_score > -20 ? "中性"
                          : item.sentiment_score > -60 ? "偏空"
                          : "利空"}
                      </Tag>
                    )}
                    <Text type="secondary" style={{ flexShrink: 0, fontSize: 11 }}>
                      {item.source} · {item.published_at ? dayjs(item.published_at).format("MM-DD HH:mm") : "-"}
                    </Text>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
            )}
          </Card>
        </Col>

        {/* Sector Money Flow Rank */}
        <Col xs={24} md={12}>
          <Card
            title={<span><DollarOutlined /> 资金流向排行</span>}
            loading={mfLoading}
          >
            <Segmented
              size="small"
              value={mfPeriod}
              onChange={setMfPeriod}
              options={[
                { value: "today", label: "当天" },
                { value: "3d", label: "近3日" },
                { value: "5d", label: "近5日" },
                { value: "10d", label: "近10日" },
              ]}
              style={{ marginBottom: 12 }}
            />
            <Table
              columns={[
                {
                  title: "板块",
                  dataIndex: "name",
                  key: "name",
                  ellipsis: true,
                  render: (v: string, record: MoneyFlowRankItem) =>
                    record.id ? (
                      <a onClick={() => navigate(`/sectors/${record.id}`)}>{v}</a>
                    ) : v,
                },
                {
                  title: "分类",
                  dataIndex: "category",
                  key: "category",
                  width: 80,
                  render: (v: string) => (
                    <Tag color={v === "industry" ? "blue" : "purple"}>
                      {v === "industry" ? "行业" : "概念"}
                    </Tag>
                  ),
                },
                {
                  title: "净流入",
                  dataIndex: "main_force_net_inflow",
                  key: "main_force_net_inflow",
                  width: 140,
                  align: "right" as const,
                  render: (v: number | null) => {
                    if (v == null) return "-";
                    const yiyuan = v / 1e8;
                    return (
                      <Text style={{ color: yiyuan >= 0 ? "#cf1322" : "#3f8600" }}>
                        {yiyuan >= 0 ? "+" : ""}{yiyuan.toFixed(2)} 亿
                      </Text>
                    );
                  },
                },
              ]}
              dataSource={moneyFlowRank ?? []}
              rowKey={(record: MoneyFlowRankItem) => record.name + record.category}
              size="small"
              pagination={mfPagination}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
