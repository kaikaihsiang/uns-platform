/**
 * App Root — Routing + AntD Theme Configuration
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme, App as AntApp } from 'antd';
import AppLayout from './components/AppLayout';
import NamespaceEditor from './pages/NamespaceEditor';
import SchemaDetect from './pages/SchemaDetect';
import SchemaManagement from './pages/SchemaManagement';
import TagsOverview from './pages/TagsOverview';
import RecycleBin from './pages/RecycleBin';
import AiChat from './pages/AiChat';
import SystemSettings from './pages/SystemSettings';
import ProductionRunHistory from './pages/ProductionRunHistory';

import './App.css';

// AntD Dark Theme tokens for industrial UI
const industrialTheme = {
  algorithm: theme.darkAlgorithm,
  token: {
    colorPrimary: '#00d2d3',
    colorBgBase: '#0a0e17',
    colorBgContainer: '#111827',
    colorBgElevated: '#1a2332',
    colorBorder: '#1e2d3d',
    colorBorderSecondary: '#2a3a4a',
    colorText: '#e2e8f0',
    colorTextSecondary: '#94a3b8',
    colorTextTertiary: '#64748b',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontSize: 14,
    borderRadius: 6,
    colorSuccess: '#00cec9',
    colorWarning: '#fdcb6e',
    colorError: '#ff7675',
    colorInfo: '#74b9ff',
  },
  components: {
    Layout: {
      siderBg: '#111827',
      headerBg: '#111827',
      bodyBg: '#0a0e17',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(0, 210, 211, 0.08)',
      darkItemColor: '#94a3b8',
      darkItemSelectedColor: '#00d2d3',
      darkItemHoverColor: '#e2e8f0',
      darkItemHoverBg: 'rgba(255, 255, 255, 0.04)',
    },
    Tree: {
      directoryNodeSelectedBg: 'rgba(0, 210, 211, 0.08)',
      nodeSelectedBg: 'rgba(0, 210, 211, 0.08)',
    },
    Modal: {
      contentBg: '#1a2332',
      headerBg: '#1a2332',
    },
    notification: {
      colorBgElevated: '#1a2332',
    },
  },
};

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: 'var(--text-muted)',
        fontSize: 16,
      }}
    >
      {title} — 開發中
    </div>
  );
}

export default function App() {
  return (
    <ConfigProvider theme={industrialTheme}>
      <AntApp>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/namespace" element={<NamespaceEditor />} />
              <Route path="/tags" element={<TagsOverview />} />
              <Route path="/schemas" element={<SchemaManagement />} />
              <Route path="/schema-detect" element={<SchemaDetect />} />
              <Route path="/run-history" element={<ProductionRunHistory />} />
              <Route path="/recycle-bin" element={<RecycleBin />} />
              <Route path="/ai-assistant" element={<AiChat />} />
              <Route path="/dashboard" element={<PlaceholderPage title="儀表板" />} />
              <Route path="/settings" element={<SystemSettings />} />
              <Route path="*" element={<Navigate to="/namespace" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}
