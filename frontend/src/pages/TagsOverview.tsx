import { useEffect, useState, useCallback, useMemo } from 'react';
import {
    Tree,
    Table,
    Button,
    Card,
    Modal,
    Form,
    Input,
    Select,
    Tag as AntTag,
    Spin,
    Typography,
    Drawer,
    message,
    Empty,
    Space,
    Popconfirm,
    Switch,
    ConfigProvider,
    Badge,
    Row,
    Col
} from 'antd';
import {
    DatabaseOutlined,
    FolderOutlined,
    ApiOutlined,
    LineChartOutlined,
    EditOutlined,
    DeleteOutlined,
    ApartmentOutlined,
    PlusOutlined,
} from '@ant-design/icons';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ScatterChart,
    Scatter,
    Cell,
    ReferenceLine
} from 'recharts';
import type { TreeDataNode } from 'antd';

import { useNamespaceStore } from '../store/namespaceStore';
import { useTagStore } from '../store/tagStore';
import { useSchemaStore } from '../store/schemaStore';
import type { NodeTreeOut, TagOut, TagCreate } from '../types/namespace';
import '../pages/NamespaceEditor.css'; // Reuse layout CSS

const { Title, Text, Paragraph } = Typography;

// Helper to find a node by its full path in the nested tree
function findNodeByPath(nodes: NodeTreeOut[], path: string): NodeTreeOut | null {
    for (const node of nodes) {
        if (node.full_path === path) return node;
        if (node.children?.length) {
            const found = findNodeByPath(node.children, path);
            if (found) return found;
        }
    }
    return null;
}

// Helper to convert tree map
function toTreeData(nodes: NodeTreeOut[]): TreeDataNode[] {
    return nodes.map((node) => ({
        key: node.full_path, // Use full_path as key for easy querying
        title: node.name,
        children: node.children?.length ? toTreeData(node.children) : [],
        isLeaf: !node.children?.length,
        icon: node.node_type === 'topic' ? (
            <ApiOutlined style={{ color: 'var(--color-primary)' }} />
        ) : (
            <FolderOutlined style={{ color: 'var(--color-info)' }} />
        ),
        _raw: node,
    }));
}

