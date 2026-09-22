import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FTool · Pontes",
  description: "Análise estrutural e dimensionamento de pontes de palitos.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="pt-BR"><body>{children}</body></html>;
}
