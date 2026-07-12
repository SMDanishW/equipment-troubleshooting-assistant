import { type EquipmentDocument } from "@/lib/api";

export function DocumentList({
  documents,
  deletingDocumentId,
  onDelete,
}: Readonly<{
  documents: EquipmentDocument[];
  deletingDocumentId: string | null;
  onDelete: (document: EquipmentDocument) => void;
}>) {
  return (
    <div className="document-list">
      {documents.map((document) => (
        <article className="document-item" key={document.id}>
          <div className="document-item-main">
            <div>
              <h3>{document.filename}</h3>
              <p>
                {document.equipment_name} - {formatDocumentType(document.document_type)}
              </p>
            </div>
            <button
              className="button danger"
              disabled={deletingDocumentId === document.id || document.status === "processing"}
              onClick={() => onDelete(document)}
              type="button"
            >
              {deletingDocumentId === document.id ? "Deleting..." : "Delete"}
            </button>
          </div>
          <div className="document-meta">
            <span className={`status status-${document.status}`}>{document.status}</span>
            <span>{document.page_count.toLocaleString()} pages</span>
            <span>{document.text_chunks_count.toLocaleString()} chunks</span>
            <span>{document.images_extracted_count.toLocaleString()} images</span>
          </div>
          {document.error_message ? <div className="form-error">{document.error_message}</div> : null}
        </article>
      ))}
    </div>
  );
}

export function formatDocumentType(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
