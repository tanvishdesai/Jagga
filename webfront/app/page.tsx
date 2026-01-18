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
    <div className="app-shell">
      <div className="bg-aurora"></div>
      <div className="bg-grid"></div>

      <main className="page">
        <header className="topbar">
          <div className="brand">
            <span className="brand-icon">💬</span>
            <div>
              <p className="brand-name">Jagga</p>
              <p className="brand-tag">Chat export converter</p>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="pill">Private by design</span>
          </div>
        </header>

        <section className="hero">
          <div className="hero-copy">
            <span className="eyebrow">AI-ready chat datasets</span>
            <h1>Turn WhatsApp + Instagram exports into clean JSON</h1>
            <p>
              Upload your chat exports, optionally compress the output, and download a neatly
              packaged zip in seconds. Built for researchers, analysts, and personal archiving.
            </p>
            <div className="hero-badges">
              <span className="badge">Zero storage</span>
              <span className="badge">Fast processing</span>
              <span className="badge">Local friendly</span>
            </div>
          </div>
          <div className="hero-card">
            <div className="hero-card-title">How it works</div>
            <ol className="steps">
              <li>
                <span className="step-index">01</span>
                <div>
                  <p className="step-title">Upload exports</p>
                  <p className="step-text">WhatsApp .txt and optional Instagram .json</p>
                </div>
              </li>
              <li>
                <span className="step-index">02</span>
                <div>
                  <p className="step-title">Process securely</p>
                  <p className="step-text">Clean, normalize, and structure messages</p>
                </div>
              </li>
              <li>
                <span className="step-index">03</span>
                <div>
                  <p className="step-title">Download zip</p>
                  <p className="step-text">Ready-to-use JSON for AI and analytics</p>
                </div>
              </li>
            </ol>
          </div>
        </section>

        <section className="content-grid">
          <div className="panel">
            <div className="panel-header">
              <h2>Upload your files</h2>
              <p>Drag, drop, and let Jagga do the rest.</p>
            </div>

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

            {error && (
              <div className="error-message">
                <span className="error-icon">⚠️</span>
                {error}
              </div>
            )}

            {progress && (
              <div className="progress-message">
                <span className="progress-spinner"></span>
                {progress}
              </div>
            )}

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

          <aside className="panel panel-alt">
            <div className="panel-header">
              <h3>Quality checks</h3>
              <p>We format, validate, and package your data for downstream use.</p>
            </div>
            <div className="stat-list">
              <div className="stat">
                <span className="stat-label">Output</span>
                <span className="stat-value">Structured JSON</span>
              </div>
              <div className="stat">
                <span className="stat-label">Processing</span>
                <span className="stat-value">Smart parsing</span>
              </div>
              <div className="stat">
                <span className="stat-label">Delivery</span>
                <span className="stat-value">Instant zip</span>
              </div>
            </div>
            <div className="info-card">
              <p className="info-title">Tip</p>
              <p className="info-text">
                For massive exports, turn on compression and keep the browser tab open until
                your download starts.
              </p>
            </div>
          </aside>
        </section>

        <section className="feature-strip">
          <div className="feature-card">
            <div className="feature-icon">📤</div>
            <h3>Easy Upload</h3>
            <p>Drag and drop your chat exports</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">🧠</div>
            <h3>AI Friendly</h3>
            <p>Normalized message structure</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">⚡</div>
            <h3>Quick Download</h3>
            <p>Get your files as a zip archive</p>
          </div>
        </section>

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
