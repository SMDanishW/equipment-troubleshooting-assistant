import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ChatWindow } from "@/components/chat/ChatWindow";

export default function ChatPage() {
  return (
    <ProtectedRoute>
      <ChatWindow />
    </ProtectedRoute>
  );
}
