FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json ./package.json
COPY apps/web/package.json ./apps/web/package.json
COPY packages/sdk-typescript/package.json ./packages/sdk-typescript/package.json
RUN npm install --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_DATA_BROWSER_V2=false
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_DATA_BROWSER_V2=${NEXT_PUBLIC_DATA_BROWSER_V2}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm --workspace packages/sdk-typescript run build \
    && npm --workspace apps/web run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "apps/web/server.js"]
