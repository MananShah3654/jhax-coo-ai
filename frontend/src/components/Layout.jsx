import { NavLink } from "react-router-dom";
import {
    Home,
    Gauge,
    MessageSquare,
    MapPin,
    Users,
    UtensilsCrossed,
    Megaphone,
    Sparkles,
    TrendingUp,
    ClipboardList,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";

const NAV = [
    { to: "/home",      label: "AI COO Home", Icon: Home,            tid: TID.navHome },
    { to: "/kpis",      label: "Key Metrics", Icon: Gauge,           tid: TID.navKpis },
    { to: "/chat",      label: "Ask Anything", Icon: MessageSquare,  tid: TID.navChat },
    { to: "/branches",  label: "Branches",     Icon: MapPin,         tid: TID.navBranches },
    { to: "/customers", label: "Customers",    Icon: Users,          tid: TID.navCustomers },
    { to: "/menu",      label: "Menu",         Icon: UtensilsCrossed, tid: TID.navMenu },
    { to: "/marketing", label: "Marketing AI", Icon: Megaphone,      tid: TID.navMarketing },
    { to: "/promotions",label: "Promotions",   Icon: Sparkles,       tid: "nav-promotions" },
    { to: "/forecast",  label: "Forecast",     Icon: TrendingUp,     tid: TID.navForecast },
    { to: "/manager",   label: "Manager Mode", Icon: ClipboardList,  tid: TID.navManager },
];

export default function Layout({ children }) {
    const { profile } = useAuth();
    const displayName = profile?.name || "Owner";
    const displayRestaurant = profile?.restaurant_name || "";
    return (
        <div className="bg-jp flex min-h-screen">
            {/* Sidebar (desktop) */}
            <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-slate-200/70 bg-white/60 backdrop-blur-xl lg:flex lg:flex-col">
                <div className="p-6">
                    <Logo />
                </div>
                <nav className="flex flex-1 flex-col gap-1 px-3">
                    {NAV.map(({ to, label, Icon, tid }) => (
                        <NavLink
                            key={to}
                            to={to}
                            data-testid={tid}
                            className={({ isActive }) =>
                                `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                                    isActive
                                        ? "bg-orange-50 text-[#E85D2A]"
                                        : "text-slate-600 hover:bg-slate-50"
                                }`
                            }
                        >
                            {({ isActive }) => (
                                <>
                                    <Icon
                                        size={16}
                                        className={
                                            isActive
                                                ? "text-[#FF6B35]"
                                                : "text-slate-400 group-hover:text-slate-600"
                                        }
                                    />
                                    <span className="font-medium">{label}</span>
                                </>
                            )}
                        </NavLink>
                    ))}
                </nav>
                <div className="border-t border-slate-200/70 p-4">
                    <div className="mb-3 rounded-xl bg-slate-50 p-3">
                        <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
                            Signed in
                        </div>
                        <div className="mt-0.5 text-sm font-semibold text-slate-900">
                            {displayName}
                        </div>
                        <div className="text-xs text-slate-500">
                            {displayRestaurant}
                        </div>
                    </div>
                </div>
            </aside>

            {/* Mobile top nav */}
            <div className="fixed inset-x-0 top-0 z-40 flex items-center border-b border-slate-200/70 bg-white/80 px-4 py-3 backdrop-blur-xl lg:hidden">
                <Logo />
            </div>

            <main className="flex-1 pb-24 pt-16 lg:pt-0">
                <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:py-10">
                    {children}
                </div>
            </main>

            {/* Mobile bottom nav */}
            <nav className="fixed inset-x-0 bottom-0 z-40 flex justify-around border-t border-slate-200/70 bg-white/95 px-2 py-1.5 backdrop-blur-xl lg:hidden">
                {NAV.slice(0, 5).map(({ to, label, Icon, tid }) => (
                    <NavLink
                        key={to}
                        to={to}
                        data-testid={tid + "-m"}
                        className={({ isActive }) =>
                            `flex flex-col items-center gap-0.5 px-2 py-1.5 text-[10px] ${
                                isActive
                                    ? "text-[#FF6B35]"
                                    : "text-slate-500"
                            }`
                        }
                    >
                        <Icon size={18} />
                        <span>{label.split(" ")[0]}</span>
                    </NavLink>
                ))}
            </nav>
        </div>
    );
}
