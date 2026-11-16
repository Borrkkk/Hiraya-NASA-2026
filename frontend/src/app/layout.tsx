import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Instrument_Sans } from "next/font/google";
import { Suspense } from "react";
import { Providers } from "@/components/providers";
import { GuidedTour } from "@/components/tour/guided-tour";
import "./globals.css";
import "./themes.css";

// Instrument Sans for everything people read; IBM Plex Mono for anything measured.
const instrumentSans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Hiraya",
  description:
    "Browse SPHEREx's infrared sky, understand what you see, and share real finds.",
};

export const viewport: Viewport = {
  themeColor: "#0e1013",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${instrumentSans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: `try{document.documentElement.dataset.theme=localStorage.getItem("pulsr:theme")==="light"?"light":"dark"}catch{document.documentElement.dataset.theme="dark"}` }} />
      </head>
      <body className="min-h-full flex flex-col">
        <Providers>
          {children}
          <Suspense>
            <GuidedTour />
          </Suspense>
        </Providers>
      </body>
    </html>
  );
}
