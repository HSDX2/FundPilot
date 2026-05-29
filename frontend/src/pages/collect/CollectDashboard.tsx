import { useCallback, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Row, Col, Card, Button, Badge, Tag, Typography, message } from "antd";
import { ThunderboltOutlined, PauseCircleOutlined } from "@ant-design/icons";
import { getCollectStatus, getCollectSettings, triggerCollect, stopCollect } from "@/api/collect";
import type { CollectorStatus } from "@/api/collect";

const { Text } = Typography;

const STATUS_META: Record<string, { status: "success" | "processing" | "default" | "error" | "warning"; label: string }> = {
  idle: { status: "default", label: "空闲" },
  running: { status: "processing", label: "运行中" },
  completed: { status: "success", label: "已完成" },
  failed: { status: "error", label: "失败" },
  partial: { status: "warning", label: "部分失败" },
  stopping: { status: "processing", label: "停止中" },
};

const COOLDOWN_MS = 5_000; // minimum interval between triggers per collector

export function CollectDashboard() {
  const [triggeringNames, setTriggeringNames] = useState<Set<string>>(new Set());
  const lastTriggeredRef = useRef<Map<string, number>>(new Map());
  const cooldownTimers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const { data, refetch } = useQuery({
    queryKey: ["collect", "status"],
    queryFn: async () => {
      const res = await getCollectStatus();
      if (res.success) {
        // Once server confirms running, clear local state — server state
        // handles button disable via item.status
        setTriggeringNames((prev) => {
          if (prev.size === 0) return prev;
          const next = new Set(prev);
          for (const item of res.data.items) {
            if (item.status === "running") {
              next.delete(item.collector_name);
              // Cancel cooldown timer since server now tracks this
              const timer = cooldownTimers.current.get(item.collector_name);
              if (timer) {
                clearTimeout(timer);
                cooldownTimers.current.delete(item.collector_name);
              }
            }
          }
          return next;
        });
        return res.data.items;
      }
      return [];
    },
    refetchInterval: 2_000,
  });

  const { data: settingsData } = useQuery({
    queryKey: ["collect", "settings"],
    queryFn: async () => {
      const res = await getCollectSettings();
      return res.success ? res.data.items : [];
    },
    staleTime: 30_000,
  });

  const descriptionMap = useRef<Record<string, string>>({});
  const sortOrderMap = useRef<Record<string, number>>({});
  if (settingsData) {
    descriptionMap.current = Object.fromEntries(
      settingsData.map((s) => [s.collector_name, s.description ?? ""]),
    );
    sortOrderMap.current = Object.fromEntries(
      settingsData.map((s) => [s.collector_name, s.sort_order]),
    );
  }

  const handleTrigger = useCallback(async (name: string) => {
    const now = Date.now();
    const lastTriggered = lastTriggeredRef.current.get(name) ?? 0;
    if (now - lastTriggered < COOLDOWN_MS) return;

    lastTriggeredRef.current.set(name, now);
    setTriggeringNames((prev) => new Set(prev).add(name));
    try {
      await triggerCollect(name);
      const displayLabel = descriptionMap.current[name] || name;
      message.success(`已触发 ${displayLabel}`);
      refetch();
      // Auto-clear cooldown after COOLDOWN_MS
      const existing = cooldownTimers.current.get(name);
      if (existing) clearTimeout(existing);
      const timer = setTimeout(() => {
        setTriggeringNames((prev) => {
          const next = new Set(prev);
          next.delete(name);
          return next;
        });
        cooldownTimers.current.delete(name);
      }, COOLDOWN_MS);
      cooldownTimers.current.set(name, timer);
    } catch (e: any) {
      const body = await e?.response?.json().catch(() => null);
      if (body?.error?.code === "COLLECTOR_BUSY") {
        message.warning(body.error.message);
      } else {
        message.error("触发失败");
      }
      // Re-enable immediately on error
      lastTriggeredRef.current.delete(name);
      setTriggeringNames((prev) => {
        const next = new Set(prev);
        next.delete(name);
        return next;
      });
    }
  }, [refetch]);

  const handleStop = async (name: string) => {
    try {
      await stopCollect(name);
      message.success(`已发送停止信号`);
      refetch();
    } catch {
      message.error("停止失败");
    }
  };

  return (
    <div>
      <h2>
        <ThunderboltOutlined /> 数据采集控制台
      </h2>
      <Row gutter={[16, 16]}>
        {(data ?? []).sort((a: CollectorStatus, b: CollectorStatus) =>
          (sortOrderMap.current[a.collector_name] ?? 999) - (sortOrderMap.current[b.collector_name] ?? 999)
        ).map((item: CollectorStatus) => {
          const meta = STATUS_META[item.status] ?? STATUS_META.idle;
          return (
            <Col xs={24} sm={12} md={8} key={item.collector_name}>
              <Card
                size="small"
                title={
                  <span>
                    <Badge status={meta.status} />
                    {" "}{item.display_name || item.collector_name}
                  </span>
                }
                extra={
                  <Tag color={meta.status === "processing" ? "blue" : meta.status === "success" ? "green" : meta.status === "error" ? "red" : "default"}>
                    {meta.label}
                  </Tag>
                }
              >
                {descriptionMap.current[item.collector_name] && (
                  <Text type="secondary" style={{ display: "block", marginBottom: 4, fontSize: 12 }}>
                    {descriptionMap.current[item.collector_name]}
                  </Text>
                )}
                {item.message && (
                  <Text type="secondary" style={{ display: "block", marginBottom: 8 }}>
                    {item.message}
                  </Text>
                )}
                {(item.status === "running" || item.status === "completed") && (
                  <Text style={{ display: "block", marginBottom: 8 }}>
                    进度: {item.progress}/{item.total || "?"}
                  </Text>
                )}
                <div style={{ display: "flex", gap: 8 }}>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => handleTrigger(item.collector_name)}
                    disabled={item.status === "running" || triggeringNames.has(item.collector_name)}
                    loading={triggeringNames.has(item.collector_name)}
                  >
                    触发
                  </Button>
                  {item.status === "running" && (
                    <Button
                      size="small"
                      danger
                      icon={<PauseCircleOutlined />}
                      onClick={() => handleStop(item.collector_name)}
                    >
                      停止
                    </Button>
                  )}
                </div>
              </Card>
            </Col>
          );
        })}
      </Row>
    </div>
  );
}
