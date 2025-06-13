# webapp.Dockerfile

# ---- Base Stage ----
# Use the official Node.js 20 image for a consistent environment.
FROM node:20-slim as base
WORKDIR /app

# ---- Dependencies Stage ----
# This stage is for installing npm dependencies.
FROM base as deps
WORKDIR /app
COPY package*.json ./
RUN npm install

# ---- Builder Stage ----
# This stage is for building the Next.js application.
FROM base as builder
WORKDIR /app
# Copy dependencies from the 'deps' stage
COPY --from=deps /app/node_modules ./node_modules
# Copy all other necessary source files
COPY . .
# Run the build command
RUN npm run build

# ---- Runner Stage ----
# This is the final, minimal image for production.
FROM base as runner
WORKDIR /app

# Install wget and ca-certificates.
# wget is required by the migration step in cloudbuild.yaml to download the Cloud SQL Proxy.
# ca-certificates is required to validate the SSL certificate of storage.googleapis.com.
RUN apt-get update && apt-get install -y --no-install-recommends wget ca-certificates && rm -rf /var/lib/apt/lists/*

ENV NODE_ENV=production

# Copy the built application from the 'builder' stage
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# The port the application will run on
EXPOSE 3000

# The command to start the application
# Using the standalone output mode server.js
CMD ["node", "server.js"] 