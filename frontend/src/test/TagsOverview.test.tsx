import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import TagsOverview from '../pages/TagsOverview';

// 0. Global Mocks for Ant Design / JSDOM issues
global.matchMedia = global.matchMedia || function() {
    return {
        matches: false,
        addListener: function() {},
        removeListener: function() {}
    };
};

class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
}
global.ResizeObserver = ResizeObserver;

// 1. Mock Stores
vi.mock('../store/tagStore', () => ({
    useTagStore: vi.fn(),
}));

vi.mock('../store/namespaceStore', () => ({
    useNamespaceStore: vi.fn(),
}));

vi.mock('../store/schemaStore', () => ({
    useSchemaStore: vi.fn(),
}));

// 2. Mock Recharts (Avoid rendering complexity in JSDOM)
vi.mock('recharts', () => ({
    ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
    LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
    ScatterChart: ({ children }: any) => <div data-testid="scatter-chart">{children}</div>,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
    Line: () => null,
    Scatter: () => null,
    Cell: () => null,
    ReferenceLine: () => null,
}));

import { useTagStore } from '../store/tagStore';
import { useNamespaceStore } from '../store/namespaceStore';
import { useSchemaStore } from '../store/schemaStore';

describe('TagsOverview Categorical History Trends', () => {
    const mockTags = [
        { tag_id: 1, display_name: 'Temp', category: 'telemetry', asset_path: 'Line1/Printer', data_type: 'float', unit: '°C' },
        { tag_id: 2, display_name: 'Machine State', category: 'status', asset_path: 'Line1/Printer', data_type: 'string' },
        { tag_id: 3, display_name: 'SPC Check', category: 'measurement', asset_path: 'Line1/Printer', data_type: 'float', unit: 'mm' },
    ];

    const mockFetchTags = vi.fn();
    const mockFetchTagValues = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();
        
        // Default Mock Store Implementation
        (useNamespaceStore as any).mockReturnValue({
            treeData: [],
            fetchTree: vi.fn(),
            isLoading: false,
        });

        (useTagStore as any).mockReturnValue({
            tags: mockTags,
            currentTagValues: [],
            isLoading: false,
            fetchTagsByNode: mockFetchTags,
            fetchTagValues: mockFetchTagValues,
        });

        (useSchemaStore as any).mockReturnValue({
            fetchSchemas: vi.fn(),
            getSchemaById: vi.fn(),
        });
    });

    it('renders tag list correctly', async () => {
        render(<TagsOverview />);
        expect(screen.getByText('Tag 總覽')).toBeInTheDocument();
        expect(screen.getByText('Temp')).toBeInTheDocument();
        expect(screen.getByText('Machine State')).toBeInTheDocument();
    });

    it('opens history drawer and shows LineChart for telemetry', async () => {
        const telemetryValues = [
            { time: '2026-03-11T10:00:00Z', value: 25.5, quality: 'good' }
        ];

        (useTagStore as any).mockReturnValue({
            tags: mockTags,
            currentTagValues: telemetryValues,
            isLoading: false,
            fetchTagsByNode: mockFetchTags,
            fetchTagValues: mockFetchTagValues,
        });

        render(<TagsOverview />);
        
        // Find "歷史趨勢" button for the first tag (Temp)
        const historyButtons = screen.getAllByText('歷史趨勢');
        fireEvent.click(historyButtons[0]);

        // Should call fetch
        expect(mockFetchTagValues).toHaveBeenCalledWith(1, 100);
        
        // Should show LineChart
        await waitFor(() => {
            expect(screen.getByTestId('line-chart')).toBeInTheDocument();
        });
    });

    it('shows Status specific columns in history table for status category', async () => {
        const statusValues = [
            { time: '2026-03-11T10:05:00Z', state_code: 'RUN', mode: 'AUTO', lot_id: 'LOT-123' }
        ];

        (useTagStore as any).mockReturnValue({
            tags: mockTags,
            currentTagValues: statusValues,
            isLoading: false,
            fetchTagsByNode: mockFetchTags,
            fetchTagValues: mockFetchTagValues,
        });

        render(<TagsOverview />);
        
        // Click history for second tag (Machine State - status)
        const historyButtons = screen.getAllByText('歷史趨勢');
        fireEvent.click(historyButtons[1]);

        await waitFor(() => {
            // Check for status specific column headers
            expect(screen.getByText('狀態碼')).toBeInTheDocument();
            expect(screen.getByText('模式')).toBeInTheDocument();
            expect(screen.getByText('Lot ID')).toBeInTheDocument();
            // Check for the value
            expect(screen.getByText('RUN')).toBeInTheDocument();
            expect(screen.getByText('AUTO')).toBeInTheDocument();
        });
    });

    it('supports sorting in the history table', async () => {
        const telemetryValues = [
            { time: '2026-03-11T10:00:00Z', value: 20 },
            { time: '2026-03-11T10:01:00Z', value: 30 }
        ];

        (useTagStore as any).mockReturnValue({
            tags: mockTags,
            currentTagValues: telemetryValues,
            isLoading: false,
            fetchTagsByNode: mockFetchTags,
            fetchTagValues: mockFetchTagValues,
        });

        render(<TagsOverview />);
        fireEvent.click(screen.getAllByText('歷史趨勢')[0]);

        await waitFor(() => {
            const timeHeader = screen.getByText('時間 (Time)');
            // Ant Design table headers have sorter classes if enabled
            expect(timeHeader.closest('th')).toHaveClass('ant-table-column-has-sorters');
        });
    });
});

