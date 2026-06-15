import React from 'react';
import { ArrowRight, Play, CheckCircle2, Bot, Code, BarChart3 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from './Button';

export const Hero: React.FC = () => {
  const navigate = useNavigate();

  return (
    <section className="relative pt-32 pb-20 md:pt-40 md:pb-28 premium-glow overflow-hidden">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
        <div className="inline-flex items-center space-x-2 bg-indigo-500/5 border border-indigo-500/10 rounded-full px-3 py-1 text-xs text-indigo-400 mb-6 backdrop-blur-sm">
          <span>Engineered for modern software infrastructure interviews</span>
        </div>
        
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-white tracking-tight max-w-4xl mx-auto leading-[1.1]">
          Crack Your Next Tech Interview With <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-500">AI</span>
        </h1>
        
        <p className="mt-6 text-base sm:text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
          Practice DSA, System Design, and Behavioral Interviews with an AI mentor that gives personalized feedback and industry-level guidance.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button variant="primary" size="lg" className="w-full sm:w-auto" onClick={() => navigate('/signup')}>
            Start Mock Interview <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
          <Button variant="secondary" size="lg" className="w-full sm:w-auto">
            <Play className="w-4 h-4 mr-2 fill-current" /> Watch Demo
          </Button>
        </div>

        {/* Trusted By Section */}
        <div className="mt-20 border-t border-slate-900/60 pt-10">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Trusted by engineers migrating to</p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-12 gap-y-6 text-slate-600 font-bold tracking-wide text-sm md:text-base">
            <span className="hover:text-slate-400 transition-colors">FAANG</span>
            <span className="hover:text-slate-400 transition-colors">STARTUPS</span>
            <span className="hover:text-slate-400 transition-colors">PRODUCT COs</span>
            <span className="hover:text-slate-400 transition-colors">ENTERPRISE TEAMS</span>
          </div>
        </div>

        {/* Interactive Mock Dashboard Illustration */}
        <div className="mt-16 relative mx-auto max-w-5xl rounded-xl border border-slate-800/80 bg-slate-900/20 p-4 backdrop-blur-xl shadow-2xl shadow-indigo-500/5">
          <div className="bg-[#0E1116] border border-slate-800 rounded-lg overflow-hidden flex flex-col h-[420px] md:h-[500px] text-left text-xs text-slate-400">
            {/* Mock Header Row */}
            <div className="border-b border-slate-800 px-4 py-3 flex items-center justify-between bg-slate-900/40">
              <div className="flex items-center space-x-2">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
                <span className="ml-2 font-mono text-slate-500">session_id: mock_792a4f</span>
              </div>
              <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded text-[10px] font-medium animate-pulse">
                Live AI Assessment Active
              </div>
            </div>

            {/* Mock Workspace Split */}
            <div className="flex-1 grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-slate-800 overflow-hidden">
              {/* Left Column: Monaco Code Preview */}
              <div className="md:col-span-2 flex flex-col bg-[#0B0D11]">
                <div className="border-b border-slate-800/50 px-4 py-2 bg-slate-900/20 font-mono flex justify-between items-center text-slate-500">
                  <span>Solution.ts</span>
                  <span className="text-indigo-400 font-sans font-medium">TypeScript</span>
                </div>
                <pre className="p-4 font-mono text-[11px] leading-relaxed text-slate-300 overflow-y-auto flex-1">
                  <code>{`function lowestCommonAncestor(root: TreeNode | null, p: TreeNode, q: TreeNode): TreeNode | null {
    if (!root || root === p || root === q) return root;
    
    const left = lowestCommonAncestor(root.left, p, q);
    const right = lowestCommonAncestor(root.right, p, q);
    
    // AI Note: Optimal localized recursion path achieved
    if (left && right) return root;
    return left ? left : right;
}`}</code>
                </pre>
              </div>

              {/* Right Column: AI Interviewer Panel */}
              <div className="bg-[#0E1116] p-4 flex flex-col justify-between overflow-y-auto">
                <div className="space-y-4">
                  <div className="flex items-start space-x-2.5">
                    <div className="bg-indigo-600/10 p-1.5 border border-indigo-500/20 rounded-lg shrink-0">
                      <Bot className="w-4 h-4 text-indigo-400" />
                    </div>
                    <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 text-slate-300 leading-normal">
                      Excellent execution on the recursive checks. Can you explain the space complexity overhead on the call stack if this tree becomes skewed?
                    </div>
                  </div>

                  <div className="flex items-start space-x-2.5 justify-end">
                    <div className="bg-slate-800 border border-slate-700/50 rounded-lg p-3 text-slate-300 leading-normal max-w-[85%]">
                      The space complexity would degrade to $O(N)$ due to stack frames matching tree height.
                    </div>
                  </div>
                </div>

                {/* Score Summary Snapshot */}
                <div className="mt-6 border-t border-slate-800/80 pt-4 space-y-2">
                  <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Real-time Performance Metrics</div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-slate-900/50 border border-slate-800 p-2 rounded">
                      <div className="text-slate-400 flex items-center"><Code className="w-3 h-3 mr-1 text-slate-500" /> Accuracy</div>
                      <div className="text-sm font-bold text-slate-200 mt-0.5">94%</div>
                    </div>
                    <div className="bg-slate-900/50 border border-slate-800 p-2 rounded">
                      <div className="text-slate-400 flex items-center"><BarChart3 className="w-3 h-3 mr-1 text-slate-500" /> Communication</div>
                      <div className="text-sm font-bold text-indigo-400 mt-0.5">88%</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};