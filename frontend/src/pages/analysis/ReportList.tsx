import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table, Tag, Button, Modal, InputNumber, Radio, Select, message, Spin, Typography, Segmented, Popconfirm, DatePicker, Space,
} from "antd";
import { ThunderboltOutlined, DeleteOutlined, SettingOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listReports, generateAllReports, deleteReport, batchDeleteReports, type AnalysisReport } from "@/api/analysis";
import { searchSectors, type SectorItem } from "@/api/sectors";
import { PromptEditor } from "@/components/PromptEditor";
import { usePageSearchParams } from "@/hooks/usePageSearchParams";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";

const { Text } = Typography;

const TYPE_TAGS: Record<string, { color: string; label: string }> = {
  daily: { color: "blue", label: "日报" },
  weekly: { color: "green", label: "周报" },
  monthly: { color: "purple", label: "月报" },
};

export function ReportList() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = usePageSearchParams({
    page: "1", reportType: "daily", category: "", page_size: "20",
  });
  const page = Number(params.page) || 1;
  const pageSize = Number(params.page_size) || 20;
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);

  // 模态框参数
  const [genType, setGenType] = useState("daily");
  const [genCategory, setGenCategory] = useState<string>("");
  const [mode, setMode] = useState<"top" | "sectors">("top");
  const [topN, setTopN] = useState(10);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [sectorSearch, setSectorSearch] = useState("");
  const [sectorOptions, setSectorOptions] = useState<{ value: string; label: string }[]>([]);
  const [loadingSectors, setLoadingSectors] = useState(false);

  const filteredSectorOptions = useMemo(() => {
    if (!sectorSearch) return sectorOptions;
    const kw = sectorSearch.toLowerCase();
    return sectorOptions.filter((o) => o.label.toLowerCase().includes(kw));
  }, [sectorOptions, sectorSearch]);

  const startStr = dateRange?.[0]?.format("YYYY-MM-DD");
  const endStr = dateRange?.[1]?.format("YYYY-MM-DD");

  const { data, isLoading } = useQuery({
    queryKey: ["reports", { page, reportType: params.reportType, category: params.category, start: startStr, end: endStr }],
    queryFn: async () => {
      const res = await listReports({
        report_type: params.reportType,
        category: params.category || undefined,
        start_date: startStr,
        end_date: endStr,
        page,
        page_size: pageSize,
      });
      return res.success ? res.data : { items: [], total: 0, page: 1, page_size: 20 };
    },
  });

  useEffect(() => {
    if (!modalOpen) return;
    const timer = setTimeout(async () => {
      setLoadingSectors(true);
      try {
        const res = await searchSectors({ page_size: 500 });
        if (res.success) {
          setSectorOptions(
            res.data.items.map((s: SectorItem) => ({ value: s.id, label: s.name })),
          );
        } else {
          message.error("加载板块列表失败");
        }
      } catch {
        message.error("加载板块列表失败，请检查网络连接");
      } finally {
        setLoadingSectors(false);
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [modalOpen]);

  const { mutate: runAnalysis, isPending: generating } = useMutation({
    mutationFn: () => generateAllReports({
      report_type: genType,
      limit: topN,
      category: genCategory || undefined,
      sector_ids: mode === "sectors" && selectedSectors.length > 0
        ? selectedSectors : undefined,
    }),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`分析完成，共生成 ${res.data.total} 份报告`);
        setModalOpen(false);
        queryClient.invalidateQueries({ queryKey: ["reports"] });
      } else {
        message.error("分析失败");
      }
    },
    onError: () => message.error("分析请求失败"),
  });

  const { mutate: removeReport } = useMutation({
    mutationFn: (id: string) => deleteReport(id),
    onSuccess: (res) => {
      if (res.success) {
        message.success("报告已删除");
        setSelectedRowKeys((prev) => prev.filter((k) => k !== selectedRowKeys[0]));
        queryClient.invalidateQueries({ queryKey: ["reports"] });
      } else {
        message.error("删除失败");
      }
    },
    onError: () => message.error("删除请求失败"),
  });

  const { mutate: batchRemove, isPending: batchDeleting } = useMutation({
    mutationFn: (ids: string[]) => batchDeleteReports(ids),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`已删除 ${res.data.deleted} 份报告`);
        setSelectedRowKeys([]);
        queryClient.invalidateQueries({ queryKey: ["reports"] });
      } else {
        message.error("批量删除失败");
      }
    },
    onError: () => message.error("批量删除请求失败"),
  });

  const columns = [
    {
      title: "类型",
      dataIndex: "report_type",
      key: "report_type",
      width: 70,
      render: (v: string) => {
        const t = TYPE_TAGS[v] ?? { color: "default", label: v };
        return <Tag color={t.color}>{t.label}</Tag>;
      },
    },
    {
      title: "分类",
      dataIndex: "category",
      key: "category",
      width: 70,
      render: (v: string | null) => {
        if (v === "industry") return <Tag color="blue">行业</Tag>;
        if (v === "concept") return <Tag color="orange">概念</Tag>;
        return <Tag>未知</Tag>;
      },
    },
    {
      title: "板块名称",
      dataIndex: "sector_name",
      key: "sector_name",
      width: 140,
      ellipsis: true,
      render: (v: string | null) => v ?? "-",
    },
    {
      title: "报告日期",
      dataIndex: "date",
      key: "date",
      width: 120,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD"),
    },
    {
      title: "AI 模型",
      dataIndex: "ai_model",
      key: "ai_model",
      width: 100,
      render: (v: string | null) => v ?? "-",
    },
    {
      title: "生成时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 170,
      render: (v: string) => dayjs(v).format("YYYY-MM-DD HH:mm:ss"),
    },
    {
      title: "操作",
      key: "actions",
      width: 60,
      render: (_: unknown, record: AnalysisReport) => (
        <Popconfirm
          title="确认删除此报告？"
          onConfirm={(e) => {
            e?.stopPropagation();
            removeReport(record.id);
          }}
          onCancel={(e) => e?.stopPropagation()}
        >
          <Button
            type="link"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={(e) => e.stopPropagation()}
          />
        </Popconfirm>
      ),
    },
  ];

  const paginationConfig = useMemo(() => ({
    pageSize,
    showSizeChanger: true,
    pageSizeOptions: ["10", "20", "50", "100"],
    showTotal: (t: number) => `共 ${t} 条`,
    onChange: (p: number) => { setParams({ page: String(p) }); setSelectedRowKeys([]); },
    onShowSizeChange: (_: number, size: number) => { setParams({ page: "1", page_size: String(size) }); setSelectedRowKeys([]); },
  }), [pageSize]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>板块分析报告</h2>
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
            onClick={() => setModalOpen(true)}
          >
            智能分析
          </Button>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <Space wrap>
          <Select
            value={params.reportType}
            onChange={(v) => setParams({ reportType: v, page: "1" })}
            style={{ width: 100 }}
            options={[
              { value: "daily", label: "日报" },
              { value: "weekly", label: "周报" },
              { value: "monthly", label: "月报" },
            ]}
          />
          <Select
            value={params.category}
            onChange={(v) => setParams({ category: v, page: "1" })}
            style={{ width: 120 }}
            options={[
              { value: "", label: "全部" },
              { value: "industry", label: "行业板块" },
              { value: "concept", label: "概念板块" },
            ]}
          />
          <DatePicker.RangePicker
            value={dateRange}
            onChange={(v) => { setDateRange(v as [Dayjs, Dayjs] | null); setParams({ page: "1" }); }}
            allowClear
            placeholder={["起始日期", "结束日期"]}
          />
        </Space>
        {selectedRowKeys.length > 0 && (
          <Popconfirm
            title={`确认删除选中的 ${selectedRowKeys.length} 份报告？`}
            onConfirm={() => batchRemove(selectedRowKeys)}
            okText="批量删除"
            cancelText="取消"
          >
            <Button danger loading={batchDeleting} icon={<DeleteOutlined />}>
              删除选中 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        )}
      </div>

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
        onRow={(r: AnalysisReport) => ({
          onClick: () => navigate(`/analysis/reports/${r.id}`),
          style: { cursor: "pointer" },
        })}
      />

      <Modal
        title="智能分析 — 板块分析报告"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => runAnalysis()}
        confirmLoading={generating}
        okText="开始分析"
        cancelText="取消"
        width={520}
      >
        <div style={{ marginTop: 16 }}>
          <Text strong>报告类型：</Text>
          <div style={{ marginTop: 8 }}>
            <Segmented
              value={genType}
              onChange={(v) => setGenType(v as string)}
              options={[
                { value: "daily", label: "日报" },
                { value: "weekly", label: "周报" },
                { value: "monthly", label: "月报" },
              ]}
            />
          </div>
        </div>

        <div style={{ marginTop: 20 }}>
          <Text strong>板块分类：</Text>
          <div style={{ marginTop: 8 }}>
            <Segmented
              value={genCategory}
              onChange={(v) => setGenCategory(v as string)}
              options={[
                { value: "", label: "全部" },
                { value: "industry", label: "行业" },
                { value: "concept", label: "概念" },
              ]}
            />
          </div>
        </div>

        <div style={{ marginTop: 20 }}>
          <Text strong>分析范围：</Text>
          <div style={{ marginTop: 8 }}>
            <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)}>
              <Radio.Button value="top">涨幅前 N 名</Radio.Button>
              <Radio.Button value="sectors">指定板块</Radio.Button>
            </Radio.Group>
          </div>
        </div>

        {mode === "top" ? (
          <div style={{ marginTop: 12 }}>
            <Text>板块数量：</Text>
            <InputNumber
              min={1}
              max={50}
              value={topN}
              onChange={(v) => setTopN(v ?? 10)}
              style={{ marginLeft: 8, width: 100 }}
            />
          </div>
        ) : (
          <div style={{ marginTop: 12 }}>
            <Select
              mode="multiple"
              placeholder="搜索并选择板块"
              value={selectedSectors}
              onChange={setSelectedSectors}
              onSearch={setSectorSearch}
              searchValue={sectorSearch}
              style={{ width: "100%" }}
              options={filteredSectorOptions}
              filterOption={false}
              notFoundContent={loadingSectors ? <Spin size="small" /> : "无匹配板块"}
              maxTagCount={5}
            />
          </div>
        )}
      </Modal>
      <PromptEditor open={promptModalOpen} onClose={() => setPromptModalOpen(false)} filter="sector_analysis" />
    </div>
  );
}
