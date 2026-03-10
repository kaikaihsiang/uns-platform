import { create } from 'zustand';
import axios from 'axios';
import type { TagOut, TagDetailOut, TagValueOut, TagCreate } from '../types/namespace';

interface TagState {
    tags: TagOut[];
    currentTagDetail: TagDetailOut | null;
    currentTagValues: TagValueOut[];
    isLoading: boolean;

    fetchTagsByNode: (nodePath: string, recursive?: boolean) => Promise<void>;
    fetchTagDetail: (tagId: number) => Promise<void>;
    fetchTagValues: (tagId: number, limit?: number) => Promise<void>;
    createTag: (data: TagCreate) => Promise<boolean>;
    updateTag: (tagId: number, data: Partial<TagCreate>) => Promise<boolean>;
    deleteTag: (tagId: number) => Promise<boolean>;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export const useTagStore = create<TagState>((set) => ({
    tags: [],
    currentTagDetail: null,
    currentTagValues: [],
    isLoading: false,

    fetchTagsByNode: async (nodePath: string, recursive: boolean = false) => {
        set({ isLoading: true });
        try {
            // Encode the path to handle slashes correctly in the URL
            const res = await axios.get(`${API_BASE}/tags/${encodeURIComponent(nodePath)}/list`, {
                params: { recursive }
            });
            set({ tags: res.data });
        } catch (err) {
            console.error('Failed to fetch tags:', err);
            set({ tags: [] });
        } finally {
            set({ isLoading: false });
        }
    },

    fetchTagDetail: async (tagId: number) => {
        set({ isLoading: true });
        try {
            const res = await axios.get(`${API_BASE}/tags/${tagId}/detail`);
            set({ currentTagDetail: res.data });
        } catch (err) {
            console.error('Failed to fetch tag detail:', err);
            set({ currentTagDetail: null });
        } finally {
            set({ isLoading: false });
        }
    },

    fetchTagValues: async (tagId: number, limit = 100) => {
        set({ isLoading: true });
        try {
            const res = await axios.get(`${API_BASE}/tags/${tagId}/values?limit=${limit}`);
            set({ currentTagValues: res.data.data }); // response is TagValuesResponse { data: TagValueOut[] }
        } catch (err) {
            console.error('Failed to fetch tag values:', err);
            set({ currentTagValues: [] });
        } finally {
            set({ isLoading: false });
        }
    },

    createTag: async (data: TagCreate) => {
        try {
            await axios.post(`${API_BASE}/tags/`, data);
            return true;
        } catch (err) {
            console.error('Failed to create tag:', err);
            return false;
        }
    },

    updateTag: async (tagId: number, data: Partial<TagCreate>) => {
        try {
            await axios.put(`${API_BASE}/tags/${tagId}`, data);
            return true;
        } catch (err) {
            console.error('Failed to update tag:', err);
            return false;
        }
    },

    deleteTag: async (tagId: number) => {
        try {
            await axios.delete(`${API_BASE}/tags/${tagId}`);
            return true;
        } catch (err) {
            console.error('Failed to delete tag:', err);
            return false;
        }
    }
}));
