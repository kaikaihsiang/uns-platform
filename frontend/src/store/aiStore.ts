import { create } from 'zustand';
import axios from 'axios';

export interface ChatMessage {
    role: 'user' | 'assistant' | 'system';
    content: string;
    tools_used?: ToolCall[];
    timestamp: string;
}

export interface ToolCall {
    name: string;
    args: Record<string, unknown>;
    result: string;
}

interface AiState {
    messages: ChatMessage[];
    isLoading: boolean;

    sendMessage: (text: string) => Promise<void>;
    clearHistory: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const SYSTEM_MSG: ChatMessage = {
    role: 'system',
    content:
        '我是 UNS AI 助手 🤖，可以幫您查詢工廠設備的即時數據、瀏覽 Namespace 結構、分析歷史趨勢。\n\n試著問我：\n- 「列出所有根節點」\n- 「Line1 有哪些設備？」\n- 「Printer 的最新溫度是多少？」',
    timestamp: new Date().toISOString(),
};

export const useAiStore = create<AiState>((set, get) => ({
    messages: [SYSTEM_MSG],
    isLoading: false,

    sendMessage: async (text: string) => {
        const userMsg: ChatMessage = {
            role: 'user',
            content: text,
            timestamp: new Date().toISOString(),
        };
        set((s) => ({ messages: [...s.messages, userMsg], isLoading: true }));

        // Build history (exclude system + current message)
        const history = get()
            .messages.filter((m) => m.role !== 'system')
            .map((m) => ({ role: m.role, content: m.content }));

        try {
            const res = await axios.post(`${API_BASE}/ai/chat`, {
                message: text,
                history: history.slice(0, -1), // exclude current
            });
            const { reply, tools_used } = res.data;
            const aiMsg: ChatMessage = {
                role: 'assistant',
                content: reply,
                tools_used: tools_used || [],
                timestamp: new Date().toISOString(),
            };
            set((s) => ({ messages: [...s.messages, aiMsg], isLoading: false }));
        } catch (err) {
            console.error('AI chat error:', err);
            const errMsg: ChatMessage = {
                role: 'assistant',
                content: '⚠️ 無法連線至 AI 服務，請確認 Backend 是否正常運行。',
                timestamp: new Date().toISOString(),
            };
            set((s) => ({ messages: [...s.messages, errMsg], isLoading: false }));
        }
    },

    clearHistory: () => set({ messages: [SYSTEM_MSG] }),
}));
