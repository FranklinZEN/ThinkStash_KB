# Knowledge Card System - Deployment Guide

This document outlines the deployment procedures for the Knowledge Card System.

## Deployment Environments

### 1. Development
- **Purpose**: Local development and testing
- **URL**: http://localhost:3000
- **Database**: Local PostgreSQL
- **Features**: Hot reloading, debug tools

### 2. Staging
- **Purpose**: Pre-production testing
- **URL**: https://staging.knowledge-card.com
- **Database**: Staging PostgreSQL
- **Features**: Production-like environment

### 3. Production
- **Purpose**: Live system
- **URL**: https://knowledge-card.com
- **Database**: Production PostgreSQL
- **Features**: Optimized for performance

## Prerequisites

### Infrastructure
- Node.js v18.x
- PostgreSQL v14.x
- Redis (for caching)
- Nginx (for reverse proxy)
- Docker (optional)

### Environment Variables
```env
# Database
DATABASE_URL=postgresql://user:password@host:5432/database

# Authentication
JWT_SECRET=your-secret-key
JWT_EXPIRES_IN=7d

# Server
PORT=3000
NODE_ENV=production

# Redis
REDIS_URL=redis://host:6379

# Email
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user
SMTP_PASS=password

# Storage
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1
S3_BUCKET=your-bucket
```

## Deployment Process

### 1. Database Setup
```bash
# Create database
createdb knowledge_card

# Run migrations
pnpm prisma migrate deploy

# Seed data (if needed)
pnpm prisma db seed
```

### 2. Build Application
```bash
# Install dependencies
pnpm install

# Build frontend
pnpm build:client

# Build backend
pnpm build:server
```

### 3. Configure Nginx
```nginx
server {
    listen 80;
    server_name knowledge-card.com;

    # Frontend
    location / {
        root /var/www/knowledge-card/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # SSL Configuration
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/knowledge-card.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/knowledge-card.com/privkey.pem;
}
```

### 4. Start Application
```bash
# Start backend server
pnpm start:server

# Start frontend server (if needed)
pnpm start:client
```

## Docker Deployment

### 1. Build Images
```bash
# Build frontend
docker build -t knowledge-card-frontend -f Dockerfile.frontend .

# Build backend
docker build -t knowledge-card-backend -f Dockerfile.backend .
```

### 2. Docker Compose
```yaml
version: '3.8'
services:
  frontend:
    image: knowledge-card-frontend
    ports:
      - "80:80"
    depends_on:
      - backend

  backend:
    image: knowledge-card-backend
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/knowledge_card
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis

  db:
    image: postgres:14
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=knowledge_card
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### 3. Deploy with Docker
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

## CI/CD Pipeline

### GitHub Actions Workflow
```yaml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: pnpm install
      
      - name: Run tests
        run: pnpm test
      
      - name: Build
        run: pnpm build
      
      - name: Deploy to production
        run: |
          ssh user@server 'cd /var/www/knowledge-card && git pull && pnpm install && pnpm build && pm2 restart all'
```

## Monitoring and Maintenance

### 1. Logging
```bash
# View application logs
pm2 logs knowledge-card

# View Nginx logs
tail -f /var/log/nginx/access.log
```

### 2. Backup
```bash
# Database backup
pg_dump -U user -d knowledge_card > backup.sql

# Restore database
psql -U user -d knowledge_card < backup.sql
```

### 3. Monitoring
- Use PM2 for process management
- Set up monitoring with New Relic or similar
- Configure alerts for critical issues

## Rollback Procedure

### 1. Database Rollback
```bash
# Revert last migration
pnpm prisma migrate reset

# Restore from backup
psql -U user -d knowledge_card < backup.sql
```

### 2. Application Rollback
```bash
# Revert to previous version
git checkout <previous-commit>
pnpm install
pnpm build
pm2 restart all
```

## Security Considerations

### 1. SSL/TLS
- Use Let's Encrypt for SSL certificates
- Configure HSTS
- Enable secure cookies

### 2. Firewall
```bash
# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Allow SSH
ufw allow 22/tcp
```

### 3. Updates
- Regular security updates
- Dependency updates
- OS updates

## Troubleshooting

### Common Issues
1. Database connection issues
2. Memory leaks
3. Performance problems
4. SSL certificate issues

### Debugging
```bash
# Check application status
pm2 status

# View detailed logs
pm2 logs --lines 100

# Monitor resources
htop
```

## Resources

- [PM2 Documentation](https://pm2.keymetrics.io/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Documentation](https://docs.docker.com/) 