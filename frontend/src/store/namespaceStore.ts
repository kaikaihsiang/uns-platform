/**
 * Namespace Store (Zustand) — Global state for the Namespace tree.
 *
 * Manages treeData, selectedNode, loading states, and provides
 * actions for CRUD + drag-and-drop with optimistic updates.
 */
import { create } from 'zustand';
import { notification } from 'antd';
import type { NodeTreeOut, NodeOut } from '../types/namespace';
import * as api from '../api/namespaceApi';
import type {
    NodeCreateRequest,
    NodeRenameRequest,
    NodePersistenceRequest,
    NodeSchemaUpdateRequest,
} from '../types/namespace';

interface NamespaceState {
    treeData: NodeTreeOut[];
    selectedNode: NodeTreeOut | null;
    isLoading: boolean;

    // Actions
    fetchTree: () => Promise<void>;
    selectNode: (node: NodeTreeOut | null) => void;
    createNode: (body: NodeCreateRequest) => Promise<NodeOut | null>;
    moveNode: (nodeId: number, newParentId: number | null) => Promise<boolean>;
    renameNode: (nodeId: number, body: NodeRenameRequest) => Promise<boolean>;
    deleteNode: (nodeId: number) => Promise<boolean>;
    updatePersistence: (nodeId: number, body: NodePersistenceRequest) => Promise<boolean>;
    updateNodeSchema: (nodeId: number, body: NodeSchemaUpdateRequest) => Promise<boolean>;
}

export const useNamespaceStore = create<NamespaceState>()((set) => ({
    treeData: [],
    selectedNode: null,
    isLoading: false,

    fetchTree: async () => {
        set({ isLoading: true });
        try {
            const data = await api.fetchNamespaceTree();
            set({ treeData: data, isLoading: false });
        } catch {
            set({ isLoading: false });
        }
    },

    selectNode: (node) => {
        set({ selectedNode: node });
    },

    createNode: async (body) => {
        try {
            const node = await api.createNode(body);
            notification.success({ message: '節點建立成功', description: node.full_path });
            // Refetch tree to reflect changes
            await useNamespaceStore.getState().fetchTree();
            return node;
        } catch {
            return null;
        }
    },

    moveNode: async (nodeId, newParentId) => {
        try {
            await api.moveNode(nodeId, { new_parent_id: newParentId });
            notification.success({ message: '節點移動成功', description: 'Live Migration 已完成' });
            await useNamespaceStore.getState().fetchTree();
            return true;
        } catch {
            // Refetch to rollback optimistic update
            await useNamespaceStore.getState().fetchTree();
            return false;
        }
    },

    renameNode: async (nodeId, body) => {
        try {
            const updated = await api.renameNode(nodeId, body);
            notification.success({ message: '節點重新命名成功' });
            
            const { selectedNode, fetchTree } = useNamespaceStore.getState();
            if (selectedNode && selectedNode.node_id === nodeId) {
                set({ selectedNode: { ...selectedNode, ...updated } });
            }
            
            await fetchTree();
            return true;
        } catch {
            return false;
        }
    },

    deleteNode: async (nodeId) => {
        try {
            await api.deleteNode(nodeId);
            notification.success({ message: '節點已刪除' });
            set({ selectedNode: null });
            await useNamespaceStore.getState().fetchTree();
            return true;
        } catch {
            return false;
        }
    },

    updatePersistence: async (nodeId, body) => {
        try {
            const updated = await api.updatePersistence(nodeId, body);
            notification.success({ message: '持久化設定已更新' });
            
            const { selectedNode, fetchTree } = useNamespaceStore.getState();
            if (selectedNode && selectedNode.node_id === nodeId) {
                set({ selectedNode: { ...selectedNode, ...updated } });
            }

            await fetchTree();
            return true;
        } catch {
            return false;
        }
    },

    updateNodeSchema: async (nodeId, body) => {
        try {
            const updated = await api.updateNodeSchema(nodeId, body);
            notification.success({ message: 'Schema 綁定已更新' });
            
            const { selectedNode, fetchTree } = useNamespaceStore.getState();
            if (selectedNode && selectedNode.node_id === nodeId) {
                // 即時合併最新資料到選取的節點，觸發 UI 重新渲染
                set({ selectedNode: { ...selectedNode, ...updated } });
            }

            await fetchTree();
            return true;
        } catch {
            return false;
        }
    },
}));
