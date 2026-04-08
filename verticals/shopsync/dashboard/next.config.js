const path = require("path");

const packagesDir = path.resolve(__dirname, "../../../packages");

/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@contentflow/ui", "@contentflow/config", "@contentflow/engine"],
  webpack(config) {
    config.resolve.symlinks = false;
    return config;
  },
};

module.exports = nextConfig;
