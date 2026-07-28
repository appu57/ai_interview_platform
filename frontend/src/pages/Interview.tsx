import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Sparkles, 
  UploadCloud, 
  Github, 
  Building2, 
  Plus, 
  Trash2, 
  ArrowLeft, 
  Layers, 
  Cpu, 
  Volume2, 
  X, 
  Settings2, 
  CheckCircle2, 
  Play,
  RotateCcw
} from 'lucide-react';
import api from '../auth/auth';


interface InterviewRound {
  id: string;
  type: string;
  name: string;
  duration: string;
  desc: string;
}

interface CompanyTemplates {
  [key: string]: InterviewRound[];
}

interface SavePreferencesResponse {
  status: string;
  message: string;
  session_id: string;
  rounds_blueprint: { rounds: InterviewRound[] };
  first_agent_question?: string | null;
  oa_problem?: Record<string, unknown> | null;
  round_turn_count?: number;
  overall_score?: unknown;
  performance_overview?: unknown;
}


const COMPANY_TEMPLATES: CompanyTemplates = {
  Google: [
    { id: '1', type: 'OA', name: 'Online Coding Assessment', duration: '45 mins', desc: 'Algorithmic efficiency & data structures focus.' },
    { id: '2', type: 'Tech_DSA', name: 'Technical Round: DSA & Algorithms', duration: '45 mins', desc: 'Complex problem-solving & optimization.' },
    { id: '3', type: 'Sys_Design', name: 'Technical Round: System Design', duration: '60 mins', desc: 'Scale, caching, databases & architectural tradeoffs.' },
    { id: '4', type: 'Behavioral', name: 'Behavioral: Googlyness & Leadership', duration: '45 mins', desc: 'Cultural alignment, collaboration & problem ownership.' }
  ],
  Meta: [
    { id: '1', type: 'Tech_DSA', name: 'Technical Round: Rapid Coding', duration: '45 mins', desc: 'High-speed algorithmic challenges (2 questions).' },
    { id: '2', type: 'Sys_Design', name: 'Technical Round: Product Architecture', duration: '45 mins', desc: 'End-to-end client-server system optimization.' },
    { id: '3', type: 'Behavioral', name: 'Behavioral: Meta Values', duration: '45 mins', desc: 'Moving fast, impact, and engineering resolution.' }
  ],
  Stripe: [
    { id: '1', type: 'Integration', name: 'Practical API & Integration Round', duration: '60 mins', desc: 'Building on top of complex, real-world codebases.' },
    { id: '2', type: 'Tech_DSA', name: 'Technical Round: Algorithmic Systems', duration: '45 mins', desc: 'Concurrency, multi-threading & scalability.' },
    { id: '3', type: 'Behavioral', name: 'Behavioral: Technical Leadership', duration: '45 mins', desc: 'Deep dive into your past engineering decisions.' }
  ]
};

const DEFAULT_ROUNDS: InterviewRound[] = [
  { id: '1', type: 'OA', name: 'Online Coding Assessment', duration: '15 mins', desc: 'Algorithmic efficiency & data structures focus.' },
  { id: '2', type: 'Behavioral', name: 'HR & Behavioral Round', duration: '15 mins', desc: 'Soft skills, communication & background validation.' }
];

const PRESET_TECH_STACKS = [
  "React", "Python", "TypeScript", "Node.js", "PostgreSQL", 
  "Go", "Docker", "AWS", "FastAPI", "Kubernetes", "Next.js", "Rust"
];

const AVAILABLE_VOICES = [
  { name: "Kore", desc: "Warm & Professional (System Default)" },
  { name: "Zephyr", desc: "Clear & Academic" },
  { name: "Fenrir", desc: "Deep & Analytical" },
  { name: "Leda", desc: "Engaging & Conversational" }
];


const DURATION_OPTIONS = ["1 min","10 mins","15 mins", "30 mins", "45 mins", "60 mins", "75 mins", "90 mins"];

