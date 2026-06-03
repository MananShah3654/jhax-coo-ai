import { fmtUsd, fmtPct } from "@/lib/api";

export default function KpiTile({
    label,
    value,
    change,
    sublabel,
    money = false,
    testId,
    icon = null,
}) {
    const up = change > 0;
    const down = change < 0;
    return (
        <div
            data-testid={testId}
            className="group fade-up flex flex-col gap-3 rounded-2xl border border-slate-200/70 bg-white p-5 shadow-[0_2px_8px_rgba(15,23,42,0.04)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(15,23,42,0.07)]"
        >
            <div className="flex items-center justify-between">
                <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                    {label}
                </div>
                {icon}
            </div>
            <div className="flex items-baseline gap-2">
                <div className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                    {money ? fmtUsd(value) : value}
                </div>
                {typeof change === "number" && (
                    <div
                        className={`text-xs font-semibold ${up ? "text-emerald-600" : down ? "text-red-500" : "text-slate-400"}`}
                    >
                        {fmtPct(change)}
                    </div>
                )}
            </div>
            {sublabel && (
                <div className="text-xs text-slate-500">{sublabel}</div>
            )}
        </div>
    );
}
