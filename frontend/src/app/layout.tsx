import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ResearchOS — Evidence first research",
  description: "A focused workspace for research projects, documents, evidence, and reports.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return <html lang="en"><body>{children}</body></html>;
}
