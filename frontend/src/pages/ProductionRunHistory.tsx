import { useEffect, useState, useMemo } from 'react';
import { Table, Form, Input, Button, DatePicker, Card, Tag, Space, Typography, Empty, Spin, Badge, Tabs, Checkbox, Row, Col, Statistic } from 'antd';
import { 
    SearchOutlined, ReloadOutlined, HistoryOutlined, 
    LineChartOutlined, CheckCircleOutlined, 
    DashboardOutlined, UnorderedListOutlined 
} from '@ant-design/icons';
import { 
    ResponsiveContainer, LineChart, Line, XAxis, YAxis, 
    CartesianGrid, Tooltip, Legend, ScatterChart, Scatter, Cell, ReferenceLine 
} from 'recharts';
import { useProductionStore } from '../store/productionStore';
import type { ProductionRun } from '../store/productionStore';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

/**
 * 下鑽詳情面板組件 (多維度互動版)
 */
function RunDetailPanel({ runId }: { runId: number }) {
    const { runDataCache, fetchRunData } = useProductionStore();
    const data = runDataCache[runId];
    
    // 控製圖表顯示的 Series
    const [visibleMetrics, setVisibleMetrics] = useState<string[]>([]);

    useEffect(() => {
        fetchRunData(runId);
    }, [runId, fetchRunData]);

    // 當數據載入時，預設顯示所有指標
    useEffect(() => {
        if (data?.telemetry && visibleMetrics.length === 0) {
            const allNames = Array.from(new Set(data.telemetry.map(t => t.display_name)));
            setVisibleMetrics(allNames);
        }
    }, [data, visibleMetrics.length]);

    const hasData = !!data;
    const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2'];

    // --- 1. 遙測趨勢處理 ---
    const telemetrySection = useMemo(() => {
        if (!data?.telemetry.length) return <Empty description="無遙測數據" />;
        
        const pivoitedMap: Record<string, any> = {};
        const metricNames = new Set<string>();

        data.telemetry.forEach(t => {
            const timeKey = new Date(t.time).toLocaleTimeString();
            if (!pivoitedMap[timeKey]) pivoitedMap[timeKey] = { time: timeKey };
            pivoitedMap[timeKey][t.display_name] = t.value;
            metricNames.add(t.display_name);
        });

        const chartData = Object.values(pivoitedMap);
        const metrics = Array.from(metricNames);

        return (
            <Row gutter={[24, 24]}>
                <Col span={24}>
                    <Card size="small" title="顯示選項 (互動圖例)" style={{ marginBottom: 16 }}>
                        <Checkbox.Group 
                            options={metrics} 
                            value={visibleMetrics} 
                            onChange={(vals) => setVisibleMetrics(vals as string[])} 
                        />
                        <Text type="secondary" style={{ marginLeft: 16, fontSize: '12px' }}>
                            * 勾選不同指標可調整 Y 軸縮放效果
                        </Text>
                    </Card>
                </Col>
                <Col span={24} style={{ height: 400 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis dataKey="time" stroke="rgba(255,255,255,0.4)" fontSize={11} />
                            <YAxis stroke="rgba(255,255,255,0.4)" fontSize={11} />
                            <Tooltip contentStyle={{ background: '#141414', border: '1px solid #333' }} />
                            <Legend />
                            {metrics.filter(m => visibleMetrics.includes(m)).map((m, idx) => (
                                <Line 
                                    key={m}
                                    type="monotone" 
                                    dataKey={m} 
                                    stroke={colors[idx % colors.length]} 
                                    strokeWidth={2}
                                    dot={false}
                                    connectNulls
                                />
                            ))}
                        </LineChart>
                    </ResponsiveContainer>
                </Col>
            </Row>
        );
    }, [data?.telemetry, visibleMetrics]);

    // --- 2. 品質測量 (Measurements) ---
    const measurementSection = useMemo(() => {
        if (!data?.measurements.length) return <Empty description="無品檢數據" />;
        
        const chartData = data.measurements.map(m => ({
            time: new Date(m.time).toLocaleTimeString(),
            value: m.value,
            result: m.result,
            usl: m.spec_upper,
            lsl: m.spec_lower
        }));

        return (
            <div style={{ height: 350 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="time" fontSize={11} />
                        <YAxis domain={['auto', 'auto']} fontSize={11} />
                        <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                        <ReferenceLine y={chartData[0]?.usl} label="USL" stroke="red" strokeDasharray="3 3" />
                        <ReferenceLine y={chartData[0]?.lsl} label="LSL" stroke="red" strokeDasharray="3 3" />
                        <Scatter name="量測值" data={chartData} fill="#8884d8">
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.result === 'oos' ? '#ff4d4f' : '#52c41a'} />
                            ))}
                        </Scatter>
                    </ScatterChart>
                </ResponsiveContainer>
            </div>
        );
    }, [data?.measurements]);

    // --- 3. 指標概覽 (Metrics) ---
    const metricsSection = (
        <Row gutter={16}>
            {data?.metrics && data.metrics.length > 0 ? data.metrics.map((m, idx) => (
                <Col span={6} key={idx}>
                    <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.03)' }}>
                        <Statistic 
                            title={m.metric_code} 
                            value={Object.values(m.values)[0] as number} 
                            suffix={m.unit || ''}
                            precision={2}
                        />
                    </Card>
                </Col>
            )) : <Empty description="無聚合指標" />}
        </Row>
    );

    if (!hasData) return <div style={{ padding: 40, textAlign: 'center' }}><Spin tip="解析批次大數據中..." /></div>;

    const tabItems = [
        { key: 'trends', label: <span><LineChartOutlined /> 趨勢分析</span>, children: telemetrySection },
        { key: 'quality', label: <span><CheckCircleOutlined /> 品質檢驗</span>, children: measurementSection },
        { key: 'metrics', label: <span><DashboardOutlined /> 關鍵指標</span>, children: metricsSection },
        { key: 'logs', label: <span><UnorderedListOutlined /> 事件日誌</span>, children: (
            <div style={{ maxHeight: 400, overflow: 'auto' }}>
                <Title level={5}>警報與生產事件</Title>
                {[...data.alarms, ...data.events].sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime()).map((item, i) => (
                    <div key={i} style={{ padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <Space>
                            <Tag color={item.severity ? 'red' : 'blue'}>{item.severity ? 'ALARM' : 'EVENT'}</Tag>
                            <Text strong>{item.message || item.event_code}</Text>
                            <Text type="secondary" style={{ fontSize: '12px' }}>{new Date(item.time).toLocaleString()}</Text>
                        </Space>
                    </div>
                ))}
            </div>
        )},
    ];

    return (
        <div style={{ padding: '16px 24px', background: 'rgba(0,0,0,0.15)', borderRadius: '8px' }}>
            <Tabs defaultActiveKey="trends" items={tabItems} />
        </div>
    );
}

export default function ProductionRunHistory() {
    const [form] = Form.useForm();
    const { historyRuns, isLoading, searchHistoryRuns } = useProductionStore();

    useEffect(() => {
        searchHistoryRuns({});
    }, [searchHistoryRuns]);

    const handleSearch = async () => {
        const values = await form.validateFields();
        const params: Record<string, any> = {};

        if (values.equipment_path) params.equipment_path = values.equipment_path;
        if (values.lot_id) params.lot_id = values.lot_id;

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
                <Tag color={status.toLowerCase() === 'running' ? 'green' : status.toLowerCase() === 'completed' ? 'blue' : 'default'}>
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
                        expandedRowRender: (record) => <RunDetailPanel runId={record.run_id} />,
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
