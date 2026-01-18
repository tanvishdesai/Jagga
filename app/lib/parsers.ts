import { UnifiedMessage } from './types';

export const parseWhatsApp = (text: string): UnifiedMessage[] => {
  const messages: UnifiedMessage[] = [];
  const pattern = /^(\d{2}\/\d{2}\/\d{4}), (\d{2}:\d{2}) - (.*?): (.*)$/;

  let currentMsg: UnifiedMessage | null = null;

  const lines = text.split('\n');

  for (let line of lines) {
    line = line.trim();
    if (!line) continue;

    // Note: The date format in the regex assumes DD/MM/YYYY.
    // Sometimes WhatsApp exports might use MM/DD/YYYY or other formats depending on locale.
    // For now we stick to the Python regex logic.
    const match = line.match(pattern);

    if (match) {
      if (currentMsg) {
        messages.push(currentMsg);
      }

      const [, dateStr, timeStr, sender, content] = match;

      if (content.trim() === '<Media omitted>') {
        currentMsg = null;
        continue;
      }

      // Parse date
      // dateStr is DD/MM/YYYY
      const [day, month, year] = dateStr.split('/').map(Number);
      const [hours, minutes] = timeStr.split(':').map(Number);

      const date = new Date(year, month - 1, day, hours, minutes);

      currentMsg = {
        timestamp: date,
        platform: 'WhatsApp',
        sender: sender.trim(),
        content: content
      };
    } else {
      if (currentMsg) {
        currentMsg.content += `\n${line}`;
      }
    }
  }

  if (currentMsg) {
    messages.push(currentMsg);
  }

  return messages;
};