export default function TagsOverview() {
    // Stores
    const { treeData, fetchTree, isLoading: isTreeLoading } = useNamespaceStore();
    const { fetchSchemas, getSchemaById } = useSchemaStore();
    const {
        tags,
        currentTagValues,
        isLoading: isTagLoading,
        fetchTagsByNode,
        fetchTagValues,
        createTag,
        updateTag,
        deleteTag
    } = useTagStore();

    // Local state
    const [selectedPath, setSelectedPath] = useState<string | null>(null);
    
    // Derived state
    const selectedNode = useMemo(() => 
        selectedPath ? findNodeByPath(treeData, selectedPath) : null
    , [treeData, selectedPath]);

    const boundSchema = useMemo(() => 
        selectedNode?.schema_id ? getSchemaById(selectedNode.schema_id) : null
    , [selectedNode, getSchemaById]);

    const [recursive, setRecursive] = useState(false);
    const [createModalOpen, setCreateModalOpen] = useState(false);
    const [editingTag, setEditingTag] = useState<TagOut | null>(null);
    const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
    const [activeTag, setActiveTag] = useState<TagOut | null>(null);
    const [form] = Form.useForm();

    // Init tree and schemas
    useEffect(() => {
        fetchTree();
        fetchSchemas();
    }, [fetchTree, fetchSchemas]);

    // Tree select handler
    const handleSelect = useCallback((selectedKeys: React.Key[], _info: any) => {
        if (selectedKeys.length > 0) {
            const path = selectedKeys[0] as string;
            setSelectedPath(path);
            fetchTagsByNode(path, recursive);
        } else {
            setSelectedPath(null);
        }
    }, [fetchTagsByNode, recursive]);

    // Re-fetch when recursive toggle changes
    useEffect(() => {
        if (selectedPath) {
            fetchTagsByNode(selectedPath, recursive);
        }
    }, [recursive, selectedPath, fetchTagsByNode]);

    // Create Tag
    const handleCreateOpen = () => {
        if (!selectedPath) {
            message.warning("請先從左側樹狀圖選擇一個 Topic 節點");
            return;
        }
        form.resetFields();
        form.setFieldsValue({
            asset_path: selectedPath,
            category: 'telemetry',
            data_type: 'float'
        });
        setCreateModalOpen(true);
    };


    // View History
    const handleViewHistory = (tag: TagOut) => {
        setActiveTag(tag);
        fetchTagValues(tag.tag_id, 100);
        setHistoryDrawerOpen(true);
    };

    // Edit Tag
    const handleEditOpen = (tag: TagOut) => {
        setEditingTag(tag);
        form.setFieldsValue({
            asset_path: tag.asset_path,
            display_name: tag.display_name,
            category: tag.category,
            data_point: tag.data_point,
            data_type: tag.data_type,
            unit: tag.unit,
            description: tag.description
        });
        setCreateModalOpen(true);
    };

    const handleDelete = async (tagId: number) => {
        const success = await deleteTag(tagId);
        if (success) {
            message.success('Tag 已移至資源回收桶');
            if (selectedPath) fetchTagsByNode(selectedPath);
        }
    };

    const handleFormSubmit = async () => {
        try {
            const values = await form.validateFields();
            const payload = {
                display_name: values.display_name,
                asset_path: values.asset_path,
                category: values.category,
                data_point: values.data_point || null,
                data_type: values.data_type,
                unit: values.unit || null,
                description: values.description || null
            };

            let success = false;
            if (editingTag) {
                success = await updateTag(editingTag.tag_id, payload);
            } else {
                success = await createTag(payload as TagCreate);
            }

            if (success) {
                message.success(`Tag ${editingTag ? '更新' : '建立'}成功！`);
                setCreateModalOpen(false);
                setEditingTag(null);
                if (selectedPath) fetchTagsByNode(selectedPath);
            }
        } catch (err) {
            // Validation failed
        }
    };

    const antTreeData = toTreeData(treeData);

    const columns = [
        {
            title: 'Tag ID',
            dataIndex: 'tag_id',
            key: 'tag_id',
            width: 80,
        },
        {
            title: '顯示名稱',
            dataIndex: 'display_name',
            key: 'display_name',
            render: (text: string) => <Text strong style={{ color: 'var(--color-primary)' }}>{text}</Text>
        },
        {
            title: '分類 (Category)',
            dataIndex: 'category',
            key: 'category',
            render: (c: string) => (
                <AntTag
                    color={
                        c === 'telemetry' ? 'blue' :
                            c === 'alarm' ? 'red' :
                                c === 'status' ? 'green' :
                                    c === 'event' ? 'purple' :
                                        c === 'measurement' ? 'orange' : 'default'
                    }
                >
                    {c?.toUpperCase() || '-'}
                </AntTag>
            )
        },
        {
            title: 'Data Point',
            dataIndex: 'data_point',
            key: 'data_point',
            render: (dp: string) => dp || <Text type="secondary">-</Text>
        },
        {
            title: '型別',
            dataIndex: 'data_type',
            key: 'data_type',
            render: (t: string) => <AntTag color="blue">{t}</AntTag>
        },
        {
            title: '單位',
            dataIndex: 'unit',
            key: 'unit',
            render: (u: string) => u || '-'
        },
        {
            title: '操作',
            key: 'action',
            render: (_: any, record: TagOut) => (
                <Space>
                    <Button
                        type="link"
                        size="small"
                        icon={<LineChartOutlined />}
                        onClick={() => handleViewHistory(record)}
                    >
                        歷史趨勢
                    </Button>
                    <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => handleEditOpen(record)}
                    />
                    <Popconfirm
                        title="確定要刪除此 Tag 嗎？"
                        description="此操作將進行 Soft Delete，歷史數據將保留。"
                        onConfirm={() => handleDelete(record.tag_id)}
                        okText="確定"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                    >
                        <Button
                            type="text"
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                        />
                    </Popconfirm>
                </Space>
            )
        }
    ];

    const historyColumns = useMemo(() => {
        const base = [
            {
                title: '時間 (Time)',
                dataIndex: 'time',
                key: 'time',
                width: 160,
                render: (t: string) => <span style={{ fontSize: 11 }}>{new Date(t).toLocaleString()}</span>,
                sorter: (a: any, b: any) => new Date(a.time).getTime() - new Date(b.time).getTime(),
                defaultSortOrder: 'descend' as const,
            },
        ];

        const contextCols = [
            { title: 'Lot ID', dataIndex: 'lot_id', key: 'lot_id', width: 100, render: (v: any) => <Text style={{ fontSize: 11 }}>{v || '-'}</Text>, sorter: (a: any, b: any) => (a.lot_id || '').localeCompare(b.lot_id || '') },
            { title: 'Run ID', dataIndex: 'run_id', key: 'run_id', width: 70, render: (v: any) => <Text type="secondary" style={{ fontSize: 11 }}>{v || '-'}</Text>, sorter: (a: any, b: any) => (a.run_id || 0) - (b.run_id || 0) },
        ];

        const category = activeTag?.category?.toLowerCase() || 'telemetry';

        if (category === 'status') {
            return [
                ...base,
                ...contextCols,
                { title: '狀態碼', dataIndex: 'state_code', render: (c: string) => <AntTag color="orange" style={{ fontSize: 10 }}>{c}</AntTag>, sorter: (a: any, b: any) => (a.state_code || '').localeCompare(b.state_code || '') },
                { title: '子狀態', dataIndex: 'sub_state_code', render: (c: string) => c || '-', sorter: (a: any, b: any) => (a.sub_state_code || '').localeCompare(b.sub_state_code || '') },
                { title: '模式', dataIndex: 'mode', render: (m: string) => <AntTag color="blue" style={{ fontSize: 10 }}>{m}</AntTag>, sorter: (a: any, b: any) => (a.mode || '').localeCompare(b.mode || '') },
                { title: '詳情', dataIndex: 'details', render: (d: any) => d ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(d)}</Text> : '-' },
            ];
        }

        if (category === 'alarm') {
            return [
                ...base,
                ...contextCols,
                { title: 'ID', dataIndex: 'alarm_id', width: 80, sorter: (a: any, b: any) => (a.alarm_id || '').localeCompare(b.alarm_id || '') },
                { title: '代碼', dataIndex: 'alarm_code', sorter: (a: any, b: any) => (a.alarm_code || '').localeCompare(b.alarm_code || '') },
                { title: '子代碼', dataIndex: 'sub_alarm_code', sorter: (a: any, b: any) => (a.sub_alarm_code || '').localeCompare(b.sub_alarm_code || '') },
                { title: '嚴重度', dataIndex: 'severity', render: (s: string) => <AntTag color="red" style={{ fontSize: 10 }}>{s}</AntTag>, sorter: (a: any, b: any) => (a.severity || '').localeCompare(b.severity || '') },
                { title: '訊息', dataIndex: 'message', ellipsis: true },
                { title: '狀態', dataIndex: 'alarm_status', render: (st: string) => <Badge status={st === 'active' ? 'error' : 'success'} text={<span style={{ fontSize: 11 }}>{st}</span>} />, sorter: (a: any, b: any) => (a.alarm_status || '').localeCompare(b.alarm_status || '') },
                { title: '數值/閾值', render: (_: any, r: any) => <span style={{ fontSize: 11 }}>{r.value ?? '-'} / {r.threshold ?? '-'}</span>, sorter: (a: any, b: any) => (a.value || 0) - (b.value || 0) },
                { title: '詳情', dataIndex: 'details', render: (d: any) => d ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(d)}</Text> : '-' },
            ];
        }

        if (category === 'event') {
            return [
                ...base,
                ...contextCols,
                { title: 'ID', dataIndex: 'event_id', width: 80, sorter: (a: any, b: any) => (a.event_id || '').localeCompare(b.event_id || '') },
                { title: '事件代碼', dataIndex: 'event_code', render: (c: string) => <Text strong style={{ fontSize: 11 }}>{c}</Text>, sorter: (a: any, b: any) => (a.event_code || '').localeCompare(b.event_code || '') },
                { title: '子代碼', dataIndex: 'sub_event_code', sorter: (a: any, b: any) => (a.sub_event_code || '').localeCompare(b.sub_event_code || '') },
                { title: '結果', dataIndex: 'result', render: (r: string) => r || '-', sorter: (a: any, b: any) => (a.result || '').localeCompare(b.result || '') },
                { title: '詳情', dataIndex: 'details', render: (d: any) => d ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(d)}</Text> : '-' },
            ];
        }

        if (category === 'measurement') {
            return [
                ...base,
                ...contextCols,
                { title: 'Step', dataIndex: 'step_id', width: 80, sorter: (a: any, b: any) => (a.step_id || '').localeCompare(b.step_id || '') },
                { title: '樣本 ID', dataIndex: 'sample_id', render: (s: any) => <Text strong style={{ fontSize: 11 }}>{s}</Text>, sorter: (a: any, b: any) => (a.sample_id || '').localeCompare(b.sample_id || '') },
                { title: '數值', dataIndex: 'value', render: (v: number) => <Text strong style={{ fontSize: 11 }}>{v} {activeTag?.unit}</Text>, sorter: (a: any, b: any) => (a.value || 0) - (b.value || 0) },
                { title: '目標', dataIndex: 'target_value', sorter: (a: any, b: any) => (a.target_value || 0) - (b.target_value || 0) },
                { title: '結果', dataIndex: 'result', render: (res: string) => <AntTag color={res?.toLowerCase() === 'fail' ? 'red' : 'green'} style={{ fontSize: 10 }}>{res || 'PASS'}</AntTag>, sorter: (a: any, b: any) => (a.result || '').localeCompare(b.result || '') },
                { title: '規格', render: (_: any, r: any) => <Text type="secondary" style={{ fontSize: 10 }}>{r.spec_lower || '-'} / {r.spec_upper || '-'}</Text> },
                { title: '檢驗員', dataIndex: 'inspector', sorter: (a: any, b: any) => (a.inspector || '').localeCompare(b.inspector || '') },
                { title: 'Context', dataIndex: 'context', render: (c: any) => c ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(c)}</Text> : '-' },
                { title: '詳情', dataIndex: 'details', render: (d: any) => d ? <Text type="secondary" style={{ fontSize: 10 }}>{JSON.stringify(d)}</Text> : '-' },
            ];
        }

        // Default / Telemetry
        return [
            ...base,
            ...contextCols,
            {
                title: '數值 (Value)',
                dataIndex: 'value',
                key: 'value',
                render: (v: any, record: any) => {
                    const displayVal = v ?? record.value_text ?? (record.value_json ? 'JSON' : null);
                    return <Text strong style={{ fontSize: 11 }}>{displayVal ?? <Text type="secondary">null</Text>}</Text>;
                },
                sorter: (a: any, b: any) => (a.value || 0) - (b.value || 0)
            },
            {
                title: '品質',
                dataIndex: 'quality',
                key: 'quality',
                render: (q: string) => (
                    <AntTag color={q === 'good' ? 'success' : 'warning'} style={{ fontSize: 10 }}>
                        {q}
                    </AntTag>
                ),
                sorter: (a: any, b: any) => (a.quality || '').localeCompare(b.quality || '')
            }
        ];
    }, [activeTag]);

    const renderHistoryContent = () => {
        if (!currentTagValues.length) return <Empty description="無歷史數據" />;

        const category = activeTag?.category?.toLowerCase() || 'telemetry';

        if (category === 'telemetry' || category === 'measurement') {
            const chartData = [...currentTagValues].reverse().map(v => ({
                time: new Date(v.time).toLocaleTimeString(),
                value: v.value,
                usl: (v as any).spec_upper,
                lsl: (v as any).spec_lower,
                result: (v as any).result
            }));

            return (
                <Space direction="vertical" style={{ width: '100%' }} size="large">
                    <div style={{ height: 300, width: '100%', background: 'rgba(255,255,255,0.02)', padding: 16, borderRadius: 8 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            {category === 'telemetry' ? (
                                <LineChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                                    <XAxis dataKey="time" fontSize={10} stroke="rgba(255,255,255,0.3)" />
                                    <YAxis fontSize={10} stroke="rgba(255,255,255,0.3)" unit={activeTag?.unit} />
                                    <Tooltip contentStyle={{ background: '#141414', border: '1px solid #333', fontSize: 11 }} />
                                    <Legend />
                                    <Line type="monotone" dataKey="value" name={activeTag?.display_name} stroke="#1890ff" dot={false} />
                                </LineChart>
                            ) : (
                                <ScatterChart>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="time" fontSize={10} />
                                    <YAxis domain={['auto', 'auto']} fontSize={10} unit={activeTag?.unit} />
                                    <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                                    <Legend />
                                    {chartData[0]?.usl && <ReferenceLine y={chartData[0].usl} label="USL" stroke="red" strokeDasharray="3 3" />}
                                    {chartData[0]?.lsl && <ReferenceLine y={chartData[0].lsl} label="LSL" stroke="red" strokeDasharray="3 3" />}
                                    <Scatter name="量測值" data={chartData}>
                                        {chartData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.result?.toLowerCase() === 'fail' ? '#ff4d4f' : '#52c41a'} />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                            )}
                        </ResponsiveContainer>
                    </div>
                    <Table
                        columns={historyColumns}
                        dataSource={currentTagValues}
                        rowKey="time"
                        pagination={{ pageSize: 10 }}
                        size="small"
                    />
                </Space>
            );
        }

        return (
            <Table
                columns={historyColumns}
                dataSource={currentTagValues}
                rowKey="time"
                pagination={{ pageSize: 20 }}
                size="small"
            />
        );
    };

    return (
        <ConfigProvider
            theme={{
                token: { fontSize: 12 },
                components: { Table: { fontSize: 12 }, Tag: { fontSize: 10 } }
            }}
        >
            <div className="namespace-editor">
                {/* ── Left: Tree Panel ── */}
                <div className="namespace-tree-panel">
                    <div className="namespace-tree-header">
                        <h3><ApartmentOutlined /> Namespace 範圍</h3>
                    </div>
                    <div className="namespace-tree-body">
                        <Spin spinning={isTreeLoading}>
                            {antTreeData.length > 0 ? (
                                <Tree
                                    treeData={antTreeData}
                                    showIcon
                                    defaultExpandAll
                                    onSelect={handleSelect}
                                />
                            ) : (
                                <Empty description="尚無節點資料" style={{ marginTop: 80 }} />
                            )}
                        </Spin>
                    </div>
                </div>

                {/* ── Right: Detail Panel (Tag List) ── */}
                <div className="namespace-detail-panel" style={{ padding: 24, overflow: 'auto' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                        <div>
                            <Title level={2} style={{ margin: 0 }}>
                                <DatabaseOutlined style={{ marginRight: 12, color: 'var(--color-primary)' }} />
                                Tag 總覽
                            </Title>
                            <Paragraph type="secondary" style={{ marginTop: 8 }}>
                                {selectedPath ? `目前檢視範圍：${selectedPath}` : '請從左側選擇 Namespace 節點以檢視關聯的 Tags'}
                            </Paragraph>
                        </div>
                        <Space size="large">
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Text type="secondary">包括子節點</Text>
                                <Switch checked={recursive} onChange={setRecursive} />
                            </div>
                            {selectedPath && (
                                <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateOpen}>
                                    註冊新 Tag
                                </Button>
                            )}
                        </Space>
                    </div>

                    <Card bodyStyle={{ padding: 0 }} bordered={false}>
                        <Table
                            columns={columns}
                            dataSource={tags}
                            rowKey="tag_id"
                            loading={isTagLoading}
                            pagination={{ pageSize: 15 }}
                            locale={{ emptyText: selectedPath ? '此節點下無 Tag' : '請先選擇節點' }}
                        />
                    </Card>
                </div>

                            {/* Create / Edit Tag Modal */}
                            <Modal
                                title={editingTag ? "編輯 Tag 資料點" : "註冊新的 Tag 資料點"}
                                open={createModalOpen}
                                onOk={handleFormSubmit}
                                onCancel={() => {
                                    setCreateModalOpen(false);
                                    setEditingTag(null);
                                }}
                                okText={editingTag ? "更新" : "建立"}
                                cancelText="取消"
                                width={650}
                            >
                                <Form form={form} layout="vertical" style={{ marginTop: 8 }}>
                                    <div style={{ background: 'rgba(255,255,255,0.02)', padding: '12px 16px', borderRadius: 8, marginBottom: 20, border: '1px solid rgba(255,255,255,0.05)' }}>
                                        <Space direction="vertical" size={2}>
                                            <Text type="secondary" style={{ fontSize: 11 }}>Asset Context:</Text>
                                            <Text strong style={{ fontSize: 13 }}><FolderOutlined /> {selectedPath}</Text>
                                            {boundSchema && (
                                                <Text type="success" style={{ fontSize: 11 }}>
                                                    <DatabaseOutlined /> Bound Schema: {boundSchema.schema_name} ({boundSchema.schema_category})
                                                </Text>
                                            )}
                                        </Space>
                                    </div>
                
                                    <Form.Item
                                        label="顯示名稱 (Display Name)"
                                        name="display_name"
                                        rules={[{ required: true, message: '請輸入顯示名稱' }]}
                                    >
                                        <Input placeholder="例如：設備溫度、主軸轉速" />
                                    </Form.Item>
                
                                    <Row gutter={16}>
                                        <Col span={12}>
                                            <Form.Item
                                                label="分類 (Category)"
                                                name="category"
                                                rules={[{ required: true }]}
                                            >
                                                <Select 
                                                    onChange={() => form.setFieldValue('data_point', null)}
                                                >
                                                    <Select.Option value="telemetry">遙測數值 (Telemetry)</Select.Option>
                                                    <Select.Option value="status">設備狀態 (Status)</Select.Option>
                                                    <Select.Option value="alarm">警報紀錄 (Alarm)</Select.Option>
                                                    <Select.Option value="event">生產事件 (Event)</Select.Option>
                                                    <Select.Option value="measurement">量測品管 (Measurement)</Select.Option>
                                                </Select>
                                            </Form.Item>
                                        </Col>
                                        <Col span={12}>
                                            <Form.Item noStyle dependencies={['category']}>
                                                {({ getFieldValue }) => {
                                                    const category = getFieldValue('category')?.toLowerCase();
                                                    const isTelemetry = category === 'telemetry';
                                                    const isEditing = !!editingTag;
                                                    
                                                    // 只有 Telemetry 在編輯模式下可以編輯 data_point
                                                    const isDataPointDisabled = isEditing && !isTelemetry;
                                                    
                                                    const availableFields = boundSchema?.fields || [];
                                                    const handleFieldChange = (val: string) => {
                                                        const field = availableFields.find(f => f.name === val);
                                                        if (field) {
                                                            if (!form.getFieldValue('display_name')) {
                                                                form.setFieldValue('display_name', field.name);
                                                            }
                                                            form.setFieldValue('data_type', field.type || 'float');
                                                            form.setFieldValue('unit', field.unit || null);
                                                        }
                                                    };
                
                                                    return (
                                                        <Form.Item
                                                            label={isTelemetry ? "主題後綴 (Topic Suffix / Data Point)" : "來源欄位 (Source Field / JSON Key)"}
                                                            name="data_point"
                                                            rules={[{ required: !isTelemetry, message: '必填' }]}
                                                            tooltip={isTelemetry ? "決定 MQTT Topic 結尾" : "Payload JSON 中的 Key"}
                                                        >
                                                            {(isTelemetry) ? (
                                                                <Input 
                                                                    placeholder="例如：temperature" 
                                                                    disabled={isDataPointDisabled}
                                                                />
                                                            ) : (
                                                                availableFields.length > 0 ? (
                                                                    <Select 
                                                                        placeholder="從 Schema 選取欄位" 
                                                                        onChange={handleFieldChange}
                                                                        disabled={isDataPointDisabled}
                                                                        options={availableFields.map(f => ({
                                                                            label: `${f.name} -> [${f.target_column || 'details'}]`,
                                                                            value: f.name
                                                                        }))}
                                                                    />
                                                                ) : (
                                                                    <Input 
                                                                        placeholder="輸入 JSON Key" 
                                                                        disabled={isDataPointDisabled}
                                                                    />
                                                                )
                                                            )}
                                                        </Form.Item>
                                                    );
                                                }}
                                            </Form.Item>
                                        </Col>
                                    </Row>
                
                                    {/* Live MQTT Preview */}
                                    <Form.Item noStyle dependencies={['category', 'data_point']}>
                                        {({ getFieldValue }) => {
                                            const cat = getFieldValue('category') || 'telemetry';
                                            const dp = getFieldValue('data_point');
                                            let topic = `${selectedPath}/${cat}`;
                                            if (cat === 'telemetry' && dp) topic += `/${dp}`;
                                            
                                            return (
                                                <div style={{ marginBottom: 20, padding: '8px 12px', background: 'rgba(0,0,0,0.2)', borderRadius: 4, borderLeft: '3px solid var(--color-primary)' }}>
                                                    <Text type="secondary" style={{ fontSize: 10, display: 'block', marginBottom: 4 }}>MQTT Topic Preview:</Text>
                                                    <Text code style={{ color: 'var(--color-primary)', fontSize: 12 }}>{topic}</Text>
                                                </div>
                                            );
                                        }}
                                    </Form.Item>
                
                                    <Row gutter={16}>
                                        <Col span={12}>
                                            <Form.Item label="型別 (Data Type)" name="data_type" initialValue="float">
                                                <Select>
                                                    <Select.Option value="float">浮點數 (Float)</Select.Option>
                                                    <Select.Option value="integer">整數 (Integer)</Select.Option>
                                                    <Select.Option value="string">字串 (String)</Select.Option>
                                                    <Select.Option value="boolean">布林值 (Boolean)</Select.Option>
                                                    <Select.Option value="json">JSON 物件</Select.Option>
                                                </Select>
                                            </Form.Item>
                                        </Col>
                                        <Col span={12}>
                                            <Form.Item label="單位 (Unit)" name="unit">
                                                <Input placeholder="例如：°C, %, mm" />
                                            </Form.Item>
                                        </Col>
                                    </Row>
                
                                    <Form.Item label="備註描述" name="description">
                                        <Input.TextArea rows={2} placeholder="描述此數據點的用途..." />
                                    </Form.Item>
                
                                    <Form.Item noStyle dependencies={['category', 'data_point']}>
                                        {({ getFieldValue }) => {
                                            const cat = getFieldValue('category');
                                            const dp = getFieldValue('data_point');
                                            const field = boundSchema?.fields.find(f => f.name === dp);
                                            const target = field?.target_column || (cat === 'telemetry' ? 'value' : 'details');
                                            
                                            return (
                                                <div style={{ textAlign: 'right' }}>
                                                    <Text type="secondary" style={{ fontSize: 11 }}>
                                                        Data Flow: Source[{dp || '*'}] ➔ Database Table[ts_{cat}s].Column[<Text strong style={{ color: '#aaa' }}>{target}</Text>]
                                                    </Text>
                                                </div>
                                            );
                                        }}
                                    </Form.Item>
                                </Form>
                            </Modal>
                {/* History Drawer */}
                <Drawer
                    title={
                        <div>
                            <LineChartOutlined style={{ marginRight: 8, color: 'var(--color-primary)' }} />
                            {activeTag?.display_name} - 歷史趨勢
                        </div>
                    }
                    placement="right"
                    width={800}
                    onClose={() => setHistoryDrawerOpen(false)}
                    open={historyDrawerOpen}
                >
                    <div style={{ marginBottom: 16 }}>
                        <Text type="secondary">
                            Tag ID: {activeTag?.tag_id} | 
                            Category: <AntTag color="blue" style={{ fontSize: 10, marginLeft: 4 }}>{activeTag?.category?.toUpperCase()}</AntTag> | 
                            Data Point: {activeTag?.data_point || 'N/A'}
                        </Text>
                    </div>

                    <Spin spinning={isTagLoading}>
                        {renderHistoryContent()}
                    </Spin>
                </Drawer>
            </div>
        </ConfigProvider>
    );
}
