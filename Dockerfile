# Dockerfile for Next.js application (Optimized for Standalone Output)

# Stage 1: Install dependencies
FROM node:18-alpine AS deps
WORKDIR /app

# Install pnpm if you use it, otherwise adjust for npm/yarn
# RUN npm install -g pnpm

COPY package.json package-lock.json* pnpm-lock.yaml* ./ 
# If using pnpm: RUN pnpm install --frozen-lockfile
# If using npm: 
RUN npm ci

# Stage 2: Build the application
FROM node:18-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Ensure your next.config.js has output: 'standalone'
# ENV NEXT_TELEMETRY_DISABLED 1 # Optional: Disable Next.js telemetry

# Generate Prisma client if you use Prisma
# RUN npx prisma generate 
# Or (if in package.json scripts): npm run prisma:generate

RUN npm run build

# Stage 3: Production Runner
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV production
# ENV NEXT_TELEMETRY_DISABLED 1 # Optional: Disable Next.js telemetry

# Create a non-root user 'nextjs' and group 'nodejs'
# RUN addgroup --system --gid 1001 nodejs
# RUN adduser --system --uid 1001 nextjs
# USER nextjs 
# The above user creation might vary based on base image. 
# Alpine's 'node' user (ID 1000) is often used by default if USER not specified.

# Copy standalone output
COPY --from=builder /app/public ./public
COPY --from=builder --chown=node:node /app/.next/standalone ./ 
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder /app/prisma ./prisma

# If you have a custom server.js for standalone mode, ensure it's copied and used in CMD
# COPY --from=builder /app/server.js ./server.js

EXPOSE 3000
ENV PORT 3000

# For Next.js 12.2.0+ with outputStandalone, server.js is in .next/standalone/
CMD ["node", "server.js"] 