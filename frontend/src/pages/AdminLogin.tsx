/**
 * Admin Login Page - Two-Step OTP Authentication
 * Secure authentication for admin panel access with email OTP
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Shield, Lock, Eye, EyeOff, AlertCircle, Mail, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/apiClient';

interface AdminLoginResponse {
  admin: {
    id: string;
    email: string;
    name: string;
    role: string;
    permissions: string[];
  };
  token: string;
  expires_at: string;
  requires_otp?: boolean;
}

interface OTPRequestResponse {
  requires_otp: boolean;
  message: string;
  email: string;
}

const AdminLogin = () => {
  const navigate = useNavigate();
  
  // Step 1: Email + Password
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  
  // Step 2: OTP
  const [otpRequired, setOtpRequired] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  
  // UI State
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const data = await api.admin.login({ email, password });
      
      // Check if OTP is required
      if (data.requires_otp) {
        setOtpRequired(true);
        // In dev mode with mock email, auto-fill OTP
        if (data.dev_otp) {
          setOtpCode(data.dev_otp);
          toast.success('Dev mode: OTP auto-filled');
        } else {
          toast.success('OTP sent to your email! Check your inbox.');
        }
      } else {
        // Direct login (fallback for admins without OTP)
        if (data.token) {
          sessionStorage.setItem('adminData', JSON.stringify(data.admin));
        }
        toast.success('Login successful!');
        navigate('/admin/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOTPVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const data = await api.admin.verifyOtp({ email, otp_code: otpCode });
      
      // Store non-sensitive admin profile for UI only; auth is cookie-backed.
      sessionStorage.setItem('adminData', JSON.stringify(data.admin));
      
      toast.success(`Welcome back, ${data.admin.name}!`);
      navigate('/admin/dashboard');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'OTP verification failed';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBackToLogin = () => {
    setOtpRequired(false);
    setOtpCode('');
    setError('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-4">
      {/* Background Effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-20 w-96 h-96 bg-red-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-amber-500/10 rounded-full blur-3xl" />
      </div>

      <Card className="w-full max-w-md glass-card border-amber-500/20 relative z-10">
        <CardHeader className="text-center space-y-4">
          {/* Logo */}
          <div className="mx-auto w-16 h-16 rounded-xl bg-gradient-to-br from-amber-500 to-red-600 flex items-center justify-center">
            <Shield className="w-8 h-8 text-white" />
          </div>
          
          <div>
            <CardTitle className="text-2xl font-display">
              Admin <span className="text-amber-400">Control Panel</span>
            </CardTitle>
            <CardDescription className="text-muted-foreground mt-2">
              {otpRequired ? 'Enter the OTP code sent to your email' : 'Secure access for authorized personnel only'}
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent>
          {!otpRequired ? (
            // Step 1: Email + Password Form
            <form onSubmit={handlePasswordLogin} className="space-y-6">
              {error && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  {error}
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm font-medium">
                  Admin Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="admin@cryptovault.financial"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-12 bg-slate-900/50 border-slate-700"
                  required
                  disabled={isLoading}
                  data-testid="admin-email-input"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm font-medium">
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-12 bg-slate-900/50 border-slate-700 pr-12"
                    required
                    disabled={isLoading}
                    data-testid="admin-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-white transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full h-12 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-black font-semibold"
                disabled={isLoading}
                data-testid="admin-login-button"
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                    Verifying...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Lock className="h-4 w-4" />
                    Continue to OTP
                  </span>
                )}
              </Button>
            </form>
          ) : (
            // Step 2: OTP Verification Form
            <form onSubmit={handleOTPVerify} className="space-y-6">
              {error && (
                <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-red-400 text-sm">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  {error}
                </div>
              )}

              <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-start gap-3">
                <Mail className="h-5 w-5 text-amber-400 flex-shrink-0 mt-0.5" />
                <div className="text-sm">
                  <p className="text-amber-400 font-medium">OTP Code Sent</p>
                  <p className="text-muted-foreground mt-1">
                    Check your email: <span className="text-white">{email}</span>
                  </p>
                  <p className="text-muted-foreground text-xs mt-1">
                    The code expires in 5 minutes
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="otp" className="text-sm font-medium">
                  6-Digit OTP Code
                </Label>
                <Input
                  id="otp"
                  type="text"
                  placeholder="000000"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  className="h-14 bg-slate-900/50 border-slate-700 text-center text-2xl font-mono tracking-widest"
                  required
                  disabled={isLoading}
                  maxLength={6}
                  pattern="\d{6}"
                  data-testid="admin-otp-input"
                />
              </div>

              <div className="space-y-3">
                <Button
                  type="submit"
                  className="w-full h-12 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-black font-semibold"
                  disabled={isLoading || otpCode.length !== 6}
                  data-testid="admin-verify-otp-button"
                >
                  {isLoading ? (
                    <span className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                      Verifying OTP...
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <Shield className="h-4 w-4" />
                      Verify & Login
                    </span>
                  )}
                </Button>

                <Button
                  type="button"
                  onClick={handleBackToLogin}
                  variant="outline"
                  className="w-full h-10 border-slate-700"
                  disabled={isLoading}
                >
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to Login
                </Button>
              </div>
            </form>
          )}

          <div className="mt-6 pt-6 border-t border-slate-800">
            <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
              <Shield className="h-3 w-3" />
              <span>Protected by email OTP verification</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AdminLogin;
