import { useEffect, useRef, useState } from "react";
import { Link, useMatch, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import type { Project } from "../lib/types";
import { Avatar } from "./Avatar";
import { Logo } from "./Logo";

/** Closes a popover when clicking outside it or pressing Escape. */
function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);
  return ref;
}

export default function TopBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const match = useMatch("/p/:projectKey/*");
  const currentKey = match?.params.projectKey?.toUpperCase();
  const [projects, setProjects] = useState<Project[]>([]);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const switcherRef = useDismiss(switcherOpen, () => setSwitcherOpen(false));
  const userRef = useDismiss(userOpen, () => setUserOpen(false));

  useEffect(() => {
    api.projects().then(setProjects).catch(() => setProjects([]));
  }, [currentKey]);

  const current = projects.find((p) => p.key === currentKey);

  return (
    <header className="topbar">
      <Link to="/" className="topbar-brand">
        <Logo />
        <span>Project Tracker</span>
      </Link>

      <div className="popover-anchor" ref={switcherRef}>
        <button
          className="switcher-button"
          aria-haspopup="menu"
          aria-expanded={switcherOpen}
          onClick={() => setSwitcherOpen((o) => !o)}
        >
          {current ? (
            <>
              <span className="project-key">{current.key}</span>
              <span className="switcher-name">{current.name}</span>
            </>
          ) : (
            <span>Projects</span>
          )}
          <span className="chevron" aria-hidden="true">▾</span>
        </button>
        {switcherOpen && (
          <div className="popover menu" role="menu">
            {projects.length === 0 && <div className="menu-empty">No projects</div>}
            {projects.map((p) => (
              <button
                key={p.id}
                role="menuitem"
                className={`menu-item${p.key === currentKey ? " active" : ""}`}
                onClick={() => {
                  setSwitcherOpen(false);
                  navigate(`/p/${p.key}`);
                }}
              >
                <span className="project-key">{p.key}</span>
                <span className="menu-item-text">{p.name}</span>
              </button>
            ))}
            <div className="menu-sep" />
            <button
              role="menuitem"
              className="menu-item"
              onClick={() => {
                setSwitcherOpen(false);
                navigate("/");
              }}
            >
              All projects
            </button>
          </div>
        )}
      </div>

      <div className="topbar-spacer" />

      {user && (
        <div className="popover-anchor" ref={userRef}>
          <button
            className="user-button"
            aria-haspopup="menu"
            aria-expanded={userOpen}
            onClick={() => setUserOpen((o) => !o)}
            title={user.name}
          >
            <Avatar user={user} />
          </button>
          {userOpen && (
            <div className="popover menu menu-right" role="menu">
              <div className="menu-header">
                <strong>{user.name}</strong>
                <span className="muted">{user.email}</span>
              </div>
              <div className="menu-sep" />
              {user.systemRole === "admin" && (
                <button
                  role="menuitem"
                  className="menu-item"
                  onClick={() => {
                    setUserOpen(false);
                    navigate("/admin/users");
                  }}
                >
                  Manage users
                </button>
              )}
              <button
                role="menuitem"
                className="menu-item"
                onClick={() => {
                  setUserOpen(false);
                  navigate("/settings/tokens");
                }}
              >
                API tokens
              </button>
              <button
                role="menuitem"
                className="menu-item"
                onClick={() => {
                  setUserOpen(false);
                  navigate("/change-password");
                }}
              >
                Change password
              </button>
              <button
                role="menuitem"
                className="menu-item"
                onClick={() => {
                  setUserOpen(false);
                  void logout().then(() => navigate("/login"));
                }}
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