export default function InterviewSetup() {
  const navigate = useNavigate();

  const [jobTitle, setJobTitle] = useState('Senior Full Stack Engineer');
  const [experienceLevel, setExperienceLevel] = useState('Senior');
  const [targetCompany, setTargetCompany] = useState('');
  const [customRounds, setCustomRounds] = useState<InterviewRound[]>(DEFAULT_ROUNDS);
  
  const [techStack, setTechStack] = useState<string[]>(["React", "Python", "PostgreSQL", "FastAPI"]);
  const [currentTechInput, setCurrentTechInput] = useState('');
  
  // Auxiliary items
  const [difficulty, setDifficulty] = useState('Rigorous (FAANG Style)');

  const [voiceModel, setVoiceModel] = useState(AVAILABLE_VOICES[0].name);
  const [interviewerPersonality, setInterviewerPersonality] = useState('Balanced');
  const [selectedLanguage, setSelectedLanguage] = useState('Python');

  // Resume states
  const [resumeName, setResumeName] = useState<string | null>(null);
  const [resumeText, setResumeText] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);

  // Simulation controls
  const [isLaunching, setIsLaunching] = useState(false);
  const [launchStep, setLaunchStep] = useState(0);
  const [simulationComplete, setSimulationComplete] = useState(false);
  const [livekitToken, setLivekitToken] = useState("");

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [oaProblem, setOaProblem] = useState<Record<string, unknown> | null>(null);
  const [firstAgentQuestion, setFirstAgentQuestion] = useState<string | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);

  // Auto-populate company templates when company input matches preset keys
  useEffect(() => {
    const matchedCompany = Object.keys(COMPANY_TEMPLATES).find(
      key => key.toLowerCase() === targetCompany.trim().toLowerCase()
    );
    if (matchedCompany) {
      setCustomRounds(COMPANY_TEMPLATES[matchedCompany]);
    } else if (targetCompany.trim() === '') {
      setCustomRounds(DEFAULT_ROUNDS);
    }
  }, [targetCompany]);

  // --- FORM MANIPULATION ACTIONS ---
  const handleAddTech = (tech: string) => {
    const cleanTech = tech.trim();
    if (cleanTech && !techStack.includes(cleanTech)) {
      setTechStack([...techStack, cleanTech]);
    }
    setCurrentTechInput('');
  };

  const handleRemoveTech = (index: number) => {
    setTechStack(techStack.filter((_, idx) => idx !== index));
  };

  const handleAddRound = (type: string) => {
    let name = "Custom Interview Round";
    let desc = "Curated AI engineering validation round.";
    let duration = "10 mins";

    if (type === "Tech_DSA") { name = "Data Structures & Algorithms"; desc = "Algorithmic thinking & code efficiency." }
    else if (type === "Sys_Design") { name = "System Design & Architecture"; desc = "Designing distributed, resilient applications."; duration = "15 mins" }
    else if (type === "Behavioral") { name = "Behavioral & Cultural Fit"; desc = "Past situations, handling conflicts & core motivations." }
    else if (type === "OA") { name = "Online Coding Challenge (OA)"; desc = "Asynchronous algorithmic assessments." }
    else if (type === "HR") { name = "HR Screening & Background Check"; desc = "Salary expectations, logistics and cultural checks."; duration = "15 mins" }

    const newRound: InterviewRound = {
      id: Date.now().toString(),
      type,
      name,
      duration,
      desc
    };
    setCustomRounds([...customRounds, newRound]);
  };

  const handleRemoveRound = (id: string) => {
    setCustomRounds(customRounds.filter(round => round.id !== id));
  };

  const handleUpdateRoundDuration = (id: string, duration: string) => {
    setCustomRounds(customRounds.map(round =>
      round.id === id ? { ...round, duration } : round
    ));
  };

  // Drag and drop resume handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      setResumeFile(files[0]); // Storing the File object
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      setResumeName(files[0].name);
      setResumeFile(files[0]);
    }
  };


  const savePreferences = async (): Promise<boolean> => {
    const formData = new FormData();
  
    if (resumeFile) {
      formData.append('resume', resumeFile);
    }
    const userId = localStorage.getItem('user');

    const preferences = {
      jobTitle,
      experienceLevel,
      targetCompany,
      customRounds,
      techStack,
      difficulty,
      voiceModel,
      interviewerPersonality,
      selectedLanguage,
      userId
    };
  
    formData.append('preferences', JSON.stringify(preferences));
  
    try {
      const response = await api.post('/api/user_preferences/save_preferences', formData);
      const data: SavePreferencesResponse = response.data;

      if (!data.session_id) {
        throw new Error('Server response did not include a session_id.');
      }

      setSessionId(data.session_id);
      setOaProblem(data.oa_problem ?? null);
      setFirstAgentQuestion(data.first_agent_question ?? null);

      const tokenResponse = await api.get(`/api/webrtc/token/${data.session_id}`, {
        params: {
          mode: 'interview' // This sends ?mode=tutor to FastAPI
        }
      });
      const token = tokenResponse.data.token;
      setLivekitToken(token);

      return true;
    } catch (error: any) {
      console.error("Error saving preferences:", error);
      setSetupError(
        error?.response?.data?.detail ||
        error?.message ||
        'Failed to configure the interview sandbox. Please try again.'
      );
      return false;
    }
  };
  

  const triggerSimulation = async () => {
    setIsLaunching(true);
    setSetupError(null);

    const ok = await savePreferences();
    if (!ok) {
      setIsLaunching(false);
      return;
    }

    setLaunchStep(1);

    const stages = [
      "Configuring LangGraph Multi-Agent Interviewer Tree...",
      "Scraping active metrics & repositories from GitHub...",
      "Parsing experience profile and resume text indexes...",
      "Injecting tech stack contexts to generate dynamic QA schemas...",
      "Launching active simulation sandbox..."
    ];

    let current = 1;
    const interval = setInterval(() => {
      current += 1;
      setLaunchStep(current);
      if (current > stages.length) {
        clearInterval(interval);
        setSimulationComplete(true);
      }
    }, 1200);
  };

  const resetSetup = () => {
    setIsLaunching(false);
    setSimulationComplete(false);
    setLaunchStep(0);
    setTargetCompany('');
    setCustomRounds(DEFAULT_ROUNDS);
    setResumeName(null);
    setResumeText('');
    setSetupError(null);
    setSessionId(null);
    setOaProblem(null);
    setFirstAgentQuestion(null);
  };

  return (
    <div className="min-h-screen bg-[#0A0B0D] text-slate-100 font-sans antialiased selection:bg-indigo-600 selection:text-white relative">
      {/* Background Decorative Mesh Glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-900/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-emerald-950/10 rounded-full blur-[120px] pointer-events-none" />

      {/* HEADER BAR */}
      <header className="border-b border-slate-900 bg-slate-950/20 backdrop-blur-md sticky top-0 z-40 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button 
            onClick={() => navigate('/workspace')} 
            className="mr-2 p-2 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="bg-indigo-600/10 p-2 rounded-lg border border-indigo-500/20">
            <Sparkles className="h-4 w-4 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-sm font-mono font-bold tracking-tight uppercase">
              Configure <span className="text-indigo-400">Interview Mode</span>
            </h1>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>AI Orchestrator Active</span>
          </span>
        </div>
      </header>

      {/* MAIN CONTAINER */}
      {!isLaunching ? (
        <main className="max-w-6xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-12 gap-8 relative z-10">

          {setupError && (
            <div className="lg:col-span-12 bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-mono px-4 py-3 rounded-lg">
              {setupError}
            </div>
          )}
          
          {/* LEFT SIDE: CONFIGURATION COLUMN */}
          <section className="lg:col-span-7 space-y-6">
            <div className="space-y-1">
              <h2 className="text-xl font-bold tracking-tight text-white flex items-center space-x-2">
                <Settings2 className="h-5 w-5 text-indigo-400" />
                <span>Sandbox Parameters</span>
              </h2>
              <p className="text-xs text-slate-400 leading-relaxed">
                Tune the multi-agent graph variables to curate high-fidelity, targeted role simulations.
              </p>
            </div>

            {/* CARD 1: PRIMARY PROFILE IDENTITIES */}
            <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-6 space-y-5 backdrop-blur-xl shadow-xl">
              <h3 className="text-xs font-mono font-semibold text-indigo-400 uppercase tracking-wider flex items-center space-x-2">
                <span className="h-1 w-2 bg-indigo-500 rounded" />
                <span>Target Role & Profile</span>
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Job Title */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-slate-300">Target Job Title</label>
                  <input 
                    type="text" 
                    value={jobTitle} 
                    onChange={(e) => setJobTitle(e.target.value)}
                    className="w-full bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-xs text-slate-100 placeholder-slate-600 transition"
                    placeholder="e.g. Senior Backend Architect"
                  />
                </div>

                {/* Experience Level */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-slate-300">Experience Tier</label>
                  <select 
                    value={experienceLevel} 
                    onChange={(e) => setExperienceLevel(e.target.value)}
                    className="w-full bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-xs text-slate-100 transition"
                  >
                    <option value="Junior">Junior Developer (0-2 years)</option>
                    <option value="Mid">Mid-Level Engineer (2-5 years)</option>
                    <option value="Senior">Senior Engineer (5-8 years)</option>
                    <option value="Lead_Staff">Lead / Staff Engineer (8+ years)</option>
                  </select>
                </div>
              </div>

              {/* Tech Stack Entry */}
              <div className="space-y-2">
                <label className="text-[11px] font-mono text-slate-300">Core Tech Stack (LangGraph Target Scope)</label>
                <div className="flex flex-wrap gap-1.5 p-3 bg-[#020203] border border-slate-900 rounded-lg min-h-[46px]">
                  {techStack.map((tech, idx) => (
                    <span 
                      key={idx} 
                      className="inline-flex items-center space-x-1 px-2.5 py-1 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-md text-[11px] font-mono"
                    >
                      <span>{tech}</span>
                      <button onClick={() => handleRemoveTech(idx)} className="hover:text-indigo-200">
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                  {techStack.length === 0 && (
                    <span className="text-[11px] text-slate-600 self-center font-mono">No technologies defined. Input stack below.</span>
                  )}
                </div>

                {/* Quick Add and Preset Badges */}
                <div className="flex space-x-2 mt-2">
                  <input 
                    type="text" 
                    value={currentTechInput}
                    onChange={(e) => setCurrentTechInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddTech(currentTechInput)}
                    className="flex-1 bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2 text-xs text-slate-100 placeholder-slate-600 transition"
                    placeholder="Type stack (e.g. Docker) and hit Enter..."
                  />
                  <button 
                    onClick={() => handleAddTech(currentTechInput)}
                    className="px-3 py-2 bg-slate-900 hover:bg-slate-800 text-slate-200 rounded-lg text-xs font-mono font-bold transition"
                  >
                    Add
                  </button>
                </div>

                <div className="flex flex-wrap gap-1 mt-2">
                  <span className="text-[10px] text-slate-600 font-mono self-center mr-1">Presets:</span>
                  {PRESET_TECH_STACKS.filter(p => !techStack.includes(p)).slice(0, 6).map((preset) => (
                    <button 
                      key={preset} 
                      onClick={() => handleAddTech(preset)}
                      className="text-[10px] font-mono bg-slate-900/50 hover:bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-2 py-0.5 rounded transition"
                    >
                      +{preset}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* CARD 2: EXTERNAL CONTEXT LINKS */}
            <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-6 space-y-5 backdrop-blur-xl shadow-xl">
              <h3 className="text-xs font-mono font-semibold text-emerald-400 uppercase tracking-wider flex items-center space-x-2">
                <span className="h-1 w-2 bg-emerald-500 rounded" />
                <span>External Portfolio Contexts</span>
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Target Company */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-mono text-slate-300 flex items-center space-x-1.5">
                      <Building2 className="h-3.5 w-3.5 text-indigo-400" />
                      <span>Target Company</span>
                    </label>
                    <span className="text-[9px] bg-indigo-500/10 text-indigo-400 px-1.5 py-0.5 rounded font-mono">Loads preset rounds</span>
                  </div>
                  <input 
                    type="text" 
                    value={targetCompany} 
                    onChange={(e) => setTargetCompany(e.target.value)}
                    className="w-full bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-xs text-slate-100 placeholder-slate-600 transition"
                    placeholder="e.g. Google, Meta, Stripe"
                  />
                </div>
              </div>

              {/* Resume File Drop Area */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-mono text-slate-300">Target Resume / Experience Dossier</label>
                
                <div 
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`border border-dashed rounded-lg p-5 text-center transition flex flex-col items-center justify-center space-y-2 relative ${
                    isDragging 
                      ? 'border-indigo-500 bg-indigo-600/5' 
                      : 'border-slate-800 hover:border-slate-700 bg-slate-900/10'
                  }`}
                >
                  <input 
                    type="file" 
                    className="absolute inset-0 opacity-0 cursor-pointer"
                    onChange={handleFileSelect}
                    accept=".pdf,.txt"
                  />
                  
                  <UploadCloud className="h-5 w-5 text-indigo-400 animate-pulse" />
                  
                  {resumeName ? (
                    <div className="space-y-0.5">
                      <p className="text-xs font-semibold text-emerald-400 flex items-center justify-center space-x-1.5">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        <span>{resumeName} Loaded</span>
                      </p>
                      <button 
                        onClick={(e) => { e.stopPropagation(); setResumeName(null); }} 
                        className="text-[10px] text-red-400 hover:underline relative z-10"
                      >
                        Remove profile
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-0.5">
                      <p className="text-xs text-slate-300">
                        Drag and drop your resume PDF, or <span className="text-indigo-400 underline">browse</span>
                      </p>
                      <p className="text-[9px] text-slate-500">Supports PDF, TXT up to 10MB</p>
                    </div>
                  )}
                </div>

                <div className="flex items-center space-x-2 mt-2">
                  <div className="h-[1px] bg-slate-900 flex-1" />
                  <span className="text-[9px] text-slate-600 font-mono uppercase tracking-wider">or paste content</span>
                  <div className="h-[1px] bg-slate-900 flex-1" />
                </div>

                <textarea 
                  value={resumeText}
                  onChange={(e) => setResumeText(e.target.value)}
                  className="w-full h-20 bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-xs text-slate-100 placeholder-slate-700 transition"
                  placeholder="Paste your resume plain text or past project experiences directly here..."
                />
              </div>
            </div>

            {/* CARD 3: AGENT SETTINGS */}
            <div className="bg-slate-950/40 border border-slate-900 rounded-xl p-6 space-y-5 backdrop-blur-xl shadow-xl">
              <h3 className="text-xs font-mono font-semibold text-indigo-400 uppercase tracking-wider flex items-center space-x-2">
                <span className="h-1 w-2 bg-indigo-500 rounded" />
                <span>AI Agent Tuning Variables</span>
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Difficulty */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-slate-300">Validation Difficulty</label>
                  <select 
                    value={difficulty} 
                    onChange={(e) => setDifficulty(e.target.value)}
                    className="w-full bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-xs text-slate-100 transition"
                  >
                    <option value="Constructive">Constructive (Junior / Guided feedback)</option>
                    <option value="Rigorous (FAANG Style)">Rigorous (FAANG Style / Edge Case deep-dives)</option>
                    <option value="Stress Test">Stress Test (Extreme Performance / Systems limits)</option>
                  </select>
                </div>

                {/* Voice Selection */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-slate-300 flex items-center space-x-1">
                    <Volume2 className="h-3.5 w-3.5 text-indigo-400" />
                    <span>Selected Voice Engine</span>
                  </label>
                  <select 
                    value={voiceModel} 
                    onChange={(e) => setVoiceModel(e.target.value)}
                    className="w-full bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-xs text-slate-100 transition"
                  >
                    {AVAILABLE_VOICES.map((v) => (
                      <option key={v.name} value={v.name}>{v.name} — {v.desc}</option>
                    ))}
                  </select>
                </div>

                {/* Personality */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-slate-300">Interviewer Persona Profile</label>
                  <select 
                    value={interviewerPersonality} 
                    onChange={(e) => setInterviewerPersonality(e.target.value)}
                    className="w-full bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-xs text-slate-100 transition"
                  >
                    <option value="Encouraging">Encouraging & Mentoring</option>
                    <option value="Balanced">Balanced (Neutral & Professional)</option>
                    <option value="Skeptical">Skeptical Engineer (Drills details, architecture-heavy)</option>
                  </select>
                </div>

                {/* Programming Language */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-mono text-slate-300">Preferred Coding Language</label>
                  <select 
                    value={selectedLanguage} 
                    onChange={(e) => setSelectedLanguage(e.target.value)}
                    className="w-full bg-[#0A0B0D] border border-slate-900 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-lg px-4 py-2.5 text-xs text-slate-100 transition"
                  >
                    <option value="Python">Python (Highly Recommended)</option>
                    <option value="TypeScript">TypeScript / JavaScript</option>
                    <option value="Go">Go (Golang)</option>
                    <option value="Java">Java</option>
                    <option value="C++">C++</option>
                    <option value="Rust">Rust</option>
                  </select>
                </div>
              </div>
            </div>
          </section>

          {/* RIGHT SIDE: INTERVIEW TIMELINE BLUEPRINT */}
          <section className="lg:col-span-5 space-y-6 lg:sticky lg:top-24 h-fit">
            <div className="bg-[#0D0E12] border border-slate-900 rounded-xl p-6 shadow-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-full blur-2xl pointer-events-none" />

              <div className="flex items-center justify-between border-b border-slate-900 pb-4">
                <div className="space-y-0.5">
                  <h3 className="text-xs font-mono font-bold text-white flex items-center space-x-1.5">
                    <Layers className="h-4 w-4 text-indigo-400" />
                    <span>Interview Timeline</span>
                  </h3>
                  <p className="text-[10px] font-mono text-slate-500">Updates live dynamically</p>
                </div>
                <span className="text-[10px] font-mono bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded-full">
                  {customRounds.length} Rounds Selected
                </span>
              </div>

              {/* Timeline Tree Visualization */}
              <div className="mt-6 relative pl-6 space-y-4">
                {/* Connective Line */}
                <div className="absolute left-2 top-2 bottom-2 w-[1px] bg-gradient-to-b from-indigo-500 via-purple-500 to-slate-900" />

                {customRounds.map((round, idx) => (
                  <div key={round.id} className="relative group">
                    {/* Node Dot Icon */}
                    <span className="absolute -left-[22px] top-1.5 h-3 w-3 rounded-full border border-[#0D0E12] bg-[#0A0B0D] flex items-center justify-center">
                      <span className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
                    </span>

                    <div className="bg-[#050608] border border-slate-900 hover:border-slate-800 rounded-lg p-3.5 transition-all">
                      <div className="flex items-start justify-between">
                        <div className="space-y-0.5">
                          <div className="flex items-center space-x-2">
                            <span className="text-[9px] font-bold tracking-wider uppercase text-indigo-400 bg-indigo-500/5 px-1.5 py-0.2 rounded font-mono">
                              {round.type}
                            </span>
                            <span className="text-[10px] font-mono font-bold text-slate-500">Round {idx + 1}</span>
                          </div>
                          <h4 className="text-xs font-bold text-slate-200">{round.name}</h4>
                        </div>
                        
                        <div className="flex items-center space-x-2">
                      
                          <select
                            value={round.duration}
                            onChange={(e) => handleUpdateRoundDuration(round.id, e.target.value)}
                            aria-label={`Duration for ${round.name}`}
                            className="text-[9px] font-mono text-slate-400 bg-[#050608] border border-slate-800 rounded px-1.5 py-0.5 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition cursor-pointer hover:border-slate-700 hover:text-white"
                          >
                            {!DURATION_OPTIONS.includes(round.duration) && (
                              <option value={round.duration}>{round.duration}</option>
                            )}
                            {DURATION_OPTIONS.map((opt) => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                          <button 
                            onClick={() => handleRemoveRound(round.id)}
                            className="text-slate-600 hover:text-red-400 transition-colors"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                      <p className="text-[10px] text-slate-500 mt-1.5 leading-relaxed">{round.desc}</p>
                    </div>
                  </div>
                ))}

                {customRounds.length === 0 && (
                  <div className="text-center py-8 text-slate-600 text-xs font-mono">
                    No rounds configured. Click triggers below to compile layout.
                  </div>
                )}
              </div>

              {/* Dynamic Add-Round Action Triggers */}
              <div className="mt-6 pt-5 border-t border-slate-900">
                <p className="text-[10px] text-slate-500 uppercase font-mono font-bold mb-3">Add Custom Validation Blocks</p>
                <div className="grid grid-cols-2 gap-2">
                  <button 
                    onClick={() => handleAddRound('Tech_DSA')}
                    className="flex items-center space-x-1.5 justify-center bg-slate-950/40 hover:bg-slate-950 border border-slate-900 hover:border-slate-800 p-2 rounded-lg text-[10px] font-mono text-slate-300 transition-colors"
                  >
                    <Plus className="h-3 w-3 text-indigo-400" />
                    <span>+ DSA Round</span>
                  </button>
                  <button 
                    onClick={() => handleAddRound('Sys_Design')}
                    className="flex items-center space-x-1.5 justify-center bg-slate-950/40 hover:bg-slate-950 border border-slate-900 hover:border-slate-800 p-2 rounded-lg text-[10px] font-mono text-slate-300 transition-colors"
                  >
                    <Plus className="h-3 w-3 text-indigo-400" />
                    <span>+ Architecture</span>
                  </button>
                  <button 
                    onClick={() => handleAddRound('Behavioral')}
                    className="flex items-center space-x-1.5 justify-center bg-slate-950/40 hover:bg-slate-950 border border-slate-900 hover:border-slate-800 p-2 rounded-lg text-[10px] font-mono text-slate-300 transition-colors"
                  >
                    <Plus className="h-3 w-3 text-indigo-400" />
                    <span>+ Behavioral</span>
                  </button>
                  <button 
                    onClick={() => handleAddRound('OA')}
                    className="flex items-center space-x-1.5 justify-center bg-slate-950/40 hover:bg-slate-950 border border-slate-900 hover:border-slate-800 p-2 rounded-lg text-[10px] font-mono text-slate-300 transition-colors"
                  >
                    <Plus className="h-3 w-3 text-indigo-400" />
                    <span>+ Challenge (OA)</span>
                  </button>
                  <button 
                    onClick={() => handleAddRound('HR')}
                    className="flex items-center space-x-1.5 justify-center bg-slate-950/40 hover:bg-slate-950 border border-slate-900 hover:border-slate-800 p-2 rounded-lg text-[10px] font-mono text-slate-300 transition-colors"
                  >
                    <Plus className="h-3 w-3 text-indigo-400" />
                    <span>+ HR</span>
                  </button>
                </div>
              </div>

              {/* LAUNCH BUTTON */}
              <div className="mt-6">
                <button 
                  onClick={triggerSimulation}
                  disabled={customRounds.length === 0}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold py-3 px-4 rounded-lg shadow-lg shadow-indigo-500/10 hover:shadow-indigo-500/25 transition-all text-xs font-mono flex items-center justify-center space-x-2"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  <span>Launch AI Simulation</span>
                </button>
                <p className="text-[9px] text-slate-600 text-center mt-2.5 font-mono">
                  Compiles sandbox variables & mounts LangGraph evaluation instances.
                </p>
              </div>
            </div>
          </section>

        </main>
      ) : (
        /* LOADING TRANSITION COMPILATION ANIMATIONS */
        <main className="max-w-2xl mx-auto px-6 py-16 text-center relative z-10">
          {!simulationComplete ? (
            <div className="space-y-6 bg-slate-950/40 border border-slate-900 p-10 rounded-xl backdrop-blur-xl shadow-2xl relative overflow-hidden">
              <div className="relative h-16 w-16 mx-auto">
                <div className="absolute inset-0 rounded-full border border-slate-800" />
                <div className="absolute inset-0 rounded-full border border-t-indigo-500 border-l-indigo-500 animate-spin" />
                <div className="absolute inset-3 rounded-full bg-[#0A0B0D] border border-slate-900 flex items-center justify-center">
                  <Cpu className="h-4 w-4 text-indigo-400 animate-pulse" />
                </div>
              </div>

              <div className="space-y-2">
                <h2 className="text-md font-mono font-bold text-white uppercase">Assembling Sandbox Environment...</h2>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Processing state parameters to construct dynamic evaluation routes.
                </p>
              </div>

              {/* Steps validation pipeline */}
              <div className="max-w-sm mx-auto bg-[#050608] border border-slate-900 rounded-lg p-5 text-left space-y-3 font-mono">
                <p className="text-[9px] font-bold text-slate-500 uppercase border-b border-slate-900 pb-2">Compilation Pipeline Logs</p>
                
                <div className="space-y-2">
                  {[
                    "Constructing StateGraphs & validation nodes...",
                    "Checking GitHub API registries for portfolio insights...",
                    "Parsing resume dossier parameters using semantic maps...",
                    "Compiling targeted question libraries for role...",
                    "Configuring audio speech synthesis nodes..."
                  ].map((step, idx) => (
                    <div key={idx} className="flex items-center space-x-2 text-[10px]">
                      {launchStep > idx + 1 ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                      ) : launchStep === idx + 1 ? (
                        <div className="h-3.5 w-3.5 rounded-full border border-indigo-500 border-t-transparent animate-spin shrink-0" />
                      ) : (
                        <div className="h-3.5 w-3.5 rounded-full border border-slate-800 shrink-0" />
                      )}
                      <span className={launchStep > idx + 1 ? "text-slate-400 font-semibold" : launchStep === idx + 1 ? "text-indigo-400 font-bold" : "text-slate-600"}>
                        {step}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* SANDBOX COMPILED SUCCESS CONTAINER */
            <div className="space-y-6 bg-slate-950/40 border border-slate-900 p-10 rounded-xl backdrop-blur-xl shadow-2xl relative overflow-hidden text-center">
              <div className="bg-emerald-500/5 border border-emerald-500/20 p-3 rounded-full w-14 h-14 flex items-center justify-center mx-auto text-emerald-400 shadow-xl shadow-emerald-500/5">
                <CheckCircle2 className="h-6 w-6" />
              </div>

              <div className="space-y-2">
                <h2 className="text-lg font-mono font-bold text-white uppercase">AI Evaluation Sandbox Ready!</h2>
                <p className="text-slate-400 text-xs max-w-sm mx-auto">
                  Your structured interview sandbox is fully compiled and active.
                </p>
              </div>

              {/* Compilation summary box */}
              <div className="max-w-sm mx-auto bg-[#050608] border border-slate-900 rounded-lg p-5 text-left space-y-3 font-mono">
                <p className="text-[9px] font-bold text-slate-500 uppercase border-b border-slate-900 pb-2">Simulation Briefing Dossier</p>
                <div className="space-y-2 text-[10px]">
                  <p className="text-slate-500"><strong className="text-slate-300">Target Role:</strong> {jobTitle} ({experienceLevel})</p>
                  <p className="text-slate-500"><strong className="text-slate-300">Company Context:</strong> {targetCompany || "General Practice Environment"}</p>
                  <p className="text-slate-500"><strong className="text-slate-300">Assigned Rounds:</strong> {customRounds.length} Sessions configured</p>
                  <p className="text-slate-500"><strong className="text-slate-300">Focus Tech:</strong> {selectedLanguage} & {techStack.join(', ')}</p>
                  <p className="text-slate-500"><strong className="text-slate-300">Voice Synthesis:</strong> Enabled ({voiceModel})</p>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <button 
                  onClick={() => {
                    navigate(`/workspace/mock-interview`, {
                      state: {
                        token: livekitToken,
                        sessionId: sessionId,
                        oa_problem: oaProblem,
                        first_agent_question: firstAgentQuestion,
                        preferred_language: selectedLanguage,
                      }
                    });
                  }}
                  disabled={!sessionId || !livekitToken}
                  className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-lg shadow-lg shadow-indigo-500/10 transition-all text-xs font-mono flex items-center justify-center space-x-2"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  <span>Begin Simulation Now</span>
                </button>
                <button 
                  onClick={resetSetup}
                  className="w-full sm:w-auto bg-slate-900 hover:bg-slate-800 text-slate-400 font-bold py-3 px-6 rounded-lg border border-slate-800 transition-all text-xs font-mono flex items-center justify-center space-x-2"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  <span>Configure Variables</span>
                </button>
              </div>
            </div>
          )}
        </main>
      )}
    </div>
  );
}