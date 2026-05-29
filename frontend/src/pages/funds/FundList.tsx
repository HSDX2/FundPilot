import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Table, Input, Select, Space, Tag, Typography, Button, message, Tooltip, Switch } from "antd";
import { SearchOutlined, StarFilled, StarOutlined, RobotOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { searchFunds, type FundItem } from "@/api/funds";
import { listWatchedFunds, watchFund, unwatchFund } from "@/api/watchlist";
import { usePageSearchParams } from "@/hooks/usePageSearchParams";
import type { ChatContext } from "@/api/chat";
import { ChatDialog } from "@/components/ChatDialog";

const { Text } = Typography;

const FUND_TYPES: Record<string, string> = {
  stock: "股票型",
  mixed: "混合型",
  index: "指数型",
  etf: "ETF",
  bond: "债券型",
  monetary: "货币型",
  qdii: "QDII",
};

export function FundList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = usePageSearchParams({
    name: "", type: "", company: "",
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const sortBy = "estimate_change_pct";
  const sortOrder = "desc";
  const [watchedOnly, setWatchedOnly] = useState(false);

  const [chatContext, setChatContext] = useState<ChatContext | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["funds", { page, name: params.name, type: params.type, company: params.company, pageSize, watchedOnly }],
    queryFn: async () => {
      const res = await searchFunds({
        page,
        page_size: pageSize,
        name: params.name || undefined,
        type: params.type || undefined,
        company: params.company || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        watched_only: watchedOnly || undefined,
      });
      return res.success ? res.data : { items: [], total: 0, page: 1, page_size: 20 };
    },
    staleTime: 0,
  });

  // 关注基金 ID 集合
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

  const paginationConfig = useMemo(() => ({
    current: page,
    pageSize,
    showSizeChanger: true,
    pageSizeOptions: ["10", "20", "50", "100"],
    showTotal: (t: number) => `共 ${t} 条`,
    onChange: (p: number) => setPage(p),
    onShowSizeChange: (_: number, size: number) => { setPageSize(size); setPage(1); },
  }), [page, pageSize]);

  const columns = [
    {
      title: "",
      key: "watch",
      width: 36,
      render: (_: unknown, r: FundItem) => {
        const isWatched = watchedIds?.has(r.id) ?? false;
        return isWatched ? (
          <Button
            type="link"
            size="small"
            icon={<StarFilled style={{ color: "#faad14" }} />}
            onClick={(e) => { e.stopPropagation(); doUnwatch(r.id); }}
          />
        ) : (
          <Button
            type="link"
            size="small"
            icon={<StarOutlined />}
            onClick={(e) => { e.stopPropagation(); doWatch(r.id); }}
          />
        );
      },
    },
    { title: "代码", dataIndex: "code", key: "code", width: 90 },
    { title: "名称", dataIndex: "name", key: "name", width: 180, ellipsis: true },
    {
      title: "类型",
      dataIndex: "type",
      key: "type",
      width: 80,
      render: (v: string) => <Tag>{FUND_TYPES[v] ?? v}</Tag>,
    },
    {
      title: "最新净值",
      key: "nav",
      width: 130,
      align: "right" as const,
      render: (_: unknown, r: FundItem) => {
        if (r.latest_nav == null) return r.latest_price != null ? Number(r.latest_price).toFixed(4) : "-";
        const n = Number(r.latest_nav);
        if (isNaN(n)) return "-";
        return (
          <Tooltip title={r.latest_nav_date ?? ""}>
            {n.toFixed(4)}
          </Tooltip>
        );
      },
    },
    {
      title: "日涨跌幅",
      key: "daily_pct",
      width: 110,
      align: "right" as const,
      render: (_: unknown, r: FundItem) => {
        let pct: number | null = null;
        if (r.latest_nav_change_pct != null) {
          pct = Number(r.latest_nav_change_pct);
        }
        if (pct == null || isNaN(pct)) {
          // 回退到 ETF 实时涨跌幅
          const fallback = r.latest_change_pct;
          if (fallback != null) {
            const n = Number(fallback);
            if (!isNaN(n)) pct = n;
          }
        }
        if (pct == null) return "-";
        const color = pct >= 0 ? "#cf1322" : "#3f8600";
        return (
          <Tooltip title={r.latest_nav_date ?? ""}>
            <Text style={{ color, fontWeight: 500 }}>
              {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
            </Text>
          </Tooltip>
        );
      },
    },
    {
      title: "盘中估值",
      key: "estimate_nav",
      width: 100,
      align: "right" as const,
      render: (_: unknown, r: FundItem) => {
        if (r.estimate_nav == null) return "-";
        const n = Number(r.estimate_nav);
        return isNaN(n) ? "-" : n.toFixed(4);
      },
    },
    {
      title: "估算涨跌",
      key: "estimate_pct",
      width: 100,
      align: "right" as const,
      sorter: true,
      defaultSortOrder: "descend",
      render: (_: unknown, r: FundItem) => {
        if (r.estimate_change_pct == null) return "-";
        const n = Number(r.estimate_change_pct);
        if (isNaN(n)) return "-";
        const color = n >= 0 ? "#cf1322" : "#3f8600";
        return (
          <Text style={{ color, fontWeight: 500 }}>
            {n >= 0 ? "+" : ""}{n.toFixed(2)}%
          </Text>
        );
      },
    },
    {
      title: "操作",
      key: "action",
      width: 90,
      render: (_: unknown, r: FundItem) => (
        <Button
          type="link"
          size="small"
          icon={<RobotOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            setChatContext({ fund_code: r.code, fund_name: r.name });
          }}
        >
          问询
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h2>基金查询</h2>
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="基金名称"
          prefix={<SearchOutlined />}
          value={params.name}
          onChange={(e) => { setPage(1); setParams({ name: e.target.value }); }}
          style={{ width: 200 }}
          allowClear
        />
        <Select
          placeholder="基金类型"
          value={params.type || undefined}
          onChange={(v) => { setPage(1); setParams({ type: v ?? "" }); }}
          allowClear
          style={{ width: 120 }}
          options={Object.entries(FUND_TYPES).map(([k, v]) => ({ value: k, label: v }))}
        />
        <Input
          placeholder="基金公司"
          value={params.company}
          onChange={(e) => { setPage(1); setParams({ company: e.target.value }); }}
          style={{ width: 160 }}
          allowClear
        />
        <Space size={4} style={{ lineHeight: "32px" }}>
          <Switch
            checked={watchedOnly}
            onChange={(v) => { setWatchedOnly(v); setPage(1); }}
          />
          <span>仅已关注</span>
          <StarFilled style={{ color: watchedOnly ? "#faad14" : "#d9d9d9" }} />
        </Space>
      </Space>
      <Table
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        scroll={{ x: "max-content" }}
        pagination={{
          ...paginationConfig,
          total: data?.total ?? 0,
        }}
        onChange={(_p, _f, sorter) => {
          if (Array.isArray(sorter)) return;
          if (!sorter.order) return;
        }}
        onRow={(r: FundItem) => ({
          onClick: () => navigate(`/funds/${r.code}`),
          style: { cursor: "pointer" },
        })}
      />
      <ChatDialog
        open={chatContext != null}
        onClose={() => setChatContext(null)}
        context={chatContext ?? {}}
      />
    </div>
  );
}
