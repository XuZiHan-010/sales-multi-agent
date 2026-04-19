/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow SSE streaming responses
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [{ key: "X-Content-Type-Options", value: "nosniff" }],
      },
    ]
  },
  // Point API calls to backend — override via NEXT_PUBLIC_API_BASE env var
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api",
  },
}

export default nextConfig
