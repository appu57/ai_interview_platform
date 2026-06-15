import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

const items = [
  {
    q: "How does Mock.ai work?",
    a: "Mock.ai couples LLM orchestration stacks with high-frequency audio paths to mirror natural human pacing. It evaluates both your plain code structure input and verbal explanations against objective industry evaluation criteria."
  },
  {
    q: "Is it suitable for beginners?",
    a: "Yes. The AI adjusts its conversational baseline complexity based on the parameters you designate prior to initiating an assessment track."
  },
  {
    q: "Can it evaluate system design?",
    a: "Absolutely. Mock.ai uses specialized visual and layout parsing contexts to analyze how you layer databases, shards, proxy layers, queues, and fallback infrastructure topologies."
  },
  {
    q: "Does it support coding interviews?",
    a: "Yes. Our engine natively parses, builds, and evaluates structure variables across major programming langages including TypeScript, Python, Go, C++, and Java."
  }
];

export const FAQ: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section id="faq" className="py-20 border-t border-slate-900/60 bg-slate-950/10">
      <div className="max-w-3xl mx-auto px-4 sm:px-6">
        <h2 className="text-2xl sm:text-3xl font-bold text-center text-white tracking-tight mb-12">Frequently Asked Questions</h2>
        
        <div className="space-y-4">
          {items.map((item, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div key={idx} className="bg-slate-950/40 border border-slate-900 rounded-xl overflow-hidden">
                <button 
                  onClick={() => setOpenIndex(isOpen ? null : idx)}
                  className="w-full px-5 py-4 text-left flex justify-between items-center text-slate-200 hover:text-white font-medium text-sm transition-colors"
                >
                  <span>{item.q}</span>
                  {isOpen ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
                </button>
                {isOpen && (
                  <div className="px-5 pb-5 pt-1 text-xs text-slate-400 border-t border-slate-900/30 leading-relaxed animate-fadeIn">
                    {item.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};