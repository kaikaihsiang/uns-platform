import { create } from 'zustand';
import axios from 'axios';

export interface SystemInfo {
    platform_version: string;
    backend_status: string;
    database: {
        status: string;
        version: string;
        connection_pool: { size: number; checked_out: number };
    };
    mqtt_broker: {
        status: string;
        version: string;
        host: string;
    };
    uptime_seconds: number;
}

export interface MqttStats {
    connected_clients: number;
    topics_count: number;
    subscriptions_count: number;
    messages_received_total: number;
    messages_sent_total: number;
    messages_per_second: number;
    retained_messages_count: number;
}

export interface RetentionPolicy {
    table_name: string;
    retention_days: number | null;
    compression_enabled: boolean;
    compress_after_days: number | null;
}

interface SystemState {
    info: SystemInfo | null;
    mqttStats: MqttStats | null;
    retention: RetentionPolicy[];
    isLoading: boolean;
    wsConnected: boolean;

    fetchInfo: () => Promise<void>;
    fetchMqttStats: () => Promise<void>;
    fetchRetention: () => Promise<void>;

    // WebSocket
    _ws: WebSocket | null;
    connectMqttWs: () => void;
    disconnectMqttWs: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const WS_BASE = API_BASE.replace(/^http/, 'ws');

export const useSystemStore = create<SystemState>((set, get) => ({
    info: null,
    mqttStats: null,
    retention: [],
    isLoading: false,
    wsConnected: false,
    _ws: null,

    fetchInfo: async () => {
        set({ isLoading: true });
        try {
            const res = await axios.get(`${API_BASE}/system/info`);
            set({ info: res.data });
        } catch (err) {
            console.error('Failed to fetch system info:', err);
        } finally {
            set({ isLoading: false });
        }
    },

    fetchMqttStats: async () => {
        try {
            const res = await axios.get(`${API_BASE}/system/mqtt-stats`);
            set({ mqttStats: res.data });
        } catch (err) {
            console.error('Failed to fetch MQTT stats:', err);
        }
    },

    fetchRetention: async () => {
        try {
            const res = await axios.get(`${API_BASE}/system/retention`);
            set({ retention: res.data.policies || res.data || [] });
        } catch (err) {
            console.error('Failed to fetch retention policies:', err);
        }
    },

    connectMqttWs: () => {
        const existing = get()._ws;
        if (existing) existing.close();

        const ws = new WebSocket(`${WS_BASE}/system/mqtt-stats/ws`);
        ws.onopen = () => set({ wsConnected: true });
        ws.onmessage = (evt) => {
            try {
                const data = JSON.parse(evt.data);
                set({ mqttStats: data });
            } catch (e) {
                console.error('WS parse error:', e);
            }
        };
        ws.onclose = () => set({ wsConnected: false, _ws: null });
        ws.onerror = () => {
            console.error('MQTT WebSocket error');
            set({ wsConnected: false });
        };
        set({ _ws: ws });
    },

    disconnectMqttWs: () => {
        const ws = get()._ws;
        if (ws) ws.close();
        set({ _ws: null, wsConnected: false });
    },
}));
