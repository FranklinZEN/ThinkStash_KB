console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - START !!!!!!!!!!!!!!!!!!");
console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - DB_USER:", process.env.DB_USER);
console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - DB_PASSWORD:", process.env.DB_PASSWORD ? "Exists" : "MISSING or empty");
console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - DB_NAME:", process.env.DB_NAME);
console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - DB_HOST_PATH:", process.env.DB_HOST_PATH);
console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - NEXTAUTH_SECRET:", process.env.NEXTAUTH_SECRET ? "Exists" : "MISSING or empty");
console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - DATABASE_URL (initial):", process.env.DATABASE_URL);
console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - NODE_ENV:", process.env.NODE_ENV);
console.log("!!!!!!!!!!!!!!!!! NEXT.CONFIG.JS - END !!!!!!!!!!!!!!!!!!");

/** @type {import('next').NextConfig} */
const nextConfig = {
  // reactStrictMode: true, // Example: your existing config might be here
  // swcMinify: true,
  // images: {
  //   domains: ['example.com'],
  // },
};

module.exports = nextConfig; 