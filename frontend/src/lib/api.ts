export type User = { id: number; name: string; email: string; role: string; is_demo: boolean; mfa_enrollment_required?: boolean; requested_role: string | null; organization: string; approval_pending: boolean; bureau_id: number | null; bureau: string; roles: string[]; capabilities: Record<string, boolean> };
export type Institution = { id: number; name: string; external_id: string | null; verified: boolean; region: string; address: string };
export type Case = {
  id: number; reference: string; institution: Institution; category: string; description?: string;
  priority: string; status: string; bureau: string; bureau_id: number; owner: string; owner_id: number;
  received_at: string; due_at: string | null; deadline_condition: string; deadline_policy: string;
  next_action: string; version: number; content_revision: number; matching_state: string; matching_error: string | null;
  paused_at: string | null; deadline_config: Record<string, unknown>; pauses?: {id: number; started_at: string; ended_at: string | null; reason: string}[];
  can_edit?: boolean; can_transfer?: boolean; allowed_transitions?: string[];
  malware_scan_enabled?: boolean; can_upload?: boolean; max_upload_bytes?: number; reports?: { id: number; created_at: string; checksum: string }[];
  can_transition?: boolean; can_route?: boolean; can_proceeding?: boolean; can_compliance?: boolean; can_export?: boolean; can_read_documents?: boolean;
  issue_summary: string; complainant_type: string; source_channel: string; source_reference: string; entered_at: string;
  affected_person?: string; submitter_name?: string; representation_basis?: string; prior_proceedings?: string;
  attachments?: { id: number; filename: string; size: number; checksum: string; proceeding_id: number | null; scan_state: string; available?: boolean; scan_detail: string | null }[];
  transfers?: { id: number; to_owner_id: number; created_at: string; acknowledged_at: string | null }[];
};
export type Event = { actor_id?: number; proof?: {id: number; filename: string; scan_state: string; available?: boolean}[]; id: number; complaint_id: number; reference: string; actor: string; kind: string; summary: string; reason: string; changes: Record<string, unknown>; outcome: string; severity: string; created_at: string };
export type Page<T> = { items: T[]; nextCursor: number | null; total: number; asOf: string };
export type Directory = { bureaus: { id: number; code: string; name: string }[]; officers: User[]; participants: User[]; categories: string[]; deadline_rules: {id: string; name: string}[] };
export type Pair = { id: number; a: Case; b: Case; state: string; band: string; version: number; stale: boolean; can_review?: boolean;
  evidence: { hybrid: number; cosine: number; reranker_raw: number; signals: Record<string, number>; truncated: boolean; shared_terms: string[]; explanation: string; bundle: { scoring_version: string; validated: boolean; top_k: number; embedding: { model: string; revision: string }; reranker: { model: string; revision: string } }; revisions: Record<string, number> };
  reviews?: { id: number; reviewer: string; decision: string; reason: string; created_at: string }[] };
export type Summary = { total: number; active: number; overdue: number; pending_pairs: number; confirmed_pairs: number; attention: Case[]; recent: Event[]; trend: { week: string; received: number; disposed: number }[]; asOf: string; policy: string; ageing: { label: string; count: number }[]; matching: { queued: number; failed: number } };
export class ApiError extends Error { constructor(message: string, public status: number, public mfaRequired = false) { super(message); } }
let csrf = '';
const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
export function setCsrf(value: string) { csrf = value; }
const pendingLogoutKey = 'onecase.logout-pending';
let leavingPage = false;
window.addEventListener('pagehide', () => { leavingPage = true; });
window.addEventListener('pageshow', () => { leavingPage = false; });
export function hasPendingLogout() { return localStorage.getItem(pendingLogoutKey) === '1'; }
export function connectionLost() {
  localStorage.setItem(pendingLogoutKey, '1');
  csrf = '';
  window.dispatchEvent(new Event('connection-lost'));
}
let revoking: Promise<void> | undefined;
export function finishPendingLogout(): Promise<void> {
  if (!hasPendingLogout()) return Promise.resolve();
  if (revoking) return revoking;
  revoking = (async () => {
    try {
      const identity = await api<{csrf: string}>('/auth/me');
      setCsrf(identity.csrf);
      await post('/auth/logout', {});
      localStorage.removeItem(pendingLogoutKey);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) localStorage.removeItem(pendingLogoutKey);
      else throw error;
    } finally { csrf = ''; }
  })().finally(() => { revoking = undefined; });
  return revoking;
}
export function logoutSession() {
  localStorage.setItem(pendingLogoutKey, '1');
  return finishPendingLogout();
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const form = options.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(apiBase + path, { ...options, signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(25000)]) : AbortSignal.timeout(25000), credentials: 'same-origin', headers: { ...(!form && options.body ? { 'Content-Type': 'application/json' } : {}), 'X-CSRF-Token': csrf, ...options.headers } });
  } catch (error) {
    // Navigation cancels outstanding fetches; it is not a service outage.
    if (leavingPage || options.signal?.aborted) throw error;
    connectionLost();
    throw new ApiError('Connection lost. You have been signed out. Reconnect and sign in again.', 0);
  }
  if ([502, 503, 504].includes(response.status) && !(response.status === 503 && path === '/auth/forgot-password')) {
    connectionLost();
    throw new ApiError('The service is unavailable. You have been signed out. Try signing in again when it is available.', response.status);
  }
  const data = await response.json().catch((error: unknown) => {
    if (!leavingPage && (error instanceof TypeError || (error instanceof DOMException && error.name !== 'SyntaxError'))) {
      connectionLost();
      throw new ApiError('Connection lost while receiving the response. Sign in again after reconnecting.', 0);
    }
    return {};
  });
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login' && !hasPendingLogout() && (path !== '/auth/me' || csrf)) window.dispatchEvent(new CustomEvent('session-expired'));
    throw new ApiError(data.error?.message || `Request failed (${response.status})`, response.status, !!data.error?.mfa_required);
  }
  return data;
}
export function post<T>(path: string, data: unknown, method = 'POST', headers = {}) { return api<T>(path, { method, body: JSON.stringify(data), headers }); }
export const label = (value: string) => value === 'unscanned' ? 'Malware scan skipped' : value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
export const date = (value: string | null, time = false) => value ? new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', ...(time ? { hour: '2-digit', minute: '2-digit' } : {}) }).format(new Date(value)) : 'Not set';
