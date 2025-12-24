import React, { useRef, useState, useEffect } from 'react';
import VideoPlayer from './components/VideoPlayer';
import ProcessedVideoPlayer from './components/ProcessedVideoPlayer';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import { videoUrl, templateBackgroundImages } from './consts';
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
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mode, setMode] = useState<'background-image' | 'background-filter' | 'no-change'>('no-change');
  const [clipStart, setClipStart] = useState(0);
  const [clipEnd, setClipEnd] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);
  const [backgroundLibrary] = useState<string[]>(templateBackgroundImages); // Use template images, not user uploads
  const [selectedBackgroundImage, setSelectedBackgroundImage] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploadedVideoUrl, setUploadedVideoUrl] = useState<string | null>(null);
  const [uploadedVideoFileName, setUploadedVideoFileName] = useState<string | null>(null);
  const [isUploadingVideo, setIsUploadingVideo] = useState(false);
  const [currentPlaybackTime, setCurrentPlaybackTime] = useState(0);
  const [viewMode, setViewMode] = useState<'side-by-side' | 'original' | 'edited'>('side-by-side');

  const {
    state,
    processCurrentFrame,
    processFullVideo,
    setFilter,
    clearProcessedFrames,
    clearError,
  } = useVideoProcessor(videoRef);

  // Update clip end when video duration is known
  useEffect(() => {
    if (videoRef.current && videoDuration > 0 && clipEnd === 0) {
      setClipEnd(videoDuration);
    }
  }, [videoDuration, clipEnd]);

  const handleVideoLoadedMetadata = () => {
    if (videoRef.current) {
      const duration = videoRef.current.duration;
      setVideoDuration(duration);
      setClipEnd(duration);
    }
  };

  const handleClipChange = (start: number, end: number) => {
    const newStart = Math.max(0, Math.min(start, videoDuration));
    const newEnd = Math.max(start, Math.min(end, videoDuration));
    
    setClipStart(newStart);
    setClipEnd(newEnd);
    
    // If clipEnd changed and video is currently past new clipEnd, pause and seek to clipStart
    if (videoRef.current) {
      const currentTime = videoRef.current.currentTime;
      if (currentTime > newEnd) {
        videoRef.current.pause();
        videoRef.current.currentTime = newStart;
        setCurrentPlaybackTime(newStart);
      } else if (currentTime < newStart) {
        videoRef.current.currentTime = newStart;
        setCurrentPlaybackTime(newStart);
      } else {
        // Just update current time if we're seeking
        videoRef.current.currentTime = newStart;
        setCurrentPlaybackTime(newStart);
      }
    }
  };

  const handleVideoSeek = (time: number) => {
    if (videoRef.current && time >= clipStart && time <= clipEnd) {
      videoRef.current.currentTime = time;
      setCurrentPlaybackTime(time);
    }
  };

  // Restrict video playback to clipStart-clipEnd range
  useEffect(() => {
    const video = videoRef.current;
    if (!video || videoDuration === 0) return;

    const handleTimeUpdate = () => {
      const currentTime = video.currentTime;
      setCurrentPlaybackTime(currentTime);
      
      // If video reaches or exceeds clipEnd, pause and seek to clipStart
      if (currentTime >= clipEnd) {
        video.pause();
        video.currentTime = clipStart;
        setCurrentPlaybackTime(clipStart);
      } else if (currentTime < clipStart) {
        // If video is before clipStart, seek to clipStart
        video.currentTime = clipStart;
        setCurrentPlaybackTime(clipStart);
      }
    };

    video.addEventListener('timeupdate', handleTimeUpdate);
    return () => video.removeEventListener('timeupdate', handleTimeUpdate);
  }, [clipStart, clipEnd, videoDuration]);

  const handleBackgroundImageUpload = (file: File) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const imageUrl = e.target?.result as string;
      setSelectedBackgroundImage(imageUrl);
      setUploadedFileName(file.name); // Store filename to show selection
      // Note: Uploaded images are NOT added to the library - library only shows templates
    };
    reader.readAsDataURL(file);
  };

  const handleSelectFromLibrary = (imageUrl: string) => {
    setSelectedBackgroundImage(imageUrl);
    setUploadedFileName(null); // Clear uploaded file name when selecting from library
  };

  const handleProcess = async () => {
    // Determine filter type and background image based on mode
    let filterType: 'grayscale' | 'sepia' | 'blur' | null = null;
    let backgroundImage: string | null = null;
    
    if (mode === 'background-filter') {
      filterType = state.currentFilter;
    } else if (mode === 'background-image') {
      // Use background image mode
      if (!selectedBackgroundImage) {
        alert('Please select a background image first');
        return;
      }
      backgroundImage = selectedBackgroundImage;
    } else if (mode === 'no-change') {
      // No change mode - only clip if clip times are set
      filterType = null;
      backgroundImage = null;
    }
    
    // Use uploaded video if available, otherwise use default video
    const currentVideoUrl = uploadedVideoUrl || videoUrl;
    
    // Process video with clip parameters, background image/filter
    await processFullVideo(currentVideoUrl, clipStart, clipEnd, filterType, backgroundImage);
  };
  
  const handleVideoUpload = async (file: File) => {
    setIsUploadingVideo(true);
    try {
      // Create FormData for file upload
      const formData = new FormData();
      formData.append('video', file);
      
      // Upload to backend
      const response = await fetch('http://127.0.0.1:8080/upload-video', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Upload failed' }));
        throw new Error(errorData.error || 'Failed to upload video');
      }
      
      const data = await response.json();
      const uploadedUrl = data.video_url;
      const uploadedFilename = data.filename;
      
      // Update state with uploaded video
      setUploadedVideoUrl(uploadedUrl);
      setUploadedVideoFileName(file.name);
      
      // Reset video-related state
      setClipStart(0);
      setClipEnd(0);
      setVideoDuration(0);
      clearProcessedFrames();
      clearError();
      
      // Wait a bit for video element to update, then trigger metadata load
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.load();
        }
      }, 100);
      
    } catch (error) {
      console.error('Error uploading video:', error);
      alert(error instanceof Error ? error.message : 'Failed to upload video');
    } finally {
      setIsUploadingVideo(false);
    }
  };
  
  const handleClearUploadedVideo = () => {
    setUploadedVideoUrl(null);
    setUploadedVideoFileName(null);
    setClipStart(0);
    setClipEnd(0);
    setVideoDuration(0);
    clearProcessedFrames();
    clearError();
    
    // Reload default video
    if (videoRef.current) {
      videoRef.current.load();
    }
  };

  const handleDownload = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    if (state.processedVideoUrl) {
      try {
        // Fetch the video file and create a blob for download
        const response = await fetch(state.processedVideoUrl);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `processed-video-${Date.now()}.mp4`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        // Clean up the blob URL
        setTimeout(() => window.URL.revokeObjectURL(url), 100);
      } catch (error) {
        console.error('Error downloading video:', error);
        // Fallback to direct link
        window.open(state.processedVideoUrl, '_blank');
      }
    }
  };

  const averageProcessingTime =
    state.processedFrames.length > 0
      ? Math.round(
          state.processedFrames.reduce((sum, frame) => sum + frame.processingTime, 0) /
            state.processedFrames.length
        )
      : 0;

  return (
    <div className="app-container">
      <Navbar
        onMenuToggle={() => setSidebarOpen(!sidebarOpen)}
        isMenuOpen={sidebarOpen}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        isProcessing={state.isProcessing || state.isProcessingFullVideo}
      />
      
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        selectedFilter={state.currentFilter}
        onFilterChange={setFilter}
        onProcess={handleProcess}
        isProcessing={state.isProcessing || state.isProcessingFullVideo}
        videoDuration={videoDuration}
        clipStart={clipStart}
        clipEnd={clipEnd}
        onClipChange={handleClipChange}
        mode={mode}
        onModeChange={setMode}
        onBackgroundImageUpload={handleBackgroundImageUpload}
        backgroundLibrary={backgroundLibrary}
        onSelectFromLibrary={handleSelectFromLibrary}
        selectedBackgroundImage={selectedBackgroundImage}
        uploadedFileName={uploadedFileName}
        currentPlaybackTime={currentPlaybackTime}
        onSeekVideo={handleVideoSeek}
        progress={state.progress}
        progressMessage={state.message}
      />

      <main className="main-content" style={{ marginLeft: sidebarOpen ? '380px' : '0' }}>
        <div className="content-wrapper">

          {/* Video Upload Section */}
          <div className="video-upload-section">
            <div className="video-upload-container">
              <div 
                className="video-upload-dropzone"
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  e.currentTarget.classList.add('drag-over');
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  e.currentTarget.classList.remove('drag-over');
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  e.currentTarget.classList.remove('drag-over');
                  
                  if (isUploadingVideo || state.isProcessing || state.isProcessingFullVideo) return;
                  
                  const files = Array.from(e.dataTransfer.files);
                  const videoFile = files.find(file => {
                    const isVideoMimeType = file.type.startsWith('video/');
                    const isVideoExtension = /\.(mp4|mov|avi|mkv|webm|m4v)$/i.test(file.name);
                    return isVideoMimeType || isVideoExtension;
                  });
                  if (videoFile) {
                    handleVideoUpload(videoFile);
                  }
                }}
              >
                <div className="video-upload-controls">
                  <button
                    className="video-sample-button"
                    onClick={() => {
                      setUploadedVideoUrl(null);
                      setUploadedVideoFileName(null);
                      setClipStart(0);
                      setClipEnd(0);
                      setVideoDuration(0);
                      clearProcessedFrames();
                      clearError();
                      
                      // Reload default video
                      if (videoRef.current) {
                        videoRef.current.load();
                      }
                    }}
                    disabled={isUploadingVideo || state.isProcessing || state.isProcessingFullVideo}
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polygon points="5 3 19 12 5 21 5 3" />
                    </svg>
                    Use Sample Video
                  </button>
                  <button
                    className="video-upload-button"
                    onClick={() => {
                      const input = document.createElement('input');
                      input.type = 'file';
                      input.accept = 'video/*,.mov,.MOV';
                      input.onchange = (e) => {
                        const file = (e.target as HTMLInputElement).files?.[0];
                        if (file) {
                          const isVideoMimeType = file.type.startsWith('video/');
                          const isVideoExtension = /\.(mp4|mov|avi|mkv|webm|m4v)$/i.test(file.name);
                          if (isVideoMimeType || isVideoExtension) {
                            handleVideoUpload(file);
                          } else {
                            alert('Please select a valid video file (mp4, mov, avi, mkv, webm, m4v)');
                          }
                        }
                      };
                      input.click();
                    }}
                    disabled={isUploadingVideo || state.isProcessing || state.isProcessingFullVideo}
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    {isUploadingVideo ? 'Uploading...' : 'Upload Video'}
                  </button>
                  <span className="video-upload-drag-hint">
                    Drag and drop a video file here
                  </span>
                  {uploadedVideoUrl && (
                    <div className="uploaded-video-info">
                      <span className="uploaded-video-name" title={uploadedVideoFileName || ''}>
                        {uploadedVideoFileName ? (uploadedVideoFileName.length > 30 ? `${uploadedVideoFileName.substring(0, 30)}...` : uploadedVideoFileName) : 'Uploaded video'}
                      </span>
                      <button
                        className="clear-video-button"
                        onClick={handleClearUploadedVideo}
                        disabled={isUploadingVideo || state.isProcessing || state.isProcessingFullVideo}
                        title="Clear uploaded video"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                  )}
                  {!uploadedVideoUrl && (
                    <span className="video-source-indicator">Using sample video</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Video Display */}
          <div className={`video-display-container ${viewMode === 'original' ? 'view-original' : viewMode === 'edited' ? 'view-edited' : ''}`}>
            {/* Original Video */}
            {(viewMode === 'side-by-side' || viewMode === 'original') && (
              <div className="video-section">
                <div className="video-section-header">
                  <h3 className="video-section-title">Original Video</h3>
                  <div className="video-section-header-spacer"></div>
                </div>
                <div className="video-container video-container-matched">
                  <VideoPlayer
                    ref={videoRef}
                    src={uploadedVideoUrl || videoUrl}
                    onLoadedMetadata={handleVideoLoadedMetadata}
                  />
                </div>
              </div>
            )}

            {/* Edited Video */}
            {(viewMode === 'side-by-side' || viewMode === 'edited') && (
              <div className="video-section">
                <div className="video-section-header">
                  <h3 className="video-section-title">Edited Video</h3>
                  {state.processedVideoUrl ? (
                    <button
                      onClick={handleDownload}
                      className="download-button-main"
                      type="button"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      Download Video
                    </button>
                  ) : (
                    <div className="video-section-header-spacer"></div>
                  )}
                </div>
                <div className="video-container video-container-matched">
                  {state.processedVideoUrl ? (
                    <VideoPlayer
                      src={state.processedVideoUrl}
                      onLoadedMetadata={() => console.log('Edited video loaded')}
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
            <div className="stats">
              <h3>Editing Statistics</h3>
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
      </main>
    </div>
  );
};

export default App;
