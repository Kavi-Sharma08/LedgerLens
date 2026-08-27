/**
 * Display formatting helpers shared across financial screens.
 * Pure functions — no React, safe on server and client.
 */

export function formatMoney(amount, currency = "INR") {
  if (amount === null || amount === undefined || amount === "") return "—";
  const numeric = Number(amount);
  if (!Number.isFinite(numeric)) return String(amount);
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numeric);
  } catch {
    return `${currency} ${numeric.toFixed(2)}`;
  }
}

function parseInstant(value) {
  if (value == null || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
  const text = String(value).trim();
  if (!text) return null;
  const isDateOnly = /^\d{4}-\d{2}-\d{2}$/.test(text);
  // Naive datetimes are treated as UTC, not local. The backend stores UTC,
  // so interpreting a tz-less value as local time would shift every
  // timestamp by the browser's offset.
  const hasTz = /(?:[zZ]|[+-]\d{2}:?\d{2})$/.test(text);
  const date = new Date(isDateOnly ? `${text}T00:00:00Z` : hasTz ? text : `${text}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value) {
  const date = parseInstant(value);
  if (!date) return value == null || value === "" ? "—" : String(value);
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function formatDateTime(value, options = {}) {
  const date = parseInstant(value);
  if (!date) return value == null || value === "" ? "—" : String(value);
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: options.year ? "numeric" : undefined,
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatRelativeTime(value) {
  const date = parseInstant(value);
  if (!date) return "";
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(value);
}

export function formatPercent(fraction, digits = 1) {
  const numeric = Number(fraction);
  if (!Number.isFinite(numeric)) return "—";
  return `${(numeric * 100).toFixed(digits)}%`;
}

export function formatCount(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "0";
  return numeric.toLocaleString("en-IN");
}
