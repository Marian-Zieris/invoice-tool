import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { InvoiceIcon, LogoutIcon, SettingsIcon } from "./icons";

const NAV_ITEMS = [
  { to: "/", label: "Faktury", icon: InvoiceIcon, end: true },
  { to: "/settings", label: "Nastavení", icon: SettingsIcon, end: false },
];

export function Sidebar() {
  const { logout } = useAuth();

  return (
    <aside className="glass-panel hidden w-60 flex-none flex-col gap-6 p-5 md:flex">
      <div className="flex items-center gap-2.5 px-2">
        <div className="flex h-7 w-7 flex-none items-center justify-center rounded-[9px] bg-accent text-[15px] font-bold text-accent-ink">
          D
        </div>
        <div className="text-[16px] font-bold tracking-tight text-ink">Dokladovna</div>
      </div>

      <nav className="flex flex-col gap-0.5">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 text-[14px] font-medium transition-colors ${
                isActive ? "bg-sidebar-active text-sidebar-ink" : "text-sidebar-muted hover:text-sidebar-ink"
              }`
            }
          >
            <Icon className="h-[18px] w-[18px] flex-none" />
            {label}
          </NavLink>
        ))}
      </nav>

      <button
        type="button"
        onClick={logout}
        className="mt-auto flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 text-left text-[13px] font-medium text-sidebar-muted transition-colors hover:text-sidebar-ink"
      >
        <LogoutIcon className="h-[16px] w-[16px] flex-none" />
        Odhlásit se
      </button>
    </aside>
  );
}
