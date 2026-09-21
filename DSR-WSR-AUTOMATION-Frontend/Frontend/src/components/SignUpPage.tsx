import { useState, type FormEvent } from "react";
import { AlertCircle, Building2, Lock, User } from "lucide-react";
import g10xLogo from "@/assets/g10x-logo.png";
import { registerUser } from "@/auth/users";

interface SignupPageProps {
  onSuccess: (username: string) => void;
  onNavigateToLogin?: () => void;
}

const DUMMY_DEPARTMENTS = [
  { id: "digital-commerce", name: "Digital Commerce & Omnichannel" },
  { id: "supply-chain", name: "Supply Chain Automation" },
  { id: "core-engineering", name: "Core Engineering & Platforms" },
  { id: "data-analytics", name: "Data Engineering & Analytics" },
  { id: "qa-testing", name: "QA & Automation Delivery" },
];

export function SignupPage({ onSuccess, onNavigateToLogin }: SignupPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [department, setDepartment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username.trim() || !password || !confirmPassword || !department) {
      setError("Please fill in all fields.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }

    setSubmitting(true);

    window.setTimeout(() => {
      const result = registerUser({
        username: username.trim(),
        password,
        department,
      });

      if (result.ok === false) {
        setError(result.error);
        setSubmitting(false);
        return;
      }

      onSuccess(username.trim());
    }, 200);
  };

  return (
    <div className="relative flex min-h-screen overflow-hidden bg-black font-[Inter,sans-serif]">
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
          {/* Liquid Glass Signup Box */}
          <div className="overflow-hidden rounded-2xl border border-white/20 bg-white/10 shadow-[0_8px_32px_0_rgba(0,0,0,0.36)] backdrop-blur-xl">
            <div className="border-b border-white/10 bg-white/5 px-6 py-5">
              <div className="mb-3 flex items-center gap-3">
                <img
                  src={g10xLogo}
                  alt="G10X"
                  className="h-8 w-8 object-contain drop-shadow-md"
                />
                <p className="text-lg font-bold tracking-wide text-white">
                  HEB Status Tracker
                </p>
              </div>
              <p className="text-sm font-medium text-gray-200">Create an account</p>
              <p className="mt-1 text-xs text-gray-400">
                Register to track deliverables, DSRs, and automated status reports
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4 px-6 py-6">
              <div className="space-y-1.5">
                <label
                  htmlFor="signup-username"
                  className="text-sm font-medium text-gray-200"
                >
                  Username
                </label>
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    id="signup-username"
                    type="text"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      setError(null);
                    }}
                    className="w-full rounded-lg border border-white/10 bg-black/20 py-2.5 pl-10 pr-3 text-sm text-white outline-none transition-all placeholder:text-gray-500 focus:border-brand-orange focus:bg-black/40 focus:ring-1 focus:ring-brand-orange"
                    placeholder="Enter desired username"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="signup-department"
                  className="text-sm font-medium text-gray-200"
                >
                  Department / Delivery Track
                </label>
                <div className="relative">
                  <Building2 className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <select
                    id="signup-department"
                    value={department}
                    onChange={(e) => {
                      setDepartment(e.target.value);
                      setError(null);
                    }}
                    className="w-full appearance-none rounded-lg border border-white/10 bg-black/20 py-2.5 pl-10 pr-8 text-sm text-white outline-none transition-all focus:border-brand-orange focus:bg-black/40 focus:ring-1 focus:ring-brand-orange"
                  >
                    <option value="" disabled className="bg-zinc-900 text-gray-500">
                      Select your department
                    </option>
                    {DUMMY_DEPARTMENTS.map((dept) => (
                      <option
                        key={dept.id}
                        value={dept.id}
                        className="bg-zinc-900 text-white"
                      >
                        {dept.name}
                      </option>
                    ))}
                  </select>
                  <div className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">
                    ▼
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="signup-password"
                  className="text-sm font-medium text-gray-200"
                >
                  Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    id="signup-password"
                    type="password"
                    autoComplete="new-password"
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

              <div className="space-y-1.5">
                <label
                  htmlFor="signup-confirm-password"
                  className="text-sm font-medium text-gray-200"
                >
                  Re-enter Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    id="signup-confirm-password"
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value);
                      setError(null);
                    }}
                    className="w-full rounded-lg border border-white/10 bg-black/20 py-2.5 pl-10 pr-3 text-sm text-white outline-none transition-all placeholder:text-gray-500 focus:border-brand-orange focus:bg-black/40 focus:ring-1 focus:ring-brand-orange"
                    placeholder="Confirm password"
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
                {submitting ? "Creating account…" : "Sign up"}
              </button>

              {onNavigateToLogin ? (
                <p className="pt-2 text-center text-xs text-gray-400">
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={onNavigateToLogin}
                    className="font-medium text-brand-orange hover:underline focus:outline-none"
                  >
                    Sign in
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
