import React, { useState } from 'react';
import { Layers, Terminal, Sparkles, Trophy } from 'lucide-react';

const steps = [
  {
    icon: <Layers className="w-4 h-4" />,
    title: "Choose Interview Type",
    desc: "Target explicit verticals like Advanced Sharding, Distributed Caching, or LeetCode Hard arrays."
  },
  {
    icon: <Terminal className="w-4 h-4" />,
    title: "Start Interview",
    desc: "Code inside our integrated engine or talk directly using our high-frequency WebRTC audio stream lines."
  },
  {
    icon: <Sparkles className="w-4 h-4" />,
    title: "Receive Feedback",
    desc: "Obtain localized score vectors pinpointing conceptual framework errors and code complexity spikes."
  },
  {
    icon: <Trophy className="w-4 h-4" />,
    title: "Improve Weak Areas",
    desc: "Engage targeted drill workspaces suggested to fill identified engineering system knowledge gaps."
  }
];

export const ProductDemo: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);

  return (
    <section id="demo" className="py-20 bg-slate-950/20 border-t border-slate-900/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          
          {/* Left Column: Visual Representation Mock */}
          <div className="bg-[#0B0D11] border border-slate-800 rounded-xl p-6 shadow-xl relative overflow-hidden h-[340px] flex flex-col justify-between">
            <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-600/5 rounded-full blur-3xl pointer-events-none" />
            
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
              <span className="text-xs font-mono text-slate-500">workflow_visualizer.step_{activeStep + 1}</span>
              <div className="w-2 h-2 rounded-full bg-indigo-500" />
            </div>

            <div className="flex-1 flex items-center justify-center py-6">
              {activeStep === 0 && (
                <div className="w-full max-w-sm space-y-3 animate-fadeIn">
                  <div className="bg-slate-900 border border-indigo-500/30 p-3 rounded-lg text-slate-200 font-medium text-sm">System Design: Core Payment Gateway</div>
                  <div className="bg-slate-900/40 border border-slate-800 p-3 rounded-lg text-slate-400 text-sm">DSA: Graph Topological Sort</div>
                  <div className="bg-slate-900/40 border border-slate-800 p-3 rounded-lg text-slate-400 text-sm">Behavioral: Conflict Management</div>
                </div>
              )}
              {activeStep === 1 && (
                <div className="font-mono text-[11px] text-slate-300 space-y-2 w-full animate-fadeIn">
                  <div className="text-slate-500">// Simulating concurrent request volume ingestion...</div>
                  <div className="text-indigo-400">Connecting to LiveKit high-frequency cluster...</div>
                  <div className="text-emerald-400">✔ Audio track pipeline established safely.</div>
                </div>
              )}
              {activeStep === 2 && (
                <div className="w-full max-w-xs space-y-2 animate-fadeIn">
                  <div className="flex justify-between text-xs text-slate-400"><span>Technical Execution Score</span><span className="text-indigo-400 font-bold">87/100</span></div>
                  <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden"><div className="bg-indigo-500 h-full w-[87%]" /></div>
                  <p className="text-[11px] text-slate-500 pt-2 leading-relaxed">Critique: Consider offloading asset uploads onto asynchronous background queues to decrease API thread locks.</p>
                </div>
              )}
              {activeStep === 3 && (
                <div className="text-center space-y-3 animate-fadeIn">
                  <div className="inline-flex bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 p-3 rounded-full"><Trophy className="w-6 h-6" /></div>
                  <div className="text-sm font-semibold text-slate-200">Recommended Path Unlocked</div>
                  <p className="text-xs text-slate-400 max-w-xs">Complete the 3 curated distributed consensus nodes exercises.</p>
                </div>
              )}
            </div>

            <div className="text-slate-500 text-[10px] text-center border-t border-slate-900 pt-2">
              Click a step sequence on the right to simulate execution
            </div>
          </div>

          {/* Right Column: Descriptions Steps List */}
          <div className="space-y-6">
            <div className="space-y-2">
              <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">How Mock.ai Prepares You</h2>
              <p className="text-slate-400 text-sm">An engineered cyclical training framework aimed at systemic optimization.</p>
            </div>

            <div className="space-y-4">
              {steps.map((step, idx) => (
                <div 
                  key={idx}
                  onClick={() => setActiveStep(idx)}
                  className={`border rounded-xl p-4 transition-all duration-200 cursor-pointer flex items-start space-x-4 ${activeStep === idx ? 'bg-slate-900/50 border-indigo-500/30 shadow-md' : 'bg-transparent border-slate-900 hover:border-slate-800'}`}
                >
                  <div className={`p-2 rounded-lg border shrink-0 transition-colors ${activeStep === idx ? 'bg-indigo-600/10 border-indigo-500/20 text-indigo-400' : 'bg-slate-900 border-slate-800 text-slate-500'}`}>
                    {step.icon}
                  </div>
                  <div>
                    <h4 className={`text-sm font-semibold transition-colors ${activeStep === idx ? 'text-white' : 'text-slate-300'}`}>{step.title}</h4>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </section>
  );
};