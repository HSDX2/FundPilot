import { useState, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Descriptions, Card, Tag, Spin, Empty, Typography, DatePicker, Space, Statistic, Button, message, Modal,
} from "antd";
import { ArrowUpOutlined, ArrowDownOutlined, RobotOutlined, HistoryOutlined, DownloadOutlined, StarFilled, StarOutlined } from "@ant-design/icons";
import type { Dayjs } from "dayjs";
import { getFundDetail, getFundNav, collectFundNav } from "@/api/funds";
import { listWatchedFunds, watchFund, unwatchFund } from "@/api/watchlist";
import { extractErrorMessage } from "@/api/client";
import { NavChart } from "@/components/NavChart";
import dayjs from "dayjs";
import { ChatDialog } from "@/components/ChatDialog";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const FUND_TYPES: Record<string, string> = {
  stock: "股票型", mixed: "混合型", index: "指数型", etf: "ETF",
  bond: "债券型", monetary: "货币型", qdii: "QDII",
};

export function FundDetail() {
  const { code } = useParams<{ code: string }>();
  const queryClient = useQueryClient();
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyStartDate, setHistoryStartDate] = useState<Dayjs | null>(null);

  const { data: fund, isLoading } = useQuery({
    queryKey: ["fund", code],
    queryFn: async () => {
      const res = await getFundDetail(code!);
      return res.success ? res.data : null;
    },
    enabled: !!code,
  });

  const { data: navData } = useQuery({
    queryKey: ["fund", "nav", code],
    queryFn: async () => {
      const res = await getFundNav(code!);
      return res.success ? res.data.items : [];
    },
    enabled: !!code,
  });

  const { mutate: collectHistory, isPending: collectingHistory } = useMutation({
    mutationFn: (startDate?: string) => collectFundNav(code!, "all", startDate),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`历史数据采集完成：新增 ${res.data.added}，更新 ${res.data.updated}`);
        queryClient.invalidateQueries({ queryKey: ["fund", code], refetchType: "active" });
        queryClient.invalidateQueries({ queryKey: ["fund", "nav", code], refetchType: "active" });
      } else message.error("历史数据采集失败");
    },
    onError: async (err) => {
      const msg = await extractErrorMessage(err, "历史数据采集请求失败");
      message.error(msg);
    },
  });

  const { mutate: collectLatest, isPending: collectingLatest } = useMutation({
    mutationFn: () => collectFundNav(code!, "incremental"),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`最新数据采集完成：新增 ${res.data.added}，更新 ${res.data.updated}`);
        queryClient.invalidateQueries({ queryKey: ["fund", code], refetchType: "active" });
        queryClient.invalidateQueries({ queryKey: ["fund", "nav", code], refetchType: "active" });
      } else message.error("最新数据采集失败");
    },
    onError: async (err) => {
      const msg = await extractErrorMessage(err, "最新数据采集请求失败");
      message.error(msg);
    },
  });

  // 关注状态
  const { data: watchedIds } = useQuery({
    queryKey: ["watchlist", "fund-ids"],
    queryFn: async () => {
      const res = await listWatchedFunds();
      if (!res.success) return new Set<string>();
      return new Set((res.data.items ?? []).map((w) => w.fund_id));
    },
  });

  const { mutate: doWatch } = useMutation({
    mutationFn: (fundId: string) => watchFund(fundId),
    onSuccess: () => {
      message.success("已关注");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
    onError: () => message.error("关注失败"),
  });

  const { mutate: doUnwatch } = useMutation({
    mutationFn: (fundId: string) => unwatchFund(fundId),
    onSuccess: () => {
      message.success("已取消关注");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
    onError: () => message.error("取消关注失败"),
  });

  const chartData = useMemo(() => {
    const base = (navData ?? [])
      .filter((d) => d.nav != null)
      .map((d) => ({ date: d.date, value: Number(d.nav), change_pct: d.daily_change_pct != null ? Number(d.daily_change_pct) : undefined }))
      .sort((a, b) => a.date.localeCompare(b.date));

    if (dateRange && dateRange[0] && dateRange[1]) {
      const start = dateRange[0].format("YYYY-MM-DD");
      const end = dateRange[1].format("YYYY-MM-DD");
      return base.filter((d) => d.date >= start && d.date <= end);
    }
    return base;
  }, [navData, dateRange]);

  const chartTitle = useMemo(() => {
    let prefix = "净值走势";
    if (chartData.length > 0) {
      prefix += ` (${chartData[0].date} ~ ${chartData[chartData.length - 1].date})`;
    }
    return prefix;
  }, [chartData]);

  const latestNav = useMemo(() => {
    if (!navData || navData.length === 0) return null;
    return navData.reduce((latest, item) =>
      !latest || item.date > latest.date ? item : latest
    , null as (typeof navData)[0] | null);
  }, [navData]);

  if (isLoading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  if (!fund) return <Empty description="未找到该基金" />;

  const estimatePct = fund.estimate_change_pct != null ? Number(fund.estimate_change_pct) : null;
  const isUp = (estimatePct ?? 0) >= 0;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 0 }}>
        <h2 style={{ margin: 0 }}>{fund.name} ({fund.code})</h2>
        <Tag color="blue">{FUND_TYPES[fund.type ?? ""] ?? fund.type}</Tag>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <Button
            icon={<HistoryOutlined />}
            loading={collectingHistory}
            onClick={() => setHistoryModalOpen(true)}
          >获取历史数据</Button>
          <Button
            icon={<DownloadOutlined />}
            loading={collectingLatest}
            onClick={() => collectLatest()}
          >获取最新数据</Button>
          <Button
            type="link"
            icon={fund && watchedIds?.has(fund.id)
              ? <StarFilled style={{ color: "#faad14" }} />
              : <StarOutlined />}
            onClick={() => {
              if (!fund) return;
              if (watchedIds?.has(fund.id)) doUnwatch(fund.id);
              else doWatch(fund.id);
            }}
          >
            {fund && watchedIds?.has(fund.id) ? "已关注" : "关注"}
          </Button>
          <Button type="primary" icon={<RobotOutlined />} onClick={() => setChatOpen(true)}>AI 问询</Button>
        </div>
      </div>

      {/* 实时估值 & 最新净值 — 独立卡片 */}
      <Card style={{ marginTop: 16 }}>
        <div style={{ display: "flex", gap: 48, alignItems: "center", flexWrap: "wrap" }}>
          <Statistic
            title="盘中估值"
            value={fund.estimate_nav != null ? Number(fund.estimate_nav).toFixed(4) : "-"}
            precision={4}
          />
          <Statistic
            title="估算涨跌幅"
            value={estimatePct != null && !isNaN(estimatePct)
              ? `${isUp ? "+" : ""}${estimatePct.toFixed(2)}%`
              : "-"}
            styles={{ content: { color: isUp ? "#cf1322" : "#3f8600" } }}
            prefix={isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
          />
          <Statistic
            title={`最新净值${latestNav ? ` (${latestNav.date})` : ""}`}
            value={latestNav?.nav != null ? Number(latestNav.nav).toFixed(4) : "-"}
            precision={4}
          />
          {(() => {
            const actualPct = latestNav?.daily_change_pct != null ? Number(latestNav.daily_change_pct) : null;
            const actualUp = (actualPct ?? 0) >= 0;
            return (
              <Statistic
                title={`实际涨跌幅${latestNav ? ` (${latestNav.date})` : ""}`}
                value={actualPct != null && !isNaN(actualPct)
                  ? `${actualUp ? "+" : ""}${actualPct.toFixed(2)}%`
                  : "-"}
                styles={{ content: { color: actualUp ? "#cf1322" : "#3f8600" } }}
                prefix={actualUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              />
            );
          })()}
          {fund.estimate_nav == null && (
            <Text type="secondary" style={{ alignSelf: "flex-end" }}>非交易时段暂无实时估值</Text>
          )}
        </div>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="基金公司">{fund.company ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="成立日期">
            {fund.established_date
              ? dayjs(fund.established_date).format("YYYY-MM-DD")
              : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="规模">
            {fund.scale != null ? `${Number(fund.scale).toFixed(2)} 亿份` : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="基金经理">
            {fund.fund_manager ?? "-"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        title={chartTitle}
        extra={
          <Space>
            <RangePicker
              value={dateRange}
              onChange={(v) => setDateRange(v as [Dayjs, Dayjs] | null)}
              allowClear
              placeholder={["开始日期", "结束日期"]}
              size="small"
              style={{ width: 240 }}
            />
          </Space>
        }
        style={{ marginTop: 24 }}
      >
        {chartData.length > 0 ? (
          <NavChart data={chartData} />
        ) : (
          <Empty description="暂无净值数据" />
        )}
      </Card>
      <ChatDialog
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        context={{ fund_code: code, fund_name: fund.name }}
      />

      {/* 历史数据采集弹窗 */}
      <Modal
        title="获取历史净值数据"
        open={historyModalOpen}
        onOk={() => {
          collectHistory(historyStartDate?.format("YYYY-MM-DD"));
          setHistoryModalOpen(false);
          setHistoryStartDate(null);
        }}
        onCancel={() => {
          setHistoryModalOpen(false);
          setHistoryStartDate(null);
        }}
        okText="开始采集"
        cancelText="取消"
        confirmLoading={collectingHistory}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Text>选择起始日期</Text>
          <DatePicker
            value={historyStartDate}
            onChange={setHistoryStartDate}
            format="YYYY-MM-DD"
            placeholder="留空 = 回补全部历史数据"
            allowClear
            style={{ width: 240 }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            留空 = 回补全部历史净值数据。填入日期 = 从该日起采集。
          </Text>
        </div>
      </Modal>
    </div>
  );
}
