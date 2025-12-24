import React, { useState } from 'react';
import { FilterType } from '../hooks/useVideoProcessor';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  selectedFilter: FilterType;
  onFilterChange: (filter: FilterType) => void;
  onProcess: () => void;
  isProcessing: boolean;
  videoDuration: number;
  clipStart: number;
  clipEnd: number;
  onClipChange: (start: number, end: number) => void;
  mode: 'background-image' | 'background-filter' | 'no-change';
  onModeChange: (mode: 'background-image' | 'background-filter' | 'no-change') => void;
  onBackgroundImageUpload: (file: File) => void;
  backgroundLibrary: string[];
  onSelectFromLibrary: (imageUrl: string) => void;
  selectedBackgroundImage: string | null;
  uploadedFileName: string | null;
  currentPlaybackTime: number;
  onSeekVideo: (time: number) => void;
  progress?: number;
  progressMessage?: string | null;
}

const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggle,
  selectedFilter,
  onFilterChange,
  onProcess,
  isProcessing,
  videoDuration,
  clipStart,
  clipEnd,
  onClipChange,
  mode,
  onModeChange,
  onBackgroundImageUpload,
  backgroundLibrary,
  onSelectFromLibrary,
  selectedBackgroundImage,
  uploadedFileName,
  currentPlaybackTime,
  onSeekVideo,
  progress = 0,
  progressMessage = null,
}) => {
  const [isLibraryExpanded, setIsLibraryExpanded] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const milliseconds = Math.floor((seconds % 1) * 1000);
    return `${mins}:${secs.toString().padStart(2, '0')}.${milliseconds.toString().padStart(3, '0')}`;
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file && file.type.startsWith('image/')) {
      onBackgroundImageUpload(file);
    }
  };

  return (
    <>
      {/* Sidebar */}
      <div className={`sidebar ${isOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
      <div className="sidebar-content">
          {/* Background Selection */}
          <div className="sidebar-section">
            <label className="sidebar-label">Background</label>
            <div className="mode-toggle">
              <button
                className={`mode-button ${mode === 'background-image' ? 'mode-button-active' : ''}`}
                onClick={() => onModeChange('background-image')}
                disabled={isProcessing}
              >
                Background Image
              </button>
              <button
                className={`mode-button ${mode === 'background-filter' ? 'mode-button-active' : ''}`}
                onClick={() => onModeChange('background-filter')}
                disabled={isProcessing}
              >
                Background Filter
              </button>
              <button
                className={`mode-button ${mode === 'no-change' ? 'mode-button-active' : ''}`}
                onClick={() => onModeChange('no-change')}
                disabled={isProcessing}
              >
                No Change
              </button>
            </div>
          </div>

          {/* Background Image Mode */}
          {mode === 'background-image' && (
            <>
              {/* Upload Section */}
              <div className="sidebar-section">
                <label className="sidebar-label">Upload Background</label>
                <button
                  className="upload-button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isProcessing}
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  Upload Image
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleFileUpload}
                  style={{ display: 'none' }}
                />
                {uploadedFileName && selectedBackgroundImage && !backgroundLibrary.includes(selectedBackgroundImage) && (
                  <div className="uploaded-file-indicator">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9 11l3 3L22 4" />
                      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                    </svg>
                    <span className="uploaded-file-name" title={uploadedFileName}>
                      {uploadedFileName.length > 25 ? `${uploadedFileName.substring(0, 25)}...` : uploadedFileName}
                    </span>
                    <span className="uploaded-file-status">Selected</span>
                  </div>
                )}
              </div>

              {/* Library Section */}
              <div className="sidebar-section">
                <button
                  className="library-toggle"
                  onClick={() => setIsLibraryExpanded(!isLibraryExpanded)}
                >
                  <span>Image Library</span>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className={isLibraryExpanded ? 'rotated' : ''}
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
                {isLibraryExpanded && (
                  <div className="library-grid">
                    {backgroundLibrary.length === 0 ? (
                      <div className="library-empty">No images in library</div>
                    ) : (
                      backgroundLibrary.map((url, index) => (
                        <div
                          key={index}
                          className={`library-item ${selectedBackgroundImage === url ? 'library-item-selected' : ''}`}
                          onClick={() => onSelectFromLibrary(url)}
                        >
                          <img src={url} alt={`Background ${index + 1}`} />
                          {selectedBackgroundImage === url && (
                            <div className="library-item-checkmark">
                              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                                <path d="M9 11l3 3L22 4" />
                              </svg>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </>
          )}

          {/* Background Filter Mode */}
          {mode === 'background-filter' && (
            <div className="sidebar-section">
              <label className="sidebar-label">Filter Type</label>
              <div className="filter-options">
                <button
                  className={`filter-option ${selectedFilter === 'grayscale' ? 'filter-option-active' : ''}`}
                  onClick={() => onFilterChange('grayscale')}
                  disabled={isProcessing}
                >
                  <span>Grayscale</span>
                  <svg className="filter-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect width="40" height="40" rx="6" fill="currentColor" opacity="0.1"/>
                    <rect x="8" y="8" width="24" height="24" rx="4" fill="url(#grayscale-gradient-sidebar)"/>
                    <defs>
                      <linearGradient id="grayscale-gradient-sidebar" x1="8" y1="8" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stopColor="#000000"/>
                        <stop offset="50%" stopColor="#808080"/>
                        <stop offset="100%" stopColor="#FFFFFF"/>
                      </linearGradient>
                    </defs>
                  </svg>
                </button>
                <button
                  className={`filter-option ${selectedFilter === 'sepia' ? 'filter-option-active' : ''}`}
                  onClick={() => onFilterChange('sepia')}
                  disabled={isProcessing}
                >
                  <span>Sepia</span>
                  <svg className="filter-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect width="40" height="40" rx="6" fill="currentColor" opacity="0.1"/>
                    <rect x="8" y="8" width="24" height="24" rx="4" fill="url(#sepia-gradient-sidebar)"/>
                    <defs>
                      <linearGradient id="sepia-gradient-sidebar" x1="8" y1="8" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                        <stop offset="0%" stopColor="#704214"/>
                        <stop offset="50%" stopColor="#C9A961"/>
                        <stop offset="100%" stopColor="#F4E4BC"/>
                      </linearGradient>
                    </defs>
                  </svg>
                </button>
                <button
                  className={`filter-option ${selectedFilter === 'blur' ? 'filter-option-active' : ''}`}
                  onClick={() => onFilterChange('blur')}
                  disabled={isProcessing}
                >
                  <span>Blur</span>
                  <svg className="filter-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect width="40" height="40" rx="6" fill="currentColor" opacity="0.1"/>
                    <circle cx="20" cy="20" r="12" fill="currentColor" opacity="0.3">
                      <animate attributeName="r" values="12;14;12" dur="2s" repeatCount="indefinite"/>
                    </circle>
                    <circle cx="20" cy="20" r="8" fill="currentColor" opacity="0.5">
                      <animate attributeName="r" values="8;10;8" dur="2s" repeatCount="indefinite"/>
                    </circle>
                    <circle cx="20" cy="20" r="4" fill="currentColor" opacity="0.7"/>
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Video Clipping */}
          <div className="sidebar-section">
            <label className="sidebar-label">Video Clipping</label>
            <div className="clip-controls">
              <div className="clip-time-display">
                <span>Start: {formatTime(clipStart)}</span>
                <span>End: {formatTime(clipEnd)}</span>
              </div>
              <div className="clip-range-wrapper">
                <div 
                  className="clip-range-track"
                  onClick={(e) => {
                    if (isProcessing || videoDuration === 0) return;
                    const track = e.currentTarget;
                    const rect = track.getBoundingClientRect();
                    const clickX = e.clientX - rect.left;
                    const percentage = Math.max(0, Math.min(1, clickX / rect.width));
                    const newTime = percentage * videoDuration;
                    
                    if (newTime >= clipStart && newTime <= clipEnd) {
                      onSeekVideo(newTime);
                    }
                  }}
                  style={{ cursor: isProcessing || videoDuration === 0 ? 'default' : 'pointer' }}
                >
                  <div 
                    className="clip-range-selected"
                    style={{
                      left: `${(clipStart / videoDuration) * 100}%`,
                      width: `${((clipEnd - clipStart) / videoDuration) * 100}%`,
                    }}
                  />
                  {videoDuration > 0 && (
                    <div
                      className="clip-playback-position"
                      style={{
                        left: `${(currentPlaybackTime / videoDuration) * 100}%`,
                      }}
                    />
                  )}
                </div>
                <input
                  type="range"
                  min="0"
                  max={videoDuration}
                  step="0.001"
                  value={clipStart}
                  onChange={(e) => {
                    const newStart = Number(e.target.value);
                    if (newStart < clipEnd) {
                      onClipChange(newStart, clipEnd);
                    }
                  }}
                  className="clip-range-slider clip-range-start"
                  disabled={isProcessing || videoDuration === 0}
                />
                <input
                  type="range"
                  min="0"
                  max={videoDuration}
                  step="0.001"
                  value={clipEnd}
                  onChange={(e) => {
                    const newEnd = Number(e.target.value);
                    if (newEnd > clipStart) {
                      onClipChange(clipStart, newEnd);
                    }
                  }}
                  className="clip-range-slider clip-range-end"
                  disabled={isProcessing || videoDuration === 0}
                />
              </div>
            </div>
          </div>

          {/* Process Button */}
          <div className="sidebar-section sidebar-footer">
            <button
              className="process-button"
              onClick={onProcess}
              disabled={isProcessing || videoDuration === 0}
            >
              {isProcessing ? (
                <>
                  <svg
                    className="spinner"
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      strokeDasharray="32"
                      strokeDashoffset="32"
                    >
                      <animate
                        attributeName="stroke-dasharray"
                        dur="2s"
                        values="0 32;16 16;0 32;0 32"
                        repeatCount="indefinite"
                      />
                      <animate
                        attributeName="stroke-dashoffset"
                        dur="2s"
                        values="0;-16;-32;-32"
                        repeatCount="indefinite"
                      />
                    </circle>
                  </svg>
                  Processing...
                </>
              ) : (
                'Edit Video'
              )}
            </button>

            {/* Progress Indicator */}
            {isProcessing && (
              <div className="progress-container sidebar-progress">
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: `${progress}%` }}>
                    {progress}%
                  </div>
                </div>
                <p className="progress-message">{progressMessage || 'Editing...'}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default Sidebar;

