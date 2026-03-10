import { create } from 'zustand';
import axios from 'axios';
import type { SchemaTypeOut, SchemaTypeCreate, SchemaTypeUpdate } from '../types/namespace';

interface SchemaState {
    schemas: SchemaTypeOut[];
    suggestions: SchemaTypeOut[];
    isLoading: boolean;
    fetchSchemas: () => Promise<void>;
    fetchSuggestions: () => Promise<void>;
    approveSuggestion: (schemaId: number, category?: string) => Promise<boolean>;
    deleteSchema: (schemaId: number) => Promise<boolean>;
    createSchema: (data: SchemaTypeCreate) => Promise<boolean>;
    updateSchema: (schemaId: number, data: SchemaTypeUpdate) => Promise<boolean>;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const useSchemaStore = create<SchemaState>((set, get) => ({
    schemas: [],
    suggestions: [],
    isLoading: false,

    fetchSchemas: async () => {
        set({ isLoading: true });
        try {
            const res = await axios.get(`${API_BASE}/payload-schemas/`);
            set({ schemas: res.data });
        } catch (err) {
            console.error('Failed to fetch schemas:', err);
        } finally {
            set({ isLoading: false });
        }
    },

    fetchSuggestions: async () => {
        set({ isLoading: true });
        try {
            const res = await axios.get(`${API_BASE}/payload-schemas/suggestions`);
            set({ suggestions: res.data });
        } catch (err) {
            console.error('Failed to fetch suggestions:', err);
        } finally {
            set({ isLoading: false });
        }
    },

    approveSuggestion: async (schemaId: number, category?: string) => {
        try {
            await axios.post(`${API_BASE}/payload-schemas/${schemaId}/approve`, { category });
            await get().fetchSuggestions();
            await get().fetchSchemas();
            return true;
        } catch (err) {
            console.error('Failed to approve suggestion:', err);
            return false;
        }
    },

    deleteSchema: async (schemaId: number) => {
        try {
            await axios.delete(`${API_BASE}/payload-schemas/${schemaId}`);
            await get().fetchSuggestions();
            await get().fetchSchemas();
            return true;
        } catch (err) {
            console.error('Failed to delete schema:', err);
            return false;
        }
    },

    createSchema: async (data) => {
        try {
            await axios.post(`${API_BASE}/payload-schemas/`, data);
            await get().fetchSchemas();
            return true;
        } catch (err) {
            console.error('Failed to create schema:', err);
            return false;
        }
    },

    updateSchema: async (schemaId, data) => {
        try {
            await axios.put(`${API_BASE}/payload-schemas/${schemaId}`, data);
            await get().fetchSchemas();
            return true;
        } catch (err) {
            console.error('Failed to update schema:', err);
            return false;
        }
    },
}));
