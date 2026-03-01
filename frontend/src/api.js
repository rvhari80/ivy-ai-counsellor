/**
 * API Integration for IVY AI Counsellor Chat Widget
 * 
 * Features:
 * - Server-Sent Events (SSE) streaming
 * - Automatic retry logic (2 retries on network failure)
 * - 30-second timeout
 * - Error handling with user-friendly messages
 */

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const CHAT_ENDPOINT = `${API_URL}/api/v1/chat`;
const REQUEST_TIMEOUT = 30000; // 30 seconds
const MAX_RETRIES = 2;

/**
 * Send a chat message and handle SSE streaming response
 * 
 * @param {string} sessionId - Unique session identifier
 * @param {string} message - User message
 * @param {Function} onToken - Callback for each received token: (token: string) => void
 * @param {Function} onComplete - Callback when streaming is complete: () => void
 * @param {Function} onError - Callback for errors: (error: Error) => void
 * @param {number} retryCount - Current retry attempt (internal use)
 */
export async function sendChatMessage(
  sessionId,
  message,
  onToken,
  onComplete,
  onError,
  retryCount = 0
) {
  let timeoutId = null;
  let reader = null;
  let aborted = false;

  try {
    // Create abort controller for timeout
    const controller = new AbortController();
    
    // Set timeout
    timeoutId = setTimeout(() => {
      aborted = true;
      controller.abort();
    }, REQUEST_TIMEOUT);

    // Send POST request
    const response = await fetch(CHAT_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        session_id: sessionId,
        message: message,
      }),
      signal: controller.signal,
    });

    // Clear timeout on successful connection
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }

    // Check response status
    if (!response.ok) {
      if (response.status === 429) {
        throw new Error('RATE_LIMIT');
      } else if (response.status >= 500) {
        throw new Error('SERVER_ERROR');
      } else {
        throw new Error('REQUEST_FAILED');
      }
    }

    // Read SSE stream
    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }

      // Decode chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });
      
      // Process complete lines
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer

      for (const line of lines) {
        // SSE format: "data: {...}"
        if (line.startsWith('data: ')) {
          try {
            const jsonData = line.slice(6); // Remove "data: " prefix
            const data = JSON.parse(jsonData);

            if (data.done) {
              // Streaming complete
              onComplete();
              return;
            } else if (data.token) {
              // New token received
              onToken(data.token);
            }
          } catch (parseError) {
            console.error('Error parsing SSE data:', parseError);
            // Continue processing other lines
          }
        }
      }
    }

    // If we reach here without done:true, call onComplete anyway
    onComplete();

  } catch (error) {
    // Clean up timeout
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    // Clean up reader
    if (reader) {
      try {
        await reader.cancel();
      } catch (e) {
        // Ignore cancel errors
      }
    }

    // Handle different error types
    if (error.name === 'AbortError' || aborted) {
      // Timeout error
      if (retryCount < MAX_RETRIES) {
        console.log(`Request timeout, retrying... (${retryCount + 1}/${MAX_RETRIES})`);
        return sendChatMessage(sessionId, message, onToken, onComplete, onError, retryCount + 1);
      } else {
        onError(new Error('TIMEOUT'));
      }
    } else if (error.message === 'RATE_LIMIT') {
      // Rate limit error - don't retry
      onError(new Error('RATE_LIMIT'));
    } else if (error.message === 'Failed to fetch' || error.message === 'NetworkError' || error.message === 'REQUEST_FAILED') {
      // Network error - retry
      if (retryCount < MAX_RETRIES) {
        console.log(`Network error, retrying... (${retryCount + 1}/${MAX_RETRIES})`);
        // Wait a bit before retrying (exponential backoff)
        await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1)));
        return sendChatMessage(sessionId, message, onToken, onComplete, onError, retryCount + 1);
      } else {
        onError(new Error('NETWORK_ERROR'));
      }
    } else {
      // Other errors - don't retry
      onError(error);
    }
  }
}

/**
 * Get user-friendly error message
 * 
 * @param {Error} error - Error object
 * @returns {string} User-friendly error message
 */
export function getErrorMessage(error) {
  switch (error.message) {
    case 'TIMEOUT':
      return 'Sorry, I could not connect. Please try WhatsApp instead.';
    case 'NETWORK_ERROR':
      return 'Sorry, I could not connect. Please try WhatsApp instead.';
    case 'RATE_LIMIT':
      return 'Please wait a moment before sending another message.';
    case 'SERVER_ERROR':
      return 'Sorry, I could not connect. Please try WhatsApp instead.';
    default:
      return 'Sorry, I could not connect. Please try WhatsApp instead.';
  }
}

/**
 * Validate message before sending
 * 
 * @param {string} message - Message to validate
 * @returns {boolean} True if valid
 */
export function validateMessage(message) {
  if (!message || typeof message !== 'string') {
    return false;
  }
  
  const trimmed = message.trim();
  return trimmed.length > 0 && trimmed.length <= 500;
}
