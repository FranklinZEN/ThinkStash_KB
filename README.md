# Knowledge Cards App

A dynamic personal knowledge base application built with Next.js and Chakra UI.

## Prerequisites

- Node.js (Version specified in `.nvmrc` - use `nvm use` if you have Node Version Manager)
- npm (comes with Node.js)
- Docker Desktop (required for the local PostgreSQL database)

## Getting Started

Follow these steps to get the development environment running:

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd knowledge-card-system
    ```

2.  **Set Node.js version (if using NVM):**
    ```bash
    nvm use
    ```

3.  **Install dependencies:**
    ```bash
    npm install
    ```

4.  **Set up environment variables:**
    - Copy the example environment file:
      ```bash
      cp .env.example .env
      ```
    - Open the `.env` file and fill in the required variables:
      - `DATABASE_URL`: Should match the Docker setup (e.g., `postgresql://user:password@localhost:5433/knowledge_cards?schema=public`)
      - `NEXTAUTH_SECRET`: Generate a secure secret (e.g., using `openssl rand -base64 32`) 
        *(Note: Need to run `openssl rand -base64 32` or similar and add to .env)*

5.  **Start the local database:**
    ```bash
    docker compose up -d
    ```

6.  **Run database migrations:**
    ```bash
    npx prisma migrate dev
    ```

7.  **Run the development server:**
    ```bash
    npm run dev
    ```

    Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

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

## Testing

- Core Card CRUD operations (Create, Read, Update, Delete) involving the BlockNote editor integration have been interactively tested and confirmed to be working (as of the last debugging session).
- Unit and integration tests are set up using Jest (see `jest.config.*.js`).

## Links

- (Placeholder for links to PRD, TDD, ADRs, etc.)

## Contributing

- (Placeholder for contribution guidelines - see `CONTRIBUTING.md` if it exists) 