import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Table, Tag, Tabs, Typography, Button, Popconfirm, message, Modal, Radio, InputNumber, Space } from "antd";
import { StarFilled, DeleteOutlined, ThunderboltOutlined, EditOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listWatchedFunds,
  listWatchedSectors,
  unwatchFund,
  unwatchSector,
  updateWatchedFund,
  type WatchedFund,
  type WatchedSector,
} from "@/api/watchlist";
import { generateBatchAdvice, generateAllReports } from "@/api/analysis";
import dayjs from "dayjs";

const { Text } = Typography;

const FUND_TYPES: Record<string, string> = {
  stock: "股票型", mixed: "混合型", index: "指数型", etf: "ETF",
  bond: "债券型", monetary: "货币型", qdii: "QDII",
};

export function Watchlist() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState("funds");

  // 多选分析
  const [selectedFundKeys, setSelectedFundKeys] = useState<string[]>([]);
  const [selectedSectorKeys, setSelectedSectorKeys] = useState<string[]>([]);
  const [batchReportModalOpen, setBatchReportModalOpen] = useState(false);
  const [batchReportType, setBatchReportType] = useState("daily");

  // 编辑持仓弹窗
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editFundId, setEditFundId] = useState<string>("");
  const [editAmount, setEditAmount] = useState<number | null>(null);

  const { data: fundData, isLoading: fundLoading } = useQuery({
    queryKey: ["watchlist", "funds"],
    queryFn: async () => {
      const res = await listWatchedFunds();
      return res.success ? res.data : { items: [], total: 0 };
    },
  });

  const { data: sectorData, isLoading: sectorLoading } = useQuery({
    queryKey: ["watchlist", "sectors"],
    queryFn: async () => {
      const res = await listWatchedSectors();
      return res.success ? res.data : { items: [], total: 0 };
    },
  });

  const { mutate: removeFund } = useMutation({
    mutationFn: (id: string) => unwatchFund(id),
    onSuccess: () => {
      message.success("已取消关注");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
    onError: () => message.error("操作失败"),
  });

  const { mutate: removeSector } = useMutation({
    mutationFn: (id: string) => unwatchSector(id),
    onSuccess: () => {
      message.success("已取消关注");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
    onError: () => message.error("操作失败"),
  });

  // 基金批量分析
  const { mutate: batchAnalyzeFunds, isPending: analyzingFunds } = useMutation({
    mutationFn: (fundIds: string[]) => generateBatchAdvice({ fund_ids: fundIds }),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`分析完成，共生成 ${res.data?.total ?? 0} 条建议`);
        setSelectedFundKeys([]);
        queryClient.invalidateQueries({ queryKey: ["advice"] });
      }
    },
    onError: () => message.error("批量分析失败"),
  });

  // 板块批量分析
  const { mutate: batchAnalyzeSectors, isPending: analyzingSectors } = useMutation({
    mutationFn: ({ sectorIds, rtype }: { sectorIds: string[]; rtype: string }) =>
      generateAllReports({ report_type: rtype, limit: 50, sector_ids: sectorIds }),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`分析完成，共生成 ${res.data?.total ?? 0} 份报告`);
        setSelectedSectorKeys([]);
        setBatchReportModalOpen(false);
        queryClient.invalidateQueries({ queryKey: ["reports"] });
      }
    },
    onError: () => message.error("批量分析失败"),
  });

  // 更新持仓金额
  const { mutate: saveAmount, isPending: savingAmount } = useMutation({
    mutationFn: ({ fundId, amount }: { fundId: string; amount: number | null }) =>
      updateWatchedFund(fundId, { holding_amount: amount }),
    onSuccess: () => {
      message.success("持仓金额已更新");
      setEditModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
    onError: () => message.error("更新失败"),
  });

  const fundColumns = [
    { title: "代码", dataIndex: "fund_code", key: "code", width: 90 },
    {
      title: "名称",
      dataIndex: "fund_name",
      key: "name",
      ellipsis: true,
      render: (v: string, r: WatchedFund) => (
        <a onClick={() => navigate(`/funds/${r.fund_code}`)}>{v}</a>
      ),
    },
    {
      title: "类型",
      dataIndex: "fund_type",
      key: "type",
      width: 90,
      render: (v: string | null) =>
        v ? <Tag>{FUND_TYPES[v] ?? v}</Tag> : "-",
    },
    {
      title: "盘中估值",
      dataIndex: "estimate_nav",
      key: "estimate_nav",
      width: 100,
      align: "right" as const,
      render: (v: number | null) =>
        v != null ? Number(v).toFixed(4) : "-",
    },
    {
      title: "估算涨跌",
      dataIndex: "estimate_change_pct",
      key: "estimate_pct",
      width: 100,
      align: "right" as const,
      render: (v: number | null) => {
        if (v == null) return "-";
        const n = Number(v);
        const color = n >= 0 ? "#cf1322" : "#3f8600";
        return (
          <Text style={{ color, fontWeight: 500 }}>
            {n >= 0 ? "+" : ""}{n.toFixed(2)}%
          </Text>
        );
      },
    },
    {
      title: "持仓金额",
      dataIndex: "holding_amount",
      key: "holding_amount",
      width: 120,
      align: "right" as const,
      render: (v: number | null) =>
        v != null ? `${Number(v).toLocaleString()} 元` : "-",
    },
    {
      title: "关注时间",
      dataIndex: "added_at",
      key: "added_at",
      width: 170,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm:ss"),
    },
    {
      title: "操作",
      key: "actions",
      width: 120,
      render: (_: unknown, r: WatchedFund) => (
        <span>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              setEditFundId(r.fund_id);
              setEditAmount(r.holding_amount);
              setEditModalOpen(true);
            }}
          />
          <Popconfirm
            title="确认取消关注？"
            onConfirm={() => removeFund(r.fund_id)}
          >
            <Button type="link" danger size="small" icon={<DeleteOutlined />} />
          </Popconfirm>
        </span>
      ),
    },
  ];

  const sectorColumns = [
    {
      title: "名称",
      dataIndex: "sector_name",
      key: "name",
      ellipsis: true,
      render: (v: string, r: WatchedSector) => (
        <a onClick={() => navigate(`/sectors/${r.sector_id}`)}>{v}</a>
      ),
    },
    {
      title: "分类",
      dataIndex: "sector_category",
      key: "category",
      width: 100,
      render: (v: string) =>
        v === "industry" ? <Tag color="blue">行业</Tag> : <Tag color="orange">概念</Tag>,
    },
    {
      title: "最新价",
      dataIndex: "price",
      key: "price",
      width: 100,
      align: "right" as const,
      render: (v: number | null) => v != null ? Number(v).toFixed(2) : "-",
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      key: "pct",
      width: 100,
      align: "right" as const,
      render: (v: number | null) => {
        if (v == null) return "-";
        const n = Number(v);
        const color = n >= 0 ? "#cf1322" : "#3f8600";
        return (
          <Text style={{ color, fontWeight: 500 }}>
            {n >= 0 ? "+" : ""}{n.toFixed(2)}%
          </Text>
        );
      },
    },
    {
      title: "关注时间",
      dataIndex: "added_at",
      key: "added_at",
      width: 180,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm:ss"),
    },
    {
      title: "操作",
      key: "actions",
      width: 60,
      render: (_: unknown, r: WatchedSector) => (
        <Popconfirm
          title="确认取消关注？"
          onConfirm={() => removeSector(r.sector_id)}
        >
          <Button type="link" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <h2><StarFilled style={{ color: "#faad14", marginRight: 8 }} />关注列表</h2>
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          {
            key: "funds",
            label: `关注基金 (${fundData?.total ?? 0})`,
            children: (
              <div>
                {selectedFundKeys.length > 0 && (
                  <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                    <span>已选 {selectedFundKeys.length} 只基金</span>
                    <Button
                      type="primary"
                      size="small"
                      icon={<ThunderboltOutlined />}
                      loading={analyzingFunds}
                      onClick={() => {
                        const ids = selectedFundKeys.map(
                          (k) => (fundData?.items ?? []).find((f) => f.id === k)?.fund_id ?? k,
                        );
                        batchAnalyzeFunds(ids);
                      }}
                    >
                      批量智能分析
                    </Button>
                  </div>
                )}
                <Table
                  columns={fundColumns}
                  dataSource={fundData?.items ?? []}
                  rowKey="id"
                  loading={fundLoading}
                  pagination={false}
                  rowSelection={{
                    selectedRowKeys: selectedFundKeys,
                    onChange: (keys) => setSelectedFundKeys(keys as string[]),
                  }}
                />
              </div>
            ),
          },
          {
            key: "sectors",
            label: `关注板块 (${sectorData?.total ?? 0})`,
            children: (
              <div>
                {selectedSectorKeys.length > 0 && (
                  <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                    <span>已选 {selectedSectorKeys.length} 个板块</span>
                    <Button
                      type="primary"
                      size="small"
                      icon={<ThunderboltOutlined />}
                      onClick={() => setBatchReportModalOpen(true)}
                    >
                      批量智能分析
                    </Button>
                  </div>
                )}
                <Table
                  columns={sectorColumns}
                  dataSource={sectorData?.items ?? []}
                  rowKey="id"
                  loading={sectorLoading}
                  scroll={{ x: "max-content" }}
                  pagination={false}
                  rowSelection={{
                    selectedRowKeys: selectedSectorKeys,
                    onChange: (keys) => setSelectedSectorKeys(keys as string[]),
                  }}
                />
              </div>
            ),
          },
        ]}
      />

      {/* 编辑持仓金额弹窗 */}
      <Modal
        title="编辑持仓金额"
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={() => saveAmount({ fundId: editFundId, amount: editAmount })}
        confirmLoading={savingAmount}
        okText="保存"
        cancelText="取消"
      >
        <div style={{ marginTop: 16 }}>
          <Text strong>持仓金额（元）：</Text>
          <InputNumber
            value={editAmount}
            onChange={(v) => setEditAmount(v ?? null)}
            min={0}
            style={{ width: "100%", marginTop: 8 }}
            placeholder="输入持仓金额"
            formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
            parser={(value) => value?.replace(/,/g, "") as unknown as number}
          />
          <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
            设置持仓金额后，AI 分析时会参考该数据给出更精准的建议
          </Text>
        </div>
      </Modal>

      {/* 板块批量分析弹窗 */}
      <Modal
        title="批量生成板块分析报告"
        open={batchReportModalOpen}
        onCancel={() => setBatchReportModalOpen(false)}
        onOk={() => batchAnalyzeSectors({
          sectorIds: selectedSectorKeys.map(
            (k) => (sectorData?.items ?? []).find((s) => s.id === k)?.sector_id ?? k,
          ),
          rtype: batchReportType,
        })}
        confirmLoading={analyzingSectors}
        okText="开始分析"
        cancelText="取消"
      >
        <div style={{ marginTop: 16 }}>
          <Text strong>报告类型：</Text>
          <Radio.Group
            value={batchReportType}
            onChange={(e) => setBatchReportType(e.target.value)}
            style={{ marginLeft: 12 }}
          >
            <Radio value="daily">日报</Radio>
            <Radio value="weekly">周报</Radio>
            <Radio value="monthly">月报</Radio>
          </Radio.Group>
        </div>
      </Modal>
    </div>
  );
}
