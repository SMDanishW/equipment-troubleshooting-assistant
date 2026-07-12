"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { type EquipmentDocument, listDocuments } from "@/lib/api";

export function useDocuments(token: string | null) {
  const [documents, setDocuments] = useState<EquipmentDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const hasProcessingDocuments = useMemo(
    () => documents.some((document) => document.status === "processing"),
    [documents],
  );

  const refresh = useCallback(
    async (silent = false) => {
      if (!token) {
        setDocuments([]);
        setIsLoading(false);
        return;
      }
      if (!silent) {
        setIsLoading(true);
      }
      try {
        setDocuments(await listDocuments(token));
        setError("");
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to load documents.");
      } finally {
        if (!silent) {
          setIsLoading(false);
        }
      }
    },
    [token],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!hasProcessingDocuments) {
      return;
    }
    const intervalId = window.setInterval(() => void refresh(true), 2000);
    return () => window.clearInterval(intervalId);
  }, [hasProcessingDocuments, refresh]);

  function upsert(document: EquipmentDocument) {
    setDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)]);
  }

  function remove(documentId: string) {
    setDocuments((current) => current.filter((document) => document.id !== documentId));
  }

  return { documents, error, isLoading, refresh, remove, upsert };
}
