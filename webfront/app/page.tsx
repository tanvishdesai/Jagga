'use client';

import { useState } from 'react';
import FileUpload from './components/FileUpload';

export default function Home() {
  const [whatsappFile, setWhatsappFile] = useState<File | null>(null);
  const [instagramFile, setInstagramFile] = useState<File | null>(null);
  const [enableCompression, setEnableCompression] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>('');

  const handleProcess = async () => {
    if (!whatsappFile) {
      setError('Please upload a WhatsApp chat file');
      return;
    }

    setIsProcessing(true);
    setError(null);
    setProgress('Uploading files...');

    try {
      const formData = new FormData();
      formData.append('whatsapp_file', whatsappFile);
      if (instagramFile) {
        formData.append('instagram_file', instagramFile);
      }
      formData.append('enable_compression', enableCompression.toString());

      setProgress('Processing messages...');

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/process`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Processing failed');
      }

      setProgress('Downloading zip file...');

      // Get the filename from Content-Disposition header
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = 'processed_chat.zip';
      if (contentDisposition) {
        const match = contentDisposition.match(/filename=(.+)/);
        if (match) {
          filename = match[1];
        }
      }

      // Download the zip file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setProgress('Done! File downloaded.');
      
      // Reset after success
      setTimeout(() => {
        setProgress('');
        setWhatsappFile(null);
        setInstagramFile(null);
        setEnableCompression(false);
      }, 3000);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setProgress('');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="app-container">
      {/* Background decoration */}
      <div className="bg-gradient"></div>
      <div className="bg-pattern"></div>
      
      <main className="main-content">
        {/* Header */}
        <header className="header">
          <div className="logo">
            <span className="logo-icon">💬</span>
            <h1 className="logo-text">Jagga</h1>
          </div>
          <p className="tagline">Transform your chat exports into AI-ready data</p>
        </header>

        {/* Upload Section */}
        <section className="upload-section">
          <div className="card">
            <h2 className="card-title">Upload Your Chat Files</h2>
            <p className="card-description">
              Upload your WhatsApp chat export and optionally add Instagram messages 
              to get preprocessed JSON files ready for AI analysis.
            </p>

            <div className="upload-grid">
              <FileUpload
                label="WhatsApp Chat"
                description="Export your WhatsApp chat as .txt file"
                accept=".txt"
                required={true}
                file={whatsappFile}
                onFileChange={setWhatsappFile}
                icon={<WhatsAppIcon />}
              />

              <FileUpload
                label="Instagram Messages"
                description="Export your Instagram messages as .json file"
                accept=".json"
                required={false}
                file={instagramFile}
                onFileChange={setInstagramFile}
                icon={<InstagramIcon />}
              />
            </div>

            {/* Compression Toggle */}
            <div className="compression-toggle">
              <label className="toggle-container">
                <input
                  type="checkbox"
                  checked={enableCompression}
                  onChange={(e) => setEnableCompression(e.target.checked)}
                  className="toggle-input"
                />
                <span className="toggle-slider"></span>
                <span className="toggle-label">
                  Enable Compression
                  <span className="toggle-hint">Reduces file size for very large chats (~2x smaller)</span>
                </span>
              </label>
            </div>

            {/* Error Message */}
            {error && (
              <div className="error-message">
                <span className="error-icon">⚠️</span>
                {error}
              </div>
            )}

            {/* Progress Message */}
            {progress && (
              <div className="progress-message">
                <span className="progress-spinner"></span>
                {progress}
              </div>
            )}

            {/* Process Button */}
            <button
              className={`process-button ${isProcessing ? 'processing' : ''} ${!whatsappFile ? 'disabled' : ''}`}
              onClick={handleProcess}
              disabled={isProcessing || !whatsappFile}
            >
              {isProcessing ? (
                <>
                  <span className="button-spinner"></span>
                  Processing...
                </>
              ) : (
                <>
                  <span className="button-icon">⚡</span>
                  Process & Download
                </>
              )}
            </button>
          </div>
        </section>

        {/* Features Section */}
        <section className="features-section">
          <div className="features-grid">
            <div className="feature-card">
              <div className="feature-icon">📤</div>
              <h3>Easy Upload</h3>
              <p>Drag and drop your chat exports</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">⚙️</div>
              <h3>Smart Processing</h3>
              <p>Optimized JSON format for AI</p>
            </div>
            <div className="feature-card">
              <div className="feature-icon">📥</div>
              <h3>Instant Download</h3>
              <p>Get your files as a zip archive</p>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="footer">
          <p>Your data is processed locally and never stored on our servers.</p>
        </footer>
      </main>
    </div>
  );
}

// Icon Components
function WhatsAppIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M3 21l1.65-3.8a9 9 0 1 1 3.4 2.9L3 21" />
      <path d="M9 10a.5.5 0 0 0 1 0V9a.5.5 0 0 0-1 0v1a5 5 0 0 0 5 5h1a.5.5 0 0 0 0-1h-1a.5.5 0 0 0 0 1" />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
    </svg>
  );
}
