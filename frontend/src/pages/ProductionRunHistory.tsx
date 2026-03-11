import { useEffect, useState, useMemo } from 'react';
import { 
    Table, Form, Input, Button, DatePicker, Card, Tag, Space, 
    Typography, Empty, Spin, Badge, Tabs, Checkbox, Row, Col, 
    Statistic, ConfigProvider 
} from 'antd';
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

    // Helper to format labels with units
    const getMetricLabel = (t: any) => t.unit ? `${t.display_name} (${t.unit})` : t.display_name;

    // 當數據載入時，預設顯示所有指標
    useEffect(() => {
        if (data?.telemetry && visibleMetrics.length === 0) {
            const allLabels = Array.from(new Set(data.telemetry.map(getMetricLabel)));
            setVisibleMetrics(allLabels);
        }
    }, [data?.telemetry, visibleMetrics.length]);

    const hasData = !!data;
    const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2'];

    // --- 1. 遙測趨勢處理 ---
    const telemetrySection = useMemo(() => {
        if (!data?.telemetry.length) return <Empty description="無遙測數據" />;
        
        const pivoitedMap: Record<string, any> = {};
        const metricLabels = new Set<string>();

        // Reverse data for chart: oldest to newest
        [...data.telemetry].reverse().forEach(t => {
            const timeKey = new Date(t.time).toLocaleTimeString();
            if (!pivoitedMap[timeKey]) pivoitedMap[timeKey] = { time: timeKey };
            const label = getMetricLabel(t);
            pivoitedMap[timeKey][label] = t.value;
            metricLabels.add(label);
        });

        const chartData = Object.values(pivoitedMap);
        const metrics = Array.from(metricLabels);

        return (
            <Row gutter={[24, 24]}>
                <Col span={24}>
                    <Card size="small" title="顯示選項 (互動圖例)" style={{ marginBottom: 16 }}>
                        <Checkbox.Group 
                            options={metrics} 
                            value={visibleMetrics} 
                            onChange={(vals) => setVisibleMetrics(vals as string[])} 
                        />
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
        
        // Reverse for chart: oldest to newest
        const chartData = [...data.measurements].reverse().map(m => ({
            time: new Date(m.time).toLocaleTimeString(),
            fullTime: new Date(m.time).toLocaleString(),
            value: m.value,
            result: m.result,
            usl: m.spec_upper,
            lsl: m.spec_lower,
            unit: m.unit || '',
            sample_id: m.sample_id,
            sample_position: m.sample_position
        }));

        return (
            <Space direction="vertical" style={{ width: '100%' }} size="large">
                <div style={{ height: 300 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ScatterChart>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} />
                            <XAxis dataKey="time" fontSize={11} />
                            <YAxis domain={['auto', 'auto']} fontSize={11} label={{ value: chartData[0]?.unit, angle: -90, position: 'insideLeft' }} />
                            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                            {chartData[0]?.usl && <ReferenceLine y={chartData[0].usl} label="USL" stroke="#ff4d4f" strokeDasharray="3 3" />}
                            {chartData[0]?.lsl && <ReferenceLine y={chartData[0].lsl} label="LSL" stroke="#ff4d4f" strokeDasharray="3 3" />}
                            <Scatter name="量測值" data={chartData} fill="#8884d8">
                                {chartData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.result?.toLowerCase() === 'fail' ? '#ff4d4f' : '#52c41a'} />
                                ))}
                            </Scatter>
                        </ScatterChart>
                    </ResponsiveContainer>
                </div>
                <Table 
                    size="small"
                    dataSource={data.measurements}
                    pagination={{ pageSize: 5 }}
                    rowKey={(record) => `${record.time}-${record.tag_id}`}
                    columns={[
                        { 
                            title: '檢驗時間', 
                            dataIndex: 'time', 
                            render: (t) => new Date(t).toLocaleString(), 
                            width: 170,
                            sorter: (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
                            defaultSortOrder: 'descend'
                        },
                        { title: '製程步序 (Step)', dataIndex: 'step_id', render: (s) => s || '-', sorter: (a, b) => (a.step_id || '').localeCompare(b.step_id || '') },
                        { title: '樣本 ID', dataIndex: 'sample_id', render: (s) => <Text strong>{s}</Text>, sorter: (a, b) => (a.sample_id || '').localeCompare(b.sample_id || '') },
                        { title: '位置', dataIndex: 'sample_position', sorter: (a, b) => (a.sample_position || '').localeCompare(b.sample_position || '') },
                        { 
                            title: '量測值', 
                            dataIndex: 'value', 
                            render: (v, r) => <Text strong>{v} {r.unit}</Text>,
                            sorter: (a, b) => (a.value || 0) - (b.value || 0)
                        },
                        { title: '目標值', dataIndex: 'target_value', sorter: (a, b) => (a.target_value || 0) - (b.target_value || 0) },
                        { title: '規格 (LSL/USL)', render: (_, r) => <Text type="secondary">{r.spec_lower || '-'} / {r.spec_upper || '-'}</Text> },
                        { 
                            title: '結果', 
                            dataIndex: 'result', 
                            render: (res) => (
                                <Tag color={res?.toLowerCase() === 'fail' ? 'red' : 'green'} style={{ fontSize: 10 }}>{res?.toUpperCase() || 'PASS'}</Tag>
                            ),
                            sorter: (a, b) => (a.result || '').localeCompare(b.result || '')
                        },
                        { title: '檢驗員', dataIndex: 'inspector', sorter: (a, b) => (a.inspector || '').localeCompare(b.inspector || '') },
                        { title: 'Context', dataIndex: 'context', render: (c) => c ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(c)}</Text> : '-' },
                        { title: '詳情', dataIndex: 'details', render: (d) => d ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(d)}</Text> : '-' },
                    ]}
                />
            </Space>
        );
    }, [data?.measurements]);

    // --- 3. 指標概覽 (Metrics) ---
    const metricsSection = (
        <Row gutter={[16, 16]}>
            {data?.metrics && data.metrics.length > 0 ? data.metrics.map((m, mIdx) => (
                <Col span={24} key={mIdx}>
                    <Card size="small" title={<Text strong>{m.metric_code} <Tag style={{ marginLeft: 8 }}>{m.metric_category}</Tag></Text>}>
                        <Row gutter={16}>
                            {Object.entries(m.values).map(([key, val], vIdx) => {
                                const unit = (m.unit && typeof m.unit === 'object') ? (m.unit as any)[key] : m.unit;
                                return (
                                    <Col span={6} key={vIdx}>
                                        <Statistic 
                                            title={key.toUpperCase()} 
                                            value={val as number} 
                                            suffix={unit || ''}
                                            precision={2}
                                            valueStyle={{ fontSize: '16px' }}
                                        />
                                    </Col>
                                );
                            })}
                        </Row>
                        {m.details && (
                            <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                                <Text type="secondary" style={{ fontSize: 10 }}>Details: {JSON.stringify(m.details)}</Text>
                            </div>
                        )}
                    </Card>
                </Col>
            )) : <Empty description="無聚合指標" />}
        </Row>
    );

    // --- 4. 狀態歷史 (Status) ---
    const statusSection = useMemo(() => {
        if (!data?.status.length) return <Empty description="無狀態數據" />;
        return (
            <Table 
                size="small"
                dataSource={data.status}
                pagination={{ pageSize: 10 }}
                rowKey={(record) => `${record.time}-${record.tag_id}`}
                columns={[
                    { 
                        title: '時間', 
                        dataIndex: 'time', 
                        render: (t) => new Date(t).toLocaleString(), 
                        width: 170,
                        sorter: (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
                        defaultSortOrder: 'descend'
                    },
                    { title: '狀態碼 (State)', dataIndex: 'state_code', render: (c) => <Tag color="orange" style={{ fontSize: 10 }}>{c}</Tag>, sorter: (a, b) => a.state_code.localeCompare(b.state_code) },
                    { title: '子狀態 (Sub)', dataIndex: 'sub_state_code', render: (c) => c || '-', sorter: (a, b) => (a.sub_state_code || '').localeCompare(b.sub_state_code || '') },
                    { title: '模式 (Mode)', dataIndex: 'mode', render: (m) => <Tag color="blue" style={{ fontSize: 10 }}>{m}</Tag>, sorter: (a, b) => (a.mode || '').localeCompare(b.mode || '') },
                    { title: '詳情 (Details)', dataIndex: 'details', render: (d) => d ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(d)}</Text> : '-' },
                ]}
            />
        );
    }, [data?.status]);

    // --- 5. 警報紀錄 (Alarms) ---
    const alarmSection = useMemo(() => {
        if (!data?.alarms.length) return <Empty description="無警報紀錄" />;
        return (
            <Table 
                size="small"
                dataSource={[...data.alarms]}
                pagination={{ pageSize: 10 }}
                rowKey={(record) => `${record.time}-${record.alarm_id}`}
                columns={[
                    { 
                        title: '時間', 
                        dataIndex: 'time', 
                        render: (t) => new Date(t).toLocaleString(), 
                        width: 170,
                        sorter: (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
                        defaultSortOrder: 'descend'
                    },
                    { title: 'ID', dataIndex: 'alarm_id', width: 100, sorter: (a, b) => a.alarm_id.localeCompare(b.alarm_id) },
                    { title: '代碼', dataIndex: 'alarm_code', sorter: (a, b) => a.alarm_code.localeCompare(b.alarm_code) },
                    { title: '嚴重度', dataIndex: 'severity', render: (s) => <Tag color="red" style={{ fontSize: 10 }}>{s}</Tag>, sorter: (a, b) => a.severity.localeCompare(b.severity) },
                    { title: '訊息', dataIndex: 'message', ellipsis: true },
                    { 
                        title: '狀態', 
                        dataIndex: 'alarm_status', 
                        render: (st) => <Badge status={st === 'active' ? 'error' : 'success'} text={<span style={{ fontSize: 12 }}>{st}</span>} />,
                        sorter: (a, b) => a.alarm_status.localeCompare(b.alarm_status)
                    },
                    { title: '數值/閾值', render: (_, r) => r.value !== null ? `${r.value} / ${r.threshold || '-'}` : '-', sorter: (a, b) => (a.value || 0) - (b.value || 0) },
                    { title: '詳情', dataIndex: 'details', render: (d) => d ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(d)}</Text> : '-' },
                ]}
            />
        );
    }, [data?.alarms]);

    // --- 6. 生產事件 (Events) ---
    const eventSection = useMemo(() => {
        if (!data?.events.length) return <Empty description="無事件紀錄" />;
        return (
            <Table 
                size="small"
                dataSource={[...data.events]}
                pagination={{ pageSize: 10 }}
                rowKey={(record) => `${record.time}-${record.event_id}`}
                columns={[
                    { 
                        title: '時間', 
                        dataIndex: 'time', 
                        render: (t) => new Date(t).toLocaleString(), 
                        width: 170,
                        sorter: (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime(),
                        defaultSortOrder: 'descend'
                    },
                    { title: 'ID', dataIndex: 'event_id', width: 100, sorter: (a, b) => a.event_id.localeCompare(b.event_id) },
                    { title: '事件代碼', dataIndex: 'event_code', render: (c) => <Text strong>{c}</Text>, sorter: (a, b) => a.event_code.localeCompare(b.event_code) },
                    { title: '子代碼', dataIndex: 'sub_event_code', sorter: (a, b) => (a.sub_event_code || '').localeCompare(b.sub_event_code || '') },
                    { title: '結果', dataIndex: 'result', render: (r) => r ? <Tag style={{ fontSize: 10 }}>{r}</Tag> : '-', sorter: (a, b) => (a.result || '').localeCompare(b.result || '') },
                    { title: '詳情', dataIndex: 'details', render: (d) => d ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(d)}</Text> : '-' },
                ]}
            />
        );
    }, [data?.events]);

    if (!hasData) return <div style={{ padding: 40, textAlign: 'center' }}><Spin tip="解析批次大數據中..." /></div>;

    const tabItems = [
        { key: 'trends', label: <span style={{ fontSize: 12 }}><LineChartOutlined /> 趨勢分析</span>, children: telemetrySection },
        { key: 'quality', label: <span style={{ fontSize: 12 }}><CheckCircleOutlined /> 品質檢驗</span>, children: measurementSection },
        { key: 'metrics', label: <span style={{ fontSize: 12 }}><DashboardOutlined /> 關鍵指標</span>, children: metricsSection },
        { key: 'status', label: <span style={{ fontSize: 12 }}><HistoryOutlined /> 狀態歷史</span>, children: statusSection },
        { key: 'alarms', label: <span style={{ fontSize: 12 }}><Badge count={data.alarms.length} size="small" offset={[10, 0]}><span style={{ fontSize: 12 }}>🚨 警報紀錄</span></Badge></span>, children: alarmSection },
        { key: 'events', label: <span style={{ fontSize: 12 }}><UnorderedListOutlined /> 生產事件</span>, children: eventSection },
    ];

    return (
        <ConfigProvider
            theme={{
                token: {
                    fontSize: 12,
                    paddingXS: 8,
                    paddingSM: 12,
                },
                components: {
                    Table: {
                        fontSize: 12,
                        cellPaddingBlockSM: 4,
                    },
                    Statistic: {
                        contentFontSize: 16,
                        titleFontSize: 12,
                    },
                    Tabs: {
                        titleFontSize: 12,
                    }
                }
            }}
        >
            <div style={{ 
                padding: '12px 20px', 
                background: 'rgba(0,0,0,0.15)', 
                borderRadius: '8px',
            }}>
                <Tabs defaultActiveKey="trends" items={tabItems} size="small" />
            </div>
        </ConfigProvider>
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
