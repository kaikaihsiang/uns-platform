/**
 * Namespace Types
 */

export interface NamespaceNode {
    node_id: number;
    parent_id: number | null;
    name: string;
    node_type: 'structural' | 'topic';
    full_path: string;
    schema_id?: number;
    persist_mode?: string;
    retention_days?: number;
    description?: string;
    created_at?: string;
    updated_at?: string;
}

// Alias for backend consistency
export type NodeOut = NamespaceNode;

export interface NodeTreeOut extends NamespaceNode {
    children: NodeTreeOut[];
}

export interface NodeCreateRequest {
    parent_id: number | null;
    name: string;
    node_type: 'structural' | 'topic';
    description?: string;
    schema_id?: number;
}

/**
 * Tag Types
 */
export interface TagOut {
    tag_id: number;
    display_name: string;
    asset_path: string;
    category: string;
    data_point?: string | null;
    unit?: string | null;
    data_type: string;
    description?: string | null;
    created_at?: string;
    last_data_at?: string | null;
}

/**
 * Schema Types
 */
export interface SchemaField {
    name: string;
    path: string;
    type: string;
    unit?: string;
    extract: boolean;
    persist: boolean;
    deadband?: string | number;
    array_mode: 'single' | 'expand' | 'avg' | 'last';
    target_column?: string | null;
}

export interface SchemaTypeOut {
    schema_id: number;
    schema_name: string;
    decoder: string;
    timestamp_field: string | null;
    store_raw: boolean;
    raw_retention_days: number;
    on_schema_mismatch: string;
    on_new_field: string;
    schema_category: string;
    fields: SchemaField[];
    status?: string | null;
    is_suggested: boolean;
    topic_pattern?: string | null;
    version: number;
    created_at?: string;
    updated_at?: string;
}

export interface SchemaTypeCreate {
    schema_name: string;
    decoder: string;
    timestamp_field?: string | null;
    store_raw: boolean;
    raw_retention_days: number;
    on_schema_mismatch: string;
    on_new_field: string;
    schema_category: string;
    fields: SchemaField[];
}

export interface SchemaTypeUpdate {
    schema_name?: string;
    decoder?: string;
    timestamp_field?: string | null;
    store_raw?: boolean;
    raw_retention_days?: number;
    on_schema_mismatch?: string;
    on_new_field?: string;
    schema_category?: string;
    fields?: SchemaField[];
}
