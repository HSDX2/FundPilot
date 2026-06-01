import { useState, useEffect, useMemo } from "react";
import { Table, Select, Tag, Button, Modal, InputNumber, Radio, Input, Space, message, Typography, Card, DatePicker, Popconfirm } from "antd";
import { SearchOutlined, ThunderboltOutlined, SettingOutlined, DeleteOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listAdvice, generateBatchAdvice, batchDeleteAdvice, type FundAdvice } from "@/api/analysis";
import { searchFunds, type FundItem } from "@/api/funds";
import { PromptEditor } from "@/components/PromptEditor";
import { usePageSearchParams } from "@/hooks/usePageSearchParams";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";

const { Text, Paragraph } = Typography;

const ACTION_TAGS: Record<string, { color: string; label: string }> = {
  buy: { color: "#cf1322", label: "买入" },
  hold: { color: "#1890ff", label: "持有" },
  reduce: { color: "#faad14", label: "减仓" },
  redeem: { color: "#3f8600", label: "赎回" },
};

const REASON_LABELS: Record<string, string> = {
  technical: "技术面分析",
  fundamental: "基本面分析",
  sentiment: "市场情绪",
  risk: "风险提示",
  summary: "综合判断",
};

export function AdviceList() {
  const queryClient = useQueryClient();
  const [params, setParams] = usePageSearchParams({
    page: "1", action: "", fund_code: "", page_size: "20",
  });
  const page = Number(params.page) || 1;
  const pageSize = Number(params.page_size) || 20;

  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);

  // 生成建议弹窗
  const [modalOpen, setModalOpen] = useState(false);
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const [genMode, setGenMode] = useState<"single" | "batch">("batch");
  const [topN, setTopN] = useState(10);
  const [selectedFund, setSelectedFund] = useState<string | undefined>();
  const [fundOptions, setFundOptions] = useState<{ value: string; label: string }[]>([]);
  const [searchText, setSearchText] = useState("");

  // 详情弹窗
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailFund, setDetailFund] = useState<FundAdvice | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);

  // 加载基金列表（用于选择基金）
  useEffect(() => {
    if (!modalOpen || genMode !== "single") return;
    const timer = setTimeout(async () => {
      try {
        const res = await searchFunds({
          page: 1,
          page_size: 100,
          name: searchText || undefined,
          sort_by: "latest_change_pct",
          sort_order: "desc",
        });
        if (res.success) {
          setFundOptions(
            res.data.items.map((f: FundItem) => ({
              value: f.id,
              label: `${f.code} - ${f.name}`,
            })),
          );
        }
      } catch {
        // ignore
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [modalOpen, genMode, searchText]);

  const startStr = dateRange?.[0]?.format("YYYY-MM-DD");
  const endStr = dateRange?.[1]?.format("YYYY-MM-DD");

  const { data, isLoading } = useQuery({
    queryKey: ["advice", {
      page,
      action: params.action,
      fund_code: params.fund_code,
      start: startStr, end: endStr,
    }],
    queryFn: async () => {
      const res = await listAdvice({
        action: params.action || undefined,
        fund_code: params.fund_code || undefined,
        start_date: startStr,
        end_date: endStr,
        page,
        page_size: pageSize,
      });
      return res.success ? res.data : { items: [], total: 0, page: 1, page_size: 20 };
    },
  });

  const { mutate: runAnalysis, isPending: generating } = useMutation({
    mutationFn: () => {
      if (genMode === "single" && selectedFund) {
        return generateBatchAdvice({ fund_ids: [selectedFund] });
      }
      return searchFunds({ page: 1, page_size: topN, sort_by: "latest_change_pct", sort_order: "desc" })
        .then((res) => {
          if (!res.success) throw new Error("Failed to load funds");
          const fundIds = res.data.items.map((f: FundItem) => f.id);
          if (fundIds.length === 0) throw new Error("没有找到基金");
          return generateBatchAdvice({ fund_ids: fundIds });
        });
    },
    onSuccess: (res) => {
      if (res.success) {
        message.success(`分析完成，共生成 ${res.data.total} 条建议`);
        setModalOpen(false);
        queryClient.invalidateQueries({ queryKey: ["advice"] });
      } else {
        message.error("分析失败");
      }
    },
    onError: (err) => message.error(err instanceof Error ? err.message : "分析请求失败"),
  });

  const { mutate: batchDelete, isPending: deleting } = useMutation({
    mutationFn: (ids: string[]) => batchDeleteAdvice(ids),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`已删除 ${res.data.deleted} 条建议`);
        setSelectedRowKeys([]);
        queryClient.invalidateQueries({ queryKey: ["advice"] });
      }
    },
    onError: () => message.error("删除失败"),
  });

  const columns = [
    {
      title: "基金代码",
      dataIndex: "fund_code",
      key: "fund_code",
      width: 100,
      render: (v: string | null, r: FundAdvice) =>
        v ? <span style={{ fontFamily: "monospace" }}>{v}</span> : r.fund_id.slice(0, 8),
    },
    {
      title: "基金名称",
      dataIndex: "fund_name",
      key: "fund_name",
      width: 180,
      ellipsis: true,
      render: (v: string | null) => v ?? "-",
    },
    {
      title: "操作建议",
      dataIndex: "action",
      key: "action",
      width: 100,
      render: (v: string) => {
        const t = ACTION_TAGS[v] ?? { color: "default", label: v };
        return <Tag color={t.color}>{t.label}</Tag>;
      },
    },
    {
      title: "置信度",
      dataIndex: "confidence",
      key: "confidence",
      width: 80,
      align: "right" as const,
      render: (v: number | null) =>
        v != null ? `${v.toFixed(0)}%` : "-",
    },
    {
      title: "AI 模型",
      dataIndex: "ai_model",
      key: "ai_model",
      width: 130,
      render: (v: string | null) => v ?? "-",
    },
    {
      title: "原因",
      dataIndex: "reason",
      key: "reason",
      ellipsis: true,
      render: (v: Record<string, unknown>, r: FundAdvice) => (
        <a onClick={() => { setDetailFund(r); setDetailOpen(true); }}>
          {v != null ? (Object.keys(v).length > 0 ? "查看详情" : "空") : "无"}
        </a>
      ),
    },
    {
      title: "日期",
      dataIndex: "date",
      key: "date",
      width: 120,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD"),
    },
    {
      title: "生成时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 180,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm:ss"),
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>AI 操作建议</h2>
        <Space>
          <Button
            icon={<SettingOutlined />}
            onClick={() => setPromptModalOpen(true)}
          >
            提示词设置
          </Button>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={() => setModalOpen(true)}
          >
            生成建议
          </Button>
        </Space>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="基金编码"
          prefix={<SearchOutlined />}
          value={params.fund_code}
          onChange={(e) => setParams({ fund_code: e.target.value, page: "1" })}
          style={{ width: 160 }}
          allowClear
        />
        <Select
          placeholder="操作类型"
          value={params.action || undefined}
          onChange={(v) => setParams({ action: v ?? "", page: "1" })}
          allowClear
          style={{ width: 120 }}
          options={Object.entries(ACTION_TAGS).map(([k, v]) => ({
            value: k,
            label: v.label,
          }))}
        />
        <DatePicker.RangePicker
          value={dateRange}
          onChange={(v) => { setDateRange(v as [Dayjs, Dayjs] | null); setParams({ page: "1" }); }}
          allowClear
          placeholder={["起始日期", "结束日期"]}
        />
      </Space>

      {selectedRowKeys.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <Popconfirm
            title={`确认删除选中的 ${selectedRowKeys.length} 条建议？`}
            onConfirm={() => batchDelete(selectedRowKeys)}
          >
            <Button danger loading={deleting} icon={<DeleteOutlined />} size="small">
              批量删除 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        </div>
      )}
      <Table
        columns={columns}
        dataSource={data?.items ?? []}
        rowKey="id"
        loading={isLoading}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys as string[]),
        }}
        pagination={{
          ...paginationConfig,
          current: page,
          total: data?.total ?? 0,
        }}
      />

      <Modal
        title="生成 AI 操作建议"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => runAnalysis()}
        confirmLoading={generating}
        okText="开始生成"
        cancelText="取消"
      >
        <div style={{ marginTop: 16 }}>
          <Radio.Group
            value={genMode}
            onChange={(e) => setGenMode(e.target.value)}
            style={{ marginBottom: 16 }}
          >
            <Radio.Button value="batch">批量生成（按涨幅排名）</Radio.Button>
            <Radio.Button value="single">指定单只基金</Radio.Button>
          </Radio.Group>

          {genMode === "batch" ? (
            <div>
              <Text strong>生成数量：</Text>
              <InputNumber
                value={topN}
                onChange={(v) => setTopN(v ?? 10)}
                min={1}
                max={50}
                style={{ marginLeft: 8, width: 100 }}
              />
              <Text type="secondary" style={{ display: "block", marginTop: 8 }}>
                按实际涨幅降序对前 N 只基金生成操作建议
              </Text>
            </div>
          ) : (
            <div>
              <Text strong>选择基金：</Text>
              <Select
                showSearch
                value={selectedFund}
                onChange={setSelectedFund}
                onSearch={setSearchText}
                style={{ width: "100%", marginTop: 8 }}
                placeholder="搜索并选择基金"
                filterOption={false}
                options={fundOptions}
                loading={fundOptions.length === 0 && searchText.length === 0}
                notFoundContent="未找到匹配的基金"
              />
            </div>
          )}
        </div>
      </Modal>

      <PromptEditor open={promptModalOpen} onClose={() => setPromptModalOpen(false)} filter="fund_advice" />

      {/* 详情弹窗 */}
      <Modal
        title={detailFund ? `${detailFund.fund_name ?? detailFund.fund_code} - AI 分析详情` : "详情"}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={<Button onClick={() => setDetailOpen(false)}>关闭</Button>}
        width={640}
      >
        {detailFund && (
          <div style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 16, display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
              <Text strong style={{ fontSize: 16 }}>
                {detailFund.fund_code && (
                  <span style={{ fontFamily: "monospace", marginRight: 8 }}>{detailFund.fund_code}</span>
                )}
                {detailFund.fund_name}
              </Text>
              {(() => {
                const t = ACTION_TAGS[detailFund.action] ?? { color: "default", label: detailFund.action };
                return <Tag color={t.color}>{t.label}</Tag>;
              })()}
              {detailFund.confidence != null && (
                <Text type="secondary">置信度: {detailFund.confidence.toFixed(0)}%</Text>
              )}
              {detailFund.ai_model && (
                <Text type="secondary" style={{ fontSize: 12 }}>模型: {detailFund.ai_model}</Text>
              )}
            </div>

            {detailFund.reason && Object.keys(detailFund.reason).length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {Object.entries(detailFund.reason).map(([key, value]) => (
                  <Card key={key} size="small" title={REASON_LABELS[key] ?? key} variant="outlined">
                    <Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
                      {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
                    </Paragraph>
                  </Card>
                ))}
              </div>
            ) : (
              <Text type="secondary">暂无详细分析内容</Text>
            )}

            {detailFund.date && (
              <div style={{ marginTop: 16 }}>
                <Text type="secondary">分析日期: {dayjs(detailFund.date).format("YYYY-MM-DD")}</Text>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
