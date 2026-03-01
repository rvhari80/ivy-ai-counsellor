/**
 * IVY AI Counsellor Chat Widget Embed Script
 * 
 * Usage: <script src="https://chat.ivyoverseas.com/embed.js"></script>
 * 
 * Features:
 * - Lazy loading (does not block page rendering)
 * - Shadow DOM (prevents CSS conflicts)
 * - Responsive design (works on mobile Safari)
 * - Fixed bottom-right positioning with high z-index
 */

(function() {
  'use strict';

  // Configuration
  const WIDGET_URL = 'https://chat.ivyoverseas.com';
  const IFRAME_ID = 'ivy-chat-widget-iframe';
  const CONTAINER_ID = 'ivy-chat-widget-container';

  // Prevent multiple initializations
  if (window.IvyChatWidgetLoaded) {
    console.warn('IVY Chat Widget already loaded');
    return;
  }
  window.IvyChatWidgetLoaded = true;

  /**
   * Initialize the chat widget
   */
  function initWidget() {
    try {
      // Create container element
      const container = document.createElement('div');
      container.id = CONTAINER_ID;
      
      // Attach shadow DOM to prevent CSS conflicts
      const shadowRoot = container.attachShadow({ mode: 'open' });

      // Create styles for shadow DOM
      const style = document.createElement('style');
      style.textContent = `
        :host {
          all: initial;
          display: block;
        }
        
        .ivy-widget-wrapper {
          position: fixed;
          bottom: 0;
          right: 0;
          z-index: 99999;
          pointer-events: none;
        }
        
        .ivy-widget-iframe {
          border: none;
          width: 100vw;
          height: 100vh;
          max-width: 420px;
          max-height: 600px;
          pointer-events: auto;
          background: transparent;
        }
        
        /* Mobile responsiveness */
        @media (max-width: 768px) {
          .ivy-widget-iframe {
            max-width: 100vw;
            max-height: 100vh;
          }
        }
        
        /* Ensure visibility on mobile Safari */
        @supports (-webkit-touch-callout: none) {
          .ivy-widget-wrapper {
            -webkit-transform: translate3d(0, 0, 0);
            transform: translate3d(0, 0, 0);
          }
        }
      `;

      // Create wrapper div
      const wrapper = document.createElement('div');
      wrapper.className = 'ivy-widget-wrapper';

      // Create iframe
      const iframe = document.createElement('iframe');
      iframe.id = IFRAME_ID;
      iframe.className = 'ivy-widget-iframe';
      iframe.src = WIDGET_URL;
      iframe.title = 'IVY AI Counsellor Chat Widget';
      iframe.allow = 'clipboard-write';
      iframe.loading = 'lazy'; // Lazy load iframe
      
      // Security attributes
      iframe.sandbox = 'allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox';

      // Assemble shadow DOM
      wrapper.appendChild(iframe);
      shadowRoot.appendChild(style);
      shadowRoot.appendChild(wrapper);

      // Add container to page
      document.body.appendChild(container);

      // Handle iframe load
      iframe.addEventListener('load', function() {
        console.log('IVY Chat Widget loaded successfully');
      });

      // Handle iframe errors
      iframe.addEventListener('error', function(e) {
        console.error('IVY Chat Widget failed to load:', e);
      });

      // Listen for messages from iframe (for future features like resize)
      window.addEventListener('message', function(event) {
        // Verify origin for security
        if (event.origin !== WIDGET_URL && event.origin !== 'http://localhost:3000') {
          return;
        }

        // Handle messages from widget
        if (event.data && event.data.type === 'ivy-widget') {
          switch (event.data.action) {
            case 'resize':
              // Future: Handle dynamic resizing
              if (event.data.width) {
                iframe.style.maxWidth = event.data.width + 'px';
              }
              if (event.data.height) {
                iframe.style.maxHeight = event.data.height + 'px';
              }
              break;
            
            case 'close':
              // Future: Handle widget close
              container.style.display = 'none';
              break;
            
            case 'open':
              // Future: Handle widget open
              container.style.display = 'block';
              break;
          }
        }
      });

    } catch (error) {
      console.error('Error initializing IVY Chat Widget:', error);
    }
  }

  /**
   * Wait for DOM to be ready before initializing
   */
  function ready(fn) {
    if (document.readyState !== 'loading') {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  // Initialize widget when DOM is ready
  ready(initWidget);

  // Expose API for manual control (optional)
  window.IvyChatWidget = {
    show: function() {
      const container = document.getElementById(CONTAINER_ID);
      if (container) {
        container.style.display = 'block';
      }
    },
    hide: function() {
      const container = document.getElementById(CONTAINER_ID);
      if (container) {
        container.style.display = 'none';
      }
    },
    reload: function() {
      const iframe = document.getElementById(IFRAME_ID);
      if (iframe) {
        iframe.src = iframe.src;
      }
    }
  };

})();
