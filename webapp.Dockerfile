# webapp.Dockerfile
# Use the official Node.js 20 image.
FROM node:20-slim

# Install wget to download the Cloud SQL Proxy.
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy dependency definitions
COPY package*.json ./

# Copy prisma schema
COPY prisma ./prisma

# Copy Next.js configuration
COPY next.config.mjs .
COPY postcss.config.js .
COPY tailwind.config.ts .
COPY tsconfig.json .

# Copy application source
COPY public ./public
COPY src ./src

# The `npm install` and `npm run build` steps are handled by Cloud Build.
# The results of those steps (node_modules, .next, public) are in the build context.
COPY .next ./.next
COPY node_modules ./node_modules

# The port the application will run on
EXPOSE 3000

# The command to start the application
CMD ["npm", "start"] 