"use client";

import { fetchEventSource } from "@microsoft/fetch-event-source";
import Link from "next/link";
import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { useAuth } from "@/components/auth/AuthProvider";
import { formatDocumentType } from "@/components/documents/DocumentList";
import { useDocuments } from "@/hooks/useDocuments";
import {
  API_BASE_URL,
  type CitationDetail,
  getCitation,
  uploadDocument,
} from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  images?: ImageReference[];
  conversationId?: string | null;
};

type AgentStatus = {
  agent: string;
  agentName: string;
  status: "running" | "completed";
};

type Citation = Partial<CitationDetail> & {
  id: string;
  type: "text" | "image";
};

type ImageReference = {
  id: string;
  image_url: string;
  source_file: string;
  page: number;
  caption?: string | null;
};

type StoredChatSession = {
  messages: ChatMessage[];
  citations?: Citation[];
  images?: ImageReference[];
  conversationId?: string | null;
};

const documentTypeOptions = [
  { label: "Detect automatically", value: "auto" },
  { label: "Operating manual", value: "operating_manual" },
  { label: "Maintenance guide", value: "maintenance_guide" },
  { label: "Error code reference", value: "error_code_reference" },
  { label: "Reference document", value: "reference_document" },
];

const thinkingStates = ["Reading manuals", "Searching evidence", "Checking sources", "Pondering wording", "Writing answer"];

