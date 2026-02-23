"""
Application constants.
These are hardcoded values that don't change between environments.
"""

# Intent Classification Constants
INTENT_CATEGORIES = [
    "BROWSING",          # Just looking around, no specific interest
    "RESEARCHING",       # Actively gathering information
    "CONSIDERING",       # Seriously considering options
    "HOT_LEAD"          # Ready to engage, high conversion potential
]

# Conversation Stage Constants
CONVERSATION_STAGES = {
    "INITIAL": "Initial greeting and introduction",
    "DISCOVERY": "Understanding user's goals and background",
    "QUALIFICATION": "Assessing fit and requirements",
    "PRESENTATION": "Presenting services and options",
    "OBJECTION_HANDLING": "Addressing concerns",
    "CLOSING": "Moving toward booking/engagement",
}

# Lead Score Ranges
LEAD_SCORE_RANGES = {
    "COLD": (0, 30),
    "WARM": (31, 60),
    "HOT": (61, 100),
}

# Message Templates
FALLBACK_MESSAGE = (
    "I don't have specific information about that. "
    "Let me connect you with one of our expert counsellors who can help you better. "
    "Would you like me to schedule a consultation?"
)

ERROR_MESSAGE = (
    "I apologize, but I'm experiencing technical difficulties. "
    "Please try again in a moment, or contact us directly at admin@ivyoverseas.com."
)

# File Upload Constants
MAX_PDF_SIZE_MB = 50
ALLOWED_FILE_EXTENSIONS = [".pdf"]

# Chunking Constants
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# Session Constants
SESSION_TIMEOUT_MINUTES = 30
MAX_CONVERSATION_HISTORY = 50  # Maximum messages to keep in memory

# API Version
API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"
