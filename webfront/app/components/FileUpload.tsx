'use client';

import { useState, useRef, DragEvent } from 'react';

interface FileUploadProps {
  label: string;
  description: string;
  accept: string;
  required?: boolean;
  file: File | null;
  onFileChange: (file: File | null) => void;
  icon: React.ReactNode;
}

export default function FileUpload({
  label,
  description,
  accept,
  required = false,
  file,
  onFileChange,
  icon,
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      onFileChange(droppedFile);
    }
  };

  const handleClick = () => {
    inputRef.current?.click();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      onFileChange(selectedFile);
    }
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onFileChange(null);
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  return (
    <div className="file-upload-container">
      <div className="file-upload-header">
        <span className="file-upload-label">
          {label}
          {required && <span className="required-badge">Required</span>}
          {!required && <span className="optional-badge">Optional</span>}
        </span>
      </div>
      
      <div
        className={`file-upload-zone ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          className="file-input-hidden"
        />
        
        {file ? (
          <div className="file-preview">
            <div className="file-icon">📄</div>
            <div className="file-info">
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatFileSize(file.size)}</span>
            </div>
            <button className="remove-file-btn" onClick={handleRemove}>
              ✕
            </button>
          </div>
        ) : (
          <div className="upload-prompt">
            <div className="upload-icon">{icon}</div>
            <p className="upload-text">{description}</p>
            <p className="upload-hint">Click or drag file here</p>
          </div>
        )}
      </div>
    </div>
  );
}
