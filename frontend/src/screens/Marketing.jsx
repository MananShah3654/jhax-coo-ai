import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "@/lib/api";
import Layout from "@/components/Layout";
import { Sparkles, Loader2, Send, Image as ImageIcon, RefreshCw, Download, UtensilsCrossed, Tag, TrendingUp, Copy, CheckCircle2, Instagram, MessageCircle } from "lucide-react";
import { TID } from "@/constants/testIds";
import { toast } from "sonner";

/**
 * Strip the markdown the LLM sometimes emits. WhatsApp and Instagram render
 * none of it — "**Free dessert**" would paste literally, asterisks and all.
 */
function stripMarkdown(text = "") {
    return String(text)
        .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")  // [label](url) / ![alt](src) -> label
        .replace(/(\*\*\*|___)(.*?)\1/g, "$2")      // ***bold italic***
        .replace(/(\*\*|__)(.*?)\1/g, "$2")         // **bold**
        .replace(/(\*|_)(.*?)\1/g, "$2")            // *italic*
        .replace(/`{1,3}([^`]*)`{1,3}/g, "$1")      // `code`
        .replace(/^\s{0,3}#{1,6}\s+/gm, "")         // # headings
        .replace(/^\s{0,3}>\s?/gm, "")              // > quotes
        .replace(/\n{3,}/g, "\n\n")
        .trim();
}

/** Full campaign message for WhatsApp: subject, body, then the CTA. */
function whatsappText(draft) {
    if (!draft) return "";
    return stripMarkdown(
        [draft.subject, draft.body, draft.cta && `👉 ${draft.cta}`]
            .filter(Boolean)
            .join("\n\n"),
    );
}

/**
 * Instagram caption — deliberately NOT the WhatsApp copy. Subject + CTA only:
 * a caption sits under an image that already carries the message, so the full
 * body would bury the call to action.
 */
function instagramCaption(draft) {
    if (!draft) return "";
    return stripMarkdown(
        [draft.subject, draft.cta && `👉 ${draft.cta}`].filter(Boolean).join("\n\n"),
    );
}

const AUDIENCES = [
    { id: "vip", label: "VIP customers" },
    { id: "at_risk", label: "At-risk (inactive 30+ days)" },
    { id: "new", label: "New customers (first visit)" },
    { id: "all", label: "All customers" },
];
const CHANNELS = [
    { id: "sms", label: "SMS" },
    { id: "email", label: "Email" },
    { id: "push", label: "Push" },
    { id: "loyalty", label: "Loyalty" },
];
const GOALS = [
    "Reactivate inactive customers",
    "Drive lunch traffic",
    "Promote weekend brunch",
    "Increase repeat visits",
    "Push the new BBQ Ribs platter",
];

export default function Marketing() {
    const location = useLocation();
    const [audience, setAudience] = useState("at_risk");
    const [channel, setChannel] = useState("sms");
    const [goal, setGoal] = useState(GOALS[0]);
    const [draft, setDraft] = useState(null);
    const [busy, setBusy] = useState(false);

    // Promotional banner (AI text-to-image)
    const [bannerDesc, setBannerDesc] = useState("");
    const [banner, setBanner] = useState(null); // {url, prompt, seed}
    const [bannerBusy, setBannerBusy] = useState(false);
    const [imgLoading, setImgLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);

    // AI Combo builder (data-grounded offer from best-sellers + sales trends)
    const [combo, setCombo] = useState(null);
    const [comboBusy, setComboBusy] = useState(false)
    ;

    // Pick up prefill from /home → Launch Campaign or from an AI action button
    useEffect(() => {
        let pre = location.state?.prefill;
        if (!pre) {
            try {
                pre = JSON.parse(sessionStorage.getItem("campaign_prefill") || "null");
            } catch {
                pre = null;
            }
        }
        if (pre && typeof pre === "object") {
            if (pre.audience && AUDIENCES.find((a) => a.id === pre.audience))
                setAudience(pre.audience);
            if (pre.channel && CHANNELS.find((c) => c.id === pre.channel))
                setChannel(pre.channel);
            if (pre.goal) setGoal(pre.goal);
            try { sessionStorage.removeItem("campaign_prefill"); } catch {}
            toast.info("Campaign prefilled from your AI COO");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const generate = async () => {
        setBusy(true);
        setDraft(null);
        try {
            const { data } = await api.post("/campaigns/generate", {
                audience: AUDIENCES.find((a) => a.id === audience).label,
                channel,
                goal,
            });
            setDraft(data.draft);
        } catch {
            toast.error("Campaign generation failed");
        } finally {
            setBusy(false);
        }
    };

    const launch = async () => {
        try {
            await api.post("/actions/execute", {
                id: "campaign_launch",
                kind: "campaign",
                label: draft?.subject || "Campaign",
                payload: { audience, channel, draft },
            });
            toast.success("Campaign scheduled for delivery");
        } catch {
            toast.error("Launch failed");
        }
    };

    // Clipboard needs a secure context (https / localhost); fall back to the
    // legacy path rather than silently doing nothing on plain http.
    const copyText = async (text, label) => {
        if (!text) return;
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(text);
            } else {
                const ta = document.createElement("textarea");
                ta.value = text;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.select();
                const ok = document.execCommand("copy");
                document.body.removeChild(ta);
                if (!ok) throw new Error("execCommand copy rejected");
            }
            toast.success(`${label} copied`);
        } catch {
            toast.error(`Couldn't copy ${label.toLowerCase()} — copy it manually`);
        }
    };

    // Fetch to a blob first: the banner is cross-origin, and <a download> is
    // ignored for cross-origin URLs (the browser just opens a tab instead).
    const downloadBanner = async () => {
        if (!banner?.url) return;
        setDownloading(true);
        try {
            const res = await fetch(banner.url, { mode: "cors" });
            if (!res.ok) throw new Error(`image host returned ${res.status}`);
            const blob = await res.blob();
            const href = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = href;
            a.download = `jhapay-banner-${banner.seed || Date.now()}.jpg`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(href);
            toast.success("Banner downloaded");
        } catch {
            toast.error("Download failed — use “Open full size” and save it manually");
        } finally {
            setDownloading(false);
        }
    };

    const generateBanner = async (regenerate = false) => {
        const description = (bannerDesc.trim() || goal).trim();
        if (!description) {
            toast.error("Describe the banner you'd like");
            return;
        }
        setBannerBusy(true);
        try {
            const { data } = await api.post("/campaigns/image", {
                description,
                // New random seed on regenerate → a fresh variant of the same idea.
                seed: regenerate ? Math.floor(Math.random() * 1_000_000) : undefined,
            });
            setImgLoading(true);
            setBanner(data);
        } catch {
            toast.error("Banner generation failed");
        } finally {
            setBannerBusy(false);
        }
    };

    const generateCombo = async () => {
        setComboBusy(true);
        try {
            // `focus` is an optional hint — the combo is built from live sales
            // trends + best-sellers even if the goal is blank.
            const { data } = await api.post("/combos/generate", { focus: goal });
            setCombo(data);
        } catch {
            toast.error("Combo generation failed");
        } finally {
            setComboBusy(false);
        }
    };

    const launchCombo = async () => {
        if (!combo) return;
        try {
            await api.post("/actions/execute", {
                id: "combo_launch",
                kind: "promotion",
                label: combo.name,
                payload: { combo },
            });
            toast.success(`"${combo.name}" scheduled as a promotion`);
        } catch {
            toast.error("Launch failed");
        }
    };

    return (
        <Layout>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Marketing AI
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                Generate a campaign in seconds
            </h1>

            <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1fr_1fr]">
                <div className="rounded-3xl border border-slate-200 bg-white p-6">
                    <div className="space-y-5">
                        <div>
                            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                Audience
                            </label>
                            <select
                                data-testid={TID.campAudience}
                                value={audience}
                                onChange={(e) => setAudience(e.target.value)}
                                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                            >
                                {AUDIENCES.map((a) => (
                                    <option key={a.id} value={a.id}>
                                        {a.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                Channel
                            </label>
                            <div className="mt-1.5 flex flex-wrap gap-2">
                                {CHANNELS.map((c) => (
                                    <button
                                        key={c.id}
                                        data-testid={`${TID.campChannel}-${c.id}`}
                                        onClick={() => setChannel(c.id)}
                                        className={`rounded-full border px-4 py-2 text-sm font-medium transition-all ${
                                            channel === c.id
                                                ? "border-[#FF6B35] bg-orange-50 text-[#E85D2A]"
                                                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                                        }`}
                                    >
                                        {c.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                Goal
                            </label>
                            <input
                                data-testid={TID.campGoal}
                                value={goal}
                                onChange={(e) => setGoal(e.target.value)}
                                list="goals-list"
                                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                            />
                            <datalist id="goals-list">
                                {GOALS.map((g) => (
                                    <option key={g} value={g} />
                                ))}
                            </datalist>
                        </div>
                        <button
                            data-testid={TID.campGenerate}
                            onClick={generate}
                            disabled={busy}
                            className="inline-flex items-center gap-2 rounded-full bg-[#FF6B35] px-6 py-2.5 text-sm font-medium text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:bg-[#E85D2A] disabled:opacity-50"
                        >
                            {busy ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <Sparkles size={14} />
                            )}
                            {busy ? "Generating…" : "Generate Campaign"}
                        </button>
                    </div>
                </div>

                <div
                    data-testid={TID.campResult}
                    className="rounded-3xl border border-slate-200 bg-white p-6"
                >
                    {!draft && !busy && (
                        <div className="grid h-full place-items-center text-center text-sm text-slate-400">
                            Generated copy will appear here.
                        </div>
                    )}
                    {busy && (
                        <div className="grid h-full place-items-center text-sm text-slate-400">
                            <div className="flex items-center gap-2">
                                <Loader2
                                    size={14}
                                    className="animate-spin text-[#FF6B35]"
                                />
                                Drafting copy…
                            </div>
                        </div>
                    )}
                    {draft && (
                        <div className="space-y-4">
                            <div>
                                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                                    Subject
                                </div>
                                <div className="mt-0.5 font-display text-xl font-semibold text-slate-900">
                                    {draft.subject}
                                </div>
                            </div>
                            <div>
                                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                                    Body
                                </div>
                                <p className="mt-0.5 whitespace-pre-line text-[15px] leading-relaxed text-slate-700">
                                    {draft.body}
                                </p>
                            </div>
                            <div className="flex flex-wrap gap-3">
                                <div className="rounded-xl bg-slate-50 px-3 py-2">
                                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                        CTA
                                    </div>
                                    <div className="font-display text-base font-semibold text-slate-900">
                                        {draft.cta}
                                    </div>
                                </div>
                                <div className="rounded-xl bg-slate-50 px-3 py-2">
                                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                        Est. Reach
                                    </div>
                                    <div className="font-display text-base font-semibold text-slate-900">
                                        {draft.estimated_reach?.toLocaleString() || "—"}
                                    </div>
                                </div>
                                <div className="rounded-xl bg-emerald-50 px-3 py-2">
                                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700">
                                        Est. Revenue
                                    </div>
                                    <div className="font-display text-base font-semibold text-emerald-600">
                                        $
                                        {draft.estimated_revenue?.toLocaleString() ||
                                            "—"}
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={launch}
                                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
                            >
                                <Send size={14} /> Launch Campaign
                            </button>

                            {/* Text actions live with the text they copy; the
                                image action lives with the banner below. */}
                            <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                                <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                    Take it to your channels
                                </div>
                                <div className="mt-3 flex flex-wrap gap-3">
                                    <button
                                        data-testid={TID.campCopyWhatsapp}
                                        onClick={() =>
                                            copyText(whatsappText(draft), "WhatsApp copy")
                                        }
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-[#25D366] hover:text-[#128C7E]"
                                    >
                                        <MessageCircle size={13} /> Copy for WhatsApp
                                    </button>
                                    <button
                                        data-testid={TID.campCopyCaption}
                                        onClick={() =>
                                            copyText(instagramCaption(draft), "Caption")
                                        }
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:border-[#FF6B35] hover:text-[#E85D2A]"
                                    >
                                        <Copy size={13} /> Copy caption
                                    </button>
                                </div>
                                <p className="mt-3 text-xs text-slate-500">
                                    Come back in 48 hours — we’ll show you if revenue moved.
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Promotional banner (AI image) */}
            <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-6">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                    <ImageIcon size={13} /> Promotional Banner
                </div>
                <h2 className="mt-1 font-display text-xl font-semibold text-slate-900">
                    Describe it — the AI designs the banner
                </h2>

                <div className="mt-4 grid items-start gap-6 lg:grid-cols-[1fr_1fr]">
                    <div>
                        <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                            What should the banner show?
                        </label>
                        <textarea
                            data-testid={TID.campBannerDesc}
                            value={bannerDesc}
                            onChange={(e) => setBannerDesc(e.target.value)}
                            rows={3}
                            placeholder={`e.g. "Sizzling BBQ ribs platter with truffle fries on a rustic wooden table" — leave empty to use the goal: "${goal}"`}
                            className="mt-1.5 w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                        />
                        <button
                            data-testid={TID.campBannerGenerate}
                            onClick={() => generateBanner(false)}
                            disabled={bannerBusy}
                            className="mt-3 inline-flex items-center gap-2 rounded-full bg-[#FF6B35] px-6 py-2.5 text-sm font-medium text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:bg-[#E85D2A] disabled:opacity-50"
                        >
                            {bannerBusy ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <ImageIcon size={14} />
                            )}
                            {bannerBusy ? "Designing…" : "Generate Banner"}
                        </button>
                    </div>

                    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
                        {!banner && !bannerBusy && (
                            <div
                                className="grid place-items-center text-center text-sm text-slate-400"
                                style={{ aspectRatio: "1200 / 628" }}
                            >
                                Your banner preview will appear here.
                            </div>
                        )}
                        {(bannerBusy || (banner && imgLoading)) && (
                            <div
                                className="grid place-items-center bg-slate-100 text-sm text-slate-400"
                                style={{ aspectRatio: "1200 / 628" }}
                            >
                                <div className="flex items-center gap-2">
                                    <Loader2 size={14} className="animate-spin text-[#FF6B35]" />
                                    Rendering banner…
                                </div>
                            </div>
                        )}
                        {banner && (
                            <img
                                data-testid={TID.campBannerImg}
                                src={banner.url}
                                alt="AI-generated promotional banner"
                                onLoad={() => setImgLoading(false)}
                                onError={() => {
                                    setImgLoading(false);
                                    toast.error("Banner image failed to load");
                                }}
                                className={`w-full ${imgLoading ? "hidden" : "block"}`}
                                style={{ aspectRatio: "1200 / 628", objectFit: "cover" }}
                            />
                        )}
                        {banner && !imgLoading && (
                            <div className="border-t border-slate-200 bg-white px-4 py-3">
                                <div
                                    data-testid={TID.campBannerReady}
                                    className="flex items-center gap-2 text-sm font-semibold text-emerald-600"
                                >
                                    <CheckCircle2 size={15} /> Banner ready
                                </div>
                                <div className="mt-3 flex flex-wrap items-center gap-3">
                                    <button
                                        data-testid={TID.campDownloadInstagram}
                                        onClick={downloadBanner}
                                        disabled={!banner?.url || downloading}
                                        className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                                    >
                                        {downloading ? (
                                            <Loader2 size={13} className="animate-spin" />
                                        ) : (
                                            <Instagram size={13} />
                                        )}
                                        {downloading ? "Downloading…" : "Download for Instagram"}
                                    </button>
                                    <button
                                        data-testid={TID.campBannerRegenerate}
                                        onClick={() => generateBanner(true)}
                                        disabled={bannerBusy}
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-[#FF6B35] hover:text-[#E85D2A] disabled:opacity-50"
                                    >
                                        <RefreshCw size={13} /> Regenerate
                                    </button>
                                    <a
                                        href={banner.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:border-[#FF6B35] hover:text-[#E85D2A]"
                                    >
                                        <Download size={13} /> Open full size
                                    </a>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
            {/* AI Combo builder (data-grounded offer) */}
            <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-6">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                    <UtensilsCrossed size={13} /> AI Combo Builder
                </div>
                <h2 className="mt-1 font-display text-xl font-semibold text-slate-900">
                    Turn your best-sellers into a combo that sells
                </h2>
                <p className="mt-1 max-w-xl text-sm text-slate-500">
                    The AI reads your live sales trends and top-selling items, then
                    bundles complementary products into an offer priced to lift
                    average order value.
                </p>

                <div className="mt-6 grid items-stretch gap-6 lg:grid-cols-2">
                    {/* LEFT — controls */}
                    <div className="flex flex-col rounded-2xl border border-slate-200 bg-slate-50/60 p-5">
                        <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                            Optimize toward (optional)
                        </label>
                        <input
                            value={goal}
                            onChange={(e) => setGoal(e.target.value)}
                            list="goals-list"
                            className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                        />
                        <p className="mt-2 text-xs text-slate-400">
                            Leave as-is to let the AI pick from what's selling best right now.
                        </p>
                        <button
                            data-testid={TID.comboGenerate}
                            onClick={generateCombo}
                            disabled={comboBusy}
                            className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-full bg-[#FF6B35] px-6 py-3 text-sm font-semibold text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:bg-[#E85D2A] disabled:opacity-50"
                        >
                            {comboBusy ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <Sparkles size={14} />
                            )}
                            {comboBusy ? "Building combo…" : "Generate Combo"}
                        </button>

                        {/* How it works — makes the panel feel like a tool */}
                        <div className="mt-6 space-y-3 border-t border-slate-200 pt-5">
                            {[
                                { Icon: TrendingUp, t: "Reads live sales trends", s: "Today vs. last week, by product" },
                                { Icon: UtensilsCrossed, t: "Bundles complementary best-sellers", s: "Across courses for a fuller basket" },
                                { Icon: Tag, t: "Prices to lift order value", s: "A charm-priced, save-more offer" },
                            ].map(({ Icon, t, s }) => (
                                <div key={t} className="flex items-start gap-3">
                                    <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white text-[#FF6B35] ring-1 ring-orange-100">
                                        <Icon size={14} />
                                    </span>
                                    <div>
                                        <div className="text-sm font-medium text-slate-800">{t}</div>
                                        <div className="text-xs text-slate-400">{s}</div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* RIGHT — combo preview */}
                    <div
                        data-testid={TID.comboResult}
                        className="flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white"
                    >
                        {/* Preview header bar */}
                        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
                            <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-slate-400">
                                Combo Preview
                            </span>
                            {combo && !comboBusy && combo.savings_pct > 0 && (
                                <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700 ring-1 ring-emerald-100">
                                    Save {combo.savings_pct}%
                                </span>
                            )}
                        </div>

                        {/* Empty / loading skeleton — structured ghost of a real combo */}
                        {(!combo || comboBusy) && (
                            <div className="flex flex-1 flex-col p-5">
                                <div className={comboBusy ? "animate-pulse" : ""}>
                                    <div className="h-6 w-40 rounded-lg bg-slate-100" />
                                    <div className="mt-2 h-3 w-52 rounded bg-slate-100" />
                                    <div className="mt-4 space-y-2.5">
                                        {[0, 1, 2].map((i) => (
                                            <div
                                                key={i}
                                                className="flex items-center gap-3 rounded-xl border border-dashed border-slate-200 bg-slate-50/70 px-3 py-2.5"
                                            >
                                                <span className="h-9 w-9 shrink-0 rounded-lg bg-slate-200/70" />
                                                <div className="flex-1 space-y-1.5">
                                                    <div className="h-2.5 w-2/3 rounded bg-slate-200/70" />
                                                    <div className="h-2 w-1/3 rounded bg-slate-200/60" />
                                                </div>
                                                <div className="h-3 w-10 rounded bg-slate-200/70" />
                                            </div>
                                        ))}
                                    </div>
                                    <div className="mt-4 h-16 rounded-2xl border border-dashed border-slate-200 bg-slate-50/70" />
                                </div>
                                <div className="mt-auto pt-5 text-center text-xs text-slate-400">
                                    {comboBusy ? (
                                        <span className="inline-flex items-center gap-2 text-slate-500">
                                            <Loader2 size={13} className="animate-spin text-[#FF6B35]" />
                                            Analyzing best-sellers…
                                        </span>
                                    ) : (
                                        "Generate a combo to see products, pricing and impact here."
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Result */}
                        {combo && !comboBusy && (
                            <div className="flex flex-1 flex-col p-5">
                                {/* Title block */}
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <h3 className="font-display text-2xl font-semibold tracking-tight text-slate-900">
                                            {combo.name}
                                        </h3>
                                        {combo.tagline && (
                                            <p className="mt-0.5 text-sm text-slate-500">
                                                {combo.tagline}
                                            </p>
                                        )}
                                    </div>
                                    <span className="shrink-0 rounded-full bg-orange-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] text-[#E85D2A]">
                                        {combo.target_daypart}
                                    </span>
                                </div>

                                {/* Product cards */}
                                <div className="mt-4 space-y-2.5">
                                    {combo.items?.map((it, i) => (
                                        <div
                                            key={i}
                                            className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-colors hover:border-orange-200"
                                        >
                                            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-[#FF6B35] to-[#E85D2A] text-white shadow-[0_3px_8px_rgba(255,107,53,0.3)]">
                                                <UtensilsCrossed size={15} />
                                            </span>
                                            <div className="min-w-0 flex-1">
                                                <div className="truncate text-sm font-semibold text-slate-800">
                                                    {it.name}
                                                </div>
                                                {it.category && (
                                                    <div className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-400">
                                                        {it.category}
                                                    </div>
                                                )}
                                            </div>
                                            <span className="font-display text-sm font-semibold tabular-nums text-slate-700">
                                                ${it.price?.toFixed(2)}
                                            </span>
                                        </div>
                                    ))}
                                </div>

                                {/* Pricing summary bar */}
                                <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-orange-100 bg-gradient-to-b from-orange-50/70 to-white px-4 py-3.5">
                                    <div>
                                        <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                            Combo price
                                        </div>
                                        <div className="flex items-baseline gap-2">
                                            <span className="font-display text-[28px] font-semibold leading-none tabular-nums text-slate-900">
                                                ${combo.combo_price?.toFixed(2)}
                                            </span>
                                            <span className="text-sm text-slate-400 line-through tabular-nums">
                                                ${combo.regular_total?.toFixed(2)}
                                            </span>
                                        </div>
                                    </div>
                                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-white shadow-[0_3px_10px_rgba(16,185,129,0.3)]">
                                        <Tag size={12} /> Save ${combo.savings?.toFixed(2)}
                                    </span>
                                </div>

                                {/* Rationale */}
                                {combo.rationale && (
                                    <p className="mt-4 border-l-2 border-orange-200 pl-3 text-[13.5px] leading-relaxed text-slate-600">
                                        {combo.rationale}
                                    </p>
                                )}

                                {/* Impact chips */}
                                <div className="mt-3 flex flex-wrap gap-2">
                                    <span className="inline-flex items-center gap-1.5 rounded-lg bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600">
                                        <TrendingUp size={13} className="text-emerald-600" />
                                        ~{combo.expected_uplift_pct}% AOV uplift
                                    </span>
                                    {combo.expected_daily_revenue > 0 && (
                                        <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700">
                                            +${combo.expected_daily_revenue?.toLocaleString()}/day est.
                                        </span>
                                    )}
                                </div>

                                {/* Actions */}
                                <div className="mt-5 flex flex-wrap items-center gap-2.5 border-t border-slate-100 pt-5">
                                    <button
                                        data-testid={TID.comboLaunch}
                                        onClick={launchCombo}
                                        className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800"
                                    >
                                        <Send size={14} /> Launch Combo
                                    </button>
                                    <button
                                        data-testid={TID.comboRegenerate}
                                        onClick={generateCombo}
                                        disabled={comboBusy}
                                        className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-[#FF6B35] hover:text-[#E85D2A] disabled:opacity-50"
                                    >
                                        <RefreshCw size={13} /> Regenerate
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </Layout>
    );
}
