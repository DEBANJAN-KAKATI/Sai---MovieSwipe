import { useQuery } from "@tanstack/react-query";
import { BrandLogo } from "./BrandLogo";
import { NavLink } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../store";
import { Icon } from "./Icon";

function useNavItems() {
  const inbox = useQuery({ queryKey: ["inbox"], queryFn: api.inbox, refetchInterval: 30_000 });
  const friends = useQuery({ queryKey: ["friends"], queryFn: api.friends, refetchInterval: 30_000 });
  const socialBadge = (inbox.data?.unseen ?? 0) + (friends.data?.incoming.length ?? 0);
  return [
    { to: "/", label: "Discover", icon: "compass", end: true, hint: "Swipe your deck" },
    { to: "/lists", label: "Lists", icon: "list", hint: "Watch List & history" },
    { to: "/together", label: "Together", icon: "heart", hint: "Duo & group matching" },
    { to: "/social", label: "Social", icon: "users", badge: socialBadge, hint: "Friends, shared lists" },
    { to: "/profile", label: "Me", icon: "user", hint: "Taste DNA & settings" },
  ];
}

/** Phones and tablets: tab bar at the bottom. Hidden on desktop by CSS. */
export function BottomNav() {
  const items = useNavItems();
  return (
    <nav className="bottom-nav" aria-label="Main">
      {items.map((it) => (
        <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => (isActive ? "active" : "")}>
          <Icon name={it.icon} size={22} />
          {it.label}
          {!!it.badge && <span className="badge-dot">{it.badge}</span>}
        </NavLink>
      ))}
    </nav>
  );
}

/** Desktop: fixed sidebar with brand, navigation and the signed-in user. Hidden on small screens by CSS. */
export function SideNav() {
  const items = useNavItems();
  const user = useAuth((s) => s.user);
  return (
    <aside className="side-nav" aria-label="Main">
      <NavLink to="/" className="brand side-brand">
        <BrandLogo height={42} />
      </NavLink>
      <nav className="side-links">
        {items.map((it) => (
          <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => `side-link${isActive ? " active" : ""}`}>
            <Icon name={it.icon} size={20} />
            <span className="grow">
              <span className="side-label">{it.label}</span>
              <span className="side-hint">{it.hint}</span>
            </span>
            {!!it.badge && <span className="count side-badge">{it.badge}</span>}
          </NavLink>
        ))}
      </nav>
      {user && (
        <NavLink to="/profile" className="side-user">
          <div className="avatar sm">{user.avatar}</div>
          <div style={{ minWidth: 0 }}>
            <div className="ellipsis" style={{ fontWeight: 700, fontSize: 14 }}>{user.display_name}</div>
            <div className="tiny faint">{user.is_guest ? "Guest — save your account" : `@${user.username}`}</div>
          </div>
        </NavLink>
      )}
    </aside>
  );
}