export function ChatWindow() {
  const { token, user } = useAuth();
  const [question, setQuestion] = useState("");
  const [equipmentName, setEquipmentName] = useState("Kemppi AX MIG Welder");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [images, setImages] = useState<ImageReference[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<CitationDetail | null>(null);
  const [selectedImageUrl, setSelectedImageUrl] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isCitationLoading, setIsCitationLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadDocumentType, setUploadDocumentType] = useState("auto");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadNotice, setUploadNotice] = useState("");
  const { documents, error: documentError, isLoading: isLoadingDocuments, upsert: upsertDocument } = useDocuments(token);
  const availableDocuments = useMemo(
    () => documents.filter((document) => document.status === "indexed"),
    [documents],
  );
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [thinkingIndex, setThinkingIndex] = useState(0);

  const storageKey = user ? `equipment_agent_chat_${user.id}` : null;
  const currentAssistantMessage = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant"),
    [messages],
  );
  const citationMap = useMemo(() => new Map(citations.map((citation) => [citation.id, citation])), [citations]);

  useEffect(() => {
    if (!storageKey) {
      return;
    }
    const stored = window.sessionStorage.getItem(storageKey);
    if (!stored) {
      return;
    }
    try {
      const parsed = JSON.parse(stored) as StoredChatSession;
      const parsedMessages = parsed.messages ?? [];
      const latestAssistantMessage = [...parsedMessages].reverse().find((message) => message.role === "assistant");
      const latestCitations = parsed.citations ?? latestAssistantMessage?.citations ?? [];
      const latestImages = parsed.images ?? latestAssistantMessage?.images ?? [];
      const latestConversationId = parsed.conversationId ?? latestAssistantMessage?.conversationId ?? null;
      const lastAssistantIndex = parsedMessages.map((message) => message.role).lastIndexOf("assistant");
      const messagesWithLegacyEvidence = parsedMessages.map((message, index) =>
        index === lastAssistantIndex && !message.citations && !message.images
          ? {
              ...message,
              citations: latestCitations,
              conversationId: latestConversationId,
              images: latestImages,
            }
          : message,
      );
      setMessages(messagesWithLegacyEvidence);
      setCitations(latestCitations);
      setImages(latestImages);
      setConversationId(latestConversationId);
    } catch {
      window.sessionStorage.removeItem(storageKey);
    }
  }, [storageKey]);

  useEffect(() => {
    setSelectedDocumentIds((current) =>
      current.filter((documentId) => availableDocuments.some((document) => document.id === documentId)),
    );
  }, [availableDocuments]);

  useEffect(() => {
    if (documentError) {
      setError(documentError);
    }
  }, [documentError]);

  useEffect(() => {
    if (!storageKey) {
      return;
    }
    const payload: StoredChatSession = { messages, citations, images, conversationId };
    window.sessionStorage.setItem(storageKey, JSON.stringify(payload));
  }, [citations, conversationId, images, messages, storageKey]);

  useEffect(() => {
    return () => {
      if (selectedImageUrl) {
        URL.revokeObjectURL(selectedImageUrl);
      }
    };
  }, [selectedImageUrl]);

  useEffect(() => {
    if (!isStreaming || currentAssistantMessage?.content) {
      setThinkingIndex(0);
      return;
    }

    const intervalId = window.setInterval(() => {
      setThinkingIndex((current) => (current + 1) % thinkingStates.length);
    }, 1200);
    return () => window.clearInterval(intervalId);
  }, [currentAssistantMessage?.content, isStreaming]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !question.trim() || isStreaming) {
      return;
    }

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: question.trim(),
    };
    const chatHistory = messages
      .filter((message) => message.content.trim())
      .slice(-8)
      .map((message) => ({
        role: message.role,
        content: message.content.replace(/\[\[img_[\w-]+\]\]/g, "").trim().slice(0, 3000),
      }));
    const assistantMessageId = crypto.randomUUID();
    setMessages((current) => [
      ...current,
      userMessage,
      { id: assistantMessageId, role: "assistant", content: "", citations: [], conversationId: null, images: [] },
    ]);
    setAgentStatuses([]);
    setCitations([]);
    setImages([]);
    setSelectedCitation(null);
    setConversationId(null);
    setError("");
    setIsStreaming(true);
    setQuestion("");

    try {
      await fetchEventSource(`${API_BASE_URL}/chat/stream`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: userMessage.content,
          equipment_name: equipmentName.trim() || null,
          document_ids: selectedDocumentIds,
          chat_history: chatHistory,
        }),
        onmessage(eventMessage) {
          const data = eventMessage.data ? JSON.parse(eventMessage.data) : {};
          if (eventMessage.event === "agent_update") {
            setAgentStatuses((current) => upsertAgentStatus(current, data));
          }
          if (eventMessage.event === "token") {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessageId
                  ? { ...message, content: `${message.content}${data.content ?? ""}` }
                  : message,
              ),
            );
          }
          if (eventMessage.event === "citation") {
            const nextCitations = normalizeCitations(data.citations);
            setCitations(nextCitations);
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessageId ? { ...message, citations: nextCitations } : message,
              ),
            );
          }
          if (eventMessage.event === "image") {
            const nextImages = normalizeImages(data.images);
            setImages(nextImages);
            setMessages((current) =>
              current.map((message) => (message.id === assistantMessageId ? { ...message, images: nextImages } : message)),
            );
          }
          if (eventMessage.event === "done") {
            const nextConversationId = typeof data.conversation_id === "string" ? data.conversation_id : null;
            setConversationId(nextConversationId);
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessageId ? { ...message, conversationId: nextConversationId } : message,
              ),
            );
            setIsStreaming(false);
          }
          if (eventMessage.event === "error") {
            setError(data.message ?? "Chat stream failed.");
            setIsStreaming(false);
          }
        },
        onerror(caught) {
          throw caught;
        },
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to stream chat response.");
      setIsStreaming(false);
    }
  }

  function handleQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) {
      return;
    }
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!token || !uploadFile) {
      setError("Select a PDF before uploading.");
      return;
    }

    setIsUploading(true);
    setUploadNotice("");
    setError("");
    try {
      const uploaded = await uploadDocument(token, {
        file: uploadFile,
        equipmentName,
        documentType: uploadDocumentType,
      });
      upsertDocument(uploaded);
      setSelectedDocumentIds(uploaded.status === "indexed" ? [uploaded.id] : []);
      setUploadFile(null);
      setUploadDocumentType("auto");
      setUploadNotice(
        uploaded.status === "processing"
          ? `${uploaded.filename} queued for indexing.`
          : `${uploaded.filename} indexed as ${formatDocumentType(uploaded.document_type)}.`,
      );
      form.reset();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to upload document.");
    } finally {
      setIsUploading(false);
    }
  }

  function clearChatSession() {
    setMessages([]);
    setAgentStatuses([]);
    setCitations([]);
    setImages([]);
    setSelectedCitation(null);
    setConversationId(null);
    setError("");
    setUploadNotice("");
    if (storageKey) {
      window.sessionStorage.removeItem(storageKey);
    }
  }

  function toggleDocumentSelection(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId) ? current.filter((id) => id !== documentId) : [...current, documentId],
    );
  }

  async function openCitation(citationId: string) {
    if (!token) {
      return;
    }
    setIsCitationLoading(true);
    setError("");
    try {
      const detail = await getCitation(token, citationId);
      setSelectedCitation(detail);
      if (selectedImageUrl) {
        URL.revokeObjectURL(selectedImageUrl);
        setSelectedImageUrl(null);
      }
      if (detail.image_url) {
        setSelectedImageUrl(await fetchAuthenticatedBlobUrl(token, detail.image_url));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load source.");
    } finally {
      setIsCitationLoading(false);
    }
  }

  async function openPdfSource(citation: CitationDetail) {
    if (!token) {
      return;
    }
    const sourceUrl = citation.highlighted_pdf_url ?? citation.pdf_url;
    if (!sourceUrl) {
      return;
    }
    const pdfUrl = await fetchAuthenticatedBlobUrl(token, sourceUrl);
    window.open(`${pdfUrl}#page=${citation.page}`, "_blank", "noopener,noreferrer");
  }

  function closeCitation() {
    setSelectedCitation(null);
    if (selectedImageUrl) {
      URL.revokeObjectURL(selectedImageUrl);
      setSelectedImageUrl(null);
    }
  }

  return (
    <main className="page-shell chat-page">
      <section className="page-header">
        <div>
          <h1>Chat</h1>
          <p>Ask troubleshooting questions across your uploaded manuals.</p>
        </div>
        <div className="trace-header-actions">
          {messages.length > 0 ? (
            <button className="button" disabled={isStreaming} onClick={clearChatSession} type="button">
              New chat
            </button>
          ) : null}
          {conversationId ? (
            <Link className="button" href={`/traces/${conversationId}`}>
              View trace
            </Link>
          ) : null}
        </div>
      </section>

      <section className="chat-layout">
        <section className="panel chat-panel">
          <div className="message-list">
            {messages.length === 0 ? (
              <div className="empty-state">No messages yet. Upload a manual or ask a maintenance, error-code, or setup question.</div>
            ) : null}
            {messages.map((message) => (
              <article className={`message message-${message.role}`} key={message.id}>
                <div className="message-role">{message.role === "user" ? "You" : "Assistant"}</div>
                <div className="message-content">
                  {message.role === "assistant" ? (
                    message.content ? (
                      <MarkdownWithCitations
                        citationMap={new Map((message.citations ?? citations).map((citation) => [citation.id, citation]))}
                        content={message.content}
                        imageReferences={message.images ?? images}
                        onCitationClick={openCitation}
                        token={token}
                      />
                    ) : (
                      <ThinkingPlaceholder label={thinkingStates[thinkingIndex]} />
                    )
                  ) : (
                    <p>{message.content}</p>
                  )}
                </div>
              </article>
            ))}
          </div>

          <form className="chat-form" onSubmit={handleSubmit}>
            <label>
              <span>Equipment</span>
              <input onChange={(event) => setEquipmentName(event.target.value)} type="text" value={equipmentName} />
            </label>
            <label className="question-field">
              <span>Question</span>
              <div className="question-composer">
                <textarea
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={handleQuestionKeyDown}
                  placeholder="What does error E102 mean and what should I check first?"
                  required
                  rows={3}
                  value={question}
                />
                <button
                  aria-label="Ask"
                  className="button primary ask-icon-button"
                  disabled={isStreaming || !question.trim()}
                  title="Ask"
                  type="submit"
                >
                  ↑
                </button>
              </div>
            </label>
            {error ? <div className="form-error">{error}</div> : null}
          </form>
        </section>

        <aside className="panel chat-side-panel">
          <section className="manual-scope-panel">
            <div className="panel-heading compact-heading">
              <h2>Manual Scope</h2>
              <span>{selectedDocumentIds.length ? `${selectedDocumentIds.length} selected` : "All manuals"}</span>
            </div>
            <div className="manual-scope-actions">
              <button
                className="link-button"
                disabled={availableDocuments.length === 0}
                onClick={() => setSelectedDocumentIds(availableDocuments.map((document) => document.id))}
                type="button"
              >
                Select all
              </button>
              <button
                className="link-button"
                disabled={selectedDocumentIds.length === 0}
                onClick={() => setSelectedDocumentIds([])}
                type="button"
              >
                Use all
              </button>
            </div>
            <div className="manual-scope-list">
              {isLoadingDocuments ? <p className="muted">Loading manuals...</p> : null}
              {!isLoadingDocuments && availableDocuments.length === 0 ? <p className="muted">No indexed manuals yet.</p> : null}
              {availableDocuments.map((document) => (
                <label className="manual-scope-row" key={document.id}>
                  <input
                    checked={selectedDocumentIds.includes(document.id)}
                    onChange={() => toggleDocumentSelection(document.id)}
                    type="checkbox"
                  />
                  <span>
                    <strong>{document.filename}</strong>
                    <small>
                      {formatDocumentType(document.document_type)} - {document.page_count} pages
                    </small>
                  </span>
                </label>
              ))}
            </div>
          </section>

          <form className="chat-upload-panel" onSubmit={handleUpload}>
            <h2>Upload Manual</h2>
            <label>
              <span>Manual type</span>
              <select onChange={(event) => setUploadDocumentType(event.target.value)} value={uploadDocumentType}>
                {documentTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>PDF</span>
              <input accept="application/pdf,.pdf" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} type="file" />
            </label>
            {uploadNotice ? <div className="form-success">{uploadNotice}</div> : null}
            <button className="button stretch" disabled={isUploading} type="submit">
              {isUploading ? "Indexing..." : "Upload PDF"}
            </button>
          </form>

          <h2>Agent Status</h2>
          <div className="agent-status-list">
            {agentStatuses.length === 0 ? <p>No active run.</p> : null}
            {agentStatuses.map((status) => (
              <div className="agent-status-row" key={status.agent}>
                <span>{status.agentName}</span>
                <strong className={`status status-${status.status}`}>{status.status}</strong>
              </div>
            ))}
          </div>
          <h2>Sources</h2>
          <div className="citation-list">
            {citations.length === 0 ? <p>No sources streamed yet.</p> : null}
            {citations.map((citation) => (
              <button className="citation-row citation-row-button" key={citation.id} onClick={() => openCitation(citation.id)} type="button">
                <strong>{formatCitationLabel(citation.id, citationMap, citations.map((item) => item.id))}</strong>
                <span>
                  {citation.source_file ?? "source"} {typeof citation.page === "number" ? `p. ${citation.page}` : ""}
                </span>
              </button>
            ))}
          </div>
          {currentAssistantMessage?.content && isStreaming ? <p className="muted">Response is streaming.</p> : null}
          {isCitationLoading ? <p className="muted">Loading source...</p> : null}
        </aside>
      </section>

      {selectedCitation ? (
        <CitationModal
          citation={selectedCitation}
          imageUrl={selectedImageUrl}
          onClose={closeCitation}
          onOpenPdf={() => openPdfSource(selectedCitation)}
        />
      ) : null}
    </main>
  );
}

