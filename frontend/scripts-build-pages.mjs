// Build the static GitHub Pages demo: dashboard + precomputed JSON in ../site
import { execSync } from "node:child_process";
import { cpSync, existsSync, rmSync, writeFileSync } from "node:fs";

if (!existsSync("static-data/fleet.json")) {
  console.error("static-data/ missing: run `python -m scripts.export_static` in backend/ first");
  process.exit(1);
}
execSync("npx vite build --outDir ../site --emptyOutDir", {
  stdio: "inherit",
  env: { ...process.env, VITE_STATIC: "1" },
});
cpSync("static-data", "../site/data", { recursive: true });
writeFileSync("../site/.nojekyll", "");
console.log("Static demo ready in site/");
