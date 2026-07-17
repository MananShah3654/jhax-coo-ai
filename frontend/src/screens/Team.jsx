import { useEffect, useRef, useState } from "react";
import { api, API, authHeader } from "@/lib/api";
import Layout from "@/components/Layout";
import { Send, Sparkles, TrendingUp, AlertTriangle, CheckCircle2 } from "lucide-react";

const PERIODS = [
    { key: "today", label: "Today" },
    { key: "yesterday", label: "Yesterday" },
    { key: "this_week", label: "This Week" },
    { key: "last_week", label: "Last Week" },
    { key: "this_month", label: "This Month" },
    { key: "last_month", label: "Last Month" },
];

const QUICK = [
    "Why is my labor cost high?",
    "Who is my most expensive shift?",
    "Am I overstaffed this week?",
    "Match staffing to rush",
    "Show me the employee list",
];

const STATUS_STYLES = {
    ok: "border-emerald-100 bg-emerald-50/60",
    warn: "border-amber-100 bg-amber-50/60",
    muted: "border-slate-200 bg-slate-50/60",
};
const STATUS_ICON = {
    ok: <CheckCircle2 size={13} className="text-emerald-600" />,
    warn: <AlertTriangle size={13} className="text-amber-600" />,
    muted: <TrendingUp size={13} className="text-slate-400" />,
};

// Render inline **bold** segments with an accent for emphasized numbers/names.
function renderInline(text) {
    return text.split(/(\*\*[^*]+\*\*)/g).map((seg, j) =>
        seg.startsWith("**") && seg.endsWith("**") ? (
            <strong key={j} className="font-semibold text-slate-900">
                {seg.slice(2, -2)}
            </strong>
        ) : (
            <span key={j}>{seg}</span>
        ),
    );
}

// Render an answer string: supports **bold** and • bullet lines, with
// nicely styled bullets and comfortable spacing.
function Answer({ text }) {
    const lines = String(text)
        .split("\n")
        .filter((l) => l.trim() !== "");
    return (
        <div className="space-y-2 text-[13px] leading-relaxed text-slate-600">
            {lines.map((line, i) => {
                const isBullet = line.trimStart().startsWith("•");
                const clean = isBullet
                    ? line.replace(/^\s*•\s?/, "")
                    : line;
                return isBullet ? (
                    <div key={i} className="flex gap-2.5">
                        <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#FF6B35]" />
                        <span>{renderInline(clean)}</span>
                    </div>
                ) : (
                    <p key={i}>{renderInline(clean)}</p>
                );
            })}
        </div>
    );
}

