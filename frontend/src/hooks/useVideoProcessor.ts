import { useState, useRef, useCallback, useEffect } from 'react';
import {
  captureVideoFrame,
  frameToBase64,
  base64ToImage,
  drawImageToCanvas,
  createCanvas,
  processFrame,
  captureAndProcessFrame,
} from '../utils/videoProcessing';

export type FilterType = 'grayscale' | 'sepia' | 'blur';

export interface ProcessedFrame {
  frameBase64: string;
  timestamp: number;
  processingTime: number;
}

export interface VideoProcessingState {
  isProcessing: boolean;
  progress: number;
  currentFilter: FilterType;
  processedFrames: ProcessedFrame[];
  error: string | null;
  isProcessingFullVideo: boolean;
  videoJobId: string | null;
  processedVideoUrl: string | null;
  message: string | null;
}

export interface UseVideoProcessorReturn {
  // State
  state: VideoProcessingState;
  
  // Actions
  processCurrentFrame: () => Promise<void>;
  processFrameAtTimestamp: (timestamp: number) => Promise<void>;
  processFullVideo: (videoUrl: string, clipStart?: number, clipEnd?: number, filterType?: FilterType | null, backgroundImage?: string | null) => Promise<void>;
  setFilter: (filter: FilterType) => void;
  clearProcessedFrames: () => void;
  clearError: () => void;
  
  // Utilities
  getProcessedFrameAtTimestamp: (timestamp: number) => ProcessedFrame | null;
  displayProcessedFrame: (canvas: HTMLCanvasElement, frame: ProcessedFrame) => Promise<void>;
}

const API_URL = 'http://127.0.0.1:8080';
const POLL_INTERVAL = 1000; // Poll every second for video processing status

