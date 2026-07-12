"use client";

import { FormEvent, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { DocumentList, formatDocumentType } from "@/components/documents/DocumentList";
import { useDocuments } from "@/hooks/useDocuments";
import { deleteDocument, type EquipmentDocument, uploadDocument } from "@/lib/api";

const documentTypeOptions = [
  { label: "Detect automatically", value: "auto" },
  { label: "Operating manual", value: "operating_manual" },
  { label: "Maintenance guide", value: "maintenance_guide" },
  { label: "Error code reference", value: "error_code_reference" },
  { label: "Reference document", value: "reference_document" },
];

export function DocumentsDashboard() {
  const { token } = useAuth();
  const { documents, error: loadError, isLoading, refresh, remove, upsert } = useDocuments(token);
  const [equipmentName, setEquipmentName] = useState("Kemppi AX MIG Welder");
  const [documentType, setDocumentType] = useState("auto");
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");

  const totals = useMemo(
    () => ({
      manuals: documents.length,
      pages: documents.reduce((sum, document) => sum + document.page_count, 0),
      chunks: documents.reduce((sum, document) => sum + document.text_chunks_count, 0),
      images: documents.reduce((sum, document) => sum + document.images_extracted_count, 0),
    }),
    [documents],
  );

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!token || !file) {
      setActionError("Select a PDF before uploading.");
      return;
    }

    setActionError("");
    setNotice("");
    setIsUploading(true);
    try {
      const uploaded = await uploadDocument(token, {
        file,
        equipmentName,
        documentType,
      });
      upsert(uploaded);
      setFile(null);
      setDocumentType("auto");
      setNotice(
        uploaded.status === "processing"
          ? `${uploaded.filename} queued for indexing.`
          : `${uploaded.filename} indexed successfully as ${formatDocumentType(uploaded.document_type)}.`,
      );
      form.reset();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to upload document.");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDeleteDocument(document: EquipmentDocument) {
    if (!token) {
      return;
    }
    const confirmed = window.confirm(
      `Delete ${document.filename}? This removes the uploaded PDF, extracted images, and index entries.`,
    );
    if (!confirmed) {
      return;
    }

    setActionError("");
    setNotice("");
    setDeletingDocumentId(document.id);
    try {
      await deleteDocument(token, document.id);
      remove(document.id);
      setNotice(`${document.filename} deleted.`);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to delete document.");
    } finally {
      setDeletingDocumentId(null);
    }
  }

  return (
    <main className="page-shell">
      <section className="page-header">
        <div>
          <h1>Documents</h1>
          <p>Upload manuals and review indexed source coverage for this account.</p>
        </div>
        <button className="button" disabled={isLoading || isUploading} onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </section>

      <section className="stats-grid" aria-label="Document totals">
        <Stat label="Manuals" value={totals.manuals} />
        <Stat label="Pages" value={totals.pages} />
        <Stat label="Text chunks" value={totals.chunks} />
        <Stat label="Images" value={totals.images} />
      </section>

      <section className="document-layout">
        <form className="panel form upload-panel" onSubmit={handleUpload}>
          <div>
            <h2>Upload PDF</h2>
            <p>PDFs are indexed into text and image evidence for retrieval.</p>
          </div>
          <label>
            <span>Equipment name</span>
            <input
              onChange={(event) => setEquipmentName(event.target.value)}
              required
              type="text"
              value={equipmentName}
            />
          </label>
          <label>
            <span>Document type</span>
            <select onChange={(event) => setDocumentType(event.target.value)} value={documentType}>
              {documentTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>PDF file</span>
            <input
              accept="application/pdf,.pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              required
              type="file"
            />
          </label>
          {actionError || loadError ? <div className="form-error">{actionError || loadError}</div> : null}
          {notice ? <div className="form-success">{notice}</div> : null}
          <button className="button primary stretch" disabled={isUploading} type="submit">
            {isUploading ? "Uploading..." : "Upload and Index"}
          </button>
        </form>

        <section className="panel document-list-panel">
          <div className="panel-heading">
            <h2>Manuals</h2>
            <span>{isLoading ? "Loading" : `${documents.length} total`}</span>
          </div>
          {isLoading ? <p>Loading documents...</p> : null}
          {!isLoading && documents.length === 0 ? <p>No manuals indexed yet.</p> : null}
          {!isLoading && documents.length > 0 ? (
            <DocumentList
              deletingDocumentId={deletingDocumentId}
              documents={documents}
              onDelete={handleDeleteDocument}
            />
          ) : null}
        </section>
      </section>
    </main>
  );
}

function Stat({ label, value }: Readonly<{ label: string; value: number }>) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
    </div>
  );
}
