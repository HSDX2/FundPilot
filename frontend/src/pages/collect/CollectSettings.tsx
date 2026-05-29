import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Table, Switch, Input, InputNumber, Button, Modal, Radio, TimePicker,
  DatePicker, Select, Tag, message, Space, Divider, Typography, Tooltip, Tabs,
} from "antd";
import { QuestionCircleOutlined } from "@ant-design/icons";
import {
  getCollectSettings, updateCollectSetting, updateCollectSchedule,
  updateCollectOtherConfig,
} from "@/api/collect";
import type { CollectorSetting, ScheduleConfig, OtherConfig } from "@/api/collect";
import dayjs from "dayjs";

const { Text } = Typography;

const addonStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "0 11px",
  border: "1px solid #d9d9d9",
  borderLeft: "none",
  borderRadius: "0 6px 6px 0",
  background: "#fafafa",
  fontSize: 13,
  color: "#999",
  lineHeight: "30px",
};

// ── Collector metadata ──────────────────────────────────────────────

const COLLECTOR_LABELS: Record<string, string> = {
  fund_list: "基金列表",
  etf: "ETF 行情",
  sector_list: "板块列表",
  sector_batch_history: "板块历史数据",
  sector_batch_daily: "板块每日数据",
  fund_nav_history: "基金净值历史数据",
  fund_nav_daily: "基金净值每日数据",
  news: "新闻",
  market_sentiment: "市场情绪",
};

/** Task-level parameters available for each collector. */
interface TaskParamDef {
  key: string;
  label: string;
  type: "select" | "date" | "date_range" | "switch" | "number" | "none";
  /** Options for select-type params. */
  options?: { value: string; label: string }[];
  /** Min/max for number-type params. */
  min?: number;
  max?: number;
  /** Annotation / example shown below the field. */
  annotation: string;
  /** Tooltip shown on the label question-mark icon. */
  tooltip: string;
}

