"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { useTheme } from "@/components/theme/ThemeProvider";

const protectedLinks = [
  { href: "/documents", label: "Documents" },
  { href: "/chat", label: "Chat" },
];

const adminLinks = [{ href: "/admin", label: "Admin" }];

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading, logout, user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <nav className="nav" aria-label="Primary navigation">
      <Link className="nav-brand" href="/">
        Equipment Agent
      </Link>
      <div className="nav-links">
        {!isLoading && isAuthenticated
          ? [...protectedLinks, ...(user?.role === "admin" ? adminLinks : [])].map((link) => (
              <Link className={pathname === link.href ? "active" : undefined} href={link.href} key={link.href}>
                {link.label}
              </Link>
            ))
          : null}
      </div>
      <div className="nav-account">
        <button className="theme-toggle" onClick={toggleTheme} type="button">
          {theme === "dark" ? "Light" : "Dark"}
        </button>
        {!isLoading && isAuthenticated ? (
          <>
            <span>{user?.username}</span>
            <button className="link-button" onClick={handleLogout} type="button">
              Logout
            </button>
          </>
        ) : (
          <>
            <Link className={pathname === "/login" ? "active" : undefined} href="/login">
              Login
            </Link>
            <Link className={pathname === "/register" ? "active" : undefined} href="/register">
              Register
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
