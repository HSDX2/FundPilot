import ReactECharts from "echarts-for-react";

interface NavDataPoint {
  date: string;
  value: number;
  change_pct?: number | null;
}

interface Props {
  data: NavDataPoint[];
  height?: number;
}

export function NavChart({ data, height = 400 }: Props) {
  const hasPct = data.some((d) => d.change_pct != null && !isNaN(d.change_pct));

  const barData = data.map((d) => {
    const v = d.change_pct;
    if (v == null || isNaN(Number(v))) return null;
    return Number(Number(v).toFixed(2));
  });

  const option: object = {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      valueFormatter: (v: number, seriesName: string) =>
        seriesName === "涨跌幅" ? `${v}%` : String(v),
    },
    xAxis: { type: "category", data: data.map((d) => d.date) },
    yAxis: [
      { type: "value", scale: true, name: "净值" },
      ...(hasPct ? [{ type: "value", scale: true, name: "涨跌幅(%)", position: "right" as const }] : []),
    ],
    dataZoom: [{ type: "inside" }],
    grid: { right: hasPct ? 60 : 20 },
    series: [
      {
        type: "line",
        name: "净值",
        yAxisIndex: 0,
        data: data.map((d) => d.value),
        smooth: true,
        symbol: "none",
        lineStyle: { color: "#1890ff", width: 2 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(24,144,255,0.3)" },
              { offset: 1, color: "rgba(24,144,255,0.05)" },
            ],
          },
        },
      },
      ...(hasPct
        ? [
            {
              type: "bar" as const,
              name: "涨跌幅",
              yAxisIndex: 1,
              data: barData,
              itemStyle: {
                color: (p: { value: number | null }) => {
                  if (p.value == null) return "transparent";
                  return p.value >= 0 ? "#cf1322" : "#3f8600";
                },
              },
            },
          ]
        : []),
    ],
  };

  return <ReactECharts option={option} style={{ height }} />;
}
