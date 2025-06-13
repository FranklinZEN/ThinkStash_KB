# Knowledge Cards App

A dynamic personal knowledge base application built with Next.js and Chakra UI.

## Prerequisites

- Node.js (Version specified in `.nvmrc` - use `nvm use` if you have Node Version Manager)
- npm (comes with Node.js)
- Docker Desktop (required for the local PostgreSQL database)

## Local Development Setup

This section provides the official, step-by-step instructions for running the complete ThinkStash application stack (Webapp, AI Worker, Database) on your local machine. This is the required setup for all development and debugging.

### 1. Environment Variable Setup

You will need to create two environment files. **These files should not be committed to git.**

A. **Webapp Environment (`.env.local`):**
   - In the project root directory, create a file named `.env.local`.
   - Add the following content:
     ```
     DATABASE_URL="postgresql://user:password@localhost:5433/knowledge_cards?sslmode=disable"
     NEXTAUTH_SECRET="a-secret-for-local-development"
     ```

B. **AI Worker Environment (`aiservice/.env.worker`):**
   - In the `aiservice/` directory, create a file named `.env.worker`.
   - This file must contain all the environment variables the worker needs to run. You will need to get your own `GEMINI_API_KEY`.
     ```
     # In aiservice/.env.worker
     DATABASE_URL="postgresql://user:password@localhost:5433/knowledge_cards?sslmode=disable"
     GEMINI_API_KEY="your-google-ai-api-key"
     GCS_BUCKET_NAME="your-gcs-bucket-name"
     PYTHONUNBUFFERED=1
     PYTHONDONTWRITEBYTECODE=1
     # ... (copy all other variables from the Phoenix Plan or cloudbuild.yaml) ...
     ```

### 2. Running the Application

Follow these steps in order.

1.  **Start the Local Database:**
    - Open a terminal in the project root.
    - Run the following command to start the PostgreSQL database in a Docker container.
      ```bash
      docker-compose up -d postgres
      ```

2.  **Set Up the Database Schema:**
    - This command applies any pending migrations to the local database, creating the necessary tables.
      ```bash
      npx prisma migrate dev
      ```

3.  **Start the Webapp:**
    - In a new terminal, run the Next.js development server.
      ```bash
      npm run dev
      ```
    - The web application will be available at `http://localhost:3000`.

4.  **Start the AI Worker:**
    - In another new terminal, run the worker startup script.
      ```bash
      sh aiservice/run_local_worker.sh
      ```
    - This will start the Python worker, which will listen for and process background tasks.

## Tech Stack

- Next.js (React Framework)
- TypeScript
- PostgreSQL (Database)
- Prisma (ORM)
- Chakra UI (Component Library)
- NextAuth.js (Authentication)
- Zustand (State Management)
- BlockNote (Rich Text Editor)
- React Flow (Node-based UI)
- ESLint / Prettier / Husky / lint-staged (Code Quality)

## Features

- **User Authentication:** Uses NextAuth.js for user sign-up and sign-in.
- **Knowledge Card Management (CRUD):**
    - Create new knowledge cards with a title and rich text content.
    - View existing cards.
    - Edit card titles and content.
    - Delete cards (with confirmation).
- **Rich Text Editing:** Utilizes the BlockNote editor (`@blocknote/react` + `@blocknote/mantine`) for card content, allowing for various formatting options.
- **Folder Management:** (Future Feature - Placeholder)
- **Card Linking / Graph View:** (Future Feature - Uses React Flow)
- Image Upload

## Testing

- Core Card CRUD operations (Create, Read, Update, Delete) involving the BlockNote editor integration have been interactively tested and confirmed to be working (as of the last debugging session).
- Unit and integration tests are set up using Jest (see `jest.config.*.js`).

## Links

* (Placeholder for links to PRD, TDD, ADRs, etc.)

## Contributing

- (Placeholder for contribution guidelines - see `CONTRIBUTING.md` if it exists)

<!-- Build trigger comment: 2024-05-15T12:00:00Z --> 