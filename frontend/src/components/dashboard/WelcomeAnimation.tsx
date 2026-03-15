/**
 * WelcomeAnimation - First Login Premium Animation
 * Shows animated logo with welcome message for first-time users
 */

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, Sparkles } from 'lucide-react';

interface WelcomeAnimationProps {
  userName: string;
  onComplete: () => void;
  duration?: number;
}

const WelcomeAnimation = ({
  userName,
  onComplete,
  duration = 3000
}: WelcomeAnimationProps) => {
  const [show, setShow] = useState(true);
  const [phase, setPhase] = useState<'logo' | 'welcome' | 'fade'>('logo');

  useEffect(() => {
    // Phase 1: Logo animation (0-1.5s)
    const welcomeTimer = setTimeout(() => setPhase('welcome'), 1500);

    // Phase 2: Welcome message (1.5-4s)
    const fadeTimer = setTimeout(() => setPhase('fade'), duration - 1000);

    // Phase 3: Fade out (4-5s)
    const completeTimer = setTimeout(() => {
      setShow(false);
      onComplete();
    }, duration);

    return () => {
      clearTimeout(welcomeTimer);
      clearTimeout(fadeTimer);
      clearTimeout(completeTimer);
    };
  }, [duration, onComplete]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8, ease: 'easeInOut' }}
          className="fixed inset-0 z-[100] bg-[#0a0a0f] flex flex-col items-center justify-center overflow-hidden"
        >
          {/* Background Effects */}
          <div className="absolute inset-0">
            {/* Radial gradient */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(251,191,36,0.08)_0%,transparent_60%)]" />

            {/* Animated particles */}
            {[...Array(30)].map((_, i) => (
              <motion.div
                key={i}
                className="absolute w-1 h-1 bg-gold-400/30 rounded-full"
                initial={{
                  x: Math.random() * window.innerWidth,
                  y: Math.random() * window.innerHeight,
                  scale: 0,
                }}
                animate={{
                  y: [null, Math.random() * -200 - 100],
                  scale: [0, 1, 0],
                  opacity: [0, 0.8, 0],
                }}
                transition={{
                  duration: 3 + Math.random() * 2,
                  delay: Math.random() * 2,
                  repeat: Infinity,
                  repeatDelay: Math.random(),
                }}
              />
            ))}

            {/* Glow rings */}
            <motion.div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full border border-gold-500/10"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1.5, opacity: [0, 0.3, 0] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: 'easeOut' }}
            />
            <motion.div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] rounded-full border border-gold-500/20"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1.3, opacity: [0, 0.4, 0] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeOut', delay: 0.3 }}
            />
          </div>

          {/* Main Content */}
          <div className="relative z-10 flex flex-col items-center">
            {/* Shield Logo with Glow */}
            <motion.div
              className="relative"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', damping: 15, stiffness: 100, duration: 1 }}
            >
              {/* Outer glow */}
              <motion.div
                className="absolute inset-0 bg-gold-400/30 blur-3xl rounded-full"
                animate={{
                  scale: [1, 1.2, 1],
                  opacity: [0.3, 0.6, 0.3],
                }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              />

              {/* Logo container */}
              <div className="relative p-6">
                <motion.img
                  src="/logo.svg"
                  alt="CryptoVault"
                  className="h-24 w-24 sm:h-32 sm:w-32 object-contain"
                  animate={{
                    filter: [
                      'drop-shadow(0 0 20px rgba(251,191,36,0.4))',
                      'drop-shadow(0 0 40px rgba(251,191,36,0.6))',
                      'drop-shadow(0 0 20px rgba(251,191,36,0.4))',
                    ],
                  }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                />
              </div>
            </motion.div>

            {/* Welcome Text - Phase 2 */}
            <AnimatePresence mode="wait">
              {phase === 'logo' && (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="mt-8 flex flex-col items-center"
                >
                  <h1 className="font-display text-3xl sm:text-4xl font-bold mb-2">
                    Crypto<span className="text-gold-400">Vault</span>
                  </h1>
                  <div className="flex items-center gap-2 text-gray-400">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    >
                      <Sparkles className="h-4 w-4 text-gold-400" />
                    </motion.div>
                    <span className="text-sm">Initializing secure environment...</span>
                  </div>
                </motion.div>
              )}

              {(phase === 'welcome' || phase === 'fade') && (
                <motion.div
                  key="welcome"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: phase === 'fade' ? 0.5 : 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="mt-8 flex flex-col items-center text-center"
                >
                  <motion.h1
                    className="font-display text-3xl sm:text-4xl font-bold mb-3"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.2 }}
                  >
                    Welcome, <span className="text-gold-400">{userName}</span>!
                  </motion.h1>

                  <motion.p
                    className="text-gray-400 text-lg mb-6 max-w-md"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.4 }}
                  >
                    Your institutional-grade crypto vault is ready.
                  </motion.p>

                  <motion.div
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-500/10 rounded-full border border-emerald-500/20"
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.6 }}
                  >
                    <Shield className="h-4 w-4 text-emerald-400" />
                    <span className="text-sm text-emerald-400 font-medium">
                      Your assets are protected with military-grade encryption
                    </span>
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Progress bar */}
            <motion.div
              className="absolute bottom-0 left-0 right-0 h-0.5 bg-white/5 mt-12"
              style={{ marginTop: 48 }}
            >
              <motion.div
                className="h-full bg-gradient-to-r from-gold-400 to-gold-600"
                initial={{ width: '0%' }}
                animate={{ width: '100%' }}
                transition={{ duration: duration / 1000, ease: 'linear' }}
              />
            </motion.div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default WelcomeAnimation;
