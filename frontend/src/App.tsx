import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import ReviewPage from './pages/ReviewPage';
import PromptsPage from './pages/PromptsPage';
import './App.css';

const queryClient = new QueryClient();

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link to={to} className={`nav-link ${isActive ? 'active' : ''}`}>
      {children}
    </Link>
  );
}

function Layout() {
  return (
    <div className="app-container">
      <nav className="navbar">
        <div className="nav-brand">
          <h1>Flashcard Generator</h1>
        </div>
        <div className="nav-links">
          <NavLink to="/">Sessions</NavLink>
          <NavLink to="/upload">Upload</NavLink>
          <NavLink to="/prompts">Prompts</NavLink>
        </div>
      </nav>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/review/:sessionId" element={<ReviewPage />} />
          <Route path="/prompts" element={<PromptsPage />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
