import { useNavigate } from "react-router-dom";
import { Form, Input, Button, Card, message } from "antd";
import { KeyOutlined } from "@ant-design/icons";
import { setApiKey, getApiKey } from "@/api/client";

export function ApiKeyPage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();

  const handleSubmit = (values: { apiKey: string }) => {
    setApiKey(values.apiKey);
    message.success("API Key 已保存");
    navigate("/");
  };

  const existing = getApiKey();

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f5f5f5",
      }}
    >
      <Card style={{ width: 400 }}>
        <h2 style={{ textAlign: "center", marginBottom: 24 }}>
          <KeyOutlined /> FundPilot API Key
        </h2>
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item
            name="apiKey"
            label="API Key"
            rules={[{ required: true, message: "请输入 API Key" }]}
          >
            <Input.Password
              placeholder="输入后端 API Key"
              defaultValue={existing ?? ""}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              保存并进入
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
