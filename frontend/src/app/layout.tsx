/**
 * @file layout.tsx
 * @purpose Root layout configuring Geist fonts, metadata, and global stylesheets.
 * @stage Frontend Stage 2 (Spatial Pro Product UI + Property Workspace)
 * @inputs React children nodes.
 * @outputs HTML shell with font CSS variables applied.
 * @dependencies next/font/google, ../styles/globals.css
 * @assumptions Standard Next.js App Router root layout.
 * @failureModes Font network failure falls back to system fonts gracefully.
 * @firstDebuggingPoints Check font CSS variable injection in <body> classList.
 */

import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import '../styles/globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
  display: 'swap',
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'COZMO — Spatial Intelligence Workspace',
  description:
    'Spatial analysis and deterministic architectural intelligence platform.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
