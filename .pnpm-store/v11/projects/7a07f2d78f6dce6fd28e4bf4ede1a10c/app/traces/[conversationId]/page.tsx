import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { TraceDashboard } from "@/components/traces/TraceDashboard";

type TracePageProps = {
  params: Promise<{
    conversationId: string;
  }>;
};

export default async function TracePage({ params }: TracePageProps) {
  const { conversationId } = await params;

  return (
    <ProtectedRoute>
      <TraceDashboard conversationId={conversationId} />
    </ProtectedRoute>
  );
}
