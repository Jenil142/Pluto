# Pluto

Pluto is a personal AI assistant that helps you with your day-to-day tasks, making them easier to manage alongside your work. Built with Google Gemini, it features persistent memory, tool integrations, and a modern web interface.

## Features

- **Conversational AI** - Powered by Google Gemini with a JARVIS-inspired personality
- **Persistent Memory** - Remembers context across sessions using SQLite-backed conversation history and automatic summarization
- **Tool Integrations**
  - Terminal command execution (with permission controls)
  - Google Calendar (events, tasks, deadlines)
  - Web search (DuckDuckGo)
  - Browser automation (via containerized browser service)
  - Date/time utilities
- **Security Layer** - User confirmation prompts and permission system for sensitive operations
- **Web UI** - React-based chat interface with a settings panel and sidebar
- **API Server** - FastAPI backend with session management
- **Docker Support** - Containerized browser automation service

## Project Structure

```
Pluto/
├── main.py                 # Entry point
├── api.py                  # FastAPI server
├── pluto/                  # Core package
│   ├── core.py             # Chat loop, tool execution, retry logic
│   ├── config.py           # Configuration
│   ├── prompts.py          # System prompts
│   ├── memory/             # Chat history & summarization
│   ├── security/           # Permissions & confirmations
│   └── tools/              # Tool integrations
├── ui/                     # React + Vite frontend
├── docker/                 # Browser automation container
├── tests/                  # Test suite
└── start_pluto_app.sh      # Launch script
```

## Prerequisites

- Python 3.10+
- Node.js 18+ (for the UI)
- A [Google Gemini API key](https://ai.google.dev/)
- Google Calendar API credentials (optional, for calendar features)
- Docker (optional, for browser automation)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/Pluto.git
cd Pluto
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys. At minimum, you need `GEMINI_API_KEY`.

### 5. Run Pluto (CLI)

```bash
python main.py
```

### 6. Run Pluto (Web UI)

Start the API server:

```bash
python api.py
```

In a separate terminal, start the UI dev server:

```bash
cd ui
npm install
npm run dev
```

### 7. Browser automation (optional)

```bash
docker-compose up -d
```

## Google Calendar Setup (Optional)

1. Create a project in the [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google Calendar API
3. Create OAuth 2.0 credentials and download the JSON file
4. Save it as `credentials/google_credentials.json`
5. On first use, Pluto will prompt you to authorize access

## License

This project is licensed under the [MIT License](LICENSE).
