import React from 'react';
import { Bot, Code, GitFork, UserCheck, Search, LineChart } from 'lucide-react';

const featureList = [
  {
    icon: <Bot className="w-5 h-5 text-indigo-400" />,
    title: "AI Mock Interviews",
    description: "Engage in vocal and code-based live interviews that adapt dynamically based on your design decisions."
  },
  {
    icon: <Search className="w-5 h-5 text-indigo-400" />,
    title: "Real-time Feedback",
    description: "Get line-by-line syntax corrections, edge-case warning alerts, and deep architectural critiques instantly."
  },
  {
    icon: <Code className="w-5 h-5 text-indigo-400" />,
    title: "DSA Tutor",
    description: "Interactive data structures workspace helping you visualize algorithmic recursion trees dynamically."
  },
  {
    icon: <GitFork className="w-5 h-5 text-indigo-400" />,
    title: "System Design Mentor",
    description: "Assess high-scale infrastructure paradigms, bottlenecks, load balancers, and cache mapping evaluations."
  },
  {
    icon: <UserCheck className="w-5 h-5 text-indigo-400" />,
    title: "Resume Analyzer",
    description: "Parses your experiences against targeted technical roles to eliminate structural bullet point weaknesses."
  },
  {
    icon: <LineChart className="w-5 h-5 text-indigo-400" />,
    title: "Progress Tracking",
    description: "Visualize continuous diagnostic growth curves across execution correctness and behavioral criteria."
  }
];

export const Features: React.FC = () => {
  return (
    <section id="features" className="py-20 border-t border-slate-900/60 bg-[#0A0B0D]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
            Comprehensive Suite Built For Technical Success
          </h2>
          <p className="mt-4 text-slate-400">
            Everything you need to surpass rigorous engineering panels across core engineering competencies.
          </p>
        </div>

        <div className="mt-16 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {featureList.map((feat, index) => (
            <div 
              key={index}
              className="bg-slate-950/40 border border-slate-900 rounded-xl p-6 hover:border-indigo-500/30 transition-all duration-300 group hover:-translate-y-1"
            >
              <div className="bg-indigo-600/5 w-10 h-10 rounded-lg border border-indigo-500/10 flex items-center justify-center group-hover:bg-indigo-600/10 transition-colors">
                {feat.icon}
              </div>
              <h3 className="mt-4 text-base font-semibold text-slate-200 group-hover:text-white transition-colors">
                {feat.title}
              </h3>
              <p className="mt-2 text-sm text-slate-400 leading-relaxed">
                {feat.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};