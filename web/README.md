# PyJHora Web Application - Setup & Deployment Guide

## Overview

This is a full-stack web application for Vedic Astrology calculations using PyJHora library. It includes:

- **Backend**: FastAPI with MongoDB for data persistence and JWT authentication
- **Frontend**: React SPA with responsive UI
- **Authentication**: User registration and login with JWT tokens
- **Features**: Birth Chart, Horoscope, Compatibility, Dhasa, Transit predictions
- **AI Integration**: Multi-model LLM support (Qwen 2.5, Google Gemini, ChatGPT)
- **Interactive Q&A**: Chat with AI Astrologer for personalized insights

## What's New - AI-Powered Features 🆕

### Ask AI Astrologer
- **Interactive Chat Interface**: Have a conversation with AI about your birth chart
- **Multiple AI Models**: Choose between Qwen 2.5 (local/free), Google Gemini, or ChatGPT
- **Personalized Insights**: Get detailed answers to specific questions about your chart
- **Example Questions**: Pre-built questions to get started quickly
- **Real-time Analysis**: AI analyzes your complete chart data for accurate responses

### Enhanced Predictions
- **AI-Powered Analysis**: All prediction endpoints now support AI enhancement
- **Comprehensive Data**: Uses complete planetary positions, nakshatras, and chart details
- **Compatibility Analysis**: Deep AI analysis of relationship compatibility beyond just scores

## Project Structure

```
pyjhora-web/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # MongoDB models and connection
│   ├── auth.py              # Authentication utilities
│   ├── astrology.py         # PyJHora wrapper
│   ├── qwen_predictor.py    # Qwen LLM integration
│   ├── requirements.txt     # Python dependencies
│   ├── Dockerfile           # Docker image for backend
│   └── .env.example         # Environment template
├── frontend/
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # Reusable components
│   │   ├── contexts/        # React contexts
│   │   ├── services/        # API service
│   │   ├── styles/          # CSS files
│   │   ├── App.js           # Main app component
│   │   └── index.js         # Entry point
│   ├── public/
│   │   └── index.html       # HTML template
│   ├── package.json         # Node dependencies
│   ├── Dockerfile           # Docker image for frontend
│   └── .env.example         # Environment template
├── docker-compose.yml       # Docker Compose configuration
└── README.md               # This file
```

## Prerequisites

### Option 1: Local Development

- Python 3.9+
- Node.js 16+ and npm
- MongoDB 5.0+ (or use Docker)
- PyJHora fork: `pip install git+https://github.com/kunwarmahen/PyJHora.git`

### Option 2: Docker (Recommended)

- Docker 20.10+
- Docker Compose 2.0+

## Installation

### Option 1: Local Development Setup

#### Backend Setup

```bash
cd backend

# Copy environment file
cp .env.example .env

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install PyJHora from fork
pip install git+https://github.com/kunwarmahen/PyJHora.git

# Edit .env with your settings
# IMPORTANT: Change SECRET_KEY to something secure

# Run backend
uvicorn main:app --reload
```

Backend will be available at `http://localhost:8000`

#### Frontend Setup

```bash
cd frontend

# Copy environment file
cp .env.example .env

# Install dependencies
npm install

# Start development server
npm start
```

Frontend will be available at `http://localhost:3000`

#### MongoDB Setup

Start MongoDB locally or use Docker:

```bash
docker run -d \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=admin123 \
  mongo:7.0
```

### Option 2: Docker Compose (Recommended for Simplicity)

```bash
# Copy environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Build and start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# MongoDB: localhost:27017
```

To stop:
```bash
docker-compose down
```

## Configuration

### Backend (.env)

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=pyjhora_db

# Security (CHANGE IN PRODUCTION)
SECRET_KEY=your-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Qwen LLM Integration
QWEN_API_URL=http://localhost:5000
USE_QWEN=false  # Set to true if running local Qwen server

