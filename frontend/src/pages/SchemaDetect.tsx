import React, { useEffect } from 'react';
import { Table, Button, Card, Tag, Space, Typography, Empty, Modal, message, Badge, Select } from 'antd';
import {
    CheckCircleOutlined,
    CloseCircleOutlined,
    InfoCircleOutlined,
    SafetyCertificateOutlined,
    ClockCircleOutlined,
} from '@ant-design/icons';
import { useSchemaStore } from '../store/schemaStore';
import './SchemaDetect.css';

const { Title, Text, Paragraph } = Typography;

const SchemaDetect: React.FC = () => {
    const { suggestions, isLoading, fetchSuggestions, approveSuggestion, deleteSchema } = useSchemaStore();
    const [approveModalOpen, setApproveModalOpen] = React.useState(false);
    const [selectedSuggestion, setSelectedSuggestion] = React.useState<any>(null);
    const [selectedCategory, setSelectedCategory] = React.useState<string>('telemetry');

    useEffect(() => {
        fetchSuggestions();
        // Poll for new suggestions every 10 seconds for demo
        const interval = setInterval(fetchSuggestions, 10000);
        return () => clearInterval(interval);
    }, [fetchSuggestions]);

    const showApproveModal = (record: any) => {
        setSelectedSuggestion(record);
        setSelectedCategory(record.category || 'telemetry');
        setApproveModalOpen(true);
    };

    const handleConfirmApprove = async () => {
        if (!selectedSuggestion) return;
        const ok = await approveSuggestion(selectedSuggestion.type_id, selectedCategory);
        if (ok) {
            message.success('Schema 已核准並轉正');
            setApproveModalOpen(false);
        } else {
            message.error('核准失敗');
        }
    };

    const handleDelete = async (id: number, name: string) => {
        Modal.confirm({
            title: '捨棄建議',
            content: `確定要捨棄這個 Schema 建議嗎？(Topic: ${name})`,
            okText: '捨棄',
            okType: 'danger',
            cancelText: '取消',
            onOk: async () => {
                const ok = await deleteSchema(id);
                if (ok) {
                    message.success('建議已捨棄');
                } else {
                    message.error('捨棄失敗');
                }
            },
        });
    };

    const columns = [
        {
            title: '建議名稱',
            render: (text: string, r: any) => (
                <Space direction="vertical" size={2}>
                    <Text strong>{text}</Text>
                    {r.category && (
                        <Tag color={
                            r.category === 'telemetry' ? 'blue' :
                                r.category === 'alarm' ? 'red' :
                                    r.category === 'status' ? 'green' :
                                        r.category === 'event' ? 'purple' :
                                            r.category === 'measurement' ? 'orange' : 'default'
                        }>
                            {r.category.toUpperCase()}
                        </Tag>
                    )}
                </Space>
            ),
        },
        {
            title: '對應 Topic (Pattern)',
            dataIndex: 'topic_pattern',
            key: 'topic_pattern',
            render: (text: string) => <Tag color="blue">{text}</Tag>,
        },
        {
            title: '推斷欄位',
            dataIndex: 'fields',
            key: 'fields',
            render: (fields: any[]) => (
                <div className="field-tags">
                    {fields && Array.isArray(fields) ? fields.map(f => (
                        <Tag key={f.name} className="field-tag">
                            {f.name} <span className="field-type">({f.type})</span>
                        </Tag>
                    )) : null}
                </div>
            ),
        },
        {
            title: '偵測時間',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (date: string) => (
                <Text type="secondary" style={{ fontSize: '12px' }}>
                    <ClockCircleOutlined /> {new Date(date).toLocaleString()}
                </Text>
            ),
        },
        {
            title: '操作',
            key: 'action',
            render: (_: any, record: any) => (
                <Space size="middle">
                    <Button
                        type="primary"
                        icon={<CheckCircleOutlined />}
                        onClick={() => showApproveModal(record)}
                    >
                        核准
                    </Button>
                    <Button
                        danger
                        icon={<CloseCircleOutlined />}
                        onClick={() => handleDelete(record.type_id, record.type_name)}
                    >
                        捨棄
                    </Button>
                </Space>
            ),
        },
    ];

    return (
        <div className="schema-detect-page">
            <div className="page-header">
                <div>
                    <Title level={2}>
                        <SafetyCertificateOutlined style={{ marginRight: 12, color: 'var(--color-primary)' }} />
                        Schema 自動偵測與建議
                    </Title>
                    <Paragraph type="secondary">
                        Data Engine 自動分析未知 Topic Payload 並推斷出結構定義。您可以在此核准建議，將其轉為正式 Schema。
                    </Paragraph>
                </div>
                <div className="header-stats">
                    <Badge count={suggestions.length} offset={[10, 0]}>
                        <Button onClick={fetchSuggestions} loading={isLoading}>
                            重新整理
                        </Button>
                    </Badge>
                </div>
            </div>

            <Card className="suggestion-card">
                <Table
                    columns={columns}
                    dataSource={suggestions}
                    rowKey="type_id"
                    loading={isLoading}
                    pagination={{ pageSize: 10 }}
                    locale={{
                        emptyText: (
                            <Empty
                                image={Empty.PRESENTED_IMAGE_SIMPLE}
                                description="目前沒有新的 Schema 建議"
                            />
                        ),
                    }}
                />
            </Card>

            <div className="info-section">
                <Card title={<span><InfoCircleOutlined /> 運作機制</span>} size="small">
                    <ul className="mechanism-list">
                        <li><strong>取樣分析：</strong>Data Engine 收集未知 Topic 的前 10 筆 Payload。</li>
                        <li><strong>結構推斷：</strong>分析 JSON 欄位與型別 (Number 為 float, String 為 string)。</li>
                        <li><strong>核准轉正：</strong>核准後，該 Pattern 下的所有 Topic 將自動套用此 Schema 並開始存入資料庫。</li>
                    </ul>
                </Card>
            </div>

            <Modal
                title="核准並轉正 Schema"
                open={approveModalOpen}
                onOk={handleConfirmApprove}
                onCancel={() => setApproveModalOpen(false)}
                okText="核准轉正"
                cancelText="取消"
            >
                <div style={{ marginTop: 10 }}>
                    <Paragraph>
                        確定要將推斷出的 Schema <Text strong>"{selectedSuggestion?.type_name}"</Text> 轉為正式定義嗎？
                    </Paragraph>
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: 16, borderRadius: 8, marginBottom: 16 }}>
                        <Text type="secondary" style={{ fontSize: 13 }}>對應 Topic Pattern:</Text>
                        <br />
                        <Text code>{selectedSuggestion?.topic_pattern}</Text>
                    </div>

                    <Text strong>選擇資料類別 (Category):</Text>
                    <Select
                        style={{ width: '100%', marginTop: 8 }}
                        value={selectedCategory}
                        onChange={setSelectedCategory}
                        options={[
                            { value: 'telemetry', label: 'Telemetry (連續傳感數據)' },
                            { value: 'status', label: 'Status (設備狀態機)' },
                            { value: 'alarm', label: 'Alarm (警報事件)' },
                            { value: 'event', label: 'Event (一般離散事件)' },
                            { value: 'measurement', label: 'Measurement (品管量測)' }
                        ]}
                    />
                    <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 12 }}>
                        ⓘ 核准後，系統將根據此類別將資料路由到不同的資料庫表。
                    </Paragraph>
                </div>
            </Modal>
        </div>
    );
};

export default SchemaDetect;