function MarkdownWithCitations({
  citationMap,
  content,
  imageReferences,
  onCitationClick,
  token,
}: Readonly<{
  citationMap: Map<string, Citation>;
  content: string;
  imageReferences: ImageReference[];
  onCitationClick: (citationId: string) => void;
  token: string | null;
}>) {
  const orderedIds = useMemo(() => citationIdsInContent(content), [content]);
  const imageMap = useMemo(() => new Map(imageReferences.map((image) => [image.id, image])), [imageReferences]);
  const parts = content.split(/(\[\[img_[\w-]+\]\])/g);

  return (
    <>
      {parts.map((part, index) => {
        const imageId = citationIdFromMarker(part);
        if (imageId?.startsWith("img_")) {
          const image = imageMap.get(imageId);
          return image ? (
            <InlineImageReferences images={[image]} key={`${imageId}-${index}`} onCitationClick={onCitationClick} token={token} />
          ) : (
            <CitationButton
              citationId={imageId}
              citationMap={citationMap}
              key={`${imageId}-${index}`}
              onCitationClick={onCitationClick}
              orderedIds={orderedIds}
            />
          );
        }

        return (
          <ReactMarkdown
            components={{
              a: ({ children, href }) => {
                const citationId = href?.startsWith("#citation-") ? href.replace("#citation-", "") : null;
                if (!citationId) {
                  return <a href={href}>{children}</a>;
                }
                return (
                  <CitationButton
                    citationId={citationId}
                    citationMap={citationMap}
                    onCitationClick={onCitationClick}
                    orderedIds={orderedIds}
                  />
                );
              },
            }}
            key={`markdown-${index}`}
            remarkPlugins={[remarkGfm]}
          >
            {linkifyTextCitationMarkers(part, citationMap, orderedIds)}
          </ReactMarkdown>
        );
      })}
    </>
  );
}

