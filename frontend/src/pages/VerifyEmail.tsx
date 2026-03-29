/**
 * Email Verification Page
 * Supports verification via token (from email link) or manual code/token paste.
 */
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft, CheckCircle2, Loader2, Mail } from "lucide-react";
import { api } from "@/lib/apiClient";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

const AUTH_REQUEST_TIMEOUT_MS = 15000;

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => {
      setTimeout(() => reject(new Error(`Request timeout after ${timeoutMs}ms`)), timeoutMs);
    }),
  ]);
}

const VerifyEmail = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const tokenFromUrl = searchParams.get("token") || "";

  const [token, setToken] = useState(tokenFromUrl);
  const [isLoading, setIsLoading] = useState(Boolean(tokenFromUrl));
  const [isSuccess, setIsSuccess] = useState(false);

  const { refreshSession } = useAuth();

  const verify = async (t: string) => {
    const trimmed = t.trim();
    if (!trimmed) {
      toast.error("Please enter the verification code or token");
      return;
    }

    setIsLoading(true);
    try {
      await withTimeout(api.auth.verifyEmail(trimmed), AUTH_REQUEST_TIMEOUT_MS);
      await refreshSession();
      setIsSuccess(true);
      toast.success("Email verified");
      // Give the UI a moment to render the success state, then go to dashboard.
      setTimeout(() => navigate("/dashboard", { replace: true }), 400);
    } catch (err: any) {
      toast.error(err?.message || "Invalid or expired verification token");
      setIsSuccess(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Auto-verify if a token is present in the URL.
  useEffect(() => {
    if (tokenFromUrl) {
      verify(tokenFromUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await verify(token);
  };

  if (isSuccess) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="h-16 w-16 mx-auto mb-6 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
          </div>
          <h1 className="font-display text-2xl font-bold mb-3">Email Verified</h1>
          <p className="text-muted-foreground mb-6">
            Your account is ready. Redirecting you to the dashboard…
          </p>
          <Button className="min-h-[44px]" onClick={() => navigate("/dashboard", { replace: true })}>
            Go to Dashboard
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 sm:p-6 border-b border-border/30">
        <button
          onClick={() => navigate("/auth")}
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors min-h-[44px]"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Back to Sign In</span>
        </button>
        <div className="flex items-center gap-3">
          <img src="/logo.svg" alt="CryptoVault" className="h-10 w-10 object-contain" />
          <span className="font-display text-lg font-bold">
            Crypto<span className="text-gold-400">Vault</span>
          </span>
        </div>
        <div className="w-10" />
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="w-full max-w-md">
          <h1 className="font-display text-2xl sm:text-3xl font-bold mb-2">Verify Email</h1>
          <p className="text-muted-foreground mb-8">
            Paste the verification code or token from your email.
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="token">Verification Code or Token</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  id="token"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="Enter code or paste token"
                  className="pl-11 h-12 text-base"
                  autoComplete="one-time-code"
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full h-12 bg-gold-500 hover:bg-gold-600 text-black font-semibold"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Verifying…
                </>
              ) : (
                "Verify Email"
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default VerifyEmail;

