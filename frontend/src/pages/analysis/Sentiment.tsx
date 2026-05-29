import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card, Row, Col, Table, Tag, Typography, Button, Popconfirm, message,
} from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { listSentiment, getLatestSentiment, clearSentiment } from "@/api/analysis";
import type { MarketSentiment } from "@/api/analysis";
import { SentimentGauge } from "@/components/SentimentGauge";
import dayjs from "dayjs";

const { Text } = Typography;

export function Sentiment() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const queryClient = useQueryClient();

  const { data: latest } = useQuery({
    queryKey: ["sentiment", "latest"],
    queryFn: async () => {
      const res = await getLatestSentiment();
      return res.success ? res.data : null;
    },
  });

  const { data: history, isLoading } = useQuery({
    queryKey: ["sentiment", "history", page],
    queryFn: async () => {
      const res = await listSentiment({ page, page_size: pageSize });
      return res.success ? res.data : { items: [], total: 0, page: 1, page_size: 20 };
    },
  });

  const clearMutation = useMutation({
    mutationFn: clearSentiment,
    onSuccess: (res) => {
      const deleted = res.success ? res.data.deleted : 0;
      message.success(`已清空 ${deleted} 条情绪记录`);
      queryClient.invalidateQueries({ queryKey: ["sentiment"] });
    },
    onError: () => message.error("清空失败"),
  });

  const columns = [
    {
      title: "日期",
      dataIndex: "date",
      key: "date",
      width: 120,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD"),
    },
    {
      title: "情绪评分",
      dataIndex: "composite_sentiment_score",
      key: "composite_sentiment_score",
      width: 100,
      render: (v: number | null) => {
        if (v == null) return "-";
        return (
          <Tag color={v >= 60 ? "green" : v >= 40 ? "orange" : "red"}>
            {v.toFixed(1)}
          </Tag>
        );
      },
    },
    {
      title: "涨停数",
      dataIndex: "limit_up_count",
      key: "limit_up_count",
      width: 80,
      align: "right" as const,
      render: (v: number | null) => v ?? "-",
    },
    {
      title: "跌停数",
      dataIndex: "limit_down_count",
      key: "limit_down_count",
      width: 80,
      align: "right" as const,
      render: (v: number | null) => v ?? "-",
    },
    {
      title: "北向净流入(亿)",
      dataIndex: "north_bound_net_inflow",
      key: "north_bound_net_inflow",
      width: 130,
      align: "right" as const,
      render: (v: number | null) =>
        v != null ? (v / 1e8).toFixed(2) : "-",
    },
    {
      title: "上涨家数",
      dataIndex: "advance_count",
      key: "advance_count",
      width: 90,
      align: "right" as const,
      render: (v: number | null) => v ?? "-",
    },
    {
      title: "下跌家数",
      dataIndex: "decline_count",
      key: "decline_count",
      width: 90,
      align: "right" as const,
      render: (v: number | null) => v ?? "-",
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

  const score = (latest as MarketSentiment | null)?.composite_sentiment_score ?? 50;

  return (
    <div>
      <h2>市场情绪</h2>
      <Row gutter={24}>
        <Col xs={24} md={10}>
          <Card title="当前情绪">
            <SentimentGauge score={score} />
            {(latest as MarketSentiment | null) && (
              <div style={{ textAlign: "center" }}>
                <Text type="secondary">
                  数据日期: {dayjs((latest as MarketSentiment).date).format("YYYY-MM-DD")}
                </Text>
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} md={14}>
          <Card
            title="情绪历史"
            extra={
              <Popconfirm
                title="确定清空全部情绪历史数据？此操作不可撤销。"
                onConfirm={() => clearMutation.mutate()}
                okText="确定"
                cancelText="取消"
              >
                <Button
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  loading={clearMutation.isPending}
                >
                  清空
                </Button>
              </Popconfirm>
            }
          >
            <Table
              columns={columns}
              dataSource={history?.items ?? []}
              rowKey="id"
              loading={isLoading}
              size="small"
              pagination={{
                ...paginationConfig,
                current: page,
                total: history?.total ?? 0,
              }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
