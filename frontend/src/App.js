import React, { useState } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Dashboard from './components/Dashboard';
import MediaManager from './components/MediaManager';
import Settings from './components/Settings';
import Login from './components/Login';
import './App.css';

function AppContent() {
  const { auth, logout } = useAuth();
  const [activeTab, setActiveTab] = useState('dashboard');

  if (!auth) {
    return <Login />;
  }

  // Define tabs with role-based access
  const allTabs = [
    { id: 'dashboard', label: 'Dashboard', icon: 'fa-th-large', roles: ['user', 'admin', 'superuser'] },
    { id: 'media', label: 'Media Manager', icon: 'fa-film', roles: ['admin', 'superuser'] },
    { id: 'settings', label: 'Settings', icon: 'fa-cog', roles: ['superuser'] },
  ];

  const tabs = allTabs.filter(tab => tab.roles.includes(auth.role));

  // Reset tab if user doesn't have access to current tab
  if (!tabs.find(t => t.id === activeTab)) {
    setActiveTab(tabs[0]?.id || 'dashboard');
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-brand">
          <img src="/assets/alairo-logo.png" alt="Alairo Solutions" className="header-logo" />
          <h1>CareStream</h1>
          <span className="header-subtitle">Patient Room Media Manager</span>
        </div>
        <nav className="header-tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <i className={`fas ${tab.icon}`}></i>
              {tab.label}
            </button>
          ))}
          <button className="tab-btn logout-btn" onClick={logout} title="Logout">
            <i className="fas fa-sign-out-alt"></i>
            Logout
          </button>
        </nav>
      </header>
      <main className="app-main">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'media' && <MediaManager />}
        {activeTab === 'settings' && <Settings />}
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
