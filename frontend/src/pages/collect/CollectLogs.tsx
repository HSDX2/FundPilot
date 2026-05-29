import {
  Table, Select, Tag, Typography, message, Tooltip, Button, Popconfirm, Space,
} from "antd";
import { CopyOutlined, DeleteOutlined } from "@ant-design/icons";
import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCollectLogs, clearCollectLogs, getCollectSettings } from "@/api/collect";
import { usePageSearchParams } from "@/hooks/usePageSearchParams";
import dayjs from "dayjs";

const { Text } = Typography;

const COLLECTOR_LABELS: Record<string, string> = {
  fund_list: "基金列表",
  etf: "ETF 行情",
  sector_list: "板块列表",
  fund_nav_history: "基金净值历史数据",
  fund_nav_daily: "基金净值每日数据",
  news: "新闻",
  market_sentiment: "市场情绪",
  sector_batch_history: "板块历史数据",
  sector_batch_daily: "板块每日数据",
};

function formatDuration(ms: number | null): string {
  if (ms == null || ms <= 0) return "-";
  if (ms < 1000) return `${ms}ms`;
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [
    String(hours).padStart(2, "0"),
    String(minutes).padStart(2, "0"),
    String(seconds).padStart(2, "0"),
  ].join(":");
}

export function CollectLogs() {
  const queryClient = useQueryClient();
  const [params, setParams] = usePageSearchParams({ page: "1", page_size: "20", collector: "" });
  const page = Number(params.page) || 1;
  const pageSize = Number(params.page_size) || 20;

  const paginationConfig = useMemo(
    () => ({
      pageSize,
      showSizeChanger: true,
      pageSizeOptions: ["10", "20", "50", "100"] as const,
      onChange: (p: number) => setParams({ page: String(p) }),
      onShowSizeChange: (_: number, size: number) => setParams({ page: "1", page_size: String(size) }),
      showTotal: (t: number) => `共 ${t} 条`,
    }),
    [pageSize, setParams],
  );

  const { data: settingsData } = useQuery({
    queryKey: ["collect", "settings"],
    queryFn: async () => {
      const res = await getCollectSettings();
      return res.success ? res.data.items : [];
    },
    staleTime: 30_000,
  });

  const collectorOptions = useMemo(() => {
    const sorted = (settingsData ?? []).sort((a, b) => a.sort_order - b.sort_order);
    return sorted.map((s) => ({
      value: s.collector_name,
      label: (s.display_name || COLLECTOR_LABELS[s.collector_name]) ?? s.collector_name,
    }));
  }, [settingsData]);

  const { data, isLoading } = useQuery({
    queryKey: ["collect", "logs", { page, page_size: pageSize, collector: params.collector }],
    queryFn: async () => {
      const res = await getCollectLogs({
        collector: params.collector || undefined,
        page,
        page_size: pageSize,
      });
      return res.success
        ? res.data
        : { items: [], total: 0, page: 1, page_size: pageSize };
    },
  });

  const clearMutation = useMutation({
    mutationFn: clearCollectLogs,
    onSuccess: (res) => {
      const deleted = res.success ? res.data.deleted : 0;
      message.success(`已清空 ${deleted} 条日志`);
      queryClient.invalidateQueries({ queryKey: ["collect", "logs"] });
    },
    onError: () => message.error("清空失败"),
  });

  const columns = [
    {
      title: "采集器",
      dataIndex: "collector_name",
      key: "collector_name",
      width: 120,
      render: (_v: string, record: CollectLog) => record.display_name || record.collector_name,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 80,
      render: (v: string) => {
        const color =
          v === "success" ? "green" :
          v === "failed" ? "red" :
          v === "partial" ? "orange" :
          v === "stopped" ? "orange" : "blue";
        const label =
          v === "success" ? "完成" :
          v === "failed" ? "失败" :
          v === "partial" ? "部分失败" :
          v === "stopped" ? "已停止" : "运行中";
        return <Tag color={color}>{label}</Tag>;
      },
    },
    {
      title: "新增",
      dataIndex: "records_added",
      key: "records_added",
      width: 70,
      align: "right" as const,
    },
    {
      title: "更新",
      dataIndex: "records_updated",
      key: "records_updated",
      width: 70,
      align: "right" as const,
    },
    {
      title: "错误",
      dataIndex: "error_message",
      key: "error_message",
      width: 220,
      ellipsis: true,
      render: (v: string | null) => {
        if (!v) return <Text type="secondary">无</Text>;
        const copy = () => {
          navigator.clipboard.writeText(v).then(
            () => message.success("已复制"),
            () => message.error("复制失败"),
          );
        };
        return (
          <Tooltip title={v} placement="topLeft">
            <Text
              type="danger"
              style={{ cursor: "pointer", userSelect: "all" }}
              onClick={copy}
            >
              {v}
              <CopyOutlined style={{ marginLeft: 4, fontSize: 11, opacity: 0.5 }} />
            </Text>
          </Tooltip>
        );
      },
    },
    {
      title: "开始时间",
      dataIndex: "started_at",
      key: "started_at",
      width: 160,
      render: (v: string | null) =>
        v ? dayjs(v).format("MM-DD HH:mm:ss") : "-",
    },
    {
      title: "结束时间",
      dataIndex: "finished_at",
      key: "finished_at",
      width: 160,
      render: (v: string | null) =>
        v ? dayjs(v).format("MM-DD HH:mm:ss") : "-",
    },
    {
      title: "总耗时",
      dataIndex: "duration_ms",
      key: "duration_ms",
      width: 90,
      render: (v: number | null) => formatDuration(v),
    },
  ];

  return (
    <div>
      <h2>采集日志</h2>
      <Space style={{ marginBottom: 16 }}>
        <Select
          placeholder="按任务类型搜索"
          value={params.collector || undefined}
          onChange={(v) => setParams({ collector: v ?? "", page: "1" })}
          allowClear
          showSearch
          optionFilterProp="label"
          style={{ width: 200 }}
          options={collectorOptions}
        />
        <Popconfirm
          title="确定清空全部采集日志？此操作不可撤销。"
          onConfirm={() => clearMutation.mutate()}
          okText="确定"
          cancelText="取消"
        >
          <Button
            danger
            icon={<DeleteOutlined />}
            loading={clearMutation.isPending}
          >
            清空日志
          </Button>
        </Popconfirm>
      </Space>
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
