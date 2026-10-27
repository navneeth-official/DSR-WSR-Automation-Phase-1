import { useCallback, useEffect, useState } from "react";
import {
  fetchWsrAnnotations,
  fetchWsrValidationReport,
  fetchWsrValidationStatus,
  runWsrValidation,
  type WsrAnnotationItem,
  type WsrValidationReport,
} from "@/api/wsr";

/** How often to ask the backend whether validation has finished. */
export const VALIDATION_POLL_MS = 5000;
/** Stop polling after this long and let the user retry manually. */
export const VALIDATION_POLL_TIMEOUT_MS = 3 * 60 * 1000;

export type WsrValidationPhase =
  | "idle"
  | "loading"
  | "pending"
  | "ready"
  | "not_started"
  | "error"
  | "timeout";

export interface WsrValidationState {
  phase: WsrValidationPhase;
  report: WsrValidationReport | null;
  annotations: WsrAnnotationItem[];
  message: string;
  /** Total findings (fail + warn) — used for the Slide Review badge. */
  findingCount: number | null;
  /** Re-check status/report from the server. */
  refresh: () => void;
  /** Ask the server to (re)run validation, then poll until it finishes. */
  rerun: () => Promise<void>;
}

interface LoadedState {
  phase: WsrValidationPhase;
  report: WsrValidationReport | null;
  annotations: WsrAnnotationItem[];
  message: string;
}

const IDLE: LoadedState = { phase: "idle", report: null, annotations: [], message: "" };

/**
 * Loads the validation report for one deck. The generation job is already "completed"
 * when validation starts, so the report is usually missing at first (404) — in that case
 * `validation-status` is polled every 5 s (max 3 min) until the report is ready.
 */
export function useWsrValidation(
  startDate: string,
  endDate: string,
  variant: number,
  enabled = true,
): WsrValidationState {
  const [state, setState] = useState<LoadedState>(IDLE);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setState(IDLE);
      return;
    }

    let cancelled = false;
    let timer: number | undefined;
    const startedAt = Date.now();
    setState({ ...IDLE, phase: "loading" });

    const loadReady = async (hasAnnotations: boolean) => {
      const report = await fetchWsrValidationReport(startDate, endDate, variant);
      if (cancelled) return;
      if (!report) {
        // Report vanished between status and fetch (e.g. re-run started) — poll again.
        schedule();
        return;
      }
      const annotations = hasAnnotations
        ? await fetchWsrAnnotations(startDate, endDate, variant).catch(() => [])
        : [];
      if (cancelled) return;
      setState({ phase: "ready", report, annotations, message: "" });
    };

    const check = async () => {
      try {
        const status = await fetchWsrValidationStatus(startDate, endDate, variant);
        if (cancelled) return;
        switch (status.status) {
          case "ready":
            await loadReady(status.has_annotations);
            return;
          case "pending":
            if (Date.now() - startedAt > VALIDATION_POLL_TIMEOUT_MS) {
              setState({
                ...IDLE,
                phase: "timeout",
                message: "Validation is taking longer than expected.",
              });
              return;
            }
            setState((prev) => ({ ...prev, phase: "pending", message: "" }));
            schedule();
            return;
          case "error":
            setState({
              ...IDLE,
              phase: "error",
              message: status.message || "Validation failed.",
            });
            return;
          default:
            setState({ ...IDLE, phase: "not_started" });
        }
      } catch (err) {
        if (cancelled) return;
        setState({
          ...IDLE,
          phase: "error",
          message: err instanceof Error ? err.message : "Could not load validation.",
        });
      }
    };

    function schedule() {
      timer = window.setTimeout(() => void check(), VALIDATION_POLL_MS);
    }

    void check();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [startDate, endDate, variant, enabled, reloadKey]);

  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);

  const rerun = useCallback(async () => {
    try {
      await runWsrValidation(startDate, endDate, variant);
    } catch (err) {
      setState({
        ...IDLE,
        phase: "error",
        message: err instanceof Error ? err.message : "Could not start validation.",
      });
      return;
    }
    setReloadKey((key) => key + 1);
  }, [startDate, endDate, variant]);

  return {
    ...state,
    findingCount: state.report ? state.report.summary.total_findings : null,
    refresh,
    rerun,
  };
}
