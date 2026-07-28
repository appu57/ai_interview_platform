import React, { useState } from 'react';
import { Terminal, ArrowLeft, AlertCircle } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Input } from '../components/Input';
import { Button } from '../components/Button';
import api from '../auth/auth';

export default function SignIn() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Execute the authenticated session sequence with your FastAPI router
      const response = await api.post('/api/auth/login', {
        email,
        password,
      });
      const userData = response.data.user_id 
      localStorage.setItem('user', userData);
      // Verification Success: The backend already set your secure HttpOnly cookies in response headers!
      // Navigate your authenticated developer straight to their interactive workspace
      navigate('/workspace');
    } catch (err: any) {
      // Safe validation mapping - extracts detail strings directly from FastAPI validation exceptions
      const errorMessage = err.response?.data?.detail || "Could not complete authentication. Please verify credentials.";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
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
          <h3 className="text-xl font-bold text-white tracking-tight">Welcome Back</h3>
          <p className="text-xs text-slate-500">Resume your technical interview assessment track</p>
        </div>

        {/* PREMIUM ERROR ALERT CONTAINER (Replacing raw alert() modals) */}
        {error && (
          <div className="mb-6 flex items-start gap-2.5 p-3.5 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span className="font-medium leading-relaxed">{error}</span>
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <Input 
            label="Email Address" 
            type="email" 
            placeholder="name@company.com" 
            required 
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input 
            label="Account Password" 
            type="password" 
            placeholder="••••••••" 
            required 
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <Button variant="primary" type="submit" className="w-full pt-2.5 pb-2.5" isLoading={loading}>
            Sign In To Workspace
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-slate-500 font-medium">
          New to the pipeline? <Link to="/signup" className="text-indigo-400 hover:underline">Create an account</Link>
        </p>
      </div>
    </div>
  );
}