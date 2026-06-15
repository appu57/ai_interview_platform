import React from 'react';
import { Linkedin, Github, Twitter, Terminal } from 'lucide-react';
import { Link } from 'react-router-dom';

export const Footer: React.FC = () => {
  return (
    <footer className="border-t border-slate-900 bg-[#0A0B0D] text-xs text-slate-500 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-2 md:grid-cols-5 gap-8">
        
        {/* Brand Block */}
        <div className="col-span-2 space-y-4">
          <Link to="/" className="flex items-center space-x-2 text-white font-bold text-base tracking-tight">
            <div className="bg-indigo-600/10 p-1 rounded-md border border-indigo-500/20">
              <Terminal className="w-4 h-4 text-indigo-400" />
            </div>
            <span>Mock<span className="text-indigo-400">.ai</span></span>
          </Link>
          <p className="text-slate-400 leading-relaxed max-w-xs">
            Advanced real-time AI modeling software tracking behavioral depth and structural algorithmic criteria.
          </p>
          <div className="flex space-x-4 pt-2 text-slate-500">
            <a href="https://linkedin.com" target="_blank" rel="noreferrer" className="hover:text-slate-300 transition-colors"><Linkedin className="w-4 h-4" /></a>
            <a href="https://github.com" target="_blank" rel="noreferrer" className="hover:text-slate-300 transition-colors"><Github className="w-4 h-4" /></a>
            <a href="https://twitter.com" target="_blank" rel="noreferrer" className="hover:text-slate-300 transition-colors"><Twitter className="w-4 h-4" /></a>
          </div>
        </div>

        {/* Links Column 1 */}
        <div className="space-y-3">
          <h6 className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Product</h6>
          <ul className="space-y-2 font-medium">
            <li><a href="#features" className="hover:text-slate-300 transition-colors">Features</a></li>
            <li><a href="#demo" className="hover:text-slate-300 transition-colors">Demo Workspace</a></li>
            <li><a href="#pricing" className="hover:text-slate-300 transition-colors">Pricing Tiers</a></li>
          </ul>
        </div>

        {/* Links Column 2 */}
        <div className="space-y-3">
          <h6 className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Resources</h6>
          <ul className="space-y-2 font-medium">
            <li><span className="hover:text-slate-300 transition-colors cursor-pointer">Documentation</span></li>
            <li><span className="hover:text-slate-300 transition-colors cursor-pointer">System Blog</span></li>
            <li><span className="hover:text-slate-300 transition-colors cursor-pointer">Core Guide</span></li>
          </ul>
        </div>

        {/* Links Column 3 */}
        <div className="space-y-3">
          <h6 className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Legal</h6>
          <ul className="space-y-2 font-medium">
            <li><span className="hover:text-slate-300 transition-colors cursor-pointer">Terms of Service</span></li>
            <li><span className="hover:text-slate-300 transition-colors cursor-pointer">Privacy Charter</span></li>
            <li><span className="hover:text-slate-300 transition-colors cursor-pointer">GDPR Metrics</span></li>
          </ul>
        </div>

      </div>
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-12 pt-6 border-t border-slate-900/60 text-center text-[11px] font-medium tracking-wide">
        &copy; {new Date().getFullYear()} Mock.ai Systems Inc. All computing layers reserved.
      </div>
    </footer>
  );
};