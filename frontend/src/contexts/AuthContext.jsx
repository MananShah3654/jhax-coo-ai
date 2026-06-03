import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
    const [auth, setAuth] = useState(() => {
        try {
            return JSON.parse(localStorage.getItem("jhapay_coo_auth")) || null;
        } catch {
            return null;
        }
    });

    useEffect(() => {
        if (auth)
            localStorage.setItem("jhapay_coo_auth", JSON.stringify(auth));
        else localStorage.removeItem("jhapay_coo_auth");
    }, [auth]);

    const loginWithPin = async (pin) => {
        const { data } = await api.post("/auth/pin", { pin });
        setAuth(data);
        return data;
    };

    const logout = () => setAuth(null);

    return (
        <AuthCtx.Provider value={{ auth, loginWithPin, logout }}>
            {children}
        </AuthCtx.Provider>
    );
}

export const useAuth = () => useContext(AuthCtx);
