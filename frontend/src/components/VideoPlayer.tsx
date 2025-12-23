import React, { forwardRef } from 'react';

interface VideoPlayerProps {
  src: string;
  onLoadedMetadata?: () => void;
}

const VideoPlayer = forwardRef<HTMLVideoElement, VideoPlayerProps>(
  ({ src, onLoadedMetadata }, ref) => {
    const handleError = (e: React.SyntheticEvent<HTMLVideoElement, Event>) => {
      const video = e.currentTarget;
      console.error('Video error:', {
        error: video.error,
        networkState: video.networkState,
        readyState: video.readyState,
        src: video.src
      });
    };

    const handleLoadStart = () => {
      console.log('Video load started:', src);
    };

    return (
      <video
        ref={ref}
        src={src}
        className="video-player"
        controls
        onLoadedMetadata={onLoadedMetadata}
        onError={handleError}
        onLoadStart={handleLoadStart}
        crossOrigin="anonymous"
        style={{
          width: '100%',
          height: 'auto',
          maxWidth: '100%',
          display: 'block'
        }}
      />
    );
  }
);

VideoPlayer.displayName = 'VideoPlayer';

export default VideoPlayer; 