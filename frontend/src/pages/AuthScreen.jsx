import { useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { ArrowLeft, LockKeyhole, Mail, Sparkles } from "lucide-react";
import {
  login,
  register,
  requestPasswordReset,
  resetPassword,
} from "../services/api";

export default function AuthScreen({ onAuthenticated }) {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState(
    location.pathname === "/reset-password" ? "reset" : "login",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const changeMode = (nextMode) => {
    setMode(nextMode);
    setError("");
    setNotice("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      if (mode === "login" || mode === "register") {
        const authenticate = mode === "register" ? register : login;
        onAuthenticated(await authenticate({ email, password }));
        return;
      }
      if (mode === "forgot") {
        const response = await requestPasswordReset(email);
        setNotice(response.message);
        return;
      }
      if (password !== confirmPassword) {
        setError("The passwords do not match.");
        return;
      }
      const token = searchParams.get("token");
      if (!token) {
        setError("This password reset link is invalid or has expired.");
        return;
      }
      await resetPassword(token, password);
      changeMode("login");
      setNotice("Your password has been updated. Sign in with your new password.");
      setPassword("");
      setConfirmPassword("");
    } catch (submitError) {
      setError(submitError.message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const isReset = mode === "reset";
  const needsEmail = mode !== "reset";
  const needsPassword = mode === "login" || mode === "register" || isReset;
  const title = {
    login: "Welcome back",
    register: "Create your account",
    forgot: "Reset your password",
    reset: "Choose a new password",
  }[mode];
  const description = {
    login: "Sign in to continue to your research workspace.",
    register: "Create an account to save and manage your research.",
    forgot: "Enter your email and we’ll send a password reset link.",
    reset: "Choose a new password for your account.",
  }[mode];

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand">
          <span className="brand-mark"><Sparkles size={19} /></span>
          <span>Atlas<span className="brand-muted"> Research</span></span>
        </div>
        <div className="auth-heading">
          <span className="auth-icon"><LockKeyhole size={20} /></span>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {error && <div className="auth-message auth-error" role="alert">{error}</div>}
        {notice && <div className="auth-message auth-success" role="status">{notice}</div>}
        <form className="auth-form" onSubmit={handleSubmit}>
          {needsEmail && <label>
            Email address
            <span className="auth-input"><Mail size={17} /><input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
            /></span>
          </label>}
          {needsPassword && <label>
            {isReset ? "New password" : "Password"}
            <input
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={8}
              maxLength={128}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              required
            />
          </label>}
          {isReset && <label>
            Confirm new password
            <input
              type="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Enter your new password again"
              required
            />
          </label>}
          {mode === "login" && <button type="button" className="auth-link auth-forgot" onClick={() => changeMode("forgot")}>Forgot password?</button>}
          <button className="primary-button auth-submit" disabled={busy}>
            {busy ? "Please wait…" : ({
              login: "Sign in",
              register: "Create account",
              forgot: "Send reset link",
              reset: "Update password",
            }[mode])}
          </button>
        </form>
        {mode === "login" && <p className="auth-switch">New to Atlas Research? <button className="auth-link" onClick={() => changeMode("register")}>Create an account</button></p>}
        {mode === "register" && <p className="auth-switch">Already have an account? <button className="auth-link" onClick={() => changeMode("login")}>Sign in</button></p>}
        {(mode === "forgot" || isReset) && <button className="auth-back" onClick={() => { changeMode("login"); if (location.pathname === "/reset-password") window.history.replaceState({}, "", "/"); }}>
          <ArrowLeft size={15} /> Back to sign in
        </button>}
      </section>
      <p className="auth-caption">A considered space for better research.</p>
    </main>
  );
}
