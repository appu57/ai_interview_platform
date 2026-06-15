import React from 'react';
import { Target, Lightbulb, TrendingUp } from 'lucide-react';

export const WhyMock: React.FC = () => {
  return (
    <section className="py-20 border-t border-slate-900/60 bg-[#0A0B0D]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">Why Engineers Train With Us</h2>
          <p className="mt-3 text-slate-400 text-sm">We swap generic, outdated question dumps for active architectural loops.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center space-y-4 p-4">
            <div className="mx-auto w-12 h-12 rounded-xl bg-indigo-600/5 border border-indigo-500/10 text-indigo-400 flex items-center justify-center">
              <Target className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-slate-200">Interview Readiness</h3>
            <p className="text-xs text-slate-400 leading-relaxed max-w-sm mx-auto">
              Receive highly dynamic configuration templates mapping precisely across real modern tech assessment pipelines.
            </p>
          </div>

          <div className="text-center space-y-4 p-4">
            <div className="mx-auto w-12 h-12 rounded-xl bg-indigo-600/5 border border-indigo-500/10 text-indigo-400 flex items-center justify-center">
              <Lightbulb className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-slate-200">Instant Feedback</h3>
            <p className="text-xs text-slate-400 leading-relaxed max-w-sm mx-auto">
              No days spent waiting for human review panels. Pinpoint code inefficiencies and optimization avenues immediately.
            </p>
          </div>

          <div className="text-center space-y-4 p-4">
            <div className="mx-auto w-12 h-12 rounded-xl bg-indigo-600/5 border border-indigo-500/10 text-indigo-400 flex items-center justify-center">
              <TrendingUp className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-slate-200">Track Growth</h3>
            <p className="text-xs text-slate-400 leading-relaxed max-w-sm mx-auto">
              Monitor clear telemetry variables tracing communication articulation, edge diagnostics, and algorithmic structural paths.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};