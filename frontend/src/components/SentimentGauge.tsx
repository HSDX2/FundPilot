import ReactECharts from "echarts-for-react";

interface Props {
  score: number;
  height?: number;
}

export function SentimentGauge({ score, height = 300 }: Props) {
  const option = {
    series: [
      {
        type: "gauge",
        startAngle: 210,
        endAngle: -30,
        center: ["50%", "60%"],
        radius: "90%",
        min: 0,
        max: 100,
        splitNumber: 10,
        axisLine: {
          show: true,
          lineStyle: {
            width: 20,
            color: [
              [0.3, "#cf1322"],
              [0.5, "#faad14"],
              [0.7, "#1890ff"],
              [1, "#3f8600"],
            ],
          },
        },
        pointer: { length: "60%", width: 6 },
        detail: {
          valueAnimation: true,
          fontSize: 24,
          offsetCenter: [0, "70%"],
        },
        data: [{ value: score, name: "情绪评分" }],
      },
    ],
  };

  return (
    <div style={{ height, minHeight: 150 }}>
      <ReactECharts option={option} style={{ height: "100%", width: "100%" }} />
    </div>
  );
}
