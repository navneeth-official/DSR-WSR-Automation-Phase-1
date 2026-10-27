# WSR Re-check / Re-validation — Implementation & Porting Guide

This guide documents the **Re-check deck** feature: an explicit control that pulls the latest SharePoint copy of a WSR (when configured), re-runs deck validation, and refreshes annotated slides + findings — **without** changing the existing **Slide Review** button (which only shows the last stored snapshot).

Use this document to replicate the same behavior in another codebase that already has:

- WSR generation → local `.pptx` under `output/`
- Post-generation validation (`validate_deck` / `run_wsr_validation`) writing a report + annotated PNGs
- Slide Review UI that reads those artifacts via GET APIs
- Optional SharePoint upload via Microsoft Graph (app-only)

---

## Problem this solves

| Scenario | Old behavior | Desired behavior |
|----------|--------------|------------------|
| Author opens findings after generate | Shows pre-computed annotations | Unchanged — fast read of last check |
| Team edits the deck **in SharePoint** | Local PPT + annotations stay stale | Explicit **Re-check** pulls latest → re-validates → updates annotations |
| SharePoint file unchanged since last check | N/A | Skip download + validation (eTag match) to save time/CPU |

**Design rule:** Do **not** put re-validation on the Slide Review button. Opening findings must stay instant. Re-analysis is opt-in via a separate control.

---

