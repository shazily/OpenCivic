FROM node:20-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=http://localhost:8100/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci --quiet; else npm install --quiet; fi
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 opencivic && adduser --system --uid 1001 opencivic
COPY --from=builder /app/public ./public
COPY --from=builder --chown=opencivic:opencivic /app/.next/standalone ./
COPY --from=builder --chown=opencivic:opencivic /app/.next/static ./.next/static
USER opencivic
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --retries=3 CMD wget -qO- http://localhost:3000 || exit 1
CMD ["node", "server.js"]
