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
    ResponsiveContainer, XAxis, YAxis,
    CartesianGrid, Tooltip, Legend, Scatter, Cell,
    ComposedChart, Line, Area
} from 'recharts';
import { useProductionStore } from '../store/productionStore';
import type { ProductionRun } from '../store/productionStore';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

/**
 * 下鑽詳情面板組件 - 單一圖表 RCA 整合版
 */
function RunDetailPanel({ runId }: { runId: number }) {
    const { runDataCache, fetchRunData } = useProductionStore();
    const data = runDataCache[runId];

    const [visibleMetrics, setVisibleMetrics] = useState<string[]>([]);

    useEffect(() => {
        fetchRunData(runId);
    }, [runId, fetchRunData]);

    const getMetricLabel = (t: any) => t.unit ? `${t.display_name} (${t.unit})` : t.display_name;

    const hasData = !!data;
    const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2'];

    // --- 1. 資料處理 (單一時間軸) ---
    const timelineData = useMemo(() => {
        if (!data) return [];

        const allTimestamps = new Set<number>();
        data.telemetry.forEach(t => allTimestamps.add(new Date(t.time).getTime()));
        data.status.forEach(s => allTimestamps.add(new Date(s.time).getTime()));
        data.alarms.forEach(a => allTimestamps.add(new Date(a.time).getTime()));
        data.events.forEach(e => allTimestamps.add(new Date(e.time).getTime()));

        const sortedTicks = Array.from(allTimestamps).sort((a, b) => a - b);

        const stateMap: Record<string, number> = {
            'RUN': 3, 'PRD': 3, 'PROD': 3,
            'IDLE': 2, 'SBY': 2, 'STANDBY': 2,
            'DOWN': 1, 'UDT': 1, 'FAIL': 1,
            'OFF': 0
        };

        let lastStatusValue = 0;
        let lastStatusCode = 'N/A';
        let lastStatusSubCode = '';
        const result = [];

        const telByTime: Record<number, any[]> = {};
        data.telemetry.forEach(t => {
            const time = new Date(t.time).getTime();
            if (!telByTime[time]) telByTime[time] = [];
            telByTime[time].push(t);
        });

        const statByTime: Record<number, any> = {};
        data.status.forEach(s => {
            statByTime[new Date(s.time).getTime()] = s;
        });

        const alarmByTime: Record<number, any[]> = {};
        data.alarms.forEach(a => {
            const time = new Date(a.time).getTime();
            if (!alarmByTime[time]) alarmByTime[time] = [];
            alarmByTime[time].push(a);
        });

        const eventByTime: Record<number, any[]> = {};
        data.events.forEach(e => {
            const time = new Date(e.time).getTime();
            if (!eventByTime[time]) eventByTime[time] = [];
            eventByTime[time].push(e);
        });

        for (const tick of sortedTicks) {
            if (statByTime[tick]) {
                lastStatusCode = statByTime[tick].state_code;
                lastStatusSubCode = statByTime[tick].sub_state_code || '';
                lastStatusValue = stateMap[lastStatusCode.toUpperCase()] || 0;
            }

            const point: any = {
                timestamp: tick,
                statusValue: lastStatusValue,
                statusCode: lastStatusCode,
                statusSubCode: lastStatusSubCode,
                alarmCount: alarmByTime[tick]?.length || 0,
                alarms: alarmByTime[tick] || [],
                eventCount: eventByTime[tick]?.length || 0,
                events: eventByTime[tick] || []
            };

            if (telByTime[tick]) {
                telByTime[tick].forEach(t => {
                    const label = getMetricLabel(t);
                    point[label] = t.value;
                });
            }
            result.push(point);
        }
        return result;
    }, [data]);

    const telemetrySection = useMemo(() => {
        if (!data?.telemetry.length) return <Empty description="無遙測數據" />;

        const telLabels = Array.from(new Set(data.telemetry.map(getMetricLabel)));
        const allOptions = [...telLabels, '🚨 警報', '📦 生產事件', '📊 設備狀態'];

        if (visibleMetrics.length === 0) {
            setVisibleMetrics(allOptions);
        }

        const renderTooltip = ({ active, payload }: any) => {
            if (active && payload && payload.length) {
                const d = payload[0].payload;
                return (
                    <div style={{
                        background: '#1f1f1f',
                        padding: '12px',
                        border: '1px solid #444',
                        borderRadius: 4,
                        boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                        maxWidth: 320,
                        pointerEvents: 'none'
                    }}>
                        <Text strong style={{ color: '#aaa', display: 'block', marginBottom: 8, borderBottom: '1px solid #333', paddingBottom: 4 }}>
                            {new Date(d.timestamp).toLocaleString()}
                        </Text>

                        <div style={{ marginBottom: 8 }}>
                            <Badge
                                status={d.statusValue === 3 ? 'success' : d.statusValue === 1 ? 'error' : 'warning'}
                                text={<Text strong style={{ color: '#fff' }}>狀態: {d.statusCode}{d.statusSubCode ? `/${d.statusSubCode}` : ''}</Text>}
                            />
                        </div>

                        {d.alarmCount > 0 && (
                            <div style={{ marginBottom: 8 }}>
                                <Text type="danger" strong>🚨 警報 ({d.alarmCount}):</Text>
                                {d.alarms.map((a: any, i: number) => (
                                    <div key={i} style={{ fontSize: 10, color: '#ff7875', marginLeft: 8 }}>
                                        • {a.alarm_code}{a.sub_alarm_code ? `/${a.sub_alarm_code}` : ''}: {a.message}
                                    </div>
                                ))}
                            </div>
                        )}

                        {d.eventCount > 0 && (
                            <div style={{ marginBottom: 8 }}>
                                <Text style={{ color: '#40a9ff' }} strong>📦 事件 ({d.eventCount}):</Text>
                                {d.events.map((e: any, i: number) => (
                                    <div key={i} style={{ fontSize: 10, color: '#91d5ff', marginLeft: 8 }}>
                                        • {e.event_code}{e.sub_event_code ? `/${e.sub_event_code}` : ''} ({e.result || 'N/A'})
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* 數值摘要 */}
                        <div style={{ borderTop: '1px solid #333', paddingTop: 4, marginTop: 4 }}>
                            {telLabels.map((l, i) => d[l] !== undefined && (
                                <div key={i} style={{ fontSize: 11, color: colors[i % colors.length] }}>
                                    {l}: <Text strong style={{ color: '#fff' }}>{d[l]}</Text>
                                </div>
                            ))}
                        </div>
                    </div>
                );
            }
            return null;
        };

        return (
            <Row gutter={[0, 16]}>
                <Col span={24}>
                    <Card size="small" style={{ marginBottom: 12, background: 'rgba(255,255,255,0.02)' }}>
                        <Space split={<Text type="secondary">|</Text>} wrap>
                            <Text strong>顯示指標:</Text>
                            <Checkbox.Group
                                options={allOptions}
                                value={visibleMetrics}
                                onChange={(vals) => setVisibleMetrics(vals as string[])}
                            />
                        </Space>
                    </Card>
                </Col>

                <Col span={24} style={{ height: 450 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart
                            data={timelineData}
                            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis
                                dataKey="timestamp"
                                type="number"
                                domain={['dataMin', 'dataMax']}
                                stroke="rgba(255,255,255,0.4)"
                                fontSize={10}
                                tickFormatter={(ts) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            />
                            {/* 主 Y 軸：遙測數值 */}
                            <YAxis
                                yAxisId="left"
                                stroke="rgba(255,255,255,0.4)"
                                fontSize={10}
                            />
                            {/* 隱藏的副 Y 軸：給狀態條使用 */}
                            <YAxis yAxisId="status" hide domain={[0, 40]} />

                            <Tooltip content={renderTooltip} />
                            <Legend verticalAlign="top" height={36} />

                            {/* 1. 狀態條 (底層色塊) - 始終顯示在最下方 */}
                            {visibleMetrics.includes('📊 設備狀態') && (
                                <Area
                                    yAxisId="status"
                                    type="stepAfter"
                                    dataKey="statusValue"
                                    stroke="none"
                                    fillOpacity={0.3}
                                    fill="#52c41a"
                                    isAnimationActive={false}
                                    name=" 設備狀態"
                                />
                            )}

                            {/* 2. 警報標記點 */}
                            {visibleMetrics.includes('🚨 警報') && (
                                <Scatter
                                    yAxisId="status"
                                    name=" 警報"
                                    dataKey="alarmCount"
                                    fill="#ff4d4f"
                                >
                                    {timelineData.map((entry, index) => (
                                        <Cell
                                            key={`cell-a-${index}`}
                                            fill={entry.alarmCount > 0 ? '#ff4d4f' : 'transparent'}
                                        />
                                    ))}
                                </Scatter>
                            )}

                            {/* 3. 事件標記點 */}
                            {visibleMetrics.includes('📦 生產事件') && (
                                <Scatter
                                    yAxisId="status"
                                    name=" 生產事件"
                                    dataKey="eventCount"
                                    fill="#40a9ff"
                                >
                                    {timelineData.map((entry, index) => (
                                        <Cell
                                            key={`cell-e-${index}`}
                                            fill={entry.eventCount > 0 ? '#40a9ff' : 'transparent'}
                                        />
                                    ))}
                                </Scatter>
                            )}

                            {/* 4. 遙測曲線 */}
                            {telLabels.filter(m => visibleMetrics.includes(m)).map((m, idx) => (
                                <Line
                                    yAxisId="left"
                                    key={m}
                                    type="monotone"
                                    dataKey={m}
                                    stroke={colors[idx % colors.length]}
                                    strokeWidth={2}
                                    dot={false}
                                    connectNulls
                                    isAnimationActive={false}
                                />
                            ))}
                        </ComposedChart>
                    </ResponsiveContainer>
                </Col>
                <Col span={24}>
                    <div style={{ textAlign: 'center', fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>
                        ※ 圖表底部淺綠色區塊代表設備 RUN 狀態，點位代表離散事件/警報。
                    </div>
                </Col>
            </Row>
        );
    }, [timelineData, visibleMetrics, colors, data]);

    // --- 其餘分頁 (保持不變) ---
    const measurementSection = useMemo(() => {
        if (!data?.measurements.length) return <Empty description="無品檢數據" />;
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
                        <ComposedChart data={chartData}>
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
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
                <Table size="small" dataSource={data.measurements} pagination={{ pageSize: 5 }} rowKey={(r) => `${r.time}-${r.tag_id}`}
                    columns={[
                        { title: '檢驗時間', dataIndex: 'time', render: (t) => new Date(t).toLocaleString(), width: 170 },
                        { title: '製程步序 (Step)', dataIndex: 'step_id', render: (s) => s || '-' },
                        { title: '樣本 ID', dataIndex: 'sample_id', render: (s) => <Text strong>{s}</Text> },
                        { title: '結果', dataIndex: 'result', render: (res) => <Tag color={res?.toLowerCase() === 'fail' ? 'red' : 'green'}>{res?.toUpperCase() || 'PASS'}</Tag> },
                        { title: '量測值', dataIndex: 'value', render: (v, r) => <Text strong>{v} {r.unit}</Text> },
                    ]}
                />
            </Space>
        );
    }, [data?.measurements]);

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
                                        <Statistic title={key.toUpperCase()} value={val as number} suffix={unit || ''} precision={2} valueStyle={{ fontSize: '16px' }} />
                                    </Col>
                                );
                            })}
                        </Row>
                    </Card>
                </Col>
            )) : <Empty description="無聚合指標" />}
        </Row>
    );

    if (!hasData) return <div style={{ padding: 40, textAlign: 'center' }}><Spin tip="解析批次大數據中..." /></div>;

    const tabItems = [
        { key: 'trends', label: <span style={{ fontSize: 12 }}><LineChartOutlined /> RCA 同步診斷</span>, children: telemetrySection },
        { key: 'quality', label: <span style={{ fontSize: 12 }}><CheckCircleOutlined /> 品質檢驗</span>, children: measurementSection },
        { key: 'metrics', label: <span style={{ fontSize: 12 }}><DashboardOutlined /> 關鍵指標</span>, children: metricsSection },
        { key: 'status', label: <span style={{ fontSize: 12 }}><HistoryOutlined /> 狀態歷史</span>, children: statusSection },
        { key: 'alarms', label: <span style={{ fontSize: 12 }}><Badge count={data.alarms.length} size="small" offset={[10, 0]}><span style={{ fontSize: 12 }}>🚨 警報紀錄</span></Badge></span>, children: alarmSection },
        { key: 'events', label: <span style={{ fontSize: 12 }}><UnorderedListOutlined /> 生產事件</span>, children: eventSection },
    ];

    return (
        <ConfigProvider theme={{ token: { fontSize: 12 }, components: { Table: { fontSize: 12 }, Tabs: { titleFontSize: 12 } } }}>
            <div style={{ padding: '12px 20px', background: 'rgba(0,0,0,0.15)', borderRadius: '8px' }}>
                <Tabs defaultActiveKey="trends" items={tabItems} size="small" />
            </div>
        </ConfigProvider>
    );
}

