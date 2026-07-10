import { Delete } from "lucide-react";

// Reusable numeric keypad for a 4-digit PIN. Controlled via value/onChange.
// Shows up to `maxLen` dots, filled to the current length.
export default function PinPad({ value, onChange, maxLen = 4, disabled, testidDigit }) {
    const press = (d) => {
        if (disabled) return;
        if (value.length >= maxLen) return;
        onChange(value + d);
    };
    const back = () => onChange(value.slice(0, -1));
    const clear = () => onChange("");

    return (
        <div>
            <div className="flex items-center justify-center gap-3">
                {Array.from({ length: maxLen }).map((_, i) => (
                    <div
                        key={i}
                        className={`h-3.5 w-3.5 rounded-full border-2 transition-all ${
                            value.length > i
                                ? "scale-110 border-[#FF6B35] bg-[#FF6B35]"
                                : "border-slate-300"
                        }`}
                    />
                ))}
            </div>

            <div className="mt-8 grid grid-cols-3 gap-3">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                    <button
                        key={n}
                        type="button"
                        data-testid={testidDigit ? testidDigit(n) : undefined}
                        onClick={() => press(String(n))}
                        className="flex h-14 items-center justify-center rounded-2xl bg-white text-2xl font-medium text-slate-900 shadow-[0_2px_8px_rgba(15,23,42,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-md active:scale-95"
                    >
                        {n}
                    </button>
                ))}
                <button
                    type="button"
                    onClick={clear}
                    className="flex h-14 items-center justify-center rounded-2xl text-slate-400 hover:bg-slate-100"
                >
                    <span className="text-sm font-medium">Clear</span>
                </button>
                <button
                    type="button"
                    data-testid={testidDigit ? testidDigit(0) : undefined}
                    onClick={() => press("0")}
                    className="flex h-14 items-center justify-center rounded-2xl bg-white text-2xl font-medium text-slate-900 shadow-[0_2px_8px_rgba(15,23,42,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-md active:scale-95"
                >
                    0
                </button>
                <button
                    type="button"
                    onClick={back}
                    className="flex h-14 items-center justify-center rounded-2xl text-slate-500 hover:bg-slate-100"
                >
                    <Delete size={20} />
                </button>
            </div>
        </div>
    );
}
