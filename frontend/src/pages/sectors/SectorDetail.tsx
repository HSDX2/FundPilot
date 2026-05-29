import { useState, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Descriptions, Card, Table, Spin, Empty, Typography, Button, message, Modal, DatePicker, Checkbox,
} from "antd";
import {
  getSectorDetail, getSectorMoneyFlow,
  collectSectorData, getSectorSnapshots,
} from "@/api/sectors";
import { extractErrorMessage } from "@/api/client";
import { RobotOutlined, HistoryOutlined, DownloadOutlined } from "@ant-design/icons";
import { ChatDialog } from "@/components/ChatDialog";
import dayjs from "dayjs";

const { Text } = Typography;

export function SectorDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [chatOpen, setChatOpen] = useState(false);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [historyStartDate, setHistoryStartDate] = useState<dayjs.Dayjs | null>(null);
  const [latestModalOpen, setLatestModalOpen] = useState(false);
  const [backfillMfDetail, setBackfillMfDetail] = useState(true);

  const { data: sector, isLoading } = useQuery({
    queryKey: ["sector", id],
    queryFn: async () => {
      const res = await getSectorDetail(id!);
      return res.success ? res.data : null;
    },
    enabled: !!id,
  });

  const { data: flows } = useQuery({
    queryKey: ["sector", "money-flow", id],
    queryFn: async () => {
      const res = await getSectorMoneyFlow(id!);
      return res.success ? res.data.items : [];
    },
    enabled: !!id,
  });

  const { data: snapshots } = useQuery({
    queryKey: ["sector", "snapshots", id],
    queryFn: async () => {
      const res = await getSectorSnapshots(id!);
      return res.success ? res.data.items : [];
    },
    enabled: !!id,
  });

  const { mutate: collectHistory, isPending: collectingHistory } = useMutation({
    mutationFn: (startDate?: string) => collectSectorData(id!, "all", startDate),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`历史数据采集完成：新增 ${res.data.added}，更新 ${res.data.updated}`);
        queryClient.invalidateQueries({ queryKey: ["sector", id], refetchType: "active" });
        queryClient.invalidateQueries({ queryKey: ["sector", "money-flow", id], refetchType: "active" });
        queryClient.invalidateQueries({ queryKey: ["sector", "snapshots", id], refetchType: "active" });
      } else message.error("历史数据采集失败");
    },
    onError: async (err) => {
      const msg = await extractErrorMessage(err, "历史数据采集请求失败");
      message.error(msg);
    },
  });

  const { mutate: collectLatest, isPending: collectingLatest } = useMutation({
    mutationFn: (backfillDetail?: boolean) =>
      collectSectorData(id!, "incremental", undefined, backfillDetail),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`最新数据采集完成：新增 ${res.data.added}，更新 ${res.data.updated}`);
        queryClient.invalidateQueries({ queryKey: ["sector", id], refetchType: "active" });
        queryClient.invalidateQueries({ queryKey: ["sector", "money-flow", id], refetchType: "active" });
        queryClient.invalidateQueries({ queryKey: ["sector", "snapshots", id], refetchType: "active" });
      } else message.error("最新数据采集失败");
    },
    onError: async (err) => {
      const msg = await extractErrorMessage(err, "最新数据采集请求失败");
      message.error(msg);
    },
  });

  const flowPagination = useMemo(() => ({ pageSize: 10 }), []);
  const snapshotPagination = useMemo(
    () => ({ pageSize: 15, showSizeChanger: true, pageSizeOptions: ["15", "30", "50"] as const }),
    [],
  );

  const sortedSnapshots = useMemo(() => {
    if (!snapshots) return [];
    // 按日期分组，每天只取一条 OHLC 完整数据（优先取含开高低收的记录，如 16:00 收盘数据）
    const byDate = new Map<string, typeof snapshots[number]>();
    for (const s of snapshots) {
      const day = s.timestamp;
      const existing = byDate.get(day);
      if (!existing) {
        byDate.set(day, s);
      } else {
        // 优先保留 open/high/low 更完整的记录（OHLC vs 实时快照）
        const existingScore = (existing.open ? 1 : 0) + (existing.high ? 1 : 0) + (existing.low ? 1 : 0);
        const currentScore = (s.open ? 1 : 0) + (s.high ? 1 : 0) + (s.low ? 1 : 0);
        if (currentScore > existingScore) {
          byDate.set(day, s);
        }
      }
    }
    return [...byDate.values()].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }, [snapshots]);

  if (isLoading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  if (!sector) return <Empty description="未找到该板块" />;

  const flowColumns = [
    { title: "日期", dataIndex: "date", key: "date", width: 120 },
    {
      title: "主力净流入",
      dataIndex: "main_force_net_inflow",
      key: "main_force_net_inflow",
      align: "right" as const,
      render: (v: number | null) => {
        if (v == null) return "-";
        return (
          <Text style={{ color: Number(v) >= 0 ? "#cf1322" : "#3f8600" }}>
            {v >= 0 ? "+" : ""}{(Number(v) / 1e8).toFixed(2)} 亿
          </Text>
        );
      },
    },
    {
      title: "中单净流入",
      dataIndex: "middle_net_inflow",
      key: "middle_net_inflow",
      align: "right" as const,
      render: (v: number | null) => {
        if (v == null) return "-";
        return <Text>{(Number(v) / 1e8).toFixed(2)} 亿</Text>;
      },
    },
    {
      title: "散户净流入",
      dataIndex: "retail_net_inflow",
      key: "retail_net_inflow",
      align: "right" as const,
      render: (v: number | null) => {
        if (v == null) return "-";
        return <Text>{(Number(v) / 1e8).toFixed(2)} 亿</Text>;
      },
    },
  ];

  const snapshotColumns = [
    { title: "日期", dataIndex: "timestamp", key: "timestamp", width: 120,
      render: (v: string) => v || "-",
    },
    {
      title: "收盘价",
      dataIndex: "price",
      key: "price",
      align: "right" as const,
      render: (v: number | null) => v != null ? Number(v).toFixed(2) : "-",
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      key: "change_pct",
      align: "right" as const,
      render: (v: number | null) => {
        if (v == null) return "-";
        return (
          <Text style={{ color: Number(v) >= 0 ? "#cf1322" : "#3f8600" }}>
            {v >= 0 ? "+" : ""}{Number(v).toFixed(2)}%
          </Text>
        );
      },
    },
    {
      title: "开盘价",
      dataIndex: "open",
      key: "open",
      align: "right" as const,
      render: (v: number | null) => v != null ? Number(v).toFixed(2) : "-",
    },
    {
      title: "最高价",
      dataIndex: "high",
      key: "high",
      align: "right" as const,
      render: (v: number | null) => v != null ? Number(v).toFixed(2) : "-",
    },
    {
      title: "最低价",
      dataIndex: "low",
      key: "low",
      align: "right" as const,
      render: (v: number | null) => v != null ? Number(v).toFixed(2) : "-",
    },
    {
      title: "成交量（万手）",
      dataIndex: "volume",
      key: "volume",
      align: "right" as const,
      render: (v: number | null) => v != null ? `${(Number(v) / 1e4).toFixed(0)} 万手` : "-",
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 0 }}>
        <h2 style={{ margin: 0 }}>{sector.name}</h2>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <Button
            icon={<HistoryOutlined />}
            loading={collectingHistory}
            onClick={() => setHistoryModalOpen(true)}
          >获取历史数据</Button>
          <Button
            icon={<DownloadOutlined />}
            loading={collectingLatest}
            onClick={() => setLatestModalOpen(true)}
          >获取最新数据</Button>
          <Button type="primary" icon={<RobotOutlined />} onClick={() => setChatOpen(true)}>AI 问询</Button>
        </div>
      </div>
      <Card style={{ marginTop: 16 }}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="代码">{sector.code ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="分类">
            {sector.category === "industry" ? "行业" : "概念"}
          </Descriptions.Item>
          <Descriptions.Item label="描述">
            {sector.description ?? "-"}
          </Descriptions.Item>
          <Descriptions.Item label="最新价">
            {sector.price != null ? Number(sector.price).toFixed(2) : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="涨跌幅">
            <Text
              strong
              style={{
                color: (Number(sector.change_pct) ?? 0) >= 0 ? "#cf1322" : "#3f8600",
              }}
            >
              {sector.change_pct != null
                ? `${Number(sector.change_pct) >= 0 ? "+" : ""}${Number(sector.change_pct).toFixed(2)}%`
                : "-"}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="成交量">
            {sector.volume != null ? `${(Number(sector.volume) / 1e4).toFixed(0)} 万手` : "-"}
          </Descriptions.Item>
          <Descriptions.Item label="实时估算价">
            <Text strong style={{ color: "#1890ff" }}>
              {sector.realtime?.price != null ? Number(sector.realtime.price).toFixed(2) : "-"}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="实时涨跌幅">
            <Text
              strong
              style={{
                color: (Number(sector.realtime?.change_pct) ?? 0) >= 0 ? "#cf1322" : "#3f8600",
              }}
            >
              {sector.realtime?.change_pct != null
                ? `${Number(sector.realtime.change_pct) >= 0 ? "+" : ""}${Number(sector.realtime.change_pct).toFixed(2)}%`
                : "-"}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="实时成交量">
            {sector.realtime?.volume != null ? `${(Number(sector.realtime.volume) / 1e4).toFixed(0)} 万手` : "-"}
          </Descriptions.Item>
        </Descriptions>
      </Card>


      <Card title="历史净值和涨跌幅" style={{ marginTop: 24 }}>
        {sortedSnapshots.length > 0 ? (
          <Table
            columns={snapshotColumns}
            dataSource={sortedSnapshots}
            rowKey="id"
            size="small"
            pagination={snapshotPagination}
          />
        ) : (
          <Empty description="暂无历史数据，请先点击「获取历史数据」" />
        )}
      </Card>

      <Card title="资金流向" style={{ marginTop: 24 }}>
        {flows && flows.length > 0 ? (
          <Table
            columns={flowColumns}
            dataSource={[...flows].sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""))}
            rowKey="id"
            size="small"
            pagination={flowPagination}
          />
        ) : (
          <Empty description="暂无资金流向数据" />
        )}
      </Card>
      <ChatDialog
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        context={{ sector_id: id, sector_name: sector.name }}
      />

      {/* 历史数据采集弹窗 */}
      <Modal
        title="获取板块历史数据"
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
            留空 = 回补全部历史行情和资金流向。填入日期 = 从该日起采集。
          </Text>
        </div>
      </Modal>

      {/* 最新数据采集弹窗 */}
      <Modal
        title="获取板块最新数据"
        open={latestModalOpen}
        onOk={() => {
          collectLatest(backfillMfDetail);
          setLatestModalOpen(false);
        }}
        onCancel={() => {
          setLatestModalOpen(false);
          setBackfillMfDetail(true);
        }}
        okText="开始采集"
        cancelText="取消"
        confirmLoading={collectingLatest}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <Checkbox
              checked={backfillMfDetail}
              onChange={(e) => setBackfillMfDetail(e.target.checked)}
            >
              补充中单/散户资金流向细分
            </Checkbox>
          </div>
          <Text type="secondary" style={{ fontSize: 12 }}>
            勾选 = 通过 EM push2his 获取详细资金流向（含中单/散户），可能因 WAF 拦截失败。
            取消勾选 = 仅通过 THS 获取资金总额（无细分数据），可避免 WAF 拦截问题。
          </Text>
        </div>
      </Modal>
    </div>
  );
}
