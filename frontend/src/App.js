import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import ShareModal from "@/components/ShareModal";
import Login from "@/screens/Login";
import Home from "@/screens/Home";
import Chat from "@/screens/Chat";
import Branches from "@/screens/Branches";
import Customers from "@/screens/Customers";
import Menu from "@/screens/Menu";
import Marketing from "@/screens/Marketing";
import Promotions from "@/screens/Promotions";
import Forecast from "@/screens/Forecast";
import Manager from "@/screens/Manager";

function Protected({ children }) {
    const { auth } = useAuth();
    return auth ? children : <Navigate to="/" replace />;
}

function GuestOnly({ children }) {
    const { auth } = useAuth();
    return auth ? <Navigate to="/home" replace /> : children;
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
