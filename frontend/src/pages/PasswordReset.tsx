/**
 * Password Reset Pages
 * - ResetRequest: Email form to request password reset
 * - ResetConfirm: New password form with token validation
 */
import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Mail, Lock, ArrowLeft, Loader2, CheckCircle2, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/apiClient';

// ============================================
// PASSWORD RESET REQUEST PAGE
// ============================================
export const ResetRequest = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email) {
      toast.error('Please enter your email address');
      return;
    }

    setIsLoading(true);

    try {
      await api.auth.forgotPassword(email);
      setIsSuccess(true);
      toast.success('Reset link sent! Check your email.');
    } catch (error: any) {
      toast.error(error.message || 'Failed to send reset link');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="h-16 w-16 mx-auto mb-6 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
          </div>
          <h1 className="font-display text-2xl font-bold mb-3">Check Your Email</h1>
          <p className="text-muted-foreground mb-6">
            We've sent a password reset link to <strong>{email}</strong>. 
            The link will expire in 1 hour.
          </p>
          <Button 
            variant="outline" 
            onClick={() => navigate('/auth')}
            className="min-h-[44px]"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Sign In
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
          onClick={() => navigate('/auth')}
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
          <h1 className="font-display text-2xl sm:text-3xl font-bold mb-2">Reset Password</h1>
          <p className="text-muted-foreground mb-8">
            Enter your email address and we'll send you a link to reset your password.
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-11 h-12 text-base"
                  data-testid="reset-email-input"
                  required
                />
              </div>
            </div>

            <Button 
              type="submit" 
              className="w-full h-12 bg-gold-500 hover:bg-gold-600 text-black font-semibold"
              disabled={isLoading}
              data-testid="reset-submit-button"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Sending...
                </>
              ) : (
                'Send Reset Link'
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};

// ============================================
// PASSWORD RESET ROUTER PAGE
// ============================================
export const ResetPasswordPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  if (token) {
    return <Navigate to={`/reset?token=${encodeURIComponent(token)}`} replace />;
  }

  return <ResetRequest />;
};

// ============================================
// PASSWORD RESET CONFIRM PAGE
// ============================================
export const ResetConfirm = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [isValidatingToken, setIsValidatingToken] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);

  useEffect(() => {
    let mounted = true;

    const validateToken = async () => {
      if (!token) {
        if (!mounted) return;
        setTokenValid(false);
        setIsValidatingToken(false);
        return;
      }

      try {
        const validation = await api.auth.validateResetToken(token);
        if (!mounted) return;
        setTokenValid(Boolean(validation?.valid));
      } catch {
        if (!mounted) return;
        setTokenValid(false);
      } finally {
        if (mounted) {
          setIsValidatingToken(false);
        }
      }
    };

    validateToken();

    return () => {
      mounted = false;
    };
  }, [token]);

  if (isValidatingToken) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <Loader2 className="h-8 w-8 mx-auto animate-spin text-gold-400 mb-4" />
          <p className="text-muted-foreground">Validating reset link…</p>
        </div>
      </div>
    );
  }

  if (!token || !tokenValid) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <h1 className="font-display text-2xl font-bold mb-3 text-destructive">Invalid Link</h1>
          <p className="text-muted-foreground mb-6">
            This password reset link is invalid or has expired.
          </p>
          <Button 
            onClick={() => navigate('/reset-password')}
            className="min-h-[44px] bg-gold-500 hover:bg-gold-600 text-black"
          >
            Request New Link
          </Button>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }

    if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
      toast.error('Password must include uppercase, lowercase, and a number');
      return;
    }

    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    setIsLoading(true);

    try {
      await api.auth.resetPassword(token, password);
      setIsSuccess(true);
      toast.success('Password updated successfully!');

      // Redirect to login after 2 seconds
      setTimeout(() => navigate('/auth'), 2000);
    } catch (error: any) {
      toast.error(error.message || 'Failed to reset password. The link may have expired.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="h-16 w-16 mx-auto mb-6 rounded-full bg-emerald-500/10 flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
          </div>
          <h1 className="font-display text-2xl font-bold mb-3">Password Updated!</h1>
          <p className="text-muted-foreground mb-6">
            Your password has been reset successfully. Redirecting to sign in...
          </p>
          <Loader2 className="h-6 w-6 mx-auto animate-spin text-gold-400" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-center p-4 sm:p-6 border-b border-border/30">
        <div className="flex items-center gap-3">
          <img src="/logo.svg" alt="CryptoVault" className="h-10 w-10 object-contain" />
          <span className="font-display text-lg font-bold">
            Crypto<span className="text-gold-400">Vault</span>
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
        <div className="w-full max-w-md">
          <h1 className="font-display text-2xl sm:text-3xl font-bold mb-2">Create New Password</h1>
          <p className="text-muted-foreground mb-8">
            Enter a strong password for your account.
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="password">New Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-11 pr-11 h-12 text-base"
                  data-testid="new-password-input"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1"
                >
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              <p className="text-xs text-muted-foreground">Minimum 8 chars, with uppercase, lowercase, and a number</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  id="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="pl-11 h-12 text-base"
                  data-testid="confirm-password-input"
                  required
                />
              </div>
            </div>

            <Button 
              type="submit" 
              className="w-full h-12 bg-gold-500 hover:bg-gold-600 text-black font-semibold"
              disabled={isLoading}
              data-testid="reset-confirm-button"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Updating...
                </>
              ) : (
                'Update Password'
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default { ResetRequest, ResetConfirm, ResetPasswordPage };