function CitationButton({
  citationId,
  citationMap,
  onCitationClick,
  orderedIds,
}: Readonly<{
  citationId: string;
  citationMap: Map<string, Citation>;
  onCitationClick: (citationId: string) => void;
  orderedIds: string[];
}>) {
  const citation = citationMap.get(citationId);
  return (
    <button
      className={`citation-badge citation-badge-${citation?.type ?? (citationId.startsWith("img_") ? "image" : "text")}`}
      onClick={() => onCitationClick(citationId)}
      title={citation?.source_file ? `${citation.source_file}, page ${citation.page}` : citationId}
      type="button"
    >
      {formatCitationLabel(citationId, citationMap, orderedIds)}
    </button>
  );
}

function CitationModal({
  citation,
  imageUrl,
  onClose,
  onOpenPdf,
}: Readonly<{
  citation: CitationDetail;
  imageUrl: string | null;
  onClose: () => void;
  onOpenPdf: () => void;
}>) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section aria-modal="true" className="citation-modal" onClick={(event) => event.stopPropagation()} role="dialog">
        <div className="modal-header">
          <div>
            <h2>{citation.type === "image" ? "Figure Source" : "Manual Source"}</h2>
            <p>
              {citation.source_file}, page {citation.page}
              {citation.page_end && citation.page_end !== citation.page ? `-${citation.page_end}` : ""}
            </p>
          </div>
          <div className="modal-actions">
            {citation.pdf_url || citation.highlighted_pdf_url ? (
              <button className="button" onClick={onOpenPdf} type="button">
                Open PDF page
              </button>
            ) : null}
            <button className="button" onClick={onClose} type="button">
              Close
            </button>
          </div>
        </div>
        {citation.type === "image" ? (
          <div className="citation-image-detail">
            {imageUrl ? <img alt={citation.caption ?? citation.id} src={imageUrl} /> : <p>Image preview unavailable.</p>}
            {citation.caption ? <p>{citation.caption}</p> : null}
            {citation.related_text ? <p className="citation-excerpt">{citation.related_text}</p> : null}
          </div>
        ) : (
          <div className="citation-text-detail">
            <span>Highlighted excerpt</span>
            <p className="citation-excerpt">{citation.excerpt}</p>
          </div>
        )}
      </section>
    </div>
  );
}

