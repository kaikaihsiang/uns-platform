/**
 * Axios HTTP Client — Centralized API client with Mock Auth interceptor.
 * 
 * ADR-001: PoC 階段硬編碼 Mock Token，未來切換至 OIDC 只需修改此檔案。
 */
import axios from 'axios';
import { notification } from 'antd';

const apiClient = axios.create({
    baseURL: '/api/v1',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// ── Request Interceptor: Inject Mock Auth Token (ADR-001) ──
apiClient.interceptors.request.use((config) => {
    // TODO: Replace with real OIDC token when moving beyond PoC
    config.headers.Authorization = 'Bearer mock-token-admin';
    return config;
});

// ── Response Interceptor: Centralized Error Handling ──
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        const status = error.response?.status;
        const detail = error.response?.data?.detail || error.message;

        if (status === 401 || status === 403) {
            notification.error({
                message: '權限不足',
                description: '您沒有執行此操作的權限。',
            });
        } else if (status === 404) {
            notification.warning({
                message: '資源不存在',
                description: detail,
            });
        } else if (status && status >= 400) {
            notification.error({
                message: `操作失敗 (${status})`,
                description: detail,
            });
        } else {
            notification.error({
                message: '網路錯誤',
                description: '無法連線到伺服器，請檢查後端服務是否正在執行。',
            });
        }

        return Promise.reject(error);
    }
);

export default apiClient;
