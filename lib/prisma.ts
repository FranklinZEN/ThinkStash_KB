import { PrismaClient } from '@prisma/client';

// Read individual environment variables
const dbUser = process.env.DB_USER;
const dbPassword = process.env.DB_PASSWORD;
const dbName = process.env.DB_NAME;
const dbHostPath = process.env.DB_HOST_PATH; // e.g., /cloudsql/project:region:instance

// Construct the DATABASE_URL
let databaseURL;
if (dbUser && dbPassword && dbName && dbHostPath) {
  databaseURL = `postgresql://${dbUser}:${dbPassword}@localhost/${dbName}?host=${dbHostPath}`;
} else {
  console.error("!!!!!!!!!!!!!!!!! Missing one or more database environment variables for constructing DATABASE_URL: DB_USER, DB_PASSWORD, DB_NAME, DB_HOST_PATH. Check Cloud Run secret configuration.");
  // Set to a value that will cause Prisma to fail clearly if construction fails, as schema expects env("DATABASE_URL")
  databaseURL = "prisma_url_construction_failed_due_to_missing_parts";
}

console.log("!!!!!!!!!!!!!!!!! Constructed DATABASE_URL for Prisma:", databaseURL);

// Set the constructed URL as an environment variable for Prisma to pick up,
// as schema.prisma likely uses `url = env("DATABASE_URL")`
process.env.DATABASE_URL = databaseURL;

declare global {
  // allow global `var` declarations
  // eslint-disable-next-line no-var
  var prisma: PrismaClient | undefined;
}

const prisma =
  global.prisma ||
  new PrismaClient({
    // Datasource override can be done here if not relying on process.env.DATABASE_URL set above
    // datasources: {
    //   db: {
    //     url: databaseURL,
    //   },
    // },
  });

if (process.env.NODE_ENV !== 'production') {
  global.prisma = prisma;
}

export default prisma; 