const TASK_PARAMS: Record<string, TaskParamDef[]> = {
  fund_list: [
    {
      key: "fund_type",
      label: "基金类型",
      type: "select",
      options: [
        { value: "", label: "全部（基金+ETF）" },
        { value: "stock", label: "股票型" },
        { value: "mixed", label: "混合型" },
        { value: "index", label: "指数型" },
        { value: "etf", label: "ETF" },
      ],
      annotation:
        "选择要采集的基金类型。留空=全部（含ETF）。示例：仅 ETF → 勾选 ETF",
      tooltip: "fund_list 采集器支持按基金类型筛选，对应 trigger API 的 fund_type 参数",
    },
  ],
  news: [
    {
      key: "sources",
      label: "新闻源",
      type: "select",
      options: [
        { value: "eastmoney", label: "东方财富 (eastmoney)" },
        { value: "jin10", label: "金十数据 (jin10)" },
        { value: "cls", label: "财联社 (cls)" },
        { value: "wallstreetcn", label: "华尔街见闻 (wallstreetcn)" },
      ],
      annotation:
        "选择要采集的新闻源。留空或不选 = 采集全部。示例：仅采集东方财富和金十 → 勾选 eastmoney、jin10",
      tooltip: "News 采集器支持按新闻源过滤，对应 trigger API 的 sources 参数",
    },
  ],
  fund_nav_history: [
    {
      key: "start_date",
      label: "起始日期",
      type: "date",
      annotation:
        "留空 = 回补全部历史数据。填入日期 = 从该日起采集。示例：2024-01-01",
      tooltip: "默认回补全部历史净值；填入起始日期则只采集该日期之后的数据",
    },
    {
      key: "new_only",
      label: "仅补抽无净值基金",
      type: "switch",
      annotation:
        "开启后只采集 fund_navs 表中无记录的基金。"
        + "用于快速补齐新基金的净值数据，跳过已有净值的基金。",
      tooltip: "fund_nav_history 支持仅补抽无历史净值数据的新基金",
    },
    {
      key: "worker_count",
      label: "多进程并发数",
      type: "number",
      min: 1,
      max: 12,
      annotation:
        "默认 8，最大 12。每进程加载独立 V8 引擎和 DB 连接，约 100-200MB 内存。"
        + "8 进程约需 800MB-1.6GB 空闲内存。仅 fund_nav_history 生效。",
      tooltip: "通过多进程并行使采集速度提升 4-8 倍，内存不足请降低此值",
    },
  ],
  fund_nav_daily: [
    {
      key: "worker_count",
      label: "多进程并发数",
      type: "number",
      min: 1,
      max: 12,
      annotation:
        "默认 8，最大 12。每进程加载独立 V8 引擎和 DB 连接，约 100-200MB 内存。"
        + "8 进程约需 800MB-1.6GB 空闲内存。",
      tooltip: "通过多进程并行使净值采集速度提升 4-8 倍，与 fund_nav_history 共享参数",
    },
  ],
  sector_batch_history: [
    {
      key: "start_date",
      label: "起始日期",
      type: "date",
      annotation:
        "留空 = 回补全部历史数据（OHLC + 资金流向）。填入日期 = 从该日起采集。示例：2024-01-01",
      tooltip: "默认回补全部历史行情和资金流向；填入起始日期则只采集该日期之后的数据",
    },
    {
      key: "sector_new_only",
      label: "仅补抽无数据板块",
      type: "switch",
      annotation:
        "开启后只采集 sector_snapshots 表中无记录的板块。"
        + "用于快速补齐新增板块的历史数据，跳过已有数据的板块。",
      tooltip: "sector_batch_history 支持仅补抽无历史行情数据的新板块",
    },
  ],
  sector_batch_daily: [
    {
      key: "backfill_mf_detail",
      label: "补充中单/散户资金流向细分",
      type: "switch",
      annotation:
        "EM push2his 接口可能被 WAF 拦截导致获取失败。"
        + "开启 = 通过东方财富获取详细资金流向（含中单/散户三分类）；"
        + "关闭 = 仅通过 THS 获取资金总额（无细分），可避免 WAF 拦截。",
      tooltip: "sector_batch_daily 支持按需跳过 EM push2his，仅获取 THS 总额数据",
    },
  ],
  etf: [
    {
      key: "start_date",
      label: "起始日期",
      type: "date",
      annotation:
        "留空 = 仅更新当天 ETF 实时行情。填入日期 = 从该日起更新 ETF 历史行情。示例：2026-01-01",
      tooltip: "留空时每次执行仅取当天行情；填入起始日期后，每次定时执行和手动触发均从该日期回补",
    },
  ],
  news_sentiment: [
    {
      key: "date_range",
      label: "分析时间段",
      type: "date_range",
      annotation:
        "留空 = 默认近 3 天。限定新闻情绪分析的时间范围。",
      tooltip: "限定新闻情绪分析的时间段，只分析在此范围内的新闻",
    },
    {
      key: "sentiment_concurrency",
      label: "AI 并发数",
      type: "number",
      min: 1,
      max: 10,
      annotation:
        "默认 3，最大 10。同时调用 AI 接口的并发数，"
        + "过大可能触发 AI 接口频率限制（取决于 AI 提供商的限流策略）。",
      tooltip: "控制单次执行中同时调用 AI 的并发数量",
    },
    {
      key: "sentiment_limit",
      label: "单次分析条数上限",
      type: "number",
      min: 1,
      max: 1000,
      annotation:
        "默认 50，最大 1000。限制单次任务处理的新闻条数上限，"
        + "避免一次执行处理过多新闻导致耗时过长。",
      tooltip: "控制单次新闻情绪分析任务处理的最大条数",
    },
  ],
};

// ── Schedule helpers ─────────────────────────────────────────────────

