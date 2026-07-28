import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Room, RoomEvent, Track } from 'livekit-client';
import {
  Volume2,
  Mic,
  MicOff,
  Video,
  VideoOff,
  Cpu,
  Code,
  PenTool,
  Play,
  Send,
  Loader2,
  Trash2,
  User,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  BookOpen,
  Lightbulb,
  LogOut,
  MessageCircle,
} from 'lucide-react';
import api from '../auth/auth';
import Whiteboard from './Practice';

// =====================================================================
// --- TYPE DEFINITIONS & GRAPH SCHEMAS ---
// =====================================================================

interface Message {
  role: 'interviewer' | 'candidate' | 'system';
  text: string;
  timestamp: string;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  timestamp: string;
}

interface GraphState {
  current_node: string;
  session_id: string;
  mode: 'interview' | 'tutor';
  current_round: number;
  total_rounds: number;
  hints_remaining: number;
}

interface ExecutionResult {
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
  compile_stdout: string;
  compile_stderr: string;
}

interface OAProblem {
  title?: string;
  problem_statement?: string;
  function_signature?: string;
  constraints?: string[];
  topic_tags?: string[];
  sample_test_cases?: { input: string; output: string }[];
}

interface RespondResponse {
  status: 'success' | 'completed';
  session_id: string;
  current_round_index?: number;
  active_round_node?: string | null;
  next_agent_question?: string | null;
  oa_problem?: OAProblem | null;
  round_turn_count?: number;
  round_turn_limit?: number;
  round_advanced?: boolean;
  overall_score?: unknown;
  performance_overview?: unknown;
  tutor_hint?: string | null;
}

interface RunResponse {
  result: ExecutionResult;
}

type SupportedLanguage = 'python' | 'javascript' | 'typescript' | 'java' | 'cpp' | 'go';

const LANGUAGE_OPTIONS: { label: string; value: SupportedLanguage }[] = [
  { label: 'Python 3', value: 'python' },
  { label: 'JavaScript', value: 'javascript' },
  { label: 'TypeScript', value: 'typescript' },
  { label: 'Java', value: 'java' },
  { label: 'C++', value: 'cpp' },
  { label: 'Go', value: 'go' },
];


const THIN_SCROLLBAR =
  '[&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-transparent ' +
  '[&::-webkit-scrollbar-thumb]:bg-slate-800 [&::-webkit-scrollbar-thumb]:rounded-full ' +
  '[&::-webkit-scrollbar-thumb:hover]:bg-slate-700 ' +
  '[scrollbar-width:thin] [scrollbar-color:#1e293b_transparent]';


function buildStarterCode(signature: string | undefined | null, lang: string): string {
  if (!signature) return '';
  const sig = signature.trim();
  if (lang === 'python') return `${sig.endsWith(':') ? sig : sig + ':'}\n    # TODO: Implement your solution here\n    pass\n`;
  if (lang === 'javascript' || lang === 'typescript') return `${sig} {\n  // TODO: Implement your solution here\n}\n`;
  if (lang === 'java') return `${sig} {\n    // TODO: Implement your solution here\n}\n`;
  if (lang === 'cpp') return `${sig} {\n    // TODO: Implement your solution here\n}\n`;
  if (lang === 'go') return `${sig} {\n\t// TODO: Implement your solution here\n}\n`;
  return `${sig}\n`;
}

function isSameProblem(a: OAProblem | null | undefined, b: OAProblem | null | undefined): boolean {
  if (!a && !b) return true;
  if (!a || !b) return false;
  return a.function_signature === b.function_signature && a.title === b.title;
}

