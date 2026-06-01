import { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import LiveSession from './pages/LiveSession';
import Replay from './pages/Replay';
import Analysis from './pages/Analysis';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/*" element={
            <>
              <Navbar />
              <main className="main-content">
                <Routes>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/live" element={<LiveSession />} />
                  <Route path="/replay" element={<Replay />} />
                  <Route path="/analysis" element={<Analysis />} />
                </Routes>
              </main>
            </>
          } />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
