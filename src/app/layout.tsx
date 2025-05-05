import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css"; // Assuming globals.css exists or will be created
import '@mantine/core/styles.css';
import "@blocknote/mantine/style.css"; // Import BlockNote Mantine styles
import { Providers } from './providers'; // Import the Chakra UI provider
import Layout from '@/components/layout/Layout'; // Import the new Layout component

const inter = Inter({ subsets: ["latin"], variable: '--font-inter' }); // Added variable for theme

export const metadata: Metadata = {
  title: "Knowledge Cards App",
  description: "Dynamic Personal Knowledge Base",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className} suppressHydrationWarning>
        <Providers>
          <Layout> {/* Wrap children with the Layout component */} 
            {children}
          </Layout>
        </Providers>
      </body>
    </html>
  );
} 