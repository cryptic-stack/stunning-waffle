FROM node:20-alpine@sha256:f598378b5240225e6beab68fa9f356db1fb8efe55173e6d4d8153113bb8f333c AS deps

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY .eslintrc.cjs .eslintignore ./
COPY apps/frontend/package.json apps/frontend/package.json
COPY packages/shared-types/package.json packages/shared-types/package.json
COPY packages/shared-client/package.json packages/shared-client/package.json

RUN pnpm install --frozen-lockfile

FROM deps AS build

ARG VITE_API_BASE_URL=""
ARG VITE_AUTH_USER_ID=""
ARG VITE_AUTH_USER_EMAIL=""
ARG VITE_AUTH_USER_NAME=""

ENV VITE_API_BASE_URL="${VITE_API_BASE_URL}"
ENV VITE_AUTH_USER_ID="${VITE_AUTH_USER_ID}"
ENV VITE_AUTH_USER_EMAIL="${VITE_AUTH_USER_EMAIL}"
ENV VITE_AUTH_USER_NAME="${VITE_AUTH_USER_NAME}"

COPY apps/frontend apps/frontend
COPY packages/shared-types packages/shared-types
COPY packages/shared-client packages/shared-client

WORKDIR /workspace/apps/frontend

RUN pnpm build

FROM deps AS dev

ARG VITE_API_BASE_URL=""
ARG VITE_AUTH_USER_ID=""
ARG VITE_AUTH_USER_EMAIL=""
ARG VITE_AUTH_USER_NAME=""

ENV VITE_API_BASE_URL="${VITE_API_BASE_URL}"
ENV VITE_AUTH_USER_ID="${VITE_AUTH_USER_ID}"
ENV VITE_AUTH_USER_EMAIL="${VITE_AUTH_USER_EMAIL}"
ENV VITE_AUTH_USER_NAME="${VITE_AUTH_USER_NAME}"

COPY apps/frontend apps/frontend
COPY packages/shared-types packages/shared-types
COPY packages/shared-client packages/shared-client

WORKDIR /workspace/apps/frontend

CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "3000"]

FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 AS runtime

COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
