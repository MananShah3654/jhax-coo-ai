/**
 * Apple-Watch style circular health ring.
 */
export default function HealthRing({
    score = 0,
    state = "green",
    size = 168,
    stroke = 14,
}) {
    const radius = (size - stroke) / 2;
    const circ = 2 * Math.PI * radius;
    const offset = circ - (Math.max(0, Math.min(100, score)) / 100) * circ;
    const color =
        state === "green"
            ? "#22C55E"
            : state === "yellow"
              ? "#F59E0B"
              : "#EF4444";
    return (
        <div
            className="relative"
            style={{ width: size, height: size }}
            data-testid="health-ring"
        >
            <svg width={size} height={size} className="-rotate-90">
                <defs>
                    <linearGradient id="hr-grad" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor="#FF6B35" />
                        <stop offset="100%" stopColor={color} />
                    </linearGradient>
                </defs>
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="#F1F5F9"
                    strokeWidth={stroke}
                />
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="url(#hr-grad)"
                    strokeWidth={stroke}
                    strokeLinecap="round"
                    strokeDasharray={circ}
                    strokeDashoffset={offset}
                    style={{
                        transition: "stroke-dashoffset 1.2s cubic-bezier(.2,.7,.3,1)",
                    }}
                />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="font-mono text-5xl font-bold text-slate-900">
                    {score}
                </div>
                <div className="mt-1 text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                    Health Score
                </div>
            </div>
        </div>
    );
}