function parseDurationSeconds(duration: string | undefined | null): number | null {
  if (!duration) return null;
  const digits = duration.replace(/\D/g, '');
  if (!digits) return null;
  return parseInt(digits, 10) * 60;
}

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function MockInterview() {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useParams<{ sessionId?: string }>();
  const livekitToken: string | undefined = location.state?.token;
  const mode = location.state?.mode;
  const isTutorMode = mode === 'tutor';

  const roundsBlueprint: { rounds: { id: string; type: string; name: string; duration: string; max_turns: number; desc: string }[] } =
    location.state?.rounds_blueprint || { rounds: [] };

  const [sessionId, setSessionId] = useState<string | null>(
    location.state?.sessionId || params.sessionId || null
  );
  const [oaProblem, setOaProblem] = useState<OAProblem | null>(
    location.state?.oa_problem || null
  );

  const [activeTab, setActiveTab] = useState<'editor' | 'whiteboard'>(
    isTutorMode ? 'whiteboard' : 'editor'
  );
  const [isMuted, setIsMuted] = useState(false);
  const [isCameraOn, setIsCameraOn] = useState(true);
  const [livekitRoom, setLivekitRoom] = useState<Room | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const [interviewerStatus, setInterviewerStatus] = useState("Initializing WebRTC Handshake...");
  const [interviewerSpeaking, setInterviewerSpeaking] = useState(false);
  const [userSpeaking, setUserSpeaking] = useState(false);
  const [tutorHint, setTutorHint] = useState<string | null>(null);

  const [language, setLanguage] = useState<SupportedLanguage>(
    location.state?.preferred_language || 'python'
  );
  const [sourceCode, setSourceCode] = useState<string>(
    buildStarterCode(
      location.state?.oa_problem?.function_signature,
      location.state?.preferred_language || 'python'
    )
  );
  const [lines, setLines] = useState<string[]>([]);

  const [tutorQuestion] = useState<string | null>(location.state?.question ?? null);
  const [tutorHints] = useState<string[] | string | null>(location.state?.hints ?? null);
  const [isFinishing, setIsFinishing] = useState(false);

  // --- CHAT (tutor mode concept Q&A) ---
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [isAskingConcept, setIsAskingConcept] = useState(false);

  const [stdin, setStdin] = useState<string>('');

  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<ExecutionResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [accompanyingMessage, setAccompanyingMessage] = useState('');

  const [roundTurnCount, setRoundTurnCount] = useState(
    location.state?.round_turn_count ?? 0
  );
  const [currentRoundIndex, setCurrentRoundIndex] = useState(0);
  const [interviewCompleted, setInterviewCompleted] = useState(false);
  const [finalFeedback, setFinalFeedback] = useState<{
    overall_score: unknown;
    performance_overview: unknown;
  } | null>(null);

  const [roundAdvanceNotice, setRoundAdvanceNotice] = useState<string | null>(null);

  const [roundStartedAt, setRoundStartedAt] = useState<Date>(() => new Date());
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const isSubmittingRef = useRef(false);
  const interviewCompletedRef = useRef(false);

  useEffect(() => { isSubmittingRef.current = isSubmitting; }, [isSubmitting]);
  useEffect(() => { interviewCompletedRef.current = interviewCompleted; }, [interviewCompleted]);

  useEffect(() => {
    const currentRoundConfig = roundsBlueprint.rounds[currentRoundIndex];
    const durationSeconds = parseDurationSeconds(currentRoundConfig?.duration);

    if (durationSeconds === null || interviewCompleted) {
      setSecondsRemaining(null);
      return;
    }

    const tick = () => {
      const elapsed = Math.floor((Date.now() - roundStartedAt.getTime()) / 1000);
      const remaining = Math.max(0, durationSeconds - elapsed);
      setSecondsRemaining(remaining);
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [roundStartedAt, currentRoundIndex, roundsBlueprint, interviewCompleted]);

  useEffect(() => {
    if (secondsRemaining !== 0) return;
    if (interviewCompletedRef.current) return;
    if (isSubmittingRef.current) return;

    setTranscripts(prev => [...prev, {
      role: 'system',
      text: `Time's up for Round ${currentRoundIndex + 1}. Your current solution has been submitted automatically.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }]);
    setLogs(prev => [...prev, `[TIMER] Round ${currentRoundIndex + 1} duration expired — triggering auto-submit.`]);

    const autoSubmit = async () => {
      await handleSubmitCore({ isTimer: true });
    };
    autoSubmit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [secondsRemaining]);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [color, setColor] = useState('#818cf8');
  const [lineWidth, setLineWidth] = useState(3);

  const [graphState, setGraphState] = useState<GraphState>({
    current_node: 'INITIALIZE',
    session_id: sessionId || 'syncing...',
    mode: 'interview',
    current_round: 1,
    total_rounds: roundsBlueprint.rounds.length,
    hints_remaining: 3,
  });

  const [logs, setLogs] = useState<string[]>([
    "[SYSTEM] Initiating voice connection node...",
    "[SYSTEM] WebRTC audio handshake completed successfully.",
    "[LANGGRAPH] Routing -> State: INITIALIZE",
  ]);

  const [transcripts, setTranscripts] = useState<Message[]>(() => {
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const initialQuestion: string | undefined =
      location.state?.first_agent_question ||
      location.state?.oa_problem?.problem_statement ||
      location.state?.question;
    if (initialQuestion) {
      return [{ role: 'interviewer', text: initialQuestion, timestamp: now }];
    }
    return [{
      role: 'system',
      text: 'No initial question was received. The problem may have failed to generate — return to setup and try again.',
      timestamp: now,
    }];
  });

  useEffect(() => {
    setLines(sourceCode.split('\n'));
  }, [sourceCode]);

  const applyOaProblemUpdate = useCallback((incoming: OAProblem | null | undefined) => {
    const next = incoming ?? null;
    setOaProblem(prev => {
      if (isSameProblem(prev, next)) return prev;
      setSourceCode(buildStarterCode(next?.function_signature, language));
      return next;
    });
  }, [language]);

  // --- LIVEKIT ---
  useEffect(() => {
    if (!livekitToken) {
      setLogs(prev => [...prev, "[ERROR] Missing session pipeline token parameter."]);
      return;
    }
    const room = new Room({ adaptiveStream: true, dynacast: true });
    async function connectToAudioGateway() {
      try {
        await room.connect("ws://localhost:7880", livekitToken as string);
        setLivekitRoom(room);
        setIsConnected(true);
        setGraphState(prev => ({ ...prev, session_id: room.name }));
        setSessionId(prev => prev ?? room.name);
        setLogs(prev => [...prev, `[WEBRTC] Connected: ${room.name}`]);
        await room.localParticipant.setMicrophoneEnabled(true);
        room.localParticipant.on('isSpeakingChanged', (speaking: boolean) => setUserSpeaking(speaking));
        room.on(RoomEvent.TrackSubscribed, (track) => {
          if (track.kind === Track.Kind.Audio) {
            const el = track.attach();
            document.body.appendChild(el);
          }
        });
        room.on(RoomEvent.DataReceived, (payload, _p, _k, topic) => {
          if (topic === "agent_events") {
            const rawData = JSON.parse(new TextDecoder().decode(payload));
            if (rawData.type === "state_update") {
              setInterviewerStatus(rawData.data.message);
              setInterviewerSpeaking(rawData.data.status === "speaking");
              setLogs(prev => [...prev, `[LANGGRAPH] ${rawData.data.message}`]);
              if (rawData.data.status === "speaking") {
                setTranscripts(prev => [...prev, {
                  role: 'interviewer',
                  text: rawData.data.message,
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                }]);
              }
            }
            if (rawData.type === "tutor_hint") {
              setTutorHint(rawData.data.hint);
              setLogs(prev => [...prev, "[TELEMETRY] Hint loaded."]);
            }
          }
        });
      } catch (err: any) {
        setLogs(prev => [...prev, `[CRITICAL] Connection failure: ${err.message}`]);
      }
    }
    connectToAudioGateway();
    return () => { room.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [livekitToken]);

  useEffect(() => {
    if (livekitRoom) livekitRoom.localParticipant.setMicrophoneEnabled(!isMuted);
  }, [isMuted, livekitRoom]);

  useEffect(() => {
    if (activeTab === 'whiteboard' && canvasRef.current) {
      const ctx = canvasRef.current.getContext('2d');
      if (ctx) { ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.strokeStyle = color; ctx.lineWidth = lineWidth; }
    }
  }, [activeTab, color, lineWidth]);

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const ctx = canvasRef.current.getContext('2d');
    if (ctx) { ctx.beginPath(); ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top); setIsDrawing(true); }
  };
  const draw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const ctx = canvasRef.current.getContext('2d');
    if (ctx) { ctx.strokeStyle = color; ctx.lineWidth = lineWidth; ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top); ctx.stroke(); }
  };
  const clearCanvas = () => {
    if (!canvasRef.current) return;
    const ctx = canvasRef.current.getContext('2d');
    if (ctx) ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
  };

  const handleFinishTutor = async () => {
    if (isFinishing) return;
    setIsFinishing(true);
    try {
      if (sessionId) {
        await api.post(`api/system-design/session/${sessionId}/stop`);
      }
    } catch (err) {
      console.error('Failed to stop tutor session:', err);
    } finally {
      livekitRoom?.disconnect();
      setIsFinishing(false);
      navigate('/workspace');
    }
  };

  // --- CONCEPT CHAT (routed to concept_qa_node via /ask-concept) ---
  const handleAskConcept = async () => {
    const question = chatInput.trim();
    if (!question || isAskingConcept || !sessionId) return;

    setChatInput('');
    setIsAskingConcept(true);

    const askedAt = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setChatMessages(prev => [...prev, { role: 'user', text: question, timestamp: askedAt }]);

    try {
      const res = await api.post(`api/system-design/session/${sessionId}/ask-concept`, { question });
      const answer: string = res.data?.answer || "Sorry, I couldn't generate an explanation just now.";
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        text: answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }]);
    } catch (err: any) {
      setChatMessages(prev => [...prev, {
        role: 'assistant',
        text: "I had trouble generating that explanation. Please try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }]);
    } finally {
      setIsAskingConcept(false);
    }
  };


  const handleRun = async () => {
    setIsRunning(true);
    setRunResult(null);
    setLogs(prev => [...prev, "[SYSTEM] Running code..."]);
    try {
      const res = await api.post<RunResponse>('api/code/run', {
        language,
        source_code: sourceCode,
        stdin: stdin || null,
        args: [],
      });
      setRunResult(res.data.result);
      setLogs(prev => [...prev, `[EXEC] exit ${res.data.result.exit_code}`]);
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Unknown run error';
      setLogs(prev => [...prev, `[ERROR] Run failed: ${message}`]);
      setRunResult({ stdout: '', stderr: message, exit_code: 1, timed_out: false, compile_stdout: '', compile_stderr: '' });
    } finally {
      setIsRunning(false);
    }
  };

  const handleSubmitCore = useCallback(async (opts?: { isTimer?: boolean }) => {
    if (!sessionId) {
      setSubmitError("No active session_id — start an interview from the setup screen first.");
      return;
    }
    if (isSubmittingRef.current) return;

    const isTimer = opts?.isTimer ?? false;

    setIsSubmitting(true);
    isSubmittingRef.current = true;
    setSubmitError(null);

    if (!isTimer) {
      setTranscripts(prev => [...prev, {
        role: 'candidate',
        text: accompanyingMessage || `[Submitted ${language} solution, ${lines.length} lines]`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }]);
    }
    setLogs(prev => [...prev, isTimer
      ? "[TIMER] Auto-submitting current solution — round duration expired."
      : "[LANGGRAPH] Submitting candidate solution..."
    ]);

    try {
      const res = await api.post<RespondResponse>(`api/code/${sessionId}/submit`, {
        language,
        source_code: sourceCode,
        stdin: stdin || null,
        args: [],
        accompanying_message: isTimer ? '' : accompanyingMessage,
        is_timer_submission: isTimer,
      });

      const data = res.data;

      if (!isTimer) setAccompanyingMessage('');

      if (data.status === 'completed') {
        setInterviewCompleted(true);
        interviewCompletedRef.current = true;
        setFinalFeedback({ overall_score: data.overall_score, performance_overview: data.performance_overview });
        setLogs(prev => [...prev, "[LANGGRAPH] Interview complete."]);
        setTranscripts(prev => [...prev, {
          role: 'system',
          text: 'Interview complete. Final feedback has been generated.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }]);
        return;
      }

      const newRoundIndex = data.current_round_index ?? currentRoundIndex;
      setRoundTurnCount(data.round_turn_count ?? 0);
      setCurrentRoundIndex(newRoundIndex);
      applyOaProblemUpdate(data.oa_problem);

      if (data.round_advanced) {
        setRoundStartedAt(new Date());

        const newRoundConfig = roundsBlueprint.rounds[newRoundIndex];
        const noticeName = newRoundConfig?.name || `Round ${newRoundIndex + 1}`;
        const noticeDuration = newRoundConfig?.duration || '';

        setRoundAdvanceNotice(`Round ${currentRoundIndex + 1} complete — entering ${noticeName}${noticeDuration ? ` (${noticeDuration})` : ''}`);
        setTimeout(() => setRoundAdvanceNotice(null), 6000);

        setTranscripts(prev => [...prev, {
          role: 'system',
          text: `--- Round ${currentRoundIndex + 1} complete. Now starting: ${noticeName} ---`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }]);
        setLogs(prev => [...prev, `[LANGGRAPH] Round advanced → index ${newRoundIndex} (${noticeName})`]);
      } else {
        setLogs(prev => [...prev, `[LANGGRAPH] Turn ${data.round_turn_count} recorded in ${data.active_round_node || ''}.`]);
      }

      if (data.tutor_hint) setTutorHint(data.tutor_hint);

      if (data.next_agent_question) {
        setTranscripts(prev => [...prev, {
          role: 'interviewer',
          text: data.next_agent_question as string,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }]);
      }
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Submit failed';
      setSubmitError(message);
      setLogs(prev => [...prev, `[ERROR] Submit failed: ${message}`]);
    } finally {
      setIsSubmitting(false);
      isSubmittingRef.current = false;
    }
  }, [sessionId, accompanyingMessage, language, sourceCode, stdin, lines, currentRoundIndex, roundsBlueprint, applyOaProblemUpdate]);

  const handleSubmit = () => handleSubmitCore({ isTimer: false });

  const handleWhiteboardFeedback = useCallback((feedback: string) => {
    setTranscripts(prev => [...prev, {
      role: 'interviewer',
      text: feedback,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }]);
    setLogs(prev => [...prev, "[LANGGRAPH] Whiteboard feedback received."]);
  }, []);
  const currentRoundConfig = roundsBlueprint.rounds[currentRoundIndex];
  const durationSeconds = parseDurationSeconds(currentRoundConfig?.duration);

  const countdownUrgent = secondsRemaining !== null && secondsRemaining <= 120;
  const countdownCritical = secondsRemaining !== null && secondsRemaining <= 30;

  return (
    <div className="h-screen bg-[#07080a] text-slate-100 font-sans antialiased flex flex-col relative overflow-hidden">

      <div className="absolute top-[-20%] left-[-20%] w-[60%] h-[60%] bg-indigo-900/5 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-20%] w-[60%] h-[60%] bg-emerald-950/5 rounded-full blur-[140px] pointer-events-none" />

      {/* HEADER */}
      <header className="h-14 shrink-0 overflow-hidden border-b border-slate-900 bg-slate-950/40 backdrop-blur-md px-6 flex items-center justify-between z-20">
        <div className="flex items-center space-x-3 min-w-0">
          <div className="bg-indigo-600/10 p-1.5 rounded-lg border border-indigo-500/20 shrink-0">
            <Cpu className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="flex items-center space-x-2 min-w-0">
            <span className="text-xs font-mono font-bold tracking-tight text-white uppercase whitespace-nowrap">Horizon Active Sandbox</span>
            <span className="text-[10px] bg-slate-900 border border-slate-800 text-slate-500 font-mono px-1.5 py-0.5 rounded max-w-[160px] truncate">
              {graphState.session_id}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          {roundAdvanceNotice && (
            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-mono border bg-emerald-500/10 text-emerald-400 border-emerald-500/25 animate-pulse max-w-[280px] truncate">
              {roundAdvanceNotice}
            </span>
          )}

          {secondsRemaining !== null && !interviewCompleted && (
            <span className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono border transition-colors whitespace-nowrap ${
              countdownCritical
                ? 'bg-red-500/20 text-red-300 border-red-500/40 animate-pulse'
                : countdownUrgent
                ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                : 'bg-slate-900/60 text-slate-400 border-slate-800'
            }`}>
              {countdownCritical ? <AlertTriangle className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
              <span>
                {currentRoundConfig?.name || `Round ${currentRoundIndex + 1}`}
                {' · '}
                {formatCountdown(secondsRemaining)}
              </span>
            </span>
          )}

          {!isTutorMode && (
            <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono border bg-slate-900/60 text-slate-400 border-slate-800 whitespace-nowrap">
              <span>Round {currentRoundIndex + 1}/{roundsBlueprint.rounds.length} · Turn {roundTurnCount}</span>
            </span>
          )}

          <span className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono border whitespace-nowrap ${
            isConnected ? 'bg-indigo-500/10 text-indigo-400 border-indigo-500/25' : 'bg-red-500/10 text-red-400 border-red-500/25'
          }`}>
            <span className={`h-1.5 w-1.5 rounded-full ${isConnected ? 'bg-indigo-400 animate-pulse' : 'bg-red-400'}`} />
            <span>{isConnected ? "WebRTC Active" : "Stream Broken"}</span>
          </span>

          {isTutorMode && (
            <button
              onClick={handleFinishTutor}
              disabled={isFinishing}
              className="flex items-center space-x-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 font-mono font-bold text-[10px] px-3 py-1.5 rounded-lg transition disabled:opacity-50 whitespace-nowrap"
            >
              {isFinishing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogOut className="w-3.5 h-3.5" />}
              <span>{isFinishing ? 'Ending...' : 'Finish'}</span>
            </button>
          )}
        </div>
      </header>

      {/* MAIN LAYOUT */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 overflow-hidden relative z-10">

        {/* LEFT — VOICE HUD / CHAT */}
        <section className="lg:col-span-5 min-h-0 border-r border-slate-900 bg-slate-950/20 flex flex-col h-full overflow-hidden">
          <div className={`flex-1 min-h-0 p-4 flex flex-col space-y-4 overflow-y-auto ${THIN_SCROLLBAR}`}>

            {isTutorMode && (tutorQuestion || tutorHints) && (
              <div className="bg-slate-950/60 border border-emerald-500/20 rounded-xl p-4 space-y-3 shadow-lg shrink-0">
                <div className="flex items-center space-x-2">
                  <BookOpen className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-mono font-bold text-emerald-400 uppercase tracking-wider">
                    System Design Question
                  </span>
                </div>
                {tutorQuestion && (
                  <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">{tutorQuestion}</p>
                )}
                {tutorHints && (
                  <div className="pt-2 border-t border-slate-800 space-y-1.5">
                    <div className="flex items-center space-x-1.5">
                      <Lightbulb className="w-3 h-3 text-amber-400" />
                      <span className="text-[10px] font-mono font-bold text-amber-400 uppercase tracking-wider">Hints</span>
                    </div>
                    {Array.isArray(tutorHints) ? (
                      <ul className="list-disc list-inside space-y-1">
                        {tutorHints.map((h, i) => (
                          <li key={i} className="text-[11px] text-slate-400 leading-relaxed">{h}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-[11px] text-slate-400 leading-relaxed whitespace-pre-wrap">{tutorHints}</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {isTutorMode ? (
              <div className="flex-1 min-h-[320px] bg-slate-950/60 border border-slate-900 rounded-xl overflow-hidden flex flex-col shadow-lg">
                <div className="px-4 py-3 border-b border-slate-900 bg-slate-950/80 flex items-center space-x-2 shrink-0">
                  <MessageCircle className="w-4 h-4 text-indigo-400" />
                  <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
                    Ask a Concept Question
                  </span>
                </div>

                <div className={`flex-1 min-h-0 overflow-y-auto p-4 space-y-3 ${THIN_SCROLLBAR}`}>
                  {chatMessages.length === 0 && !isAskingConcept && (
                    <div className="h-full flex items-center justify-center text-center px-6">
                      <p className="text-[11px] text-slate-600 italic leading-relaxed max-w-[260px]">
                        Ask about any concept — consistency models, sharding strategies, caching
                        patterns, whatever's unclear — and get a full written explanation.
                      </p>
                    </div>
                  )}
                  {chatMessages.map((msg, idx) => (
                    <div key={idx} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                      <div className={`max-w-[92%] rounded-lg px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                        msg.role === 'user'
                          ? 'bg-indigo-600/10 border border-indigo-500/20 text-indigo-200'
                          : 'bg-slate-900 border border-slate-800 text-slate-300'
                      }`}>
                        <p>{msg.text}</p>
                        <span className="text-[8px] text-slate-500 font-mono block mt-1 text-right">{msg.timestamp}</span>
                      </div>
                    </div>
                  ))}
                  {isAskingConcept && (
                    <div className="flex items-center space-x-2 text-slate-500 text-[11px]">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Putting together a full explanation...</span>
                    </div>
                  )}
                </div>

                <div className="p-3 border-t border-slate-900 bg-slate-950/80 flex items-center space-x-2 shrink-0">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleAskConcept();
                      }
                    }}
                    placeholder="Ask about a concept, e.g. 'When should I use CQRS here?'"
                    disabled={isAskingConcept}
                    className="flex-1 bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-300 outline-none focus:border-indigo-500/40 disabled:opacity-50"
                  />
                  <button
                    onClick={handleAskConcept}
                    disabled={isAskingConcept || !chatInput.trim()}
                    className="flex items-center justify-center bg-indigo-600 hover:bg-indigo-500 text-white p-2.5 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isAskingConcept ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            ) : (
              <>
                {/* Candidate stream — interview mode only */}
                <div className="h-1/2 bg-slate-950/80 border border-slate-900 rounded-xl overflow-hidden relative group flex flex-col justify-between shadow-lg">
                  {isCameraOn ? (
                    <div className="absolute inset-0 bg-[#0E1014] flex items-center justify-center">
                      <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent z-10" />
                      <div className="w-16 h-16 rounded-full bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center">
                        <User className="w-8 h-8 text-indigo-400" />
                      </div>
                    </div>
                  ) : (
                    <div className="absolute inset-0 bg-slate-950 flex flex-col items-center justify-center">
                      <VideoOff className="w-8 h-8 text-slate-700 mb-2" />
                      <p className="text-[10px] font-mono text-slate-600">Video source inactive</p>
                    </div>
                  )}
                  {userSpeaking && (
                    <div className="absolute top-4 right-4 z-20 flex items-center space-x-1 bg-indigo-500/10 border border-indigo-500/25 px-2.5 py-1 rounded-lg">
                      <div className="h-2 w-1 bg-indigo-400 animate-bounce" />
                      <div className="h-3 w-1 bg-indigo-400 animate-bounce [animation-delay:0.2s]" />
                      <div className="h-1 w-1 bg-indigo-400 animate-bounce [animation-delay:0.4s]" />
                      <span className="text-[9px] font-mono font-bold text-indigo-400 uppercase">Speaking</span>
                    </div>
                  )}
                  <div className="p-3 z-10 relative">
                    <span className="text-[9px] font-mono font-bold bg-slate-900/80 border border-slate-800 text-slate-400 px-2 py-1 rounded">
                      Local Stream (Candidate)
                    </span>
                  </div>
                  <div className="p-3 z-10 relative bg-slate-950/80 border-t border-slate-900/60 flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-slate-300">Workspace Candidate</span>
                    <div className="flex space-x-1.5">
                      <button onClick={() => setIsMuted(!isMuted)} className={`p-1.5 rounded-lg border transition ${isMuted ? 'bg-red-500/10 border-red-500/30 text-red-400' : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'}`}>
                        {isMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                      </button>
                      <button onClick={() => setIsCameraOn(!isCameraOn)} className="p-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-slate-400 hover:text-white transition">
                        {isCameraOn ? <Video className="w-3.5 h-3.5" /> : <VideoOff className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* AI Interviewer avatar — interview mode only */}
                <div className="h-1/2 bg-[#08090C] border border-slate-900 rounded-xl overflow-hidden relative flex flex-col justify-between shadow-lg">
                  <div className="absolute top-4 right-4 z-20">
                    <span className="text-[9px] font-mono font-bold bg-slate-900 border border-slate-800 text-slate-500 px-2 py-1 rounded">Latency Flow Secure</span>
                  </div>
                  <div className="flex-1 flex flex-col items-center justify-center p-6 relative">
                    <div className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 relative ${
                      interviewerSpeaking ? 'bg-indigo-500/20 border-2 border-indigo-400/80 scale-105 shadow-[0_0_30px_rgba(99,102,241,0.25)]' : 'bg-slate-900 border border-slate-800'
                    }`}>
                      <Cpu className={`w-8 h-8 ${interviewerSpeaking ? 'text-indigo-400' : 'text-slate-600'}`} />
                      {interviewerSpeaking && (
                        <>
                          <div className="absolute inset-0 rounded-full border border-indigo-500/30 animate-ping" />
                          <div className="absolute inset-2 rounded-full border border-indigo-400/20 animate-pulse" />
                        </>
                      )}
                    </div>
                    <div className="mt-3 text-center space-y-1">
                      <p className="text-xs font-mono font-bold text-slate-200">AI Core Tutor Agent</p>
                      <p className="text-[10px] font-mono text-indigo-400 font-medium">{interviewerStatus}</p>
                    </div>
                  </div>
                  <div className="p-3 border-t border-slate-900 bg-[#060709] flex items-center justify-between">
                    <span className="text-[9px] font-mono font-bold bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 px-2 py-0.5 rounded uppercase">Interviewer Streaming</span>
                    <button className="p-1.5 bg-slate-900 border border-slate-800 rounded-lg text-slate-400 hover:text-white transition">
                      <Volume2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>

        {/* RIGHT — CODE ENGINE / WHITEBOARD (unchanged) */}
        <section className="lg:col-span-7 min-h-0 flex flex-col h-full overflow-hidden bg-slate-950/40">

          <div className="h-11 shrink-0 border-b border-slate-900 bg-slate-950/60 px-4 flex items-center justify-between">
            <div className="flex space-x-1">
              {!isTutorMode && (
                <button onClick={() => setActiveTab('editor')} className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-mono font-bold transition ${activeTab === 'editor' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'text-slate-500 hover:text-slate-300'}`}>
                  <Code className="w-3.5 h-3.5" /><span>Compiler Sandbox</span>
                </button>
              )}
              <button onClick={() => setActiveTab('whiteboard')} className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-mono font-bold transition ${activeTab === 'whiteboard' ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'text-slate-500 hover:text-slate-300'}`}>
                <PenTool className="w-3.5 h-3.5" /><span>System Whiteboard</span>
              </button>
            </div>
            {activeTab === 'editor' && !isTutorMode && (
              <select value={language} onChange={(e) => setLanguage(e.target.value as SupportedLanguage)} className="bg-slate-900 border border-slate-800 text-slate-300 text-[10px] font-mono font-bold rounded-md px-2 py-1 outline-none focus:border-indigo-500/40">
                {LANGUAGE_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            )}
          </div>

          <div className="flex-1 min-h-0 overflow-hidden relative flex flex-col">
            {activeTab === 'editor' && !isTutorMode && (
              <div className="h-full flex flex-col bg-[#050608] font-mono text-xs overflow-hidden">

                {oaProblem?.problem_statement && (
                  <div className={`mx-4 mt-4 p-3 bg-slate-900/60 border border-slate-800 rounded-lg text-slate-300 text-[11px] space-y-1 max-h-40 overflow-y-auto shrink-0 ${THIN_SCROLLBAR}`}>
                    {oaProblem.title && <strong className="block text-xs text-slate-100 font-mono mb-1">{oaProblem.title}</strong>}
                    <p className="whitespace-pre-wrap leading-relaxed">{oaProblem.problem_statement}</p>
                    {oaProblem.sample_test_cases && oaProblem.sample_test_cases.length > 0 && (
                      <div className="mt-2 space-y-1 border-t border-slate-800 pt-2">
                        <span className="text-[9px] font-bold uppercase text-slate-500">Sample Test Cases</span>
                        {oaProblem.sample_test_cases.map((tc, i) => (
                          <div key={i} className="text-[10px] font-mono">
                            <span className="text-slate-500">Input:</span>{' '}
                            <span className="text-slate-300">{tc.input}</span>
                            {' → '}
                            <span className="text-slate-500">Output:</span>{' '}
                            <span className="text-emerald-400">{tc.output}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {tutorHint && (
                  <div className="mx-4 mt-2 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400 text-[11px] shrink-0">
                    <strong className="block text-xs uppercase mb-0.5 tracking-wider font-mono">💡 Guardrail Warning:</strong>
                    {tutorHint}
                  </div>
                )}

                {interviewCompleted && finalFeedback && (
                  <div className="mx-4 mt-4 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-emerald-300 text-[11px] space-y-1 shrink-0">
                    <strong className="block text-xs uppercase tracking-wider font-mono">Interview Complete</strong>
                    <p>Overall score: {JSON.stringify(finalFeedback.overall_score)}</p>
                    {finalFeedback.performance_overview != null && (
                      <p className="text-emerald-400/80">{JSON.stringify(finalFeedback.performance_overview)}</p>
                    )}
                  </div>
                )}

                <div className={`flex-1 min-h-0 overflow-auto flex p-4 relative ${THIN_SCROLLBAR}`}>
                  <div className="text-slate-600 select-none text-right pr-4 border-r border-slate-900/60 mr-4 space-y-1.5">
                    {lines.map((_, i) => <div key={i}>{i + 1}</div>)}
                  </div>
                  <textarea
                    value={sourceCode}
                    onChange={(e) => setSourceCode(e.target.value)}
                    disabled={interviewCompleted}
                    placeholder={oaProblem?.function_signature ? '' : 'No problem signature available for this round yet.'}
                    className="flex-1 bg-transparent border-none outline-none resize-none text-slate-300 leading-relaxed font-mono h-full disabled:opacity-50"
                    spellCheck="false"
                  />
                </div>

                {runResult && (
                  <div className={`mx-4 mb-3 max-h-32 overflow-y-auto bg-slate-950 border border-slate-900 rounded-lg p-3 text-[11px] font-mono shrink-0 ${THIN_SCROLLBAR}`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-slate-500 uppercase text-[9px] font-bold tracking-wider">Execution Output</span>
                      <span className={`inline-flex items-center space-x-1 text-[9px] font-bold ${runResult.exit_code === 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {runResult.exit_code === 0 ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        <span>exit {runResult.exit_code}{runResult.timed_out ? ' · timed out' : ''}</span>
                      </span>
                    </div>
                    {runResult.compile_stderr && <pre className="text-amber-400 whitespace-pre-wrap mb-1">{runResult.compile_stderr}</pre>}
                    {runResult.stdout && <pre className="text-slate-300 whitespace-pre-wrap">{runResult.stdout}</pre>}
                    {runResult.stderr && <pre className="text-red-400 whitespace-pre-wrap">{runResult.stderr}</pre>}
                    {!runResult.stdout && !runResult.stderr && !runResult.compile_stderr && (
                      <p className="text-slate-600">No output produced.</p>
                    )}
                  </div>
                )}

                {submitError && (
                  <div className="mx-4 mb-3 p-2.5 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-[11px] shrink-0">
                    {submitError}
                  </div>
                )}

                <div className="border-t border-slate-900 bg-slate-950/60 px-4 py-3 space-y-2 shrink-0">
                  <input
                    type="text"
                    value={stdin}
                    onChange={(e) => setStdin(e.target.value)}
                    placeholder="stdin — custom input piped to your program on Run and Submit..."
                    disabled={interviewCompleted}
                    className="w-full bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-1.5 text-[11px] text-slate-300 font-mono outline-none focus:border-indigo-500/40 disabled:opacity-50"
                  />
                  <input
                    type="text"
                    value={accompanyingMessage}
                    onChange={(e) => setAccompanyingMessage(e.target.value)}
                    placeholder="Explain your approach (optional) — sent with Submit..."
                    disabled={interviewCompleted}
                    className="w-full bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-1.5 text-[11px] text-slate-300 outline-none focus:border-indigo-500/40 disabled:opacity-50"
                  />
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-600">{LANGUAGE_OPTIONS.find(o => o.value === language)?.label}</span>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={handleRun}
                        disabled={isRunning || interviewCompleted}
                        className="flex items-center space-x-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 font-bold text-xs px-3 py-1.5 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
                        <span>{isRunning ? 'Running...' : 'Run'}</span>
                      </button>
                      <button
                        onClick={handleSubmit}
                        disabled={isSubmitting || interviewCompleted}
                        className="flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs px-3 py-1.5 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                        <span>{isSubmitting ? 'Submitting...' : 'Submit Answer'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'whiteboard' && (
              <div className="h-full flex flex-col bg-[#07080B] overflow-hidden">
                <Whiteboard sessionId={sessionId} onFeedback={handleWhiteboardFeedback} />
              </div>
            )}
          </div>

          <footer className="h-10 shrink-0 border-t border-slate-900 bg-[#060709] px-6 flex items-center justify-between font-mono text-[10px] text-slate-500">
            <span>Core Router: <strong className="text-indigo-400">langgraph_distributed_worker</strong></span>
            <span>Status: Pipes Synced Cleanly</span>
          </footer>
        </section>
      </div>
    </div>
  );
}