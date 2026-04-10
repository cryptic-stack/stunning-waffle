FROM node:20-alpine AS deps

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /workspace

COPY package.json pnpm-workspace.yaml tsconfig.base.json ./
COPY .eslintrc.cjs .eslintignore ./
COPY apps/frontend/package.json apps/frontend/package.json
COPY packages/shared-types/package.json packages/shared-types/package.json
COPY packages/shared-client/package.json packages/shared-client/package.json

RUN pnpm install --no-frozen-lockfile

FROM deps AS build

COPY apps/frontend apps/frontend
COPY packages/shared-types packages/shared-types
COPY packages/shared-client packages/shared-client

WORKDIR /workspace/apps/frontend

RUN pnpm build

FROM deps AS dev

COPY apps/frontend apps/frontend
COPY packages/shared-types packages/shared-types
COPY packages/shared-client packages/shared-client

WORKDIR /workspace/apps/frontend

CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "3000"]

FROM nginx:1.27-alpine AS runtime

COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
