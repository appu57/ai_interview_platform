import React from 'react';

const reviews = [
  {
    name: "Marcus Vance",
    role: "Senior Infrastructure Engineer",
    company: "Netflix",
    text: "The System Design Mentor simulation accurately mirrored the open-ended nature of my real architecture evaluation loop. Absolute game changer for clearing hard infrastructure questions."
  },
  {
    name: "Elena Rostova",
    role: "Staff Software Engineer",
    company: "Stripe",
    text: "The real-time code execution diagnostic analysis flagged an optimization oversight inside a graph search algorithm I completely missed. Got me cleanly through the technical phase."
  },
  {
    name: "Devon Keith",
    role: "L5 Backend Developer",
    company: "Google",
    text: "Vocal mock evaluations felt remarkably seamless. The conversational AI captures pauses, communication pacing gaps, and technical jargon errors flawlessly."
  }
];

export const Testimonials: React.FC = () => {
  return (
    <section className="py-20 border-t border-slate-900/60 bg-slate-950/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">Validated By Top-Tier Engineers</h2>
          <p className="mt-3 text-slate-400 text-sm">See how modern developers use our system to transition their careers safely.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {reviews.map((rev, index) => (
            <div key={index} className="bg-slate-900/30 border border-slate-900 rounded-xl p-6 flex flex-col justify-between">
              <p className="text-xs sm:text-sm text-slate-300 italic leading-relaxed">
                "{rev.text}"
              </p>
              <div className="mt-6 pt-4 border-t border-slate-900/80 flex items-center justify-between">
                <div>
                  <h5 className="text-xs font-semibold text-slate-200">{rev.name}</h5>
                  <p className="text-[11px] text-slate-500 mt-0.5">{rev.role}</p>
                </div>
                <span className="text-[10px] font-bold text-indigo-400 tracking-wider bg-indigo-500/5 border border-indigo-500/10 px-2 py-0.5 rounded uppercase">
                  {rev.company}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};