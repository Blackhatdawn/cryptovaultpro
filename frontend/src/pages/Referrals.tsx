/**
 * Referrals Page - Dashboard Version
 * Premium referral program management
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
  ChevronRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { resolveAppUrl } from '@/lib/runtimeConfig';
import { cn } from '@/lib/utils';
import apiClient from '@/lib/apiClient';
import DashboardCard from '@/components/dashboard/DashboardCard';

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4 } }
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

  const handleCopy = async (text: string, type: 'code' | 'link') => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success(`${type === 'code' ? 'Referral code' : 'Referral link'} copied!`);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleShare = (platform: string) => {
    const text = `Join me on CryptoVault - the most secure crypto trading platform! Use my referral code: ${referralCode}`;
    const encodedText = encodeURIComponent(text);
    const encodedLink = encodeURIComponent(referralLink);

    const urls: Record<string, string> = {
      twitter: `https://twitter.com/intent/tweet?text=${encodedText}&url=${encodedLink}`,
      telegram: `https://t.me/share/url?url=${encodedLink}&text=${encodedText}`,
      email: `mailto:?subject=Join CryptoVault&body=${encodedText}%0A%0A${encodedLink}`,
    };

    if (urls[platform]) {
      window.open(urls[platform], '_blank');
    }
  };

  // Stats
  const totalReferrals = summary?.totalReferrals ?? referrals.length;
  const activeReferrals = summary?.activeReferrals ?? referrals.filter(r => r.status === 'qualified' || r.status === 'active').length;
  const totalEarned = summary?.totalEarned ?? referrals.reduce((sum: number, r: any) => sum + (r.earned || 0), 0);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-display font-bold text-white flex items-center gap-3">
          <Gift className="h-7 w-7 text-gold-400" />
          Referral Program
        </h1>
        <p className="text-gray-400 mt-1">
          Invite friends and you both get $10 credited to your wallet
        </p>
      </div>

      {/* Stats Cards */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <motion.div variants={itemVariants}>
          <DashboardCard glowColor="gold">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-gold-500/10 rounded-xl">
                <Users className="h-6 w-6 text-gold-400" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Total Referrals</p>
                <p className="text-2xl font-bold text-white">{totalReferrals}</p>
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
                <p className="text-sm text-gray-400">Active</p>
                <p className="text-2xl font-bold text-white">{activeReferrals}</p>
              </div>
            </div>
          </DashboardCard>
        </motion.div>

        <motion.div variants={itemVariants}>
          <DashboardCard glowColor="violet">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-violet-500/10 rounded-xl">
                <Award className="h-6 w-6 text-violet-400" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Total Earned</p>
                <p className="text-2xl font-bold text-emerald-400">${totalEarned.toFixed(2)}</p>
              </div>
            </div>
          </DashboardCard>
        </motion.div>

        <motion.div variants={itemVariants}>
          <DashboardCard>
            <div className="flex items-center gap-3">
              <div className="p-3 bg-blue-500/10 rounded-xl">
                <Gift className="h-6 w-6 text-blue-400" />
              </div>
              <div>
                <p className="text-sm text-gray-400">Bonus Per Referral</p>
                <p className="text-2xl font-bold text-white">$10</p>
              </div>
            </div>
          </DashboardCard>
        </motion.div>
      </motion.div>

      {/* Referral Code Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DashboardCard title="Your Referral Code" icon={<LinkIcon className="h-5 w-5" />} glowColor="gold">
          <div className="space-y-4">
            {/* Code Display */}
            <div className="p-4 bg-gradient-to-r from-gold-500/10 to-gold-600/10 rounded-xl border border-gold-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-gray-400 mb-1">Your Code</p>
                  <p className="text-3xl font-bold font-mono text-gold-400">{referralCode}</p>
                </div>
                <button
                  onClick={() => handleCopy(referralCode, 'code')}
                  className="p-3 bg-gold-500/20 hover:bg-gold-500/30 rounded-lg transition-colors"
                >
                  {copied ? (
                    <Check className="h-5 w-5 text-emerald-400" />
                  ) : (
                    <Copy className="h-5 w-5 text-gold-400" />
                  )}
                </button>
              </div>
            </div>

            {/* Referral Link */}
            <div className="space-y-2">
              <p className="text-sm text-gray-400">Or share your referral link:</p>
              <div className="flex gap-2">
                <Input
                  value={referralLink}
                  readOnly
                  className="bg-white/5 border-white/10 font-mono text-sm"
                />
                <Button
                  variant="outline"
                  onClick={() => handleCopy(referralLink, 'link')}
                  className="border-white/10 hover:bg-white/5 px-4"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Share Buttons */}
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleShare('twitter')}
                className="flex-1 border-white/10 hover:bg-[#1DA1F2]/10 hover:border-[#1DA1F2]/30"
              >
                <Twitter className="h-4 w-4 mr-2" />
                Twitter
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleShare('telegram')}
                className="flex-1 border-white/10 hover:bg-[#0088cc]/10 hover:border-[#0088cc]/30"
              >
                <MessageCircle className="h-4 w-4 mr-2" />
                Telegram
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleShare('email')}
                className="flex-1 border-white/10 hover:bg-white/5"
              >
                <Mail className="h-4 w-4 mr-2" />
                Email
              </Button>
            </div>
          </div>
        </DashboardCard>

        {/* How It Works */}
        <DashboardCard title="How It Works" icon={<Gift className="h-5 w-5" />}>
          <div className="space-y-4">
            <div className="flex items-start gap-4 p-3 bg-white/5 rounded-xl">
              <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center text-gold-400 font-bold flex-shrink-0">
                1
              </div>
              <div>
                <h4 className="font-medium text-white">Share Your Code</h4>
                <p className="text-sm text-gray-400 mt-1">
                  Share your unique referral code or link with friends
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-3 bg-white/5 rounded-xl">
              <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center text-gold-400 font-bold flex-shrink-0">
                2
              </div>
              <div>
                <h4 className="font-medium text-white">Friends Sign Up</h4>
                <p className="text-sm text-gray-400 mt-1">
                  They create an account using your referral code
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-3 bg-white/5 rounded-xl">
              <div className="w-8 h-8 rounded-full bg-gold-500/20 flex items-center justify-center text-gold-400 font-bold flex-shrink-0">
                3
              </div>
              <div>
                <h4 className="font-medium text-white">Both Get $10</h4>
                <p className="text-sm text-gray-400 mt-1">
                  You both receive $10 credited directly to your wallets!
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
          <div className="space-y-2">
            {/* Header */}
            <div className="hidden sm:grid grid-cols-4 gap-4 px-4 py-2 text-xs text-gray-500 uppercase tracking-wider">
              <div>User</div>
              <div>Status</div>
              <div>Earned</div>
              <div>Date</div>
            </div>
            
            {/* Rows */}
            {referrals.map((referral: any) => (
              <div
                key={referral.id}
                className="grid grid-cols-2 sm:grid-cols-4 gap-4 px-4 py-3 bg-white/5 rounded-xl hover:bg-white/10 transition-colors"
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
