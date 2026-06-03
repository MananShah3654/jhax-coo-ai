import { useEffect, useState } from "react";
import { X, MessageCircle, Mail, Download, Loader2 } from "lucide-react";
import { API } from "@/lib/api";
import { toast } from "sonner";

const REPORT_TYPES = [
    { id: "daily",     label: "Daily" },
    { id: "weekly",    label: "Weekly" },
    { id: "monthly",   label: "Monthly" },
    { id: "branch",    label: "Branch" },
    { id: "investor",  label: "Investor" },
    { id: "marketing", label: "Marketing" },
];

/**
 * Generates a real PDF on the backend then offers WhatsApp + Email + Download.
 * Mounted near the top of the tree so it can be opened from anywhere by
 * dispatching `window.dispatchEvent(new CustomEvent("share-report",{detail:{type:"daily"}}))`.
 */
export default function ShareModal() {
    const [open, setOpen] = useState(false);
    const [type, setType] = useState("daily");
    const [pdfUrl, setPdfUrl] = useState(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        const onShare = (e) => {
            const t = e.detail?.type || "daily";
            setType(REPORT_TYPES.find((r) => r.id === t) ? t : "daily");
            setOpen(true);
        };
        window.addEventListener("share-report", onShare);
        return () => window.removeEventListener("share-report", onShare);
    }, []);

    useEffect(() => {
        if (!open) {
            setPdfUrl((prev) => {
                if (prev) URL.revokeObjectURL(prev);
                return null;
            });
            return;
        }
        let cancelled = false;
        setBusy(true);
        fetch(`${API}/reports/${type}/pdf`)
            .then((r) => r.blob())
            .then((b) => {
                if (cancelled) return;
                setPdfUrl((prev) => {
                    if (prev) URL.revokeObjectURL(prev);
                    return URL.createObjectURL(b);
                });
            })
            .catch(() => toast.error("Could not generate PDF"))
            .finally(() => !cancelled && setBusy(false));
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, type]);

    if (!open) return null;

    const directPdf = `${API}/reports/${type}/pdf`;
    const waText = `JhaPay AI COO ${type} report — ${directPdf}`;
    const waHref = `https://wa.me/?text=${encodeURIComponent(waText)}`;
    const mailHref = `mailto:?subject=${encodeURIComponent(
        `JhaPay ${type[0].toUpperCase() + type.slice(1)} Report`
    )}&body=${encodeURIComponent(
        `Here's your latest restaurant ${type} report from JhaPay AI COO.\n\n${directPdf}`
    )}`;

    const download = () => {
        if (!pdfUrl) return;
        const a = document.createElement("a");
        a.href = pdfUrl;
        a.download = `jhapay_${type}_report.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
    };

    return (
        <div className="fixed inset-0 z-[60] grid place-items-center bg-slate-900/50 backdrop-blur-sm">
            <div
                data-testid="share-modal"
                className="fade-up w-full max-w-3xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl"
            >
                <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
                    <div>
                        <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                            Share Report
                        </div>
                        <h3 className="font-display text-xl font-semibold text-slate-900">
                            One-click share
                        </h3>
                    </div>
                    <button
                        data-testid="share-close"
                        onClick={() => setOpen(false)}
                        className="grid h-9 w-9 place-items-center rounded-full text-slate-500 hover:bg-slate-100"
                    >
                        <X size={16} />
                    </button>
                </div>

                <div className="flex flex-wrap gap-2 px-6 pt-4">
                    {REPORT_TYPES.map((r) => (
                        <button
                            key={r.id}
                            data-testid={`share-type-${r.id}`}
                            onClick={() => setType(r.id)}
                            className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all ${
                                type === r.id
                                    ? "border-[#FF6B35] bg-orange-50 text-[#E85D2A]"
                                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                            }`}
                        >
                            {r.label}
                        </button>
                    ))}
                </div>

                <div className="grid gap-4 px-6 py-4 md:grid-cols-[1fr_280px]">
                    {/* PDF preview */}
                    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
                        {busy && (
                            <div className="grid h-[420px] place-items-center text-sm text-slate-500">
                                <div className="flex items-center gap-2">
                                    <Loader2
                                        size={14}
                                        className="animate-spin text-[#FF6B35]"
                                    />
                                    Generating PDF…
                                </div>
                            </div>
                        )}
                        {!busy && pdfUrl && (
                            <iframe
                                data-testid="share-pdf-preview"
                                title="Report preview"
                                src={pdfUrl}
                                className="h-[420px] w-full"
                            />
                        )}
                    </div>
                    {/* Actions */}
                    <div className="flex flex-col gap-2">
                        <a
                            data-testid="share-whatsapp"
                            href={waHref}
                            target="_blank"
                            rel="noreferrer"
                            onClick={() => toast.success("Opening WhatsApp")}
                            className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-emerald-300"
                        >
                            <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-50 text-emerald-600">
                                <MessageCircle size={18} />
                            </div>
                            <div>
                                <div className="font-medium text-slate-900">
                                    WhatsApp
                                </div>
                                <div className="text-xs text-slate-500">
                                    Send link to PDF
                                </div>
                            </div>
                        </a>
                        <a
                            data-testid="share-email"
                            href={mailHref}
                            onClick={() => toast.success("Opening email")}
                            className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 transition-all hover:-translate-y-0.5 hover:border-blue-300"
                        >
                            <div className="grid h-10 w-10 place-items-center rounded-full bg-blue-50 text-blue-600">
                                <Mail size={18} />
                            </div>
                            <div>
                                <div className="font-medium text-slate-900">
                                    Email
                                </div>
                                <div className="text-xs text-slate-500">
                                    Compose with PDF link
                                </div>
                            </div>
                        </a>
                        <button
                            data-testid="share-download"
                            disabled={!pdfUrl}
                            onClick={download}
                            className="flex items-center gap-3 rounded-2xl bg-[#FF6B35] p-4 text-left text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:-translate-y-0.5 hover:bg-[#E85D2A] disabled:opacity-50"
                        >
                            <div className="grid h-10 w-10 place-items-center rounded-full bg-white/15">
                                <Download size={18} />
                            </div>
                            <div>
                                <div className="font-medium">Download PDF</div>
                                <div className="text-xs text-white/80">
                                    Save to device
                                </div>
                            </div>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

/** Helper: trigger the modal from anywhere */
export function openShareModal(type = "daily") {
    window.dispatchEvent(new CustomEvent("share-report", { detail: { type } }));
}
