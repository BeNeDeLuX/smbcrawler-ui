// Tiny fetch wrapper. The session lives in an httpOnly cookie, so every request
// just needs credentials: "include".

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const res = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body = text ? JSON.parse(text) : undefined;
  if (!res.ok) {
    throw new ApiError(res.status, body?.detail ?? res.statusText);
  }
  return body as T;
}

async function reqText(path: string): Promise<string> {
  const res = await fetch(path, { credentials: "include" });
  const text = await res.text();
  if (!res.ok) throw new ApiError(res.status, text || res.statusText);
  return text;
}

export const api = {
  get: <T>(p: string) => req<T>(p),
  getText: (p: string) => reqText(p),
  post: <T>(p: string, data?: unknown) =>
    req<T>(p, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) }),
  put: <T>(p: string, data: unknown) =>
    req<T>(p, { method: "PUT", body: JSON.stringify(data) }),
  del: (p: string) => req<void>(p, { method: "DELETE" }),
  postForm: <T>(p: string, form: FormData) =>
    req<T>(p, { method: "POST", body: form }),
};

// ---- shared types ------------------------------------------------------------
export type ScanStatus =
  | "queued"
  | "running"
  | "done"
  | "failed"
  | "canceled"
  | "imported";

export interface Scan {
  id: string;
  name: string;
  source: "crawl" | "import_";
  status: ScanStatus;
  params: Record<string, any>;
  progress: Record<string, any>;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Share {
  name: string;
  remark: string | null;
  high_value: number;
  auth_access: number | null;
  guest_access: number | null;
  write_access: number | null;
  read_level: number | null;
  maxed_out: number | null;
  target: string;
}

export interface PathRow {
  id: number;
  target: string;
  share: string;
  path: string;
  size: number;
  high_value: number;
  content_hash: string | null;
  annotation?: Annotation | null;
}

export interface TreeNode {
  id: number;
  name: string;
  size: number;
  content_hash: string | null;
  high_value: number;
  child_count: number;
}

export interface SecretRow {
  secret: string;
  line: string;
  line_number: number;
  target: string;
  share: string;
  path: string;
  content_hash: string;
  annotation?: Annotation | null;
}

export interface SearchHit {
  target: string;
  share: string;
  path: string;
  content_hash: string;
  snippet: string;
}

export type AnnotationStatus =
  | "open"
  | "reviewed"
  | "false_positive"
  | "important";

export interface Annotation {
  status: AnnotationStatus;
  note: string;
}