describe('TagsOverview Edit Permissions', () => {
    const mockTags = [
        { tag_id: 1, display_name: 'Temp', category: 'telemetry', asset_path: 'Line1/Printer', data_type: 'float', data_point: 'temp1' },
        { tag_id: 2, display_name: 'Alarm', category: 'alarm', asset_path: 'Line1/Printer', data_type: 'string', data_point: 'main_alarm' },
    ];

    const mockFetchTags = vi.fn();
    const mockUpdateTag = vi.fn();

    beforeEach(() => {
        vi.clearAllMocks();
        (useTagStore as any).mockReturnValue({
            tags: mockTags,
            currentTagValues: [],
            isLoading: false,
            fetchTagsByNode: mockFetchTags,
            updateTag: mockUpdateTag,
        });
        (useNamespaceStore as any).mockReturnValue({
            treeData: [
                { name: 'Printer', full_path: 'Line1/Printer', node_type: 'topic' }
            ],
            fetchTree: vi.fn(),
            isLoading: false,
        });
        (useSchemaStore as any).mockReturnValue({
            fetchSchemas: vi.fn(),
            getSchemaById: vi.fn(),
        });
    });

    it('allows editing Data Point for telemetry category', async () => {
        render(<TagsOverview />);
        
        // Find Edit button for Temp (telemetry)
        const editButtons = screen.getAllByRole('button', { name: /edit/i });
        fireEvent.click(editButtons[0]);

        // Expect Modal to be open
        expect(screen.getByText('編輯 Tag 資料點')).toBeInTheDocument();
        
        // Data Point should be editable (Input not disabled)
        const dataPointInput = screen.getByLabelText(/主題後綴/);
        expect(dataPointInput).not.toBeDisabled();
        
        // Other fields like Display Name should be editable
        const displayNameInput = screen.getByLabelText(/顯示名稱/);
        expect(displayNameInput).not.toBeDisabled();
    });

    it('restricts editing Data Point for non-telemetry categories (e.g. alarm)', async () => {
        render(<TagsOverview />);
        
        // Find Edit button for Alarm (non-telemetry)
        const editButtons = screen.getAllByRole('button', { name: /edit/i });
        fireEvent.click(editButtons[1]);

        expect(screen.getByText('編輯 Tag 資料點')).toBeInTheDocument();
        
        // Label should be "來源欄位"
        expect(screen.getByText('來源欄位 (Source Field / JSON Key)')).toBeInTheDocument();
        
        // Data Point should be disabled in edit mode for non-telemetry
        // Note: Depending on whether schema is bound, it might be a Select or Input
        const dataPointField = screen.getByLabelText(/來源欄位/);
        expect(dataPointField).toBeDisabled();
        
        // But Category and Description should be editable
        const categorySelect = screen.getByLabelText(/分類/);
        expect(categorySelect).not.toBeDisabled();
    });
});

