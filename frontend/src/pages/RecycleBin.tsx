import { useEffect, useState } from 'react';
import { Typography, Table, Tabs, Button, Space, Modal, Tag, Empty, Tooltip, notification } from 'antd';
import {
    DeleteOutlined,
    UndoOutlined,
    ApartmentOutlined,
    SafetyCertificateOutlined,
    TagsOutlined,
    ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useRecycleBinStore } from '../store/recycleBinStore';

const { Title, Paragraph } = Typography;

const formatDateTime = (iso: string | null) => {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleString('zh-TW', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    });
};

export default function RecycleBin() {
    const {
        deletedNodes, deletedSchemas, deletedTags, isLoading,
        fetchDeletedNodes, fetchDeletedSchemas, fetchDeletedTags,
        restoreNode, restoreSchema, restoreTag,
        hardDeleteNode, hardDeleteSchema, hardDeleteTag,
    } = useRecycleBinStore();

    const [activeTab, setActiveTab] = useState('nodes');

    useEffect(() => {
        fetchDeletedNodes();
        fetchDeletedSchemas();
        fetchDeletedTags();
    }, []);

    // ─── Common Action Handlers ──────────────────────────────────

    const handleRestore = async (type: string, id: number, name: string) => {
        let ok = false;
        if (type === 'node') ok = await restoreNode(id);
        else if (type === 'schema') ok = await restoreSchema(id);
        else if (type === 'tag') ok = await restoreTag(id);

        if (ok) {
            notification.success({ message: '還原成功', description: `「${name}」已從回收桶還原。` });
        } else {
            notification.error({ message: '還原失敗', description: '請檢查 Backend 日誌。' });
        }
    };

    const handleHardDelete = (type: string, id: number, name: string) => {
        Modal.confirm({
            title: '⚠️ 永久刪除確認',
            icon: <ExclamationCircleOutlined />,
            content: (
                <div>
                    <p>您確定要永久刪除「<strong>{name}</strong>」嗎？</p>
                    <p style={{ color: '#ff7675', fontSize: 13 }}>
                        此操作不可逆！資料將從資料庫中徹底移除，包含所有關聯的歷史資料。
                    </p>
                </div>
            ),
            okText: '確認刪除',
            okButtonProps: { danger: true },
            cancelText: '取消',
            onOk: async () => {
                let ok = false;
                if (type === 'node') ok = await hardDeleteNode(id);
                else if (type === 'schema') ok = await hardDeleteSchema(id);
                else if (type === 'tag') ok = await hardDeleteTag(id);

                if (ok) {
                    notification.success({ message: '永久刪除成功', description: `「${name}」已徹底清除。` });
                } else {
                    notification.error({ message: '永久刪除失敗', description: '請檢查 Backend 日誌。' });
                }
            },
        });
    };

    const renderActions = (type: string, id: number, name: string) => (
        <Space>
            <Tooltip title="還原">
                <Button
                    type="primary"
                    ghost
                    size="small"
                    icon={<UndoOutlined />}
                    onClick={() => handleRestore(type, id, name)}
                >
                    還原
                </Button>
            </Tooltip>
            <Tooltip title="永久刪除（不可逆）">
                <Button
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => handleHardDelete(type, id, name)}
                >
                    永久刪除
                </Button>
            </Tooltip>
        </Space>
    );



    // ─── Nodes Tab ───────────────────────────────────────────────

    const nodeColumns = [
        {
            title: 'ID',
            dataIndex: 'node_id',
            key: 'node_id',
            width: 60,
        },
        {
            title: '名稱',
            dataIndex: 'name',
            key: 'name',
            render: (name: string) => <strong>{name}</strong>,
        },
        {
            title: '完整路徑',
            dataIndex: 'full_path',
            key: 'full_path',
            render: (path: string) => (
                <code style={{ fontSize: 12, color: 'var(--color-warning)' }}>{path}</code>
            ),
        },
        {
            title: '類型',
            dataIndex: 'node_type',
            key: 'node_type',
            width: 100,
            render: (t: string) => (
                <Tag color={t === 'topic' ? 'cyan' : 'default'}>{t}</Tag>
            ),
        },
        {
            title: '刪除時間',
            dataIndex: 'deleted_at',
            key: 'deleted_at',
            width: 180,
            render: formatDateTime,
        },
        {
            title: '操作',
            key: 'actions',
            width: 220,
            render: (_: any, record: any) => renderActions('node', record.node_id, record.name),
        },
    ];

    // ─── Schemas Tab ─────────────────────────────────────────────

    const schemaColumns = [
        {
            title: 'ID',
            dataIndex: 'type_id',
            key: 'type_id',
            width: 60,
        },
        {
            title: 'Schema 名稱',
            dataIndex: 'type_name',
            key: 'type_name',
            render: (name: string) => <strong>{name}</strong>,
        },
        {
            title: 'Decoder',
            dataIndex: 'decoder',
            key: 'decoder',
            width: 100,
            render: (d: string) => <Tag color="blue">{d || 'json'}</Tag>,
        },
        {
            title: '欄位數',
            key: 'field_count',
            width: 80,
            render: (_: any, record: any) => (record.fields?.length ?? 0),
        },
        {
            title: '刪除時間',
            dataIndex: 'deleted_at',
            key: 'deleted_at',
            width: 180,
            render: formatDateTime,
        },
        {
            title: '操作',
            key: 'actions',
            width: 220,
            render: (_: any, record: any) => renderActions('schema', record.type_id, record.type_name),
        },
    ];

    // ─── Tags Tab ────────────────────────────────────────────────

    const tagColumns = [
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
            render: (name: string) => <strong>{name}</strong>,
        },
        {
            title: '資料類型',
            dataIndex: 'data_type',
            key: 'data_type',
            width: 100,
            render: (t: string) => <Tag color="green">{t}</Tag>,
        },
        {
            title: '單位',
            dataIndex: 'unit',
            key: 'unit',
            width: 80,
        },
        {
            title: '刪除時間',
            dataIndex: 'deleted_at',
            key: 'deleted_at',
            width: 180,
            render: formatDateTime,
        },
        {
            title: '操作',
            key: 'actions',
            width: 220,
            render: (_: any, record: any) => renderActions('tag', record.tag_id, record.display_name || `Tag #${record.tag_id}`),
        },
    ];

    // ─── Tab Items ───────────────────────────────────────────────

    const tabItems = [
        {
            key: 'nodes',
            label: (
                <span>
                    <ApartmentOutlined style={{ marginRight: 6 }} />
                    Namespace Nodes ({deletedNodes.length})
                </span>
            ),
            children: (
                <Table
                    dataSource={deletedNodes}
                    columns={nodeColumns}
                    rowKey="node_id"
                    loading={isLoading}
                    pagination={{ pageSize: 10 }}
                    locale={{ emptyText: <Empty description="沒有已刪除的 Namespace 節點" /> }}
                />
            ),
        },
        {
            key: 'schemas',
            label: (
                <span>
                    <SafetyCertificateOutlined style={{ marginRight: 6 }} />
                    Schema Types ({deletedSchemas.length})
                </span>
            ),
            children: (
                <Table
                    dataSource={deletedSchemas}
                    columns={schemaColumns}
                    rowKey="type_id"
                    loading={isLoading}
                    pagination={{ pageSize: 10 }}
                    locale={{ emptyText: <Empty description="沒有已刪除的 Schema Types" /> }}
                />
            ),
        },
        {
            key: 'tags',
            label: (
                <span>
                    <TagsOutlined style={{ marginRight: 6 }} />
                    Tags ({deletedTags.length})
                </span>
            ),
            children: (
                <Table
                    dataSource={deletedTags}
                    columns={tagColumns}
                    rowKey="tag_id"
                    loading={isLoading}
                    pagination={{ pageSize: 10 }}
                    locale={{ emptyText: <Empty description="沒有已刪除的 Tags" /> }}
                />
            ),
        },
    ];

    return (
        <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
            <div style={{ marginBottom: 24 }}>
                <Title level={2}>
                    <DeleteOutlined style={{ marginRight: 12, color: 'var(--color-primary)' }} />
                    資源回收桶
                </Title>
                <Paragraph type="secondary">
                    檢視並管理被軟刪除的 Namespace Nodes、Schema Types 與 Tags。您可以選擇還原或永久刪除。
                </Paragraph>
            </div>

            <Tabs
                activeKey={activeTab}
                onChange={setActiveTab}
                items={tabItems}
                type="card"
                style={{
                    background: 'var(--color-bg-container)',
                    borderRadius: 8,
                    padding: '12px 16px',
                }}
            />
        </div>
    );
}
