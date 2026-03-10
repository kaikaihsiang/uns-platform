/**
 * Auth Store — Mock Auth per ADR-001.
 * 
 * PoC 階段寫死 Admin 身分。未來接入 OIDC 後，
 * 只需修改此 Store 的 login/logout 邏輯。
 */
import { create } from 'zustand';

interface User {
    name: string;
    role: 'admin' | 'engineer' | 'operator' | 'readonly';
}

interface AuthState {
    currentUser: User;
    isAuthenticated: boolean;
}

export const useAuthStore = create<AuthState>()(() => ({
    currentUser: { name: 'Admin', role: 'admin' },
    isAuthenticated: true,
}));
