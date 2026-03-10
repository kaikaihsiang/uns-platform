/**
 * Namespace API — All REST calls for Namespace CRUD.
 * Matches backend endpoints in PROGRESS.md API Contract Log.
 */
import apiClient from './client';
import type {
    NodeTreeOut,
    NodeOut,
    NodeCreateRequest,
    NodeMoveRequest,
    NodeRenameRequest,
    NodePersistenceRequest,
} from '../types/namespace';

/** GET /namespace/tree — 取得完整巢狀樹 */
export async function fetchNamespaceTree(): Promise<NodeTreeOut[]> {
    const { data } = await apiClient.get<NodeTreeOut[]>('/namespace/tree');
    return data;
}

/** POST /namespace/nodes — 建立 Node */
export async function createNode(body: NodeCreateRequest): Promise<NodeOut> {
    const { data } = await apiClient.post<NodeOut>('/namespace/nodes', body);
    return data;
}

/** PUT /namespace/nodes/{id}/move — 移動 Node（觸發 Live Migration）*/
export async function moveNode(nodeId: number, body: NodeMoveRequest): Promise<NodeOut> {
    const { data } = await apiClient.put<NodeOut>(`/namespace/nodes/${nodeId}/move`, body);
    return data;
}

/** PUT /namespace/nodes/{id}/rename — 重新命名 */
export async function renameNode(nodeId: number, body: NodeRenameRequest): Promise<NodeOut> {
    const { data } = await apiClient.put<NodeOut>(`/namespace/nodes/${nodeId}/rename`, body);
    return data;
}

/** DELETE /namespace/nodes/{id} — Soft delete */
export async function deleteNode(nodeId: number): Promise<NodeOut> {
    const { data } = await apiClient.delete<NodeOut>(`/namespace/nodes/${nodeId}`);
    return data;
}

/** PUT /namespace/nodes/{id}/persistence — 設定 persist_mode */
export async function updatePersistence(
    nodeId: number,
    body: NodePersistenceRequest
): Promise<NodeOut> {
    const { data } = await apiClient.put<NodeOut>(`/namespace/nodes/${nodeId}/persistence`, body);
    return data;
}
