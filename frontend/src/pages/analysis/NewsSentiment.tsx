import { useState, useMemo } from "react";
import {
  Table, Tag, Typography, Button, DatePicker, Space, message, Popconfirm,
} from "antd";
import { ThunderboltOutlined, SettingOutlined, ReloadOutlined, LinkOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { searchNews, getUnanalyzedCount } from "@/api/news";
import { triggerCollect } from "@/api/collect";
import { reanalyzeNewsSentiment } from "@/api/analysis";
import { PromptEditor } from "@/components/PromptEditor";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";

const { Text } = Typography;
const { RangePicker } = DatePicker;

export function NewsSentiment() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);

  const startStr = dateRange?.[0]?.format("YYYY-MM-DD");
  const endStr = dateRange?.[1]?.format("YYYY-MM-DD");

  const { data, isLoading } = useQuery({
    queryKey: ["news", "sentiment", { page, start: startStr, end: endStr }],
    queryFn: async () => {
      const res = await searchNews({
        page, page_size: pageSize,
        start: startStr, end: endStr,
      });
      return res.success ? res.data : { items: [], total: 0, page: 1, page_size: 20 };
    },
  });

  const { data: unanalyzedCount } = useQuery({
    queryKey: ["news", "unanalyzed-count", { start: startStr, end: endStr }],
    queryFn: async () => {
      const res = await getUnanalyzedCount({ start: startStr, end: endStr });
      return res.success ? res.data.count : 0;
    },
  });

  const { mutate: runAnalysis, isPending: analyzing } = useMutation({
    mutationFn: () => triggerCollect("news_sentiment"),
    onSuccess: (res) => {
      if (res.success) {
        message.success("新闻情绪分析任务已触发，可在采集日志查看进度");
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ["news", "sentiment"] });
        }, 5000);
      }
    },
    onError: () => message.error("触发分析失败"),
  });

  const { mutate: reanalyze, isPending: reanalyzing } = useMutation({
    mutationFn: (newsId: string) => reanalyzeNewsSentiment(newsId),
    onSuccess: (res) => {
      if (res.success) {
        message.success("重新分析完成");
        queryClient.invalidateQueries({ queryKey: ["news", "sentiment"] });
      } else {
        message.error("分析失败");
      }
    },
    onError: () => message.error("分析请求失败"),
  });

  function sentimentTag(score: number | null) {
    if (score == null) return <Tag>未分析</Tag>;
    let label = "中性";
    let color = "default";
    if (score >= 60) { label = "利好"; color = "red"; }
    else if (score >= 20) { label = "偏利好"; color = "orange"; }
    else if (score > -20) { label = "中性"; color = "default"; }
    else if (score > -60) { label = "偏利空"; color = "blue"; }
    else { label = "利空"; color = "purple"; }
    return <Tag color={color}>{label}</Tag>;
  }

  const columns = [
    {
      title: "操作",
      key: "actions",
      width: 70,
      render: (_: unknown, record: { id: string }) => (
        <Popconfirm
          title="确认重新分析此新闻？"
          onConfirm={(e) => {
            e?.stopPropagation();
            reanalyze(record.id);
          }}
          onCancel={(e) => e?.stopPropagation()}
        >
          <Button
            type="link"
            size="small"
            icon={<ReloadOutlined />}
            loading={reanalyzing}
            onClick={(e) => e.stopPropagation()}
          />
        </Popconfirm>
      ),
    },
    { title: "标题", dataIndex: "title", key: "title", ellipsis: true, width: 300 },
    {
      title: "来源", dataIndex: "source", key: "source", width: 90,
      render: (v: string | null) => v ?? "-",
    },
    {
      title: "原文", key: "url", width: 50, align: "center" as const,
      render: (_: unknown, record: { url: string | null }) =>
        record.url ? (
          <a href={record.url} target="_blank" rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}>
            <LinkOutlined />
          </a>
        ) : "-",
    },
    {
      title: "发布时间",
      dataIndex: "published_at",
      key: "published_at",
      width: 120,
      render: (v: string | null) => v ? dayjs(v).format("MM-DD HH:mm") : "-",
    },
    {
      title: "情绪评分",
      dataIndex: "sentiment_score",
      key: "sentiment_score",
      width: 120,
      align: "center" as const,
      render: (score: number | null) => {
        if (score == null) return <Tag>未分析</Tag>;
        const color = score >= 0 ? "#cf1322" : "#3f8600";
        return <Text style={{ color, fontWeight: 500 }}>{score}</Text>;
      },
    },
    {
      title: "情绪标签",
      dataIndex: "sentiment_score",
      key: "tag",
      width: 90,
      align: "center" as const,
      render: (score: number | null) => sentimentTag(score),
    },
  ];

  const paginationConfig = useMemo(() => ({
    pageSize,
    showSizeChanger: true,
    pageSizeOptions: ["10", "20", "50", "100"],
    showTotal: (t: number) => `共 ${t} 条`,
    onChange: (p: number) => setPage(p),
    onShowSizeChange: (_: number, size: number) => { setPageSize(size); setPage(1); },
  }), [pageSize]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>新闻情绪分析 {unanalyzedCount != null && (
          <Tag color="orange" style={{ fontSize: 14, marginLeft: 8 }}>待分析: {unanalyzedCount}</Tag>
        )}</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            icon={<SettingOutlined />}
            onClick={() => setPromptModalOpen(true)}
          >
            提示词设置
          </Button>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={analyzing}
            onClick={() => runAnalysis()}
          >
            智能分析
          </Button>
        </div>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <RangePicker
          value={dateRange}
          onChange={(v) => { setDateRange(v as [Dayjs, Dayjs] | null); setPage(1); }}
          allowClear
          placeholder={["开始日期", "结束日期"]}
        />
      </Space>

      <Table
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        onRow={(record) => ({
          onClick: () => {
            if (!record.sentiment_detail) return;
            setExpandedKeys((prev) =>
              prev.includes(record.id)
                ? prev.filter((k) => k !== record.id)
                : [...prev, record.id],
            );
          },
          style: { cursor: record.sentiment_detail ? "pointer" : "default" },
        })}
        expandable={{
          expandedRowKeys: expandedKeys,
          onExpandedRowsChange: (keys) => setExpandedKeys(keys as string[]),
          expandedRowRender: (record) => {
            const detail = record.sentiment_detail as Record<string, unknown> | null;
            if (!detail) return <Text type="secondary">暂未分析</Text>;
            return (
              <div style={{ padding: "8px 0" }}>
                <div style={{ marginBottom: 8 }}>
                  <Text strong>分析内容：</Text>
                  <Text>{(detail.analysis_content as string) ?? "-"}</Text>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <Text strong>情绪判断：</Text>
                  <Text>{(detail.sentiment as string) ?? "-"}</Text>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <Text strong>影响级别：</Text>
                  <Text>{(detail.impact_level as string) ?? "-"}</Text>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <Text strong>关键词：</Text>
                  {detail.keywords
                    ? (detail.keywords as string[]).map((k, i) => (
                        <Tag key={i} style={{ marginRight: 4 }}>{k}</Tag>
                      ))
                    : <Text>-</Text>}
                </div>
                <div>
                  <Text strong>影响板块：</Text>
                  {detail.affected_sectors
                    ? (detail.affected_sectors as string[]).map((s, i) => (
                        <Tag key={i} color="blue" style={{ marginRight: 4 }}>{s}</Tag>
                      ))
                    : <Text>-</Text>}
                </div>
              </div>
            );
          },
          rowExpandable: (record) => record.sentiment_detail != null,
        }}
        pagination={{
          ...paginationConfig,
          current: page,
          total: data?.total ?? 0,
        }}
      />
      <PromptEditor open={promptModalOpen} onClose={() => setPromptModalOpen(false)} filter="news_sentiment" />
    </div>
  );
}
