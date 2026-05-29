import { useState, useEffect } from "react";
import { Modal, Input, Button, message, Typography, Spin, Popconfirm } from "antd";
import { SaveOutlined, UndoOutlined } from "@ant-design/icons";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listPrompts,
  savePrompt,
  resetPrompt,
  type PromptItem,
} from "@/api/prompts";

const { TextArea } = Input;
const { Text } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
  /** 过滤提示词 key 前缀，不传则显示全部。 */
  filter?: string;
}

export function PromptEditor({ open, onClose, filter }: Props) {
  const queryClient = useQueryClient();
  const [activeKey, setActiveKey] = useState<string>("");
  const [editingText, setEditingText] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: async () => {
      const res = await listPrompts();
      return res.success ? res.data.items : [];
    },
    enabled: open,
  });

  const prompts = filter
    ? (data ?? []).filter((p) => p.key.startsWith(filter))
    : (data ?? []);

  // 初始化选中第一个
  useEffect(() => {
    if (prompts.length > 0 && !activeKey) {
      const first = prompts[0];
      setActiveKey(first.key);
      setEditingText(first.custom_text ?? first.default_text);
    }
  }, [prompts, activeKey]);

  const handleSelect = (key: string) => {
    setActiveKey(key);
    const item = prompts.find((p) => p.key === key);
    if (item) {
      setEditingText(item.custom_text ?? item.default_text);
    }
  };

  const activeItem = prompts.find((p) => p.key === activeKey);

  const { mutate: save, isPending: saving } = useMutation({
    mutationFn: () => savePrompt(activeKey, editingText),
    onSuccess: (res) => {
      if (res.success) {
        message.success("提示词已保存");
        queryClient.invalidateQueries({ queryKey: ["prompts"] });
      } else {
        message.error("保存失败");
      }
    },
    onError: () => message.error("保存请求失败"),
  });

  const { mutate: reset, isPending: resetting } = useMutation({
    mutationFn: () => resetPrompt(activeKey),
    onSuccess: (res) => {
      if (res.success) {
        message.success("已重置为默认值");
        queryClient.invalidateQueries({ queryKey: ["prompts"] });
        if (activeItem) {
          setEditingText(activeItem.default_text);
        }
      } else {
        message.error("重置失败");
      }
    },
    onError: () => message.error("重置请求失败"),
  });

  return (
    <Modal
      title="编辑提示词"
      open={open}
      onCancel={onClose}
      width={1100}
      footer={[
        activeItem?.custom_text && (
          <Popconfirm
            key="reset"
            title="确认重置为默认提示词？"
            onConfirm={() => reset()}
          >
            <Button icon={<UndoOutlined />} loading={resetting} danger>
              重置为默认值
            </Button>
          </Popconfirm>
        ),
        <Button key="cancel" onClick={onClose}>关闭</Button>,
        <Button key="save" type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => save()}>
          保存
        </Button>,
      ]}
    >
      {isLoading ? (
        <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>
      ) : (
        <div style={{ display: "flex", gap: 0, height: "65vh" }}>
          {/* 左侧：列表 */}
          <div style={{
            width: 220, flexShrink: 0, overflowY: "auto",
            borderRight: "1px solid #f0f0f0", padding: "8px 0",
          }}>
            {prompts.map((item: PromptItem) => (
              <div
                key={item.key}
                onClick={() => handleSelect(item.key)}
                style={{
                  padding: "10px 16px",
                  cursor: "pointer",
                  fontSize: 13,
                  backgroundColor: activeKey === item.key ? "#e6f4ff" : "transparent",
                  color: activeKey === item.key ? "#1677ff" : "#333",
                  borderRight: activeKey === item.key ? "2px solid #1677ff" : "2px solid transparent",
                  transition: "all 0.2s",
                }}
              >
                <div style={{ fontWeight: activeKey === item.key ? 600 : 400 }}>
                  {item.label}
                </div>
                {item.custom_text && (
                  <div style={{ fontSize: 11, color: "#faad14", marginTop: 2 }}>
                    ● 已自定义
                  </div>
                )}
              </div>
            ))}
          </div>
          {/* 右侧：编辑区 */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "0 16px" }}>
            {activeItem ? (
              <>
                <Text strong style={{ marginBottom: 8, fontSize: 13 }}>
                  {activeItem.label}
                </Text>
                <div style={{ display: "flex", gap: 12, flex: 1, minHeight: 0 }}>
                  {/* 自定义编辑 */}
                  <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                    <Text type="secondary" style={{ fontSize: 12, marginBottom: 4 }}>
                      自定义提示词
                    </Text>
                    <TextArea
                      value={editingText}
                      onChange={(e) => setEditingText(e.target.value)}
                      style={{ flex: 1, fontFamily: "monospace", fontSize: 13 }}
                      placeholder="在此编辑提示词..."
                    />
                    {activeItem.custom_text ? (
                      <Text type="warning" style={{ marginTop: 4, fontSize: 12 }}>
                        ● 已自定义
                      </Text>
                    ) : (
                      <Text type="secondary" style={{ marginTop: 4, fontSize: 12 }}>
                        当前使用默认提示词
                      </Text>
                    )}
                  </div>
                  {/* 默认参考 */}
                  <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                    <Text type="secondary" style={{ fontSize: 12, marginBottom: 4 }}>
                      默认提示词（参考）
                    </Text>
                    <TextArea
                      value={activeItem.default_text}
                      readOnly
                      style={{
                        flex: 1,
                        fontFamily: "monospace",
                        fontSize: 13,
                        backgroundColor: "#fafafa",
                        color: "#888",
                      }}
                    />
                  </div>
                </div>
              </>
            ) : (
              <div style={{ textAlign: "center", padding: 40 }}>
                <Text type="secondary">请从左侧选择一个提示词</Text>
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}
