import { useEffect, useRef } from "react";

const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
  "click",
];

/**
 * Calls `onTimeout` after `timeoutMs` with no user activity.
 * Resets the timer on pointer/keyboard/scroll activity.
 */
export function useInactivityTimeout(
  enabled: boolean,
  timeoutMs: number,
  onTimeout: () => void,
): void {
  const onTimeoutRef = useRef(onTimeout);
  onTimeoutRef.current = onTimeout;

  useEffect(() => {
    if (!enabled || timeoutMs <= 0) return;

    let timerId: number | null = null;

    const clearTimer = () => {
      if (timerId != null) {
        window.clearTimeout(timerId);
        timerId = null;
      }
    };

    const arm = () => {
      clearTimer();
      timerId = window.setTimeout(() => {
        onTimeoutRef.current();
      }, timeoutMs);
    };

    arm();

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, arm, { passive: true });
    }

    return () => {
      clearTimer();
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, arm);
      }
    };
  }, [enabled, timeoutMs]);
}
