import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { adminApi, getAdminKey, setAdminKey } from "./adminClient";

interface AdminAuthContextValue {
  isUnlocked: boolean;
  unlock: (key: string) => Promise<void>;
  lock: () => void;
}

const AdminAuthContext = createContext<AdminAuthContextValue | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [key, setKeyState] = useState<string | null>(() => getAdminKey());

  const unlock = useCallback(async (candidate: string) => {
    setAdminKey(candidate);
    try {
      await adminApi.listCustomers();
      setKeyState(candidate);
    } catch (err) {
      setAdminKey(null);
      throw err;
    }
  }, []);

  const lock = useCallback(() => {
    setAdminKey(null);
    setKeyState(null);
  }, []);

  const value = useMemo<AdminAuthContextValue>(
    () => ({ isUnlocked: key !== null, unlock, lock }),
    [key, unlock, lock],
  );

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
}

export function useAdminAuth(): AdminAuthContextValue {
  const ctx = useContext(AdminAuthContext);
  if (!ctx) throw new Error("useAdminAuth must be used within AdminAuthProvider");
  return ctx;
}
