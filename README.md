# RAG Chatbot - Customer Support Assistant

A Retrieval-Augmented Generation (RAG) chatbot built with Django backend and React frontend, designed to answer customer support queries based on AngelOne support documentation and insurance PDFs.

## 🚀 Features

- **Context-Aware Responses**: Answers questions only based on provided source documents
- **Fallback Handling**: Returns "I Don't know" for queries outside the knowledge base
- **Modern UI**: Clean, responsive React frontend
- **RESTful API**: Django backend with comprehensive API endpoints
- **Document Processing**: Supports PDF and web content ingestion
- **Dockerized**: Easy deployment with Docker Compose

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  Django Backend │
│   (Port 80)     │◄───┤   (Internal)    │
└─────────────────┘    └─────────────────┘
                              │
                        ┌─────────────┐
                        │  SQLite DB  │
                        │  Vector DB  │
                        └─────────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose
- Git
- Node.js 18+ (for local development)
- Python 3.9+ (for local development)

## 🛠️ Installation & Setup

### Local Development with Docker

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/rag-chatbot.git
   cd rag-chatbot
   ```

2. **Build and run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

3. **Access the application**
   - Frontend: http://localhost:80
   - Backend API: http://localhost:8000 (if exposed)

### Local Development (Without Docker)

1. **Backend Setup**
   ```bash
   cd backend
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py collectstatic
   python manage.py runserver
   ```

2. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   npm start
   ```

## 🚀 Deployment to Railway

### Prerequisites
- Railway account (https://railway.app)
- GitHub account

### Step 1: Prepare for Railway Deployment

1. **Create railway.json in project root**
   ```json
   {
     "$schema": "https://railway.app/railway.schema.json",
     "build": {
       "builder": "DOCKERFILE",
       "dockerfilePath": "./Dockerfile"
     },
     "deploy": {
       "startCommand": "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT",
       "healthcheckPath": "/health/",
       "healthcheckTimeout": 100,
       "restartPolicyType": "ON_FAILURE",
       "restartPolicyMaxRetries": 10
     }
   }
   ```

2. **Create Dockerfile for Railway (root directory)**
   ```dockerfile
   # Multi-stage build for Railway deployment
   FROM node:18-alpine AS frontend-builder
   WORKDIR /app/frontend
   COPY frontend/package*.json ./
   RUN npm ci --only=production
   COPY frontend/ ./
   RUN npm run build

   FROM python:3.9-slim
   WORKDIR /app

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       gcc \
       && rm -rf /var/lib/apt/lists/*

   # Install Python dependencies
   COPY backend/requirements.txt ./
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy backend code
   COPY backend/ ./

   # Copy built frontend
   COPY --from=frontend-builder /app/frontend/build ./staticfiles/

   # Collect static files
   RUN python manage.py collectstatic --noinput

   EXPOSE $PORT

   CMD python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```

3. **Update Django settings for Railway**
   ```python
   # In backend/config/settings.py
   import os
   from pathlib import Path

   # Railway specific settings
   if 'RAILWAY_ENVIRONMENT' in os.environ:
       DEBUG = False
       ALLOWED_HOSTS = ['*']
       
       # Database for Railway (PostgreSQL)
       DATABASES = {
           'default': {
               'ENGINE': 'django.db.backends.postgresql',
               'NAME': os.environ.get('PGDATABASE'),
               'USER': os.environ.get('PGUSER'),
               'PASSWORD': os.environ.get('PGPASSWORD'),
               'HOST': os.environ.get('PGHOST'),
               'PORT': os.environ.get('PGPORT', 5432),
           }
       }
   ```

### Step 2: Deploy to Railway

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Prepare for Railway deployment"
   git push origin main
   ```

2. **Deploy on Railway**
   - Go to https://railway.app
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your repository
   - Railway will automatically detect and deploy your app

3. **Add Environment Variables** (in Railway dashboard)
   ```
   RAILWAY_ENVIRONMENT=production
   DEBUG=False
   DJANGO_SECRET_KEY=your-secret-key-here
   ```

## 📚 API Documentation

### Endpoints

- `POST /api/chat/` - Send message to chatbot
- `GET /api/health/` - Health check endpoint
- `GET /api/documents/` - List indexed documents

### Request/Response Examples

**Chat Request:**
```json
{
  "message": "How do I open a trading account?"
}
```

**Chat Response:**
```json
{
  "response": "To open a trading account with AngelOne...",
  "sources": ["support/account-opening.html"],
  "confidence": 0.85
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DEBUG` | Django debug mode | `True` |
| `ALLOWED_HOSTS` | Allowed hosts | `localhost,127.0.0.1` |
| `CORS_ALLOWED_ORIGINS` | CORS origins | `http://localhost:3000` |
| `DATABASE_URL` | Database connection string | SQLite |

### Docker Compose Configuration

The application uses multi-service architecture:
- **Backend**: Django API server
- **Frontend**: React application served via Nginx
- **Volumes**: Persistent storage for database and media files

## 🧪 Testing

### Run Tests
```bash
# Backend tests
cd backend
python manage.py test

# Frontend tests
cd frontend
npm test
```

### Manual Testing
1. Access the chatbot interface
2. Ask questions related to AngelOne support
3. Verify responses are contextually accurate
4. Test edge cases with unrelated queries

## 🔍 Troubleshooting

### Common Issues

1. **Docker build fails**
   - Check Docker and Docker Compose versions
   - Ensure all files are properly copied to build context

2. **Frontend not loading**
   - Verify CORS settings in backend
   - Check network connectivity between services

3. **Database connection errors**
   - Ensure volume mounting is correct
   - Check database migrations

### Logs
```bash
# View application logs
docker-compose logs -f

# View specific service logs
docker-compose logs backend
docker-compose logs frontend
```

## 📖 Data Sources

The chatbot is trained on:
- AngelOne support documentation (https://www.angelone.in/support)
- Insurance PDF documents
- Customer support knowledge base

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Create an issue in the GitHub repository
- Contact: [your-email@domain.com]

## 🔄 Updates & Maintenance

### Adding New Documents
1. Place documents in the appropriate directory
2. Run the document ingestion script
3. Restart the application

### Updating Dependencies
```bash
# Backend
pip freeze > backend/requirements.txt

# Frontend
cd frontend && npm audit fix
```

---

**Built with ❤️ using Django, React, and Docker**
