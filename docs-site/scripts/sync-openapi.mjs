import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..", "..");
const source = resolve(projectRoot, "docs", "openapi.json");
const destination = resolve(__dirname, "..", "openapi.json");

await mkdir(dirname(destination), { recursive: true });
await copyFile(source, destination);
console.log(`Copied OpenAPI schema to ${destination}`);
