import { useEffect } from 'react';
import { Typography, Card, Row, Col, Descriptions, Badge, Tag, Statistic, Table, Button, Tooltip, Space } from 'antd';
import {
    SettingOutlined,
    CloudServerOutlined,
    DatabaseOutlined,
    ApiOutlined,
    WifiOutlined,
    ReloadOutlined,
    CheckCircleOutlined,
    CloseCircleOutlined,
} from '@ant-design/icons';
import { useSystemStore } from '../store/systemStore';
import { useSchemaStore } from '../store/schemaStore';

const { Title, Text } = Typography;

function formatUptime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
}

function StatusDot({ ok }: { ok: boolean }) {
    return (
        <Badge
            status={ok ? 'success' : 'error'}
            text={ok ? '連線中' : '離線'}
        />
    );
}

// ─── Panel 1: Platform Info ──────────────────────────────────

function PlatformInfoPanel() {
    const { info, isLoading, fetchInfo } = useSystemStore();

    return (
        <Card
            title={<><CloudServerOutlined style={{ marginRight: 8 }} />平台資訊</>}
            loading={isLoading && !info}
            extra={
                <Tooltip title="重新載入">
                    <Button type="text" size="small" icon={<ReloadOutlined />} onClick={fetchInfo} />
                </Tooltip>
            }
        >
            {info ? (
                <Descriptions column={1} size="small">
                    <Descriptions.Item label="Platform Version">
                        <Tag color="cyan">v{info.platform_version}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="Backend">
                        <StatusDot ok={info.backend_status === 'ok'} />
                    </Descriptions.Item>
                    <Descriptions.Item label="Database">
                        <Space direction="vertical" size={2}>
                            <StatusDot ok={info.database.status === 'connected'} />
                            <Text type="secondary" style={{ fontSize: 11 }}>
                                {info.database.version.split(',')[0]}
                            </Text>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                                Pool: {info.database.connection_pool.checked_out}/{info.database.connection_pool.size}
                            </Text>
                        </Space>
                    </Descriptions.Item>
                    <Descriptions.Item label="MQTT Broker">
                        <Space direction="vertical" size={2}>
                            <StatusDot ok={info.mqtt_broker.status === 'connected'} />
                            <Text type="secondary" style={{ fontSize: 11 }}>
                                {info.mqtt_broker.host}
                            </Text>
                        </Space>
                    </Descriptions.Item>
                    <Descriptions.Item label="Uptime">
                        <Text strong>{formatUptime(info.uptime_seconds)}</Text>
                    </Descriptions.Item>
                </Descriptions>
            ) : (
                <Text type="secondary">載入中...</Text>
            )}
        </Card>
    );
}

// ─── Panel 2: MQTT Stats ─────────────────────────────────────

function MqttStatsPanel() {
    const { mqttStats, wsConnected, connectMqttWs, disconnectMqttWs, fetchMqttStats } = useSystemStore();

    useEffect(() => {
        connectMqttWs();
        return () => disconnectMqttWs();
    }, []);

    return (
        <Card
            title={<><ApiOutlined style={{ marginRight: 8 }} />MQTT Broker 狀態</>}
            extra={
                <Space size={4}>
                    <Badge status={wsConnected ? 'processing' : 'default'} text="" />
                    <Tag color={wsConnected ? 'green' : 'default'} style={{ fontSize: 11, margin: 0 }}>
                        {wsConnected ? 'LIVE' : 'OFFLINE'}
                    </Tag>
                    <Tooltip title="手動更新">
                        <Button type="text" size="small" icon={<ReloadOutlined />} onClick={fetchMqttStats} />
                    </Tooltip>
                </Space>
            }
        >
            {mqttStats ? (
                <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Statistic
                            title="Connected Clients"
                            value={mqttStats.connected_clients}
                            prefix={<WifiOutlined />}
                        />
                    </Col>
                    <Col span={12}>
                        <Statistic title="Topics" value={mqttStats.topics_count} />
                    </Col>
                    <Col span={12}>
                        <Statistic title="Subscriptions" value={mqttStats.subscriptions_count} />
                    </Col>
                    <Col span={12}>
                        <Statistic
                            title="Messages/s"
                            value={mqttStats.messages_per_second}
                            precision={1}
                        />
                    </Col>
                    <Col span={12}>
                        <Statistic title="Received Total" value={mqttStats.messages_received_total} />
                    </Col>
                    <Col span={12}>
                        <Statistic title="Retained" value={mqttStats.retained_messages_count} />
                    </Col>
                </Row>
            ) : (
                <Text type="secondary">等待 MQTT 統計資料...</Text>
            )}
        </Card>
    );
}

