export default function Logo({ size = 28, className = "" }) {
    return (
        <div className={`flex items-center gap-2 ${className}`}>
            <div
                className="grid place-items-center rounded-xl shadow-[0_4px_14px_0_rgba(255,107,53,0.35)]"
                style={{
                    width: size + 8,
                    height: size + 8,
                    background:
                        "linear-gradient(180deg,#FF6B35 0%, #E85D2A 100%)",
                }}
            >
                <svg
                    viewBox="0 0 24 24"
                    width={size - 4}
                    height={size - 4}
                    fill="none"
                    stroke="white"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    <path d="M3 11h18l-1.5 9H4.5L3 11Z" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    <path d="M9 15v2M15 15v2" />
                </svg>
            </div>
            <div className="flex flex-col leading-none">
                <span className="font-display text-[17px] font-semibold tracking-tight text-slate-900">
                    JHAX
                </span>
            </div>
        </div>
    );
}
