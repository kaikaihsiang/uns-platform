import { useEffect, useRef, useState } from 'react';
import { Input, Button, Typography, Space, Collapse, Spin, Tooltip } from 'antd';
import {
    SendOutlined,
    ClearOutlined,
    RobotOutlined,
    UserOutlined,
    InfoCircleOutlined,
    ToolOutlined,
} from '@ant-design/icons';
import { useAiStore, type ChatMessage, type ToolCall } from '../store/aiStore';

const { Text } = Typography;

// ─── Tool Call Badge ─────────────────────────────────────────

function ToolCallBadge({ tools }: { tools: ToolCall[] }) {
    if (!tools || tools.length === 0) return null;

    const items = tools.map((tool, i) => ({
        key: String(i),
        label: (
            <Space size={4}>
                <ToolOutlined style={{ color: 'var(--color-primary)' }} />
                <Text strong style={{ color: 'var(--color-primary)', fontSize: 12 }}>
                    {tool.name}
                </Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                    ({JSON.stringify(tool.args)})
                </Text>
            </Space>
        ),
        children: (
            <pre
                style={{
                    background: 'rgba(0,0,0,0.3)',
                    padding: 8,
                    borderRadius: 4,
                    fontSize: 11,
                    maxHeight: 200,
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                }}
            >
                {(() => {
                    try {
                        return JSON.stringify(JSON.parse(tool.result), null, 2);
                    } catch {
                        return tool.result;
                    }
                })()}
            </pre>
        ),
    }));

    return (
        <Collapse
            ghost
            size="small"
            items={items}
            style={{ marginTop: 8, background: 'rgba(0,210,211,0.05)', borderRadius: 6 }}
        />
    );
}

// ─── Message Bubble ──────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
    const isUser = msg.role === 'user';
    const isSystem = msg.role === 'system';

    const avatar = isUser ? (
        <UserOutlined style={{ fontSize: 18, color: '#00d2d3' }} />
    ) : isSystem ? (
        <InfoCircleOutlined style={{ fontSize: 18, color: '#636e72' }} />
    ) : (
        <RobotOutlined style={{ fontSize: 18, color: '#6c5ce7' }} />
    );

    const bubbleStyle: React.CSSProperties = {
        background: isUser
            ? 'linear-gradient(135deg, rgba(0,210,211,0.15), rgba(0,210,211,0.05))'
            : isSystem
                ? 'rgba(99,110,114,0.1)'
                : 'linear-gradient(135deg, rgba(108,92,231,0.15), rgba(108,92,231,0.05))',
        border: isUser
            ? '1px solid rgba(0,210,211,0.2)'
            : isSystem
                ? '1px solid rgba(99,110,114,0.2)'
                : '1px solid rgba(108,92,231,0.2)',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        padding: '12px 16px',
        maxWidth: '85%',
        alignSelf: isUser ? 'flex-end' : 'flex-start',
    };

    const timeStr = new Date(msg.timestamp).toLocaleTimeString('zh-TW', {
        hour: '2-digit',
        minute: '2-digit',
    });

    return (
        <div
            style={{
                display: 'flex',
                flexDirection: isUser ? 'row-reverse' : 'row',
                alignItems: 'flex-start',
                gap: 8,
                marginBottom: 16,
            }}
        >
            <div
                style={{
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: 'rgba(255,255,255,0.05)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                }}
            >
                {avatar}
            </div>
            <div style={bubbleStyle}>
                <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, fontSize: 14 }}>
                    {msg.content}
                </div>
                {msg.tools_used && <ToolCallBadge tools={msg.tools_used} />}
                <div style={{ textAlign: 'right', marginTop: 6 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                        {timeStr}
                    </Text>
                </div>
            </div>
        </div>
    );
}

// ─── Main Page ───────────────────────────────────────────────

export default function AiChat() {
    const { messages, isLoading, sendMessage, clearHistory } = useAiStore();
    const [input, setInput] = useState('');
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async () => {
        const trimmed = input.trim();
        if (!trimmed || isLoading) return;
        setInput('');
        await sendMessage(trimmed);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                padding: 0,
                overflow: 'hidden',
            }}
        >
            {/* Header */}
            <div
                style={{
                    padding: '16px 24px',
                    borderBottom: '1px solid rgba(255,255,255,0.06)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                }}
            >
                <Space>
                    <RobotOutlined style={{ fontSize: 24, color: '#6c5ce7' }} />
                    <div>
                        <Text strong style={{ fontSize: 18 }}>
                            AI 助手
                        </Text>
                        <br />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            透過 MCP 工具查詢工廠資料 — Powered by Gemini
                        </Text>
                    </div>
                </Space>
                <Tooltip title="清除對話">
                    <Button
                        icon={<ClearOutlined />}
                        onClick={clearHistory}
                        type="text"
                        style={{ color: 'var(--text-muted)' }}
                    >
                        清除
                    </Button>
                </Tooltip>
            </div>

            {/* Messages Area */}
            <div
                style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '16px 24px',
                    display: 'flex',
                    flexDirection: 'column',
                }}
            >
                {messages.map((msg, idx) => (
                    <MessageBubble key={idx} msg={msg} />
                ))}

                {isLoading && (
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                            padding: '8px 16px',
                            alignSelf: 'flex-start',
                        }}
                    >
                        <Spin size="small" />
                        <Text type="secondary" style={{ fontSize: 13 }}>
                            AI 正在思考...
                        </Text>
                    </div>
                )}

                <div ref={bottomRef} />
            </div>

            {/* Input Area */}
            <div
                style={{
                    padding: '12px 24px 16px',
                    borderTop: '1px solid rgba(255,255,255,0.06)',
                    background: 'rgba(0,0,0,0.2)',
                }}
            >
                <div style={{ display: 'flex', gap: 8 }}>
                    <Input.TextArea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="請問工廠設備的問題... (Enter 送出, Shift+Enter 換行)"
                        autoSize={{ minRows: 1, maxRows: 4 }}
                        disabled={isLoading}
                        style={{
                            flex: 1,
                            borderRadius: 12,
                            background: 'rgba(255,255,255,0.05)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            resize: 'none',
                        }}
                    />
                    <Button
                        type="primary"
                        icon={<SendOutlined />}
                        onClick={handleSend}
                        loading={isLoading}
                        style={{
                            height: 'auto',
                            borderRadius: 12,
                            minWidth: 56,
                            background: 'linear-gradient(135deg, #6c5ce7, #00d2d3)',
                            border: 'none',
                        }}
                    />
                </div>
                <div style={{ textAlign: 'center', marginTop: 8 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                        AI 回覆基於 MCP 工具查詢結果，可能不完全準確
                    </Text>
                </div>
            </div>
        </div>
    );
}
