import { fmtUsd, fmtPct } from "@/lib/api";

/**
 * A single headline KPI tile.
 *
 * value  — the number to show (null/undefined => rendered as "—")
 * money  — format value as USD
 * suffix — unit appended to a plain numeric value (e.g. "%", "×", "/seat·hr")
 * prefix — unit prepended (e.g. "$" when not using the `money` currency format)
 * change — optional delta % (green up / red down arrow)
 * naHint — sublabel shown when the value is unavailable (null) on the active source
 * chart  — optional node (e.g. <Sparkline/>) rendered beside the value; hidden
 *          when the value is unavailable, since there's no trend to draw
 */
export default function KpiTile({
    label,
    value,
    change,
    sublabel,
    money = false,
    suffix = "",
    prefix = "",
    naHint = "Not tracked on this source",
    testId,
    icon = null,
    chart = null,
}) {
    const isNil = value === null || value === undefined || value === "";
    const up = change > 0;
    const down = change < 0;

    const display = isNil
        ? "—"
        : money
          ? fmtUsd(value)
          : `${prefix}${value}${suffix}`;

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
                <div
                    className={`font-display text-3xl font-semibold tracking-tight tabular-nums ${
                        isNil ? "text-slate-300" : "text-slate-900"
                    }`}
                >
                    {display}
                </div>
                {!isNil && typeof change === "number" && (
                    <div
                        className={`text-xs font-semibold ${up ? "text-emerald-600" : down ? "text-red-500" : "text-slate-400"}`}
                    >
                        {fmtPct(change)}
                    </div>
                )}
                {!isNil && chart && <div className="ml-auto shrink-0">{chart}</div>}
            </div>
            {(sublabel || isNil) && (
                <div className="text-xs text-slate-500">
                    {isNil ? naHint : sublabel}
                </div>
            )}
        </div>
    );
}
