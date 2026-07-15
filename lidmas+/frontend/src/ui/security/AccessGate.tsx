import { useEffect, useState } from "react";
import type { FormEvent, PropsWithChildren } from "react";

import { ApiError } from "../../api/client";
import { useAuthMe, useSignIn, useSignUp } from "../../api/hooks";
import {
  AUTH_UPDATED_EVENT,
  clearAuthSession,
  loadAuthSession,
  saveAuthSession,
  type AuthSession,
} from "../../auth/session";
import ibmLogo from "../../assets/partner-logos/ibm.svg";
import xanaduLogo from "../../assets/partner-logos/xanadu.png";
import ankaaLogo from "../../assets/partner-logos/ankaa.svg";

type AuthMode = "signin" | "signup";
const AUTH_PARTNERS = [
  { name: "IBM", src: ibmLogo, variant: "ibm" },
  { name: "Xanadu", src: xanaduLogo, variant: "xanadu" },
  { name: "Ankaa", src: ankaaLogo, variant: "ankaa" },
] as const;

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export function AccessGate({ children }: PropsWithChildren) {
  const [session, setSession] = useState<AuthSession | null>(() => loadAuthSession());
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);

  const signUpMutation = useSignUp();
  const signInMutation = useSignIn();
  const authMeQuery = useAuthMe({ enabled: Boolean(session) });

  useEffect(() => {
    const syncSession = () => {
      setSession(loadAuthSession());
    };
    window.addEventListener(AUTH_UPDATED_EVENT, syncSession);
    window.addEventListener("storage", syncSession);
    return () => {
      window.removeEventListener(AUTH_UPDATED_EVENT, syncSession);
      window.removeEventListener("storage", syncSession);
    };
  }, []);

  useEffect(() => {
    if (!session || !authMeQuery.error) {
      return;
    }
    if (authMeQuery.error instanceof ApiError && authMeQuery.error.status === 401) {
      clearAuthSession();
      setSession(null);
      setAuthError("Session expired. Sign in again.");
    }
  }, [authMeQuery.error, session]);

  useEffect(() => {
    if (!session || !authMeQuery.data) {
      return;
    }
    const user = authMeQuery.data;
    if (
      user.email !== session.user.email ||
      user.full_name !== session.user.full_name ||
      user.id !== session.user.id
    ) {
      const refreshed = saveAuthSession({
        token: session.token,
        token_type: session.token_type,
        expires_at: session.expires_at,
        user,
      });
      setSession(refreshed);
    }
  }, [authMeQuery.data, session]);

  const checkingExistingSession = Boolean(session) && authMeQuery.isLoading;
  const shouldLock = !session && !checkingExistingSession;
  const shouldBlur = shouldLock || checkingExistingSession;

  const beginSession = (nextSession: AuthSession) => {
    setSession(nextSession);
    setPassword("");
    setConfirmPassword("");
    setAuthError(null);
  };

  const submitAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAuthError(null);
    try {
      const normalizedEmail = email.trim().toLowerCase();
      if (!isValidEmail(normalizedEmail)) {
        throw new Error("Enter a valid email address.");
      }
      if (password.length < 8) {
        throw new Error("Password must be at least 8 characters.");
      }

      if (authMode === "signup") {
        const trimmedName = fullName.trim();
        if (trimmedName.length < 2) {
          throw new Error("Full name must be at least 2 characters.");
        }
        if (password !== confirmPassword) {
          throw new Error("Password confirmation does not match.");
        }
        const response = await signUpMutation.mutateAsync({
          full_name: trimmedName,
          email: normalizedEmail,
          password,
        });
        beginSession(saveAuthSession(response));
        return;
      }

      const response = await signInMutation.mutateAsync({
        email: normalizedEmail,
        password,
      });
      beginSession(saveAuthSession(response));
    } catch (error) {
      if (error instanceof ApiError) {
        setAuthError(error.message);
      } else if (error instanceof Error) {
        setAuthError(error.message);
      } else {
        setAuthError("Authentication failed.");
      }
    }
  };

  const authBusy = signUpMutation.isPending || signInMutation.isPending;

  return (
    <div className="access-gate">
      <div className={`access-gate-content ${shouldBlur ? "blurred" : ""}`}>{children}</div>

      {checkingExistingSession ? (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="auth-check-title">
          <div className="modal modal-small auth-modal">
            <div className="modal-body">
              <div className="loading-block">
                <span className="loading-dot" />
                <span id="auth-check-title">Validating session...</span>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {shouldLock ? (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="auth-gate-title">
          <div className="auth-lock-shell">
            <div className="modal modal-small auth-modal">
              <div className="modal-header auth-modal-header">
                <div className="auth-branding">
                  <div className="auth-brand-title" id="auth-gate-title">
                    LiDMaS+
                  </div>
                  <div className="auth-brand-subtitle">Logical Qubit Decoder</div>
                  <div className="auth-brand-mode">
                    {authMode === "signup" ? "Create secure operator account" : "Secure operator sign in"}
                  </div>
                </div>
              </div>
              <form onSubmit={submitAuth}>
                <div className="modal-body">
                  <div className="auth-mode-tabs">
                    <button
                      type="button"
                      className={`auth-mode-tab ${authMode === "signin" ? "active" : ""}`}
                      onClick={() => {
                        setAuthMode("signin");
                        setAuthError(null);
                      }}
                    >
                      Sign In
                    </button>
                    <button
                      type="button"
                      className={`auth-mode-tab ${authMode === "signup" ? "active" : ""}`}
                      onClick={() => {
                        setAuthMode("signup");
                        setAuthError(null);
                      }}
                    >
                      Sign Up
                    </button>
                  </div>

                  {authMode === "signup" ? (
                    <div className="form-group">
                      <label className="form-label required">Full Name</label>
                      <input
                        className="form-input"
                        type="text"
                        value={fullName}
                        onChange={(event) => setFullName(event.target.value)}
                        placeholder="Operator Name"
                        autoComplete="name"
                        required
                      />
                    </div>
                  ) : null}

                  <div className="form-group">
                    <label className="form-label required">Email</label>
                    <input
                      className="form-input"
                      type="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="you@example.org"
                      autoComplete="email"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label required">Password</label>
                    <input
                      className="form-input"
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="At least 8 characters"
                      autoComplete={authMode === "signup" ? "new-password" : "current-password"}
                      required
                    />
                  </div>

                  {authMode === "signup" ? (
                    <div className="form-group">
                      <label className="form-label required">Confirm Password</label>
                      <input
                        className="form-input"
                        type="password"
                        value={confirmPassword}
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        placeholder="Repeat password"
                        autoComplete="new-password"
                        required
                      />
                    </div>
                  ) : null}

                  {authError ? <div className="warning-message auth-warning">{authError}</div> : null}
                </div>
                <div className="modal-footer">
                  <button type="submit" className="btn btn-primary" disabled={authBusy}>
                    {authBusy ? "Processing..." : authMode === "signup" ? "Create Account" : "Sign In"}
                  </button>
                </div>
              </form>
            </div>
            <div className="auth-partner-marquee auth-partner-marquee-outside" aria-label="Hardware partners">
              <div className="auth-partner-heading">Open Live and Replay Data Sourced from:</div>
              <div className="auth-partner-track-wrap">
                <div className="auth-partner-track">
                  {[...AUTH_PARTNERS, ...AUTH_PARTNERS].map((partner, index) => (
                    <div key={`${partner.name}-${index}`} className="auth-partner-item">
                      <img
                        className={`auth-partner-logo ${partner.variant}`}
                        src={partner.src}
                        alt={`${partner.name} logo`}
                        loading="lazy"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

    </div>
  );
}
