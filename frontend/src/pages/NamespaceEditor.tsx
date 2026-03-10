/**
 * NamespaceEditor — Feature 1: Namespace Tree Drag & Drop + CRUD
 *
 * Left panel: AntD Tree with draggable nodes + context actions
 * Right panel: Selected node detail + property editor
 */
import { useEffect, useState, useCallback } from 'react';
import {
    Tree,
    Button,
    Modal,
    Form,
    Input,
    Select,
    InputNumber,
    Spin,
    Tooltip,
    Popconfirm,
    Tag,
    Empty,
    Typography,
} from 'antd';
import {
    ApartmentOutlined,
    PlusOutlined,
    EditOutlined,
    DeleteOutlined,
    FolderOutlined,
    ApiOutlined,
    ReloadOutlined,
} from '@ant-design/icons';
import type { TreeProps, TreeDataNode } from 'antd';
import { useNamespaceStore } from '../store/namespaceStore';
import { useProductionStore } from '../store/productionStore';
import { useSchemaStore } from '../store/schemaStore';
import type { NodeTreeOut } from '../types/namespace';
import './NamespaceEditor.css';

const { Paragraph } = Typography;

// ── Convert backend tree to AntD TreeDataNode ──
function toTreeData(nodes: NodeTreeOut[]): TreeDataNode[] {
    return nodes.map((node) => ({
        key: node.node_id,
        title: node.name,
        children: node.children?.length ? toTreeData(node.children) : [],
        isLeaf: !node.children?.length,
        icon:
            node.node_type === 'topic' ? (
                <ApiOutlined style={{ color: 'var(--color-primary)' }} />
            ) : (
                <FolderOutlined style={{ color: 'var(--color-info)' }} />
            ),
        // Store original data for detail panel
        _raw: node,
    }));
}

// ── Find a node in tree by key ──
function findNodeByKey(nodes: NodeTreeOut[], key: number): NodeTreeOut | null {
    for (const node of nodes) {
        if (node.node_id === key) return node;
        if (node.children?.length) {
            const found = findNodeByKey(node.children, key);
            if (found) return found;
        }
    }
    return null;
}