export function useVideoProcessor(
  videoRef: React.RefObject<HTMLVideoElement>,
  apiUrl: string = API_URL
): UseVideoProcessorReturn {
  const [state, setState] = useState<VideoProcessingState>({
    isProcessing: false,
    progress: 0,
    currentFilter: 'grayscale',
    processedFrames: [],
    error: null,
    isProcessingFullVideo: false,
    videoJobId: null,
    processedVideoUrl: null,
    message: null,
  });

  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  // Get or create canvas for frame processing
  const getCanvas = useCallback((): HTMLCanvasElement => {
    if (!canvasRef.current) {
      canvasRef.current = createCanvas(640, 480); // Default size, will be resized
    }
    return canvasRef.current;
  }, []);

  // Set filter type
  const setFilter = useCallback((filter: FilterType) => {
    setState((prev) => ({ ...prev, currentFilter: filter }));
  }, []);

  // Clear processed frames
  const clearProcessedFrames = useCallback(() => {
    setState((prev) => ({
      ...prev,
      processedFrames: [],
      processedVideoUrl: null,
    }));
  }, []);

  // Clear error
  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  // Process current video frame
  const processCurrentFrame = useCallback(async () => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) {
      setState((prev) => ({
        ...prev,
        error: 'Video is not ready. Please wait for video to load.',
      }));
      return;
    }

    setState((prev) => ({
      ...prev,
      isProcessing: true,
      error: null,
    }));

    try {
      const result = await captureAndProcessFrame(video, state.currentFilter, apiUrl);
      const timestamp = video.currentTime;

      setState((prev) => ({
        ...prev,
        isProcessing: false,
        processedFrames: [
          ...prev.processedFrames,
          {
            frameBase64: result.processedFrame,
            timestamp,
            processingTime: result.processingTime,
          },
        ],
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to process frame';
      setState((prev) => ({
        ...prev,
        isProcessing: false,
        error: errorMessage,
      }));
    }
  }, [videoRef, state.currentFilter, apiUrl]);

  // Process frame at specific timestamp
  const processFrameAtTimestamp = useCallback(
    async (timestamp: number) => {
      const video = videoRef.current;
      if (!video || video.readyState < 2) {
        setState((prev) => ({
          ...prev,
          error: 'Video is not ready. Please wait for video to load.',
        }));
        return;
      }

      setState((prev) => ({
        ...prev,
        isProcessing: true,
        error: null,
      }));

      try {
        const canvas = getCanvas();
        await captureVideoFrame(video, canvas, timestamp);
        const frameBase64 = frameToBase64(canvas);
        const result = await processFrame(frameBase64, state.currentFilter, apiUrl);

        setState((prev) => ({
          ...prev,
          isProcessing: false,
          processedFrames: [
            ...prev.processedFrames,
            {
              frameBase64: result.processedFrame,
              timestamp,
              processingTime: result.processingTime,
            },
          ],
        }));
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to process frame';
        setState((prev) => ({
          ...prev,
          isProcessing: false,
          error: errorMessage,
        }));
      }
    },
    [videoRef, state.currentFilter, apiUrl, getCanvas]
  );

  // Poll for video processing status
  const pollVideoStatus = useCallback(
    async (jobId: string) => {
      try {
        const response = await fetch(`${apiUrl}/process-status/${jobId}`);
        if (!response.ok) {
          throw new Error('Failed to fetch processing status');
        }

        const data = await response.json();

        setState((prev) => ({
          ...prev,
          progress: data.progress || 0,
          isProcessingFullVideo: data.status === 'processing',
          message: data.message || null,
        }));

        if (data.status === 'completed') {
          // Stop polling
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }

          setState((prev) => ({
            ...prev,
            isProcessingFullVideo: false,
            progress: 100,
            processedVideoUrl: data.result_url,
            videoJobId: null,
            message: data.message || 'Video processing complete',
          }));
        } else if (data.status === 'error') {
          // Stop polling
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }

          setState((prev) => ({
            ...prev,
            isProcessingFullVideo: false,
            error: data.error || 'Video processing failed',
            videoJobId: null,
            message: data.message || null,
          }));
        }
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to check processing status';
        setState((prev) => ({
          ...prev,
          error: errorMessage,
        }));
      }
    },
    [apiUrl]
  );

  // Process full video
  const processFullVideo = useCallback(
    async (videoUrl: string, clipStart?: number, clipEnd?: number, filterType?: FilterType | null, backgroundImage?: string | null) => {
      setState((prev) => ({
        ...prev,
        isProcessingFullVideo: true,
        progress: 0,
        error: null,
        videoJobId: null,
        message: 'Starting video processing...',
      }));

      try {
        // Build request body
        const requestBody: any = {
          video_url: videoUrl,
        };
        
        // Add filter type (null for clipping only)
        if (filterType !== null && filterType !== undefined) {
          requestBody.filter_type = filterType;
        } else {
          requestBody.filter_type = null;
        }
        
        // Add clip parameters if provided
        if (clipStart !== undefined && clipStart !== null) {
          requestBody.clip_start = clipStart;
        }
        if (clipEnd !== undefined && clipEnd !== null) {
          requestBody.clip_end = clipEnd;
        }
        
        // Add background image if provided
        if (backgroundImage) {
          // Check if it's a URL (template image) or base64 (uploaded image)
          if (backgroundImage.startsWith('http://') || backgroundImage.startsWith('https://')) {
            // It's a URL - send as-is
            requestBody.background_image = backgroundImage;
          } else {
            // It's base64 data - remove data URL prefix if present
            const base64Data = backgroundImage.includes(',') 
              ? backgroundImage.split(',')[1] 
              : backgroundImage;
            requestBody.background_image = base64Data;
          }
        }
        
        const response = await fetch(`${apiUrl}/process-video`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
          throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const jobId = data.job_id;

        setState((prev) => ({
          ...prev,
          videoJobId: jobId,
        }));

        // Start polling for status
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }

        pollingIntervalRef.current = setInterval(() => {
          pollVideoStatus(jobId);
        }, POLL_INTERVAL);

        // Initial status check
        pollVideoStatus(jobId);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to start video processing';
        setState((prev) => ({
          ...prev,
          isProcessingFullVideo: false,
          error: errorMessage,
          videoJobId: null,
        }));
      }
    },
    [state.currentFilter, apiUrl, pollVideoStatus]
  );

  // Get processed frame at specific timestamp
  const getProcessedFrameAtTimestamp = useCallback(
    (timestamp: number): ProcessedFrame | null => {
      // Find the closest processed frame to the given timestamp
      const sortedFrames = [...state.processedFrames].sort(
        (a, b) => Math.abs(a.timestamp - timestamp) - Math.abs(b.timestamp - timestamp)
      );

      if (sortedFrames.length === 0) {
        return null;
      }

      const closest = sortedFrames[0];
      // Return frame if it's within 0.5 seconds of the timestamp
      if (Math.abs(closest.timestamp - timestamp) < 0.5) {
        return closest;
      }

      return null;
    },
    [state.processedFrames]
  );

  // Display processed frame on canvas
  const displayProcessedFrame = useCallback(
    async (canvas: HTMLCanvasElement, frame: ProcessedFrame) => {
      try {
        await drawImageToCanvas(frame.frameBase64, canvas);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to display processed frame';
        setState((prev) => ({
          ...prev,
          error: errorMessage,
        }));
      }
    },
    []
  );

  return {
    state,
    processCurrentFrame,
    processFrameAtTimestamp,
    processFullVideo,
    setFilter,
    clearProcessedFrames,
    clearError,
    getProcessedFrameAtTimestamp,
    displayProcessedFrame,
  };
}