function InlineImageReferences({
  images,
  onCitationClick,
  token,
}: Readonly<{
  images: ImageReference[];
  onCitationClick: (citationId: string) => void;
  token: string | null;
}>) {
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    let isCancelled = false;
    const loadedUrls: string[] = [];

    async function loadImages() {
      if (!token) {
        return;
      }
      const entries = await Promise.all(
        images.map(async (image) => {
          const url = await fetchAuthenticatedBlobUrl(token, image.image_url);
          loadedUrls.push(url);
          return [image.id, url] as const;
        }),
      );
      if (!isCancelled) {
        setImageUrls(Object.fromEntries(entries));
      }
    }

    void loadImages();
    return () => {
      isCancelled = true;
      loadedUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [images, token]);

  return (
    <div className="inline-image-grid">
      {images.map((image) => (
        <button
          className="inline-image-card"
          key={image.id}
          onClick={() => onCitationClick(image.id)}
          title="Open figure"
          type="button"
        >
          <span aria-hidden="true" className="inline-image-expand">
            ⤢
          </span>
          {imageUrls[image.id] ? <img alt={image.caption ?? image.id} src={imageUrls[image.id]} /> : <span>Loading figure...</span>}
          <strong>{formatCitationLabel(image.id, new Map([[image.id, { ...image, type: "image" }]]), [image.id])}</strong>
          <span>
            {image.source_file}, page {image.page}
          </span>
        </button>
      ))}
    </div>
  );
}

