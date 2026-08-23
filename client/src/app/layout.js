import { Inter, JetBrains_Mono } from "next/font/google";
import { ToastProvider } from "@/components/ui/toaster";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: {
    default: "LedgerLens — Financial reconciliation without the manual investigation",
    template: "%s · LedgerLens",
  },
  description:
    "LedgerLens automatically reconciles financial records and uses AI to investigate the exceptions that matter.",
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
