import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import SignIn from './pages/SignIn';
import SignUp from './pages/SignUp';
// 1. Import your secure WorkspaceHome dashboard component
import WorkspaceHome from './pages/WorkHomePage'; 
import InterviewSetup from './pages/Interview';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/signin" element={<SignIn />} />
        <Route path="/signup" element={<SignUp />} />
        
        {/* 2. Register the secure /workspace route */}
        <Route path="/workspace" element={<WorkspaceHome />} />
        <Route path="/workspace/interview-mode" element={<InterviewSetup />} />
      </Routes>
    </BrowserRouter>
  );
}