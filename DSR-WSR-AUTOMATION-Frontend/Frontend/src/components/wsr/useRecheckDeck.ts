import { useState } from "react";
import { revalidateWsrDeck, type WsrRevalidateResponse } from "@/api/wsr";
import {
  useFloatingNotice,
  type FloatingNoticeTone,
} from "@/components/ui/FloatingNotice";

interface UseRecheckDeckOptions {
  startDate: string;
  endDate: string;
  variant: number;
  templateId?: string | null;
  /** Pull the latest SharePoint copy first. Use `Boolean(deck.cloud_web_url)`. */
  fromSharepoint: boolean;
  /** Re-fetch the report + annotations (`useWsrValidation().refresh`). */
  onRefresh: () => void;
  /** Called after a re-check that actually re-ran validation (e.g. open Slide Review). */
  onValidated?: () => void;
}

function describe(result: WsrRevalidateResponse): string {
  if (result.status !== "validated") return result.message;
  const count = result.findings_count;
  if (count == null) return result.message;
  const summary =
    count === 0
      ? "No findings."
      : `${count} ${count === 1 ? "finding" : "findings"} (${result.fail_count ?? 0} must fix · ${
          result.warn_count ?? 0
        } polish).`;
  return `${result.message} ${summary}`;
}

/**
 * "Re-check deck" action. Separate from Slide Review (which only reads the last stored
 * snapshot): this calls `POST /api/wsr/revalidate`, then asks the validation hook to refetch.
 */
export function useRecheckDeck({
  startDate,
  endDate,
  variant,
  templateId,
  fromSharepoint,
  onRefresh,
  onValidated,
}: UseRecheckDeckOptions) {
  const [rechecking, setRechecking] = useState(false);
  const [tone, setTone] = useState<FloatingNoticeTone>("success");
  const notice = useFloatingNotice();

  const recheck = async () => {
    if (rechecking || !startDate || !endDate) return;
    setRechecking(true);
    try {
      const result = await revalidateWsrDeck({
        startDate,
        endDate,
        variant,
        templateId,
        fromSharepoint,
      });
      setTone("success");
      notice.show(describe(result));
      if (result.status === "validated") {
        onRefresh();
        onValidated?.();
      }
    } catch (err) {
      setTone("info");
      notice.show(`Re-check failed: ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      setRechecking(false);
    }
  };

  return {
    recheck,
    rechecking,
    notice: {
      message: notice.message,
      exiting: notice.exiting,
      dismiss: notice.dismiss,
      tone,
    },
  };
}
