import {
  intro,
  outro,
  text,
  multiselect,
  select,
  isCancel,
  cancel,
} from "@clack/prompts";
import { readFileSync, writeFileSync, cpSync, existsSync } from "fs";
import path from "path";

const PLATFORMS = [
  { value: "youtube", label: "YouTube" },
  { value: "tiktok", label: "TikTok" },
  { value: "instagram", label: "Instagram" },
  { value: "x", label: "X (Twitter)" },
  { value: "threads", label: "Threads" },
  { value: "facebook", label: "Facebook" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "medium", label: "Medium" },
  { value: "naver_blog", label: "Naver Blog" },
  { value: "tistory", label: "Tistory" },
  { value: "kakao", label: "Kakao" },
  { value: "mastodon", label: "Mastodon" },
  { value: "line", label: "LINE" },
] as const;

function exitIfCancelled<T>(value: T | symbol): T {
  if (isCancel(value)) {
    cancel("Operation cancelled.");
    process.exit(0);
  }
  return value as T;
}

async function main() {
  const rootDir = path.resolve(__dirname, "../../..");
  const templateDir = path.join(rootDir, "verticals/_template");

  if (!existsSync(templateDir)) {
    console.error("Template directory not found:", templateDir);
    process.exit(1);
  }

  intro("Create a new ContentFlow vertical");

  const id = exitIfCancelled(
    await text({
      message: "Vertical ID (lowercase, no spaces)",
      placeholder: "ytboost",
      validate: (v) =>
        /^[a-z][a-z0-9-]*$/.test(v) ? undefined : "Must be lowercase letters, numbers, and hyphens",
    }),
  );

  const targetDir = path.join(rootDir, "verticals", id);
  if (existsSync(targetDir)) {
    cancel(`Directory verticals/${id} already exists.`);
    process.exit(1);
  }

  const displayName = exitIfCancelled(
    await text({ message: "Display name", placeholder: "YtBoost" }),
  );

  const tagline = exitIfCancelled(
    await text({ message: "Tagline (one line)", placeholder: "Turn 1 video into 18 pieces of content" }),
  );

  const primaryColor = exitIfCancelled(
    await text({
      message: "Primary brand color (hex)",
      placeholder: "#FF0000",
      validate: (v) =>
        /^#[0-9A-Fa-f]{6}$/.test(v) ? undefined : "Must be a valid hex color (e.g. #FF0000)",
    }),
  );

  const currency = exitIfCancelled(
    await select({
      message: "Pricing currency",
      options: [
        { value: "USD", label: "USD ($)" },
        { value: "KRW", label: "KRW (\u20A9)" },
        { value: "EUR", label: "EUR (\u20AC)" },
        { value: "JPY", label: "JPY (\u00A5)" },
      ],
    }),
  );

  const heroPlatforms = exitIfCancelled(
    await multiselect({
      message: "Hero platforms (shown prominently on landing page)",
      options: PLATFORMS.map((p) => ({ value: p.value, label: p.label })),
      required: true,
    }),
  );

  // Copy template
  cpSync(templateDir, targetDir, { recursive: true });

  // Read and update config
  const configPath = path.join(targetDir, "config.json");
  const config = JSON.parse(readFileSync(configPath, "utf-8"));

  const updatedConfig = {
    ...config,
    id,
    name: displayName,
    tagline,
    brand: {
      ...config.brand,
      colors: { ...config.brand.colors, primary: primaryColor },
    },
    domain: {
      primary: `${id}.dev`,
      api: `api.${id}.dev`,
      docs: `docs.${id}.dev`,
    },
    pricing: { ...config.pricing, currency },
    features: {
      ...config.features,
      platforms_hero: heroPlatforms,
      platforms_enabled: [
        ...new Set([...heroPlatforms, ...config.features.platforms_enabled]),
      ],
    },
  };

  writeFileSync(configPath, JSON.stringify(updatedConfig, null, 2) + "\n");

  // Update landing package.json name
  const landingPkgPath = path.join(targetDir, "landing/package.json");
  if (existsSync(landingPkgPath)) {
    const landingPkg = JSON.parse(readFileSync(landingPkgPath, "utf-8"));
    writeFileSync(
      landingPkgPath,
      JSON.stringify({ ...landingPkg, name: `@${id}/landing` }, null, 2) + "\n",
    );
  }

  // Update dashboard package.json name
  const dashPkgPath = path.join(targetDir, "dashboard/package.json");
  if (existsSync(dashPkgPath)) {
    const dashPkg = JSON.parse(readFileSync(dashPkgPath, "utf-8"));
    writeFileSync(
      dashPkgPath,
      JSON.stringify({ ...dashPkg, name: `@${id}/dashboard` }, null, 2) + "\n",
    );
  }

  // Create vercel.json
  const vercelConfig = {
    name: id,
    builds: [
      { src: "landing/package.json", use: "@vercel/next" },
      { src: "dashboard/package.json", use: "@vercel/next" },
    ],
    routes: [
      { src: "/app/(.*)", dest: "/dashboard/$1" },
      { src: "/(.*)", dest: "/landing/$1" },
    ],
  };
  writeFileSync(
    path.join(targetDir, "vercel.json"),
    JSON.stringify(vercelConfig, null, 2) + "\n",
  );

  outro(`Created verticals/${id}. Run: cd verticals/${id} && pnpm install && pnpm dev`);
}

main().catch(console.error);
