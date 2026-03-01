import React, { useState, useEffect, useRef } from 'react';
import { sendChatMessage, getErrorMessage, validateMessage } from './api';

// Generate UUID v4
const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

const ChatWidget = () => {
  // State management
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [sessionId] = useState(() => generateUUID());
  const [hasShownWelcome, setHasShownWelcome] = useState(false);
  const [userMessageCount, setUserMessageCount] = useState(0);
  
  const messagesEndRef = useRef(null);
  const eventSourceRef = useRef(null);

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Show welcome message on first open
  useEffect(() => {
    if (isOpen && !hasShownWelcome) {
      const welcomeMessage = {
        id: Date.now(),
        type: 'agent',
        text: `Hi! I am IVY AI Counsellor. I can help you with:\nUniversities, Visas, Scholarships, IELTS/PTE,\nCosts and Post-Study Work Visas.\nWhat would you like to know?`,
        timestamp: new Date()
      };
      setMessages([welcomeMessage]);
      setHasShownWelcome(true);
    }
  }, [isOpen, hasShownWelcome]);

  // Handle opening chat window
  const handleOpen = () => {
    setIsOpen(true);
    setUnreadCount(0);
  };

  // Handle closing chat window
  const handleClose = () => {
    setIsOpen(false);
  };

  // Handle sending message
  const handleSend = async () => {
    if (!inputValue.trim()) return;

    // Validate message
    if (!validateMessage(inputValue)) {
      return;
    }

    const userMessage = {
      id: Date.now(),
      type: 'user',
      text: inputValue,
      timestamp: new Date()
    };

    const messageToSend = inputValue;
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);
    setUserMessageCount(prev => prev + 1);

    // Create placeholder for agent response
    const agentMessageId = Date.now() + 1;
    const agentMessage = {
      id: agentMessageId,
      type: 'agent',
      text: '',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, agentMessage]);

    // Use the new API integration
    sendChatMessage(
      sessionId,
      messageToSend,
      // onToken callback
      (token) => {
        setMessages(prev => prev.map(msg => 
          msg.id === agentMessageId 
            ? { ...msg, text: msg.text + token }
            : msg
        ));
      },
      // onComplete callback
      () => {
        setIsTyping(false);
        // If chat is closed, increment unread count
        if (!isOpen) {
          setUnreadCount(prev => prev + 1);
        }
      },
      // onError callback
      (error) => {
        console.error('Error sending message:', error);
        const errorMessage = getErrorMessage(error);
        setMessages(prev => prev.map(msg => 
          msg.id === agentMessageId 
            ? { ...msg, text: errorMessage }
            : msg
        ));
        setIsTyping(false);
      }
    );
  };

  // Handle Enter key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Typing indicator component
  const TypingIndicator = () => (
    <div style={styles.typingIndicator}>
      <div style={styles.typingDot}></div>
      <div style={{ ...styles.typingDot, animationDelay: '0.2s' }}></div>
      <div style={{ ...styles.typingDot, animationDelay: '0.4s' }}></div>
    </div>
  );

  // WhatsApp handoff button
  const WhatsAppButton = () => (
    <a
      href="https://wa.me/919105491054"
      target="_blank"
      rel="noopener noreferrer"
      style={styles.whatsappButton}
    >
      <span style={styles.whatsappIcon}>💬</span>
      Chat with a human counsellor on WhatsApp
    </a>
  );

  return (
    <>
      <style>
        {`
          @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
          }
          
          @keyframes typing {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 1; }
          }
        `}
      </style>

      {/* Chat Window */}
      {isOpen && (
        <div style={styles.chatWindow}>
          {/* Header */}
          <div style={styles.header}>
            <div>
              <div style={styles.headerTitle}>IVY AI Counsellor</div>
              <div style={styles.headerSubtext}>Ask me anything about studying abroad</div>
            </div>
            <button onClick={handleClose} style={styles.minimizeButton}>
              −
            </button>
          </div>

          {/* Messages */}
          <div style={styles.messagesContainer}>
            {messages.map((message) => (
              <div
                key={message.id}
                style={{
                  ...styles.messageWrapper,
                  justifyContent: message.type === 'user' ? 'flex-end' : 'flex-start'
                }}
              >
                <div
                  style={{
                    ...styles.message,
                    ...(message.type === 'user' ? styles.userMessage : styles.agentMessage)
                  }}
                >
                  {message.text.split('\n').map((line, i) => (
                    <React.Fragment key={i}>
                      {line}
                      {i < message.text.split('\n').length - 1 && <br />}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))}
            
            {isTyping && (
              <div style={{ ...styles.messageWrapper, justifyContent: 'flex-start' }}>
                <div style={{ ...styles.message, ...styles.agentMessage }}>
                  <TypingIndicator />
                </div>
              </div>
            )}

            {/* WhatsApp handoff button after 3 user messages */}
            {userMessageCount >= 3 && (
              <div style={styles.whatsappButtonWrapper}>
                <WhatsAppButton />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div style={styles.inputContainer}>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              style={styles.input}
              maxLength={500}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim()}
              style={{
                ...styles.sendButton,
                opacity: inputValue.trim() ? 1 : 0.5,
                cursor: inputValue.trim() ? 'pointer' : 'not-allowed'
              }}
            >
              ➤
            </button>
          </div>
        </div>
      )}

      {/* Floating Bubble Button */}
      {!isOpen && (
        <button onClick={handleOpen} style={styles.bubbleButton}>
          <span style={styles.chatIcon}>💬</span>
          {unreadCount > 0 && (
            <div style={styles.unreadBadge}>
              {unreadCount > 9 ? '9+' : unreadCount}
            </div>
          )}
        </button>
      )}
    </>
  );
};

// Styles
const styles = {
  // Floating bubble button
  bubbleButton: {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    width: '60px',
    height: '60px',
    borderRadius: '50%',
    backgroundColor: '#1B5E20',
    border: 'none',
    cursor: 'pointer',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    transition: 'transform 0.2s',
  },
  chatIcon: {
    fontSize: '28px',
    filter: 'grayscale(100%) brightness(200%)',
  },
  unreadBadge: {
    position: 'absolute',
    top: '-5px',
    right: '-5px',
    backgroundColor: '#F9A825',
    color: 'white',
    borderRadius: '50%',
    width: '24px',
    height: '24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '12px',
    fontWeight: 'bold',
    boxShadow: '0 2px 4px rgba(0, 0, 0, 0.2)',
  },

  // Chat window
  chatWindow: {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    width: '380px',
    height: '520px',
    backgroundColor: 'white',
    borderRadius: '12px',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
    display: 'flex',
    flexDirection: 'column',
    zIndex: 1000,
    overflow: 'hidden',
  },

  // Header
  header: {
    backgroundColor: '#1B5E20',
    color: 'white',
    padding: '16px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: '18px',
    fontWeight: 'bold',
    marginBottom: '4px',
  },
  headerSubtext: {
    fontSize: '12px',
    opacity: 0.9,
  },
  minimizeButton: {
    backgroundColor: '#F9A825',
    color: 'white',
    border: 'none',
    borderRadius: '50%',
    width: '32px',
    height: '32px',
    fontSize: '24px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    lineHeight: '1',
    fontWeight: 'bold',
  },

  // Messages
  messagesContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '16px',
    backgroundColor: '#f5f5f5',
  },
  messageWrapper: {
    display: 'flex',
    marginBottom: '12px',
  },
  message: {
    maxWidth: '75%',
    padding: '10px 14px',
    borderRadius: '12px',
    fontSize: '14px',
    lineHeight: '1.4',
    wordWrap: 'break-word',
  },
  userMessage: {
    backgroundColor: '#F9A825',
    color: 'white',
    borderBottomRightRadius: '4px',
  },
  agentMessage: {
    backgroundColor: '#E8F5E9',
    color: '#1B5E20',
    borderBottomLeftRadius: '4px',
  },

  // Typing indicator
  typingIndicator: {
    display: 'flex',
    gap: '4px',
    alignItems: 'center',
  },
  typingDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#1B5E20',
    animation: 'typing 1.4s infinite',
  },

  // WhatsApp button
  whatsappButtonWrapper: {
    display: 'flex',
    justifyContent: 'center',
    marginTop: '16px',
    marginBottom: '8px',
  },
  whatsappButton: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: '#25D366',
    color: 'white',
    padding: '12px 20px',
    borderRadius: '24px',
    textDecoration: 'none',
    fontSize: '14px',
    fontWeight: '500',
    boxShadow: '0 2px 8px rgba(37, 211, 102, 0.3)',
    transition: 'transform 0.2s, box-shadow 0.2s',
  },
  whatsappIcon: {
    fontSize: '18px',
  },

  // Input
  inputContainer: {
    display: 'flex',
    padding: '12px',
    backgroundColor: 'white',
    borderTop: '1px solid #e0e0e0',
    gap: '8px',
  },
  input: {
    flex: 1,
    padding: '10px 14px',
    border: '1px solid #e0e0e0',
    borderRadius: '20px',
    fontSize: '14px',
    outline: 'none',
    fontFamily: 'inherit',
  },
  sendButton: {
    backgroundColor: '#1B5E20',
    color: 'white',
    border: 'none',
    borderRadius: '50%',
    width: '40px',
    height: '40px',
    fontSize: '18px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'background-color 0.2s',
  },
};

export default ChatWidget;
