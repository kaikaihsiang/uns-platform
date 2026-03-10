/**
 * AppLayout — Main application shell with Sidebar + Header + Content.
 */
import { useState } from 'react';
import { Layout, Menu, Avatar, Tooltip } from 'antd';
import {
    ApartmentOutlined,
    DatabaseOutlined,
    SettingOutlined,
    DashboardOutlined,
    UserOutlined,
    MenuFoldOutlined,
    MenuUnfoldOutlined,
    SafetyCertificateOutlined,
    RobotOutlined,
    DeleteOutlined,
    HistoryOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

const { Sider, Header, Content } = Layout;

const menuItems = [
    {
        key: '/namespace',
        icon: <ApartmentOutlined />,
        label: 'Namespace 管理',
    },
    {
        key: '/tags',
        icon: <DatabaseOutlined />,
        label: 'Tag 總覽',
    },
    {
        key: '/schemas',
        icon: <SafetyCertificateOutlined />,
        label: 'Schema 管理',
    },
    {
        key: '/schema-detect',
        icon: <SafetyCertificateOutlined />,
        label: 'Schema 建議',
    },
    {
        key: '/recycle-bin',
        icon: <DeleteOutlined />,
        label: '資源回收桶',
    },
    {
        key: '/ai-assistant',
        icon: <RobotOutlined />,
        label: 'AI 助手',
    },
    {
        key: '/run-history',
        icon: <HistoryOutlined />,
        label: '生產批次歷史',
    },
    {
        key: '/dashboard',
        icon: <DashboardOutlined />,
        label: '儀表板',
    },
    {
        key: '/settings',
        icon: <SettingOutlined />,
        label: '系統設定',
    },
];

export default function AppLayout() {
    const [collapsed, setCollapsed] = useState(false);
    const navigate = useNavigate();
    const location = useLocation();
    const { currentUser } = useAuthStore();

    const selectedKey = '/' + (location.pathname.split('/')[1] || 'namespace');

    return (
        <Layout className="app-layout">
            <Sider
                className="app-sider"
                width={260}
                collapsedWidth={64}
                collapsible
                collapsed={collapsed}
                onCollapse={setCollapsed}
                trigger={null}
            >
                {/* Logo */}
                <div className="sidebar-logo" onClick={() => navigate('/')}>
                    <div className="sidebar-logo-icon">U</div>
                    {!collapsed && (
                        <div className="sidebar-logo-text">
                            <span className="sidebar-logo-title">UNS Platform</span>
                            <span className="sidebar-logo-subtitle">Namespace Data Platform</span>
                        </div>
                    )}
                </div>

                {/* Navigation */}
                <Menu
                    mode="inline"
                    selectedKeys={[selectedKey]}
                    items={menuItems}
                    onClick={({ key }) => navigate(key)}
                    style={{
                        background: 'transparent',
                        borderRight: 'none',
                        marginTop: 8,
                    }}
                />
            </Sider>

            <Layout>
                {/* Header */}
                <Header className="app-header">
                    <div className="app-header-left">
                        <Tooltip title={collapsed ? '展開側欄' : '收合側欄'}>
                            {collapsed ? (
                                <MenuUnfoldOutlined
                                    style={{ fontSize: 18, cursor: 'pointer', color: 'var(--text-secondary)' }}
                                    onClick={() => setCollapsed(false)}
                                />
                            ) : (
                                <MenuFoldOutlined
                                    style={{ fontSize: 18, cursor: 'pointer', color: 'var(--text-secondary)' }}
                                    onClick={() => setCollapsed(true)}
                                />
                            )}
                        </Tooltip>
                    </div>

                    <div className="app-header-right">
                        <div className="header-user-info">
                            <Avatar
                                size="small"
                                icon={<UserOutlined />}
                                style={{ backgroundColor: 'var(--color-primary)' }}
                            />
                            <span className="header-user-name">{currentUser.name}</span>
                            <span className="header-user-role">{currentUser.role}</span>
                        </div>
                    </div>
                </Header>

                {/* Content — React Router Outlet */}
                <Content className="app-content">
                    <Outlet />
                </Content>
            </Layout>
        </Layout>
    );
}
