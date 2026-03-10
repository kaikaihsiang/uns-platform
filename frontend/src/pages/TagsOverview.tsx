import { useEffect, useState, useCallback } from 'react';
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
    Switch
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
import type { TreeDataNode } from 'antd';

import { useNamespaceStore } from '../store/namespaceStore';
import { useTagStore } from '../store/tagStore';
import type { NodeTreeOut, TagOut, TagCreate } from '../types/namespace';
import '../pages/NamespaceEditor.css'; // Reuse layout CSS

const { Title, Text, Paragraph } = Typography;

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
    const [recursive, setRecursive] = useState(false);
    const [createModalOpen, setCreateModalOpen] = useState(false);
    const [editingTag, setEditingTag] = useState<TagOut | null>(null);
    const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
    const [activeTag, setActiveTag] = useState<TagOut | null>(null);
    const [form] = Form.useForm();

    // Init tree
    useEffect(() => {
        fetchTree();
    }, [fetchTree]);

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

    const historyColumns = [
        {
            title: '時間 (Time)',
            dataIndex: 'time',
            key: 'time',
            render: (t: string) => new Date(t).toLocaleString()
        },
        {
            title: '數值 (Value)',
            dataIndex: 'value',
            key: 'value',
            render: (_: any, record: any) => record.value ?? record.value_text ?? <Text type="secondary">null</Text>
        },
        {
            title: '品質 (Quality)',
            dataIndex: 'quality',
            key: 'quality',
            render: (q: string) => (
                <AntTag color={q === 'good' ? 'success' : q === 'bad' ? 'error' : 'warning'}>
                    {q}
                </AntTag>
            )
        }
    ];

    return (
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
            >
                <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
                    <Form.Item label="Asset Path (綁定節點)" name="asset_path">
                        <Input disabled />
                    </Form.Item>

                    <Form.Item
                        label="顯示名稱 (Display Name)"
                        name="display_name"
                        rules={[{ required: true, message: '必填' }]}
                    >
                        <Input placeholder="例如：設備溫度" />
                    </Form.Item>

                    <div style={{ display: 'flex', gap: 16 }}>
                        <Form.Item
                            label="分類 (Category)"
                            name="category"
                            style={{ flex: 1 }}
                            rules={[{ required: true }]}
                        >
                            <Select>
                                <Select.Option value="telemetry">遙測數值 (Telemetry)</Select.Option>
                                <Select.Option value="status">設備狀態 (Status)</Select.Option>
                                <Select.Option value="alarm">警報 (Alarm)</Select.Option>
                                <Select.Option value="event">事件 (Event)</Select.Option>
                                <Select.Option value="measurement">量測品管 (Measurement)</Select.Option>
                            </Select>
                        </Form.Item>

                        <Form.Item noStyle dependencies={['category']}>
                            {({ getFieldValue }) => {
                                const category = getFieldValue('category');
                                const isTelemetry = !category || category === 'telemetry';

                                const categoryColumns: Record<string, { label: string, value: string }[]> = {
                                    status: [
                                        { label: 'state_code', value: 'state_code' },
                                        { label: 'sub_state_code', value: 'sub_state_code' },
                                        { label: 'mode', value: 'mode' },
                                        { label: 'code_category', value: 'code_category' }
                                    ],
                                    alarm: [
                                        { label: 'alarm_id', value: 'alarm_id' },
                                        { label: 'alarm_code', value: 'alarm_code' },
                                        { label: 'sub_alarm_code', value: 'sub_alarm_code' },
                                        { label: 'severity', value: 'severity' },
                                        { label: 'message', value: 'message' },
                                        { label: 'alarm_status', value: 'alarm_status' },
                                        { label: 'value', value: 'value' },
                                        { label: 'threshold', value: 'threshold' }
                                    ],
                                    event: [
                                        { label: 'event_id', value: 'event_id' },
                                        { label: 'event_code', value: 'event_code' },
                                        { label: 'sub_event_code', value: 'sub_event_code' },
                                        { label: 'result', value: 'result' }
                                    ],
                                    measurement: [
                                        { label: 'value', value: 'value' },
                                        { label: 'spec_upper', value: 'spec_upper' },
                                        { label: 'spec_lower', value: 'spec_lower' },
                                        { label: 'target_value', value: 'target_value' },
                                        { label: 'result', value: 'result' },
                                        { label: 'lot_id', value: 'lot_id' },
                                        { label: 'sample_id', value: 'sample_id' },
                                        { label: 'sample_position', value: 'sample_position' },
                                        { label: 'inspector', value: 'inspector' }
                                    ]
                                };

                                return (
                                    <Form.Item
                                        label={isTelemetry ? "資料點欄位 (Data Point)" : "目標欄位 (Target Column)"}
                                        name="data_point"
                                        style={{ flex: 1 }}
                                        tooltip="將對應到資料表中的特定欄位或 JSON key"
                                    >
                                        {isTelemetry ? (
                                            <Input placeholder="選填，例如：temperature" />
                                        ) : (
                                            <Select
                                                placeholder="請選擇對應欄位"
                                                options={categoryColumns[category] || []}
                                                allowClear
                                            />
                                        )}
                                    </Form.Item>
                                );
                            }}
                        </Form.Item>
                    </div>

                    <div style={{ display: 'flex', gap: 16 }}>
                        <Form.Item label="型別 (Data Type)" name="data_type" style={{ flex: 1 }}>
                            <Select>
                                <Select.Option value="float">浮點數 (Float)</Select.Option>
                                <Select.Option value="integer">整數 (Integer)</Select.Option>
                                <Select.Option value="string">字串 (String)</Select.Option>
                                <Select.Option value="boolean">布林值 (Boolean)</Select.Option>
                            </Select>
                        </Form.Item>

                        <Form.Item label="單位 (Unit)" name="unit" style={{ flex: 1 }}>
                            <Input placeholder="例如：°C, %, mm" />
                        </Form.Item>
                    </div>

                    <Form.Item label="備註描述" name="description">
                        <Input.TextArea rows={2} />
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
                width={600}
                onClose={() => setHistoryDrawerOpen(false)}
                open={historyDrawerOpen}
            >
                <div style={{ marginBottom: 16 }}>
                    <Text type="secondary">Tag ID: {activeTag?.tag_id} | Data Point: {activeTag?.data_point || 'N/A'}</Text>
                </div>

                <Spin spinning={isTagLoading}>
                    <Table
                        columns={historyColumns}
                        dataSource={currentTagValues}
                        rowKey="time"
                        pagination={{ pageSize: 20 }}
                        size="small"
                    />
                </Spin>
            </Drawer>
        </div>
    );
}
