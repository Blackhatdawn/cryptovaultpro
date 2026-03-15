/**
 * Onboarding Loading Overlay Component
 * Full-screen loading with logo animation
 */
import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface OnboardingLoaderProps {
  isLoading: boolean;
  minDisplayTime?: number;
}

const OnboardingLoader = ({ isLoading, minDisplayTime = 800 }: OnboardingLoaderProps) => {
  const [showLoader, setShowLoader] = useState(true);
  const [fadeOut, setFadeOut] = useState(false);
  const [hasMinTimeElapsed, setHasMinTimeElapsed] = useState(false);

  useEffect(() => {
    // Minimum display time
    const timer = setTimeout(() => {
      setHasMinTimeElapsed(true);
    }, minDisplayTime);

    return () => clearTimeout(timer);
  }, [minDisplayTime]);

  useEffect(() => {
    // Only hide when both loading is done AND min time has elapsed
    if (!isLoading && hasMinTimeElapsed) {
      setFadeOut(true);
      const hideTimer = setTimeout(() => {
        setShowLoader(false);
      }, 500);
      return () => clearTimeout(hideTimer);
    }
  }, [isLoading, hasMinTimeElapsed]);

  // Fallback: Force hide after max 2.5 seconds regardless of loading state
  useEffect(() => {
    const maxTimer = setTimeout(() => {
      setFadeOut(true);
      setTimeout(() => setShowLoader(false), 300);
    }, 2500);
    
    return () => clearTimeout(maxTimer);
  }, []);

  if (!showLoader) return null;

  return (
    <div
      className={cn(
        'fixed inset-0 z-[100] bg-background flex flex-col items-center justify-center',
        'transition-opacity duration-500',
        fadeOut && 'opacity-0 pointer-events-none'
      )}
      data-testid="onboarding-loader"
    >
      {/* Background gradient */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-gold-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-gold-600/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      {/* Logo with pulse animation */}
      <div className="relative z-10 flex flex-col items-center">
        <div className="relative">
          {/* Glow effect */}
          <div className="absolute inset-0 bg-gold-500/30 blur-2xl rounded-full animate-pulse" />
          
          {/* Logo */}
          <img 
            src="/logo.svg" 
            alt="CryptoVault" 
            className="h-20 w-20 sm:h-24 sm:w-24 object-contain relative z-10 animate-logo-pulse"
          />
        </div>

        {/* Brand name */}
        <h1 className="font-display text-2xl sm:text-3xl font-bold mt-6 mb-2">
          Crypto<span className="text-gold-400">Vault</span>
        </h1>
        
        <p className="text-sm text-muted-foreground mb-8">Secure Digital Custody</p>

        {/* Loading spinner */}
        <div className="relative">
          <div className="h-10 w-10 rounded-full border-2 border-gold-500/20 border-t-gold-500 animate-spin" />
        </div>

        {/* Loading text */}
        <p className="mt-6 text-sm text-muted-foreground animate-pulse">
          Currently Initializing secure connection...
        </p>
      </div>

      <style>{`
        @keyframes logo-pulse {
          0%, 100% { 
            transform: scale(1);
            filter: drop-shadow(0 0 20px rgba(245, 158, 11, 0.3));
          }
          50% { 
            transform: scale(1.05);
            filter: drop-shadow(0 0 40px rgba(245, 158, 11, 0.5));
          }
        }
        .animate-logo-pulse {
          animation: logo-pulse 2s ease-in-out infinite;
        }
      `}</style>
    </div>
  );
};

export default OnboardingLoader;
