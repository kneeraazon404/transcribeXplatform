import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import "./globals.css";

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const metadataBase = new URL(siteUrl);

export const metadata: Metadata = {
  metadataBase,
  title: "Transcribe — Audio & Video to Text",
  description:
    "Transcribe audio and video files into speaker-labelled Markdown with local desktop, web, and CLI workflows.",
  applicationName: "Transcribe",
  keywords: [
    "audio transcription",
    "video transcription",
    "speech to text",
    "speaker diarization",
    "markdown transcript",
    "desktop transcription app",
  ],
  alternates: {
    canonical: "/",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  openGraph: {
    title: "Transcribe — Audio & Video to Text",
    description:
      "Convert audio and video into clean Markdown transcripts with speaker labels.",
    url: "/",
    siteName: "Transcribe",
    type: "website",
    images: [
      {
        url: "/logo.svg",
        width: 900,
        height: 300,
        alt: "Transcribe logo",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Transcribe — Audio & Video to Text",
    description:
      "Convert audio and video into clean Markdown transcripts with speaker labels.",
    images: ["/logo.svg"],
  },
  icons: {
    icon: "/logo.svg",
    shortcut: "/logo.svg",
    apple: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${jetbrainsMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
