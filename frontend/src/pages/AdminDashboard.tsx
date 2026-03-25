/**
 * Admin Dashboard - Enterprise Control Panel
 * Real-time monitoring with full user management and system controls
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import {
  Users, Activity, DollarSign, Bell, Search, Shield, RefreshCw, TrendingUp, TrendingDown,
  MoreHorizontal, Ban, Eye, Edit, LogOut, Home, Settings, BarChart3, Wallet, Send,
  AlertTriangle, CheckCircle, XCircle, Clock, Server, Database, Wifi, Power,
  UserCheck, UserX, MessageSquare, Download, Filter, ChevronLeft, ChevronRight
} from 'lucide-react';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { Line, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler, ArcElement
} from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler, ArcElement);

// Types
interface AdminData {
  id: string;
  email: string;
  name: string;
  role: string;
  permissions: string[];
}

interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  is_suspended: boolean;
  email_verified: boolean;
  wallet_balance: Record<string, number>;
  created_at: string;
  last_login?: string;
}

interface DashboardStats {
  users: {
    total: number;
    active: number;
    verified: number;
    suspended: number;
    new_today: number;
    new_week: number;
    growth_rate: number;
  };
  transactions: {
    total: number;
    today: number;
    volume_today: number;
  };
  pending: {
    withdrawals: number;
    deposits: number;
    total: number;
  };
  system: {
    active_connections: number;
    server_time: string;
    environment: string;
  };
}

interface SystemHealth {
  status: string;
  timestamp: string;
  services: Record<string, { status: string; error?: string; active_connections?: number }>;
}

const AdminDashboard = () => {
  const navigate = useNavigate();
  
  // Auth state - AdminRoute wrapper handles redirect, we just load data
  const [admin, setAdmin] = useState<AdminData | null>(null);
  const isAuthenticated = Boolean(admin);
  
  // Dashboard state
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [totalUsers, setTotalUsers] = useState(0);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [userFilter, setUserFilter] = useState('all');
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'transactions' | 'withdrawals' | 'system' | 'broadcast'>('overview');
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize] = useState(20);
  
  // Modals
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [userActionModal, setUserActionModal] = useState(false);
  const [userAction, setUserAction] = useState<string>('');
  const [actionReason, setActionReason] = useState('');
  const [broadcastModal, setBroadcastModal] = useState(false);
  const [broadcastMessage, setBroadcastMessage] = useState({ title: '', message: '', type: 'info' });
  const [walletAdjustModal, setWalletAdjustModal] = useState(false);
  const [walletAdjust, setWalletAdjust] = useState({ currency: 'USD', amount: 0, reason: '' });

  // Withdrawal approvals state
  const [pendingWithdrawals, setPendingWithdrawals] = useState<any[]>([]);
  const [withdrawalStats, setWithdrawalStats] = useState<any>(null);
  const [withdrawalLoading, setWithdrawalLoading] = useState(false);
  const [withdrawalRefreshInterval, setWithdrawalRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  // Load admin data from sessionStorage (AdminRoute already verified auth)
  useEffect(() => {
    const adminData = sessionStorage.getItem('adminData');
    if (adminData) {
      try {
        setAdmin(JSON.parse(adminData));
      } catch {
        // AdminRoute will handle redirect if needed
      }
    }
  }, []);

  // Helper to get CSRF token from cookie
  const getCSRFToken = useCallback((): string | null => {
    const cookies = document.cookie.split(';');
    for (const cookie of cookies) {
      const trimmed = cookie.trim();
      if (trimmed.startsWith('csrf_token=')) {
        return trimmed.substring('csrf_token='.length);
      }
    }
    return null;
  }, []);

  // API call helper
  const adminFetch = useCallback(async (endpoint: string, options: RequestInit = {}) => {
    const csrfToken = getCSRFToken();
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
    const response = await fetch(`${baseUrl}/api/admin${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
        ...options.headers,
      },
      credentials: 'include',
    });
    
    if (response.status === 401) {
      sessionStorage.removeItem('adminData');
      navigate('/admin/login');
      throw new Error('Session expired');
    }
    
    return response;
  }, [navigate, getCSRFToken]);

  // Fetch dashboard data
  const fetchDashboardData = useCallback(async () => {
    if (!isAuthenticated) return;
    
    try {
      const [statsRes, healthRes] = await Promise.all([
        adminFetch('/dashboard/stats'),
        adminFetch('/system/health'),
      ]);
      
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
      
      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setSystemHealth(healthData);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, adminFetch]);

  // Fetch users
  const fetchUsers = useCallback(async () => {
    if (!isAuthenticated) return;
    
    try {
      const params = new URLSearchParams({
        skip: String(currentPage * pageSize),
        limit: String(pageSize),
        ...(searchQuery && { search: searchQuery }),
        ...(userFilter !== 'all' && { status: userFilter }),
      });
      
      const response = await adminFetch(`/users?${params}`);
      if (response.ok) {
        const data = await response.json();
        setUsers(data.users);
        setTotalUsers(data.total);
      }
    } catch (error) {
      console.error('Failed to fetch users:', error);
    }
  }, [isAuthenticated, currentPage, pageSize, searchQuery, userFilter, adminFetch]);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  useEffect(() => {
    if (activeTab === 'users') {
      fetchUsers();
    }
  }, [activeTab, fetchUsers]);

  // Handle user action
  const handleUserAction = async () => {
    if (!selectedUser || !userAction) return;
    
    try {
      const response = await adminFetch(`/users/${selectedUser.id}/action`, {
        method: 'POST',
        body: JSON.stringify({ action: userAction, reason: actionReason }),
      });
      
      if (response.ok) {
        toast.success(`Successfully ${userAction}ed user`);
        setUserActionModal(false);
        setSelectedUser(null);
        setUserAction('');
        setActionReason('');
        fetchUsers();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Action failed');
      }
    } catch (error) {
      toast.error('Failed to perform action');
    }
  };

  // Handle wallet adjustment
  const handleWalletAdjust = async () => {
    if (!selectedUser) return;
    
    try {
      const response = await adminFetch('/wallets/adjust', {
        method: 'POST',
        body: JSON.stringify({
          user_id: selectedUser.id,
          currency: walletAdjust.currency,
          amount: walletAdjust.amount,
          reason: walletAdjust.reason,
        }),
      });
      
      if (response.ok) {
        const result = await response.json();
        toast.success(`Wallet adjusted: ${result.previous_balance} → ${result.new_balance}`);
        setWalletAdjustModal(false);
        setWalletAdjust({ currency: 'USD', amount: 0, reason: '' });
        fetchUsers();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Adjustment failed');
      }
    } catch (error) {
      toast.error('Failed to adjust wallet');
    }
  };

  // Handle broadcast
  const handleBroadcast = async () => {
    try {
      const response = await adminFetch('/system/broadcast', {
        method: 'POST',
        body: JSON.stringify(broadcastMessage),
      });
      
      if (response.ok) {
        toast.success('Broadcast sent successfully');
        setBroadcastModal(false);
        setBroadcastMessage({ title: '', message: '', type: 'info' });
      } else {
        toast.error('Failed to send broadcast');
      }
    } catch (error) {
      toast.error('Broadcast failed');
    }
  };

  // ============================================
  // WITHDRAWAL APPROVAL FUNCTIONS
  // ============================================

  const fetchPendingWithdrawals = useCallback(async () => {
    setWithdrawalLoading(true);
    try {
      const [wdRes, statsRes] = await Promise.all([
        adminFetch('/withdrawals/pending?limit=50'),
        adminFetch('/withdrawals/stats'),
      ]);
      if (wdRes.ok) {
        const data = await wdRes.json();
        setPendingWithdrawals(data.withdrawals || []);
      }
      if (statsRes.ok) {
        const data = await statsRes.json();
        setWithdrawalStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch withdrawals:', err);
    } finally {
      setWithdrawalLoading(false);
    }
  }, [adminFetch]);

  // Auto-refresh withdrawals every 15 seconds when tab is active
  useEffect(() => {
    if (activeTab === 'withdrawals') {
      fetchPendingWithdrawals();
      const interval = setInterval(fetchPendingWithdrawals, 15000);
      setWithdrawalRefreshInterval(interval);
      return () => clearInterval(interval);
    } else if (withdrawalRefreshInterval) {
      clearInterval(withdrawalRefreshInterval);
      setWithdrawalRefreshInterval(null);
    }
  }, [activeTab, fetchPendingWithdrawals]);

  const handleApproveWithdrawal = async (withdrawalId: string) => {
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const csrfToken = getCSRFToken();
      const response = await fetch(`${baseUrl}/api/wallet/withdraw/${withdrawalId}/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
        },
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        toast.success(`Withdrawal approved (${data.approvalCount}/${data.requiredApprovals})`);
        fetchPendingWithdrawals();
      } else {
        const err = await response.json();
        toast.error(err?.error?.message || err?.detail || 'Failed to approve');
      }
    } catch (error) {
      toast.error('Approval failed');
    }
  };

  const handleRejectWithdrawal = async (withdrawalId: string) => {
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
      const csrfToken = getCSRFToken();
      const response = await fetch(`${baseUrl}/api/wallet/withdraw/${withdrawalId}/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
        },
        credentials: 'include',
      });
      if (response.ok) {
        toast.success('Withdrawal rejected and user refunded');
        fetchPendingWithdrawals();
      } else {
        const err = await response.json();
        toast.error(err?.error?.message || err?.detail || 'Failed to reject');
      }
    } catch (error) {
      toast.error('Rejection failed');
    }
  };

  // Handle logout
  const handleLogout = async () => {
    try {
      await adminFetch('/logout', { method: 'POST' });
    } catch {
      // Continue with local logout even if API fails
    }
    sessionStorage.removeItem('adminData');
    navigate('/admin/login');
  };

  if (!isAuthenticated || isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-muted-foreground">Loading admin panel...</p>
        </div>
      </div>
    );
  }

  const totalPages = Math.ceil(totalUsers / pageSize);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Header */}
      <header className="border-b border-amber-500/20 bg-slate-900/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-red-600 flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div>
                <span className="font-display text-lg font-bold">Admin <span className="text-amber-400">Control Panel</span></span>
                <div className="text-xs text-muted-foreground">{admin?.role}</div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="border-emerald-500/50 text-emerald-400">
                <span className="w-2 h-2 bg-emerald-500 rounded-full mr-2 animate-pulse" />
                {stats?.system?.active_connections || 0} Online
              </Badge>
              <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
                <Home className="h-4 w-4 mr-2" /> Site
              </Button>
              <Button variant="ghost" size="sm" onClick={handleLogout} className="text-red-400 hover:text-red-300">
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden lg:block w-64 border-r border-amber-500/10 min-h-[calc(100vh-64px)] p-4 bg-slate-900/50">
          <nav className="space-y-1">
            {[
              { id: 'overview', label: 'Overview', icon: BarChart3 },
              { id: 'users', label: 'User Management', icon: Users },
              { id: 'withdrawals', label: 'Withdrawals', icon: Wallet },
              { id: 'transactions', label: 'Transactions', icon: Activity },
              { id: 'system', label: 'System Health', icon: Server },
              { id: 'broadcast', label: 'Broadcast', icon: MessageSquare },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id as any)}
                className={cn(
                  'w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-left',
                  activeTab === item.id
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    : 'text-muted-foreground hover:bg-slate-800 hover:text-white'
                )}
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </button>
            ))}
          </nav>
          
          <div className="mt-8 p-4 rounded-lg bg-slate-800/50 border border-slate-700/50">
            <div className="text-xs text-muted-foreground mb-2">Logged in as</div>
            <div className="font-medium">{admin?.name}</div>
            <div className="text-xs text-muted-foreground">{admin?.email}</div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          {/* Overview Tab */}
          {activeTab === 'overview' && stats && (
            <div className="space-y-6">
              {/* Stats Grid */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="bg-slate-900/50 border-amber-500/10">
                  <CardContent className="p-4 sm:p-6">
                    <div className="flex items-center justify-between mb-3">
                      <Users className="h-5 w-5 text-amber-400" />
                      <Badge className={cn('text-xs', stats.users.growth_rate >= 0 ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500')}>
                        {stats.users.growth_rate >= 0 ? '+' : ''}{stats.users.growth_rate}%
                      </Badge>
                    </div>
                    <div className="font-display text-2xl sm:text-3xl font-bold">{stats.users.total.toLocaleString()}</div>
                    <div className="text-xs sm:text-sm text-muted-foreground">Total Users</div>
                  </CardContent>
                </Card>

                <Card className="bg-slate-900/50 border-emerald-500/10">
                  <CardContent className="p-4 sm:p-6">
                    <div className="flex items-center justify-between mb-3">
                      <UserCheck className="h-5 w-5 text-emerald-400" />
                    </div>
                    <div className="font-display text-2xl sm:text-3xl font-bold">{stats.users.verified.toLocaleString()}</div>
                    <div className="text-xs sm:text-sm text-muted-foreground">Verified Users</div>
                  </CardContent>
                </Card>

                <Card className="bg-slate-900/50 border-amber-500/10">
                  <CardContent className="p-4 sm:p-6">
                    <div className="flex items-center justify-between mb-3">
                      <DollarSign className="h-5 w-5 text-amber-400" />
                    </div>
                    <div className="font-display text-2xl sm:text-3xl font-bold">${stats.transactions.volume_today.toLocaleString()}</div>
                    <div className="text-xs sm:text-sm text-muted-foreground">Today's Volume</div>
                  </CardContent>
                </Card>

                <Card className="bg-slate-900/50 border-orange-500/10">
                  <CardContent className="p-4 sm:p-6">
                    <div className="flex items-center justify-between mb-3">
                      <Clock className="h-5 w-5 text-orange-400" />
                    </div>
                    <div className="font-display text-2xl sm:text-3xl font-bold">{stats.pending.total}</div>
                    <div className="text-xs sm:text-sm text-muted-foreground">Pending Actions</div>
                  </CardContent>
                </Card>
              </div>

              {/* Quick Actions */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Button onClick={() => setActiveTab('users')} variant="outline" className="h-auto py-4 flex-col gap-2 border-slate-700 hover:border-amber-500/50">
                  <Users className="h-6 w-6 text-amber-400" />
                  <span>Manage Users</span>
                </Button>
                <Button onClick={() => setBroadcastModal(true)} variant="outline" className="h-auto py-4 flex-col gap-2 border-slate-700 hover:border-amber-500/50">
                  <Send className="h-6 w-6 text-amber-400" />
                  <span>Send Broadcast</span>
                </Button>
                <Button onClick={() => setActiveTab('system')} variant="outline" className="h-auto py-4 flex-col gap-2 border-slate-700 hover:border-amber-500/50">
                  <Server className="h-6 w-6 text-amber-400" />
                  <span>System Status</span>
                </Button>
                <Button onClick={fetchDashboardData} variant="outline" className="h-auto py-4 flex-col gap-2 border-slate-700 hover:border-amber-500/50">
                  <RefreshCw className="h-6 w-6 text-amber-400" />
                  <span>Refresh Data</span>
                </Button>
              </div>

              {/* Recent Activity */}
              <div className="grid lg:grid-cols-2 gap-6">
                <Card className="bg-slate-900/50 border-amber-500/10">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <TrendingUp className="h-5 w-5 text-amber-400" />
                      User Growth
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">New Today</span>
                        <span className="font-mono font-bold text-emerald-400">+{stats.users.new_today}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">New This Week</span>
                        <span className="font-mono font-bold text-emerald-400">+{stats.users.new_week}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Active Users</span>
                        <span className="font-mono font-bold">{stats.users.active}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Suspended</span>
                        <span className="font-mono font-bold text-red-400">{stats.users.suspended}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-slate-900/50 border-amber-500/10">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="h-5 w-5 text-amber-400" />
                      Transactions
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Total Transactions</span>
                        <span className="font-mono font-bold">{stats.transactions.total.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Today</span>
                        <span className="font-mono font-bold text-emerald-400">{stats.transactions.today}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Pending Withdrawals</span>
                        <span className="font-mono font-bold text-orange-400">{stats.pending.withdrawals}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Pending Deposits</span>
                        <span className="font-mono font-bold text-orange-400">{stats.pending.deposits}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* Users Tab */}
          {activeTab === 'users' && (
            <div className="space-y-4">
              {/* Filters */}
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by email or name..."
                    value={searchQuery}
                    onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(0); }}
                    className="pl-10 bg-slate-900/50 border-slate-700"
                  />
                </div>
                <Select value={userFilter} onValueChange={(v) => { setUserFilter(v); setCurrentPage(0); }}>
                  <SelectTrigger className="w-[180px] bg-slate-900/50 border-slate-700">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Users</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="verified">Verified</SelectItem>
                    <SelectItem value="unverified">Unverified</SelectItem>
                    <SelectItem value="suspended">Suspended</SelectItem>
                  </SelectContent>
                </Select>
                <Button onClick={fetchUsers} variant="outline" className="border-slate-700">
                  <RefreshCw className="h-4 w-4 mr-2" /> Refresh
                </Button>
              </div>

              {/* Users Table */}
              <Card className="bg-slate-900/50 border-amber-500/10 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-slate-700/50 bg-slate-800/30">
                        <th className="text-left p-4 text-sm font-medium text-muted-foreground">User</th>
                        <th className="text-left p-4 text-sm font-medium text-muted-foreground hidden sm:table-cell">Status</th>
                        <th className="text-right p-4 text-sm font-medium text-muted-foreground">Balance</th>
                        <th className="text-right p-4 text-sm font-medium text-muted-foreground hidden md:table-cell">Joined</th>
                        <th className="text-right p-4 text-sm font-medium text-muted-foreground">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((user) => (
                        <tr key={user.id} className="border-b border-slate-700/30 hover:bg-slate-800/50 transition-colors">
                          <td className="p-4">
                            <div className="flex items-center gap-3">
                              <div className="h-10 w-10 rounded-full bg-gradient-to-br from-amber-500/20 to-amber-600/20 flex items-center justify-center text-amber-400 font-bold">
                                {user.name?.charAt(0) || user.email.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <div className="font-medium text-sm">{user.name || 'No name'}</div>
                                <div className="text-xs text-muted-foreground">{user.email}</div>
                              </div>
                            </div>
                          </td>
                          <td className="p-4 hidden sm:table-cell">
                            <div className="flex gap-1">
                              {user.is_suspended ? (
                                <Badge className="bg-red-500/10 text-red-500">Suspended</Badge>
                              ) : user.email_verified ? (
                                <Badge className="bg-emerald-500/10 text-emerald-500">Verified</Badge>
                              ) : (
                                <Badge className="bg-amber-500/10 text-amber-500">Pending</Badge>
                              )}
                            </div>
                          </td>
                          <td className="p-4 text-right font-mono text-sm">
                            ${(user.wallet_balance?.USD || 0).toLocaleString()}
                          </td>
                          <td className="p-4 text-right text-sm text-muted-foreground hidden md:table-cell">
                            {user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}
                          </td>
                          <td className="p-4 text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm"><MoreHorizontal className="h-4 w-4" /></Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="bg-slate-900 border-slate-700">
                                <DropdownMenuItem onClick={() => { setSelectedUser(user); setUserAction('view'); }}>
                                  <Eye className="h-4 w-4 mr-2" /> View Details
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => { setSelectedUser(user); setWalletAdjustModal(true); }}>
                                  <Wallet className="h-4 w-4 mr-2" /> Adjust Wallet
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                {!user.email_verified && (
                                  <DropdownMenuItem onClick={() => { setSelectedUser(user); setUserAction('verify'); setUserActionModal(true); }}>
                                    <UserCheck className="h-4 w-4 mr-2" /> Verify Email
                                  </DropdownMenuItem>
                                )}
                                {user.is_suspended ? (
                                  <DropdownMenuItem onClick={() => { setSelectedUser(user); setUserAction('unsuspend'); setUserActionModal(true); }}>
                                    <CheckCircle className="h-4 w-4 mr-2 text-emerald-400" /> Unsuspend
                                  </DropdownMenuItem>
                                ) : (
                                  <DropdownMenuItem onClick={() => { setSelectedUser(user); setUserAction('suspend'); setUserActionModal(true); }} className="text-red-400">
                                    <Ban className="h-4 w-4 mr-2" /> Suspend
                                  </DropdownMenuItem>
                                )}
                                <DropdownMenuItem onClick={() => { setSelectedUser(user); setUserAction('force_logout'); setUserActionModal(true); }} className="text-orange-400">
                                  <Power className="h-4 w-4 mr-2" /> Force Logout
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                
                {/* Pagination */}
                <div className="flex items-center justify-between p-4 border-t border-slate-700/50">
                  <div className="text-sm text-muted-foreground">
                    Showing {currentPage * pageSize + 1}-{Math.min((currentPage + 1) * pageSize, totalUsers)} of {totalUsers}
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setCurrentPage(p => Math.max(0, p - 1))} disabled={currentPage === 0}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setCurrentPage(p => p + 1)} disabled={currentPage >= totalPages - 1}>
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* System Health Tab */}
          {activeTab === 'system' && systemHealth && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold">System Health</h2>
                <Badge className={cn(
                  'text-sm px-3 py-1',
                  systemHealth.status === 'healthy' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
                  systemHealth.status === 'degraded' ? 'bg-amber-500/10 text-amber-400 border-amber-500/30' :
                  'bg-red-500/10 text-red-400 border-red-500/30'
                )}>
                  {systemHealth.status === 'healthy' ? <CheckCircle className="h-4 w-4 mr-2" /> :
                   systemHealth.status === 'degraded' ? <AlertTriangle className="h-4 w-4 mr-2" /> :
                   <XCircle className="h-4 w-4 mr-2" />}
                  {systemHealth.status.toUpperCase()}
                </Badge>
              </div>

              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(systemHealth.services).map(([service, status]) => (
                  <Card key={service} className={cn(
                    'bg-slate-900/50',
                    status.status === 'healthy' ? 'border-emerald-500/20' :
                    status.status === 'degraded' ? 'border-amber-500/20' : 'border-red-500/20'
                  )}>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                          {service === 'mongodb' && <Database className="h-6 w-6 text-emerald-400" />}
                          {service === 'redis' && <Server className="h-6 w-6 text-red-400" />}
                          {service === 'socketio' && <Wifi className="h-6 w-6 text-blue-400" />}
                          {service === 'price_feed' && <Activity className="h-6 w-6 text-amber-400" />}
                          <span className="font-medium capitalize">{service.replace('_', ' ')}</span>
                        </div>
                        <div className={cn(
                          'w-3 h-3 rounded-full',
                          status.status === 'healthy' ? 'bg-emerald-500 animate-pulse' :
                          status.status === 'degraded' ? 'bg-amber-500' : 'bg-red-500'
                        )} />
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Status: <span className={cn(
                          status.status === 'healthy' ? 'text-emerald-400' :
                          status.status === 'degraded' ? 'text-amber-400' : 'text-red-400'
                        )}>{status.status}</span>
                      </div>
                      {status.active_connections !== undefined && (
                        <div className="text-sm text-muted-foreground mt-1">
                          Connections: <span className="text-white">{status.active_connections}</span>
                        </div>
                      )}
                      {status.error && (
                        <div className="text-xs text-red-400 mt-2">{status.error}</div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Card className="bg-slate-900/50 border-slate-700">
                <CardHeader>
                  <CardTitle>Server Information</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <div className="text-sm text-muted-foreground">Server Time</div>
                      <div className="font-mono">{new Date(systemHealth.timestamp).toLocaleString()}</div>
                    </div>
                    <div>
                      <div className="text-sm text-muted-foreground">Environment</div>
                      <div className="font-mono">{stats?.system?.environment || 'production'}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}


          {/* Withdrawal Approvals Tab */}
          {activeTab === 'withdrawals' && (
            <div className="space-y-6" data-testid="withdrawal-approvals-tab">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold">Withdrawal Approvals</h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchPendingWithdrawals}
                  disabled={withdrawalLoading}
                  data-testid="refresh-withdrawals-btn"
                  className="border-amber-500/30 hover:border-amber-500"
                >
                  <RefreshCw className={cn("h-4 w-4 mr-2", withdrawalLoading && "animate-spin")} />
                  Refresh
                </Button>
              </div>

              {/* Stats Cards */}
              {withdrawalStats && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <Card className="bg-slate-900/50 border-amber-500/10">
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-amber-400">{withdrawalStats.pending + withdrawalStats.pending_approval}</div>
                      <div className="text-xs text-muted-foreground mt-1">Pending</div>
                    </CardContent>
                  </Card>
                  <Card className="bg-slate-900/50 border-red-500/10">
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-red-400">{withdrawalStats.high_value_count}</div>
                      <div className="text-xs text-muted-foreground mt-1">High Value</div>
                    </CardContent>
                  </Card>
                  <Card className="bg-slate-900/50 border-blue-500/10">
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-blue-400">{withdrawalStats.processing}</div>
                      <div className="text-xs text-muted-foreground mt-1">Processing</div>
                    </CardContent>
                  </Card>
                  <Card className="bg-slate-900/50 border-green-500/10 col-span-2">
                    <CardContent className="p-4 text-center">
                      <div className="text-2xl font-bold text-green-400">${withdrawalStats.total_pending_amount?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                      <div className="text-xs text-muted-foreground mt-1">Total Pending Amount</div>
                    </CardContent>
                  </Card>
                </div>
              )}

              {/* Withdrawal List */}
              {withdrawalLoading && pendingWithdrawals.length === 0 ? (
                <div className="flex justify-center py-12">
                  <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : pendingWithdrawals.length === 0 ? (
                <Card className="bg-slate-900/50 border-slate-700/50">
                  <CardContent className="p-12 text-center">
                    <CheckCircle className="h-12 w-12 mx-auto text-green-500 mb-4" />
                    <h3 className="text-lg font-semibold">All Clear</h3>
                    <p className="text-muted-foreground mt-1">No pending withdrawal requests</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {pendingWithdrawals.map((wd) => (
                    <Card
                      key={wd.id}
                      data-testid={`withdrawal-card-${wd.id}`}
                      className={cn(
                        "bg-slate-900/50 border transition-all",
                        wd.requires_multi_approval
                          ? "border-red-500/30 hover:border-red-500/50"
                          : "border-amber-500/10 hover:border-amber-500/30"
                      )}
                    >
                      <CardContent className="p-4 sm:p-6">
                        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                          {/* Left: Info */}
                          <div className="flex-1 space-y-2">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-mono text-lg font-bold text-white">
                                ${wd.amount.toLocaleString(undefined, {minimumFractionDigits: 2})}
                              </span>
                              <Badge variant="outline" className="text-xs">{wd.currency}</Badge>
                              {wd.requires_multi_approval && (
                                <Badge className="bg-red-500/20 text-red-400 border-red-500/30 text-xs">
                                  <AlertTriangle className="h-3 w-3 mr-1" />
                                  Multi-Approval Required
                                </Badge>
                              )}
                              <Badge
                                className={cn(
                                  "text-xs",
                                  wd.status === 'pending_approval'
                                    ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                                    : "bg-blue-500/20 text-blue-400 border-blue-500/30"
                                )}
                              >
                                {wd.status.replace('_', ' ').toUpperCase()}
                              </Badge>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
                              <div>
                                <span className="text-muted-foreground">User: </span>
                                <span className="text-white">{wd.user_email}</span>
                              </div>
                              <div>
                                <span className="text-muted-foreground">Fee: </span>
                                <span className="text-white">${wd.fee?.toFixed(2)}</span>
                              </div>
                              <div className="col-span-2">
                                <span className="text-muted-foreground">Address: </span>
                                <code className="text-xs text-amber-300 bg-slate-800 px-1 py-0.5 rounded">
                                  {wd.address?.substring(0, 24)}...
                                </code>
                              </div>
                              <div>
                                <span className="text-muted-foreground">Created: </span>
                                <span className="text-white">{new Date(wd.created_at).toLocaleString()}</span>
                              </div>
                              {wd.requires_multi_approval && (
                                <div>
                                  <span className="text-muted-foreground">Approvals: </span>
                                  <span className={cn(
                                    "font-bold",
                                    wd.approval_count >= wd.required_approvals ? "text-green-400" : "text-amber-400"
                                  )}>
                                    {wd.approval_count}/{wd.required_approvals}
                                  </span>
                                </div>
                              )}
                            </div>

                            {/* Show approval history */}
                            {wd.approvals && wd.approvals.length > 0 && (
                              <div className="mt-2 pt-2 border-t border-slate-700/50">
                                <div className="text-xs text-muted-foreground mb-1">Approval History:</div>
                                {wd.approvals.map((a: any, i: number) => (
                                  <div key={i} className="text-xs text-green-400 flex items-center gap-1">
                                    <CheckCircle className="h-3 w-3" />
                                    {a.admin_email || a.admin_id} - {new Date(a.approved_at).toLocaleString()}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>

                          {/* Right: Actions */}
                          <div className="flex gap-2 lg:flex-col">
                            <Button
                              size="sm"
                              data-testid={`approve-withdrawal-${wd.id}`}
                              onClick={() => handleApproveWithdrawal(wd.id)}
                              className="bg-green-600 hover:bg-green-700 text-white"
                            >
                              <CheckCircle className="h-4 w-4 mr-1" />
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              data-testid={`reject-withdrawal-${wd.id}`}
                              onClick={() => handleRejectWithdrawal(wd.id)}
                            >
                              <XCircle className="h-4 w-4 mr-1" />
                              Reject
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              <div className="text-xs text-muted-foreground text-center mt-4">
                <Clock className="h-3 w-3 inline mr-1" />
                Auto-refreshes every 15 seconds. Telegram notifications sent for all high-value withdrawals.
              </div>
            </div>
          )}


          {/* Broadcast Tab */}
          {activeTab === 'broadcast' && (
            <div className="max-w-2xl space-y-6">
              <h2 className="text-2xl font-bold">Broadcast Message</h2>
              <Card className="bg-slate-900/50 border-amber-500/10">
                <CardContent className="p-6 space-y-4">
                  <div>
                    <label className="text-sm font-medium mb-2 block">Title</label>
                    <Input
                      placeholder="Message title..."
                      value={broadcastMessage.title}
                      onChange={(e) => setBroadcastMessage(m => ({ ...m, title: e.target.value }))}
                      className="bg-slate-800/50 border-slate-700"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">Message</label>
                    <Textarea
                      placeholder="Enter your broadcast message..."
                      value={broadcastMessage.message}
                      onChange={(e) => setBroadcastMessage(m => ({ ...m, message: e.target.value }))}
                      className="bg-slate-800/50 border-slate-700 min-h-[120px]"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">Type</label>
                    <Select value={broadcastMessage.type} onValueChange={(v) => setBroadcastMessage(m => ({ ...m, type: v }))}>
                      <SelectTrigger className="bg-slate-800/50 border-slate-700">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="info">Info</SelectItem>
                        <SelectItem value="warning">Warning</SelectItem>
                        <SelectItem value="critical">Critical</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button onClick={handleBroadcast} className="w-full bg-amber-500 hover:bg-amber-600 text-black" disabled={!broadcastMessage.title || !broadcastMessage.message}>
                    <Send className="h-4 w-4 mr-2" /> Send to All Users
                  </Button>
                </CardContent>
              </Card>
            </div>
          )}
        </main>
      </div>

      {/* User Action Modal */}
      <Dialog open={userActionModal} onOpenChange={setUserActionModal}>
        <DialogContent className="bg-slate-900 border-slate-700">
          <DialogHeader>
            <DialogTitle>Confirm Action: {userAction}</DialogTitle>
            <DialogDescription>
              {userAction === 'suspend' && 'This will immediately suspend the user\'s account.'}
              {userAction === 'unsuspend' && 'This will restore the user\'s account access.'}
              {userAction === 'verify' && 'This will mark the user\'s email as verified.'}
              {userAction === 'force_logout' && 'This will log the user out of all sessions.'}
            </DialogDescription>
          </DialogHeader>
          {(userAction === 'suspend') && (
            <Textarea
              placeholder="Reason for action (required for suspension)..."
              value={actionReason}
              onChange={(e) => setActionReason(e.target.value)}
              className="bg-slate-800/50 border-slate-700"
            />
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setUserActionModal(false)}>Cancel</Button>
            <Button onClick={handleUserAction} className={cn(
              userAction === 'suspend' ? 'bg-red-500 hover:bg-red-600' : 'bg-amber-500 hover:bg-amber-600',
              'text-white'
            )}>
              Confirm {userAction}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Wallet Adjust Modal */}
      <Dialog open={walletAdjustModal} onOpenChange={setWalletAdjustModal}>
        <DialogContent className="bg-slate-900 border-slate-700">
          <DialogHeader>
            <DialogTitle>Adjust Wallet Balance</DialogTitle>
            <DialogDescription>
              Modify {selectedUser?.email}'s wallet balance. This action will be logged.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium mb-2 block">Currency</label>
              <Select value={walletAdjust.currency} onValueChange={(v) => setWalletAdjust(w => ({ ...w, currency: v }))}>
                <SelectTrigger className="bg-slate-800/50 border-slate-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="BTC">BTC</SelectItem>
                  <SelectItem value="ETH">ETH</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Amount (use negative for deduction)</label>
              <Input
                type="number"
                placeholder="100.00"
                value={walletAdjust.amount || ''}
                onChange={(e) => setWalletAdjust(w => ({ ...w, amount: parseFloat(e.target.value) || 0 }))}
                className="bg-slate-800/50 border-slate-700"
              />
            </div>
            <div>
              <label className="text-sm font-medium mb-2 block">Reason (required)</label>
              <Textarea
                placeholder="Reason for adjustment..."
                value={walletAdjust.reason}
                onChange={(e) => setWalletAdjust(w => ({ ...w, reason: e.target.value }))}
                className="bg-slate-800/50 border-slate-700"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setWalletAdjustModal(false)}>Cancel</Button>
            <Button onClick={handleWalletAdjust} className="bg-amber-500 hover:bg-amber-600 text-black" disabled={!walletAdjust.reason}>
              Apply Adjustment
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AdminDashboard;
