import { AdminAuthProvider, useAdminAuth } from "./AdminAuthContext";
import { AdminKeyGate } from "./AdminKeyGate";
import { AdminDashboard } from "./AdminDashboard";

function AdminPageContent() {
  const { isUnlocked } = useAdminAuth();
  return isUnlocked ? <AdminDashboard /> : <AdminKeyGate />;
}

export function AdminPage() {
  return (
    <AdminAuthProvider>
      <AdminPageContent />
    </AdminAuthProvider>
  );
}
