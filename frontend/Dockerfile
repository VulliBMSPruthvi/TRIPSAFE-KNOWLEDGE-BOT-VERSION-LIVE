# syntax=docker/dockerfile:1.7
# Dev image for the React frontend — Vite dev server with HMR.
# The production build (multi-stage with nginx) lives in Phase D-deploy.

FROM node:20-alpine

ENV NODE_ENV=development
WORKDIR /app

# Workaround for corporate TLS-intercepting proxies (same pattern as the
# Python image): tell npm to skip strict SSL only at install time.
ARG NPM_STRICT_SSL=false
RUN npm config set strict-ssl ${NPM_STRICT_SSL}

COPY package.json package-lock.json* ./
RUN npm install --no-fund --no-audit

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