// --- Status/Alarm/Event Section Tables (保持簡潔) ---
const statusSection = (data: any) => (
    <Table size="small" dataSource={data.status} pagination={{ pageSize: 10 }} rowKey={(r: any) => `${r.time}-${r.tag_id}`}
        columns={[
            { title: '時間', dataIndex: 'time', render: (t) => new Date(t).toLocaleString(), width: 170 },
            { title: '狀態 (State)', dataIndex: 'state_code', render: (c) => <Tag color="orange">{c}</Tag> },
            { title: '子狀態', dataIndex: 'sub_state_code' },
            { title: '模式', dataIndex: 'mode' },
        ]}
    />
);

const alarmSection = (data: any) => (
    <Table size="small" dataSource={data.alarms} pagination={{ pageSize: 10 }} rowKey={(r: any) => `${r.time}-${r.alarm_id}`}
        columns={[
            { title: '時間', dataIndex: 'time', render: (t) => new Date(t).toLocaleString(), width: 170 },
            { title: '代碼', dataIndex: 'alarm_code' },
            { title: '嚴重度', dataIndex: 'severity', render: (s) => <Tag color="red">{s}</Tag> },
            { title: '訊息', dataIndex: 'message', ellipsis: true },
            { title: '狀態', dataIndex: 'alarm_status' },
        ]}
    />
);

