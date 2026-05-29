import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Table,
  Button,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  message,
  Space,
  Dropdown,
  Tooltip,
} from "antd";
import type { MenuProps } from "antd";
import {
  PlusOutlined,
  CheckCircleOutlined,
  MoreOutlined,
  EditOutlined,
  DeleteOutlined,
  ApiOutlined,
} from "@ant-design/icons";
import { useState } from "react";
import {
  listProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  activateProvider,
  testProviderConnection,
} from "@/api/providers";
import type { AIProviderItem } from "@/api/providers";

const PROVIDER_TYPES = [
  "deepseek",
  "glm",
  "qwen",
  "openai",
  "kimi",
  "minimax",
];

export function AIProviders() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<AIProviderItem | null>(null);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["ai-providers"],
    queryFn: async () => {
      const res = await listProviders();
      return res.success ? res.data.items : [];
    },
  });

  const createMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => createProvider(body as Parameters<typeof createProvider>[0]),
    onSuccess: () => {
      message.success("创建成功");
      queryClient.invalidateQueries({ queryKey: ["ai-providers"] });
      setModalOpen(false);
      form.resetFields();
    },
    onError: () => message.error("创建失败"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Record<string, unknown>) =>
      updateProvider(id, body),
    onSuccess: () => {
      message.success("更新成功");
      queryClient.invalidateQueries({ queryKey: ["ai-providers"] });
      setModalOpen(false);
      setEditing(null);
      form.resetFields();
    },
    onError: () => message.error("更新失败"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProvider,
    onSuccess: () => {
      message.success("删除成功");
      queryClient.invalidateQueries({ queryKey: ["ai-providers"] });
    },
    onError: () => message.error("删除失败"),
  });

  const activateMutation = useMutation({
    mutationFn: activateProvider,
    onSuccess: () => {
      message.success("已切换激活");
      queryClient.invalidateQueries({ queryKey: ["ai-providers"] });
    },
    onError: () => message.error("激活失败"),
  });

  const testMutation = useMutation({
    mutationFn: testProviderConnection,
    onSuccess: (res) => {
      if (res.success && res.data) {
        if (res.data.success) {
          message.success(`连接成功: ${res.data.reply}`);
        } else {
          message.error(`连接失败: ${res.data.error}`);
        }
      }
    },
    onError: () => message.error("测试请求失败"),
  });

  const handleOpenCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleOpenEdit = (record: AIProviderItem) => {
    setEditing(record);
    form.setFieldsValue(record);
    setModalOpen(true);
  };

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      if (editing) {
        updateMutation.mutate({ id: editing.id, ...values });
      } else {
        createMutation.mutate(values);
      }
    });
  };

  const columns = [
    { title: "名称", dataIndex: "name", key: "name", width: 120 },
    {
      title: "类型",
      dataIndex: "provider_type",
      key: "provider_type",
      width: 100,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    { title: "模型", dataIndex: "model_name", key: "model_name", width: 140, ellipsis: true },
    { title: "API Base", dataIndex: "api_base_url", key: "api_base_url", ellipsis: true },
    {
      title: "状态",
      dataIndex: "is_active",
      key: "is_active",
      width: 80,
      render: (v: boolean) =>
        v ? <Tag color="green">激活</Tag> : <Tag>未激活</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      width: 120,
      render: (_: unknown, record: AIProviderItem) => {
        const items: MenuProps["items"] = [
          ...(!record.is_active
            ? [{
                key: "activate",
                icon: <CheckCircleOutlined />,
                label: "激活",
                onClick: () => activateMutation.mutate(record.id),
              }]
            : []),
          {
            key: "test",
            icon: <ApiOutlined />,
            label: "测试连接",
            onClick: () => testMutation.mutate(record.id),
          },
          {
            key: "edit",
            icon: <EditOutlined />,
            label: "编辑",
            onClick: () => handleOpenEdit(record),
          },
          ...(!record.is_active
            ? [{
                key: "delete",
                icon: <DeleteOutlined />,
                label: "删除",
                danger: true,
                onClick: () => deleteMutation.mutate(record.id),
              }]
            : []),
        ];
        return (
          <Space size="small">
            {!record.is_active && (
              <Tooltip title="激活">
                <Button
                  size="small"
                  type="primary"
                  ghost
                  icon={<CheckCircleOutlined />}
                  onClick={() => activateMutation.mutate(record.id)}
                />
              </Tooltip>
            )}
            <Tooltip title="测试连接">
              <Button
                size="small"
                icon={<ApiOutlined />}
                loading={testMutation.isPending}
                onClick={() => testMutation.mutate(record.id)}
              />
            </Tooltip>
            <Dropdown menu={{ items }} trigger={["click"]}>
              <Button size="small" icon={<MoreOutlined />} />
            </Dropdown>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <h2>AI Provider 配置</h2>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={handleOpenCreate}
        style={{ marginBottom: 16 }}
      >
        添加 Provider
      </Button>
      <Table
        columns={columns}
        dataSource={data ?? []}
        rowKey="id"
        loading={isLoading}
        pagination={false}
      />

      <Modal
        title={editing ? "编辑 Provider" : "添加 Provider"}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => {
          setModalOpen(false);
          setEditing(null);
          form.resetFields();
        }}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: "请输入名称" }]}
          >
            <Input placeholder="如 DeepSeek 生产" />
          </Form.Item>
          <Form.Item
            name="provider_type"
            label="类型"
            rules={[{ required: true, message: "请选择类型" }]}
          >
            <Select options={PROVIDER_TYPES.map((t) => ({ value: t, label: t }))} />
          </Form.Item>
          <Form.Item
            name="api_key"
            label="API Key"
            rules={[{ required: true, message: "请输入 API Key" }]}
          >
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          <Form.Item
            name="api_base_url"
            label="API Base URL"
            rules={[{ required: true, message: "请输入 API Base URL" }]}
          >
            <Input placeholder="https://api.deepseek.com" />
          </Form.Item>
          <Form.Item
            name="model_name"
            label="模型名称"
            rules={[{ required: true, message: "请输入模型名称" }]}
          >
            <Input placeholder="deepseek-chat" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
