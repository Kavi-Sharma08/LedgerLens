import { api } from "@/lib/api/client";

/**
 * Source file (import) API. Uploads send the raw bytes as the request body —
 * mirroring the backend contract — with progress reported via XHR because
 * fetch cannot observe upload progress.
 */

export function listFiles({ sourceId, limit = 50, cursor, signal } = {}) {
  const params = new URLSearchParams({ sourceId });
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  return api.get(`/api/files?${params.toString()}`, { signal });
}

export function getFile(fileId, { signal } = {}) {
  return api.get(`/api/files/${encodeURIComponent(fileId)}`, { signal });
}

/**
 * Resolves with { file, isDuplicate } on success; rejects with ApiError.
 * onProgress receives 0..100.
 */
export function uploadFile({ sourceId, file, onProgress, signal }) {
  return new Promise((resolve, reject) => {
    const params = new URLSearchParams({
      sourceId,
      fileName: file.name,
    });
    if (file.type) params.set("mimeType", file.type);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/backend/api/files/upload?${params.toString()}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.setRequestHeader("Accept", "application/json");
    xhr.responseType = "json";

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      const body = xhr.response;
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body);
        return;
      }
      const detail =
        (body && (typeof body.detail === "string" ? body.detail : null)) || null;
      reject(
        Object.assign(new Error(detail || friendlyStatusMessage(xhr.status)), {
          status: xhr.status,
          name: "ApiError",
        })
      );
    });

    xhr.addEventListener("error", () => {
      reject(
        Object.assign(
          new Error(
            "We couldn't reach the LedgerLens servers. Check your internet connection and try again."
          ),
          { status: 0, name: "ApiError" }
        )
      );
    });

    xhr.addEventListener("abort", () => {
      reject(Object.assign(new Error("Upload cancelled."), { name: "AbortError" }));
    });

    if (signal) {
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }

    xhr.send(file);
  });
}

function friendlyStatusMessage(status) {
  switch (status) {
    case 401:
      return "Your session has expired. Please sign in again.";
    case 403:
      return "You don't have permission to import files for this workspace.";
    case 404:
      return "That financial source no longer exists.";
    case 413:
      return "That file is too large to import.";
    default:
      return "The import failed while LedgerLens was processing this file. Please try again.";
  }
}
