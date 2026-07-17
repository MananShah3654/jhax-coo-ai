/**
 * A tiny inline SVG trend line — no chart library, no bundle cost.
 *
 * points — array of numbers, oldest first. Fewer than 2 points renders nothing
 *          (a single dot implies a trend we can't actually show).
 */
export default function Sparkline({
    points = [],
    width = 104,
    height = 28,
    className = "",
}) {
    const vals = (points || []).filter((n) => typeof n === "number");
    if (vals.length < 2) return null;

    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const span = max - min || 1; // flat series => straight line, never /0
    const stepX = width / (vals.length - 1);

    const xy = vals.map((v, i) => [
        i * stepX,
        // invert: SVG y grows downward. Inset by 1px so the stroke isn't clipped.
        height - 1 - ((v - min) / span) * (height - 2),
    ]);
    const line = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    const area = `${line} ${width},${height} 0,${height}`;
    const rising = vals[vals.length - 1] >= vals[0];
    const stroke = rising ? "#059669" : "#ef4444";

    return (
        <svg
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
            className={className}
            aria-hidden="true"
            preserveAspectRatio="none"
        >
            <polygon points={area} fill={stroke} opacity="0.08" />
            <polyline
                points={line}
                fill="none"
                stroke={stroke}
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}
