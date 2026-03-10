import { create } from 'zustand';
import axios from 'axios';
import type { NodeOut, SchemaTypeOut, TagOut } from '../types/namespace';

interface RecycleBinState {
    deletedNodes: NodeOut[];
    deletedSchemas: SchemaTypeOut[];
    deletedTags: TagOut[];
    isLoading: boolean;

    fetchDeletedNodes: () => Promise<void>;
    fetchDeletedSchemas: () => Promise<void>;
    fetchDeletedTags: () => Promise<void>;

    restoreNode: (id: number) => Promise<boolean>;
    restoreSchema: (id: number) => Promise<boolean>;
    restoreTag: (id: number) => Promise<boolean>;

    hardDeleteNode: (id: number) => Promise<boolean>;
    hardDeleteSchema: (id: number) => Promise<boolean>;
    hardDeleteTag: (id: number) => Promise<boolean>;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const useRecycleBinStore = create<RecycleBinState>((set, get) => ({
    deletedNodes: [],
    deletedSchemas: [],
    deletedTags: [],
    isLoading: false,

    // ─── Fetch Deleted ───────────────────────────────────────────

    fetchDeletedNodes: async () => {
        set({ isLoading: true });
        try {
            const res = await axios.get(`${API_BASE}/namespace/nodes/deleted`);
            set({ deletedNodes: res.data });
        } catch (err) {
            console.error('Failed to fetch deleted nodes:', err);
            set({ deletedNodes: [] });
        } finally {
            set({ isLoading: false });
        }
    },

    fetchDeletedSchemas: async () => {
        set({ isLoading: true });
        try {
            const res = await axios.get(`${API_BASE}/payload-schemas/deleted`);
            set({ deletedSchemas: res.data });
        } catch (err) {
            console.error('Failed to fetch deleted schemas:', err);
            set({ deletedSchemas: [] });
        } finally {
            set({ isLoading: false });
        }
    },

    fetchDeletedTags: async () => {
        set({ isLoading: true });
        try {
            const res = await axios.get(`${API_BASE}/tags/deleted`);
            set({ deletedTags: res.data });
        } catch (err) {
            console.error('Failed to fetch deleted tags:', err);
            set({ deletedTags: [] });
        } finally {
            set({ isLoading: false });
        }
    },

    // ─── Restore ─────────────────────────────────────────────────

    restoreNode: async (id: number) => {
        try {
            await axios.put(`${API_BASE}/namespace/nodes/${id}/restore`);
            await get().fetchDeletedNodes();
            return true;
        } catch (err) {
            console.error('Failed to restore node:', err);
            return false;
        }
    },

    restoreSchema: async (id: number) => {
        try {
            await axios.put(`${API_BASE}/payload-schemas/${id}/restore`);
            await get().fetchDeletedSchemas();
            return true;
        } catch (err) {
            console.error('Failed to restore schema:', err);
            return false;
        }
    },

    restoreTag: async (id: number) => {
        try {
            await axios.put(`${API_BASE}/tags/${id}/restore`);
            await get().fetchDeletedTags();
            return true;
        } catch (err) {
            console.error('Failed to restore tag:', err);
            return false;
        }
    },

    // ─── Hard Delete ─────────────────────────────────────────────

    hardDeleteNode: async (id: number) => {
        try {
            await axios.delete(`${API_BASE}/namespace/nodes/${id}/hard`);
            await get().fetchDeletedNodes();
            return true;
        } catch (err) {
            console.error('Failed to hard delete node:', err);
            return false;
        }
    },

    hardDeleteSchema: async (id: number) => {
        try {
            await axios.delete(`${API_BASE}/payload-schemas/${id}/hard`);
            await get().fetchDeletedSchemas();
            return true;
        } catch (err) {
            console.error('Failed to hard delete schema:', err);
            return false;
        }
    },

    hardDeleteTag: async (id: number) => {
        try {
            await axios.delete(`${API_BASE}/tags/${id}/hard`);
            await get().fetchDeletedTags();
            return true;
        } catch (err) {
            console.error('Failed to hard delete tag:', err);
            return false;
        }
    },
}));
