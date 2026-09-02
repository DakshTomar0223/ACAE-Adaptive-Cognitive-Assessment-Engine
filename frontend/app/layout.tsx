import type { Metadata } from "next";
import { Fraunces, Inter, IBM_Plex_Mono } from "next/font/google";
import Header from "./components/Header";
import { themeInitScript } from "./components/ThemeToggle";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["300", "500", "600"],
  variable: "--font-fraunces",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ACAE — Adaptive Cognitive Assessment Engine",
  description:
    "A JEE/NEET practice quiz that diagnoses why an answer went wrong, not just whether it did — then targets practice at the specific reasoning gap.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // suppressHydrationWarning: the inline script below sets data-theme
    // on this element before React hydrates, on purpose — without this,
    // React would flag the server/client mismatch as an error.
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Blocking (non-async) so it runs before first paint — this is
            what prevents a flash of the wrong theme on load. Reads the
            saved choice from localStorage, falling back to the OS
            preference the very first time the app is opened. */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className={`${fraunces.variable} ${inter.variable} ${plexMono.variable}`}>
        <Header />
        <main>{children}</main>
      </body>
    </html>
  );
}