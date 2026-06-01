import { NavLink } from "react-router-dom";
import { Gauge, Radio, PlayCircle, BarChart3 } from "lucide-react";

interface NavbarProps {}

export default function Navbar({}: NavbarProps) {
  const links = [
    { to: "/dashboard", icon: Gauge, label: "Dashboard" },
    { to: "/live", icon: Radio, label: "Live" },
    { to: "/replay", icon: PlayCircle, label: "Replay" },
    { to: "/analysis", icon: BarChart3, label: "Analysis" },
  ];

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="navbar-logo">●</span>
        <span className="navbar-title">koru</span>
      </div>

      <div className="navbar-links">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) =>
              `navbar-link ${isActive ? "active" : ""}`
            }
          >
            <l.icon size={16} />
            <span>{l.label}</span>
          </NavLink>
        ))}
      </div>

      <div className="navbar-actions">
        <div className="api-status connected">● Koru Proxy</div>
      </div>
    </nav>
  );
}
