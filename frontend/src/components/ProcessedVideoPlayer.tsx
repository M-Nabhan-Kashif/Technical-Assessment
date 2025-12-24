import React, { useEffect, useRef, useState } from 'react';
import { ProcessedFrame } from '../hooks/useVideoProcessor';
import { drawImageToCanvas } from '../utils/videoProcessing';

interface ProcessedVideoPlayerProps {
  videoRef: React.RefObject<HTMLVideoElement>;
  processedFrames: ProcessedFrame[];
  width?: number;
  height?: number;
  className?: string;
  showPlaceholder?: boolean;
  placeholderText?: string;
}

const ProcessedVideoPlayer: React.FC<ProcessedVideoPlayerProps> = ({
  videoRef,
  processedFrames,
  width,
  height,
  className = '',
  showPlaceholder = true,
  placeholderText = 'No processed frame available',
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [currentFrame, setCurrentFrame] = useState<ProcessedFrame | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const animationFrameRef = useRef<number | null>(null);
  const currentFrameRef = useRef<ProcessedFrame | null>(null);

  // Find the closest processed frame to the current video timestamp
  const findFrameForTimestamp = (timestamp: number): ProcessedFrame | null => {
    if (processedFrames.length === 0) {
      return null;
    }

    // Find the closest frame within 0.5 seconds
    const sortedFrames = [...processedFrames].sort(
      (a, b) => Math.abs(a.timestamp - timestamp) - Math.abs(b.timestamp - timestamp)
    );

    const closest = sortedFrames[0];
    if (Math.abs(closest.timestamp - timestamp) < 0.5) {
      return closest;
    }

    return null;
  };

  // Update canvas with processed frame
  const updateCanvas = async (frame: ProcessedFrame | null) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (!frame) {
      // Clear canvas or show placeholder
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        if (showPlaceholder) {
          ctx.fillStyle = '#666';
          ctx.font = '16px sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(placeholderText, canvas.width / 2, canvas.height / 2);
        }
      }
      return;
    }

    try {
      setIsLoading(true);
      await drawImageToCanvas(frame.frameBase64, canvas);
      setCurrentFrame(frame);
      currentFrameRef.current = frame;
    } catch (error) {
      console.error('Error drawing processed frame:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Sync with video playback
  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    if (!video || !canvas) return;

    // Set canvas dimensions
    // Define updateDimensions outside conditional so it can be referenced in cleanup
    const updateDimensions = () => {
      if (canvas) {
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
      }
    };
    
    if (width && height) {
      canvas.width = width;
      canvas.height = height;
    } else {
      // Match video dimensions
      if (video.videoWidth && video.videoHeight) {
        updateDimensions();
      } else {
        video.addEventListener('loadedmetadata', updateDimensions);
      }
    }

    // Function to update frame based on video time
    const updateFrame = () => {
      const timestamp = video.currentTime;
      const frame = findFrameForTimestamp(timestamp);
      
      // Only update if frame changed
      if (frame !== currentFrameRef.current) {
        updateCanvas(frame);
      }

      // Continue animation loop if video is playing
      if (!video.paused && !video.ended) {
        animationFrameRef.current = requestAnimationFrame(updateFrame);
      }
    };

    // Event handlers
    const handleTimeUpdate = () => {
      if (animationFrameRef.current === null) {
        updateFrame();
      }
    };

    const handlePlay = () => {
      if (animationFrameRef.current === null) {
        animationFrameRef.current = requestAnimationFrame(updateFrame);
      }
    };

    const handlePause = () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      // Update to current frame when paused
      updateFrame();
    };

    const handleSeeked = () => {
      updateFrame();
    };

    // Initial frame update
    updateFrame();

    // Add event listeners
    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('play', handlePlay);
    video.addEventListener('pause', handlePause);
    video.addEventListener('seeked', handleSeeked);

    // Cleanup
    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('play', handlePlay);
      video.removeEventListener('pause', handlePause);
      video.removeEventListener('seeked', handleSeeked);
      video.removeEventListener('loadedmetadata', updateDimensions);
      
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [videoRef, processedFrames, width, height, showPlaceholder, placeholderText]);

  // Update canvas when processed frames change
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const timestamp = video.currentTime;
    const frame = findFrameForTimestamp(timestamp);
    updateCanvas(frame);
  }, [processedFrames]);

  return (
    <div className={`processed-video-container ${className}`} style={{ position: 'relative' }}>
      <canvas
        ref={canvasRef}
        className="processed-video-canvas"
        style={{
          width: '100%',
          height: 'auto',
          display: 'block',
          maxWidth: width || '800px',
        }}
      />
      {isLoading && (
        <div
          className="processed-video-loading"
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            color: '#fff',
            fontSize: '14px',
            pointerEvents: 'none',
          }}
        >
          Loading...
        </div>
      )}
    </div>
  );
};

export default ProcessedVideoPlayer;

