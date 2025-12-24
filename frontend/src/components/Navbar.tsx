import React from 'react';

interface NavbarProps {
  onMenuToggle: () => void;
  isMenuOpen: boolean;
  viewMode: 'side-by-side' | 'original' | 'edited';
  onViewModeChange: (mode: 'side-by-side' | 'original' | 'edited') => void;
  isProcessing?: boolean;
}

const Navbar: React.FC<NavbarProps> = ({ 
  onMenuToggle, 
  isMenuOpen, 
  viewMode, 
  onViewModeChange,
  isProcessing = false 
}) => {
  return (
    <nav className="navbar">
      <div className="navbar-content">
        <button
          className="navbar-menu-button"
          onClick={onMenuToggle}
          aria-label={isMenuOpen ? 'Close menu' : 'Open menu'}
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3 12h18M3 6h18M3 18h18" />
          </svg>
        </button>
        <h1 className="navbar-title">Video Background Editor</h1>
        <div className="navbar-view-controls">
          <button
            className={`navbar-view-button ${viewMode === 'side-by-side' ? 'navbar-view-button-active' : ''}`}
            onClick={() => onViewModeChange('side-by-side')}
            title="Side-by-side view"
          >
            Side-by-side
          </button>
          <button
            className={`navbar-view-button ${viewMode === 'original' ? 'navbar-view-button-active' : ''}`}
            onClick={() => onViewModeChange('original')}
            title="Original video only"
          >
            Original
          </button>
          <button
            className={`navbar-view-button ${viewMode === 'edited' ? 'navbar-view-button-active' : ''}`}
            onClick={() => onViewModeChange('edited')}
            title="Edited video only"
          >
            Edited
          </button>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;

