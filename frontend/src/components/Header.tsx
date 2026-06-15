import React, { useState, useEffect } from 'react';
import { Menu, X, Terminal } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from './Button';

export const Header: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id: string) => {
    setIsOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled ? 'bg-[#0A0B0D]/80 backdrop-blur-md border-b border-slate-900 py-3' : 'bg-transparent py-5'}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-2 text-white font-bold text-lg tracking-tight">
          <div className="bg-indigo-600/10 p-1.5 rounded-lg border border-indigo-500/20">
            <Terminal className="w-5 h-5 text-indigo-400" />
          </div>
          <span>Mock<span className="text-indigo-400">.ai</span></span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center space-x-8 text-sm font-medium text-slate-400">
          <button onClick={() => scrollToSection('features')} className="hover:text-slate-200 transition-colors cursor-pointer">Features</button>
          <button onClick={() => scrollToSection('demo')} className="hover:text-slate-200 transition-colors cursor-pointer">Product Demo</button>
          <button onClick={() => scrollToSection('pricing')} className="hover:text-slate-200 transition-colors cursor-pointer">Pricing</button>
          <button onClick={() => scrollToSection('faq')} className="hover:text-slate-200 transition-colors cursor-pointer">FAQ</button>
        </nav>

        <div className="hidden md:flex items-center space-x-4">
          <Button variant="outline" size="sm" onClick={() => navigate('/signin')}>Login</Button>
          <Button variant="primary" size="sm" onClick={() => navigate('/signup')}>Sign Up</Button>
        </div>

        {/* Mobile Hamburguer Toggle */}
        <button className="md:hidden text-slate-400 hover:text-slate-200" onClick={() => setIsOpen(!isOpen)}>
          {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Drawer Overlay */}
      {isOpen && (
        <div className="md:hidden fixed inset-0 top-[57px] bg-[#0A0B0D] z-40 px-4 py-6 border-t border-slate-900 flex flex-col justify-between">
          <nav className="flex flex-col space-y-6 text-base font-medium text-slate-300">
            <button onClick={() => scrollToSection('features')} className="text-left py-2 border-b border-slate-900">Features</button>
            <button onClick={() => scrollToSection('demo')} className="text-left py-2 border-b border-slate-900">Product Demo</button>
            <button onClick={() => scrollToSection('pricing')} className="text-left py-2 border-b border-slate-900">Pricing</button>
            <button onClick={() => scrollToSection('faq')} className="text-left py-2 border-b border-slate-900">FAQ</button>
          </nav>
          <div className="flex flex-col space-y-3 pt-6 pb-20">
            <Button variant="outline" className="w-full" onClick={() => navigate('/signin')}>Login</Button>
            <Button variant="primary" className="w-full" onClick={() => navigate('/signup')}>Sign Up</Button>
          </div>
        </div>
      )}
    </header>
  );
};