// ─── Panel 3: Retention Policy ───────────────────────────────

function RetentionPanel() {
    const { retention, fetchRetention } = useSystemStore();

    const columns = [
        {
            title: 'Table',
            dataIndex: 'table_name',
            key: 'table_name',
            render: (name: string) => <Text code>{name}</Text>,
        },
        {
            title: '保留天數',
            dataIndex: 'retention_days',
            key: 'retention_days',
            render: (days: number | null) =>
                days ? <Tag color="blue">{days} 天</Tag> : <Tag>未設定</Tag>,
        },
        {
            title: '壓縮',
            dataIndex: 'compression_enabled',
            key: 'compression_enabled',
            render: (enabled: boolean, record: any) =>
                enabled ? (
                    <Space size={4}>
                        <CheckCircleOutlined style={{ color: '#00d2d3' }} />
                        <Text type="secondary" style={{ fontSize: 11 }}>
                            {record.compress_after_days}天後
                        </Text>
                    </Space>
                ) : (
                    <CloseCircleOutlined style={{ color: '#636e72' }} />
                ),
        },
    ];

    return (
        <Card
            title={<><DatabaseOutlined style={{ marginRight: 8 }} />資料保留策略</>}
            extra={
                <Tooltip title="重新載入">
                    <Button type="text" size="small" icon={<ReloadOutlined />} onClick={fetchRetention} />
                </Tooltip>
            }
        >
            <Table
                dataSource={retention}
                columns={columns}
                rowKey="table_name"
                pagination={false}
                size="small"
            />
            <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 11 }}>
                ⓘ 保留策略修改功能將在 Phase 2 提供
            </Text>
        </Card>
    );
}

// ─── Panel 4: Schema Engine Summary ──────────────────────────

function SchemaEnginePanel() {
    const { schemas, fetchSchemas } = useSchemaStore();

    useEffect(() => {
        if (schemas.length === 0) fetchSchemas();
    }, []);

    const misMatchCounts: Record<string, number> = {};
    const newFieldCounts: Record<string, number> = {};

    schemas.forEach((s: any) => {
        const mm = s.on_schema_mismatch || 'log_and_store';
        const nf = s.on_new_field || 'suggest';
        misMatchCounts[mm] = (misMatchCounts[mm] || 0) + 1;
        newFieldCounts[nf] = (newFieldCounts[nf] || 0) + 1;
    });

    return (
        <Card title={<><SettingOutlined style={{ marginRight: 8 }} />Schema Engine 設定</>}>
            <Descriptions column={1} size="small">
                <Descriptions.Item label="已定義 Schema 數">
                    <Tag color="cyan">{schemas.length}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label="on_schema_mismatch">
                    <Space wrap>
                        {Object.entries(misMatchCounts).map(([k, v]) => (
                            <Tag key={k} color={k === 'strict' ? 'red' : k === 'reject' ? 'orange' : 'blue'}>
                                {k}: {v}
                            </Tag>
                        ))}
                    </Space>
                </Descriptions.Item>
                <Descriptions.Item label="on_new_field">
                    <Space wrap>
                        {Object.entries(newFieldCounts).map(([k, v]) => (
                            <Tag key={k} color={k === 'auto_create' ? 'green' : k === 'suggest' ? 'gold' : 'default'}>
                                {k}: {v}
                            </Tag>
                        ))}
                    </Space>
                </Descriptions.Item>
            </Descriptions>
            <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 11 }}>
                ⓘ 各 Schema 可獨立設定策略，此處為全域彙總統計
            </Text>
        </Card>
    );
}

// ─── Main Page ───────────────────────────────────────────────

export default function SystemSettings() {
    const { fetchInfo, fetchRetention } = useSystemStore();

    useEffect(() => {
        fetchInfo();
        fetchRetention();
    }, []);

    return (
        <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
            <div style={{ marginBottom: 24 }}>
                <Title level={2}>
                    <SettingOutlined style={{ marginRight: 12, color: 'var(--color-primary)' }} />
                    系統設定
                </Title>
                <Text type="secondary">
                    平台健康狀態總覽 — 所有設定為唯讀。
                </Text>
            </div>

            <Row gutter={[16, 16]}>
                <Col xs={24} lg={12}>
                    <PlatformInfoPanel />
                </Col>
                <Col xs={24} lg={12}>
                    <MqttStatsPanel />
                </Col>
                <Col xs={24} lg={12}>
                    <RetentionPanel />
                </Col>
                <Col xs={24} lg={12}>
                    <SchemaEnginePanel />
                </Col>
            </Row>
        </div>
    );
}
