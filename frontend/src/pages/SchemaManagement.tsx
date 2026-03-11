import { useEffect, useState } from 'react';
import {
    Table,
    Button,
    Card,
    Modal,
    Form,
    Input,
    Select,
    Space,
    Tag,
    Popconfirm,
    message,
    Typography,
    Divider,
    Switch,
    Row,
    Col,
    Alert
} from 'antd';
import {
    PlusOutlined,
    EditOutlined,
    DeleteOutlined,
    SafetyCertificateOutlined,
    MinusCircleOutlined,
} from '@ant-design/icons';
import { useSchemaStore } from '../store/schemaStore';
import type { PayloadSchemaOut, PayloadSchemaCreate, PayloadSchemaUpdate } from '../types/namespace';

const { Title, Paragraph, Text } = Typography;

export default function SchemaManagement() {
    const { schemas, isLoading, fetchSchemas, deleteSchema, createSchema, updateSchema } = useSchemaStore();
    const [modalOpen, setModalOpen] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [form] = Form.useForm();
    const watchedFields = Form.useWatch('fields', form);
    const watchedCategory = Form.useWatch('schema_category', form);

    // Target Column options per category
    const targetColumnOptions: Record<string, { value: string, label: string }[]> = {
        alarm: [
            { value: 'alarm_id', label: 'alarm_id' },
            { value: 'alarm_code', label: 'alarm_code' },
            { value: 'sub_alarm_code', label: 'sub_alarm_code' },
            { value: 'severity', label: 'severity' },
            { value: 'message', label: 'message' },
            { value: 'alarm_status', label: 'alarm_status' },
            { value: 'value', label: 'value' },
            { value: 'threshold', label: 'threshold' },
            { value: 'details', label: 'details' },
        ],
        status: [
            { value: 'state_code', label: 'state_code' },
            { value: 'sub_state_code', label: 'sub_state_code' },
            { value: 'mode', label: 'mode' },
            { value: 'code_category', label: 'code_category' },
            { value: 'details', label: 'details' },
        ],
        event: [
            { value: 'event_id', label: 'event_id' },
            { value: 'event_code', label: 'event_code' },
            { value: 'sub_event_code', label: 'sub_event_code' },
            { value: 'result', label: 'result' },
            { value: 'details', label: 'details' },
        ],
        measurement: [
            { value: 'value', label: 'value' },
            { value: 'spec_upper', label: 'spec_upper' },
            { value: 'spec_lower', label: 'spec_lower' },
            { value: 'target_value', label: 'target_value' },
            { value: 'result', label: 'result' },
            { value: 'lot_id', label: 'lot_id' },
            { value: 'sample_id', label: 'sample_id' },
            { value: 'sample_position', label: 'sample_position' },
            { value: 'inspector', label: 'inspector' },
            { value: 'details', label: 'details' },
        ],
        metrics: [
            { value: 'value_min', label: 'value_min' },
            { value: 'value_max', label: 'value_max' },
            { value: 'value_avg', label: 'value_avg' },
            { value: 'details', label: 'details' },
        ],
    };

    useEffect(() => {
        fetchSchemas();
    }, [fetchSchemas]);

    const handleCreate = () => {
        setEditingId(null);
        form.resetFields();
        form.setFieldsValue({
            decoder: 'json',
            store_raw: true,
            raw_retention_days: 30,
            on_schema_mismatch: 'log_and_store',
            on_new_field: 'suggest',
            schema_category: 'telemetry',
            fields: [
                {
                    name: '',
                    path: '',
                    type: 'float',
                    extract: true,
                    persist: true,
                    array_mode: 'single'
                }
            ],
        });
        setModalOpen(true);
    };

    const handleEdit = (record: PayloadSchemaOut) => {
        setEditingId(record.schema_id);
        form.setFieldsValue({
            schema_name: record.schema_name,
            decoder: record.decoder,
            timestamp_field: record.timestamp_field,
            store_raw: record.store_raw,
            raw_retention_days: record.raw_retention_days,
            on_schema_mismatch: record.on_schema_mismatch,
            on_new_field: record.on_new_field,
            schema_category: record.schema_category || 'telemetry',
            fields: record.fields,
        });
        setModalOpen(true);
    };

    const handleDelete = async (schemaId: number) => {
        const success = await deleteSchema(schemaId);
        if (success) {
            message.success('Schema 已刪除');
        }
    };

    const handleSubmit = async () => {
        try {
            const values = await form.validateFields();
            let success = false;

            const payload = {
                schema_name: values.schema_name,
                decoder: values.decoder,
                timestamp_field: values.timestamp_field || null,
                store_raw: values.store_raw,
                raw_retention_days: values.raw_retention_days,
                on_schema_mismatch: values.on_schema_mismatch,
                on_new_field: values.on_new_field,
                schema_category: values.schema_category,
                fields: values.fields,
            };

            if (editingId) {
                success = await updateSchema(editingId, payload as PayloadSchemaUpdate);
            } else {
                success = await createSchema(payload as PayloadSchemaCreate);
            }

            if (success) {
                message.success(`Schema ${editingId ? '更新' : '建立'}成功`);
                setModalOpen(false);
            }
        } catch (err) {
            // validation failed
        }
    };

    const columns = [
        {
            title: 'Schema 名稱',
            dataIndex: 'schema_name',
            key: 'schema_name',
            render: (text: string, r: PayloadSchemaOut) => (
                <Space direction="vertical" size={0}>
                    <Text strong style={{ color: 'var(--color-primary)' }}>{text}</Text>
                    {r.schema_category && (
                        <Tag
                            color={
                                r.schema_category === 'telemetry' ? 'blue' :
                                    r.schema_category === 'alarm' ? 'red' :
                                        r.schema_category === 'status' ? 'green' :
                                            r.schema_category === 'event' ? 'purple' :
                                                r.schema_category === 'measurement' ? 'orange' : 'default'
                            }
                            style={{ fontSize: 10, lineHeight: '16px', marginTop: 4 }}
                        >
                            {r.schema_category.toUpperCase()}
                        </Tag>
                    )}
                </Space>
            ),
            filters: [
                { text: 'Telemetry', value: 'telemetry' },
                { text: 'Status', value: 'status' },
                { text: 'Alarm', value: 'alarm' },
                { text: 'Event', value: 'event' },
                { text: 'Measurement', value: 'measurement' },
                { text: 'Metrics', value: 'metrics' },
            ],
            onFilter: (value: any, record: PayloadSchemaOut) => record.schema_category === value,
        },
        {
            title: '解碼器配置',
            key: 'decoder_config',
            render: (_: any, r: PayloadSchemaOut) => (
                <div style={{ fontSize: 12 }}>
                    <div><Text type="secondary">Decoder:</Text> <Tag color="blue">{r.decoder}</Tag></div>
                    {r.timestamp_field && <div><Text type="secondary">TS_Field:</Text> <code>{r.timestamp_field}</code></div>}
                    <div><Text type="secondary">Raw:</Text> {r.store_raw ? `${r.raw_retention_days}d` : 'Off'}</div>
                </div>
            )
        },
        {
            title: '提取規則 (JSONPath)',
            dataIndex: 'fields',
            key: 'fields',
            render: (fields: any[]) => (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {fields?.map((f, i) => (
                        <div key={i} style={{ fontSize: 13, background: 'var(--bg-surface)', padding: '2px 8px', borderRadius: 4 }}>
                            <Text strong>{f.name}</Text> <Text type="secondary">({f.type})</Text>
                            <br />
                            <code style={{ fontSize: 11, color: 'var(--color-warning)' }}>{f.path || `$.${f.name}`}</code>
                            {f.array_mode !== 'single' && <Tag style={{ marginLeft: 4, fontSize: 10 }}>{f.array_mode}</Tag>}
                        </div>
                    ))}
                </div>
            ),
        },
        {
            title: '演化策略',
            key: 'evolution',
            render: (_: any, r: PayloadSchemaOut) => (
                <div style={{ fontSize: 12 }}>
                    <div><Text type="secondary">Mismatch:</Text> {r.on_schema_mismatch}</div>
                    <div><Text type="secondary">NewField:</Text> {r.on_new_field}</div>
                </div>
            )
        },
        {
            title: '操作',
            key: 'action',
            width: 100,
            render: (_: any, record: PayloadSchemaOut) => (
                <Space size="small">
                    <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
                    <Popconfirm
                        title="確定要刪除嗎？"
                        onConfirm={() => handleDelete(record.schema_id)}
                        okButtonProps={{ danger: true }}
                    >
                        <Button type="text" danger icon={<DeleteOutlined />} />
                    </Popconfirm>
                </Space>
            ),
        },
    ];

    // Helper to generate Preview JSON based on defined Field Paths
    const generatePreviewJson = (fields: any[]) => {
        if (!fields || fields.length === 0) return {};
        const result: any = {};

        fields.forEach(f => {
            if (!f || (!f.name && !f.path)) return;
            const pathInfo = f.path || `$.${f.name}`;

            // Very simple JSONPath to Object converter for preview
            let current = result;
            const parts = pathInfo.replace('$.', '').split('.');

            parts.forEach((part: string, idx: number) => {
                const isArray = part.includes('[*]');
                const cleanPart = part.replace('[*]', '');

                if (idx === parts.length - 1) {
                    // Leaf node
                    let val: any = 0;
                    if (f.type === 'string') val = "string_value";
                    else if (f.type === 'boolean') val = true;
                    else if (f.type === 'json') val = { "key": "value" };

                    if (isArray) {
                        current[cleanPart] = [val];
                    } else {
                        current[cleanPart] = val;
                    }
                } else {
                    // Intermediate node
                    if (isArray) {
                        if (!current[cleanPart]) current[cleanPart] = [{}];
                        current = current[cleanPart][0];
                    } else {
                        if (!current[cleanPart]) current[cleanPart] = {};
                        current = current[cleanPart];
                    }
                }
            });
        });
        return result;
    };

    const previewJson = generatePreviewJson(watchedFields);

    return (
        <div style={{ padding: 24, height: '100%', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
                <div>
                    <Title level={2} style={{ margin: 0 }}>
                        <SafetyCertificateOutlined style={{ marginRight: 12, color: 'var(--color-primary)' }} />
                        Schema 管理
                    </Title>
                    <Paragraph type="secondary" style={{ marginTop: 8 }}>
                        精確定義 Payload 提取契約，支援 JSONPath 解析、陣列展開、Deadband 濾波與演化策略。
                    </Paragraph>
                </div>
                <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                    建立 Schema
                </Button>
            </div>

            <Card bodyStyle={{ padding: 0 }} bordered={false}>
                <Table
                    columns={columns}
                    dataSource={schemas}
                    rowKey="schema_id"
                    loading={isLoading}
                    pagination={{ pageSize: 10 }}
                />
            </Card>

            <Modal
                title={editingId ? '編輯 Schema' : '建立 Schema'}
                open={modalOpen}
                onOk={handleSubmit}
                onCancel={() => setModalOpen(false)}
                width={1200}
                destroyOnClose
            >
                <Row gutter={24} style={{ marginTop: 16 }}>
                    {/* Left Panel: Form Settings */}
                    <Col span={14} style={{ maxHeight: '70vh', overflowY: 'auto', paddingRight: 12 }}>
                        <Form form={form} layout="vertical">
                            <Row gutter={16}>
                                <Col span={12}>
                                    <Form.Item name="schema_name" label="Schema 名稱" rules={[{ required: true }]}>
                                        <Input placeholder="例如：SMT_Printer_Telemetry" />
                                    </Form.Item>
                                </Col>
                                <Col span={12}>
                                    <Form.Item name="decoder" label="解碼器 (Decoder)" rules={[{ required: true }]}>
                                        <Select options={[
                                            { value: 'json', label: '標準 JSON (預設)' },
                                            { value: 'sparkplug', label: 'Sparkplug B (Protobuf)' },
                                            { value: 'text_csv', label: 'CSV 格式' }
                                        ]} />
                                    </Form.Item>
                                </Col>
                            </Row>

                            <Row gutter={16}>
                                <Col span={12}>
                                    <Form.Item name="timestamp_field" label="Timestamp 欄位 (JSONPath)" tooltip="Payload 中的時間戳欄位。留空則使用 MQTT 抵達時間。">
                                        <Input placeholder="例如：$._meta.timestamp" />
                                    </Form.Item>
                                </Col>
                                <Col span={12}>
                                    <Form.Item name="store_raw" label="儲存 Raw Payload" valuePropName="checked">
                                        <Switch />
                                    </Form.Item>
                                </Col>
                            </Row>

                            <Divider style={{ margin: '12px 0' }}>Schema 演化與異常處理</Divider>

                            <Row gutter={16}>
                                <Col span={12}>
                                    <Form.Item name="on_schema_mismatch" label="Payload 與 Schema 不符時">
                                        <Select options={[
                                            { value: 'strict', label: 'Strict (直接拒絕)' },
                                            { value: 'log_and_store', label: 'Log & Store (記錄並保留 Raw)' },
                                            { value: 'reject', label: 'Reject (丟棄)' }
                                        ]} />
                                    </Form.Item>
                                </Col>
                                <Col span={12}>
                                    <Form.Item name="on_new_field" label="偵測到未知新欄位時">
                                        <Select options={[
                                            { value: 'suggest', label: 'Suggest (保留並於 UI 建議確認)' },
                                            { value: 'auto_create', label: 'Auto Create (自動擴充並建立 Tag)' },
                                            { value: 'ignore', label: 'Ignore (直接丟棄)' }
                                        ]} />
                                    </Form.Item>
                                </Col>
                            </Row>

                            <Row gutter={16}>
                                <Col span={12}>
                                    <Form.Item name="schema_category" label="資料類別 (Category)" rules={[{ required: true }]}>
                                        <Select options={[
                                            { value: 'telemetry', label: 'Telemetry (連續傳感數據)' },
                                            { value: 'status', label: 'Status (設備狀態機)' },
                                            { value: 'alarm', label: 'Alarm (警報事件)' },
                                            { value: 'event', label: 'Event (一般離散事件)' },
                                            { value: 'measurement', label: 'Measurement (品管量測)' },
                                            { value: 'metrics', label: 'Metrics (指標統計資料)' }
                                        ]} />
                                    </Form.Item>
                                </Col>
                            </Row>

                            <Divider style={{ margin: '12px 0' }}>資料欄位定義 (Fields Extraction Rules)</Divider>

                            <Form.List name="fields">
                                {(fields, { add, remove }) => (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                                        {fields.map(({ key, name, ...restField }) => (
                                            <Card
                                                key={key}
                                                size="small"
                                                title={<Text strong style={{ color: 'var(--color-primary)' }}>欄位 #{name + 1}</Text>}
                                                extra={<Button type="text" danger icon={<MinusCircleOutlined />} onClick={() => remove(name)} />}
                                                style={{ background: 'var(--bg-surface-light)', border: '1px solid var(--border-color)' }}
                                            >
                                                <Row gutter={16}>
                                                    <Col span={8}>
                                                        <Form.Item {...restField} name={[name, 'name']} label="Tag 名稱 (name)" rules={[{ required: true }]}>
                                                            <Input placeholder="如: temperature" size="small" />
                                                        </Form.Item>
                                                    </Col>
                                                    <Col span={16}>
                                                        <Form.Item {...restField} name={[name, 'path']} label="提取路徑 (JSONPath)" rules={[{ required: true }]}>
                                                            <Input placeholder="如: $.zones[*].temp" size="small" />
                                                        </Form.Item>
                                                    </Col>
                                                </Row>
                                                <Row gutter={16}>
                                                    <Col span={6}>
                                                        <Form.Item {...restField} name={[name, 'type']} label="型別 (type)" rules={[{ required: true }]}>
                                                            <Select size="small">
                                                                <Select.Option value="float">Float</Select.Option>
                                                                <Select.Option value="integer">Integer</Select.Option>
                                                                <Select.Option value="string">String</Select.Option>
                                                                <Select.Option value="boolean">Boolean</Select.Option>
                                                                <Select.Option value="json">JSON</Select.Option>
                                                            </Select>
                                                        </Form.Item>
                                                    </Col>
                                                    <Col span={6}>
                                                        <Form.Item {...restField} name={[name, 'array_mode']} label="陣列處理 (array_mode)">
                                                            <Select size="small">
                                                                <Select.Option value="single">Single (單一值)</Select.Option>
                                                                <Select.Option value="expand">Expand (展開多筆)</Select.Option>
                                                                <Select.Option value="avg">Avg (取平均)</Select.Option>
                                                                <Select.Option value="last">Last (取最新)</Select.Option>
                                                            </Select>
                                                        </Form.Item>
                                                    </Col>
                                                    <Col span={6}>
                                                        <Form.Item {...restField} name={[name, 'unit']} label="單位 (unit)">
                                                            <Input size="small" placeholder="如: °C" />
                                                        </Form.Item>
                                                    </Col>
                                                    <Col span={6}>
                                                        <Form.Item {...restField} name={[name, 'deadband']} label="濾波 (deadband)">
                                                            <Input size="small" placeholder="如: 0.1 或 change_only" />
                                                        </Form.Item>
                                                    </Col>
                                                </Row>
                                                <Row gutter={16}>
                                                    <Col span={6}>
                                                        <Form.Item {...restField} name={[name, 'extract']} valuePropName="checked" style={{ marginBottom: 0 }}>
                                                            <Switch size="small" checkedChildren="Extract" unCheckedChildren="Skip Extract" />
                                                        </Form.Item>
                                                    </Col>
                                                    <Col span={6}>
                                                        <Form.Item {...restField} name={[name, 'persist']} valuePropName="checked" style={{ marginBottom: 0 }}>
                                                            <Switch size="small" checkedChildren="Persist" unCheckedChildren="No Persist" />
                                                        </Form.Item>
                                                    </Col>
                                                    {watchedCategory !== 'telemetry' && (
                                                        <Col span={12}>
                                                            <Form.Item
                                                                {...restField}
                                                                name={[name, 'target_column']}
                                                                label="目標欄位 (Target Column)"
                                                                tooltip="將此欄位映射到資料庫中的具體欄位。若未映射則自動存入 details (JSONB)。"
                                                            >
                                                                <Select
                                                                    size="small"
                                                                    placeholder="選擇資料庫目標欄位"
                                                                    allowClear
                                                                    options={targetColumnOptions[watchedCategory] || []}
                                                                />
                                                            </Form.Item>
                                                        </Col>
                                                    )}
                                                </Row>
                                            </Card>
                                        ))}
                                        <Button type="dashed" onClick={() => add({ name: '', path: '', type: 'float', extract: true, persist: true, array_mode: 'single' })} block icon={<PlusOutlined />}>
                                            新增提取欄位
                                        </Button>
                                    </div>
                                )}
                            </Form.List>
                        </Form>
                    </Col>

                    {/* Right Panel: Live JSON Preview */}
                    <Col span={10}>
                        <div style={{ position: 'sticky', top: 0 }}>
                            <Typography.Title level={5}>Live Payload Preview</Typography.Title>
                            <Paragraph type="secondary" style={{ fontSize: 13 }}>
                                這是根據您左側配置的 JSONPath ({`$.path`}) 即時生成的 Payload 預覽，幫助您驗證解碼器是否能正確匹配。
                            </Paragraph>
                            <Alert
                                message="此預覽僅支援標準 JSON 展現方式，實際的 Regex/Array 特殊匹配邏輯還是由 Backend Data Engine 負責。"
                                type="info"
                                showIcon
                                style={{ marginBottom: 16, fontSize: 12 }}
                            />
                            <div style={{
                                background: '#1e1e1e',
                                padding: 16,
                                borderRadius: 8,
                                border: '1px solid #333',
                                height: '50vh',
                                overflowY: 'auto'
                            }}>
                                <pre style={{ margin: 0, color: '#9cdcfe', fontFamily: "'Fira Code', 'Consolas', monospace", fontSize: 13 }}>
                                    {JSON.stringify(previewJson, null, 2)}
                                </pre>
                            </div>
                        </div>
                    </Col>
                </Row>
            </Modal>
        </div>
    );
}
