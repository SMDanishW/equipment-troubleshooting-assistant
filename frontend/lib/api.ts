export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type ApiOptions = {
  method?: string;
  token?: string | null;
  body?: unknown;
  headers?: HeadersInit;
};

export type User = {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: "bearer";
  user: User;
};

export type DocumentStatus = "processing" | "indexed" | "failed";

export type EquipmentDocument = {
  id: string;
  filename: string;
  equipment_name: string;
  document_type: string;
  page_count: number;
  text_chunks_count: number;
  images_extracted_count: number;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
};

export type DockerLogResponse = {
  service: string;
  tail: number;
  logs: string;
};

export type CitationDetail = {
  id: string;
  type: "text" | "image";
  source_file: string;
  document_id: string;
  page: number;
  page_end: number | null;
  excerpt: string | null;
  image_url: string | null;
  pdf_url: string | null;
  highlighted_pdf_url: string | null;
  caption: string | null;
  related_text: string | null;
  width: number | null;
  height: number | null;
};

export type AgentTrace = {
  id: string;
  sequence: number;
  agent_name: string;
  status: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  started_at: string;
  completed_at: string;
};

export type ConversationTrace = {
  id: string;
  question: string;
  equipment_name: string | null;
  final_answer: string | null;
  status: string;
  created_at: string;
  completed_at: string | null;
  agent_traces: AgentTrace[];
};

export type AdminConversation = {
  id: string;
  question: string;
  equipment_name: string | null;
  final_answer: string | null;
  status: string;
  created_at: string;
  completed_at: string | null;
};

export type AdminUserOverview = User & {
  documents_count: number;
  conversations_count: number;
  documents: EquipmentDocument[];
  conversations: AdminConversation[];
};

export async function apiRequest<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body:
      options.body === undefined
        ? undefined
        : options.body instanceof FormData
          ? options.body
          : JSON.stringify(options.body),
  });

  if (!response.ok) {
    let message = `API request failed with ${response.status}`;
    try {
      const errorBody = (await response.json()) as { detail?: string };
      if (errorBody.detail) {
        message = errorBody.detail;
      }
    } catch {
      // Keep the fallback message.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string, token?: string): Promise<T> {
  return apiRequest<T>(path, { token });
}

export async function login(identifier: string, password: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/login", {
    method: "POST",
    body: { identifier, password },
  });
}

export async function register(username: string, email: string, password: string): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/register", {
    method: "POST",
    body: { username, email, password },
  });
}

export async function getCurrentUser(token: string): Promise<User> {
  return apiGet<User>("/auth/me", token);
}

export async function listDocuments(token: string): Promise<EquipmentDocument[]> {
  return apiGet<EquipmentDocument[]>("/documents", token);
}

export async function uploadDocument(
  token: string,
  payload: {
    file: File;
    equipmentName: string;
    documentType: string;
  },
): Promise<EquipmentDocument> {
  const formData = new FormData();
  formData.append("file", payload.file);
  formData.append("equipment_name", payload.equipmentName);
  formData.append("document_type", payload.documentType);

  return apiRequest<EquipmentDocument>("/documents/upload", {
    method: "POST",
    token,
    body: formData,
  });
}

export async function deleteDocument(token: string, documentId: string): Promise<void> {
  return apiRequest<void>(`/documents/${documentId}`, {
    method: "DELETE",
    token,
  });
}

export async function listDockerLogServices(token: string): Promise<string[]> {
  const response = await apiGet<{ services: string[] }>("/admin/docker/services", token);
  return response.services;
}

export async function getDockerLogs(token: string, service: string, tail: number): Promise<DockerLogResponse> {
  return apiGet<DockerLogResponse>(
    `/admin/docker/logs?service=${encodeURIComponent(service)}&tail=${encodeURIComponent(String(tail))}`,
    token,
  );
}

export async function getCitation(token: string, citationId: string): Promise<CitationDetail> {
  return apiGet<CitationDetail>(`/citations/${encodeURIComponent(citationId)}`, token);
}

export async function getTrace(token: string, conversationId: string): Promise<ConversationTrace> {
  return apiGet<ConversationTrace>(`/traces/${encodeURIComponent(conversationId)}`, token);
}

export async function listAdminUserOverview(token: string): Promise<AdminUserOverview[]> {
  return apiGet<AdminUserOverview[]>("/admin/users/overview", token);
}
