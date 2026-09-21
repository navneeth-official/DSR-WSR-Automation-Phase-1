import { useEffect, useRef } from "react";
import { INACTIVITY_TIMEOUT_MS } from "@/auth/session";

const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
  "click",
];

/**
 * Calls onExpire after INACTIVITY_TIMEOUT_MS with no pointer/keyboard activity.
 * Disabled when `enabled` is false (e.g. on the login screen).
 */
export function useSessionInactivity(
  enabled: boolean,
  onExpire: () => void,
): void {
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    if (!enabled) return;

    let timerId: number | null = null;

    const clearTimer = () => {
      if (timerId != null) {
        window.clearTimeout(timerId);
        timerId = null;
      }
    };

    const armTimer = () => {
      clearTimer();
      timerId = window.setTimeout(() => {
        onExpireRef.current();
      }, INACTIVITY_TIMEOUT_MS);
    };

    armTimer();

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, armTimer, { passive: true });
    }

    return () => {
      clearTimer();
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, armTimer);
      }
    };
  }, [enabled]);
}
