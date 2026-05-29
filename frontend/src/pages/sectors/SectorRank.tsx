import { useNavigate } from "react-router-dom";
import { Table, Select, Typography, Button, message, Tooltip, Switch, Space } from "antd";
import { StarFilled, StarOutlined, RobotOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSectorRank, type SectorRankItem } from "@/api/sectors";
import { listWatchedSectors, watchSector, unwatchSector } from "@/api/watchlist";
import { usePageSearchParams } from "@/hooks/usePageSearchParams";
import { useState, useMemo } from "react";
import type { ChatContext } from "@/api/chat";
import { ChatDialog } from "@/components/ChatDialog";

const { Text } = Typography;

export function SectorRank() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = usePageSearchParams({ category: "industry" });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(30);

  const [watchedOnly, setWatchedOnly] = useState(false);
  const [sortBy, setSortBy] = useState("realtime_change_pct");
  const [chatContext, setChatContext] = useState<ChatContext | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["sectors", "rank", params.category, page, pageSize, sortBy, watchedOnly],
    queryFn: async () => {
      const res = await getSectorRank({ category: params.category, page, page_size: pageSize, sort_by: sortBy, watched_only: watchedOnly || undefined });
      return res.success ? res.data : { items: [], total: 0, page: 1, page_size: 30 };
    },
    refetchInterval: 60_000,
  });

  // 关注板块 ID 集合
  const { data: watchedIds } = useQuery({
    queryKey: ["watchlist", "sector-ids"],
    queryFn: async () => {
      const res = await listWatchedSectors();
      if (!res.success) return new Set<string>();
      return new Set((res.data.items ?? []).map((w) => w.sector_id));
    },
  });

  const { mutate: doWatch } = useMutation({
    mutationFn: (sectorId: string) => watchSector(sectorId),
    onSuccess: () => {
      message.success("已关注");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
    onError: () => message.error("关注失败"),
  });

  const { mutate: doUnwatch } = useMutation({
    mutationFn: (sectorId: string) => unwatchSector(sectorId),
    onSuccess: () => {
      message.success("已取消关注");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
    onError: () => message.error("取消关注失败"),
  });

  const paginationConfig = useMemo(
    () => ({
      current: page,
      pageSize,
      showSizeChanger: true,
      pageSizeOptions: ["10", "20", "30", "50", "100"],
      showTotal: (t: number) => `共 ${t} 个板块`,
      onChange: (p: number) => setPage(p),
      onShowSizeChange: (_: number, size: number) => { setPageSize(size); setPage(1); },
    }),
    [page, pageSize],
  );

  const columns = [
    {
      title: "",
      key: "watch",
      width: 36,
      render: (_: unknown, r: SectorRankItem) => {
        const isWatched = watchedIds?.has(r.sector_id) ?? false;
        return isWatched ? (
          <Button
            type="link"
            size="small"
            icon={<StarFilled style={{ color: "#faad14" }} />}
            onClick={(e) => { e.stopPropagation(); doUnwatch(r.sector_id); }}
          />
        ) : (
          <Button
            type="link"
            size="small"
            icon={<StarOutlined />}
            onClick={(e) => { e.stopPropagation(); doWatch(r.sector_id); }}
          />
        );
      },
    },
    { title: "#", key: "idx", width: 50, render: (_: unknown, __: unknown, i: number) => i + 1 },
    { title: "板块名称", dataIndex: "sector_name", key: "sector_name", ellipsis: true },
    {
      title: "分类",
      dataIndex: "category",
      key: "category",
      width: 90,
      render: (v: string) => v === "industry" ? "行业" : "概念",
    },
    {
      title: "最新价",
      dataIndex: "price",
      key: "price",
      width: 110,
      align: "right" as const,
      render: (v: string | null) => v ? (
        <Tooltip title={v}>
          <span>{parseFloat(v).toFixed(2)}</span>
        </Tooltip>
      ) : "-",
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      key: "change_pct",
      width: 100,
      align: "right" as const,
      render: (v: string | null) => {
        if (v == null) return "-";
        const n = parseFloat(v);
        const color = n >= 0 ? "#cf1322" : "#3f8600";
        return (
          <Text style={{ color, fontWeight: 500 }}>
            {n >= 0 ? "+" : ""}{n.toFixed(2)}%
          </Text>
        );
      },
    },
    {
      title: "实时估算价",
      dataIndex: "realtime_price",
      key: "realtime_price",
      width: 120,
      align: "right" as const,
      render: (v: string | null) => v ? parseFloat(v).toFixed(2) : "-",
    },
    {
      title: "实时涨跌幅",
      dataIndex: "realtime_change_pct",
      key: "realtime_change_pct",
      width: 120,
      align: "right" as const,
      sorter: true,
      defaultSortOrder: "descend",
      render: (v: string | null) => {
        if (v == null) return "-";
        const n = parseFloat(v);
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
      render: (_: unknown, r: SectorRankItem) => (
        <Button
          type="link"
          size="small"
          icon={<RobotOutlined />}
          onClick={(e) => {
            e.stopPropagation();
            setChatContext({ sector_id: r.sector_id, sector_name: r.sector_name });
          }}
        >
          问询
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h2>板块排行</h2>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
        <Select
          value={params.category}
          onChange={(v) => setParams({ category: v })}
          style={{ width: 120 }}
          options={[
            { value: "industry", label: "行业" },
            { value: "concept", label: "概念" },
          ]}
        />
        <Space size={4} style={{ lineHeight: "32px" }}>
          <Switch
            checked={watchedOnly}
            onChange={setWatchedOnly}
          />
          <span>仅已关注</span>
          <StarFilled style={{ color: watchedOnly ? "#faad14" : "#d9d9d9" }} />
        </Space>
      </div>
      <Table
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="sector_id"
        loading={isLoading}
        scroll={{ x: "max-content" }}
        pagination={{
          ...paginationConfig,
          total: data?.total ?? 0,
        }}
        onChange={(_p, _f, sorter) => {
          if (Array.isArray(sorter)) return;
          if (!sorter.order) return;
          const newSort = sorter.order === "descend" ? "realtime_change_pct" : "change_pct";
          if (newSort === sortBy) return;
          setSortBy(newSort);
          setPage(1);
        }}
        onRow={(r: SectorRankItem) => ({
          onClick: () => navigate(`/sectors/${r.sector_id}`),
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
