import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, fmtUsd } from "@/lib/api";
import Layout from "@/components/Layout";
import { ArrowLeft, Clock } from "lucide-react";

function fmtDateTime(iso) {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleString("en-US", {
            weekday: "short",
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return iso;
    }
}

function fmtBreak(h) {
    if (!h) return "—";
    return `${Math.round(h * 60)}m`;
}

function Fact({ label, value }) {
    return (
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
            <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
                {label}
            </div>
            <div className="mt-0.5 text-sm font-semibold text-slate-900">
                {value}
            </div>
        </div>
    );
}

export default function TeamEmployee() {
    const { employeeId } = useParams();
    const [emp, setEmp] = useState(null);
    const [shifts, setShifts] = useState(null);

    useEffect(() => {
        api
            .get(`/employees/${employeeId}`)
            .then((r) => setEmp(r.data))
            .catch(() => setEmp(false));
        api
            .get(`/employees/${employeeId}/shifts?days=30`)
            .then((r) => setShifts(r.data.shifts || []))
            .catch(() => setShifts([]));
    }, [employeeId]);

    if (emp === false)
        return (
            <Layout>
                <Link
                    to="/team"
                    className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"
                >
                    <ArrowLeft size={14} /> Back to Team
                </Link>
                <div className="mt-6 text-slate-500">Employee not found.</div>
            </Layout>
        );

    if (!emp)
        return (
            <Layout>
                <div className="text-slate-400">Loading employee…</div>
            </Layout>
        );

    return (
        <Layout>
            <Link
                to="/team"
                className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"
            >
                <ArrowLeft size={14} /> Back to Team
            </Link>

            <div className="mt-4 flex items-baseline gap-3">
                <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                    {emp.name || "—"}
                </h1>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold capitalize text-slate-600">
                    {emp.title || "staff"}
                </span>
            </div>
            <div className="mt-1 text-sm text-slate-500">
                {emp.email || ""} {emp.phone ? `· ${emp.phone}` : ""}
            </div>

            {/* Payroll facts */}
            <div className="mt-6 grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
                <Fact
                    label="Hourly Rate"
                    value={
                        emp.hourly_rate != null
                            ? `${fmtUsd(emp.hourly_rate)}/h`
                            : "—"
                    }
                />
                <Fact
                    label="Tax Declared"
                    value={emp.tax_declared ? "Yes" : "No"}
                />
                <Fact
                    label="Advance Taken"
                    value={
                        emp.advance_taken && emp.advance_amount != null
                            ? fmtUsd(emp.advance_amount)
                            : "No"
                    }
                />
                <Fact
                    label="Advance Date"
                    value={
                        emp.advance_date
                            ? new Date(emp.advance_date).toLocaleDateString()
                            : "—"
                    }
                />
                <Fact label="Status" value={emp.status || "—"} />
            </div>

            {/* Shift history */}
            <h2 className="mt-10 font-display text-xl font-semibold tracking-tight text-slate-900">
                Shift history · last 30 days
            </h2>

            {!shifts ? (
                <div className="mt-4 text-sm text-slate-400">Loading shifts…</div>
            ) : shifts.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-8 text-center text-sm text-slate-500">
                    No shifts recorded in the last 30 days.
                </div>
            ) : (
                <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
                    <table className="w-full min-w-[720px] text-sm">
                        <thead className="bg-slate-50 text-left text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                            <tr>
                                <th className="px-5 py-3">Clock-In</th>
                                <th className="px-5 py-3">Clock-Out</th>
                                <th className="px-5 py-3 text-right">Break</th>
                                <th className="px-5 py-3 text-center">Meal</th>
                                <th className="px-5 py-3 text-right">Worked</th>
                                <th className="px-5 py-3">Flags</th>
                            </tr>
                        </thead>
                        <tbody>
                            {shifts.map((s) => (
                                <tr
                                    key={s.id}
                                    className="border-t border-slate-100 hover:bg-slate-50/50"
                                >
                                    <td className="px-5 py-4 text-slate-700">
                                        <span className="inline-flex items-center gap-1">
                                            <Clock
                                                size={12}
                                                className="text-slate-400"
                                            />
                                            {fmtDateTime(s.clock_in)}
                                        </span>
                                    </td>
                                    <td className="px-5 py-4 text-slate-700">
                                        {s.status === "MISSED" ? (
                                            <span className="font-medium text-red-500">
                                                No-show
                                            </span>
                                        ) : s.clock_out ? (
                                            fmtDateTime(s.clock_out)
                                        ) : (
                                            <span className="font-medium text-emerald-600">
                                                On shift
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-5 py-4 text-right text-slate-700">
                                        {fmtBreak(s.break_hours)}
                                    </td>
                                    <td className="px-5 py-4 text-center">
                                        {s.meal_taken ? (
                                            <span className="text-emerald-600">
                                                ✓
                                            </span>
                                        ) : (
                                            <span className="text-slate-300">
                                                —
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-5 py-4 text-right font-mono text-slate-900">
                                        {s.hours_worked != null
                                            ? `${s.hours_worked}h`
                                            : "—"}
                                    </td>
                                    <td className="px-5 py-4">
                                        <div className="flex flex-wrap gap-1">
                                            {s.late_clockin && (
                                                <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-500">
                                                    Late
                                                </span>
                                            )}
                                            {s.hours_worked != null &&
                                                s.hours_worked > 8 && (
                                                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-600">
                                                        OT
                                                    </span>
                                                )}
                                            {s.missed_clockin && (
                                                <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-500">
                                                    Missed
                                                </span>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </Layout>
    );
}
