FROM node:22-alpine AS dependencies
WORKDIR /app
COPY website/package.json website/package-lock.json ./
RUN npm ci
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY website/ ./
COPY shared/ /shared/
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_MAPTILER_KEY
ARG NEXT_PUBLIC_MAP_ENABLED=false
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY NEXT_PUBLIC_MAPTILER_KEY=$NEXT_PUBLIC_MAPTILER_KEY NEXT_PUBLIC_MAP_ENABLED=$NEXT_PUBLIC_MAP_ENABLED NEXT_TELEMETRY_DISABLED=1
RUN npm run build
FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S -g 10001 awaaz && adduser -S -u 10001 -G awaaz awaaz
COPY --from=builder --chown=awaaz:awaaz /app/.next/standalone ./
COPY --from=builder --chown=awaaz:awaaz /app/.next/static ./.next/static
COPY --from=builder --chown=awaaz:awaaz /app/public ./public
USER awaaz
EXPOSE 3000
CMD ["node", "server.js"]
