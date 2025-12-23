import React, { useRef, useState } from 'react';
import VideoPlayer from './components/VideoPlayer';
import FilterSelector from './components/FilterSelector';
import ProcessedVideoPlayer from './components/ProcessedVideoPlayer';
import { videoUrl } from './consts';
import { useVideoProcessor } from './hooks/useVideoProcessor';

export interface FaceDetection {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  confidence: number;
  label?: string;
}

const App: React.FC = () => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [showProcessed, setShowProcessed] = useState(false);
  const [viewMode, setViewMode] = useState<'original' | 'processed' | 'side-by-side'>('side-by-side');

  const {
    state,
    processCurrentFrame,
    processFullVideo,
    setFilter,
    clearProcessedFrames,
    clearError,
  } = useVideoProcessor(videoRef);

  const handleProcessFrame = async () => {
    await processCurrentFrame();
  };

  const handleProcessVideo = async () => {
    await processFullVideo(videoUrl);
  };

  const averageProcessingTime =
    state.processedFrames.length > 0
      ? Math.round(
          state.processedFrames.reduce((sum, frame) => sum + frame.processingTime, 0) /
            state.processedFrames.length
        )
      : 0;

  return (
    <div className="container">
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ marginBottom: '20px', color: '#333' }}>Video Background Filter</h1>

        {/* Filter Selector */}
        <FilterSelector
          selectedFilter={state.currentFilter}
          onFilterChange={setFilter}
          disabled={state.isProcessing || state.isProcessingFullVideo}
        />

        {/* View Mode Toggle */}
        <div className="controls" style={{ marginTop: '20px' }}>
          <button
            className={`btn ${viewMode === 'original' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setViewMode('original')}
            disabled={state.isProcessing || state.isProcessingFullVideo}
          >
            Original
          </button>
          <button
            className={`btn ${viewMode === 'processed' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setViewMode('processed')}
            disabled={state.isProcessing || state.isProcessingFullVideo}
          >
            Processed
          </button>
          <button
            className={`btn ${viewMode === 'side-by-side' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setViewMode('side-by-side')}
            disabled={state.isProcessing || state.isProcessingFullVideo}
          >
            Side by Side
          </button>
        </div>

        {/* Video Display */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '20px',
            marginTop: '20px',
            flexWrap: 'wrap',
          }}
        >
          {/* Original Video */}
          {(viewMode === 'original' || viewMode === 'side-by-side') && (
            <div>
              <h3 style={{ marginBottom: '10px', fontSize: '16px', color: '#666' }}>Original Video</h3>
              <div className="video-container">
                <VideoPlayer
                  ref={videoRef}
                  src={videoUrl}
                  onLoadedMetadata={() => console.log('Video loaded')}
                />
              </div>
            </div>
          )}

          {/* Processed Video */}
          {(viewMode === 'processed' || viewMode === 'side-by-side') && (
            <div>
              <h3 style={{ marginBottom: '10px', fontSize: '16px', color: '#666' }}>
                Processed Video
                {state.processedVideoUrl && (
                  <a
                    href={state.processedVideoUrl}
                    download
                    style={{
                      marginLeft: '10px',
                      fontSize: '14px',
                      color: '#007bff',
                      textDecoration: 'none',
                      padding: '5px 10px',
                      border: '1px solid #007bff',
                      borderRadius: '4px',
                      display: 'inline-block'
                    }}
                  >
                    Download
                  </a>
                )}
              </h3>
              <div className="video-container">
                {state.processedVideoUrl ? (
                  <VideoPlayer
                    src={state.processedVideoUrl}
                    onLoadedMetadata={() => console.log('Processed video loaded')}
                  />
                ) : (
                  <ProcessedVideoPlayer
                    videoRef={videoRef}
                    processedFrames={state.processedFrames}
                    showPlaceholder={true}
                    placeholderText="No processed frame available"
                  />
                )}
              </div>
            </div>
          )}
        </div>

        {/* Processing Controls */}
        <div className="controls" style={{ marginTop: '30px' }}>
          <button
            className="btn btn-primary"
            onClick={handleProcessFrame}
            disabled={state.isProcessing || state.isProcessingFullVideo}
          >
            {state.isProcessing ? 'Processing Frame...' : 'Process Current Frame'}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleProcessVideo}
            disabled={state.isProcessing || state.isProcessingFullVideo}
          >
            {state.isProcessingFullVideo ? 'Processing Video...' : 'Process Full Video'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={clearProcessedFrames}
            disabled={state.isProcessing || state.isProcessingFullVideo || state.processedFrames.length === 0}
          >
            Clear Processed Frames
          </button>
        </div>

        {/* Progress Indicator for Full Video Processing */}
        {state.isProcessingFullVideo && (
          <div className="progress-container">
            <h3 style={{ marginTop: 0, marginBottom: '10px', color: '#333' }}>Processing Video</h3>
            <div className="progress-bar">
              <div className="progress-bar-fill" style={{ width: `${state.progress}%` }}>
                {state.progress}%
              </div>
            </div>
            <p style={{ marginTop: '10px', color: '#666', fontSize: '14px' }}>{state.message || 'Processing...'}</p>
          </div>
        )}

        {/* Error Display */}
        {state.error && (
          <div className="error-message">
            <span>{state.error}</span>
            <button
              onClick={clearError}
              className="error-close"
              aria-label="Close error"
            >
              ×
            </button>
          </div>
        )}

        {/* Processing Stats */}
        {state.processedFrames.length > 0 && (
          <div className="stats" style={{ marginTop: '20px' }}>
            <h3>Processing Statistics</h3>
            <div className="stats-grid">
              <div className="stat-item">
                <div className="stat-value">{state.processedFrames.length}</div>
                <div className="stat-label">Frames Processed</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{averageProcessingTime}ms</div>
                <div className="stat-label">Avg Processing Time</div>
              </div>
              <div className="stat-item">
                <div className="stat-value">{state.currentFilter}</div>
                <div className="stat-label">Current Filter</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default App; 