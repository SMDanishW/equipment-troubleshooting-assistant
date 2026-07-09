import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { DocumentsDashboard } from "@/components/documents/DocumentsDashboard";

export default function DocumentsPage() {
  return (
    <ProtectedRoute>
      <DocumentsDashboard />
    </ProtectedRoute>
  );
}
