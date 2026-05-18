import type { NextConfig } from 'next'

// Set NEXT_PUBLIC_API_URL in Vercel env vars once Railway is deployed.
// Example: https://btc-stm-production.up.railway.app
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'https://btcstm-production.up.railway.app'

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${API_URL}/api/:path*`,
      },
    ]
  },
}
export default nextConfig
