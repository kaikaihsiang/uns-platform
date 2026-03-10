import { useEffect } from 'react';
import { Table, Form, Input, Button, DatePicker, Card, Tag, Space, Typography } from 'antd';
import { SearchOutlined, ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import { useProductionStore } from '../store/productionStore';
import type { ProductionRun } from '../store/productionStore';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

export default function ProductionRunHistory() {
    const [form] = Form.useForm();
    const { historyRuns, isLoading, searchHistoryRuns } = useProductionStore();

    useEffect(() => {
        // Initial search to populate the table (empty params)
        searchHistoryRuns({});
    }, [searchHistoryRuns]);

    const handleSearch = async () => {
        const values = await form.validateFields();
        const params: Record<string, any> = {};

        if (values.equipment_path) params.equipment_path = values.equipment_path;
        if (values.lot_id) params.lot_id = values.lot_id;

        // Handle date range
        if (values.timeRange && values.timeRange.length === 2) {
            params.start_time = values.timeRange[0].toISOString();
            params.end_time = values.timeRange[1].toISOString();
        }

        searchHistoryRuns(params);
    };

    const handleReset = () => {
        form.resetFields();
        searchHistoryRuns({});
    };

    const columns = [
        {
            title: 'Lot ID',
            dataIndex: 'lot_id',
            key: 'lot_id',
            render: (text: string) => <Text strong>{text}</Text>,
        },
        {
            title: '設備路徑 (Equipment)',
            dataIndex: 'equipment_path',
            key: 'equipment_path',
            render: (text: string) => <Text code>{text}</Text>,
        },
        {
            title: 'Recipe',
            dataIndex: 'recipe_id',
            key: 'recipe_id',
            render: (text: string) => text || '-',
        },
        {
            title: '狀態',
            dataIndex: 'status',
            key: 'status',
            render: (status: string) => (
                <Tag color={status === 'Running' ? 'green' : status === 'Completed' ? 'blue' : 'default'}>
                    {status}
                </Tag>
            ),
        },
        {
            title: '開始時間',
            dataIndex: 'start_time',
            key: 'start_time',
            render: (time: string) => new Date(time).toLocaleString(),
        },
        {
            title: '結束時間',
            dataIndex: 'end_time',
            key: 'end_time',
            render: (time: string | null) => time ? new Date(time).toLocaleString() : '-',
        },
        {
            title: '操作員',
            dataIndex: 'operator_id',
            key: 'operator_id',
            render: (text: string) => text || '-',
        },
    ];

    return (
        <div className="page-container" style={{ padding: '24px' }}>
            <div className="page-header" style={{ marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <HistoryOutlined style={{ fontSize: '24px', color: 'var(--color-primary)' }} />
                <Title level={3} style={{ margin: 0 }}>生產批次歷史記錄 (Run History)</Title>
            </div>

            <Card style={{ marginBottom: '24px', background: 'var(--bg-glass)', border: '1px solid var(--border-color)' }}>
                <Form
                    form={form}
                    layout="inline"
                    onFinish={handleSearch}
                    style={{ gap: '16px' }}
                >
                    <Form.Item name="equipment_path" label="設備路徑">
                        <Input placeholder="過濾 Equipment Path" allowClear />
                    </Form.Item>
                    <Form.Item name="lot_id" label="Lot ID">
                        <Input placeholder="過濾 Lot ID" allowClear />
                    </Form.Item>
                    <Form.Item name="timeRange" label="時間範圍">
                        <RangePicker showTime />
                    </Form.Item>
                    <Form.Item>
                        <Space>
                            <Button type="primary" htmlType="submit" icon={<SearchOutlined />} loading={isLoading}>
                                查詢
                            </Button>
                            <Button onClick={handleReset} icon={<ReloadOutlined />}>
                                重設
                            </Button>
                        </Space>
                    </Form.Item>
                </Form>
            </Card>

            <Card style={{ background: 'var(--bg-glass)', border: '1px solid var(--border-color)' }}>
                <Table<ProductionRun>
                    columns={columns}
                    dataSource={historyRuns}
                    rowKey="run_id"
                    loading={isLoading}
                    expandable={{
                        expandedRowRender: (record) => (
                            <div style={{ padding: '8px 48px' }}>
                                <Text type="secondary">上下文數據 (Context JSON):</Text>
                                <pre style={{ 
                                    background: 'rgba(0,0,0,0.2)', 
                                    padding: '12px', 
                                    borderRadius: '4px',
                                    marginTop: '8px',
                                    fontSize: '12px'
                                }}>
                                    {JSON.stringify(record.context || {}, null, 2)}
                                </pre>
                            </div>
                        ),
                        rowExpandable: (record) => !!record.context && Object.keys(record.context).length > 0,
                    }}
                    pagination={{
                        defaultPageSize: 10,
                        showSizeChanger: true,
                        showTotal: (total) => `共 ${total} 筆紀錄`,
                    }}
                />
            </Card>
        </div>
    );
}
