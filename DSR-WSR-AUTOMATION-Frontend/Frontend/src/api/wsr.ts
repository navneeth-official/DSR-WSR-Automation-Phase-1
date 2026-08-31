import type { PresentationDocument } from "@/components/ppt-editor/types";

export interface WsrContentSection {
  sprint_name: string;
  sprint_dates: string;
  sprint_status: string;
  released: string[];
  inprogress: string[];
  completed: string[];
}

export interface WsrContentSlide {
  project_key: string;
  project_name: string;
  title: string;
  sections: WsrContentSection[];
  key_activities: string[];
}

export interface WsrPreviewSlide {
  slide_index: number;
  title: string;
  image_url: string;
}

export interface WsrTemplateInfo {
  filename: string;
  original_filename: string;
  uploaded_at: string;
  slide_count: number;
  file_size_bytes: number;
}

export interface WsrTemplateItem {
  id: string;
  filename: string;
  original_filename: string;
  updated_at: string;
  slide_count: number;
  file_size_bytes: number;
  is_draft?: boolean;
  thumbnail_url: string;
}

export interface WsrTemplateListResponse {
  templates: WsrTemplateItem[];
  draft: WsrTemplateItem | null;
}

export interface WsrTemplateUploadResponse extends WsrTemplateInfo {
  preview_slides: WsrPreviewSlide[];
}

export interface WsrTemplateStageResponse extends WsrTemplateItem {
  preview_slides: WsrPreviewSlide[];
}

export interface WsrMeta {
  story_count: number;
  slide_count: number;
  titles_from_db?: number;
  titles_fallback_summary?: number;
  titles_generated: number;
  titles_reused: number;
}

export interface WsrGenerateResponse {
  report_start_date: string;
  report_end_date: string;
  meta: WsrMeta;
  preview: string;
  filename: string;
  download_url: string;
  slides: WsrContentSlide[];
  preview_slides: WsrPreviewSlide[];
  onedrive_web_url?: string | null;
  cloud_web_url?: string | null;
  cloud_provider?: "google_drive" | "onedrive" | string | null;
  variant?: number;
  variant_label?: string;
  template_id?: string | null;
  template_name?: string | null;
}

export interface WsrWeekSummary {
  report_start_date: string;
  report_end_date: string;
  variant?: number;
  variant_label?: string;
  template_id?: string | null;
  template_name?: string | null;
  filename: string;
  generated_at: string;
  story_count: number;
  slide_count: number;
  thumbnail_url: string | null;
  download_url: string;
}

export interface WsrWeekListResponse {
  count: number;
  weeks: WsrWeekSummary[];
}

export interface WsrGenerateRequest {
  start_date: string;
  end_date: string;
  template_id: string;
  force?: boolean;
}

export interface WsrJobStartResponse {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  report_start_date: string;
  report_end_date: string;
  message: string;
}

export interface WsrStatusResponse {
  status: "not_found" | "queued" | "running" | "completed" | "failed";
  job_id?: string | null;
  report_start_date?: string | null;
  report_end_date?: string | null;
  error?: string | null;
  result?: WsrGenerateResponse | null;
}

export interface WsrGenerationCheckResponse {
  can_generate: boolean;
  reason: "new_week" | "different_template" | "same_template";
  variant: number;
  variant_label: string;
  template_id?: string | null;
  template_name?: string | null;
  message: string;
  existing_variants?: {
    variant: number;
    variant_label: string;
    template_id?: string | null;
    template_name?: string | null;
  }[];
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: string | { msg?: string }[] };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail) && data.detail[0]?.msg) return data.detail[0].msg;
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status})`;
}

function weekParams(
  startDate: string,
  endDate: string,
  variant?: number,
): URLSearchParams {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });
  if (variant != null && variant > 1) {
    params.set("variant", String(variant));
  }
  return params;
}

export async function checkWsrGeneration(
  startDate: string,
  endDate: string,
  templateId: string,
): Promise<WsrGenerationCheckResponse> {
  const params = weekParams(startDate, endDate);
  params.set("template_id", templateId);
  const res = await fetch(`/api/wsr/generate/check?${params.toString()}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrGenerationCheckResponse>;
}

export async function fetchWsrWeeks(): Promise<WsrWeekListResponse> {
  const res = await fetch("/api/wsr/weeks");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrWeekListResponse>;
}

