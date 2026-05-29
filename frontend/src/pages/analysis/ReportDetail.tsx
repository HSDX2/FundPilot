import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, Descriptions, Tag, Spin, Empty, Typography } from "antd";
import {
  RiseOutlined, FallOutlined, MinusOutlined,
} from "@ant-design/icons";
import { getReport } from "@/api/analysis";
import dayjs from "dayjs";

const { Text, Paragraph } = Typography;

const RISK_COLORS: Record<string, string> = {
  low: "green",
  medium: "orange",
  high: "red",
};

const RISK_LABELS: Record<string, string> = {
  low: "低风险",
  medium: "中等风险",
  high: "高风险",
};

function TrendIcon({ trend }: { trend?: string }) {
  if (trend === "up") return <Tag color="red" icon={<RiseOutlined />}>上涨</Tag>;
  if (trend === "down") return <Tag color="green" icon={<FallOutlined />}>下跌</Tag>;
  return <Tag color="default" icon={<MinusOutlined />}>震荡</Tag>;
}

/** 各 JSON 字段的中文说明 */
const FIELD_NOTES: Record<string, string> = {
  summary: "一句话总结板块当前状态",
  trend: "趋势方向: up=上涨, down=下跌, sideways=震荡",
  strength_score: "综合强度评分 0-100，越高越强势",
  risk_level: "风险等级: low=低风险, medium=中等风险, high=高风险",
  key_factors: "驱动因素列表",
  support_level: "关键技术支撑位",
  resistance_level: "关键技术压力位",
  volume_analysis: "成交量分析",
  money_flow_analysis: "资金面分析",
  outlook: "短期走势展望",
  analysis_text: "自然语言分析报告",
};

function JsonWithNotes({ data }: { data: Record<string, unknown> }) {
  const { analysis_text, ...fields } = data;

  return (
    <div>
      {/* 自然语言分析 */}
      {typeof analysis_text === "string" ? (
        <Card size="small" style={{ marginBottom: 16, background: "#fafafa" }}>
          <Paragraph style={{ whiteSpace: "pre-wrap", margin: 0, lineHeight: 1.8 }}>
            {analysis_text}
          </Paragraph>
        </Card>
      ) : null}

      {/* 量化指标卡片 */}
      {data.strength_score != null && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>综合强度</Text>
              <div>
                <Text strong style={{ fontSize: 28, color: (data.strength_score as number) >= 60 ? "#cf1322" : (data.strength_score as number) >= 40 ? "#d48806" : "#3f8600" }}>
                  {data.strength_score as number}
                </Text>
                <Text type="secondary" style={{ marginLeft: 4 }}>/ 100</Text>
              </div>
            </div>
            {(data.trend as string) && <div><Text type="secondary" style={{ fontSize: 12 }}>趋势</Text><div><TrendIcon trend={data.trend as string} /></div></div>}
            {(data.risk_level as string) && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>风险等级</Text>
                <div>
                  <Tag color={RISK_COLORS[data.risk_level as string] ?? "default"}>
                    {RISK_LABELS[data.risk_level as string] ?? String(data.risk_level)}
                  </Tag>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* JSON 结构化数据（带注释） */}
      <Card title="结构化分析数据" size="small">
        {Object.entries(fields).map(([key, value]) => (
          <div key={key} style={{ marginBottom: 12 }}>
            <Text strong style={{ fontSize: 13 }}>{key}</Text>
            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
              — {FIELD_NOTES[key] ?? ""}
            </Text>
            <div style={{ marginTop: 2 }}>
              {Array.isArray(value) ? (
                <div style={{ paddingLeft: 16 }}>
                  {value.map((item, i) => (
                    <Tag key={i} style={{ marginBottom: 4 }}>{String(item)}</Tag>
                  ))}
                </div>
              ) : (
                <Text style={{ whiteSpace: "pre-wrap" }}>
                  {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
                </Text>
              )}
            </div>
          </div>
        ))}
      </Card>
    </div>
  );
}

export function ReportDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: report, isLoading } = useQuery({
    queryKey: ["report", id],
    queryFn: async () => {
      const res = await getReport(id!);
      return res.success ? res.data : null;
    },
    enabled: !!id,
  });

  if (isLoading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;
  if (!report) return <Empty description="未找到该报告" />;

  const title = `${report.report_type === "daily" ? "日报" : report.report_type === "weekly" ? "周报" : report.report_type === "monthly" ? "月报" : report.report_type} — ${dayjs(report.date).format("YYYY-MM-DD")}`;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>{title}</h2>
      <Card style={{ marginTop: 16 }}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="报告类型">
            <Tag>{report.report_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="板块分类">
            {report.category === "industry" ? <Tag color="blue">行业</Tag> : report.category === "concept" ? <Tag color="orange">概念</Tag> : <Tag>未知</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="AI 模型">
            {report.ai_model ?? "-"}
          </Descriptions.Item>
          <Descriptions.Item label="生成时间">
            {dayjs(report.created_at).format("YYYY-MM-DD HH:mm:ss")}
          </Descriptions.Item>
        </Descriptions>
      </Card>
      <Card style={{ marginTop: 16 }}>
        <JsonWithNotes data={report.content as Record<string, unknown>} />
      </Card>
    </div>
  );
}
