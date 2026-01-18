'use client';

import { useState } from 'react';
import { processChat, analyzeChunkAction, generateFinalReports } from './actions';
import { motion } from 'framer-motion';
import { Upload, FileText, Gift, Heart, Loader2, AlertCircle } from 'lucide-react';

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [status, setStatus] = useState<string>('');
  const [progress, setProgress] = useState(0);

  const [, setChunkResults] = useState<Record<string, unknown>[]>([]); // Keeping this for future visualization of per-chunk results

  const [giftRecommendations, setGiftRecommendations] = useState<string>('');
  const [relationshipReport, setRelationshipReport] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const startAnalysis = async () => {
    if (!file) return;

    setIsProcessing(true);
    setStatus('Reading file...');
    setProgress(0);
    setError(null);
    setGiftRecommendations('');
    setRelationshipReport('');
    setChunkResults([]);

    try {
      const text = await file.text();
      setStatus('Parsing and chunking messages...');

      const result = await processChat(text);
      if (!result.success || !result.chunks) {
        throw new Error(result.error || 'Failed to process chat.');
      }

      setStatus(`Found ${result.messageCount} messages. Starting analysis of ${result.chunks.length} chunks...`);

      const results: Record<string, unknown>[] = [];
      const totalChunks = result.chunks.length;

      // Process chunks sequentially or in small batches to show progress
      for (let i = 0; i < totalChunks; i++) {
        setStatus(`Analyzing chunk ${i + 1}/${totalChunks}...`);
        const chunkRes = await analyzeChunkAction(i, result.chunks[i]);
        if (chunkRes.success && chunkRes.result) {
            results.push(chunkRes.result);
        }
        setChunkResults([...results]);
        setProgress(((i + 1) / totalChunks) * 100);
      }

      setStatus('Generating final reports...');
      const reportRes = await generateFinalReports(results);

      if (reportRes.success) {
        setGiftRecommendations(reportRes.giftRecommendations || "");
        setRelationshipReport(reportRes.relationshipReport || "");
        setStatus('Analysis Complete!');
      } else {
        throw new Error(reportRes.error || 'Failed to generate reports.');
      }

    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || "An unknown error occurred");
      setStatus('Error occurred.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <main className="min-h-screen bg-gray-900 text-gray-100 p-4 md:p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-8">

        {/* Header */}
        <header className="text-center space-y-2">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-pink-500 to-purple-500 bg-clip-text text-transparent">
            Chat Insight & Gift AI
          </h1>
          <p className="text-gray-400">
            Upload your WhatsApp chat to discover relationship insights and perfect gift ideas.
          </p>
        </header>

        {/* Upload Section */}
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl">
          <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-600 rounded-lg p-8 hover:border-pink-500 transition-colors bg-gray-800/50">
            <Upload className="w-12 h-12 text-gray-400 mb-4" />
            <label className="cursor-pointer bg-pink-600 hover:bg-pink-700 text-white px-6 py-2 rounded-full font-medium transition-colors">
              <span>Select WhatsApp Chat (.txt)</span>
              <input type="file" accept=".txt" className="hidden" onChange={handleFileChange} disabled={isProcessing} />
            </label>
            {file && (
              <div className="mt-4 flex items-center space-x-2 text-green-400">
                <FileText className="w-4 h-4" />
                <span>{file.name}</span>
              </div>
            )}
          </div>

          {file && !isProcessing && !giftRecommendations && (
            <div className="mt-6 flex justify-center">
              <button
                onClick={startAnalysis}
                className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white text-lg font-bold px-8 py-3 rounded-xl shadow-lg transform transition hover:scale-105"
              >
                Analyze Chat
              </button>
            </div>
          )}

          {/* Progress Section */}
          {isProcessing && (
            <div className="mt-8 space-y-4">
              <div className="flex justify-between text-sm text-gray-300">
                <span>{status}</span>
                <span>{Math.round(progress)}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2.5 overflow-hidden">
                <motion.div
                  className="bg-pink-500 h-2.5 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
              <div className="flex justify-center text-pink-400">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            </div>
          )}

          {error && (
             <div className="mt-6 p-4 bg-red-900/50 border border-red-500 rounded-lg flex items-center space-x-3 text-red-200">
               <AlertCircle className="w-5 h-5 flex-shrink-0" />
               <span>{error}</span>
             </div>
          )}
        </div>

        {/* Results Section */}
        {(giftRecommendations || relationshipReport) && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-700">

            {/* Relationship Report */}
            {relationshipReport && (
              <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl overflow-hidden">
                <div className="flex items-center space-x-3 mb-6 border-b border-gray-700 pb-4">
                  <Heart className="w-6 h-6 text-pink-500" />
                  <h2 className="text-2xl font-bold text-white">Relationship Insights</h2>
                </div>
                <div className="prose prose-invert max-w-none text-gray-300">
                  <pre className="whitespace-pre-wrap font-sans">{relationshipReport}</pre>
                </div>
              </div>
            )}

            {/* Gift Recommendations */}
            {giftRecommendations && (
              <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 shadow-xl overflow-hidden">
                <div className="flex items-center space-x-3 mb-6 border-b border-gray-700 pb-4">
                  <Gift className="w-6 h-6 text-purple-500" />
                  <h2 className="text-2xl font-bold text-white">Gift Recommendations</h2>
                </div>
                <div className="prose prose-invert max-w-none text-gray-300">
                    <pre className="whitespace-pre-wrap font-sans">{giftRecommendations}</pre>
                </div>
              </div>
            )}

          </div>
        )}

      </div>
    </main>
  );
}