const WEEKDAY_OPTIONS = [
  { value: 1, label: "周一" },
  { value: 2, label: "周二" },
  { value: 3, label: "周三" },
  { value: 4, label: "周四" },
  { value: 5, label: "周五" },
  { value: 6, label: "周六" },
  { value: 7, label: "周日" },
];

const MONTH_DAY_OPTIONS = Array.from({ length: 31 }, (_, i) => ({
  value: i + 1,
  label: `${i + 1} 号`,
}));

function formatScheduleSummary(sc: ScheduleConfig | null): string {
  if (!sc || (!sc.interval_minutes && !sc.specific_time)) return "未配置";
  const parts: string[] = [];
  if (sc.mode === "interval" && sc.interval_minutes) {
    const h = Math.floor(sc.interval_minutes / 60);
    const m = sc.interval_minutes % 60;
    parts.push(h > 0 ? `每 ${h}h${m > 0 ? `${m}m` : ""}` : `每 ${m}m`);
  } else if (sc.mode === "specific_time" && sc.specific_time) {
    parts.push(`每日 ${sc.specific_time}`);
  }
  if (sc.weekdays?.length) {
    parts.push(sc.weekdays.map((d) => WEEKDAY_OPTIONS.find((o) => o.value === d)?.label).join("、"));
  }
  if (sc.month_days?.length) {
    parts.push(`每月 ${sc.month_days.join("、")} 号`);
  }
  return parts.join(" · ");
}

// ── Component ────────────────────────────────────────────────────────

