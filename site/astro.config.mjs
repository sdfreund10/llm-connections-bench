// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import { siteUrl } from "./src/lib/site.ts";

// https://astro.build/config
export default defineConfig({
  site: siteUrl,
  integrations: [sitemap()],
});
