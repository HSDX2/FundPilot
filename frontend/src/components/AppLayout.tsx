import { useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, Typography, Space } from "antd";
import {
  DashboardOutlined,
  LineChartOutlined,
  PieChartOutlined,
  FundOutlined,
  FileTextOutlined,
  BulbOutlined,
  SmileOutlined,
  SoundOutlined,
  ReadOutlined,
  CloudDownloadOutlined,
  FileSearchOutlined,
  SettingOutlined,
  KeyOutlined,
  StarOutlined,
  ArrowLeftOutlined,
} from "@ant-design/icons";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "首页看板" },
  { key: "/funds", icon: <FundOutlined />, label: "基金查询" },
  { key: "/sectors", icon: <PieChartOutlined />, label: "板块排行" },
  {
    key: "/analysis",
    icon: <BulbOutlined />,
    label: "AI 分析",
    children: [
      { key: "/analysis/reports", icon: <FileTextOutlined />, label: "板块分析报告" },
      { key: "/analysis/news-sentiment", icon: <SoundOutlined />, label: "新闻情绪分析" },
      { key: "/analysis/advice", icon: <LineChartOutlined />, label: "操作建议" },
      { key: "/analysis/sentiment", icon: <SmileOutlined />, label: "市场情绪" },
	      { key: "/analysis/recommend", icon: <BulbOutlined />, label: "AI 推荐" },
    ],
  },
  { key: "/news", icon: <ReadOutlined />, label: "新闻资讯" },
  { key: "/watchlist", icon: <StarOutlined />, label: "关注列表" },
  {
    key: "collect",
    icon: <CloudDownloadOutlined />,
    label: "数据采集",
    children: [
      { key: "/collect", icon: <DashboardOutlined />, label: "采集状态" },
      { key: "/collect/logs", icon: <FileSearchOutlined />, label: "采集日志" },
      { key: "/collect/settings", icon: <SettingOutlined />, label: "采集配置" },
    ],
  },
  { key: "/settings/ai", icon: <KeyOutlined />, label: "AI 配置" },
];

function findOpenKeys(pathname: string): string[] {
  if (pathname.startsWith("/analysis")) return ["/analysis"];
  if (pathname.startsWith("/collect")) return ["collect"];
  return [];
}

/** 判断当前路由是否为详情页（显示返回按钮） */
function isDetailPage(pathname: string): boolean {
  // /funds/xxx, /sectors/xxx, /analysis/reports/xxx (但排除列表页)
  if (pathname === "/funds" || pathname === "/sectors" || pathname === "/analysis/reports") return false;
  return /^\/(funds|sectors)\/.+/.test(pathname) || /^\/analysis\/reports\/.+/.test(pathname);
}

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={200}
      >
        <div
          style={{
            height: 48,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Text
            strong
            style={{ color: "#fff", fontSize: collapsed ? 14 : 18 }}
          >
            {collapsed ? "FP" : "FundPilot"}
          </Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={findOpenKeys(location.pathname)}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <Space>
            {isDetailPage(location.pathname) && (
              <Button
                type="text"
                icon={<ArrowLeftOutlined />}
                onClick={() => navigate(-1)}
              >
                返回
              </Button>
            )}
          </Space>
          <Button
            type="link"
            icon={<KeyOutlined />}
            onClick={() => navigate("/api-key")}
          >
            API Key
          </Button>
        </Header>
        <Content style={{ margin: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
