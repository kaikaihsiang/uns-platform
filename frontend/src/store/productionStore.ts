import { create } from 'zustand';
import api from '../api/client';

export interface ProductionRun {
    run_id: number;
    equipment_path: string;
    lot_id: string;
    recipe_id: string | null;
    product_id?: string | null;
    step_id?: string | null;
    status: string;
    operator_id?: string | null;
    start_time: string;
    end_time: string | null;
    context?: Record<string, any> | null;
}

interface ProductionState {
    activeRuns: ProductionRun[];
    historyRuns: ProductionRun[];
    isLoading: boolean;
    error: string | null;

    fetchActiveRuns: (equipmentPath?: string) => Promise<void>;
    searchHistoryRuns: (params?: { equipment_path?: string; lot_id?: string; start_time?: string }) => Promise<void>;
}

export const useProductionStore = create<ProductionState>((set) => ({
    activeRuns: [],
    historyRuns: [],
    isLoading: false,
    error: null,

    fetchActiveRuns: async (equipmentPath) => {
        set({ isLoading: true, error: null });
        try {
            const url = equipmentPath
                ? `/production-runs/active?equipment_path=${encodeURIComponent(equipmentPath)}`
                : '/production-runs/active';
            const response = await api.get(url);
            set({ activeRuns: response.data, isLoading: false });
        } catch (error: any) {
            set({
                error: error.response?.data?.detail || 'Failed to fetch active runs',
                isLoading: false
            });
        }
    },

    searchHistoryRuns: async (params) => {
        set({ isLoading: true, error: null });
        try {
            const response = await api.get('/production-runs/search', { params });
            set({ historyRuns: response.data, isLoading: false });
        } catch (error: any) {
            set({
                error: error.response?.data?.detail || 'Failed to search history runs',
                isLoading: false
            });
        }
    }
}));
