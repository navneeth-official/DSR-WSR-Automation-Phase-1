import { useEffect, useState } from "react";
import { Loader2, MessageCircle, X } from "lucide-react";

interface StoryCommentModalProps {
  jiraKey: string;
  onClose: () => void;
  onSubmit?: (comment: string) => Promise<void>;
}

export function StoryCommentModal({ jiraKey, onClose, onSubmit }: StoryCommentModalProps) {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const handleSubmit = async () => {
    const text = comment.trim();
    if (!text) {
      setError("Enter a comment before adding.");
      return;
    }

    if (!onSubmit) {
      setError("Comment saving is not available yet. This will create a new story version when enabled.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      await onSubmit(text);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add comment");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-gray-200 bg-gray-50">
          <div className="flex items-start gap-3 min-w-0">
            <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-brand-red/10 text-brand-red flex-shrink-0">
              <MessageCircle className="w-4 h-4" />
            </span>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                Add comment
              </p>
              <h2 className="text-base font-semibold text-gray-900 truncate">{jiraKey}</h2>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md text-gray-400 hover:bg-white hover:text-gray-600"
            title="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-3">
          <textarea
            value={comment}
            onChange={(e) => {
              setComment(e.target.value);
              if (error) setError("");
            }}
            rows={4}
            placeholder="Write a comment for this story…"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-red/20 focus:border-brand-red/40 resize-y min-h-[96px]"
          />
          {!onSubmit && (
            <p className="text-xs text-gray-500 leading-relaxed">
              Saving comments requires the backend comment API to be available.
            </p>
          )}
          {error && (
            <p className="text-xs text-red-600">{error}</p>
          )}
        </div>

        <div className="px-5 py-4 border-t border-gray-200 bg-gray-50 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-white disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={submitting}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-orange text-sm font-medium text-white hover:bg-brand-orange-hover disabled:opacity-60"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Add comment
          </button>
        </div>
      </div>
    </div>
  );
}

export function StoryCommentButton({
  onClick,
  disabled,
}: {
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title="Add comment"
      className="inline-flex items-center justify-center w-7 h-7 rounded-md border border-gray-200 text-gray-500 hover:text-brand-red hover:border-brand-red/30 hover:bg-brand-red/10 disabled:opacity-40 disabled:pointer-events-none"
    >
      <MessageCircle className="w-3.5 h-3.5" />
    </button>
  );
}