function ThinkingPlaceholder({ label }: Readonly<{ label: string }>) {
  return (
    <div className="thinking-placeholder" aria-live="polite">
      <span>{label}</span>
      <span className="thinking-dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
}

function upsertAgentStatus(current: AgentStatus[], data: Record<string, unknown>): AgentStatus[] {
  const nextStatus: AgentStatus = {
    agent: String(data.agent ?? "agent"),
    agentName: String(data.agent_name ?? data.agent ?? "Agent"),
    status: data.status === "completed" ? "completed" : "running",
  };
  const existing = current.find((status) => status.agent === nextStatus.agent);
  if (!existing) {
    return [...current, nextStatus];
  }
  return current.map((status) => (status.agent === nextStatus.agent ? nextStatus : status));
}

function normalizeCitations(value: unknown): Citation[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Citation => Boolean(item && typeof item === "object" && "id" in item && "type" in item))
    .map((item) => ({ ...item, id: String(item.id), type: item.type === "image" ? "image" : "text" }));
}

function normalizeImages(value: unknown): ImageReference[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is ImageReference => Boolean(item && typeof item === "object" && "id" in item && "image_url" in item))
    .map((item) => ({
      id: String(item.id),
      image_url: String(item.image_url),
      source_file: String(item.source_file ?? "source"),
      page: Number(item.page ?? 0),
      caption: typeof item.caption === "string" ? item.caption : null,
    }));
}

function linkifyTextCitationMarkers(content: string, citationMap: Map<string, Citation>, orderedIds: string[]): string {
  return content.replace(/\[\[(txt_[\w-]+)\]\]/g, (_match, citationId: string) => {
    return `[${formatCitationLabel(citationId, citationMap, orderedIds)}](#citation-${citationId})`;
  });
}

function citationIdsInContent(content: string): string[] {
  return Array.from(content.matchAll(/\[\[((?:txt|img)_[\w-]+)\]\]/g)).map((match) => match[1]);
}

function citationIdFromMarker(value: string): string | null {
  const match = value.match(/^\[\[((?:txt|img)_[\w-]+)\]\]$/);
  return match ? match[1] : null;
}

function formatCitationLabel(citationId: string, citationMap: Map<string, Citation>, orderedIds: string[]): string {
  const citation = citationMap.get(citationId);
  const type = citation?.type ?? (citationId.startsWith("img_") ? "image" : "text");
  const idsOfType = orderedIds.filter((id) => (type === "image" ? id.startsWith("img_") : id.startsWith("txt_")));
  const index = Math.max(1, idsOfType.indexOf(citationId) + 1);
  return type === "image" ? `Figure ${index}` : `Source ${index}`;
}

async function fetchAuthenticatedBlobUrl(token: string, path: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error(`Unable to load source ${response.status}`);
  }
  return URL.createObjectURL(await response.blob());
}
