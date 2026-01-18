'use server';

import { parseWhatsApp } from './lib/parsers';
import { UnifiedMessage } from './lib/types';
import { analyzeChunk, aggregateProfiles, generateGiftRecommendations, generateRelationshipReport } from './lib/analyzer';

// We'll limit the file size or message count if needed, but for now we assume standard processing
const CHUNK_SIZE = 50;

export async function processChat(fileContent: string) {
  try {
    // 1. Parse
    const messages = parseWhatsApp(fileContent);
    if (messages.length === 0) {
      throw new Error("No valid messages found in the file.");
    }

    // 2. Chunk
    const chunks: UnifiedMessage[][] = [];
    for (let i = 0; i < messages.length; i += CHUNK_SIZE) {
      chunks.push(messages.slice(i, i + CHUNK_SIZE));
    }

    console.log(`Split into ${chunks.length} chunks.`);

    // 3. Analyze Chunks
    // We can run these in parallel with a concurrency limit
    // const chunkResults = [];

    // Simple serial for now to avoid overwhelming rate limits if manager isn't perfect,
    // or we can use Promise.all with batching.
    // Given the KeyManager handles rotation, we can try some parallelism.
    // But Vercel server actions have timeouts (default 10s-60s).
    // If the chat is long, this WILL timeout.

    // For a real "website", we should probably return the parsed messages first,
    // then have the client request analysis for chunks progressivly, or use a background job.
    // However, for this task, let's try to process a limited amount or assume reasonable size.
    // Or we can return a "Plan" to the client?

    // Let's implement a simpler flow: Client sends text -> Server parses & chunks -> Client gets chunks info
    // -> Client requests analysis for each chunk (streaming/progress) -> Client requests final aggregation.

    // But since this is a server action, let's just do parsing here.
    return {
        success: true,
        messageCount: messages.length,
        chunks: chunks
    };

  } catch (e: unknown) {
    const err = e as { message?: string };
    return { success: false, error: err.message };
  }
}

export async function analyzeChunkAction(chunkId: number, messages: UnifiedMessage[]) {
    try {
        const result = await analyzeChunk(chunkId, messages);
        return { success: true, chunkId, result };
    } catch (e: unknown) {
        const err = e as { message?: string };
        return { success: false, chunkId, error: err.message };
    }
}

export async function generateFinalReports(chunkResults: Record<string, unknown>[]) {
    try {
        const profile = aggregateProfiles(chunkResults);
        const [giftRecommendations, relationshipReport] = await Promise.all([
            generateGiftRecommendations(profile),
            generateRelationshipReport(profile)
        ]);

        return { success: true, giftRecommendations: giftRecommendations || "", relationshipReport: relationshipReport || "" };
    } catch (e: unknown) {
        const err = e as { message?: string };
        return { success: false, error: err.message };
    }
}
