import { useMemo } from "react";
import { Table, Input, Select, Tag, Typography } from "antd";
import { SearchOutlined, LinkOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { searchNews } from "@/api/news";
import { usePageSearchParams } from "@/hooks/usePageSearchParams";
import dayjs from "dayjs";

const SOURCES = ["jin10", "cls", "wallstreetcn", "eastmoney"];

function sentimentLabel(score: number | null): { color: string; text: string } {
  if (score == null) return { color: "default", text: "未分析" };
  if (score > 0) return { color: "red", text: "正向" };
  if (score < 0) return { color: "green", text: "负向" };
  return { color: "default", text: "中性" };
}

export function NewsList() {
  const [params, setParams] = usePageSearchParams({
    page: "1", keyword: "", source: "", page_size: "20",
  });
  const page = Number(params.page) || 1;
  const pageSize = Number(params.page_size) || 20;

  const { data, isLoading } = useQuery({
    queryKey: ["news", { page, keyword: params.keyword, source: params.source }],
    queryFn: async () => {
      const res = await searchNews({
        keyword: params.keyword || undefined,
        source: params.source || undefined,
        page,
        page_size: pageSize,
      });
      return res.success
        ? res.data
        : { items: [], total: 0, page: 1, page_size: 20 };
    },
  });

  const columns = [
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (v: string, record: { url?: string | null }) =>
        record.url ? (
          <a
            href={record.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ display: "inline-flex", alignItems: "center", gap: 4 }}
          >
            <Typography.Text ellipsis style={{ maxWidth: 400 }}>
              {v}
            </Typography.Text>
            <LinkOutlined style={{ fontSize: 12, opacity: 0.4, flexShrink: 0 }} />
          </a>
        ) : (
          v
        ),
    },
    {
      title: "来源",
      dataIndex: "source",
      key: "source",
      width: 90,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: "情感",
      dataIndex: "sentiment_score",
      key: "sentiment",
      width: 90,
      render: (v: number | null) => {
        const s = sentimentLabel(v);
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: "情感评分",
      dataIndex: "sentiment_score",
      key: "sentiment_score",
      width: 90,
      align: "right" as const,
      render: (v: number | null) =>
        v != null ? v.toFixed(2) : "-",
    },
    {
      title: "发布时间",
      dataIndex: "published_at",
      key: "published_at",
      width: 170,
      render: (v: string | null) =>
        v ? dayjs(v).format("YYYY-MM-DD HH:mm:ss") : "-",
    },
  ];

  const paginationConfig = useMemo(() => ({
    pageSize,
    showSizeChanger: true,
    pageSizeOptions: ["10", "20", "50", "100"],
    showTotal: (t: number) => `共 ${t} 条`,
    onChange: (p: number) => setParams({ page: String(p) }),
    onShowSizeChange: (_: number, size: number) => setParams({ page: "1", page_size: String(size) }),
  }), [pageSize]);

  return (
    <div>
      <h2>新闻资讯</h2>
      <div style={{ marginBottom: 16, display: "flex", gap: 12 }}>
        <Input
          placeholder="关键词搜索"
          prefix={<SearchOutlined />}
          value={params.keyword}
          onChange={(e) => setParams({ keyword: e.target.value, page: "1" })}
          style={{ width: 240 }}
          allowClear
        />
        <Select
          placeholder="来源"
          value={params.source || undefined}
          onChange={(v) => setParams({ source: v ?? "", page: "1" })}
          allowClear
          style={{ width: 140 }}
          options={SOURCES.map((s) => ({ value: s, label: s }))}
        />
      </div>
      <Table
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        pagination={{
          ...paginationConfig,
          current: page,
          total: data?.total ?? 0,
        }}
      />
    </div>
  );
}
