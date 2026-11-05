// Copies the Fluent MDL2 icon fonts into public/ so the portal never loads them from a CDN.
import { cpSync, existsSync, mkdirSync } from "node:fs";

const fonts = "node_modules/@fluentui/font-icons-mdl2/fonts";
if (!existsSync(fonts)) throw new Error(`Missing ${fonts}; run npm ci first`);
mkdirSync("public/fluent-icons", { recursive: true });
cpSync(fonts, "public/fluent-icons", { recursive: true });
