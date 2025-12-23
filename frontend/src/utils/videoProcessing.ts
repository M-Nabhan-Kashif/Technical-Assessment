/**
 * Video Processing Utilities
 * 
 * Functions for capturing video frames, converting to/from base64,
 * and handling video processing operations.
 */

/**
 * Capture a frame from a video element and draw it to a canvas
 * 
 * @param video - HTML video element to capture frame from
 * @param canvas - HTML canvas element to draw frame to
 * @param timestamp - Optional timestamp in seconds to seek to before capturing
 * @returns Promise that resolves when frame is captured
 */
export async function captureVideoFrame(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  timestamp?: number
): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      // Set canvas dimensions to match video
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      // Define drawFrame as a function expression (ES5 compatible)
      const drawFrame = () => {
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Failed to get canvas context'));
          return;
        }

        // Draw current video frame to canvas
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        resolve();
      };

      // If timestamp is provided, seek to that position
      if (timestamp !== undefined) {
        video.currentTime = timestamp;
        
        const onSeeked = () => {
          video.removeEventListener('seeked', onSeeked);
          drawFrame();
        };
        
        video.addEventListener('seeked', onSeeked);
      } else {
        drawFrame();
      }
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Convert canvas content to base64 encoded string
 * 
 * @param canvas - HTML canvas element to convert
 * @param format - Image format (default: 'image/jpeg')
 * @param quality - JPEG quality 0-1 (default: 0.95)
 * @returns Base64 encoded image string (without data URL prefix)
 */
export function frameToBase64(
  canvas: HTMLCanvasElement,
  format: string = 'image/jpeg',
  quality: number = 0.95
): string {
  const base64 = canvas.toDataURL(format, quality);
  
  // Remove data URL prefix (e.g., "data:image/jpeg;base64,")
  const base64Data = base64.split(',')[1];
  
  return base64Data;
}

/**
 * Convert base64 string to Image object
 * 
 * @param base64 - Base64 encoded image string (with or without data URL prefix)
 * @returns Promise that resolves with HTMLImageElement
 */
export function base64ToImage(base64: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    
    // Add data URL prefix if not present
    const dataUrl = base64.startsWith('data:') 
      ? base64 
      : `data:image/jpeg;base64,${base64}`;
    
    img.onload = () => resolve(img);
    img.onerror = (error) => reject(new Error('Failed to load image from base64'));
    img.src = dataUrl;
  });
}

/**
 * Draw an image to a canvas element
 * 
 * @param image - HTMLImageElement or base64 string to draw
 * @param canvas - HTML canvas element to draw to
 * @returns Promise that resolves when image is drawn
 */
export async function drawImageToCanvas(
  image: HTMLImageElement | string,
  canvas: HTMLCanvasElement
): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Failed to get canvas context'));
        return;
      }

      if (typeof image === 'string') {
        // If image is a base64 string, convert it first
        base64ToImage(image).then((img) => {
          canvas.width = img.width;
          canvas.height = img.height;
          ctx.drawImage(img, 0, 0);
          resolve();
        }).catch(reject);
      } else {
        // If image is already an HTMLImageElement
        canvas.width = image.width;
        canvas.height = image.height;
        ctx.drawImage(image, 0, 0);
        resolve();
      }
    } catch (error) {
      reject(error);
    }
  });
}

/**
 * Create a canvas element (helper function)
 * 
 * @param width - Canvas width
 * @param height - Canvas height
 * @returns HTMLCanvasElement
 */
export function createCanvas(width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

/**
 * Download processed video or image
 * 
 * @param dataUrl - Data URL of the content to download
 * @param filename - Name for the downloaded file
 */
export function downloadFile(dataUrl: string, filename: string): void {
  const link = document.createElement('a');
  link.href = dataUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Download processed video from blob URL
 * 
 * @param blobUrl - Blob URL of the video
 * @param filename - Name for the downloaded file (default: 'processed-video.mp4')
 */
export function downloadProcessedVideo(blobUrl: string, filename: string = 'processed-video.mp4'): void {
  fetch(blobUrl)
    .then(response => response.blob())
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      downloadFile(url, filename);
      // Clean up the blob URL after a delay
      setTimeout(() => window.URL.revokeObjectURL(url), 100);
    })
    .catch(error => {
      console.error('Error downloading video:', error);
    });
}

/**
 * Get video frame at specific timestamp
 * 
 * @param video - HTML video element
 * @param timestamp - Timestamp in seconds
 * @returns Promise that resolves with base64 encoded frame
 */
export async function getFrameAtTimestamp(
  video: HTMLVideoElement,
  timestamp: number
): Promise<string> {
  const canvas = createCanvas(video.videoWidth, video.videoHeight);
  await captureVideoFrame(video, canvas, timestamp);
  return frameToBase64(canvas);
}

/**
 * Process a single frame through the backend API
 * 
 * @param frameBase64 - Base64 encoded frame
 * @param filterType - Filter type to apply ('grayscale', 'sepia', 'blur')
 * @param apiUrl - Backend API URL (default: 'http://127.0.0.1:8080')
 * @returns Promise that resolves with processed frame base64 and processing time
 */
export async function processFrame(
  frameBase64: string,
  filterType: string = 'grayscale',
  apiUrl: string = 'http://127.0.0.1:8080'
): Promise<{ processedFrame: string; processingTime: number }> {
  try {
    const response = await fetch(`${apiUrl}/process-frame`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        frame: frameBase64,
        filter_type: filterType,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return {
      processedFrame: data.processed_frame,
      processingTime: data.processing_time,
    };
  } catch (error) {
    console.error('Error processing frame:', error);
    throw error;
  }
}

/**
 * Capture and process a frame from video
 * 
 * @param video - HTML video element
 * @param filterType - Filter type to apply
 * @param apiUrl - Backend API URL
 * @returns Promise that resolves with processed frame base64 and processing time
 */
export async function captureAndProcessFrame(
  video: HTMLVideoElement,
  filterType: string = 'grayscale',
  apiUrl: string = 'http://127.0.0.1:8080'
): Promise<{ processedFrame: string; processingTime: number }> {
  const canvas = createCanvas(video.videoWidth, video.videoHeight);
  await captureVideoFrame(video, canvas);
  const frameBase64 = frameToBase64(canvas);
  return processFrame(frameBase64, filterType, apiUrl);
}