export default function NamespaceEditor() {
    const {
        treeData,
        selectedNode,
        isLoading,
        fetchTree,
        selectNode,
        createNode,
        moveNode,
        renameNode,
        deleteNode,
        updatePersistence,
        updateNodeSchema,
    } = useNamespaceStore();

    const { activeRuns, fetchActiveRuns, isLoading: prodLoading } = useProductionStore();
    const { schemas, fetchSchemas } = useSchemaStore();

    // Modal states
    const [createModalOpen, setCreateModalOpen] = useState(false);
    const [renameModalOpen, setRenameModalOpen] = useState(false);
    const [actionNode, setActionNode] = useState<NodeTreeOut | null>(null);
    const [createForm] = Form.useForm();
    const [renameForm] = Form.useForm();

    // Fetch tree and schemas on mount
    useEffect(() => {
        fetchTree();
        fetchSchemas();
    }, [fetchTree, fetchSchemas]);

    const handleDrop: TreeProps['onDrop'] = useCallback(
        async (info: Parameters<NonNullable<TreeProps['onDrop']>>[0]) => {
            const dragNodeId = info.dragNode.key as number;
            const dropNodeId = info.node.key as number;

            // If dropping ON a node (not between), the drop node is the new parent
            // If dropping between nodes, we use the parent of the drop target
            if (!info.dropToGap) {
                // Dropped on the node — it becomes the parent
                await moveNode(dragNodeId, dropNodeId);
            } else {
                // Dropped between nodes — use the drop node's parent
                // parent_id === null means "move to root level"
                const dropNode = findNodeByKey(treeData, dropNodeId);
                if (dropNode) {
                    await moveNode(dragNodeId, dropNode.parent_id);
                }
            }
        },
        [treeData, moveNode]
    );

    // ── Tree Selection ──
    const handleSelect = useCallback(
        (selectedKeys: React.Key[]) => {
            if (selectedKeys.length) {
                const node = findNodeByKey(treeData, selectedKeys[0] as number);
                selectNode(node);
                if (node && node.node_type === 'structural') {
                    // Fetch active runs for this equipment node
                    fetchActiveRuns(node.full_path);
                } else if (node && node.node_type === 'topic') {
                    // Also fetch if selecting a topic under an equipment
                    const equipmentPath = node.full_path.substring(0, node.full_path.lastIndexOf('/'));
                    fetchActiveRuns(equipmentPath);
                }
            } else {
                selectNode(null);
            }
        },
        [treeData, selectNode, fetchActiveRuns]
    );

    // ── Create Node ──
    const handleCreate = useCallback(
        (parentNode: NodeTreeOut | null) => {
            setActionNode(parentNode);
            createForm.resetFields();
            createForm.setFieldsValue({
                node_type: 'structural',
                parent_id: parentNode?.node_id ?? null,
            });
            setCreateModalOpen(true);
        },
        [createForm]
    );

    const handleCreateSubmit = useCallback(async () => {
        const values = await createForm.validateFields();
        const result = await createNode({
            parent_id: values.parent_id,
            name: values.name,
            node_type: values.node_type,
            description: values.description || null,
            schema_id: values.schema_id || null,
        });
        if (result) setCreateModalOpen(false);
    }, [createForm, createNode]);

    // ── Rename Node ──
    const handleRename = useCallback(
        (node: NodeTreeOut) => {
            setActionNode(node);
            renameForm.setFieldsValue({ name: node.name });
            setRenameModalOpen(true);
        },
        [renameForm]
    );

    const handleRenameSubmit = useCallback(async () => {
        if (!actionNode) return;
        const values = await renameForm.validateFields();
        const ok = await renameNode(actionNode.node_id, { name: values.name });
        if (ok) setRenameModalOpen(false);
    }, [renameForm, renameNode, actionNode]);

    // ── Custom Title Renderer ──
    const renderTreeNode = useCallback(
        (nodeData: TreeDataNode): React.ReactNode => {
            const raw = (nodeData as TreeDataNode & { _raw: NodeTreeOut })._raw;
            return (
                <div className="tree-node-content">
                    <div className="tree-node-label">
                        <span className="tree-node-name">{raw.name}</span>
                        <span className={`tree-node-type-badge ${raw.node_type}`}>
                            {raw.node_type}
                        </span>
                        {raw.node_type === 'topic' && (
                            <span
                                className={`tree-node-persist-badge ${raw.persist_mode || 'db'}`}
                                title={`Persistence: ${raw.persist_mode || 'db'} ${raw.persist_mode === 'db' ? `(${raw.retention_days || 90}d)` : ''}`}
                            />
                        )}
                    </div>
                    <div className="tree-node-actions">
                        <Tooltip title="新增子節點">
                            <Button
                                type="text"
                                size="small"
                                icon={<PlusOutlined />}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleCreate(raw);
                                }}
                            />
                        </Tooltip>
                        <Tooltip title="重新命名">
                            <Button
                                type="text"
                                size="small"
                                icon={<EditOutlined />}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleRename(raw);
                                }}
                            />
                        </Tooltip>
                        {/* 移除了 persistence 的 context action，因為我們將在 detail panel 中直接操作 */}
                        <Popconfirm
                            title={`確定要刪除「${raw.name}」嗎？`}
                            description="此操作將 Soft Delete 此節點及其所有子節點與關聯的 Tags。歷史數據仍會保留。"
                            onConfirm={(e) => {
                                e?.stopPropagation();
                                deleteNode(raw.node_id);
                            }}
                            onCancel={(e) => e?.stopPropagation()}
                        >
                            <Tooltip title="刪除">
                                <Button
                                    type="text"
                                    size="small"
                                    danger
                                    icon={<DeleteOutlined />}
                                    onClick={(e) => e.stopPropagation()}
                                />
                            </Tooltip>
                        </Popconfirm>
                    </div>
                </div>
            );
        },
        [handleCreate, handleRename, deleteNode]
    );

    const antTreeData = toTreeData(treeData);

    return (
        <div className="namespace-editor">
            {/* ── Left: Tree Panel ── */}
            <div className="namespace-tree-panel">
                <div className="namespace-tree-header">
                    <h3>
                        <ApartmentOutlined /> Namespace Tree
                    </h3>
                    <div style={{ display: 'flex', gap: 4 }}>
                        <Tooltip title="重新載入">
                            <Button
                                type="text"
                                icon={<ReloadOutlined />}
                                onClick={fetchTree}
                                loading={isLoading}
                            />
                        </Tooltip>
                        <Tooltip title="新增根節點">
                            <Button
                                type="primary"
                                size="small"
                                icon={<PlusOutlined />}
                                onClick={() => handleCreate(null)}
                            >
                                新增
                            </Button>
                        </Tooltip>
                    </div>
                </div>

                <div className="namespace-tree-body">
                    <Spin spinning={isLoading}>
                        {antTreeData.length > 0 ? (
                            <Tree
                                treeData={antTreeData}
                                draggable={{ icon: false }}
                                blockNode
                                showIcon
                                defaultExpandAll
                                onDrop={handleDrop}
                                onSelect={handleSelect}
                                selectedKeys={selectedNode ? [selectedNode.node_id] : []}
                                titleRender={renderTreeNode}
                            />
                        ) : (
                            <Empty
                                description="尚無命名空間節點"
                                style={{ marginTop: 80 }}
                            />
                        )}
                    </Spin>
                </div>
            </div>

            {/* ── Right: Detail Panel ── */}
            <div className="namespace-detail-panel">
                {selectedNode ? (
                    <div className="namespace-detail-content">
                        <div className="detail-section">
                            <div className="detail-section-title">節點資訊</div>
                            <div className="detail-field">
                                <span className="detail-field-label">Node ID</span>
                                <span className="detail-field-value">{selectedNode.node_id}</span>
                            </div>
                            <div className="detail-field">
                                <span className="detail-field-label">名稱</span>
                                <span className="detail-field-value">{selectedNode.name}</span>
                            </div>
                            <div className="detail-field">
                                <span className="detail-field-label">完整路徑</span>
                                <span className="detail-field-value">{selectedNode.full_path}</span>
                            </div>
                            <div className="detail-field">
                                <span className="detail-field-label">節點類型</span>
                                <Tag
                                    color={selectedNode.node_type === 'topic' ? 'cyan' : 'blue'}
                                >
                                    {selectedNode.node_type}
                                </Tag>
                            </div>
                            {selectedNode.description && (
                                <div className="detail-field">
                                    <span className="detail-field-label">描述</span>
                                    <span className="detail-field-value">{selectedNode.description}</span>
                                </div>
                            )}
                        </div>

                        <div className="detail-section">
                            <div className="detail-section-title">MQTT Topic / Path</div>
                            <div className="detail-field">
                                <span className="detail-field-label">Topic</span>
                                <code className="detail-field-value" style={{ color: 'var(--color-primary)' }}>
                                    {selectedNode.full_path}
                                </code>
                            </div>
                        </div>

                        {selectedNode.node_type === 'topic' && (
                            <div className="detail-section">
                                <div className="detail-section-title">持久化設定</div>
                                <div className="detail-field">
                                    <span className="detail-field-label">模式</span>
                                    <Select
                                        size="small"
                                        value={selectedNode.persist_mode || 'db'}
                                        onChange={(val) =>
                                            updatePersistence(selectedNode.node_id, {
                                                persist_mode: val,
                                                retention_days: selectedNode.retention_days ?? 90
                                            })
                                        }
                                        style={{ width: 140 }}
                                        options={[
                                            { value: 'db', label: '✅ Database' },
                                            { value: 'retain', label: '🔁 Retain (MQTT Only)' },
                                            { value: 'passthrough', label: '💨 Passthrough (No Storage)' },
                                        ]}
                                    />
                                </div>
                                <div className="detail-field" style={{ marginTop: 8 }}>
                                    <span className="detail-field-label">保留天數</span>
                                    <InputNumber
                                        size="small"
                                        value={selectedNode.retention_days ?? 90}
                                        disabled={selectedNode.persist_mode !== 'db'}
                                        min={1}
                                        onChange={(val) => {
                                            if (val !== null) {
                                                updatePersistence(selectedNode.node_id, {
                                                    persist_mode: selectedNode.persist_mode || 'db',
                                                    retention_days: val
                                                });
                                            }
                                        }}
                                        addonAfter="天"
                                    />
                                </div>
                                {selectedNode.schema_id && (
                                    <div className="detail-field" style={{ marginTop: 12 }}>
                                        <span className="detail-field-label">目前綁定 ID</span>
                                        <span className="detail-field-value">
                                            {selectedNode.schema_id}
                                        </span>
                                    </div>
                                )}

                                <div className="detail-field" style={{ marginTop: 16, borderTop: '1px solid var(--border-color)', paddingTop: 16 }}>
                                    <span className="detail-field-label">資料解析 Schema (Binding)</span>
                                    <Select
                                        placeholder="選擇解析 Schema"
                                        style={{ width: '100%', marginTop: 8 }}
                                        value={selectedNode.schema_id}
                                        allowClear
                                        onChange={(val) => updateNodeSchema(selectedNode.node_id, { schema_id: val })}
                                        options={(schemas || [])
                                            .filter(s => !s.is_suggested)
                                            .map(s => ({
                                                value: s.schema_id,
                                                label: `${s.schema_name} (${s.schema_category})`
                                            }))}
                                    />
                                    <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8 }}>
                                        綁定核准後的 Schema，Data Engine 才能開始解析並提取資料點。
                                    </Paragraph>
                                </div>
                            </div>
                        )}
                        {/* Active Run Card (L3 Production Context) */}
                        {selectedNode.node_type === 'structural' && activeRuns.length > 0 && (
                            <div className="active-run-section" style={{ marginTop: '24px', padding: '16px', background: 'var(--bg-glass)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                                <h4 style={{ margin: '0 0 16px 0', color: 'var(--color-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <span className="status-dot success" style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--color-success)' }}></span>
                                    當前生產批次 (Active Run)
                                </h4>
                                {prodLoading ? (
                                    <Spin size="small" />
                                ) : (
                                    <div className="property-grid">
                                        <div className="property-item">
                                            <span className="property-label">Lot ID</span>
                                            <span className="property-value highlight">{activeRuns[0].lot_id}</span>
                                        </div>
                                        <div className="property-item">
                                            <span className="property-label">Recipe</span>
                                            <span className="property-value">{activeRuns[0].recipe_id || '-'}</span>
                                        </div>
                                        <div className="property-item">
                                            <span className="property-label">狀態</span>
                                            <Tag color={activeRuns[0].status === 'Running' ? 'green' : 'blue'}>
                                                {activeRuns[0].status}
                                            </Tag>
                                        </div>
                                        <div className="property-item">
                                            <span className="property-label">開始時間</span>
                                            <span className="property-value">
                                                {new Date(activeRuns[0].start_time).toLocaleString()}
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="namespace-detail-empty">
                        <ApartmentOutlined />
                        <span>選擇一個節點以檢視詳細資訊</span>
                        <span className="text-muted" style={{ fontSize: 12 }}>
                            支援拖放移動節點（觸發 Live Migration）
                        </span>
                    </div>
                )}
            </div>

            {/* ═══ Modals ═══ */}

            {/* Create Node Modal */}
            <Modal
                title="新增節點"
                open={createModalOpen}
                onOk={handleCreateSubmit}
                onCancel={() => setCreateModalOpen(false)}
                okText="建立"
                cancelText="取消"
            >
                <Form form={createForm} layout="vertical" style={{ marginTop: 16 }}>
                    <Form.Item name="parent_id" hidden>
                        <Input />
                    </Form.Item>
                    <Form.Item
                        name="name"
                        label="節點名稱"
                        rules={[{ required: true, message: '請輸入節點名稱' }]}
                    >
                        <Input placeholder="例如：Line1, Printer, Telemetry" />
                    </Form.Item>
                    <Form.Item
                        name="node_type"
                        label="節點類型"
                        rules={[{ required: true }]}
                    >
                        <Select
                            options={[
                                { value: 'structural', label: 'Structural（結構節點）' },
                                { value: 'topic', label: 'Topic（MQTT 主題節點）' },
                            ]}
                        />
                    </Form.Item>
                    <Form.Item name="description" label="描述">
                        <Input.TextArea rows={2} placeholder="選填" />
                    </Form.Item>
                </Form>
            </Modal>

            {/* Rename Node Modal */}
            <Modal
                title={`重新命名：${actionNode?.name || ''}`}
                open={renameModalOpen}
                onOk={handleRenameSubmit}
                onCancel={() => setRenameModalOpen(false)}
                okText="確認"
                cancelText="取消"
            >
                <Form form={renameForm} layout="vertical" style={{ marginTop: 16 }}>
                    <Form.Item
                        name="name"
                        label="新名稱"
                        rules={[{ required: true, message: '請輸入新名稱' }]}
                    >
                        <Input />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
}
