import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, MouseEvent as ReactMouseEvent, PropsWithChildren } from "react";
import {
  Activity,
  Bell,
  Cable,
  FileText,
  FlaskConical,
  LogOut,
  Server,
  Settings,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import {
  AUTH_UPDATED_EVENT,
  clearAuthSession,
  loadAuthSession,
  sessionUserDisplayName,
  type AuthSession,
} from "../auth/session";
import ankaaLogo from "../assets/partner-logos/ankaa.svg";
import cirqLogo from "../assets/partner-logos/cirq.svg";
import ibmLogo from "../assets/partner-logos/ibm.svg";
import pennylaneLogo from "../assets/partner-logos/pennylane.svg";
import qiskitLogo from "../assets/partner-logos/qiskit.svg";
import xanaduLogo from "../assets/partner-logos/xanadu.png";

const navSections = [
  {
    title: "Decoder",
    items: [
      { to: "/decoder/scientific", label: "Scientific", icon: FlaskConical },
      { to: "/decoder/telemetry", label: "Telemetry", icon: Activity },
      { to: "/decoder/validation", label: "Validation", icon: ShieldCheck },
      { to: "/decoder/logs", label: "Logs", icon: FileText },
    ],
  },
  {
    title: "Platform",
    className: "nav-section-spaced",
    items: [
      { to: "/runs", label: "Runs", icon: Workflow },
      { to: "/providers", label: "Providers", icon: Server },
      { to: "/observability", label: "Observability", icon: Bell },
    ],
  },
  {
    title: "System",
    className: "nav-section-divider",
    items: [
      { to: "/settings", label: "Settings", icon: Settings },
      { to: "/hardware-api", label: "Hardware API", icon: Cable },
    ],
  },
];

const hardwareDataSourceLogos = [
  { label: "IBM", src: ibmLogo },
  { label: "Xanadu", src: xanaduLogo },
  { label: "Ankaa", src: ankaaLogo },
];

const simulatorDataSourceLogos = [
  { label: "PennyLane", src: pennylaneLogo },
  { label: "Cirq", src: cirqLogo },
  { label: "Qiskit", src: qiskitLogo },
];

const RIGHT_RAIL_WIDTH_STORAGE_KEY = "lidmas.rightRailWidth";
const RIGHT_RAIL_DEFAULT_WIDTH = 340;
const RIGHT_RAIL_MIN_WIDTH = 280;
const RIGHT_RAIL_MAX_WIDTH = 560;

function clampRailWidth(value: number) {
  return Math.min(RIGHT_RAIL_MAX_WIDTH, Math.max(RIGHT_RAIL_MIN_WIDTH, value));
}

export function AppShell({ children }: PropsWithChildren) {
  const location = useLocation();
  const showRightRail = location.pathname === "/decoder/scientific";
  const [session, setSession] = useState<AuthSession | null>(() => loadAuthSession());
  const [rightRailWidth, setRightRailWidth] = useState<number>(() => {
    if (typeof window === "undefined") {
      return RIGHT_RAIL_DEFAULT_WIDTH;
    }
    const raw = window.localStorage.getItem(RIGHT_RAIL_WIDTH_STORAGE_KEY);
    if (!raw) {
      return RIGHT_RAIL_DEFAULT_WIDTH;
    }
    const parsed = Number.parseInt(raw, 10);
    if (!Number.isFinite(parsed)) {
      return RIGHT_RAIL_DEFAULT_WIDTH;
    }
    return clampRailWidth(parsed);
  });
  const [rightRailDragging, setRightRailDragging] = useState(false);
  const rightRailDraggingRef = useRef(false);

  useEffect(() => {
    const syncSession = () => {
      setSession(loadAuthSession());
    };
    syncSession();
    window.addEventListener(AUTH_UPDATED_EVENT, syncSession);
    window.addEventListener("storage", syncSession);
    return () => {
      window.removeEventListener(AUTH_UPDATED_EVENT, syncSession);
      window.removeEventListener("storage", syncSession);
    };
  }, []);

  useEffect(() => {
    setSession(loadAuthSession());
  }, [location.pathname]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(RIGHT_RAIL_WIDTH_STORAGE_KEY, String(rightRailWidth));
  }, [rightRailWidth]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (!rightRailDragging) {
      return;
    }

    const handleMouseMove = (event: MouseEvent) => {
      if (!rightRailDraggingRef.current) {
        return;
      }
      const widthFromRight = window.innerWidth - event.clientX;
      setRightRailWidth(clampRailWidth(widthFromRight));
    };
    const stopDrag = () => {
      rightRailDraggingRef.current = false;
      setRightRailDragging(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", stopDrag);
    window.addEventListener("mouseleave", stopDrag);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", stopDrag);
      window.removeEventListener("mouseleave", stopDrag);
    };
  }, [rightRailDragging]);

  useEffect(() => {
    if (showRightRail) {
      return;
    }
    rightRailDraggingRef.current = false;
    setRightRailDragging(false);
  }, [showRightRail]);

  const sessionName = sessionUserDisplayName(session?.user);
  const sessionEmail = session?.user.email ?? "";

  const sessionInitials = useMemo(() => {
    const parts = sessionName
      .trim()
      .split(/\s+/)
      .filter((part) => part.length > 0);
    if (parts.length === 0) {
      return "LD";
    }
    if (parts.length === 1) {
      return parts[0].slice(0, 2).toUpperCase();
    }
    return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
  }, [sessionName]);

  const handleSignOut = () => {
    clearAuthSession();
    window.location.reload();
  };

  const handleRightRailResizeStart = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!showRightRail) {
      return;
    }
    event.preventDefault();
    rightRailDraggingRef.current = true;
    setRightRailDragging(true);
  };

  return (
    <div
      className={`app-shell ${showRightRail ? "app-shell-with-right-rail" : ""} ${
        rightRailDragging ? "app-shell-resizing" : ""
      }`}
      style={{ "--right-rail-width": `${showRightRail ? rightRailWidth : 0}px` } as CSSProperties}
    >
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-text">LiDMaS+</div>
          <div className="logo-subtext">Decoder Intelligence Layer</div>
        </div>

        {navSections.map((section) => (
          <div key={section.title} className={section.className}>
            <div className="nav-section-title">{section.title}</div>
            <ul className="nav-menu">
              {section.items.map((item) => (
                <li key={item.to} className="nav-item">
                  <NavLink to={item.to} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
                    <span className="nav-icon">
                      <item.icon size={14} aria-hidden="true" />
                    </span>
                    <span>{item.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}

        <div className="sidebar-data-source">
          <div className="sidebar-data-source-block">
            <div className="nav-section-title">Hardware Data Source</div>
            <div className="sidebar-data-source-marquee" aria-label="Hardware data sources">
              <div className="sidebar-data-source-track">
                <div className="sidebar-data-source-group">
                  {hardwareDataSourceLogos.map((logo) => (
                    <div key={`source-logo-${logo.label}`} className="sidebar-data-source-item" title={logo.label}>
                      <img src={logo.src} alt={`${logo.label} logo`} />
                    </div>
                  ))}
                </div>
                <div className="sidebar-data-source-group" aria-hidden="true">
                  {hardwareDataSourceLogos.map((logo) => (
                    <div key={`source-logo-repeat-${logo.label}`} className="sidebar-data-source-item">
                      <img src={logo.src} alt="" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="sidebar-data-source-block">
            <div className="nav-section-title">Simulator Data Source</div>
            <div className="sidebar-data-source-marquee sidebar-data-source-marquee-simulator" aria-label="Simulator data sources">
              <div className="sidebar-data-source-track">
                <div className="sidebar-data-source-group">
                  {simulatorDataSourceLogos.map((logo) => (
                    <div
                      key={`simulator-source-${logo.label}`}
                      className="sidebar-data-source-item sidebar-data-source-item-simulator"
                      title={logo.label}
                    >
                      <img src={logo.src} alt={`${logo.label} logo`} />
                    </div>
                  ))}
                </div>
                <div className="sidebar-data-source-group" aria-hidden="true">
                  {simulatorDataSourceLogos.map((logo) => (
                    <div
                      key={`simulator-source-repeat-${logo.label}`}
                      className="sidebar-data-source-item sidebar-data-source-item-simulator"
                    >
                      <img src={logo.src} alt="" />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">{sessionInitials}</div>
            <div className="user-info">
              <div className="user-name">{sessionName}</div>
              <div className="user-status">{sessionEmail || "Signed in"}</div>
            </div>
            <button className="btn-icon sidebar-signout" title="Sign out" onClick={handleSignOut}>
              <LogOut size={14} aria-hidden="true" />
            </button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <div className="content-container">
          {children}
        </div>
      </main>
      <div
        className={`right-rail-resizer ${showRightRail ? "active" : ""}`}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize live console rail"
        onMouseDown={handleRightRailResizeStart}
      />

      <aside
        id="app-right-rail"
        className={`right-rail ${showRightRail ? "active" : ""}`}
        aria-label="Metric interpretation panel"
      />
    </div>
  );
}
