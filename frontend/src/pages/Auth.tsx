import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail, Lock, User, ArrowLeft, Eye, EyeOff, Loader2, Phone, MapPin, Gift, ChevronRight } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/apiClient";
import { signUpSchema, signInSchema, validateFormData } from "@/lib/validation";
import OTPVerificationModal from "@/components/OTPVerificationModal";
import RecommendedSetup from "@/components/RecommendedSetup";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";

interface ValidationError {
  field: string;
  message: string;
}

const AUTH_REQUEST_TIMEOUT_MS = 15000;

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) => {
      setTimeout(() => reject(new Error(`Request timeout after ${timeoutMs}ms`)), timeoutMs);
    }),
  ]);
}

const Auth = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [referralCode, setReferralCode] = useState("");
  const [signupStep, setSignupStep] = useState<1 | 2>(1);
  const [showReferralHelp, setShowReferralHelp] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<ValidationError[]>([]);
  const [emailVerificationStep, setEmailVerificationStep] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");
  const [pendingEmail, setPendingEmail] = useState("");
  const [pendingUserName, setPendingUserName] = useState("");
  const [showOTPModal, setShowOTPModal] = useState(false);
  const [showRecommendedSetup, setShowRecommendedSetup] = useState(false);

  const { signIn, signUp } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  const validateForm = (): boolean => {
    const schema = isLogin ? signInSchema : signUpSchema;
    const formData = isLogin
      ? { email, password }
      : { email, password, name, phone_number: phoneNumber, country, city, referral_code: referralCode.toUpperCase() };

    const fieldErrors = validateFormData(schema, formData);
    const newErrors: ValidationError[] = Object.entries(fieldErrors).map(([field, message]) => ({
      field,
      message,
    }));

    setErrors(newErrors);
    return newErrors.length === 0;
  };

  const getFieldError = (field: string): string | null => {
    const error = errors.find(e => e.field === field);
    return error ? error.message : null;
  };

  useEffect(() => {
    const referralFromUrl = new URLSearchParams(location.search).get("ref");
    if (referralFromUrl) {
      setIsLogin(false);
      setSignupStep(2);
      setReferralCode(referralFromUrl.toUpperCase());
    }
  }, [location.search]);

  const handleVerifyEmail = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!verificationCode.trim()) {
      toast({
        title: "Verification code required",
        description: "Please enter the verification code or paste the token",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);

    try {
      await withTimeout(api.auth.verifyEmail(verificationCode), AUTH_REQUEST_TIMEOUT_MS);

      toast({
        title: "Email verified!",
        description: "Your email has been verified. You can now sign in.",
      });

      setEmailVerificationStep(false);
      setVerificationCode("");
      setPendingEmail("");
      setIsLogin(true);
      setEmail("");
      setPassword("");
      setName("");
      setPhoneNumber("");
      setCountry("");
      setCity("");
      setReferralCode("");
      setSignupStep(1);
    } catch (error: any) {
      toast({
        title: "Verification failed",
        description: error.message || "Invalid or expired verification token",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    try {
      if (isLogin) {
        const result = await withTimeout(signIn(email, password), AUTH_REQUEST_TIMEOUT_MS);

        if (result.error) {
          if (result.error.includes("Email not verified") || result.error.includes("Email verification required")) {
            toast({
              title: "Email not verified",
              description: "Please verify your email address first. Check your inbox for a verification link.",
              variant: "destructive",
            });
          } else {
            toast({
              title: "Sign in failed",
              description: result.error,
              variant: "destructive",
            });
          }
        } else {
          toast({
            title: "Welcome back!",
            description: "You have successfully signed in",
          });
          navigate("/dashboard");
        }
      } else {
        if (signupStep === 1) {
          setSignupStep(2);
          setIsLoading(false);
          return;
        }

        const result = await withTimeout(signUp({
          email,
          password,
          name,
          phone_number: phoneNumber || undefined,
          country: country || undefined,
          city: city || undefined,
          referral_code: referralCode ? referralCode.toUpperCase() : undefined,
        }), AUTH_REQUEST_TIMEOUT_MS);

        if (result.error) {
          toast({
            title: "Sign up failed",
            description: result.error,
            variant: "destructive",
          });
        } else if (result.verificationRequired === false) {
          // Email auto-verified (mock mode) - go directly to dashboard
          toast({
            title: "Account created!",
            description: "Welcome to CryptoVault! Your account is ready.",
          });
          navigate("/dashboard");
        } else {
          // Email verification required
          toast({
            title: "Account created!",
            description: "Please check your email for a verification code.",
          });

          setPendingEmail(email);
          setPendingUserName(name);
          setShowOTPModal(true);
        }
      }
    } catch (error: any) {
      toast({
        title: isLogin ? "Sign in failed" : "Sign up failed",
        description: error?.message || "Request failed. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col lg:flex-row">
      {/* Left Panel - Branding (Desktop Only) */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-gold-500/10 via-background to-gold-600/5" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(251,191,36,0.15),transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(217,119,6,0.1),transparent_50%)]" />
        
        <div className="relative z-10 flex flex-col justify-center px-12 xl:px-20">
          {/* Logo - Desktop */}
          <div className="flex items-center gap-4 mb-10">
            <img 
              src="/logo.svg" 
              alt="CryptoVault" 
              className="h-16 w-16 object-contain drop-shadow-lg"
            />
            <span className="font-display text-3xl font-bold">
              Crypto<span className="text-gold-400">Vault</span>
            </span>
          </div>
          
          <h1 className="text-4xl xl:text-5xl font-display font-bold mb-6 leading-tight">
            Your Gateway to<br />
            <span className="bg-gradient-to-r from-gold-400 to-gold-600 bg-clip-text text-transparent">Digital Assets</span>
          </h1>
          
          <p className="text-lg text-muted-foreground max-w-md mb-12">
            Join millions of users trading cryptocurrencies securely. Start your journey with CryptoVault today.
          </p>
          
          <div className="grid grid-cols-3 gap-4 xl:gap-6">
            <div className="glass-card p-4 rounded-xl border border-gold-500/10">
              <div className="text-xl xl:text-2xl font-bold text-gold-400">$2.8T+</div>
              <div className="text-xs xl:text-sm text-muted-foreground">Trading Volume</div>
            </div>
            <div className="glass-card p-4 rounded-xl border border-gold-500/10">
              <div className="text-xl xl:text-2xl font-bold text-gold-400">100M+</div>
              <div className="text-xs xl:text-sm text-muted-foreground">Users</div>
            </div>
            <div className="glass-card p-4 rounded-xl border border-gold-500/10">
              <div className="text-xl xl:text-2xl font-bold text-gold-400">150+</div>
              <div className="text-xs xl:text-sm text-muted-foreground">Countries</div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Right Panel - Auth Form */}
      <div className="flex-1 lg:w-1/2 flex flex-col">
        {/* Mobile Header with Logo */}
        <div className="lg:hidden flex items-center justify-between p-4 sm:p-6 border-b border-border/30">
          <button 
            onClick={() => navigate("/")}
            className="p-2 -ml-2 hover:bg-gold-500/10 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="Go back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-3">
            <img 
              src="/logo.svg" 
              alt="CryptoVault" 
              className="h-10 w-10 sm:h-12 sm:w-12 object-contain"
            />
            <span className="font-display text-lg sm:text-xl font-bold">
              Crypto<span className="text-gold-400">Vault</span>
            </span>
          </div>
          <div className="w-10" /> {/* Spacer for centering */}
        </div>

        {/* Form Container */}
        <div className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-12">
          <div className="w-full max-w-md">
            {/* Desktop Back Button */}
            <div className="hidden lg:block mb-8">
              <button 
                onClick={() => navigate("/")}
                className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors min-h-[44px]"
              >
                <ArrowLeft className="h-4 w-4" />
                Back to home
              </button>
            </div>
            
            {emailVerificationStep ? (
              <>
                <h2 className="text-2xl sm:text-3xl font-display font-bold mb-2">
                  Verify Your Email
                </h2>
                <p className="text-muted-foreground mb-8 text-sm sm:text-base">
                  We've sent a verification link to {pendingEmail}. Enter the verification code below.
                </p>
              </>
            ) : (
              <>
                <h2 className="text-2xl sm:text-3xl font-display font-bold mb-2">
                  {isLogin ? "Welcome back" : "Create account"}
                </h2>
                <p className="text-muted-foreground mb-6 sm:mb-8 text-sm sm:text-base">
                  {isLogin
                    ? "Enter your credentials to access your account"
                    : "Start your crypto journey today"}
                </p>
              </>
            )}

            <form onSubmit={emailVerificationStep ? handleVerifyEmail : handleSubmit} className="space-y-4 sm:space-y-5">
              {!isLogin && (
                <>
                  <div className="rounded-xl border border-border/60 p-3 flex items-center justify-between text-xs">
                    <span className={signupStep === 1 ? "text-gold-400 font-semibold" : "text-muted-foreground"}>Step 1: Account</span>
                    <ChevronRight className="h-3 w-3 text-muted-foreground" />
                    <span className={signupStep === 2 ? "text-gold-400 font-semibold" : "text-muted-foreground"}>Step 2: Personal + Referral</span>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="name" className="text-sm sm:text-base">Full Name</Label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 sm:h-5 sm:w-5 text-muted-foreground" />
                      <Input
                        id="name"
                        type="text"
                        placeholder="John Doe"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        className={`pl-10 sm:pl-11 h-12 sm:h-14 text-base bg-muted/50 border-border/50 focus:border-primary ${
                          getFieldError("name") ? "border-destructive" : ""
                        }`}
                        data-testid="signup-name-input"
                      />
                    </div>
                    {getFieldError("name") && (
                      <p className="text-xs text-destructive">{getFieldError("name")}</p>
                    )}
                  </div>

                  {signupStep === 2 && (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="phoneNumber" className="text-sm sm:text-base">Phone Number</Label>
                        <div className="relative">
                          <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                          <Input id="phoneNumber" value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} className="pl-10 h-12 sm:h-14" placeholder="+1 555 123 4567" />
                        </div>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="country" className="text-sm sm:text-base">Country</Label>
                          <div className="relative">
                            <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <Input id="country" value={country} onChange={(e) => setCountry(e.target.value)} className="pl-10 h-12 sm:h-14" placeholder="United States" />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="city" className="text-sm sm:text-base">City</Label>
                          <Input id="city" value={city} onChange={(e) => setCity(e.target.value)} className="h-12 sm:h-14" placeholder="New York" />
                        </div>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="referralCode" className="text-sm sm:text-base">Referral Code (Optional)</Label>
                          <button type="button" onClick={() => setShowReferralHelp(true)} className="text-xs text-gold-400 hover:underline">Where do I find this?</button>
                        </div>
                        <div className="relative">
                          <Gift className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                          <Input id="referralCode" value={referralCode} onChange={(e) => setReferralCode(e.target.value.toUpperCase())} className={`pl-10 h-12 sm:h-14 ${getFieldError("referral_code") ? "border-destructive" : ""}`} placeholder="Enter valid code" />
                        </div>
                        {getFieldError("referral_code") && <p className="text-xs text-destructive">{getFieldError("referral_code")}</p>}
                      </div>
                    </>
                  )}
                </>
              )}

              <div className="space-y-2">
                <Label htmlFor="email" className="text-sm sm:text-base">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 sm:h-5 sm:w-5 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={`pl-10 sm:pl-11 h-12 sm:h-14 text-base bg-muted/50 border-border/50 focus:border-primary ${
                      getFieldError("email") ? "border-destructive" : ""
                    }`}
                    data-testid="auth-email-input"
                  />
                </div>
                {getFieldError("email") && (
                  <p className="text-xs text-destructive">{getFieldError("email")}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="text-sm sm:text-base">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 sm:h-5 sm:w-5 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={`pl-10 sm:pl-11 pr-12 h-12 sm:h-14 text-base bg-muted/50 border-border/50 focus:border-primary ${
                      getFieldError("password") ? "border-destructive" : ""
                    }`}
                    data-testid="auth-password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 min-h-[44px] min-w-[44px] flex items-center justify-center -mr-2"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4 sm:h-5 sm:w-5" /> : <Eye className="h-4 w-4 sm:h-5 sm:w-5" />}
                  </button>
                </div>
                {getFieldError("password") && (
                  <p className="text-xs text-destructive">{getFieldError("password")}</p>
                )}
                {!isLogin && !getFieldError("password") && password && (
                  <p className="text-xs text-muted-foreground">
                    ✓ Password meets security requirements
                  </p>
                )}
              </div>
              
              {isLogin && (
                <div className="flex justify-end">
                  <button 
                    type="button" 
                    className="text-sm text-gold-400 hover:text-gold-300 hover:underline min-h-[44px] px-2"
                  >
                    Forgot password?
                  </button>
                </div>
              )}
              
              <Button 
                type="submit" 
                size="lg" 
                className="w-full h-12 sm:h-14 text-base bg-gradient-to-r from-gold-500 to-gold-600 hover:from-gold-400 hover:to-gold-500 text-black font-semibold"
                disabled={isLoading}
                data-testid="auth-submit-button"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 sm:h-5 sm:w-5 mr-2 animate-spin" />
                    Please wait...
                  </>
                 ) : isLogin ? "Sign In" : signupStep === 1 ? "Continue" : "Create Account"}
              </Button>
            </form>
            
            <div className="mt-6 sm:mt-8 text-center">
              <p className="text-muted-foreground text-sm sm:text-base">
                {isLogin ? "Don't have an account?" : "Already have an account?"}
                {" "}
                <button
                  type="button"
                  onClick={() => { setIsLogin(!isLogin); setSignupStep(1); }}
                  className="text-gold-400 hover:text-gold-300 hover:underline font-medium min-h-[44px]"
                  data-testid="auth-toggle-mode"
                >
                  {isLogin ? "Sign up" : "Sign in"}
                </button>
              </p>
            </div>
            
            <p className="mt-6 sm:mt-8 text-xs text-center text-muted-foreground px-4">
              By continuing, you agree to our{" "}
              <a href="/terms" className="underline hover:text-gold-400">Terms of Service</a>
              {" "}and{" "}
              <a href="/privacy" className="underline hover:text-gold-400">Privacy Policy</a>
            </p>
          </div>
        </div>
      </div>


      <Dialog open={showReferralHelp} onOpenChange={setShowReferralHelp}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>About referral codes</DialogTitle>
            <DialogDescription>
              Ask your referrer for their unique CryptoVault code. Codes are 4-20 uppercase letters/numbers.
              If valid, it links both referrer and referee for rewards tracking.
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>

      {/* OTP Verification Modal */}
      <OTPVerificationModal
        isOpen={showOTPModal}
        onClose={() => setShowOTPModal(false)}
        email={pendingEmail}
        onVerify={async (code: string) => {
          try {
            await api.auth.verifyEmail(code);
            return true;
          } catch (error) {
            return false;
          }
        }}
        onResend={async () => {
          try {
            await api.auth.resendVerification(pendingEmail);
            toast({
              title: "Code resent",
              description: "A new verification code has been sent to your email.",
            });
            return true;
          } catch (error) {
            return false;
          }
        }}
        onSuccess={() => {
          setShowOTPModal(false);
          setShowRecommendedSetup(true);
        }}
      />

      {/* Recommended Setup Modal */}
      <RecommendedSetup
        isOpen={showRecommendedSetup}
        onClose={() => setShowRecommendedSetup(false)}
        userName={pendingUserName || name}
      />
    </div>
  );
};

export default Auth;