const eventSection = (data: any) => (
    <Table size="small" dataSource={data.events} pagination={{ pageSize: 10 }} rowKey={(r: any) => `${r.time}-${r.event_id}`}
        columns={[
            { title: '時間', dataIndex: 'time', render: (t) => new Date(t).toLocaleString(), width: 170 },
            { title: '事件代碼', dataIndex: 'event_code', render: (c) => <Text strong>{c}</Text> },
            { title: '子代碼', dataIndex: 'sub_event_code' },
            { title: '結果', dataIndex: 'result', render: (r) => r ? <Tag>{r}</Tag> : '-' },
        ]}
    />
);

export default function ProductionRunHistory() {
    const [form] = Form.useForm();
    const { historyRuns, isLoading, searchHistoryRuns } = useProductionStore();

    useEffect(() => { searchHistoryRuns({}); }, [searchHistoryRuns]);

    const handleSearch = async () => {
        const values = await form.validateFields();
        const params: any = { ...values };
        if (values.timeRange) {
            params.start_time = values.timeRange[0].toISOString();
            params.end_time = values.timeRange[1].toISOString();
        }
        searchHistoryRuns(params);
    };

    const columns = [
        { title: 'Lot ID', dataIndex: 'lot_id', render: (t: string) => <Text strong>{t}</Text> },
        { title: '設備路徑 (Equipment)', dataIndex: 'equipment_path', render: (t: string) => <Text code>{t}</Text> },
        { title: 'Step_id', dataIndex: 'step_id', render: (t: string) => t || '-' },
        { title: 'Recipe', dataIndex: 'recipe_id', render: (t: string) => t || '-' },
        { title: '狀態', dataIndex: 'status', render: (s: string) => <Tag color={s === 'running' ? 'green' : 'blue'}>{s}</Tag> },
        { title: '開始時間', dataIndex: 'start_time', render: (t: string) => new Date(t).toLocaleString() },
        { title: '結束時間', dataIndex: 'end_time', render: (t: string) => t ? new Date(t).toLocaleString() : '-' },
        { title: '詳情 (Details)', dataIndex: 'context', render: (c: any) => c ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(c)}</Text> : '-' },
    ];

    return (
        <div style={{ padding: '24px' }}>
            <Title level={3}><HistoryOutlined /> 生產批次歷史記錄</Title>
            <Card style={{ marginBottom: 24 }}>
                <Form form={form} layout="inline" onFinish={handleSearch}>
                    <Form.Item name="equipment_path" label="設備"><Input /></Form.Item>
                    <Form.Item name="lot_id" label="Lot"><Input /></Form.Item>
                    <Form.Item name="timeRange" label="時間"><RangePicker showTime /></Form.Item>
                    <Button type="primary" htmlType="submit" icon={<SearchOutlined />} loading={isLoading}>查詢</Button>
                    <Button onClick={() => { form.resetFields(); searchHistoryRuns({}); }} style={{ marginLeft: 8 }}>重設</Button>
                </Form>
            </Card>
            <Card>
                <Table<ProductionRun> columns={columns} dataSource={historyRuns} rowKey="run_id" loading={isLoading}
                    expandable={{ expandedRowRender: (record) => <RunDetailPanel runId={record.run_id} /> }}
                />
            </Card>
        </div>
    );
}
