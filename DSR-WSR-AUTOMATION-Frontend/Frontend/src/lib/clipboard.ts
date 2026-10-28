/**
 * Copy text to the clipboard.
 *
 * `navigator.clipboard` only exists in secure contexts (HTTPS / localhost). When the app is
 * served over plain HTTP (e.g. `http://<VM-IP>`) it is undefined, so we fall back to the
 * legacy `document.execCommand("copy")` path with a temporary off-screen textarea.
 *
 * Resolves to `true` when the text was copied, `false` otherwise.
 */
export async function copyTextToClipboard(text: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      console.warn("navigator.clipboard.writeText failed, using fallback:", error);
    }
  }
  return legacyCopy(text);
}

function legacyCopy(text: string): boolean {
  const previouslyFocused = document.activeElement as HTMLElement | null;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.setAttribute("aria-hidden", "true");
  Object.assign(textarea.style, {
    position: "fixed",
    top: "0",
    left: "0",
    width: "1px",
    height: "1px",
    padding: "0",
    border: "none",
    outline: "none",
    boxShadow: "none",
    opacity: "0",
  });
  document.body.appendChild(textarea);

  try {
    textarea.focus();
    textarea.select();
    textarea.setSelectionRange(0, text.length);
    return document.execCommand("copy");
  } catch (error) {
    console.warn("document.execCommand('copy') failed:", error);
    return false;
  } finally {
    document.body.removeChild(textarea);
    previouslyFocused?.focus?.();
  }
}
