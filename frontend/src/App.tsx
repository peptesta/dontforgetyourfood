import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import BatchFlowPage from "./pages/BatchFlowPage";
import LoginPage from "./pages/LoginPage";
import PantryListPage from "./pages/PantryListPage";
import ReceiptFlowPage from "./pages/ReceiptFlowPage";
import RegisterPage from "./pages/RegisterPage";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth();

  if (status === "loading") {
    return <div className="flex min-h-svh items-center justify-center text-slate-500">Cargando…</div>;
  }
  if (status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <PantryListPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/batch"
        element={
          <ProtectedRoute>
            <BatchFlowPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/receipt"
        element={
          <ProtectedRoute>
            <ReceiptFlowPage />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
