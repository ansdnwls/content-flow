import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

import { marketingPlatforms } from "@/lib/marketing";

export const runtime = "nodejs";
export const alt = "ContentFlow Open Graph Image";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

function getPlatformColor(platform?: string) {
  const match = marketingPlatforms.find((item) => item.id === platform);
  return match?.color ?? "#06ffa5";
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const title = searchParams.get("title") ?? "One topic. 21 platforms. Zero clicks.";
  const subtitle = searchParams.get("subtitle") ?? "The API for creators who ship";
  const platform = searchParams.get("platform") ?? "youtube";
  const color = getPlatformColor(platform);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          position: "relative",
          overflow: "hidden",
          background:
            "radial-gradient(circle at 18% 22%, rgba(255,107,53,0.24), transparent 26%), radial-gradient(circle at 82% 18%, rgba(255,210,63,0.2), transparent 22%), radial-gradient(circle at 70% 84%, rgba(6,255,165,0.18), transparent 26%), linear-gradient(180deg, #120A14 0%, #1B101A 100%)",
          color: "#fff6ef",
          fontFamily: "Arial",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
            maskImage: "radial-gradient(circle at center, black 44%, transparent 90%)",
            opacity: 0.35,
          }}
        />

        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "52px 56px", width: "100%" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 18,
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  background: "linear-gradient(135deg, #FF6B35 0%, #FFD23F 60%, #06FFA5 100%)",
                  color: "#20110b",
                  fontSize: 24,
                  fontWeight: 800,
                }}
              >
                CF
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 30, fontWeight: 800 }}>ContentFlow</span>
                <span style={{ fontSize: 16, textTransform: "uppercase", letterSpacing: "0.16em", color: "#d3c1b6" }}>
                  The API for creators who ship
                </span>
              </div>
            </div>
            <div
              style={{
                display: "flex",
                minWidth: 120,
                height: 42,
                justifyContent: "center",
                alignItems: "center",
                borderRadius: 999,
                border: "1px solid rgba(255,173,129,0.4)",
                color,
                fontSize: 18,
                fontWeight: 700,
              }}
            >
              {platform}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", maxWidth: 860 }}>
            <div style={{ display: "flex", marginBottom: 18, fontSize: 18, textTransform: "uppercase", letterSpacing: "0.18em", color: "#ffd23f" }}>
              1 API. 21 Platforms.
            </div>
            <div style={{ display: "flex", fontSize: 76, lineHeight: 0.96, fontWeight: 900, letterSpacing: "-0.06em" }}>{title}</div>
            <div style={{ display: "flex", marginTop: 20, fontSize: 30, lineHeight: 1.3, color: "#d3c1b6" }}>{subtitle}</div>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
            <div style={{ display: "flex", gap: 14 }}>
              {marketingPlatforms.slice(0, 8).map((item) => (
                <div
                  key={item.id}
                  style={{
                    width: 68,
                    height: 68,
                    borderRadius: 22,
                    border: "1px solid rgba(255,173,129,0.36)",
                    background: "rgba(31,18,27,0.82)",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    color: item.color,
                    fontSize: 24,
                    fontWeight: 800,
                  }}
                >
                  {item.short}
                </div>
              ))}
            </div>
            <div style={{ display: "flex", fontSize: 20, color: "#fff6ef" }}>contentflow.dev</div>
          </div>
        </div>
      </div>
    ),
    size
  );
}
