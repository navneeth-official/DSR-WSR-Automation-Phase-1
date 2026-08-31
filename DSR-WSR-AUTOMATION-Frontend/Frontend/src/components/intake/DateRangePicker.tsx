import { useEffect, useRef, useState } from "react";
import { Calendar, ChevronDown } from "lucide-react";

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function fmtShort(d: Date): string {
  return d.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function sameDay(a: Date | null, b: Date | null): boolean {
  return !!a && !!b && a.toDateString() === b.toDateString();
}

function inRange(d: Date, start: Date | null, end: Date | null): boolean {
  if (!start || !end) return false;
  const t = d.getTime();
  return t >= start.getTime() && t <= end.getTime();
}

function DayCalendar({
  viewDate,
  onViewDateChange,
  start,
  end,
  picking,
  mode,
  onPick,
}: {
  viewDate: Date;
  onViewDateChange: (d: Date) => void;
  start: Date | null;
  end: Date | null;
  picking: "start" | "end";
  mode: "single" | "range";
  onPick: (d: Date) => void;
}) {
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7;
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: (Date | null)[] = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <button
          type="button"
          onClick={() => onViewDateChange(new Date(year, month - 1, 1))}
          className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-500 font-bold"
        >
          ‹
        </button>
        <span className="text-sm font-semibold text-gray-800">
          {MONTH_NAMES[month]} {year}
        </span>
        <button
          type="button"
          onClick={() => onViewDateChange(new Date(year, month + 1, 1))}
          className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-gray-100 text-gray-500 font-bold"
        >
          ›
        </button>
      </div>
      <p className="text-[10px] text-brand-red font-medium mb-2 text-center">
        {mode === "single"
          ? "Select date"
          : picking === "start"
            ? "Select start date"
            : "Select end date"}
      </p>
      <div className="grid grid-cols-7 mb-1">
        {DAY_NAMES.map((d) => (
          <div
            key={d}
            className={`text-center text-[10px] font-semibold py-1 ${
              d === "Sat" || d === "Sun" ? "text-gray-300" : "text-gray-400"
            }`}
          >
            {d}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-y-0.5">
        {cells.map((d, i) => {
          if (!d) return <div key={i} />;
          const isStart = sameDay(d, start);
          const isEnd = sameDay(d, end);
          const isWeekend = d.getDay() === 0 || d.getDay() === 6;
          const ranged = inRange(d, start, end);
          return (
            <button
              key={i}
              type="button"
              onClick={() => onPick(d)}
              className={[
                "h-7 w-full text-[11px] font-medium transition-colors rounded-full",
                isStart || isEnd ? "bg-brand-red text-white" : "",
                !isStart && !isEnd && ranged ? "bg-brand-red/10 text-brand-red" : "",
                !isStart && !isEnd && !ranged && isWeekend
                  ? "text-gray-300 hover:bg-gray-50"
                  : "",
                !isStart && !isEnd && !ranged && !isWeekend
                  ? "text-gray-700 hover:bg-brand-red/10 hover:text-brand-red"
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {d.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function DateRangePicker({
  start,
  end,
  onChange,
  className = "",
}: {
  start: Date | null;
  end: Date | null;
  onChange: (start: Date, end: Date) => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [viewDate, setViewDate] = useState(() => start ?? new Date());
  const [mode, setMode] = useState<"single" | "range">(() =>
    start && end && sameDay(start, end) ? "single" : "range",
  );
  const [picking, setPicking] = useState<"start" | "end">("start");
  const [draftStart, setDraftStart] = useState<Date | null>(start);
  const [draftEnd, setDraftEnd] = useState<Date | null>(end);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setDraftStart(start);
    setDraftEnd(end);
  }, [start, end]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const label =
    start && end
      ? sameDay(start, end)
        ? fmtShort(start)
        : `${fmtShort(start)} – ${fmtShort(end)}`
      : mode === "single"
        ? "Select date"
        : "Select date range";

  const handlePick = (d: Date) => {
    if (mode === "single") {
      setDraftStart(d);
      setDraftEnd(d);
      onChange(d, d);
      setOpen(false);
      setPicking("start");
      return;
    }

    if (picking === "start") {
      setDraftStart(d);
      setDraftEnd(null);
      setPicking("end");
      return;
    }
    const s = draftStart ?? d;
    let newStart = s;
    let newEnd = d;
    if (newEnd < newStart) {
      newStart = d;
      newEnd = s;
    }
    setDraftStart(newStart);
    setDraftEnd(newEnd);
    onChange(newStart, newEnd);
    setOpen(false);
    setPicking("start");
  };

  const switchMode = (next: "single" | "range") => {
    setMode(next);
    setPicking("start");
    if (next === "single") {
      const single = draftStart ?? draftEnd ?? start ?? end ?? new Date();
      setDraftStart(single);
      setDraftEnd(single);
      onChange(single, single);
      return;
    }
    const rangeStart = draftStart ?? start ?? new Date();
    const rangeEnd = draftEnd ?? end ?? rangeStart;
    setDraftStart(rangeStart);
    setDraftEnd(sameDay(rangeStart, rangeEnd) ? null : rangeEnd);
    if (sameDay(rangeStart, rangeEnd)) {
      setPicking("end");
    }
  };

  return (
    <div className={`relative inline-block ${className}`} ref={ref}>
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o);
          setPicking("start");
          setDraftStart(start);
          setDraftEnd(end);
          if (start && end) {
            setMode(sameDay(start, end) ? "single" : "range");
          }
        }}
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-xs font-medium transition-all ${
          open
            ? "border-brand-red/50 ring-2 ring-brand-red/20 bg-brand-red/10 text-brand-red"
            : "border-brand-red/30 bg-white text-brand-red hover:border-brand-red/40"
        }`}
      >
        <Calendar className="w-3.5 h-3.5 text-brand-red flex-shrink-0" />
        <span className="whitespace-nowrap">{label}</span>
        <ChevronDown
          className={`w-3 h-3 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div
          className="absolute top-full left-0 mt-1 z-50 bg-white rounded-xl shadow-xl border border-gray-200 p-3 select-none"
          style={{ width: 260 }}
        >
          <div className="flex rounded-lg border border-gray-200 p-0.5 mb-3">
            <button
              type="button"
              onClick={() => switchMode("single")}
              className={`flex-1 px-2 py-1 rounded-md text-[10px] font-semibold transition-colors ${
                mode === "single"
                  ? "bg-brand-red text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              Single day
            </button>
            <button
              type="button"
              onClick={() => switchMode("range")}
              className={`flex-1 px-2 py-1 rounded-md text-[10px] font-semibold transition-colors ${
                mode === "range"
                  ? "bg-brand-red text-white"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              Date range
            </button>
          </div>
          <DayCalendar
            viewDate={viewDate}
            onViewDateChange={setViewDate}
            start={draftStart}
            end={mode === "single" ? draftStart : draftEnd}
            picking={picking}
            mode={mode}
            onPick={handlePick}
          />
        </div>
      )}
    </div>
  );
}
