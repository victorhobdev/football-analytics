import "@/app/globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter, Manrope } from "next/font/google";

const appBodyFont = Inter({
  subsets: ["latin"],
  variable: "--font-app-body",
  weight: ["400", "500", "600", "700"],
});

const appHeadlineFont = Manrope({
  subsets: ["latin"],
  variable: "--font-app-headline",
  weight: ["700", "800"],
});

export const metadata: Metadata = {
  title: "Football Analytics",
  description: "Historical football analytics platform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block" rel="stylesheet" />
      </head>
      <body className={`${appBodyFont.variable} ${appHeadlineFont.variable}`}>{children}</body>
    </html>
  );
}
