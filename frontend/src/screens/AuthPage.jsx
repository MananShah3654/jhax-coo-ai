// AuthPage — the sign-in gate shown at "/" when no one is logged in.
//
// It replaces the old <Login /> tabbed screen. It renders the branded page and
// opens the reusable <AuthModal /> (which is the actual login UI). The modal is
// open by default here; if the user closes it they see a "Log in or sign up"
// button that reopens it — the same standalone trigger pattern that any other
// button in the app (e.g. a header "Log in") can use.
import { useState } from "react";
import Logo from "@/components/Logo";
import AuthModal from "@/components/AuthModal";

export default function AuthPage() {
    const [showAuth, setShowAuth] = useState(true);

    return (
        <div className="bg-jp grid min-h-screen place-items-center px-4 py-8">
            <div className="w-full max-w-md text-center">
                <div className="mb-8 flex justify-center">
                    <Logo size={36} />
                </div>
                <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                    Ask your restaurant anything
                </h1>
                <p className="mt-2 text-sm text-slate-500">
                    Sign in to open your AI COO dashboard.
                </p>
                <button
                    type="button"
                    data-testid="open-auth-modal"
                    onClick={() => setShowAuth(true)}
                    className="mt-8 inline-flex items-center justify-center gap-2 rounded-full bg-[#FF6B35] px-8 py-3 font-medium text-white shadow-sm transition hover:brightness-105 active:scale-[0.99]"
                >
                    Log in or sign up
                </button>
            </div>

            <AuthModal open={showAuth} onClose={() => setShowAuth(false)} />
        </div>
    );
}
