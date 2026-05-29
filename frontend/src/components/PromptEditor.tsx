import { useState, useEffect } from "react";
import { Modal, Tabs, Input, Button, message, Typography, Spin, Popconfirm } from "antd";
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
  /** 过滤提示词 key 前缀，如 "sector_analysis" 或 "news_sentiment"。不传则显示全部。 */
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

  // 切换 tab 时更新编辑内容
  useEffect(() => {
    if (prompts.length > 0 && !activeKey) {
      const first = prompts[0];
      setActiveKey(first.key);
      setEditingText(first.custom_text ?? first.default_text);
    }
  }, [prompts, activeKey]);

  const handleTabChange = (key: string) => {
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
      title="编辑分析提示词"
      open={open}
      onCancel={onClose}
      width={960}
      footer={[
        activeItem?.custom_text && (
          <Popconfirm
            key="reset"
            title="确认重置为默认提示词？"
            onConfirm={() => reset()}
          >
            <Button
              icon={<UndoOutlined />}
              loading={resetting}
              danger
            >
              重置为默认值
            </Button>
          </Popconfirm>
        ),
        <Button key="cancel" onClick={onClose}>
          关闭
        </Button>,
        <Button
          key="save"
          type="primary"
          icon={<SaveOutlined />}
          loading={saving}
          onClick={() => save()}
        >
          保存
        </Button>,
      ]}
    >
      {isLoading ? (
        <div style={{ textAlign: "center", padding: 40 }}>
          <Spin />
        </div>
      ) : (
        <Tabs
          activeKey={activeKey}
          onChange={(key) => handleTabChange(key)}
          items={prompts.map((item: PromptItem) => ({
            key: item.key,
            label: item.label,
            children: (
              <div style={{ display: "flex", gap: 16, height: "60vh" }}>
                {/* 左侧：编辑区 */}
                <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                  <Text strong style={{ marginBottom: 8 }}>
                    自定义提示词
                  </Text>
                  <TextArea
                    value={editingText}
                    onChange={(e) => setEditingText(e.target.value)}
                    style={{ flex: 1, fontFamily: "monospace", fontSize: 13 }}
                    placeholder="在此编辑提示词..."
                  />
                  {item.custom_text && (
                    <Text type="secondary" style={{ marginTop: 4 }}>
                      已自定义（上次保存：覆盖默认值）
                    </Text>
                  )}
                  {!item.custom_text && (
                    <Text type="secondary" style={{ marginTop: 4 }}>
                      当前使用默认提示词
                    </Text>
                  )}
                </div>
                {/* 右侧：默认参考 */}
                <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                  <Text strong style={{ marginBottom: 8 }}>
                    默认提示词（参考）
                  </Text>
                  <TextArea
                    value={item.default_text}
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
            ),
          }))}
        />
      )}
    </Modal>
  );
}
