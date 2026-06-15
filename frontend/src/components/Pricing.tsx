import React from 'react';
import { Check } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from './Button';

export const Pricing: React.FC = () => {
  const navigate = useNavigate();

  return (
    <section id="pricing" className="py-20 border-t border-slate-900/60 bg-[#0A0B0D]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">Predictable Transparent Pricing</h2>
          <p className="mt-3 text-slate-400 text-sm">Accelerate your technical depth with plans scaled for both individuals and teams.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto items-stretch">
          {/* Starter Plan */}
          <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-6 flex flex-col justify-between">
            <div>
              <h4 className="text-sm font-semibold text-slate-300">Starter</h4>
              <div className="mt-4 flex items-baseline text-white">
                <span className="text-3xl font-extrabold tracking-tight">$0</span>
                <span className="ml-1 text-xs text-slate-500">/ forever</span>
              </div>
              <p className="mt-3 text-xs text-slate-400">Essential diagnostics for exploratory evaluation tracks.</p>
              
              <ul className="mt-6 space-y-3 text-xs text-slate-300 border-t border-slate-900 pt-6">
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> 2 Core AI Mock Assessments</li>
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> Basic DSA Syntax Analyzer</li>
                <li className="flex items-center text-slate-600"><Check className="w-3.5 h-3.5 text-slate-800 mr-2 shrink-0" /> Real-time Voice WebRTC Session</li>
              </ul>
            </div>
            <Button variant="outline" size="sm" className="w-full mt-8" onClick={() => navigate('/signup')}>Get Started</Button>
          </div>

          {/* Pro Plan */}
          <div className="bg-slate-900/40 border-2 border-indigo-500/40 rounded-xl p-6 flex flex-col justify-between relative shadow-xl shadow-indigo-500/5">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-indigo-600 text-white font-semibold tracking-wider text-[10px] uppercase px-2.5 py-0.5 rounded-full">
              Most Popular
            </div>
            <div>
              <h4 className="text-sm font-semibold text-slate-200">Pro</h4>
              <div className="mt-4 flex items-baseline text-white">
                <span className="text-3xl font-extrabold tracking-tight">$29</span>
                <span className="ml-1 text-xs text-slate-500">/ monthly</span>
              </div>
              <p className="mt-3 text-xs text-slate-400">Comprehensive training capabilities for active job hunters.</p>
              
              <ul className="mt-6 space-y-3 text-xs text-slate-300 border-t border-slate-800 pt-6">
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> Unlimited Mock Evaluations</li>
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> Full System Design Sandbox Evaluator</li>
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> WebRTC Vocal Stream Coaching</li>
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> Historical Trend Score Metrics</li>
              </ul>
            </div>
            <Button variant="primary" size="sm" className="w-full mt-8" onClick={() => navigate('/signup')}>Upgrade to Pro</Button>
          </div>

          {/* Team Plan */}
          <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-6 flex flex-col justify-between">
            <div>
              <h4 className="text-sm font-semibold text-slate-300">Team</h4>
              <div className="mt-4 flex items-baseline text-white">
                <span className="text-3xl font-extrabold tracking-tight">$149</span>
                <span className="ml-1 text-xs text-slate-500">/ monthly</span>
              </div>
              <p className="mt-3 text-xs text-slate-400">Tailored multi-seat pipelines for training teams and bootcamps.</p>
              
              <ul className="mt-6 space-y-3 text-xs text-slate-300 border-t border-slate-900 pt-6">
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> Everything inside Pro (Up to 10 Seats)</li>
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> Central Management Dashboard</li>
                <li className="flex items-center"><Check className="w-3.5 h-3.5 text-indigo-400 mr-2 shrink-0" /> Custom System Infrastructure Nodes</li>
              </ul>
            </div>
            <Button variant="outline" size="sm" className="w-full mt-8" onClick={() => navigate('/signup')}>Contact Sales</Button>
          </div>
        </div>
      </div>
    </section>
  );
};