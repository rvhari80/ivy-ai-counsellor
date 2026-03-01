# IVY AI Counsellor Chat Widget - Embed Guide

## Overview

This guide explains how to integrate the IVY AI Counsellor chat widget into any website using the embed script.

## Quick Start

Add this single line to your website's HTML (before the closing `</body>` tag):

```html
<script src="https://chat.ivyoverseas.com/embed.js"></script>
```

That's it! The chat widget will automatically appear in the bottom-right corner of your website.

## Features

### 1. **Lazy Loading**
- Does not block page rendering
- Widget loads asynchronously after page content
- Minimal impact on page load performance

### 2. **Shadow DOM Isolation**
- Prevents CSS conflicts with your website
- Widget styles are completely isolated
- No interference with existing styles

### 3. **Responsive Design**
- Works on desktop and mobile devices
- Optimized for mobile Safari
- Adapts to different screen sizes

### 4. **High Z-Index**
- Fixed positioning with z-index: 99999
- Always visible above other content
- Bottom-right corner placement

### 5. **Cross-Browser Compatible**
- Works on all modern browsers
- Chrome, Firefox, Safari, Edge
- Mobile browsers including iOS Safari

## Advanced Usage

### Manual Control API

The embed script exposes a global API for manual control:

```javascript
// Show the widget
window.IvyChatWidget.show();

// Hide the widget
window.IvyChatWidget.hide();

// Reload the widget
window.IvyChatWidget.reload();
```

### Example: Show widget on button click

```html
<button onclick="window.IvyChatWidget.show()">
  Chat with us
</button>
```

### Example: Hide widget initially

```html
<script src="https://chat.ivyoverseas.com/embed.js"></script>
<script>
  // Wait for widget to load
  window.addEventListener('load', function() {
    window.IvyChatWidget.hide();
  });
</script>
```

## Configuration

### Environment Variables

The widget connects to the backend API using the `REACT_APP_API_URL` environment variable:

- **Production**: `https://api.ivyoverseas.com`
- **Development**: `http://localhost:8000`

Set this in your `.env` file:

```bash
REACT_APP_API_URL=https://api.ivyoverseas.com
```

## API Integration Details

### Backend Endpoint

The widget communicates with the FastAPI backend at:

```
POST /api/chat
```

**Request Body:**
```json
{
  "session_id": "uuid-v4-string",
  "message": "User message text"
}
```

**Response:**
Server-Sent Events (SSE) stream with format:
```
data: {"token": "word", "done": false}
data: {"token": " ", "done": false}
data: {"token": "another", "done": false}
data: {"token": "", "done": true}
```

### Error Handling

The widget includes comprehensive error handling:

1. **Network Failures**: 2 automatic retries with exponential backoff
2. **Timeouts**: 30-second timeout per request
3. **Rate Limiting**: Handles 429 status codes gracefully
4. **Server Errors**: User-friendly error messages

**Error Message:**
> "Sorry, I could not connect. Please try WhatsApp instead."

## Security Features

### Iframe Sandbox

The embed script uses iframe sandboxing for security:

```javascript
iframe.sandbox = 'allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox';
```

### Origin Verification

The widget verifies message origins to prevent XSS attacks:

```javascript
if (event.origin !== WIDGET_URL && event.origin !== 'http://localhost:3000') {
  return; // Ignore messages from unknown origins
}
```

## Deployment

### Building for Production

1. Set environment variables:
```bash
REACT_APP_API_URL=https://api.ivyoverseas.com
```

2. Build the React app:
```bash
cd frontend
npm run build
```

3. Deploy the build folder to your hosting service

4. Ensure `embed.js` is accessible at:
```
https://chat.ivyoverseas.com/embed.js
```

### CORS Configuration

Ensure your backend allows requests from the widget domain:

```python
# In FastAPI backend
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ivyoverseas.com", "https://chat.ivyoverseas.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Testing

### Local Testing

1. Start the backend:
```bash
python main.py
```

2. Start the frontend:
```bash
cd frontend
npm start
```

3. Create a test HTML file:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Widget Test</title>
</head>
<body>
    <h1>Test Page</h1>
    <p>The chat widget should appear in the bottom-right corner.</p>
    
    <script src="http://localhost:3000/embed.js"></script>
</body>
</html>
```

### Production Testing

Test on the actual website:

```html
<script src="https://chat.ivyoverseas.com/embed.js"></script>
```

## Troubleshooting

### Widget Not Appearing

1. Check browser console for errors
2. Verify the embed script URL is correct
3. Ensure JavaScript is enabled
4. Check for Content Security Policy (CSP) restrictions

### Connection Errors

1. Verify `REACT_APP_API_URL` is set correctly
2. Check backend is running and accessible
3. Verify CORS configuration
4. Check network tab in browser DevTools

### CSS Conflicts

The widget uses Shadow DOM to prevent CSS conflicts. If you still experience issues:

1. Check for global CSS that might affect iframes
2. Verify z-index values on your site
3. Ensure no JavaScript is modifying the widget container

## Support

For issues or questions:
- Email: support@ivyoverseas.com
- WhatsApp: +91 9105491054

## License

Copyright © 2026 IVY Overseas. All rights reserved.