export function CollectSettings() {
  const queryClient = useQueryClient();
  const [editingRecord, setEditingRecord] = useState<CollectorSetting | null>(null);

  // edit form state
  const [editDisplayName, setEditDisplayName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [editMode, setEditMode] = useState<"interval" | "specific_time">("interval");
  const [editIntervalMin, setEditIntervalMin] = useState<number | null>(null);
  const [editSpecificTime, setEditSpecificTime] = useState<dayjs.Dayjs | null>(null);
  const [editWeekdays, setEditWeekdays] = useState<number[] | null>(null);
  const [editMonthDays, setEditMonthDays] = useState<number[] | null>(null);
  const [editActiveStart, setEditActiveStart] = useState<dayjs.Dayjs | null>(null);
  const [editActiveEnd, setEditActiveEnd] = useState<dayjs.Dayjs | null>(null);
  const [editSortOrder, setEditSortOrder] = useState<number>(0);
  const [editStartDate, setEditStartDate] = useState<dayjs.Dayjs | null>(null);
  const [editTaskParams, setEditTaskParams] = useState<Record<string, unknown>>({});

  const { data, isLoading } = useQuery({
    queryKey: ["collect", "settings"],
    queryFn: async () => {
      const res = await getCollectSettings();
      return res.success ? res.data.items : [];
    },
  });

  const saveSetting = useMutation({
    mutationFn: (params: { name: string; body: Record<string, unknown> }) =>
      updateCollectSetting(params.name, params.body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collect", "settings"] }),
    onError: () => message.error("保存失败"),
  });

  const saveSchedule = useMutation({
    mutationFn: (params: { name: string; body: Partial<ScheduleConfig> }) =>
      updateCollectSchedule(params.name, params.body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collect", "settings"] }),
    onError: () => message.error("保存定时配置失败"),
  });

  const saveOtherConfig = useMutation({
    mutationFn: (params: { name: string; body: Partial<OtherConfig> }) =>
      updateCollectOtherConfig(params.name, params.body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collect", "settings"] }),
    onError: () => message.error("保存额外参数失败"),
  });

  // ── Open / close modal ──────────────────────────────────────────

  const openEdit = useCallback((record: CollectorSetting) => {
    setEditingRecord(record);
    setEditDisplayName(record.display_name ?? "");
    setEditDescription(record.description ?? "");
    setEditActive(record.is_active);
    setEditSortOrder(record.sort_order);

    const sc = record.schedule_config;
    setEditMode(sc?.mode ?? "interval");
    setEditIntervalMin(sc?.interval_minutes ?? null);
    setEditSpecificTime(sc?.specific_time ? dayjs(sc.specific_time, "HH:mm:ss") : null);
    setEditWeekdays(sc?.weekdays ?? null);
    setEditMonthDays(sc?.month_days ?? null);
    setEditActiveStart(sc?.active_start_time ? dayjs(sc.active_start_time, "HH:mm") : null);
    setEditActiveEnd(sc?.active_end_time ? dayjs(sc.active_end_time, "HH:mm") : null);
    setEditStartDate(null);  // start_date moved to other_config

    // Populate task params from other_config
    const taskParams: Record<string, unknown> = {};
    const oc = record.other_config;
    if (oc) {
      const taskDefs = TASK_PARAMS[record.collector_name] ?? [];
      for (const def of taskDefs) {
        if (def.type === "date") {
          const v = (oc as any)[def.key];
          if (v != null) taskParams[def.key] = dayjs(v, "YYYY-MM-DD");
        } else if (def.type === "date_range") {
          const sd = (oc as any)["start_date"];
          const ed = (oc as any)["end_date"];
          if (sd != null && ed != null) {
            taskParams[def.key] = [dayjs(sd, "YYYY-MM-DD"), dayjs(ed, "YYYY-MM-DD")];
          }
        } else if (def.type === "select") {
          const v = (oc as any)[def.key];
          if (v != null) taskParams[def.key] = v;
        } else if (def.type === "switch") {
          // Default to true if not explicitly set
          taskParams[def.key] = (oc as any)[def.key] !== false;
        } else if (def.type === "number") {
          taskParams[def.key] = (oc as any)[def.key] ?? null;
        }
      }
    }
    setEditTaskParams(taskParams);
  }, []);

  const closeEdit = useCallback(() => {
    setEditingRecord(null);
  }, []);

  // ── Save ────────────────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    if (!editingRecord) return;

    const name = editingRecord.collector_name;

    // 1. Save display_name, description, active state, sort_order
    const settingBody: Record<string, unknown> = {};
    if (editDisplayName !== (editingRecord.display_name ?? "")) {
      settingBody.display_name = editDisplayName || undefined;
    }
    if (editDescription !== (editingRecord.description ?? "")) {
      settingBody.description = editDescription || undefined;
    }
    if (editActive !== editingRecord.is_active) {
      settingBody.is_active = editActive;
    }
    if (editSortOrder !== editingRecord.sort_order) {
      settingBody.sort_order = editSortOrder;
    }
    if (Object.keys(settingBody).length > 0) {
      await saveSetting.mutateAsync({ name, body: settingBody });
    }

    // 2. Save schedule config (timer only, no start_date)
    const scBody: Partial<ScheduleConfig> = {
      mode: editMode,
      interval_minutes: editMode === "interval" ? (editIntervalMin ?? null) : null,
      specific_time: editMode === "specific_time"
        ? (editSpecificTime?.format("HH:mm:ss") ?? null)
        : null,
      weekdays: editWeekdays?.length ? editWeekdays : null,
      month_days: editMonthDays?.length ? editMonthDays : null,
      active_start_time: editActiveStart?.format("HH:mm") ?? null,
      active_end_time: editActiveEnd?.format("HH:mm") ?? null,
    };
    await saveSchedule.mutateAsync({ name, body: scBody });

    // 3. Save other_config (task params) — collect non-null task params from editTaskParams
    const ocBody: Record<string, unknown> = {};
    const taskDefs = TASK_PARAMS[name] ?? [];
    for (const def of taskDefs) {
      if (def.type === "date") {
        const v = editTaskParams[def.key] as dayjs.Dayjs | null | undefined;
        ocBody[def.key] = v ? v.format("YYYY-MM-DD") : null;
      } else if (def.type === "date_range") {
        const v = editTaskParams[def.key] as [dayjs.Dayjs, dayjs.Dayjs] | null | undefined;
        ocBody["start_date"] = v?.[0] ? v[0].format("YYYY-MM-DD") : null;
        ocBody["end_date"] = v?.[1] ? v[1].format("YYYY-MM-DD") : null;
      } else if (def.type === "select") {
        const v = editTaskParams[def.key] as string[] | null | undefined;
        ocBody[def.key] = v?.length ? v : null;
      } else if (def.type === "switch") {
        ocBody[def.key] = editTaskParams[def.key] !== false;
      } else if (def.type === "number") {
        const v = editTaskParams[def.key] as number | null | undefined;
        if (v != null) ocBody[def.key] = v;
      }
    }
    if (Object.keys(ocBody).length > 0) {
      await saveOtherConfig.mutateAsync({ name, body: ocBody as Partial<OtherConfig> });
    }

    message.success("配置已保存");
    closeEdit();
  }, [
    editingRecord, editDisplayName, editDescription, editActive,
    editMode, editIntervalMin, editSpecificTime,
    editWeekdays, editMonthDays, editActiveStart, editActiveEnd,
    editTaskParams,
    saveSetting, saveSchedule, saveOtherConfig, closeEdit,
  ]);

  // ── Table columns ───────────────────────────────────────────────

  const columns = [
    {
      title: "序号",
      dataIndex: "sort_order",
      key: "sort_order",
      width: 60,
      align: "center" as const,
    },
    {
      title: "采集器",
      dataIndex: "display_name",
      key: "display_name",
      width: 120,
      render: (v: string | null, record: CollectorSetting) =>
        (v || COLLECTOR_LABELS[record.collector_name]) ?? record.collector_name,
    },
    {
      title: "说明",
      dataIndex: "description",
      key: "description",
      width: 200,
      ellipsis: true,
      render: (v: string | null) => v ?? "-",
    },
    {
      title: "定时策略",
      dataIndex: "schedule_config",
      key: "schedule",
      width: 240,
      render: (sc: ScheduleConfig | null) => (
        <Text>{formatScheduleSummary(sc)}</Text>
      ),
    },
    {
      title: "启用",
      dataIndex: "is_active",
      key: "is_active",
      width: 70,
      render: (v: boolean, record: CollectorSetting) => (
        <Switch
          checked={v}
          loading={saveSetting.isPending}
          onChange={async (checked) => {
            try {
              await saveSetting.mutateAsync({
                name: record.collector_name,
                body: { is_active: checked },
              });
            } catch {
              // 后端校验失败（如无定时策略），Switch 会自动回弹
            }
          }}
        />
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 80,
      render: (_: unknown, record: CollectorSetting) => (
        <Button size="small" type="primary" onClick={() => openEdit(record)}>
          修改
        </Button>
      ),
    },
  ];

  // ── Task params for current collector ────────────────────────────

  const taskParamDefs = editingRecord
    ? (TASK_PARAMS[editingRecord.collector_name] ?? [])
    : [];

  return (
    <div>
      <h2>采集配置</h2>
      <Table
        columns={columns}
        dataSource={data ?? []}
        rowKey="id"
        loading={isLoading || saveSetting.isPending || saveSchedule.isPending}
        pagination={false}
      />

      {/* ── Edit Modal ─────────────────────────────────────────── */}
      <Modal
        title={`修改配置 — ${editingRecord ? (editingRecord.display_name || COLLECTOR_LABELS[editingRecord.collector_name] || editingRecord.collector_name) : ""}`}
        open={!!editingRecord}
        onOk={handleSave}
        onCancel={closeEdit}
        okText="保存"
        cancelText="取消"
        width={640}
        confirmLoading={saveSetting.isPending || saveSchedule.isPending || saveOtherConfig.isPending}
      >
        {editingRecord && (
          <Tabs>
            <Tabs.TabPane tab="基础信息" key="basic">
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div>
                  <Text strong>任务名称</Text>
                  <Input
                    value={editDisplayName}
                    onChange={(e) => setEditDisplayName(e.target.value)}
                    placeholder="采集器显示名称"
                    style={{ marginTop: 4 }}
                  />
                </div>
                <div>
                  <Text strong>说明</Text>
                  <Input.TextArea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    placeholder="采集任务说明"
                    rows={2}
                    style={{ marginTop: 4 }}
                  />
                </div>
                <div>
                  <Text strong>排序序号</Text>
                  <InputNumber
                    value={editSortOrder}
                    onChange={(v) => setEditSortOrder(v ?? 0)}
                    min={0}
                    style={{ marginTop: 4, width: 120 }}
                  />
                </div>
              </div>
            </Tabs.TabPane>

            <Tabs.TabPane tab="定时配置" key="schedule">
              <Radio.Group
                value={editMode}
                onChange={(e) => {
                  setEditMode(e.target.value);
                  if (e.target.value === "specific_time") {
                    setEditIntervalMin(null);
                    setEditActiveStart(null);
                    setEditActiveEnd(null);
                  } else {
                    setEditSpecificTime(null);
                  }
                }}
              >
                <Radio.Button value="interval">间隔执行</Radio.Button>
                <Radio.Button value="specific_time">指定时刻</Radio.Button>
              </Radio.Group>

              <div style={{ marginTop: 12 }}>
                {editMode === "interval" ? (
                  <Space>
                    <Text>每</Text>
                    <Space.Compact>
                      <InputNumber
                        min={1}
                        max={1440}
                        value={editIntervalMin ?? undefined}
                        onChange={(v) => setEditIntervalMin(v ?? null)}
                        placeholder="分钟"
                        style={{ width: 90 }}
                      />
                      <span style={addonStyle}>分钟</span>
                    </Space.Compact>
                    <Text type="secondary">
                      示例：60 = 每 60 分钟执行一次；1440 = 每天一次
                    </Text>
                  </Space>
                ) : (
                  <Space>
                    <Text>每日</Text>
                    <TimePicker
                      value={editSpecificTime}
                      onChange={setEditSpecificTime}
                      format="HH:mm"
                      placeholder="选择时刻"
                      minuteStep={5}
                    />
                    <Text type="secondary">
                      示例：12:00 = 每天中午 12:00 执行
                    </Text>
                  </Space>
                )}
              </div>

              <div style={{ marginTop: 16 }}>
                <Text>执行日期约束（可选）</Text>
                <Tooltip title="限制任务仅在指定日期执行。不设 = 每天有效">
                  <QuestionCircleOutlined style={{ marginLeft: 4, color: "#999" }} />
                </Tooltip>
              </div>

              <div style={{ marginTop: 8, display: "flex", gap: 16 }}>
                <div style={{ flex: 1 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>星期维度</Text>
                  <Select
                    mode="multiple"
                    placeholder="选择星期，如周一至周五"
                    value={editWeekdays ?? undefined}
                    onChange={(v) => setEditWeekdays(v?.length ? v as number[] : null)}
                    style={{ width: "100%" }}
                    options={WEEKDAY_OPTIONS}
                    allowClear
                  />
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    示例：[周一、周二、周三、周四、周五] = 仅工作日执行
                  </Text>
                </div>

                <div style={{ flex: 1 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>月日期维度</Text>
                  <Select
                    mode="multiple"
                    placeholder="选择日期，如 1、15"
                    value={editMonthDays ?? undefined}
                    onChange={(v) => setEditMonthDays(v?.length ? v as number[] : null)}
                    style={{ width: "100%" }}
                    options={MONTH_DAY_OPTIONS}
                    allowClear
                  />
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    示例：[1, 15] = 每月 1 号和 15 号执行
                  </Text>
                </div>
              </div>

              {editMode === "interval" && (
                <>
                  <div style={{ marginTop: 16 }}>
                    <Text>激活时间窗口（可选）</Text>
                    <Tooltip title="仅在指定时间段内触发执行。不设 = 全天有效">
                      <QuestionCircleOutlined style={{ marginLeft: 4, color: "#999" }} />
                    </Tooltip>
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Space>
                      <TimePicker
                        value={editActiveStart}
                        onChange={setEditActiveStart}
                        format="HH:mm"
                        placeholder="开始时间"
                        minuteStep={15}
                      />
                      <Text>—</Text>
                      <TimePicker
                        value={editActiveEnd}
                        onChange={setEditActiveEnd}
                        format="HH:mm"
                        placeholder="结束时间"
                        minuteStep={15}
                      />
                      <Text type="secondary">
                        示例：08:00 – 15:00 = 仅在交易时段内执行
                      </Text>
                    </Space>
                  </div>
                </>
              )}
            </Tabs.TabPane>

            <Tabs.TabPane tab="任务参数" key="params">
              {taskParamDefs.length > 0 ? (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <Text type="secondary">以下参数会持久化到数据库中，定时任务和手动触发均会读取使用</Text>
                  </div>
                  {taskParamDefs.map((def) => (
                    <div key={def.key} style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 4 }}>
                        <Text>{def.label}</Text>
                        <Tooltip title={def.tooltip}>
                          <QuestionCircleOutlined style={{ marginLeft: 4, color: "#1677ff", fontSize: 12 }} />
                        </Tooltip>
                      </div>
                      {def.type === "select" && def.options && (
                        <Select
                          mode="multiple"
                          placeholder="留空 = 使用默认值（全部）"
                          value={(editTaskParams[def.key] as string[]) ?? undefined}
                          onChange={(v) =>
                            setEditTaskParams((prev) => ({ ...prev, [def.key]: v }))
                          }
                          style={{ width: "100%" }}
                          options={def.options}
                          allowClear
                        />
                      )}
                      {def.type === "date" && (
                        <DatePicker
                          value={
                            (editTaskParams[def.key] as dayjs.Dayjs) ?? null
                          }
                          onChange={(v) =>
                            setEditTaskParams((prev) => ({ ...prev, [def.key]: v }))
                          }
                          format="YYYY-MM-DD"
                          placeholder="留空 = 当天"
                          allowClear
                          style={{ width: 200 }}
                        />
                      )}
                      {def.type === "date_range" && (
                        <DatePicker.RangePicker
                          value={
                            (editTaskParams[def.key] as [dayjs.Dayjs, dayjs.Dayjs]) ?? null
                          }
                          onChange={(v) =>
                            setEditTaskParams((prev) => ({ ...prev, [def.key]: v }))
                          }
                          format="YYYY-MM-DD"
                          placeholder={["开始日期", "结束日期"]}
                          allowClear
                          style={{ width: 260 }}
                        />
                      )}
                      {def.type === "switch" && (
                        <Switch
                          checked={editTaskParams[def.key] !== false}
                          onChange={(v) =>
                            setEditTaskParams((prev) => ({ ...prev, [def.key]: v }))
                          }
                        />
                      )}
                      {def.type === "number" && (
                        <InputNumber
                          value={(editTaskParams[def.key] as number) ?? undefined}
                          onChange={(v) =>
                            setEditTaskParams((prev) => ({ ...prev, [def.key]: v }))
                          }
                          min={def.min}
                          max={def.max}
                          style={{ width: 120 }}
                        />
                      )}
                      <div style={{ marginTop: 2 }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {def.annotation}
                        </Text>
                      </div>
                    </div>
                  ))}
                </>
              ) : (
                <Text type="secondary">该采集器无额外任务参数</Text>
              )}
            </Tabs.TabPane>
          </Tabs>
        )}
      </Modal>
    </div>
  );
}
