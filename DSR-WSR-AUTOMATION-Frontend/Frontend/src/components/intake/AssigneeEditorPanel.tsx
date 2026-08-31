import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, Users, X } from "lucide-react";
import {
  isCatalogTrackActive,
  isProjectTrackInactive,
  type TrackListItem,
} from "@/api/dsr";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/app/components/ui/tooltip";
import {
  assignTrackToEmployee,
  createEmployee,
  fetchEmployeeById,
  fetchEmployeesByTeam,
  updateEmployeeTrack,
} from "@/api/employees";

const DEFAULT_TEAM = "HEB";

interface TrackRow {
  project_id: number;
  project_name: string;
  is_active: boolean;
  /** True when added locally and not yet saved to the server. */
  isPending?: boolean;
}

function cloneTrackRows(rows: TrackRow[]): TrackRow[] {
  return rows.map((r) => ({ ...r }));
}

function uniqueEmployeesFromRows(
  rows: { employee_id: number; employee_name: string }[],
): { employee_id: number; employee_name: string }[] {
  const seen = new Set<number>();
  const out: { employee_id: number; employee_name: string }[] = [];
  for (const row of rows) {
    if (seen.has(row.employee_id)) continue;
    seen.add(row.employee_id);
    out.push({ employee_id: row.employee_id, employee_name: row.employee_name });
  }
  return out.sort((a, b) => a.employee_name.localeCompare(b.employee_name));
}

function employeeNameExists(
  employees: { employee_name: string }[],
  name: string,
): boolean {
  const normalized = name.trim().toLowerCase();
  if (!normalized) return false;
  return employees.some(
    (employee) => employee.employee_name.trim().toLowerCase() === normalized,
  );
}

const inputClass =
  "w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-red/20 focus:border-brand-red/50";
const selectClass =
  "text-sm border border-gray-200 rounded-lg px-2 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-brand-red/20 focus:border-brand-red/50";

const INACTIVE_TRACK_TOOLTIP =
  "This track is inactive. The track and assignment status are read-only and cannot be changed here.";

function InactiveTrackWarning() {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className="inline-flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-amber-100 text-[11px] font-bold text-amber-700 cursor-help"
          aria-label="Inactive track"
        >
          !
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[220px] bg-gray-900 text-white">
        {INACTIVE_TRACK_TOOLTIP}
      </TooltipContent>
    </Tooltip>
  );
}

