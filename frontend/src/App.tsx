import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAdmin, RequireAuth } from "./auth/guards";
import { LoginPage } from "./pages/LoginPage";
import { ChatPage } from "./pages/ChatPage";
import { AdminLayout } from "./pages/admin/AdminLayout";
import { DashboardPage } from "./pages/admin/DashboardPage";
import { UsersPage } from "./pages/admin/UsersPage";
import { ChatLogsPage } from "./pages/admin/ChatLogsPage";
import { KnowledgePage } from "./pages/admin/KnowledgePage";
import { PromptsPage } from "./pages/admin/PromptsPage";
import { IntegrationsPage } from "./pages/admin/IntegrationsPage";
import { ActivityPage } from "./pages/admin/ActivityPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <RequireAuth>
            <ChatPage />
          </RequireAuth>
        }
      />

      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminLayout />
          </RequireAdmin>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="chats" element={<ChatLogsPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="prompts" element={<PromptsPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="activity" element={<ActivityPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
