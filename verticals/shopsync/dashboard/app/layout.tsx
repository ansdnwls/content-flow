import type { Metadata } from "next";
import config from "../../config.json";
import { Sidebar } from "../components/sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: `${config.name} Dashboard`,
  description: `${config.name} management dashboard`,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { colors } = config.brand;

  return (
    <html lang={config.target.language[0] ?? "en"}>
      <head>
        <style
          dangerouslySetInnerHTML={{
            __html: `
              :root {
                --color-primary: ${colors.primary};
                --color-secondary: ${colors.secondary};
                --color-accent: ${colors.accent};
                --color-bg: ${colors.bg};
                --color-text: ${colors.text};
              }
            `,
          }}
        />
      </head>
      <body className="antialiased">
        <div className="flex h-screen">
          <Sidebar />
          <main className="flex-1 overflow-y-auto p-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
