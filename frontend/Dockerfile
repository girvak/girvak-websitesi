# GİRVAK site — Astro SSR on Node.
#
# The build stage needs the dev dependencies; the runtime stage installs only
# production ones (astro, @astrojs/node, sharp) and carries the built server.
FROM node:24-slim@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df AS build

WORKDIR /build
COPY package.json package-lock.json ./
# npm ci installs from the lockfile; a bare `install` would re-resolve.
RUN npm ci
COPY . .
# No PUBLIC_* value is baked in: env.ts reads the environment at request time,
# so one image serves every environment and a config change is a restart.
RUN npm run build


FROM node:24-slim@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df AS runtime

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=4321

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /build/dist ./dist

USER node
EXPOSE 4321

CMD ["node", "./dist/server/entry.mjs"]
