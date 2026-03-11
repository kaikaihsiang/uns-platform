import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import TagsOverview from '../pages/TagsOverview';
import { useTagStore } from '../store/tagStore';
import { useNamespaceStore } from '../store/namespaceStore';

// 1. Mock Stores
vi.mock('../store/tagStore', () => ({
    useTagStore: vi.fn(),
}));

vi.mock('../store/namespaceStore', () => ({
    useNamespaceStore: vi.fn(),
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
