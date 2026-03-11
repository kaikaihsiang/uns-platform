import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useNamespaceStore } from '../store/namespaceStore';
import * as api from '../api/namespaceApi';
import { NodeTreeOut, NodeOut } from '../types/namespace';

// Mock the API module
vi.mock('../api/namespaceApi', () => ({
    fetchNamespaceTree: vi.fn(),
    updateNodeSchema: vi.fn(),
    // Add other mocks if needed
}));

describe('useNamespaceStore', () => {
    beforeEach(() => {
        // Reset Zustand store state before each test
        useNamespaceStore.setState({
            treeData: [],
            selectedNode: null,
            isLoading: false
        });
        vi.clearAllMocks();
    });

    it('should update selectedNode state when updateNodeSchema succeeds', async () => {
        // 1. Initial State: A selected topic node
        const initialNode: NodeTreeOut = {
            node_id: 10,
            parent_id: 1,
            name: 'Telemetry',
            node_type: 'topic',
            full_path: 'Line1/Telemetry',
            schema_id: null,
            children: []
        };
        
        useNamespaceStore.setState({ selectedNode: initialNode });

        // 2. Mock API Response
        const updatedNode: NodeOut = {
            ...initialNode,
            schema_id: 42,
            updated_at: new Date().toISOString()
        };
        vi.mocked(api.updateNodeSchema).mockResolvedValue(updatedNode);
        vi.mocked(api.fetchNamespaceTree).mockResolvedValue([updatedNode as NodeTreeOut]);

        // 3. Execute Action
        const success = await useNamespaceStore.getState().updateNodeSchema(10, { schema_id: 42 });

        // 4. Verification
        expect(success).toBe(true);
        const currentState = useNamespaceStore.getState();
        
        // Ensure selectedNode is merged with updated data
        expect(currentState.selectedNode?.schema_id).toBe(42);
        
        // Ensure fetchTree was triggered to sync the left panel
        expect(api.fetchNamespaceTree).toHaveBeenCalled();
    });

    it('should not update state when updateNodeSchema fails', async () => {
        const initialNode: NodeTreeOut = {
            node_id: 10,
            parent_id: 1,
            name: 'Telemetry',
            node_type: 'topic',
            full_path: 'Line1/Telemetry',
            schema_id: null,
            children: []
        };
        
        useNamespaceStore.setState({ selectedNode: initialNode });

        // Mock API Failure
        vi.mocked(api.updateNodeSchema).mockRejectedValue(new Error('Network Error'));

        // Execute Action
        const success = await useNamespaceStore.getState().updateNodeSchema(10, { schema_id: 42 });

        // Verification
        expect(success).toBe(false);
        const currentState = useNamespaceStore.getState();
        
        // selectedNode should remain unchanged
        expect(currentState.selectedNode?.schema_id).toBe(null);
    });
});