export function AssigneeEditorPanel({
  trackCatalog,
  onChanged,
}: {
  trackCatalog: TrackListItem[];
  onChanged?: (message?: string) => void;
}) {
  const [name, setName] = useState("");
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(null);
  const [trackRows, setTrackRows] = useState<TrackRow[]>([]);
  const [savedSnapshot, setSavedSnapshot] = useState<TrackRow[]>([]);
  const [existingEmployees, setExistingEmployees] = useState<
    { employee_id: number; employee_name: string }[]
  >([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [showAddTrack, setShowAddTrack] = useState(false);
  const [addTrackProjectId, setAddTrackProjectId] = useState<number | "">("");
  const [addTrackActive, setAddTrackActive] = useState(true);
  const [loadingEmployee, setLoadingEmployee] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const assignedProjectIds = useMemo(
    () => new Set(trackRows.map((r) => r.project_id)),
    [trackRows],
  );

  const assignableTracks = useMemo(
    () => trackCatalog.filter(isCatalogTrackActive),
    [trackCatalog],
  );

  const availableTracks = useMemo(
    () => assignableTracks.filter((t) => !assignedProjectIds.has(t.project_id)),
    [assignableTracks, assignedProjectIds],
  );

  const resetForm = useCallback(() => {
    setName("");
    setSelectedEmployeeId(null);
    setTrackRows([]);
    setSavedSnapshot([]);
    setPickerOpen(false);
    setShowAddTrack(false);
    setAddTrackProjectId("");
    setAddTrackActive(true);
    setError("");
  }, []);

  const refreshEmployeeList = useCallback(() => {
    void fetchEmployeesByTeam(DEFAULT_TEAM).then((response) => {
      setExistingEmployees(uniqueEmployeesFromRows(response.employees));
    });
  }, []);

  useEffect(() => {
    refreshEmployeeList();
  }, [refreshEmployeeList]);

  const applyEmployeeDetail = (detail: {
    employee_id: number;
    employee_name: string;
    tracks: { project_id: number; project_name: string; is_active: boolean }[];
  }) => {
    const rows = detail.tracks.map((t) => ({
      project_id: t.project_id,
      project_name: t.project_name,
      is_active: t.is_active,
      isPending: false,
    }));
    setSelectedEmployeeId(detail.employee_id);
    setName(detail.employee_name);
    setTrackRows(cloneTrackRows(rows));
    setSavedSnapshot(cloneTrackRows(rows));
    setShowAddTrack(false);
    setPickerOpen(false);
  };

  const loadExistingEmployee = async (employeeId: number) => {
    setLoadingEmployee(true);
    setError("");
    try {
      const detail = await fetchEmployeeById(employeeId);
      applyEmployeeDetail(detail);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load employee");
    } finally {
      setLoadingEmployee(false);
    }
  };

  const handleSelectExisting = (employeeId: number) => {
    void loadExistingEmployee(employeeId);
  };

  const handleClearExisting = () => {
    resetForm();
  };

  const handleStatusChange = (projectId: number, isActive: boolean) => {
    setTrackRows((rows) =>
      rows.map((r) => (r.project_id === projectId ? { ...r, is_active: isActive } : r)),
    );
  };

  const handleRemovePendingTrack = (projectId: number) => {
    setTrackRows((rows) => rows.filter((r) => r.project_id !== projectId));
  };

  const handleConfirmAddTrack = () => {
    if (addTrackProjectId === "") {
      setError("Select a track.");
      return;
    }

    const track = assignableTracks.find((t) => t.project_id === addTrackProjectId);
    if (!track) {
      setError("Select an active track.");
      return;
    }

    setTrackRows((rows) => [
      ...rows,
      {
        project_id: track.project_id,
        project_name: track.project_name,
        is_active: addTrackActive,
        isPending: true,
      },
    ]);
    setShowAddTrack(false);
    setAddTrackProjectId("");
    setAddTrackActive(true);
    setError("");
  };

  const handleSaveNew = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Employee name is required.");
      return;
    }
    if (trackRows.length === 0) {
      setError("Add at least one track assignment.");
      return;
    }
    if (employeeNameExists(existingEmployees, trimmed)) {
      setError(`Assignee "${trimmed}" already exists (case-insensitive match).`);
      return;
    }

    setSaving(true);
    setError("");
    try {
      const [first, ...rest] = trackRows;
      const created = await createEmployee({
        employee_name: trimmed,
        team_name: DEFAULT_TEAM,
        project_id: first.project_id,
        is_active: first.is_active,
      });
      for (const row of rest) {
        await assignTrackToEmployee(created.employee_id, {
          project_id: row.project_id,
          is_active: row.is_active,
        });
      }
      onChanged?.("Assignee created successfully.");
      resetForm();
      refreshEmployeeList();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add employee");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveExisting = async () => {
    if (selectedEmployeeId === null) return;

    setSaving(true);
    setError("");
    try {
      for (const row of trackRows) {
        if (isProjectTrackInactive(trackCatalog, row.project_id)) {
          continue;
        }

        if (row.isPending) {
          await assignTrackToEmployee(selectedEmployeeId, {
            project_id: row.project_id,
            is_active: row.is_active,
          });
          continue;
        }

        const saved = savedSnapshot.find((s) => s.project_id === row.project_id);
        if (saved && saved.is_active !== row.is_active) {
          await updateEmployeeTrack(selectedEmployeeId, row.project_id, row.is_active);
        }
      }

      onChanged?.("Assignee updated successfully.");
      const detail = await fetchEmployeeById(selectedEmployeeId);
      applyEmployeeDetail(detail);
      refreshEmployeeList();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setSaving(false);
    }
  };

  const handleCancelExisting = () => {
    setTrackRows(cloneTrackRows(savedSnapshot));
    setShowAddTrack(false);
    setAddTrackProjectId("");
    setAddTrackActive(true);
    setError("");
  };

  const openAddTrackRow = () => {
    if (availableTracks.length === 0) {
      setError("No more tracks available to assign.");
      return;
    }
    setShowAddTrack(true);
    setAddTrackProjectId(availableTracks[0].project_id);
    setAddTrackActive(true);
    setError("");
  };

  const isExisting = selectedEmployeeId !== null;

  const hasUnsavedChanges = useMemo(() => {
    if (!isExisting) {
      return name.trim() !== "" || trackRows.length > 0 || showAddTrack;
    }
    if (showAddTrack) return true;
    if (trackRows.some((row) => row.isPending)) return true;
    if (trackRows.length !== savedSnapshot.length) return true;
    return trackRows.some((row) => {
      const saved = savedSnapshot.find((s) => s.project_id === row.project_id);
      return !saved || saved.is_active !== row.is_active;
    });
  }, [isExisting, name, trackRows, savedSnapshot, showAddTrack]);

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm font-semibold text-gray-800">
          {isExisting ? "Edit assignee" : "Add assignee"}
        </p>
        <p className="text-[11px] text-gray-500 mt-0.5">
          {isExisting
            ? "Update track assignments and active status, then save."
            : `Create a new assignee and link to tracks (${DEFAULT_TEAM}).`}
        </p>
      </div>

      <div className="space-y-1">
        <label className="text-[11px] font-medium text-gray-500">Name</label>
        <div className="flex gap-1.5">
          <input
            type="text"
            value={name}
            onChange={(e) => {
              if (!isExisting) setName(e.target.value);
            }}
            readOnly={isExisting}
            placeholder="Full name"
            className={`${inputClass} flex-1 min-w-0 ${isExisting ? "bg-gray-50 text-gray-700" : ""}`}
          />
          <div className="relative flex-shrink-0">
            <button
              type="button"
              onClick={() => setPickerOpen((o) => !o)}
              disabled={loadingEmployee}
              className="h-full px-2.5 border border-gray-200 rounded-lg text-brand-red hover:bg-brand-red/10 disabled:opacity-50"
              title="Select existing employee"
            >
              <Users className="w-4 h-4" />
            </button>
            {pickerOpen && (
              <div className="absolute right-0 top-full mt-1 z-10 w-52 max-h-48 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg py-1">
                <button
                  type="button"
                  onClick={handleClearExisting}
                  className="w-full text-left px-3 py-2 text-xs text-brand-red hover:bg-brand-red/10 border-b border-gray-100"
                >
                  + New assignee
                </button>
                {existingEmployees.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-gray-400">No employees yet</p>
                ) : (
                  existingEmployees.map((emp) => (
                    <button
                      key={emp.employee_id}
                      type="button"
                      onClick={() => handleSelectExisting(emp.employee_id)}
                      className={`w-full text-left px-3 py-2 text-xs hover:bg-gray-50 ${
                        selectedEmployeeId === emp.employee_id
                          ? "bg-brand-red/10 text-brand-red font-medium"
                          : "text-gray-700"
                      }`}
                    >
                      {emp.employee_name}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {loadingEmployee ? (
        <p className="text-xs text-gray-400">Loading assignments…</p>
      ) : (
        <>
          {trackRows.length > 0 && (
            <div className="space-y-2">
              <label className="text-[11px] font-medium text-gray-500">Tracks</label>
              {trackRows.map((row, index) => {
                const trackInactiveInCatalog = isProjectTrackInactive(
                  trackCatalog,
                  row.project_id,
                );
                const showInactiveWarning =
                  isExisting && !row.isPending && trackInactiveInCatalog;

                return (
                <div key={`${row.project_id}-${index}`} className="flex items-center gap-1.5">
                  {isExisting && !row.isPending ? (
                    <select
                      value={row.project_id}
                      disabled
                      className={`${selectClass} flex-1 min-w-0 bg-gray-50 text-gray-600 cursor-not-allowed`}
                    >
                      <option value={row.project_id}>{row.project_name}</option>
                    </select>
                  ) : (
                    <select
                      value={row.project_id}
                      onChange={(e) => {
                        const nextId = Number(e.target.value);
                        const track = assignableTracks.find((t) => t.project_id === nextId);
                        if (!track) return;
                        setTrackRows((rows) =>
                          rows.map((r) =>
                            r.project_id === row.project_id
                              ? {
                                  project_id: track.project_id,
                                  project_name: track.project_name,
                                  is_active: r.is_active,
                                  isPending: r.isPending,
                                }
                              : r,
                          ),
                        );
                      }}
                      className={`${selectClass} flex-1 min-w-0`}
                    >
                      {assignableTracks
                        .filter(
                          (t) =>
                            t.project_id === row.project_id ||
                            !trackRows.some((r) => r.project_id === t.project_id),
                        )
                        .map((t) => (
                          <option key={t.project_id} value={t.project_id}>
                            {t.project_name}
                          </option>
                        ))}
                    </select>
                  )}
                  <select
                    value={row.is_active ? "active" : "inactive"}
                    disabled={showInactiveWarning}
                    onChange={(e) =>
                      handleStatusChange(row.project_id, e.target.value === "active")
                    }
                    className={`${selectClass} w-[5.5rem] flex-shrink-0 ${
                      showInactiveWarning
                        ? "bg-gray-50 text-gray-600 cursor-not-allowed"
                        : ""
                    }`}
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                  {showInactiveWarning ? <InactiveTrackWarning /> : null}
                  {(!isExisting || row.isPending) && (
                    <button
                      type="button"
                      onClick={() => handleRemovePendingTrack(row.project_id)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg flex-shrink-0"
                      title="Remove track"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              );
              })}
            </div>
          )}

          {showAddTrack ? (
            <div className="flex items-center gap-1.5 pt-1">
              {assignableTracks.length === 0 && trackCatalog.length === 0 ? (
                <p className="text-xs text-gray-400">Loading tracks…</p>
              ) : assignableTracks.length === 0 ? (
                <p className="text-xs text-gray-400">No active tracks available to assign.</p>
              ) : (
                <>
                  <select
                    value={addTrackProjectId}
                    onChange={(e) => setAddTrackProjectId(Number(e.target.value))}
                    className={`${selectClass} flex-1 min-w-0`}
                  >
                    {availableTracks.map((t) => (
                      <option key={t.project_id} value={t.project_id}>
                        {t.project_name}
                      </option>
                    ))}
                  </select>
                  <select
                    value={addTrackActive ? "active" : "inactive"}
                    onChange={(e) => setAddTrackActive(e.target.value === "active")}
                    className={`${selectClass} w-[5.5rem] flex-shrink-0`}
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => setShowAddTrack(false)}
                    className="p-2 text-gray-400 hover:text-gray-600 rounded-lg flex-shrink-0"
                    title="Cancel"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </>
              )}
            </div>
          ) : (
            availableTracks.length > 0 && (
              <button
                type="button"
                onClick={openAddTrackRow}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-red hover:text-brand-red-dark"
              >
                <Plus className="w-3.5 h-3.5" />
                Assign to track
              </button>
            )
          )}

          {showAddTrack && availableTracks.length > 0 && (
            <button
              type="button"
              disabled={saving}
              onClick={handleConfirmAddTrack}
              className="w-full px-3 py-1.5 text-xs font-medium text-brand-red border border-brand-red/30 hover:bg-brand-red/10 rounded-lg disabled:opacity-50"
            >
              Add track assignment
            </button>
          )}
        </>
      )}

      {error && <p className="text-xs text-red-500">{error}</p>}

      <div className="flex justify-end gap-2 pt-1">
        {isExisting ? (
          <>
            <button
              type="button"
              onClick={handleCancelExisting}
              disabled={!hasUnsavedChanges || saving || loadingEmployee}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!hasUnsavedChanges || saving || loadingEmployee}
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
              disabled={!hasUnsavedChanges || saving || loadingEmployee}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Clear
            </button>
            <button
              type="button"
              disabled={!hasUnsavedChanges || saving || assignableTracks.length === 0 || loadingEmployee}
              onClick={() => void handleSaveNew()}
              className="px-3 py-1.5 text-xs font-medium text-white bg-brand-orange hover:bg-brand-orange-hover rounded-lg disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
