import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from './Button';

export const CTA: React.FC = () => {
  const navigate = useNavigate();

  return (
    <section className="py-20 border-t border-slate-900/60 bg-gradient-to-b from-[#0A0B0D] to-[#0D0E12] text-center relative overflow-hidden">
      <div className="absolute inset-0 bg-indigo-600/[0.02] pointer-events-none" />
      <div className="max-w-4xl mx-auto px-4 sm:px-6 relative z-10 space-y-6">
        <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">Ready To Land Your Dream Job?</h2>
        <p className="text-slate-400 text-sm sm:text-base max-w-xl mx-auto leading-relaxed">
          Stop guessing your engineering depth levels. Optimize your technical communication loops under authentic constraints today.
        </p>
        <div className="pt-4 flex flex-col sm:flex-row justify-center items-center gap-4">
          <Button variant="primary" size="lg" className="w-full sm:w-auto" onClick={() => navigate('/signup')}>Start Free</Button>
          <Button variant="secondary" size="lg" className="w-full sm:w-auto">Schedule Demo</Button>
        </div>
      </div>
    </section>
  );
};