# CORS
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### Frontend (.env)

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_API_TIMEOUT=30000
```

## Quick Start Guide

### Getting Started with AI Astrologer

1. **Register/Login**: Create an account at http://localhost:3000
2. **Choose AI Model**: Set up at least one AI model (Qwen recommended for free local use)
3. **Navigate to "Ask AI Astrologer"** from the dashboard
4. **Enter Birth Details**: Date, time, and place of birth
5. **Ask Questions**: Use example questions or ask your own
6. **Get Insights**: Receive detailed, personalized astrological analysis

### Example Questions to Ask

- "What are my key strengths and weaknesses?"
- "Which career path is most suitable for me?"
- "When should I consider marriage?"
- "What do my planetary positions reveal about my personality?"
- "How can I overcome current challenges in my life?"
- "What remedies would be beneficial for me?"

## Features

### 1. Authentication
- User registration with username, email, password
- JWT-based login
- Secure token storage in localStorage
- Protected routes

### 2. Birth Chart Calculator
- Calculate Rasi chart from birth details
- Store charts in MongoDB
- Display planetary positions

### 3. Horoscope & Predictions
- General horoscope predictions
- Health predictions
- Career predictions
- Current transits (Gochara)
- Optional AI enhancement with Qwen

### 4. Marriage Compatibility
- Calculate compatibility scores
- Ashta Koota analysis
- Detailed compatibility breakdown
- Optional AI analysis with Qwen

### 5. Dhasa Periods
- Calculate planetary periods
- Support multiple Dhasa types:
  - Vimsottari (default)
  - Ashtottari
  - Yogini
  - Shodasottari

### 6. Qwen LLM Integration (Optional)
- Enhanced predictions with local Qwen model
- Contextual astrological interpretations
- Personalized analysis

## AI Models Setup (Optional but Recommended)

### Option 1: Qwen 2.5 via Ollama (Recommended - Free & Local)

Install and run Qwen 2.5 locally using Ollama:

```bash
# 1. Install Ollama
curl https://ollama.ai/install.sh | sh

# 2. Start Ollama service
ollama serve

# 3. Pull Qwen 2.5 model
ollama pull qwen2.5

# 4. Update backend/.env
QWEN_API_URL=http://localhost:11434

# 5. Restart backend
```

**Advantages**: Free, private, no API costs, runs offline

### Option 2: Google Gemini

Use Google's Gemini AI (requires API key):

```bash
# 1. Get API key from: https://aistudio.google.com/app/apikey

# 2. Add to backend/.env
GEMINI_API_KEY=your-gemini-api-key-here

# 3. Restart backend
```

**Advantages**: Cloud-based, no local resources needed, free tier available

### Option 3: OpenAI ChatGPT

Use ChatGPT for AI predictions (requires API key):

```bash
# 1. Get API key from: https://platform.openai.com/api-keys

# 2. Add to backend/.env
OPENAI_API_KEY=your-openai-api-key-here

# 3. Restart backend
```

**Advantages**: Very high quality responses, well-tested

### Switching Between AI Models

Users can select their preferred AI model directly in the frontend:
- Go to "Ask AI Astrologer" page
- Choose between Qwen, Gemini, or ChatGPT in the AI Model selector
- Each model will provide different perspectives on your chart

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/user/profile` - Get current user profile

### Astrology
- `POST /api/astrology/birth-chart` - Calculate birth chart
- `GET /api/astrology/birth-chart/{chart_id}` - Retrieve stored chart
- `POST /api/astrology/horoscope` - Get horoscope predictions
- `POST /api/astrology/doshas` - Calculate doshas
- `POST /api/astrology/yogas` - Get yogas
- `POST /api/astrology/dhasa` - Calculate Dhasa periods
- `POST /api/astrology/transit` - Get current transits
- `POST /api/astrology/compatibility` - Check marriage compatibility

