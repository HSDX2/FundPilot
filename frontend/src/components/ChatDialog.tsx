import { useState, useRef, useCallback, useEffect } from "react";
import {
  Modal, Input, Button, Typography, Switch, Space, Spin, Tag,
} from "antd";
import {
  SendOutlined, RobotOutlined, GlobalOutlined, SettingOutlined,
} from "@ant-design/icons";
import { PromptEditor } from "@/components/PromptEditor";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { chatStream, destroySession, type ChatContext } from "@/api/chat";

const { Text } = Typography;

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  context: ChatContext;
}

export function ChatDialog({ open, onClose, context }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "你好！我是 FundPilot AI 助手，你可以问我关于这只基金/板块的问题。" },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);
  const [webSearch, setWebSearch] = useState(context.web_search ?? false);
  const sessionRef = useRef<string | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  // Cleanup on close
  const handleClose = useCallback(async () => {
    // Abort any ongoing stream
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    // Destroy session on server
    if (sessionRef.current) {
      try {
        await destroySession(sessionRef.current);
      } catch {
        // ignore
      }
      sessionRef.current = undefined;
    }
    setMessages([
      { role: "assistant", content: "你好！我是 FundPilot AI 助手，你可以问我关于这只基金/板块的问题。" },
    ]);
    setInput("");
    setStreaming(false);
    onClose();
  }, [onClose]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");

    // Add user message
    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);

    // Add placeholder for assistant
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    let fullContent = "";

    try {
      for await (const event of chatStream(
        {
          session_id: sessionRef.current,
          message: text,
          context: { ...context, web_search: webSearch },
        },
        controller.signal,
      )) {
        switch (event.type) {
          case "session_id":
            sessionRef.current = event.content;
            break;
          case "token":
            fullContent += event.content;
            setMessages((prev) => {
              const next = [...prev];
              next[next.length - 1] = { role: "assistant", content: fullContent };
              return next;
            });
            break;
          case "tool_result":
            // Tool results are handled server-side, just notify user
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = {
                ...last,
                content: last.content + "\n\n*(正在查询数据...)*",
              };
              return next;
            });
            break;
          case "error":
            setMessages((prev) => [
              ...prev,
              { role: "system", content: `错误：${event.content}` },
            ]);
            break;
          case "done":
            // Done
            break;
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      setMessages((prev) => [
        ...prev,
        { role: "system", content: `请求中断：${err}` },
      ]);
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [input, streaming, context, webSearch]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Modal
      title={
        <Space>
          <RobotOutlined />
          <span>AI 问询</span>
          {context.fund_name && <Tag>{context.fund_name}</Tag>}
          {context.sector_name && <Tag>{context.sector_name}</Tag>}
        </Space>
      }
      open={open}
      onCancel={handleClose}
      footer={null}
      width={720}
      extra={
        <Button size="small" icon={<SettingOutlined />} onClick={() => setPromptOpen(true)}>
          提示词设置
        </Button>
      }
      destroyOnHidden
      styles={{ body: { padding: 0 } }}
    >
      {/* Message list */}
      <div
        ref={listRef}
        style={{
          height: 420,
          overflowY: "auto",
          padding: "16px 20px",
          background: "#f5f5f5",
        }}
      >
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              marginBottom: 12,
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                maxWidth: "80%",
                padding: "10px 14px",
                borderRadius: 12,
                background: msg.role === "user" ? "#1677ff" : "#fff",
                color: msg.role === "user" ? "#fff" : "#333",
                fontSize: 14,
                lineHeight: 1.7,
                boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {msg.role === "system" ? (
                <Text type="warning" style={{ fontSize: 13 }}>{msg.content}</Text>
              ) : msg.content === "" && msg.role === "assistant" ? (
                <Spin size="small" />
              ) : msg.role === "assistant" ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noreferrer">{children}</a>
                    ),
                    code: ({ className, children, ...props }) => {
                      const isInline = !className;
                      if (isInline) {
                        return <code style={{ background: "#f0f0f0", padding: "1px 4px", borderRadius: 4, fontSize: "0.9em" }}>{children}</code>;
                      }
                      return (
                        <pre style={{ background: "#1e1e1e", color: "#d4d4d4", padding: 12, borderRadius: 8, overflowX: "auto", fontSize: 13, lineHeight: 1.5 }}>
                          <code className={className} {...props}>{children}</code>
                        </pre>
                      );
                    },
                    table: ({ children }) => (
                      <div style={{ overflowX: "auto", margin: "8px 0" }}>
                        <table style={{ borderCollapse: "collapse", fontSize: 13, width: "100%" }}>{children}</table>
                      </div>
                    ),
                    th: ({ children }) => (
                      <th style={{ border: "1px solid #ddd", padding: "6px 10px", background: "#fafafa", fontWeight: 600, textAlign: "left" }}>{children}</th>
                    ),
                    td: ({ children }) => (
                      <td style={{ border: "1px solid #ddd", padding: "6px 10px" }}>{children}</td>
                    ),
                    p: ({ children }) => <p style={{ margin: "4px 0" }}>{children}</p>,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input area */}
      <div style={{ padding: "12px 20px", borderTop: "1px solid #f0f0f0" }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
          <GlobalOutlined style={{ color: "#999" }} />
          <Text type="secondary" style={{ fontSize: 13 }}>联网搜索</Text>
          <Switch
            size="small"
            checked={webSearch}
            onChange={setWebSearch}
          />
          <Text type="secondary" style={{ fontSize: 12, marginLeft: 4 }}>
            {webSearch ? "已开启（可搜索互联网）" : "已关闭（仅查询项目数据）"}
          </Text>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的问题..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={streaming}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={sendMessage}
            loading={streaming}
            disabled={!input.trim()}
            style={{ alignSelf: "flex-end" }}
          >
            发送
          </Button>
        </div>
      </div>
      <PromptEditor open={promptOpen} onClose={() => setPromptOpen(false)} filter="chat" />
    </Modal>
  );
}
