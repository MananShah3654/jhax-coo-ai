/**
 * Promotions / Combo Builder.
 *
 * Lands here from AI action buttons with kind="promotion" and a prefill
 * like {items:["BLT Sandwich","Beverage Bar"], discount:15, name:"Lunch Combo"}.
 *
 * Owner can:
 *  - Edit name / items / discount
 *  - See live profit estimate
 *  - "Launch Promotion" -> POST /api/actions/execute (mocked)
 */
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Plus, Trash2, Sparkles, Loader2 } from "lucide-react";
import Layout from "@/components/Layout";
import { api, fmtUsd } from "@/lib/api";
import { toast } from "sonner";

const PREFILL_KEY = "promotion_prefill";

const PRESETS = [
    {
        id: "lunch_combo",
        name: "Lunch Combo",
        items: ["BLT Sandwich", "Beverage Bar"],
        discount: 15,
        audience: "Lunch crowd",
    },
    {
        id: "breakfast_bundle",
        name: "Breakfast Bundle",
        items: ["Belgian Waffle", "Bacon & Eggs", "Iced Latte"],
        discount: 20,
        audience: "Morning regulars",
    },
    {
        id: "weekend_feast",
        name: "Weekend Feast",
        items: ["BBQ Ribs Platter", "Truffle Fries", "Chocolate Lava Cake"],
        discount: 18,
        audience: "Weekend diners",
    },
];