### AI Q&A (New) 🆕
- `POST /api/astrology/ask` - Ask a question about birth chart with AI
- `POST /api/astrology/predict` - Generate AI-powered predictions (general, health, career, relationships)
- `POST /api/astrology/compatibility-analysis` - Get detailed AI compatibility analysis

### User
- `GET /api/user/charts` - Get user's saved charts

### Health
- `GET /health` - Health check endpoint

## Frontend Pages

- `/login` - Login page
- `/register` - Registration page
- `/dashboard` - Main dashboard with feature overview
- `/birth-chart` - Birth chart calculator
- `/ask-astrologer` - **NEW**: Interactive AI chat for personalized astrology insights 🆕
- `/compatibility` - Marriage compatibility checker
- `/dhasa` - Dhasa periods calculator
- `/predictions` - Horoscope and predictions generator

## Development Notes

### Backend Architecture

The backend uses a layered architecture:

- **main.py**: FastAPI routes and endpoints
- **config.py**: Configuration management
- **database.py**: MongoDB models and async connection
- **auth.py**: JWT and password utilities
- **astrology.py**: PyJHora wrapper functions
- **qwen_predictor.py**: LLM integration for enhanced predictions

### Frontend Architecture

The frontend uses React with:

- **React Router**: Navigation between pages
- **Context API**: Global authentication state
- **Axios**: HTTP client for API calls
- **Responsive CSS**: Mobile-friendly design
- **Protected Routes**: Authentication checks

### Important: PyJHora Installation

The PyJHora package needs to be installed from Mahen's fork:

```bash
pip install git+https://github.com/kunwarmahen/PyJHora.git
```

For Docker, this is already included in the backend requirements.

## Testing

### Manual API Testing

Use curl or Postman:

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"testpass"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}'

# Calculate birth chart (use token from login)
curl -X POST http://localhost:8000/api/astrology/birth-chart \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "name":"John Doe",
    "dob":"1990-01-15",
    "tob":"14:30:00",
    "place":"Chennai, India",
    "latitude":13.0827,
    "longitude":80.2707
  }'
```

## Production Deployment

### Before Going Live

1. **Change SECRET_KEY** in backend/.env to a secure random string
2. **Set CORS_ORIGINS** to your production domain
3. **Use production MongoDB**: Update MONGODB_URL
4. **Enable SSL/HTTPS**: Use reverse proxy (nginx, traefik)
5. **Set USE_QWEN to false** if not using local LLM
6. **Add environment variables** for production database credentials

### Docker Production Build

```bash
# Build production images
docker-compose -f docker-compose.yml build

# Push to registry and deploy
docker-compose up -d
```

### Using Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
    }
}
```

## Troubleshooting

### MongoDB Connection Issues

```bash
# Check if MongoDB is running
docker ps | grep mongodb

# View MongoDB logs
docker-compose logs mongodb
```

### Backend API Errors

```bash
# Check backend logs
docker-compose logs backend

# Ensure PyJHora is installed
pip list | grep PyJHora
```

### Frontend Not Loading

```bash
# Check if frontend is built
ls -la frontend/build/

# Check REACT_APP_API_URL configuration
cat frontend/.env
```

### Port Already in Use

```bash
# Change ports in docker-compose.yml or kill process
# On macOS/Linux:
lsof -i :3000  # Find process on port 3000
kill -9 <PID>

# On Windows:
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

## Future Enhancements

- [ ] Real-time chart visualization with SVG/Canvas
- [ ] Advanced prediction algorithms
- [ ] Multi-language support
- [ ] Mobile app with React Native
- [ ] Advanced Qwen integration for remedies
- [ ] Chart sharing and collaboration
- [ ] Subscription plans and analytics
- [ ] Integration with other astrology APIs

## Support and Contributing

For issues or contributions, please refer to the PyJHora fork:
https://github.com/kunwarmahen/PyJHora

## License

Check the PyJHora license for terms of use.