## Architecture overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Frontend                                                                 │
│  • Slide Review  → GET report + annotations (cached snapshot)             │
│  • Re-check deck → POST /api/wsr/revalidate → bump refreshKey → refetch   │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ REST
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Backend                                                                  │
│  1. Resolve local PPT path + template_id (week manifest)                  │
│  2. If SharePoint active + from_sharepoint:                               │
│       GET drive item metadata (eTag)                                      │
│       If eTag == fingerprint && !force → return status=unchanged          │
│       Else GET …/content → overwrite local PPT                            │
│  3. run_wsr_validation(annotate=True) → report JSON + slide_*.png         │
│  4. Save fingerprint { eTag, validated_at, … }                            │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ Microsoft Graph (app-only)
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  SharePoint document library                                              │
│  {SHAREPOINT_UPLOAD_FOLDER}/WSR_{start}_{end}[_vN].pptx                   │
└──────────────────────────────────────────────────────────────────────────┘
```

**Source of truth for Re-check (when SharePoint is on):** remote file in the library.  
**Source of truth for Slide Review:** local validation artifacts under `output/`.

---

## UX contract (keep these separate)

| Control | Label | Behavior |
|---------|-------|----------|
| **Slide Review** | Existing black button | Opens inset panel; loads `validation-report` + `annotations` once; no Graph; no validate |
| **Re-check deck** | New bordered red/white button | Calls `POST /revalidate`; shows toast; on `validated` optionally auto-opens Slide Review; bumps `refreshKey` so panel refetches |

Place both next to SharePoint / Download on:

- View WSR deck detail (`ViewWSRPage`)
- Post-generate / report panel (`WSRReportPanel`)

---

## Prerequisites (target codebase)

### Already required (generation + Slide Review)

- [ ] Local WSR PPT path helpers (e.g. `WSR_{start}_{end}[_vN].pptx`)
- [ ] `run_wsr_validation` / `validate_deck(..., annotate=True)` writing per-deck report + PNGs
- [ ] GET endpoints (or equivalents):
  - validation report JSON
  - annotation list + image serve
- [ ] Week manifest (or similar) storing `template_id` per variant
- [ ] Frontend Slide Review panel that consumes those GET APIs

### Required for SharePoint pull path

Same Entra app-only setup as upload:

| Item | Notes |
|------|--------|
| `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_CLIENT_SECRET` | Client credentials |
| `SHAREPOINT_SITE_ID` | Site hosting the library |
| `SHAREPOINT_UPLOAD_FOLDER` | e.g. `Shared Documents/WSR` |
| `SHAREPOINT_DRIVE_ID` | Optional; blank = site default drive |
| `CLOUD_UPLOAD_PROVIDER=sharepoint` or `SHAREPOINT_UPLOAD_ENABLED=true` | Active provider |
| Graph application permission | **`Sites.ReadWrite.All`** (admin consent) — write already covers download/read of site files |

No new Graph permission is typically needed beyond what upload already uses. Confirm admin consent and that the app can access the target site/library.

### Env example

```env
CLOUD_UPLOAD_PROVIDER=sharepoint
SHAREPOINT_UPLOAD_ENABLED=true
AZURE_CLIENT_ID=...
AZURE_TENANT_ID=...
AZURE_CLIENT_SECRET=...
SHAREPOINT_SITE_ID=hostname,siteCollectionId,webId
SHAREPOINT_UPLOAD_FOLDER=Shared Documents/WSR
# SHAREPOINT_DRIVE_ID=
```

---

## Files to port / create

### Backend — new

| Path | Role |
|------|------|
| `app/services/wsr_revalidate_service.py` | Core: eTag compare → optional download → `run_wsr_validation` → fingerprint |
| (optional) fingerprint helper in `app/paths.py` | `wsr_validation_fingerprint_path(...)` |

### Backend — modify

| Path | Change |
|------|--------|
| `app/services/sharepoint_upload_service.py` | Upload returns item meta (`webUrl`, `id`, `eTag`, …); add `get_sharepoint_item_metadata`, `download_ppt_from_sharepoint`; enrich saved meta JSON |
| `app/services/cloud_upload_service.py` | Pass through richer SharePoint item + `variant` when saving meta |
| `app/services/wsr_service.py` | Pass `variant=` into cloud upload on generate |
| `app/services/wsr_job_service.py` | After post-gen validation, call `record_validation_fingerprint_from_sharepoint` |
| `app/schemas/wsr.py` | `WsrRevalidateRequest`, `WsrRevalidateResponse` |
| `app/api/routes/wsr.py` | `POST /api/wsr/revalidate` |
| `app/paths.py` | `wsr_validation_fingerprint_path` |
| `scripts/upload_ppt_to_sharepoint.py` | Handle dict return from `upload_ppt_to_sharepoint` |

### Frontend — modify

| Path | Change |
|------|--------|
| `src/api/wsr.ts` | `revalidateWsrDeck()`, `WsrRevalidateResponse` |
| `src/components/WsrSlidePanel.tsx` | Export `RecheckDeckButton`; add `refreshKey` prop to reset cache |
| `src/components/ViewWSRPage.tsx` | Wire Re-check + toast + `refreshKey` |
| `src/components/WSRReportPanel.tsx` | Same wiring on generate/view panel |

### Disk artifacts (created at runtime)

| Artifact | Example |
|----------|---------|
| Validation report | `output/WSR_{start}_{end}[_vN]_validation_report.json` |
| Annotated PNGs | `output/WSR_{start}_{end}[_vN]_validation/slide_*.png` |
| SharePoint meta | `output/WSR_{start}_{end}[_vN]_sharepoint.json` (legacy week-level file also kept for v1) |
| Validation fingerprint | `output/WSR_{start}_{end}[_vN]_validation_fingerprint.json` |

Fingerprint shape:

```json
{
  "validated_at": "2026-10-27T15:30:00+00:00",
  "source": "sharepoint",
  "filename": "WSR_2026-10-26_2026-10-30.pptx",
  "variant": 1,
  "template_id": "e9987619115f",
  "eTag": "\"{GUID},2\"",
  "id": "...",
  "lastModifiedDateTime": "...",
  "driveId": "...",
  "webUrl": "https://..."
}
```

---

## API contract

### `POST /api/wsr/revalidate`

**Request body**

```json
{
  "start_date": "2026-10-26",
  "end_date": "2026-10-30",
  "variant": 1,
  "template_id": null,
  "from_sharepoint": true,
  "force": false
}
```

| Field | Default | Meaning |
|-------|---------|---------|
| `variant` | `1` | Deck variant (`_v2` filename suffix when > 1) |
| `template_id` | `null` | Override; else taken from week manifest |
| `from_sharepoint` | `true` | Attempt Graph pull when provider is SharePoint |
| `force` | `false` | If `true`, ignore eTag match and always download+validate |

**Response**

```json
{
  "status": "unchanged",
  "message": "SharePoint copy matches the last check — skipped download and re-validation.",
  "from_sharepoint": true,
  "pulled": false,
  "force": false,
  "variant": 1,
  "template_id": "e9987619115f",
  "eTag": "\"{...}\"",
  "deck_pass": true,
  "findings_count": 6,
  "fail_count": 0,
  "warn_count": 6
}
```

| `status` | Meaning |
|----------|---------|
| `unchanged` | Remote eTag == fingerprint; report already present; **no** download/validate |
| `validated` | Validation ran (after pull and/or local-only) |

**Errors**

| HTTP | When |
|------|------|
| `404` | Local deck missing (and cannot pull), or template_id unresolved |
| `502` | Validation finished but report missing / Graph runtime error surfaced as RuntimeError |
| `500` | Unexpected failure |

### Existing read APIs (unchanged — used by Slide Review)

| Method | Path | Role |
|--------|------|------|
| GET | `/api/wsr/validation-report?start_date&end_date&variant` | Findings JSON |
| GET | `/api/wsr/annotations?...` | Annotated PNG metadata + `image_url`s |
| GET | `/api/wsr/annotation-image?filename&...` | Serve one PNG |

---

## Backend logic (porting steps)

### 1) SharePoint download + metadata

Reuse the same path builder as upload, but:

- Metadata: `GET /drives/{driveId}/root:/{folder}/{filename}:`  
  or `GET /sites/{siteId}/drive/root:/{folder}/{filename}:`
- Content: same URL + `:/content`

Normalize Graph driveItem fields to: `webUrl`, `id`, `eTag` (fallback `cTag`), `lastModifiedDateTime`, `name`, `size`, `driveId`.

Upload should return this dict (not only `webUrl`) and persist it into `*_sharepoint.json`.

Remote filename must match the **local PPT basename** (including `_v2` for variants).

### 2) Revalidate service algorithm

```
resolve ppt_path + template_id
if from_sharepoint and provider == sharepoint:
  meta = GET metadata(filename)
  if not force and meta.eTag == fingerprint.eTag and report exists:
    return status=unchanged (+ summary from existing report)
  download content → overwrite ppt_path
  pulled = true
