import { useState, type FormEvent } from "react";
import { AlertCircle, Lock, User } from "lucide-react";
import g10xLogo from "@/assets/g10x-logo.png";
import { validateCredentials } from "@/auth/users";

interface LoginPageProps {
  onSuccess: (username: string) => void;
  onNavigateToSignup?: () => void;
}

export function LoginPage({ onSuccess, onNavigateToSignup }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username.trim() || !password) {
      setError("Enter both username and password.");
      return;
    }

    setSubmitting(true);
    window.setTimeout(() => {
      if (validateCredentials(username, password)) {
        onSuccess(username.trim());
      } else {
        setError("Invalid username or password.");
        setSubmitting(false);
      }
    }, 150);
  };

  return (
    <div className="relative flex min-h-screen bg-black font-[Inter,sans-serif] overflow-hidden">
      {/* Background Watermark */}
      <div className="pointer-events-none absolute inset-0 z-0 flex items-center justify-center">
        <img
          src={g10xLogo}
          alt=""
          className="w-2/5 max-w-2xl object-contain opacity-30"
          aria-hidden="true"
        />
      </div>

      {/* Form area */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          {/* Liquid Glass Sign-in Box */}
          <div className="overflow-hidden rounded-2xl border border-white/20 bg-white/10 shadow-[0_8px_32px_0_rgba(0,0,0,0.36)] backdrop-blur-xl">
            <div className="border-b border-white/10 bg-white/5 px-6 py-5">
              <div className="mb-3 flex items-center gap-3">
                <img
                  src={g10xLogo}
                  alt="G10X"
                  className="h-8 w-8 object-contain drop-shadow-md"
                />
                <p className="text-lg font-bold text-white tracking-wide">
                  HEB Status Tracker
                </p>
              </div>
              <p className="text-sm font-medium text-gray-200">Sign in</p>
              <p className="mt-1 text-xs text-gray-400">
                Daily status reports and weekly WSR generation
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5 px-6 py-6">
              <div className="space-y-1.5">
                <label
                  htmlFor="login-username"
                  className="text-sm font-medium text-gray-200"
                >
                  Username
                </label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    id="login-username"
                    type="text"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      setError(null);
                    }}
                    className="w-full rounded-lg border border-white/10 bg-black/20 py-2.5 pl-10 pr-3 text-sm text-white outline-none transition-all placeholder:text-gray-500 focus:border-brand-orange focus:bg-black/40 focus:ring-1 focus:ring-brand-orange"
                    placeholder="Enter username"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="login-password"
                  className="text-sm font-medium text-gray-200"
                >
                  Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    id="login-password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setError(null);
                    }}
                    className="w-full rounded-lg border border-white/10 bg-black/20 py-2.5 pl-10 pr-3 text-sm text-white outline-none transition-all placeholder:text-gray-500 focus:border-brand-orange focus:bg-black/40 focus:ring-1 focus:ring-brand-orange"
                    placeholder="Enter password"
                  />
                </div>
              </div>

              {error ? (
                <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2.5 text-xs text-red-200">
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-red-400" />
                  <span>{error}</span>
                </div>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-lg bg-brand-orange px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-brand-orange/90 hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Signing in…" : "Sign in"}
              </button>

              {onNavigateToSignup ? (
                <p className="pt-2 text-center text-xs text-gray-400">
                  Don't have an account?{" "}
                  <button
                    type="button"
                    onClick={onNavigateToSignup}
                    className="font-medium text-brand-orange hover:underline focus:outline-none"
                  >
                    Sign up
                  </button>
                </p>
              ) : null}
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}