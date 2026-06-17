import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Terminal, 
  Cpu, 
  Brain, 
  Compass, 
  LogOut, 
  Loader2, 
  AlertTriangle,
  User,
  ExternalLink,
  ShieldAlert
} from 'lucide-react';
import api from '../auth/auth';

interface UserData {
  id: string;
  email: string;
  full_name: string | null;
  role?: string;
}

export default function WorkspaceHome() {
  const [user, setUser] = useState<UserData | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const navigate = useNavigate();

  // Helper function to extract a specific cookie value from document.cookie
  const getCookie = (name: string): string | null => {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
      return parts.pop()?.split(';').shift() || null;
    }
    return null;
  };

  useEffect(() => {
    const verifySecurityContext = async () => {
      try {
        // 1. STRICT SECURITY GATE: Client-side check for CSRF token existence
        const csrfToken = getCookie('csrf_token');
        if (!csrfToken) {
          console.warn("Security Breach: CSRF security token missing from local cookie context.");
          setAuthError("CSRF verification token missing. Please sign in again.");
          setCheckingAuth(false);
          // Redirect immediately to login
          setTimeout(() => navigate('/signin'), 2000);
          return;
        }

        // 2. BACKEND HANDSHAKE: Hit our protected /me profile route
        // This implicitly validates the secure HttpOnly access_token and refresh_token
        const response = await api.get('/api/auth/me');
        
        // Successfully passed all security checks! Let's set user session state
        setUser(response.data);
        setCheckingAuth(false);
      } catch (err: any) {
        console.error("Authentication handshake failed:", err);
        setAuthError("Secure session validation failed. Redirecting...");
        setCheckingAuth(false);
        // Clean cleanup and bounce to credentials route
        setTimeout(() => navigate('/signin'), 2000);
      }
    };

    verifySecurityContext();
  }, [navigate]);

  const handleLogout = async () => {
    try {
      // Clear security tokens on backend
      await api.post('/api/auth/logout');
    } catch (err) {
      console.error("Logout request failed:", err);
    } finally {
      // Always clear user state and bounce back to landing
      navigate('/');
    }
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-[#0A0B0D] flex flex-col items-center justify-center space-y-4">
        <div className="relative">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          <div className="absolute inset-0 bg-indigo-500/20 blur-xl rounded-full" />
        </div>
        <div className="text-center space-y-1">
          <p className="text-xs font-mono text-indigo-400 tracking-wider uppercase">Authenticating Environment</p>
          <p className="text-[10px] text-slate-600">Verifying security parameters & token integrity...</p>
        </div>
      </div>
    );
  }

  if (authError) {
    return (
      <div className="min-h-screen bg-[#0A0B0D] flex flex-col items-center justify-center px-4">
        <div className="max-w-md w-full bg-red-500/5 border border-red-500/20 rounded-xl p-8 text-center space-y-6 backdrop-blur-xl">
          <div className="inline-flex bg-red-500/10 p-3 rounded-xl border border-red-500/20 text-red-400 mx-auto">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div className="space-y-2">
            <h4 className="text-sm font-bold text-red-400 font-mono tracking-tight uppercase">Security Handshake Failure</h4>
            <p className="text-xs text-slate-400 leading-relaxed">{authError}</p>
          </div>
          <div className="h-1 bg-slate-900 overflow-hidden rounded-full w-24 mx-auto">
            <div className="h-full bg-red-500 animate-pulse w-full" />
          </div>
        </div>
      </div>
    );
  }

  const username = user?.full_name || user?.email?.split('@')[0] || "Developer";

  return (
    <div className="min-h-screen bg-[#0A0B0D] text-slate-100 flex flex-col relative overflow-hidden">
      {/* Background Decorative Mesh Glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-900/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-emerald-950/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Workspace Header */}
      <header className="border-b border-slate-900 bg-slate-950/20 backdrop-blur-md px-6 py-4 flex items-center justify-between relative z-10">
        <div className="flex items-center space-x-3">
          <div className="bg-indigo-600/10 p-1.5 rounded-lg border border-indigo-500/20">
            <Terminal className="w-4 h-4 text-indigo-400" />
          </div>
          <span className="text-sm font-mono font-bold tracking-tight text-white uppercase">
            AI Interviewer <span className="text-indigo-400">Workspace</span>
          </span>
        </div>

        <div className="flex items-center space-x-4">
          {/* User Badge */}
          <div className="flex items-center space-x-2 px-3 py-1.5 bg-slate-900/40 border border-slate-800/80 rounded-lg text-xs font-mono">
            <User className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-300 font-medium">{user?.email}</span>
          </div>

          {/* Secure Logout Trigger */}
          <button 
            onClick={handleLogout}
            className="inline-flex items-center text-xs text-slate-500 hover:text-red-400 transition-colors bg-slate-950/40 hover:bg-red-500/5 px-3 py-1.5 border border-slate-900 hover:border-red-500/20 rounded-lg"
          >
            <LogOut className="w-3.5 h-3.5 mr-1.5" />
            Logout Session
          </button>
        </div>
      </header>

      {/* Core Workspace Hub */}
      <main className="flex-1 flex flex-col justify-center max-w-5xl w-full mx-auto px-6 py-12 relative z-10">
        
        {/* PREMIUM WELCOME HERO BANNER */}
        <section className="mb-12 relative">
          <div className="bg-gradient-to-r from-slate-950 to-slate-900/80 border border-slate-900 rounded-2xl p-8 md:p-10 relative overflow-hidden shadow-2xl">
            {/* Visual background details */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 rounded-full blur-[80px] pointer-events-none" />
            <div className="absolute -bottom-10 -right-10 opacity-10">
              <Compass className="w-64 h-64 text-indigo-500" />
            </div>

            <div className="space-y-3 max-w-2xl relative z-10">
              <span className="px-2.5 py-1 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-md text-[10px] font-mono uppercase tracking-wider">
                System Active
              </span>
              <h2 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight leading-tight">
                Welcome, <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 to-indigo-500">{username}</span>!
              </h2>
              <p className="text-sm md:text-base text-slate-400 font-medium">
                Ready to get interview ready? Select your pipeline to configure and initialize your real-time simulator run.
              </p>
            </div>
          </div>
        </section>

        {/* CONTAINER MODES GRID */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* OPTION 1: INTERVIEW MODE */}
          <div 
            onClick={() => navigate('/workspace/interview-mode')}
            className="group cursor-pointer bg-slate-950/30 border border-slate-900 hover:border-indigo-500/30 rounded-2xl p-6 transition-all duration-300 hover:shadow-[0_0_30px_rgba(99,102,241,0.05)] flex flex-col justify-between h-72 relative"
          >
            {/* Corner highlight glow */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-600/0 group-hover:bg-indigo-600/5 rounded-bl-full transition-all duration-300 blur-2xl" />

            <div className="space-y-4">
              <div className="inline-flex bg-indigo-600/10 p-3.5 rounded-xl border border-indigo-500/20 text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-all duration-300">
                <Cpu className="w-6 h-6" />
              </div>
              <div className="space-y-1.5">
                <h4 className="text-lg font-bold text-white tracking-tight group-hover:text-indigo-300 transition-colors">
                  Interview Mode
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Experience standard mock evaluations modeled on rigorous tech-firm loops. Features structured verbal questions, live terminal sandbox prompts, and an interactive grading cycle with critical engineering reports.
                </p>
              </div>
            </div>

            <div className="flex items-center text-xs text-indigo-400 font-mono font-bold group-hover:translate-x-1.5 transition-transform duration-300">
              Initialize Simulator Run
              <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
            </div>
          </div>

          {/* OPTION 2: TUTOR MODE */}
          <div 
            onClick={() => navigate('/workspace/tutor-mode')}
            className="group cursor-pointer bg-slate-950/30 border border-slate-900 hover:border-emerald-500/30 rounded-2xl p-6 transition-all duration-300 hover:shadow-[0_0_30px_rgba(16,185,129,0.05)] flex flex-col justify-between h-72 relative"
          >
            {/* Corner highlight glow */}
            <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-600/0 group-hover:bg-emerald-600/5 rounded-bl-full transition-all duration-300 blur-2xl" />

            <div className="space-y-4">
              <div className="inline-flex bg-emerald-600/10 p-3.5 rounded-xl border border-emerald-500/20 text-emerald-400 group-hover:bg-emerald-600 group-hover:text-white transition-all duration-300">
                <Brain className="w-6 h-6" />
              </div>
              <div className="space-y-1.5">
                <h4 className="text-lg font-bold text-white tracking-tight group-hover:text-emerald-300 transition-colors">
                  Tutor Mode
                </h4>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Learn interactively. Run practice loops with real-time corrective tips, detailed architecture discussions, and instant guidance step-by-step as you construct solution scripts in the terminal window.
                </p>
              </div>
            </div>

            <div className="flex items-center text-xs text-emerald-400 font-mono font-bold group-hover:translate-x-1.5 transition-transform duration-300">
              Initialize Practice Loop
              <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
            </div>
          </div>

        </div>

        {/* Footer info label */}
        <div className="mt-12 text-center">
          <p className="text-[10px] font-mono text-slate-600">
            Secure Session Verified • Double-Submit Cookie CSRF Defense Pattern Active • HSTS Enforced
          </p>
        </div>

      </main>
    </div>
  );
}