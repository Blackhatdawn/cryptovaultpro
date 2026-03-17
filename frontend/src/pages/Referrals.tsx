/**
 * Referrals Page - Tiered Referral Program
 * Bronze -> Silver -> Gold -> Platinum with increasing rewards
 */
import { useState } from 'react';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import {
  Gift,
  Users,
  Copy,
  Check,
  TrendingUp,
  Award,
  Share2,
  Twitter,
  MessageCircle,
  Mail,
  Link as LinkIcon,
  ChevronRight,
  Star,
  Crown,
  Trophy,
  Zap
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { resolveAppUrl } from '@/lib/runtimeConfig';
import { cn } from '@/lib/utils';
import apiClient from '@/lib/apiClient';
import DashboardCard from '@/components/dashboard/DashboardCard';

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } }
};

const tierIcons: Record<string, any> = {
  Bronze: Star,
  Silver: Award,
  Gold: Crown,
  Platinum: Trophy,
};

const Referrals = () => {
  const { user } = useAuth();
  const [copied, setCopied] = useState(false);

  const { data: summary } = useQuery({
    queryKey: ['referral-summary'],
    queryFn: async () => apiClient.get('/api/referrals/summary'),
  });

  const { data: referralsData } = useQuery({
    queryKey: ['referrals-list'],
    queryFn: async () => apiClient.get('/api/referrals'),
  });

  const referrals = referralsData?.referrals || [];
  const referralCode = summary?.referralCode || ('CV' + (user?.id?.slice(-6)?.toUpperCase() || 'VAULT'));
  const referralLink = summary?.referralLink || `${resolveAppUrl()}/auth?ref=${referralCode}`;

  const tier = summary?.tier || { name: 'Bronze', bonus: 10, color: '#CD7F32', nextTier: null };
  const allTiers = summary?.allTiers || [
    { name: 'Bronze', min_referrals: 0, bonus: 10, color: '#CD7F32' },
    { name: 'Silver', min_referrals: 5, bonus: 15, color: '#C0C0C0' },
    { name: 'Gold', min_referrals: 10, bonus: 20, color: '#FFD700' },
    { name: 'Platinum', min_referrals: 25, bonus: 30, color: '#E5E4E2' },
  ];

  const totalReferrals = summary?.totalReferrals ?? 0;
  const activeReferrals = summary?.activeReferrals ?? 0;
  const totalEarned = summary?.totalEarned ?? 0;

  const handleCopy = async (text: string, type: 'code' | 'link') => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success(`${type === 'code' ? 'Referral code' : 'Referral link'} copied!`);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleShare = (platform: string) => {
    const text = `Join me on CryptoVault! Use my referral code: ${referralCode} and we both get $${tier.bonus}!`;
    const encodedText = encodeURIComponent(text);
    const encodedLink = encodeURIComponent(referralLink);

    const urls: Record<string, string> = {
      twitter: `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedLink}`,
      telegram: `https://t.me/share/url?url=${encodedLink}&text=${encodedText}`,
      email: `mailto:?subject=Join CryptoVault&body=${encodedText}%0A%0A${encodedLink}`,
    };

    if (urls[platform]) window.open(urls[platform], '_blank');
  };

  const TierIcon = tierIcons[tier.name] || Star;

  return (
    <div className="space-y-6" data-testid="referrals-page">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-display font-bold text-white flex items-center gap-3">
          <Gift className="h-7 w-7 text-gold-400" />
          Referral Program
        </h1>
        <p className="text-gray-400 mt-1">
          Invite friends - you earn up to $30 per referral, they get $10 signup bonus
        </p>
      </div>

      {/* Tier Badge + Stats */}
      <motion.div variants={containerVariants} initial="hidden" animate="show" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Current Tier Card */}
        <motion.div variants={itemVariants}>
          <DashboardCard glowColor="gold">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-xl" style={{ backgroundColor: `${tier.color}20` }}>
                <TierIcon className="h-6 w-6" style={{ color: tier.color }} />
              </div>
              <div>
                <p className="text-xs text-gray-400">Your Tier</p>
                <p className="text-xl font-bold" style={{ color: tier.color }} data-testid="current-tier">
                  {tier.name}
                </p>
                <p className="text-xs text-gray-500">${tier.bonus}/referral</p>
              </div>
            </div>
          </DashboardCard>
        </motion.div>

        <motion.div variants={itemVariants}>
          <DashboardCard>
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-500/10 rounded-xl">
                <Users className="h-6 w-6 text-blue-400" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Total Referrals</p>
                <p className="text-2xl font-bold text-white" data-testid="total-referrals">{totalReferrals}</p>
              </div>
            </div>
          </DashboardCard>
        </motion.div>

        <motion.div variants={itemVariants}>
          <DashboardCard glowColor="emerald">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-emerald-500/10 rounded-xl">
                <TrendingUp className="h-6 w-6 text-emerald-400" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Total Earned</p>
                <p className="text-2xl font-bold text-emerald-400" data-testid="total-earned">${totalEarned.toFixed(2)}</p>
              </div>
            </div>
          </DashboardCard>
        </motion.div>

        <motion.div variants={itemVariants}>
          <DashboardCard>
            <div className="flex items-center gap-3">
              <div className="p-3 bg-violet-500/10 rounded-xl">
                <Zap className="h-6 w-6 text-violet-400" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Active</p>
                <p className="text-2xl font-bold text-white">{activeReferrals}</p>
              </div>
            </div>
          </DashboardCard>
        </motion.div>
      </motion.div>

      {/* Tier Progress */}
      {tier.nextTier && (
        <DashboardCard title="Tier Progress" icon={<ChevronRight className="h-5 w-5" />}>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium" style={{ color: tier.color }}>{tier.name}</span>
              <span className="text-gray-400">
                {tier.nextTier.referrals_needed} more referral{tier.nextTier.referrals_needed !== 1 ? 's' : ''} to{' '}
                <span className="font-medium" style={{ color: tier.nextTier.color }}>{tier.nextTier.name}</span>
              </span>
            </div>
            <div className="w-full h-3 bg-white/5 rounded-full overflow-hidden">
              {(() => {
                const currentTierIdx = allTiers.findIndex((t: any) => t.name === tier.name);
                const nextTierIdx = allTiers.findIndex((t: any) => t.name === tier.nextTier?.name);
                const currentMin = allTiers[currentTierIdx]?.min_referrals || 0;
                const nextMin = allTiers[nextTierIdx]?.min_referrals || 1;
                const progress = Math.min(100, ((totalReferrals - currentMin) / (nextMin - currentMin)) * 100);
                return (
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${progress}%`, backgroundColor: tier.color }}
                  />
                );
              })()}
            </div>
          </div>
        </DashboardCard>
      )}

      {/* Tier Roadmap */}
      <DashboardCard title="Tier Rewards" icon={<Trophy className="h-5 w-5" />}>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {allTiers.map((t: any) => {
            const isActive = t.name === tier.name;
            const isUnlocked = totalReferrals >= t.min_referrals;
            const Icon = tierIcons[t.name] || Star;
            return (
              <div
                key={t.name}
                className={cn(
                  'relative p-4 rounded-xl border text-center transition-all',
                  isActive
                    ? 'border-opacity-60 bg-opacity-10 ring-1'
                    : isUnlocked
                    ? 'border-white/10 bg-white/5'
                    : 'border-white/5 bg-white/[0.02] opacity-60'
                )}
                style={{
                  borderColor: isActive ? t.color : undefined,
                  backgroundColor: isActive ? `${t.color}10` : undefined,
                  ...(isActive ? { boxShadow: `0 0 20px ${t.color}15` } : {}),
                }}
                data-testid={`tier-card-${t.name.toLowerCase()}`}
              >
                {isActive && (
                  <div className="absolute -top-2 left-1/2 -translate-x-1/2 px-2 py-0.5 text-[10px] font-bold rounded-full bg-white/10 text-white">
                    CURRENT
                  </div>
                )}
                <Icon className="h-8 w-8 mx-auto mb-2" style={{ color: t.color }} />
                <p className="font-bold text-sm" style={{ color: t.color }}>{t.name}</p>
                <p className="text-lg font-bold text-white mt-1">${t.bonus}</p>
                <p className="text-[10px] text-gray-500 mt-1">per referral</p>
                <p className="text-[10px] text-gray-600 mt-0.5">
                  {t.min_referrals === 0 ? 'Starting tier' : `${t.min_referrals}+ referrals`}
                </p>
              </div>
            );
          })}
        </div>
      </DashboardCard>

      {/* Referral Code + How It Works */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DashboardCard title="Your Referral Code" icon={<LinkIcon className="h-5 w-5" />} glowColor="gold">
          <div className="space-y-4">
            <div className="p-4 bg-gradient-to-r from-gold-500/10 to-gold-600/10 rounded-xl border border-gold-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-gray-400 mb-1">Your Code</p>
                  <p className="text-3xl font-bold font-mono text-gold-400" data-testid="referral-code">{referralCode}</p>
                </div>
                <button
                  onClick={() => handleCopy(referralCode, 'code')}
                  className="p-3 bg-gold-500/20 hover:bg-gold-500/30 rounded-lg transition-colors"
                  data-testid="copy-code-btn"
                >
                  {copied ? <Check className="h-5 w-5 text-emerald-400" /> : <Copy className="h-5 w-5 text-gold-400" />}
                </button>
              </div>
            </div>

            <div className="p-3 bg-white/5 rounded-xl">
              <p className="text-xs text-gray-400 mb-2">Referral Link</p>
              <div className="flex items-center gap-2">
                <code className="text-sm text-gray-300 truncate flex-1 font-mono">{referralLink}</code>
                <button
                  onClick={() => handleCopy(referralLink, 'link')}
                  className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
                  data-testid="copy-link-btn"
                >
                  <Copy className="h-4 w-4 text-gray-400" />
                </button>
              </div>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => handleShare('twitter')} className="flex-1 border-white/10 hover:bg-white/5" data-testid="share-twitter">
                <Twitter className="h-4 w-4 mr-2" /> Twitter
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleShare('telegram')} className="flex-1 border-white/10 hover:bg-white/5" data-testid="share-telegram">
                <MessageCircle className="h-4 w-4 mr-2" /> Telegram
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleShare('email')} className="flex-1 border-white/10 hover:bg-white/5" data-testid="share-email">
                <Mail className="h-4 w-4 mr-2" /> Email
              </Button>
            </div>
          </div>
        </DashboardCard>

        {/* How It Works */}
        <DashboardCard title="How It Works" icon={<Gift className="h-5 w-5" />}>
          <div className="space-y-4">
            <div className="flex items-start gap-4 p-3 bg-white/5 rounded-xl">
              <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center text-gold-400 font-bold flex-shrink-0">1</div>
              <div>
                <h4 className="font-medium text-white">Share Your Code</h4>
                <p className="text-sm text-gray-400 mt-1">Share your unique referral code or link with friends</p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-3 bg-white/5 rounded-xl">
              <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center text-gold-400 font-bold flex-shrink-0">2</div>
              <div>
                <h4 className="font-medium text-white">Friends Sign Up</h4>
                <p className="text-sm text-gray-400 mt-1">They create an account using your referral code</p>
              </div>
            </div>
            <div className="flex items-start gap-4 p-3 bg-white/5 rounded-xl">
              <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center text-gold-400 font-bold flex-shrink-0">3</div>
              <div>
                <h4 className="font-medium text-white">Both Get Rewarded</h4>
                <p className="text-sm text-gray-400 mt-1">
                  They get $10, you get <span className="font-bold" style={{ color: tier.color }}>${tier.bonus}</span> ({tier.name} tier). Level up for more!
                </p>
              </div>
            </div>
          </div>
        </DashboardCard>
      </div>

      {/* Referrals List */}
      <DashboardCard title="Your Referrals" icon={<Users className="h-5 w-5" />}>
        {referrals.length === 0 ? (
          <div className="text-center py-12">
            <div className="p-4 bg-white/5 rounded-full w-fit mx-auto mb-4">
              <Users className="h-8 w-8 text-gray-500" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">No referrals yet</h3>
            <p className="text-gray-400">Share your referral code to start earning</p>
          </div>
        ) : (
          <div className="space-y-2" data-testid="referrals-list">
            <div className="hidden sm:grid grid-cols-5 gap-4 px-4 py-2 text-xs text-gray-500 uppercase tracking-wider">
              <div>User</div>
              <div>Status</div>
              <div>Tier</div>
              <div>Earned</div>
              <div>Date</div>
            </div>
            {referrals.map((referral: any) => (
              <div
                key={referral.id}
                className="grid grid-cols-2 sm:grid-cols-5 gap-4 px-4 py-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors"
                data-testid="referral-row"
              >
                <div className="font-mono text-sm text-white">{referral.email}</div>
                <div>
                  <span className={cn(
                    'px-2 py-0.5 text-xs font-medium rounded-full',
                    referral.status === 'active' || referral.status === 'qualified'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-yellow-500/10 text-yellow-400'
                  )}>
                    {referral.status}
                  </span>
                </div>
                <div className="text-sm font-medium" style={{ color: allTiers.find((t: any) => t.name === referral.tier)?.color || '#CD7F32' }}>
                  {referral.tier || 'Bronze'}
                </div>
                <div className="text-emerald-400 font-semibold">
                  ${(referral.reward ?? referral.earned ?? 0).toFixed(2)}
                </div>
                <div className="text-gray-400 text-sm">
                  {new Date(referral.date).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </DashboardCard>
    </div>
  );
};

export default Referrals;