export async function fetchWsrWeek(
  startDate: string,
  endDate: string,
  variant = 1,
): Promise<WsrGenerateResponse | null> {
  const res = await fetch(
    `/api/wsr/week?${weekParams(startDate, endDate, variant).toString()}`,
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrGenerateResponse>;
}

export async function startWsrJob(
  payload: WsrGenerateRequest,
): Promise<WsrJobStartResponse> {
  const res = await fetch("/api/wsr/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      force: false,
      ...payload,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrJobStartResponse>;
}

export async function fetchWsrStatus(
  startDate: string,
  endDate: string,
): Promise<WsrStatusResponse> {
  const res = await fetch(`/api/wsr/status?${weekParams(startDate, endDate).toString()}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrStatusResponse>;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function waitForWsrJob(
  startDate: string,
  endDate: string,
  options?: { pollMs?: number; signal?: AbortSignal },
): Promise<WsrGenerateResponse> {
  const pollMs = options?.pollMs ?? 2000;

  while (true) {
    if (options?.signal?.aborted) {
      throw new Error("WSR generation cancelled");
    }

    const status = await fetchWsrStatus(startDate, endDate);
    if (status.status === "completed" && status.result) {
      return status.result;
    }
    if (status.status === "failed") {
      throw new Error(status.error ?? "WSR generation failed");
    }

    await sleep(pollMs);
  }
}

/** @deprecated Use startWsrJob + waitForWsrJob */
export async function generateWsr(
  payload: WsrGenerateRequest,
): Promise<WsrGenerateResponse> {
  await startWsrJob(payload);
  return waitForWsrJob(payload.start_date, payload.end_date);
}

export async function fetchWsrPreviewSlides(
  startDate: string,
  endDate: string,
  variant = 1,
): Promise<WsrPreviewSlide[]> {
  const res = await fetch(
    `/api/wsr/preview/slides?${weekParams(startDate, endDate, variant).toString()}`,
  );
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrPreviewSlide[]>;
}

export function wsrDownloadUrl(
  startDate: string,
  endDate: string,
  variant = 1,
): string {
  return `/api/wsr/download?${weekParams(startDate, endDate, variant).toString()}`;
}

export function wsrTemplateThumbnailUrl(templateId: string): string {
  const params = new URLSearchParams({
    template_id: templateId,
    slide_index: "1",
    thumb: "1",
  });
  return `/api/wsr/template/preview/image?${params.toString()}`;
}

export async function fetchEditorDeck(
  startDate: string,
  endDate: string,
): Promise<PresentationDocument> {
  const res = await fetch(`/api/wsr/editor/deck?${weekParams(startDate, endDate).toString()}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<PresentationDocument>;
}

export async function saveEditorDeck(
  startDate: string,
  endDate: string,
  document: PresentationDocument,
): Promise<void> {
  const res = await fetch(`/api/wsr/editor/deck?${weekParams(startDate, endDate).toString()}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document }),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function exportEditorDeck(
  startDate: string,
  endDate: string,
  document: PresentationDocument,
): Promise<Blob> {
  const res = await fetch(`/api/wsr/editor/export?${weekParams(startDate, endDate).toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.blob();
}

export interface EditorSyncResponse {
  ok: boolean;
  preview_slides: { slide_index: number; title: string; image_url: string }[];
}

/** Apply edits to the real .pptx and refresh slide preview PNGs */
export async function syncEditorDeck(
  startDate: string,
  endDate: string,
  document: PresentationDocument,
): Promise<EditorSyncResponse> {
  const res = await fetch(`/api/wsr/editor/sync?${weekParams(startDate, endDate).toString()}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<EditorSyncResponse>;
}

export async function fetchWsrTemplate(): Promise<WsrTemplateInfo | null> {
  const res = await fetch("/api/wsr/template");
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as WsrTemplateInfo | null;
  return data;
}

export async function fetchWsrTemplates(): Promise<WsrTemplateListResponse> {
  const res = await fetch("/api/wsr/templates");
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrTemplateListResponse>;
}

export async function fetchWsrTemplatePreviewSlides(
  templateId?: string,
): Promise<WsrPreviewSlide[]> {
  const params = new URLSearchParams();
  if (templateId) params.set("template_id", templateId);
  const query = params.toString();
  const res = await fetch(`/api/wsr/template/preview/slides${query ? `?${query}` : ""}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrPreviewSlide[]>;
}

export async function stageWsrTemplate(file: File): Promise<WsrTemplateStageResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/wsr/template/stage", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrTemplateStageResponse>;
}

export async function saveStagedWsrTemplate(): Promise<WsrTemplateItem> {
  const res = await fetch("/api/wsr/template/save", { method: "POST" });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrTemplateItem>;
}

export async function cancelStagedWsrTemplate(): Promise<void> {
  const res = await fetch("/api/wsr/template/draft", { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function uploadWsrTemplate(file: File): Promise<WsrTemplateUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch("/api/wsr/template/upload", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<WsrTemplateUploadResponse>;
}