else:
  require local ppt_path exists
run_wsr_validation(...)
save fingerprint from remote meta (if any)
return status=validated + finding counts
```

Fallbacks:

- SharePoint metadata/download fails but local PPT exists → validate local and note in logs/message path.
- After generation validation, best-effort `record_validation_fingerprint_from_sharepoint` so the first Re-check can skip if nobody edited SharePoint.

### 3) Wire the route

```python
@router.post("/revalidate", response_model=WsrRevalidateResponse)
def revalidate_wsr_deck_endpoint(body: WsrRevalidateRequest) -> WsrRevalidateResponse:
    result = revalidate_wsr_deck(
        body.start_date,
        body.end_date,
        variant=body.variant,
        template_id=body.template_id,
        from_sharepoint=body.from_sharepoint,
        force=body.force,
    )
    return WsrRevalidateResponse(**result)
```

Map `FileNotFoundError` → 404, `RuntimeError` → 502.

---

## Frontend logic (porting steps)

### 1) API client

```ts
export async function revalidateWsrDeck(options: {
  startDate: string;
  endDate: string;
  variant?: number;
  templateId?: string | null;
  fromSharepoint?: boolean;
  force?: boolean;
}): Promise<WsrRevalidateResponse> {
  const res = await fetch("/api/wsr/revalidate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start_date: options.startDate,
      end_date: options.endDate,
      variant: options.variant ?? 1,
      template_id: options.templateId ?? null,
      from_sharepoint: options.fromSharepoint ?? true,
      force: options.force ?? false,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
```

Suggested `fromSharepoint`: `Boolean(deck.cloud_web_url)` so weeks without a cloud link only re-validate local.

### 2) `RecheckDeckButton`

Separate component from `SlideReviewButton`. Show spinner label **Re-checking…** while the POST is in flight. Disable while loading.

### 3) Cache invalidation on Slide Review panel

Add `refreshKey?: number`. When it changes, clear `dataLoaded` / report / annotations so the next open (or already-open panel) refetches GET report + annotations.

Do **not** close the panel solely because `refreshKey` changed (only reset data).

### 4) Handler pattern

```ts
const result = await revalidateWsrDeck({ ... });
setSlideRefreshKey((k) => k + 1);
showNotice(result.message + optional finding counts);
if (result.status === "validated") setSlideReviewOpen(true);
```

For `unchanged`, still bump `refreshKey` if you want a refresh, but auto-opening Slide Review is optional (this codebase opens only on `validated`).

---

## Porting checklist (other codebase)

Use this as an ordered implementation list:

1. **Confirm Slide Review works** on pre-computed artifacts (GET report + annotations).
2. **Confirm SharePoint upload works** (same site/folder/credentials).
3. Extend SharePoint service: metadata GET + content download + richer upload meta.
4. Add fingerprint path helper + `wsr_revalidate_service.py`.
5. Add schemas + `POST /revalidate`.
6. After generation validation, record SharePoint eTag fingerprint.
7. Frontend: `revalidateWsrDeck` + `RecheckDeckButton` + `refreshKey`.
8. Wire button on View WSR / report screens **next to** Slide Review (not instead of).
9. Smoke tests below.
10. Document env + Graph consent for the target environment.

---

## Smoke tests

### A) Local re-validate (no SharePoint pull)

```powershell
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/api/wsr/revalidate" `
  -ContentType "application/json" `
  -Body '{"start_date":"2026-10-26","end_date":"2026-10-30","variant":1,"from_sharepoint":false,"force":false}'
```

Expect: `"status":"validated"`, `findings_count` present, report/PNGs refreshed under `output/`.

### B) Unchanged SharePoint skip

1. Generate (or Re-check once) so fingerprint exists.
2. Do **not** edit the SharePoint file.
3. Call with `"from_sharepoint": true`, `"force": false`.

Expect: `"status":"unchanged"`, `"pulled": false`, fast response.

### C) Changed SharePoint re-run

1. Edit/save the PPT in SharePoint (Office Online or desktop sync).
2. Call Re-check again (`from_sharepoint: true`).

Expect: `"status":"validated"`, `"pulled": true`, new annotations; Slide Review shows updated findings.

### D) Force

`"force": true` even when eTag matches → always download + validate → `"status":"validated"`.

### E) UI

1. **Slide Review** alone → no long wait; shows last snapshot.
2. **Re-check deck** → loading state → toast → on validate, panel refreshes.

---

## Non-goals / caveats

| Topic | Notes |
|-------|--------|
| Auto re-validate on Slide Review open | Intentionally **not** done |
| Sync SharePoint → local on every page load | Not done; only on Re-check |
| OneDrive / Google Drive pull | Re-check SharePoint path is implemented; other providers fall back to local validate |
| Concurrent Office Online edits | Graph returns a saved version; unsaved browser buffers are not visible |
| Overwrite policy | Pull overwrites the server’s local PPT; a later generate/upload can overwrite SharePoint with local again |
| Rendered bounds / COM | Server validation uses the same flags as post-gen (`use_rendered_bounds=False` in this app) — keep parity when porting |
| First Re-check after old decks | Decks generated before fingerprinting always validate once until a fingerprint is written |

---

## Related docs

- `docs/WSR_SHAREPOINT_ONEDRIVE_UPLOAD_GUIDE.md` — cloud upload / Entra setup context (note: some sections may lag behind the current SharePoint app-only implementation; prefer `.env.example` + `sharepoint_upload_service.py` as source of truth for upload).
- Validation engine: `app/validation/engine.py` (`validate_deck`)
- Post-gen wrapper: `app/services/wsr_service.py` (`run_wsr_validation`)

---

## Reference: key symbols in this repo

| Symbol | Location |
|--------|----------|
| `revalidate_wsr_deck` | `app/services/wsr_revalidate_service.py` |
| `record_validation_fingerprint_from_sharepoint` | same |
| `download_ppt_from_sharepoint` / `get_sharepoint_item_metadata` | `app/services/sharepoint_upload_service.py` |
| `POST /api/wsr/revalidate` | `app/api/routes/wsr.py` |
| `WsrRevalidateRequest` / `WsrRevalidateResponse` | `app/schemas/wsr.py` |
| `revalidateWsrDeck` | `Frontend/src/api/wsr.ts` |
| `RecheckDeckButton` | `Frontend/src/components/WsrSlidePanel.tsx` |
| UI wiring | `ViewWSRPage.tsx`, `WSRReportPanel.tsx` |
