import { useCallback, useEffect, useMemo, useState } from "react";
import { Layers } from "lucide-react";
import {
  createTrack,
  fetchTracks,
  updateTrack,
  type TrackResponse,
} from "@/api/dsr";

const inputClass =
  "w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-red/20 focus:border-brand-red/50";
const selectClass =
  "text-sm border border-gray-200 rounded-lg px-2 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brand-red/20 focus:border-brand-red/50";

function deriveProjectKey(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "";
  const parts = trimmed.split(/\s+/);
  if (parts.length === 1) return parts[0].toUpperCase();
  return parts[0].toUpperCase();
}

function trackNameExists(tracks: TrackResponse[], name: string): boolean {
  const normalized = name.trim().toLowerCase();
  if (!normalized) return false;
  return tracks.some(
    (track) => track.project_name.trim().toLowerCase() === normalized,
  );
}

function trackKeyExists(tracks: TrackResponse[], key: string): boolean {
  const normalized = key.trim().toLowerCase();
  if (!normalized) return false;
  return tracks.some(
    (track) => track.project_key.trim().toLowerCase() === normalized,
  );
}

export function TrackEditorPanel({
  onChanged,
}: {
  onChanged?: (message?: string) => void;
}) {
  const [trackName, setTrackName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [selectedTrackId, setSelectedTrackId] = useState<number | null>(null);
  const [savedIsActive, setSavedIsActive] = useState(true);
  const [existingTracks, setExistingTracks] = useState<TrackResponse[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loadingTracks, setLoadingTracks] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const isExisting = selectedTrackId !== null;

  const hasUnsavedChanges = useMemo(() => {
    if (isExisting) {
      return isActive !== savedIsActive;
    }
    return trackName.trim() !== "" || !isActive;
  }, [isExisting, isActive, savedIsActive, trackName]);

  const refreshTrackList = useCallback(() => {
    setLoadingTracks(true);
    void fetchTracks()
      .then((response) => {
        setExistingTracks(
          [...response.tracks].sort((a, b) =>
            a.project_name.localeCompare(b.project_name),
          ),
        );
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load tracks");
      })
      .finally(() => setLoadingTracks(false));
  }, []);

  useEffect(() => {
    refreshTrackList();
  }, [refreshTrackList]);

  const resetForm = () => {
    setTrackName("");
    setIsActive(true);
    setSelectedTrackId(null);
    setSavedIsActive(true);
    setPickerOpen(false);
    setError("");
  };

  const applyExistingTrack = (track: TrackResponse) => {
    setSelectedTrackId(track.project_id);
    setTrackName(track.project_name);
    setIsActive(track.is_active);
    setSavedIsActive(track.is_active);
    setPickerOpen(false);
    setError("");
  };

  const handleSelectExisting = (trackId: number) => {
    const track = existingTracks.find((t) => t.project_id === trackId);
    if (track) applyExistingTrack(track);
  };

  const handleSaveNew = async () => {
    const trimmed = trackName.trim();
    if (!trimmed) {
      setError("Track name is required.");
      return;
    }

    const projectKey = deriveProjectKey(trimmed);
    if (trackNameExists(existingTracks, trimmed)) {
      setError(`Track "${trimmed}" already exists (case-insensitive match).`);
      return;
    }
    if (trackKeyExists(existingTracks, projectKey)) {
      setError(`Track key "${projectKey}" already exists (case-insensitive match).`);
      return;
    }

    setSaving(true);
    setError("");
    try {
      await createTrack({
        project_key: projectKey,
        project_name: trimmed,
        is_active: isActive,
      });
      onChanged?.("Track created successfully.");
      resetForm();
      refreshTrackList();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add track");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveExisting = async () => {
    if (selectedTrackId === null) return;

    setSaving(true);
    setError("");
    try {
      if (isActive !== savedIsActive) {
        const updated = await updateTrack(selectedTrackId, { is_active: isActive });
        applyExistingTrack(updated);
        onChanged?.(
          isActive
            ? "Track activated successfully."
            : "Track set to inactive. Active assignees on this track were deactivated.",
        );
      }
      refreshTrackList();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save track");
    } finally {
      setSaving(false);
    }
  };

  const handleCancelExisting = () => {
    setIsActive(savedIsActive);
    setError("");
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-semibold text-gray-800">
          {isExisting ? "Edit track" : "Add track"}
        </p>
        <p className="text-[11px] text-gray-500 mt-0.5">
          {isExisting
            ? "Update active status for an existing track, then save."
            : "Create a new track in the projects table."}
        </p>
      </div>

      <div className="space-y-1">
        <label className="text-[11px] font-medium text-gray-500">Track name</label>
        <div className="flex gap-1.5">
          <input
            type="text"
            value={trackName}
            onChange={(e) => {
              if (!isExisting) setTrackName(e.target.value);
            }}
            readOnly={isExisting}
            placeholder="e.g. Cost Core Service"
            className={`${inputClass} flex-1 min-w-0 ${isExisting ? "bg-gray-50 text-gray-700" : ""}`}
          />
          <div className="relative flex-shrink-0">
            <button
              type="button"
              onClick={() => setPickerOpen((o) => !o)}
              disabled={loadingTracks}
              className="h-full px-2.5 border border-gray-200 rounded-lg text-brand-red hover:bg-brand-red/10 disabled:opacity-50"
              title="Select existing track"
            >
              <Layers className="w-4 h-4" />
            </button>
            {pickerOpen && (
              <div className="absolute right-0 top-full mt-1 z-10 w-56 max-h-48 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg py-1">
                <button
                  type="button"
                  onClick={resetForm}
                  className="w-full text-left px-3 py-2 text-xs text-brand-red hover:bg-brand-red/10 border-b border-gray-100"
                >
                  + New track
                </button>
                {existingTracks.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-gray-400">No tracks yet</p>
                ) : (
                  existingTracks.map((track) => (
                    <button
                      key={track.project_id}
                      type="button"
                      onClick={() => handleSelectExisting(track.project_id)}
                      className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 ${
                        selectedTrackId === track.project_id
                          ? "bg-brand-red/10 text-brand-red font-medium"
                          : "text-gray-700"
                      }`}
                    >
                      <span className="block truncate">{track.project_name}</span>
                      <span className="block text-[10px] text-gray-400 truncate">
                        {track.project_key} · {track.is_active ? "Active" : "Inactive"}
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {(trackName.trim() || isExisting) && (
        <div className="space-y-1">
          <label className="text-[11px] font-medium text-gray-500">Status</label>
          <select
            value={isActive ? "active" : "inactive"}
            onChange={(e) => setIsActive(e.target.value === "active")}
            className={`${selectClass} w-full`}
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      )}

      {loadingTracks && existingTracks.length === 0 ? (
        <p className="text-xs text-gray-400">Loading tracks…</p>
      ) : null}

      {error && <p className="text-xs text-red-500">{error}</p>}

      <div className="flex justify-end gap-2 pt-1">
        {isExisting ? (
          <>
            <button
              type="button"
              onClick={handleCancelExisting}
              disabled={!hasUnsavedChanges || saving || loadingTracks}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!hasUnsavedChanges || saving || loadingTracks}
              onClick={() => void handleSaveExisting()}
              className="px-3 py-1.5 text-xs font-medium text-white bg-brand-orange hover:bg-brand-orange-hover rounded-lg disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={resetForm}
              disabled={!hasUnsavedChanges || saving || loadingTracks}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!hasUnsavedChanges || saving || loadingTracks}
              onClick={() => void handleSaveNew()}
              className="px-3 py-1.5 text-xs font-medium text-white bg-brand-orange hover:bg-brand-orange-hover rounded-lg disabled:opacity-50"
            >
              {saving ? "Saving…" : "Add track"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
