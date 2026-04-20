/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [{ key: "X-Content-Type-Options", value: "nosniff" }],
      },
    ]
  },
}

export default nextConfig
