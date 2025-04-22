# Knowledge Card System - Setup Guide

This guide will help you set up the Knowledge Card System development environment.

## Prerequisites

- Node.js (v18.x or later)
- PostgreSQL (v14.x or later)
- Git
- Docker (optional, for containerized development)
- pnpm (recommended package manager)

## Environment Setup

1. **Clone the Repository**
   ```bash
   git clone [repository-url]
   cd knowledge-card-system
   ```

2. **Install Dependencies**
   ```bash
   pnpm install
   ```

3. **Environment Variables**
   Create a `.env` file in the root directory with the following variables:
   ```env
   # Database
   DATABASE_URL=postgresql://user:password@localhost:5432/knowledge_card
   
   # Authentication
   JWT_SECRET=your-secret-key
   JWT_EXPIRES_IN=7d
   
   # Server
   PORT=3000
   NODE_ENV=development
   ```

4. **Database Setup**
   ```bash
   # Create database
   createdb knowledge_card
   
   # Run migrations
   pnpm prisma migrate dev
   ```

5. **Start Development Servers**
   ```bash
   # Start backend server
   pnpm dev:server
   
   # Start frontend development server
   pnpm dev:client
   ```

## Development Tools

- **VS Code Extensions**
  - ESLint
  - Prettier
  - Prisma
  - TypeScript Vue Plugin
  - Volar

- **Browser Extensions**
  - Vue.js devtools
  - Redux DevTools

## Common Issues and Solutions

1. **Database Connection Issues**
   - Ensure PostgreSQL is running
   - Verify database credentials in `.env`
   - Check if the database exists

2. **Dependency Issues**
   - Clear pnpm cache: `pnpm store prune`
   - Delete node_modules and reinstall
   - Check for version conflicts

3. **Environment Variables**
   - Ensure all required variables are set
   - Check for typos in variable names
   - Verify values are properly formatted

## Testing Setup

1. **Unit Tests**
   ```bash
   pnpm test
   ```

2. **Integration Tests**
   ```bash
   pnpm test:integration
   ```

3. **Coverage**
   ```bash
   pnpm test:coverage
   ```

## Production Setup

1. **Build**
   ```bash
   pnpm build
   ```

2. **Start Production Server**
   ```bash
   pnpm start
   ```

## Docker Setup (Optional)

1. **Build Containers**
   ```bash
   docker-compose build
   ```

2. **Start Services**
   ```bash
   docker-compose up
   ```

## Additional Resources

- [Project Documentation](docs/)
- [API Documentation](docs/api.md)
- [Testing Guide](docs/testing.md)
- [Deployment Guide](docs/deployment.md)

## Getting Help

If you encounter any issues during setup:
1. Check the documentation
2. Search existing issues
3. Contact the development team 