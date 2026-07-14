import { useEffect, useState } from "react";
import { api, fmtUsd, fmtPct } from "@/lib/api";
import Layout from "@/components/Layout";
import { Crown, AlertTriangle, Users, Clock } from "lucide-react";
import { TID } from "@/constants/testIds";

function fmtDateTime(iso) {
    if (!iso) return "—";
    try {
        return new Date(iso).toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
    } catch {
        return iso;
    }
}

// Roster for the selected restaurant. Auto-selects when the owner has just one
// restaurant; otherwise shows a picker and loads the clicked restaurant's team.
function TeamSection({ restaurants }) {
    const [selectedId, setSelectedId] = useState(
        restaurants.length === 1 ? restaurants[0].id : null,
    );
    const [employees, setEmployees] = useState(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!selectedId) {
            setEmployees(null);
            return;
        }
        setLoading(true);
        api
            .get(`/employees?restaurant_id=${selectedId}`)
            .then((r) => setEmployees(r.data.employees || []))
            .catch(() => setEmployees([]))
            .finally(() => setLoading(false));
    }, [selectedId]);

    const selected = restaurants.find((r) => r.id === selectedId);

    return (
        <div className="mt-10">
            <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                <Users size={12} /> Team
            </div>
            <h2 className="font-display text-2xl font-semibold tracking-tight text-slate-900">
                Employees
            </h2>

            {/* Restaurant picker — only when there's more than one */}
            {restaurants.length > 1 && (
                <div className="mt-4 flex flex-wrap gap-2">
                    {restaurants.map((r) => (
                        <button
                            key={r.id}
                            onClick={() => setSelectedId(r.id)}
                            data-testid={`branch-pick-${r.id}`}
                            className={`rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                                r.id === selectedId
                                    ? "border-[#FF6B35] bg-orange-50 text-[#E85D2A]"
                                    : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                            }`}
                        >
                            {r.name}
                        </button>
                    ))}
                </div>
            )}

            {!selectedId && (
                <div className="mt-4 text-sm text-slate-500">
                    Select a restaurant above to view its team.
                </div>
            )}

            {selectedId && (
                <div className="mt-4">
                    {restaurants.length > 1 && (
                        <div className="mb-3 text-sm text-slate-500">
                            Showing team for{" "}
                            <span className="font-semibold text-slate-800">
                                {selected?.name}
                            </span>
                        </div>
                    )}

                    {loading && (
                        <div className="text-sm text-slate-400">Loading team…</div>
                    )}

                    {!loading && employees && employees.length === 0 && (
                        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-8 text-center text-sm text-slate-500">
                            No employees synced for this restaurant yet. Run the
                            Square sync to populate the roster.
                        </div>
                    )}

                    {!loading && employees && employees.length > 0 && (
                        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 text-left text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                                    <tr>
                                        <th className="px-5 py-3">Employee</th>
                                        <th className="px-5 py-3">Contact</th>
                                        <th className="px-5 py-3">Status</th>
                                        <th className="px-5 py-3">Last Clock-In</th>
                                        <th className="px-5 py-3">Last Clock-Out</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {employees.map((e) => (
                                        <tr
                                            key={e.id}
                                            data-testid={`employee-row-${e.id}`}
                                            className="border-t border-slate-100 hover:bg-slate-50/50"
                                        >
                                            <td className="px-5 py-4">
                                                <div className="font-display text-base font-semibold text-slate-900">
                                                    {e.name || "—"}
                                                </div>
                                                {e.is_owner && (
                                                    <div className="text-xs font-medium text-amber-600">
                                                        Owner
                                                    </div>
                                                )}
                                            </td>
                                            <td className="px-5 py-4 text-slate-600">
                                                <div>{e.email || "—"}</div>
                                                <div className="text-xs text-slate-400">
                                                    {e.phone || ""}
                                                </div>
                                            </td>
                                            <td className="px-5 py-4">
                                                <span
                                                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                                                        e.status === "ACTIVE"
                                                            ? "bg-emerald-50 text-emerald-700"
                                                            : "bg-slate-100 text-slate-500"
                                                    }`}
                                                >
                                                    {e.status || "—"}
                                                </span>
                                            </td>
                                            <td className="px-5 py-4 text-slate-700">
                                                <span className="inline-flex items-center gap-1">
                                                    <Clock
                                                        size={12}
                                                        className="text-slate-400"
                                                    />
                                                    {fmtDateTime(
                                                        e.last_shift?.clock_in,
                                                    )}
                                                </span>
                                            </td>
                                            <td className="px-5 py-4 text-slate-700">
                                                {e.last_shift ? (
                                                    e.last_shift.clock_out ? (
                                                        fmtDateTime(
                                                            e.last_shift.clock_out,
                                                        )
                                                    ) : (
                                                        <span className="font-medium text-emerald-600">
                                                            On shift
                                                        </span>
                                                    )
                                                ) : (
                                                    "—"
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

export default function Branches() {
    const [data, setData] = useState(null);
    const [restaurants, setRestaurants] = useState(null);

    useEffect(() => {
        api
            .get("/branches?days=7")
            .then((r) => setData(r.data))
            .catch(() => setData({ branches: [] }));
        api
            .get("/restaurants")
            .then((r) => setRestaurants(r.data.restaurants || []))
            .catch(() => setRestaurants([]));
    }, []);

    if (!data || !restaurants)
        return (
            <Layout>
                <div className="text-slate-400">Loading branches…</div>
            </Layout>
        );

    const hasBranches = data.branches && data.branches.length > 0;
    const best = hasBranches ? data.branches[0] : null;
    const worst = hasBranches ? data.branches[data.branches.length - 1] : null;

    return (
        <Layout>
            <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Multi-Location{hasBranches ? " · last 7 days" : ""}
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                Branch Performance
            </h1>

            {!hasBranches && (
                <div className="mt-8 rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-10 text-center">
                    <div className="font-display text-lg font-semibold text-slate-900">
                        No performance data yet
                    </div>
                    <div className="mt-1 text-sm text-slate-500">
                        Once orders come in, best/worst branch performance shows
                        here. Your team roster is below.
                    </div>
                </div>
            )}

            {hasBranches && (
                <>
                    <div className="mt-6 grid gap-4 md:grid-cols-2">
                        <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-5">
                            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-emerald-700">
                                <Crown size={12} /> Best Branch
                            </div>
                            <div className="mt-1 font-display text-2xl font-semibold text-slate-900">
                                {best.name}
                            </div>
                            <div className="text-sm text-slate-600">
                                {fmtUsd(best.revenue)} · {best.orders} orders ·{" "}
                                <span className="font-semibold text-emerald-600">
                                    {fmtPct(best.growth_pct)}
                                </span>
                            </div>
                        </div>
                        <div className="rounded-2xl border border-red-100 bg-red-50/60 p-5">
                            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-red-700">
                                <AlertTriangle size={12} /> Needs Attention
                            </div>
                            <div className="mt-1 font-display text-2xl font-semibold text-slate-900">
                                {worst.name}
                            </div>
                            <div className="text-sm text-slate-600">
                                {fmtUsd(worst.revenue)} · {worst.orders} orders ·{" "}
                                <span className="font-semibold text-red-500">
                                    {fmtPct(worst.growth_pct)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 text-left text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                                <tr>
                                    <th className="px-5 py-3">Branch</th>
                                    <th className="px-5 py-3">Manager</th>
                                    <th className="px-5 py-3 text-right">Revenue</th>
                                    <th className="px-5 py-3 text-right">Orders</th>
                                    <th className="px-5 py-3 text-right">AOV</th>
                                    <th className="px-5 py-3 text-right">Growth</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.branches.map((b) => (
                                    <tr
                                        key={b.id}
                                        data-testid={TID.branchRow(b.id)}
                                        className="border-t border-slate-100 hover:bg-slate-50/50"
                                    >
                                        <td className="px-5 py-4">
                                            <div className="font-display text-base font-semibold text-slate-900">
                                                {b.name}
                                            </div>
                                            <div className="text-xs text-slate-500">
                                                {b.city}
                                            </div>
                                        </td>
                                        <td className="px-5 py-4 text-slate-700">
                                            {b.manager}
                                        </td>
                                        <td className="px-5 py-4 text-right font-mono font-semibold text-slate-900">
                                            {fmtUsd(b.revenue)}
                                        </td>
                                        <td className="px-5 py-4 text-right text-slate-700">
                                            {b.orders}
                                        </td>
                                        <td className="px-5 py-4 text-right text-slate-700">
                                            {fmtUsd(b.avg_order_value)}
                                        </td>
                                        <td
                                            className={`px-5 py-4 text-right font-semibold ${b.growth_pct >= 0 ? "text-emerald-600" : "text-red-500"}`}
                                        >
                                            {fmtPct(b.growth_pct)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </>
            )}

            {/* Team / Employees — the login → restaurant → roster flow */}
            {restaurants.length === 0 ? (
                <div className="mt-10 rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-8 text-center">
                    <div className="font-display text-lg font-semibold text-slate-900">
                        No restaurants yet
                    </div>
                    <div className="mt-1 text-sm text-slate-500">
                        Add a restaurant or run the Square sync to see your team
                        here.
                    </div>
                </div>
            ) : (
                <TeamSection restaurants={restaurants} />
            )}
        </Layout>
    );
}
