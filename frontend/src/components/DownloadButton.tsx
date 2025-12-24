import React from 'react';
import { ProcessedFrame } from '../hooks/useVideoProcessor';

interface DownloadButtonProps {
  processedVideoUrl: string | null;
  processedFrames: ProcessedFrame[];
  currentTimestamp?: number;
  disabled?: boolean;
}

const DownloadButton: React.FC<DownloadButtonProps> = ({
  processedVideoUrl,
  processedFrames,
  currentTimestamp,
  disabled = false,
}) => {
  const downloadVideo = () => {
    if (processedVideoUrl) {
      const link = document.createElement('a');
      link.href = processedVideoUrl;
      link.download = `processed-video-${Date.now()}.mp4`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const downloadCurrentFrame = () => {
    if (currentTimestamp !== undefined && processedFrames.length > 0) {
      // Find the closest frame to current timestamp
      const closestFrame = processedFrames.reduce((prev, curr) => {
        const prevDiff = Math.abs(prev.timestamp - currentTimestamp);
        const currDiff = Math.abs(curr.timestamp - currentTimestamp);
        return currDiff < prevDiff ? curr : prev;
      });

      if (closestFrame) {
        const link = document.createElement('a');
        link.href = `data:image/jpeg;base64,${closestFrame.frameBase64}`;
        link.download = `processed-frame-${Date.now()}.jpg`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    }
  };

  return (
    <>
      {processedVideoUrl && (
        <button
          className="btn btn-primary download-button"
          onClick={downloadVideo}
          disabled={disabled || !processedVideoUrl}
        >
          Download Video
        </button>
      )}
      {processedFrames.length > 0 && currentTimestamp !== undefined && (
        <button
          className="btn btn-secondary download-button"
          onClick={downloadCurrentFrame}
          disabled={disabled || processedFrames.length === 0}
        >
          Download Image
        </button>
      )}
    </>
  );
};

export default DownloadButton;

