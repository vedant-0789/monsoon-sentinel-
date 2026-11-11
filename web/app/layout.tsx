import type { Metadata, Viewport } from "next";
import { Geist, Noto_Sans_Devanagari } from "next/font/google";
import TopBar from "@/components/TopBar";
import { SentinelProvider } from "@/lib/store";
import "./globals.css";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const deva = Noto_Sans_Devanagari({ variable: "--font-deva", subsets: ["devanagari"], weight: ["400", "600", "700"] });

export const metadata: Metadata = {
  title: "Monsoon Sentinel — Pune rain & waterlogging alerts",
  description: "Explainable, street-level heavy-rain and waterlogging early warnings for Pune.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#09090b" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geist.variable} ${deva.variable} h-full antialiased`}>
      <body className="flex h-full flex-col">
        <SentinelProvider>
          <TopBar />
          <main className="min-h-0 flex-1">{children}</main>
        </SentinelProvider>
      </body>
    </html>
  );
}
