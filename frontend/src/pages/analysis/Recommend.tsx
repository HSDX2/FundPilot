import { useState } from "react";
import {
  Card, Table, Tag, Typography, Button, Segmented, Space, message, Empty, Spin, Popconfirm, DatePicker, Modal, Card as AntCard,
} from "antd";
import {
  BulbOutlined, SettingOutlined, ReloadOutlined, WarningFilled, CheckCircleFilled, DeleteOutlined,
} from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { getTopPicks, getDipBuy, getRecommendHistory, deleteRecommendHistory, type RecommendRecord } from "@/api/recommend";
import { PromptEditor } from "@/components/PromptEditor";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";

const { Text } = Typography;

const ACTION_STYLES: Record<string, { color: string; label: string }> = {
  buy: { color: "#cf1322", label: "推荐" },
  add: { color: "#cf1322", label: "加仓" },
  watch: { color: "#faad14", label: "观望" },
  stop: { color: "#3f8600", label: "止损" },
};

const TYPE_STYLES: Record<string, string> = {
  fund: "blue",
  sector: "purple",
};

export function Recommend() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [genTab, setGenTab] = useState("top-picks");
  const [page, setPage] = useState(1);
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const [detailItem, setDetailItem] = useState<RecommendRecord | null>(null);

  const startStr = dateRange?.[0]?.format("YYYY-MM-DD");
  const endStr = dateRange?.[1]?.format("YYYY-MM-DD");

  const historyMode = genTab === "top-picks" ? "top_picks" : "dip_buy";

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["recommend", "history", page, startStr, endStr, historyMode],
    queryFn: async () => {
      const res = await getRecommendHistory({ page, page_size: 20, start_date: startStr, end_date: endStr, mode: historyMode });
      return res.success ? res.data : { items: [], total: 0, page: 1, page_size: 20 };
    },
  });

  // 生成推荐
  const { mutate: generate, isPending: generating } = useMutation({
    mutationFn: () => genTab === "top-picks"
      ? getTopPicks({ limit: 10 })
      : getDipBuy({ limit: 10 }),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`推荐完成，共 ${res.data.total} 条结果`);
        queryClient.invalidateQueries({ queryKey: ["recommend", "history"] });
      } else {
        message.error("推荐请求失败");
      }
    },
    onError: () => message.error("推荐请求失败"),
  });

  // 批量删除
  const { mutate: batchDelete, isPending: deleting } = useMutation({
    mutationFn: (ids: string[]) => deleteRecommendHistory(ids),
    onSuccess: (res) => {
      if (res.success) {
        message.success(`已删除 ${res.data.deleted} 条记录`);
        setSelectedRowKeys([]);
        queryClient.invalidateQueries({ queryKey: ["recommend", "history"] });
      }
    },
    onError: () => message.error("删除失败"),
  });

  const columns = [
    {
      title: "日期", dataIndex: "date", key: "date", width: 110,
      render: (v: string) => dayjs(v).format("MM-DD"),
    },
    {
      title: "类型", dataIndex: "type", key: "type", width: 70,
      render: (v: string) => <Tag color={TYPE_STYLES[v] ?? "default"}>{v === "fund" ? "基金" : "板块"}</Tag>,
    },
    {
      title: "操作", dataIndex: "action", key: "action", width: 70,
      render: (v: string) => {
        const s = ACTION_STYLES[v] ?? { color: "default", label: v };
        return <Tag color={s.color}>{s.label}</Tag>;
      },
    },
    {
      title: "名称", key: "name", ellipsis: true,
      render: (_: unknown, r: RecommendRecord) => {
        const isUuid = r.target_code ? r.target_code.includes("-") && r.target_code.length === 36 : false;
        const isFundCode = r.target_code && r.target_code.length <= 10 && /^\d/.test(r.target_code);
        return (
          <a onClick={() => {
            if (r.type === "fund" && isFundCode) navigate(`/funds/${r.target_code}`);
            else if (r.type === "sector" && isUuid) navigate(`/sectors/${r.target_code}`);
            else if (r.type === "sector") navigate("/sectors");
          }}>
            {r.target_name}
            {r.target_code && <Text code style={{ marginLeft: 4 }}>{r.target_code}</Text>}
          </a>
        );
      },
    },
    {
      title: "置信度", dataIndex: "confidence", key: "confidence", width: 70, align: "right" as const,
      render: (v: number) => (
        <Text style={{ color: v >= 60 ? "#cf1322" : "#faad14", fontWeight: 500 }}>{v}</Text>
      ),
    },
    {
      title: "推荐理由", dataIndex: "reason_summary", key: "reason", ellipsis: true,
      render: (v: string, r: RecommendRecord) => (
        <a onClick={() => setDetailItem(r)}>{v}</a>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>
          <BulbOutlined /> AI 推荐
        </h2>
        <Space>
          <Button
            type="primary"
            icon={<BulbOutlined />}
            loading={generating}
            onClick={() => generate()}
          >
            生成{genTab === "top-picks" ? "综合推荐" : "加仓推荐"}
          </Button>
          <Button
            icon={<SettingOutlined />}
            onClick={() => setPromptModalOpen(true)}
          >
            提示词设置
          </Button>
        </Space>
      </div>

      <Segmented
        value={genTab}
        onChange={(v) => setGenTab(v as string)}
        options={[
          { value: "top-picks", label: "综合推荐" },
          { value: "dip-buy", label: "加仓推荐" },
        ]}
        style={{ margin: "16px 0" }}
      />

      <div style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Space wrap>
          <DatePicker.RangePicker
            size="small"
            value={dateRange}
            onChange={(v) => { setDateRange(v as [Dayjs, Dayjs] | null); setPage(1); }}
            allowClear
            placeholder={["起始日期", "结束日期"]}
          />
          <Button size="small" icon={<ReloadOutlined />} onClick={() => queryClient.invalidateQueries({ queryKey: ["recommend", "history"] })}>
            刷新
          </Button>
        </Space>
        {selectedRowKeys.length > 0 && (
          <Popconfirm
            title={`确认删除选中的 ${selectedRowKeys.length} 条推荐记录？`}
            onConfirm={() => batchDelete(selectedRowKeys)}
          >
            <Button danger loading={deleting} icon={<DeleteOutlined />} size="small">
              删除选中 ({selectedRowKeys.length})
            </Button>
          </Popconfirm>
        )}
      </div>

      <Table
        columns={columns}
        dataSource={history?.items ?? []}
        rowKey="id"
        loading={historyLoading || generating}
        size="small"
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys as string[]),
        }}
        pagination={{
          current: page,
          pageSize: 20,
          total: history?.total ?? 0,
          showSizeChanger: false,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => setPage(p),
        }}
      />

      <Modal
        title={detailItem ? `${detailItem.target_name} — 推荐详情` : "推荐详情"}
        open={detailItem != null}
        onCancel={() => setDetailItem(null)}
        footer={<Button onClick={() => setDetailItem(null)}>关闭</Button>}
        width={640}
      >
        {detailItem && (
          <div style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 16, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <Tag color={detailItem.type === "fund" ? "blue" : "purple"}>
                {detailItem.type === "fund" ? "基金" : "板块"}
              </Tag>
              <Text strong style={{ fontSize: 16 }}>{detailItem.target_name}</Text>
              {detailItem.target_code && (
                <Text code>{detailItem.target_code}</Text>
              )}
              <Tag color={detailItem.confidence >= 60 ? "#cf1322" : "#faad14"}>
                置信度 {detailItem.confidence}
              </Tag>
            </div>

            <div style={{ marginBottom: 16, padding: 12, background: "#f5f5f5", borderRadius: 6 }}>
              <Text>{detailItem.reason_summary}</Text>
            </div>

            {detailItem.reason_detail && Object.keys(detailItem.reason_detail).length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {Object.entries(detailItem.reason_detail).map(([key, value]) => {
                  const labels: Record<string, string> = {
                    market_analysis: "市场面分析",
                    technical: "技术面分析",
                    sentiment: "情绪面分析",
                    catalyst: "潜在催化剂",
                    drawdown_analysis: "回撤分析",
                    divergence: "与板块背离情况",
                    fundamental_check: "基本面检查",
                  };
                  return (
                    <AntCard key={key} size="small" title={labels[key] ?? key} variant="outlined">
                      <Typography.Paragraph style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}>
                        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
                      </Typography.Paragraph>
                    </AntCard>
                  );
                })}
              </div>
            )}

            {detailItem.risk_warning && (
              <div style={{ marginTop: 16, padding: "8px 12px", background: "#fff7e6", borderRadius: 6 }}>
                <Text type="warning">⚠️ {detailItem.risk_warning}</Text>
              </div>
            )}
          </div>
        )}
      </Modal>

      <PromptEditor
        open={promptModalOpen}
        onClose={() => setPromptModalOpen(false)}
        filter="recommend"
      />
    </div>
  );
}