export default function Promotions() {
    const location = useLocation();
    const [menu, setMenu] = useState([]);
    const [name, setName] = useState("Lunch Combo");
    const [items, setItems] = useState(["BLT Sandwich", "Beverage Bar"]);
    const [discount, setDiscount] = useState(15);
    const [audience, setAudience] = useState("Lunch crowd");
    const [busy, setBusy] = useState(false);

    // Load menu items for picker
    useEffect(() => {
        api.get("/menu").then((r) => setMenu(r.data.all || []));
    }, []);

    // Pick up prefill from navigation OR sessionStorage
    useEffect(() => {
        let pre = location.state?.prefill;
        if (!pre) {
            try {
                pre = JSON.parse(sessionStorage.getItem(PREFILL_KEY) || "null");
            } catch {
                pre = null;
            }
        }
        if (pre && typeof pre === "object") {
            if (pre.name) setName(pre.name);
            if (Array.isArray(pre.items) && pre.items.length) setItems(pre.items);
            if (typeof pre.discount === "number") setDiscount(pre.discount);
            if (pre.audience) setAudience(pre.audience);
            try { sessionStorage.removeItem(PREFILL_KEY); } catch {}
            toast.info("Promotion prefilled from your AI COO");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Compute live economics from menu
    const itemsResolved = items
        .map((n) => menu.find((m) => m.name === n))
        .filter(Boolean);
    const fullPrice = itemsResolved.reduce((s, m) => s + m.price, 0);
    const combo = fullPrice * (1 - discount / 100);
    const cost = itemsResolved.reduce((s, m) => s + m.cost, 0);
    const profit = combo - cost;
    const margin = combo ? (profit / combo) * 100 : 0;

    const addItem = (n) => {
        if (!items.includes(n)) setItems((arr) => [...arr, n]);
    };
    const removeItem = (n) => setItems((arr) => arr.filter((x) => x !== n));

    const applyPreset = (p) => {
        setName(p.name);
        setItems(p.items);
        setDiscount(p.discount);
        setAudience(p.audience);
    };

    const launch = async () => {
        setBusy(true);
        try {
            await api.post("/actions/execute", {
                id: "promotion_launch",
                kind: "promotion",
                label: name,
                payload: { items, discount, audience, combo_price: combo },
            });
            toast.success(`"${name}" scheduled — managers notified`);
        } catch {
            toast.error("Launch failed");
        } finally {
            setBusy(false);
        }
    };

    return (
        <Layout>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Promotions · Combo Builder
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                Design a combo in 30 seconds
            </h1>

            <div className="mt-2 flex flex-wrap gap-2">
                {PRESETS.map((p) => (
                    <button
                        key={p.id}
                        data-testid={`promo-preset-${p.id}`}
                        onClick={() => applyPreset(p)}
                        className="rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:border-[#FF6B35] hover:text-[#E85D2A]"
                    >
                        ✨ {p.name}
                    </button>
                ))}
            </div>

            <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1fr_360px]">
                {/* Builder */}
                <div className="rounded-3xl border border-slate-200 bg-white p-6">
                    <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                        Combo Name
                    </label>
                    <input
                        data-testid="promo-name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-lg font-display font-semibold text-slate-900 focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                    />

                    <div className="mt-5">
                        <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                            Items in this combo
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                            {items.length === 0 && (
                                <div className="text-sm text-slate-400">
                                    Pick items below.
                                </div>
                            )}
                            {items.map((n) => (
                                <span
                                    key={n}
                                    data-testid={`promo-item-chip-${n.replace(/[^a-z]+/gi, "-").toLowerCase()}`}
                                    className="inline-flex items-center gap-2 rounded-full bg-orange-50 px-3 py-1.5 text-sm font-medium text-[#E85D2A]"
                                >
                                    {n}
                                    <button
                                        onClick={() => removeItem(n)}
                                        className="grid h-5 w-5 place-items-center rounded-full bg-orange-100 text-[#E85D2A] hover:bg-orange-200"
                                    >
                                        <Trash2 size={11} />
                                    </button>
                                </span>
                            ))}
                        </div>
                    </div>

                    <div className="mt-5">
                        <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                            Add menu item
                        </div>
                        <div className="mt-2 max-h-56 overflow-y-auto rounded-xl border border-slate-100">
                            {menu.map((m) => (
                                <button
                                    key={m.id}
                                    data-testid={`promo-add-${m.id}`}
                                    onClick={() => addItem(m.name)}
                                    disabled={items.includes(m.name)}
                                    className="flex w-full items-center justify-between border-b border-slate-100 px-4 py-2.5 text-left text-sm last:border-0 hover:bg-slate-50 disabled:opacity-40"
                                >
                                    <div>
                                        <div className="font-medium text-slate-900">
                                            {m.name}
                                        </div>
                                        <div className="text-xs text-slate-500">
                                            {m.category} · {fmtUsd(m.price)}
                                        </div>
                                    </div>
                                    <Plus size={14} className="text-[#FF6B35]" />
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="mt-5 grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                Discount %
                            </label>
                            <input
                                data-testid="promo-discount"
                                type="number"
                                min={0}
                                max={50}
                                value={discount}
                                onChange={(e) => setDiscount(Number(e.target.value) || 0)}
                                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-base focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                            />
                        </div>
                        <div>
                            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                Target Audience
                            </label>
                            <input
                                data-testid="promo-audience"
                                value={audience}
                                onChange={(e) => setAudience(e.target.value)}
                                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-base focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                            />
                        </div>
                    </div>
                </div>

                {/* Economics */}
                <div className="sticky top-6 rounded-3xl border border-slate-200 bg-gradient-to-br from-white to-orange-50/40 p-6">
                    <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                        Live Economics
                    </div>
                    <div className="mt-2 font-display text-xl font-semibold text-slate-900">
                        {name || "Untitled Combo"}
                    </div>

                    <dl className="mt-4 space-y-2 text-sm">
                        <div className="flex justify-between">
                            <dt className="text-slate-500">Full price</dt>
                            <dd className="font-mono text-slate-900">
                                {fmtUsd(fullPrice)}
                            </dd>
                        </div>
                        <div className="flex justify-between">
                            <dt className="text-slate-500">Discount</dt>
                            <dd className="font-mono text-[#FF6B35]">
                                −{discount}%
                            </dd>
                        </div>
                        <div className="flex justify-between border-t border-slate-200 pt-2">
                            <dt className="font-medium text-slate-900">
                                Combo price
                            </dt>
                            <dd
                                data-testid="promo-combo-price"
                                className="font-mono font-semibold text-slate-900"
                            >
                                {fmtUsd(combo)}
                            </dd>
                        </div>
                        <div className="flex justify-between">
                            <dt className="text-slate-500">Food cost</dt>
                            <dd className="font-mono text-slate-700">
                                {fmtUsd(cost)}
                            </dd>
                        </div>
                        <div className="flex justify-between">
                            <dt className="text-slate-500">Profit / sale</dt>
                            <dd className="font-mono font-semibold text-emerald-600">
                                {fmtUsd(profit)}
                            </dd>
                        </div>
                        <div className="flex justify-between">
                            <dt className="text-slate-500">Margin</dt>
                            <dd className="font-mono font-semibold text-emerald-600">
                                {margin.toFixed(0)}%
                            </dd>
                        </div>
                    </dl>

                    <button
                        data-testid="promo-launch"
                        onClick={launch}
                        disabled={busy || items.length === 0}
                        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-full bg-[#FF6B35] px-5 py-3 text-sm font-medium text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:-translate-y-0.5 hover:bg-[#E85D2A] disabled:opacity-50"
                    >
                        {busy ? (
                            <Loader2 size={14} className="animate-spin" />
                        ) : (
                            <Sparkles size={14} />
                        )}
                        Launch Promotion
                    </button>
                </div>
            </div>
        </Layout>
    );
}
