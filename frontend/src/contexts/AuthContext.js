import React, { createContext, useState, useCallback, useEffect, useRef } from 'react';

export const AuthContext = createContext(null);

const USERS = {
  user: { password: process.env.REACT_APP_AUTH_USER_PW || 'password', role: 'user' },
  admin: { password: process.env.REACT_APP_AUTH_ADMIN_PW || 'password', role: 'admin' },
  superuser: { password: process.env.REACT_APP_AUTH_SUPERUSER_PW || 'password', role: 'superuser' }
};

const SESSION_TIMEOUT_MINUTES = 30;
const SESSION_TIMEOUT_MS = SESSION_TIMEOUT_MINUTES * 60 * 1000;

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(null);
  const timeoutRef = useRef(null);

  const logout = useCallback(() => {
    setAuth(null);
    localStorage.removeItem('authUser');
    localStorage.removeItem('authTimestamp');
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  }, []);

  const resetSessionTimeout = useCallback(() => {
    if (!auth) return;
    
    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Update last activity timestamp
    const now = Date.now();
    localStorage.setItem('authTimestamp', now.toString());

    // Set new timeout
    timeoutRef.current = setTimeout(() => {
      console.log('Session expired due to inactivity');
      logout();
    }, SESSION_TIMEOUT_MS);
  }, [auth, logout]);

  const login = useCallback((username, password) => {
    const user = USERS[username];
    if (!user) return false;
    if (user.password !== password) return false;
    
    const now = Date.now();
    setAuth({ username, role: user.role });
    localStorage.setItem('authUser', JSON.stringify({ username, role: user.role }));
    localStorage.setItem('authTimestamp', now.toString());
    return true;
  }, []);

  // Restore auth from localStorage on mount and check for expiration
  useEffect(() => {
    const stored = localStorage.getItem('authUser');
    const timestamp = localStorage.getItem('authTimestamp');
    
    if (stored && timestamp) {
      try {
        const lastActivity = parseInt(timestamp);
        const now = Date.now();
        const elapsedTime = now - lastActivity;

        // Check if session has expired
        if (elapsedTime > SESSION_TIMEOUT_MS) {
          console.log('Session expired on page load');
          logout();
        } else {
          // Session still valid, restore it
          setAuth(JSON.parse(stored));
        }
      } catch (e) {
        localStorage.removeItem('authUser');
        localStorage.removeItem('authTimestamp');
      }
    }
  }, [logout]);

  // Set up session timeout after auth state changes
  useEffect(() => {
    if (auth) {
      resetSessionTimeout();
    }
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [auth, resetSessionTimeout]);

  // Track user activity globally
  useEffect(() => {
    if (!auth) return;

    const handleActivity = () => {
      resetSessionTimeout();
    };

    // Listen for various user interactions
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart', 'click'];
    events.forEach(event => {
      document.addEventListener(event, handleActivity);
    });

    return () => {
      events.forEach(event => {
        document.removeEventListener(event, handleActivity);
      });
    };
  }, [auth, resetSessionTimeout]);

  return (
    <AuthContext.Provider value={{ auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
