# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuakeSense is a full-stack application with a React frontend and Python Flask backend for earthquake monitoring and analysis using machine learning.

**Current State**: The project is in early setup phase with empty backend implementation files and a basic React frontend scaffold.

## Architecture

### Frontend (`frontend/`)
- **Framework**: React 19.2.0 with Vite (rolldown-vite@7.2.5)
- **Styling**: Tailwind CSS v4 with shadcn/ui component system
- **Build Tool**: Vite with Rolldown bundler
- **Component Library**: shadcn/ui (New York style, using Lucide icons)
- **Path Aliases**: `@/*` maps to `./src/*` (configured in jsconfig.json)

### Backend (`backend/`)
- **Framework**: Flask 3.0.0+ with Flask-CORS
- **ML Stack**: scikit-learn, numpy, pandas, scipy, matplotlib
- **Data Processing**: joblib for model persistence
- **Environment**: Python virtual environment in `backend/venv/`

### Key Integration Points
- Frontend expects to make HTTP requests to Flask backend
- Backend will serve ML predictions and earthquake data
- CORS enabled for cross-origin requests between frontend and backend

## Development Commands

### Frontend Development
```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Start dev server (Vite HMR)
npm run build        # Production build
npm run preview      # Preview production build
npm run lint         # Run ESLint
```

### Backend Development
```bash
cd backend
python -m venv venv                    # Create virtual environment (if needed)
source venv/bin/activate               # Activate venv (Linux/Mac)
venv\Scripts\activate                  # Activate venv (Windows)
pip install -r requirements.txt        # Install dependencies
python quake.py                        # Run Flask server (when implemented)
```

### Component Development
The project uses shadcn/ui components. To add new components:
```bash
cd frontend
npx shadcn@latest add <component-name>
```

Components are configured in `components.json` to use:
- New York style
- JavaScript (not TypeScript)
- CSS variables for theming
- Lucide icons

## Current Implementation

### Frontend Components
The frontend includes a complete earthquake monitoring dashboard:
- `Dashboard.jsx` - Main container with stats and layout
- `EarthquakeAlerts.jsx` - Real-time alert banner system
- `EarthquakeStats.jsx` - Magnitude distribution and depth analysis
- `FrequencyChart.jsx` - Interactive frequency chart (7d/30d/90d views)
- `EarthquakeTable.jsx` - Comprehensive data table with filtering

**Key Features**:
- Real-time earthquake alerts with severity classification
- AI false alarm detection indicators
- Interactive charts and statistics
- Filterable earthquake history table
- Dark theme optimized for monitoring stations

### Backend Status
**Backend files are currently empty**: `backend/quake.py` and `backend/__init__.py` need implementation. The frontend uses mock data and is ready to connect to Flask API endpoints.

## Important Notes

- **Virtual environment**: Always activate `backend/venv/` before running Python code
- **Path aliases**: Use `@/` prefix for imports (e.g., `import { cn } from "@/lib/utils"`)
- **Styling utility**: The `cn()` function in `@/lib/utils` merges Tailwind classes using `clsx` and `tailwind-merge`
- **Vite override**: The project uses `rolldown-vite` as a drop-in replacement for standard Vite
- **Mock data**: Frontend currently uses generated mock data; replace with API calls when backend is ready
