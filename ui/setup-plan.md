## What I found
- **App framework:** React with Vite
- **Package manager:** npm
- **Agent framework:** Custom Python FastAPI backend (Pluto Core)
- **Model provider:** Google Gemini (handled server-side via python SDK)
- **Components:** src/components/
- **Chat route:** http://localhost:8000/api/chat (Returns static JSON, not streaming)

## What I will install
- components.json (shadcn config)
- @assistant-ui/react
- @assistant-ui/thread components via shadcn
- TailwindCSS (required for shadcn)

## Steps
1. Install TailwindCSS and configure vite.config.ts.
2. Initialize shadcn via npx shadcn@latest init --defaults --yes.
3. Add assistant-ui registry to components.json.
4. Run npx shadcn@latest add @assistant-ui/thread.
5. Create a custom transport in React that talks to Pluto's existing REST API (/api/chat).
6. Update App.jsx to render the Assistant-UI <Thread /> component.

## Open questions
- Pluto's existing backend returns a single JSON object. Do you want me to write a custom transport to wrap this non-streaming response into assistant-ui, or would you like me to refactor the Python backend to support streaming?
