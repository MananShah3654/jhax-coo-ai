import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ShareModal from "@/components/ShareModal";
import Login from "@/screens/Login";
import Onboarding from "@/screens/Onboarding";


import PinSetup from "@/screens/PinSetup";
import PinLock from "@/screens/PinLock";
import Home from "@/screens/Home";
import Chat from "@/screens/Chat";
import Branches from "@/screens/Branches";
import Customers from "@/screens/Customers";
import Menu from "@/screens/Menu";
import Marketing from "@/screens/Marketing";
import CampaignRoi from "@/screens/CampaignRoi";
import Promotions from "@/screens/Promotions";
import Forecast from "@/screens/Forecast";
import Manager from "@/screens/Manager";

// Brief splash while Firebase resolves its initial auth state, so we don't
// flash the login screen at an already-signed-in user.
function Splash() {
    return (
        <div className="bg-jp grid min-h-screen place-items-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-[#FF6B35]" />
        </div>
    );
}

// Single source of truth for where an authenticated user belongs right now:
// finish onboarding → set a PIN → unlock with PIN → into the app ("/home").
function firstStep({ needsOnboarding, needsPinSetup, locked }) {
    if (needsOnboarding) return "/onboarding";
    if (needsPinSetup) return "/set-pin";
    if (locked) return "/unlock";
    return "/home";
}

function Protected({ children }) {
    const { auth, ready, sessionActive, ...flags } = useAuth();
    if (!ready) return <Splash />;
    // No session, or a cold-restored session that hasn't logged in this
    // page-load → back to Login.
    if (!auth || !sessionActive) return <Navigate to="/" replace />;
    const step = firstStep(flags);
    // "/home" means all gates passed → render the requested screen.
    if (step !== "/home") return <Navigate to={step} replace />;
    return children;
}

function GuestOnly({ children }) {
    const { auth, ready, sessionActive, ...flags } = useAuth();
    if (!ready) return <Splash />;
    // Only skip Login for an ACTIVE session (fresh login this page-load, or a
    // complete account with a PIN to unlock). A half-finished restored session
    // stays on Login — we never jump straight to /onboarding on app open.
    if (auth && sessionActive) return <Navigate to={firstStep(flags)} replace />;
    return children;
}

// Gate a specific onboarding step to exactly the users who belong there.
function StepRoute({ path, children }) {
    const { fbUser, ready, sessionActive, ...flags } = useAuth();
    if (!ready) return <Splash />;
    if (!fbUser || !sessionActive) return <Navigate to="/" replace />;
    const step = firstStep(flags);
    if (step !== path) return <Navigate to={step} replace />;
    return children;
}

function AppRoutes() {
    return (
        <Routes>
            <Route
                path="/"
                element={
                    <GuestOnly>
                        <Login />
                    </GuestOnly>
                }
            />
            <Route
                path="/onboarding"
                element={
                    <StepRoute path="/onboarding">
                        <Onboarding />
                    </StepRoute>
                }
            />
            <Route
                path="/set-pin"
                element={
                    <StepRoute path="/set-pin">
                        <PinSetup />
                    </StepRoute>
                }
            />
            <Route
                path="/unlock"
                element={
                    <StepRoute path="/unlock">
                        <PinLock />
                    </StepRoute>
                }
            />
            <Route
                path="/home"
                element={
                    <Protected>
                        <Home />
                    </Protected>
                }
            />
            <Route
                path="/chat"
                element={
                    <Protected>
                        <Chat />
                    </Protected>
                }
            />
            <Route
                path="/branches"
                element={
                    <Protected>
                        <Branches />
                    </Protected>
                }
            />
            <Route
                path="/customers"
                element={
                    <Protected>
                        <Customers />
                    </Protected>
                }
            />
            <Route
                path="/menu"
                element={
                    <Protected>
                        <Menu />
                    </Protected>
                }
            />
            <Route
                path="/marketing"
                element={
                    <Protected>
                        <Marketing />
                    </Protected>
                }
            />
            <Route
                path="/campaign-roi"
                element={
                    <Protected>
                        <CampaignRoi />
                    </Protected>
                }
            />
            <Route
                path="/promotions"
                element={
                    <Protected>
                        <Promotions />
                    </Protected>
                }
            />
            <Route
                path="/forecast"
                element={
                    <Protected>
                        <Forecast />
                    </Protected>
                }
            />
            <Route
                path="/manager"
                element={
                    <Protected>
                        <Manager />
                    </Protected>
                }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}

export default function App() {
    return (
        <div className="App">
            <AuthProvider>
                <BrowserRouter>
                    <AppRoutes />
                    <ShareModal />
                    <Toaster
                        position="top-right"
                        richColors
                        toastOptions={{
                            style: { fontFamily: "Manrope, sans-serif" },
                        }}
                    />
                </BrowserRouter>
            </AuthProvider>
        </div>
    );
}
