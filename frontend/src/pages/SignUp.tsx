import React, { useState } from 'react';
import { Terminal, ArrowLeft } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

export default function SignUp() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      alert("Registration cluster initialized! Let's wire up your parameters.");
    }, 1400);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0A0B0D] px-4 relative premium-glow">
      <Link to="/" className="absolute top-6 left-6 inline-flex items-center text-xs text-slate-500 hover:text-slate-300 transition-colors">
        <ArrowLeft className="w-3.5 h-3.5 mr-1.5" /> Back to root
      </Link>

      <div className="w-full max-w-sm bg-slate-950/40 border border-slate-900 rounded-xl p-8 backdrop-blur-xl shadow-xl">
        <div className="text-center space-y-2 mb-8">
          <div className="inline-flex bg-indigo-600/10 p-2 rounded-lg border border-indigo-500/20 mx-auto">
            <Terminal className="w-5 h-5 text-indigo-400" />
          </div>
          <h3 className="text-xl font-bold text-white tracking-tight">Initialize Training</h3>
          <p className="text-xs text-slate-500">Create your environment profiles to start</p>
        </div>

        <form onSubmit={handleRegister} className="space-y-4">
          <Input 
            label="Full Name" 
            type="text" 
            placeholder="Alex Mercer" 
            required 
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input 
            label="Email Address" 
            type="email" 
            placeholder="alex@engineering.io" 
            required 
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input 
            label="Secure Password" 
            type="password" 
            placeholder="••••••••" 
            required 
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button variant="primary" type="submit" className="w-full pt-2.5 pb-2.5" isLoading={loading}>
            Create Account & Build Plan
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500 font-medium">
          Already running cycles? <Link to="/signin" className="text-indigo-400 hover:underline">Log in here</Link>
        </p>
      </div>
    </div>
  );
}