function AnswerTable({ table }) {
    return (
        <div className="mt-3 overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-xs">
                <thead className="bg-slate-50 text-left font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                        {table.columns.map((c) => (
                            <th key={c} className="px-3 py-2 whitespace-nowrap">
                                {c}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {table.rows.map((row, i) => (
                        <tr key={i} className="border-t border-slate-100">
                            {row.map((cell, j) => (
                                <td
                                    key={j}
                                    className={`px-3 py-2 whitespace-nowrap ${
                                        cell === "overstaffed"
                                            ? "font-semibold text-amber-600"
                                            : cell === "understaffed"
                                              ? "font-semibold text-red-500"
                                              : "text-slate-700"
                                    }`}
                                >
                                    {String(cell)}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default function Team() {
    const [restaurants, setRestaurants] = useState(null);
    const [restaurantId, setRestaurantId] = useState(null);
    const [period, setPeriod] = useState("this_week");
    const [insights, setInsights] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState("");
    const [asking, setAsking] = useState(false);
    const scrollRef = useRef(null);

    useEffect(() => {
        api
            .get("/restaurants")
            .then((r) => {
                const list = r.data.restaurants || [];
                setRestaurants(list);
                if (list.length) setRestaurantId(list[0].id);
            })
            .catch(() => setRestaurants([]));
    }, []);

    // (Re)load KPI cards when branch or period changes.
    useEffect(() => {
        if (!restaurantId) return;
        setInsights(null);
        api
            .get(`/team/insights?restaurant_id=${restaurantId}&period=${period}`)
            .then((r) => setInsights(r.data))
            .catch(() => setInsights(false));
    }, [restaurantId, period]);

    useEffect(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
    }, [messages, asking]);

    // Update the most recent assistant message in place (streaming).
    const patchAssistant = (patch) =>
        setMessages((m) => {
            const copy = [...m];
            for (let i = copy.length - 1; i >= 0; i--) {
                if (copy[i].role === "assistant") {
                    copy[i] = { ...copy[i], ...patch };
                    break;
                }
            }
            return copy;
        });

    const ask = async (question) => {
        const q = (question ?? input).trim();
        if (!q || !restaurantId || asking) return;
        setInput("");
        setMessages((m) => [
            ...m,
            { role: "user", text: q },
            { role: "assistant", text: "", table: null, streaming: true },
        ]);
        setAsking(true);
        try {
            // Stream the reply (SSE), same pattern as the Ask Anything page.
            const auth = await authHeader();
            const res = await fetch(`${API}/team/ask`, {
                method: "POST",
                headers: { "Content-Type": "application/json", ...auth },
                body: JSON.stringify({
                    restaurant_id: restaurantId,
                    period,
                    question: q,
                }),
            });
            if (!res.body) throw new Error("No stream");
            const reader = res.body.getReader();
            const dec = new TextDecoder();
            let sseBuf = "";
            let textBuf = "";
            let table = null;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                sseBuf += dec.decode(value, { stream: true });
                let idx;
                while ((idx = sseBuf.indexOf("\n\n")) !== -1) {
                    const raw = sseBuf.slice(0, idx);
                    sseBuf = sseBuf.slice(idx + 2);
                    let event = "message";
                    let data = "";
                    for (const ln of raw.split("\n")) {
                        if (ln.startsWith("event:")) event = ln.slice(6).trim();
                        else if (ln.startsWith("data:")) data += ln.slice(5).trim();
                    }
                    if (event === "meta") {
                        try {
                            const meta = JSON.parse(data);
                            table = meta.table;
                            patchAssistant({
                                table,
                                metrics: meta.metrics || [],
                            });
                        } catch {}
                    } else if (event === "delta") {
                        try {
                            textBuf += JSON.parse(data).text || "";
                            patchAssistant({ text: textBuf });
                        } catch {}
                    }
                }
            }
            patchAssistant({ streaming: false });
        } catch {
            patchAssistant({
                text: "Sorry — I couldn't answer that just now.",
                streaming: false,
            });
        } finally {
            setAsking(false);
        }
    };

    if (!restaurants)
        return (
            <Layout>
                <div className="text-slate-400">Loading team…</div>
            </Layout>
        );

    const periodLabel =
        PERIODS.find((p) => p.key === period)?.label || "This Week";

    return (
        <Layout>
            <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                    <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                        Workforce Assistant
                    </div>
                    <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                        Team
                    </h1>
                </div>
                {restaurants.length > 1 && (
                    <div className="flex flex-col gap-1">
                        <label className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
                            Branch
                        </label>
                        <select
                            value={restaurantId || ""}
                            onChange={(e) => setRestaurantId(e.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-[#FF6B35]"
                        >
                            {restaurants.map((r) => (
                                <option key={r.id} value={r.id}>
                                    {r.name}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
            </div>

            {/* Period selector */}
            <div className="mt-4 flex flex-wrap gap-2">
                {PERIODS.map((p) => (
                    <button
                        key={p.key}
                        onClick={() => setPeriod(p.key)}
                        data-testid={`period-${p.key}`}
                        className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
                            period === p.key
                                ? "bg-slate-900 text-white"
                                : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                        }`}
                    >
                        {p.label}
                    </button>
                ))}
            </div>

            {/* KPI cards */}
            {restaurants.length === 0 ? (
                <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50/60 p-8 text-center text-sm text-slate-500">
                    No branches yet. Add a restaurant or run the Square sync.
                </div>
            ) : (
                <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    {(insights?.kpis || Array(5).fill(null)).map((k, i) => (
                        <div
                            key={k?.key || i}
                            className={`rounded-2xl border p-4 ${
                                k ? STATUS_STYLES[k.status] : "border-slate-200 bg-white"
                            }`}
                        >
                            <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                                {k && STATUS_ICON[k.status]}
                                {k ? k.label : "…"}
                            </div>
                            <div className="mt-1.5 font-display text-2xl font-semibold text-slate-900">
                                {k ? k.value : "—"}
                            </div>
                            <div className="mt-0.5 text-xs text-slate-500">
                                {k ? k.detail : ""}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Chat */}
            <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_4px_24px_rgba(15,23,42,0.06)]">
                <div
                    ref={scrollRef}
                    className="max-h-[52vh] min-h-[200px] space-y-4 overflow-y-auto p-5"
                >
                    {messages.length === 0 && (
                        <div className="flex items-start gap-3">
                            <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#FF8A5B] to-[#E85D2A] shadow-sm">
                                <Sparkles size={15} className="text-white" />
                            </div>
                            <div className="rounded-2xl rounded-tl-sm border border-slate-200/80 bg-white px-4 py-3 text-sm text-slate-600 shadow-[0_2px_12px_rgba(15,23,42,0.05)]">
                                Ask me anything about your team for{" "}
                                <span className="font-semibold text-slate-800">
                                    {periodLabel}
                                </span>
                                . Try a question below 👇
                            </div>
                        </div>
                    )}

                    {messages.map((m, i) =>
                        m.role === "user" ? (
                            <div key={i} className="flex justify-end">
                                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-[#FF6B35] px-4 py-2.5 text-sm font-medium text-white">
                                    {m.text}
                                </div>
                            </div>
                        ) : (
                            <div key={i} className="fade-up">
                                <div className="relative overflow-hidden rounded-[24px] rounded-tl-lg border border-orange-100 bg-gradient-to-b from-orange-50/60 via-white to-white p-5 shadow-[0_6px_24px_rgba(255,107,53,0.07)] ring-1 ring-orange-100/60">
                                    {/* warm accent bar */}
                                    <span className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#FF6B35] via-[#F7931E] to-[#FF6B35]" />

                                    {/* persona badge */}
                                    <div className="mb-3 flex items-center gap-2">
                                        <div className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-[#FF6B35] to-[#E85D2A] text-white shadow-[0_4px_12px_rgba(255,107,53,0.35)]">
                                            <Sparkles size={13} />
                                        </div>
                                        <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#E85D2A]">
                                            Workforce Analyst
                                        </span>
                                        <span className="flex items-center gap-1.5 rounded-full bg-orange-50 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.16em] text-[#E85D2A] ring-1 ring-orange-100">
                                            <span
                                                className={`h-1.5 w-1.5 rounded-full bg-[#FF6B35] ${m.streaming ? "animate-pulse" : ""}`}
                                            />
                                            {m.streaming ? "Analyzing" : "Answer"}
                                        </span>
                                    </div>

                                    {/* body */}
                                    {m.text ? (
                                        <Answer text={m.text} />
                                    ) : (
                                        <span className="text-sm text-slate-400">
                                            Analyzing the numbers…
                                        </span>
                                    )}

                                    {/* metric tiles */}
                                    {m.metrics?.length > 0 && (
                                        <div className="mt-4 flex flex-wrap gap-2.5">
                                            {m.metrics.map((mt, k) => (
                                                <div
                                                    key={k}
                                                    className="rounded-xl border border-l-[3px] border-slate-200/80 border-l-[#FF6B35] bg-white px-3.5 py-2 shadow-[0_1px_3px_rgba(15,23,42,0.05)]"
                                                >
                                                    <div className="text-[9px] font-bold uppercase tracking-[0.16em] text-slate-400">
                                                        {mt.label}
                                                    </div>
                                                    <div className="mt-0.5 font-display text-lg font-semibold tabular-nums text-slate-900">
                                                        {mt.value}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {m.table && <AnswerTable table={m.table} />}
                                </div>
                            </div>
                        ),
                    )}

                </div>

                {/* Quick questions */}
                <div className="flex flex-wrap gap-2 border-t border-slate-100 px-5 py-3">
                    {QUICK.map((q) => (
                        <button
                            key={q}
                            onClick={() => ask(q)}
                            disabled={asking}
                            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-[#FF6B35] hover:text-[#E85D2A] disabled:opacity-50"
                        >
                            {q}
                        </button>
                    ))}
                </div>

                {/* Input */}
                <div className="flex items-center gap-2 border-t border-slate-100 p-3">
                    <input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && ask()}
                        placeholder="Ask about labor cost, overtime, staffing…"
                        className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-[#FF6B35]"
                    />
                    <button
                        onClick={() => ask()}
                        disabled={asking || !input.trim()}
                        className="grid h-10 w-10 place-items-center rounded-xl bg-[#FF6B35] text-white hover:brightness-105 disabled:opacity-50"
                    >
                        <Send size={16} />
                    </button>
                </div>
            </div>
        </Layout>
    );
}
