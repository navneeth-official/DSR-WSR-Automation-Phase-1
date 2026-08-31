export function variantBadgeLabel(variant: number): string {
  return `V${variant}`;
}

interface VariantRibbonProps {
  label: string;
  /** Tailwind color classes for the ribbon fill, e.g. bg-[#d3072a] */
  colorClassName?: string;
}

export function VariantRibbon({
  label,
  colorClassName = "bg-brand-red",
}: VariantRibbonProps) {
  return (
    <div
      className="pointer-events-none absolute top-0 right-0 z-10 h-16 w-16 overflow-hidden"
      aria-hidden
    >
      <span
        className={`absolute top-[14px] -right-[28px] block w-[104px] rotate-45 py-1 text-center text-[10px] font-bold tracking-wide text-white shadow-md ${colorClassName}`}
      >
        {label}
      </span>
    </div>
  );
}
