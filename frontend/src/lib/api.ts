export type User = { id: number; name: string; email: string; role: string; bureau_id: number | null; bureau: string };
export type Institution = { id: number; name: string; external_id: string | null; verified: boolean; region: string; address: string };
export type Case = {
  id: number; reference: string; institution: Institution; category: string; description?: string;
  priority: string; status: string; bureau: string; bureau_id: number; owner: string; owner_id: number;
  received_at: string; due_at: string | null; deadline_condition: string; deadline_policy: string;
  next_action: string; version: number; content_revision: number; matching_state: string; matching_error: string | null;
  paused_at: string | null; deadline_config: Record<string, unknown>; pauses?: {id: number; started_at: string; ended_at: string | null; reason: string}[];
  can_edit?: boolean; can_transfer?: boolean; allowed_transitions?: string[];
  attachments?: { id: number; filename: string; size: number; checksum: string }[];
  transfers?: { id: number; to_owner_id: number; created_at: string; acknowledged_at: string | null }[];
};
export type Event = { id: number; complaint_id: number; reference: string; actor: string; kind: string; summary: string; reason: string; changes: Record<string, unknown>; outcome: string; severity: string; created_at: string };
export type Page<T> = { items: T[]; nextCursor: number | null; total: number; asOf: string };
export type Directory = { bureaus: { id: number; code: string; name: string }[]; officers: User[]; categories: string[]; deadline_rules: {id: string; name: string}[] };
export type Pair = { id: number; a: Case; b: Case; state: string; band: string; version: number; stale: boolean; can_review?: boolean;
  evidence: { hybrid: number; cosine: number; reranker_raw: number; signals: Record<string, number>; truncated: boolean; shared_terms: string[]; explanation: string; bundle: { scoring_version: string; validated: boolean; top_k: number; embedding: { model: string; revision: string }; reranker: { model: string; revision: string } }; revisions: Record<string, number> };
  reviews?: { id: number; reviewer: string; decision: string; reason: string; created_at: string }[] };
export type Summary = { total: number; active: number; overdue: number; pending_pairs: number; confirmed_pairs: number; attention: Case[]; recent: Event[]; trend: { week: string; received: number; disposed: number }[]; asOf: string; policy: string; ageing: { label: string; count: number }[]; matching: { queued: number; failed: number } };
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
let csrf = '';
export function setCsrf(value: string) { csrf = value; }
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const form = options.body instanceof FormData;
  const response = await fetch('/api' + path, { ...options, credentials: 'same-origin', headers: { ...(!form && options.body ? { 'Content-Type': 'application/json' } : {}), 'X-CSRF-Token': csrf, ...options.headers } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login' && path !== '/auth/me') window.dispatchEvent(new CustomEvent('session-expired'));
    throw new ApiError(data.error?.message || `Request failed (${response.status})`, response.status);
  }
  return data;
}
export function post<T>(path: string, data: unknown, method = 'POST', headers = {}) { return api<T>(path, { method, body: JSON.stringify(data), headers }); }
export const label = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
export const date = (value: string | null, time = false) => value ? new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', ...(time ? { hour: '2-digit', minute: '2-digit' } : {}) }).format(new Date(value)) : 'Not set';
