# Production frontend image for the NAS deployment: build the React bundle, then
# serve it from nginx. nginx also reverse-proxies /api + /health to the backend
# (config is mounted at runtime — see web/nginx/nginx.conf in docker-compose.nas.yml).
#
# Built locally by dev.sh (`./dev.sh nas deploy`) and loaded onto the NAS; never
# built on the NAS itself.

FROM node:18-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
# npm here is 10.8.2 (whatever node:18-alpine ships) and `npm ci` rejects a
# lockfile that disagrees with package.json. A newer host npm (11.x) prunes
# nested entries npm 10 still needs, so regenerate the lock through THIS image
# when adding a dependency — see "Adding a dependency" in web/README.md.
RUN npm ci

COPY . .

# Same-origin relative API paths — one hostname fronts app + API behind Cloudflare.
# The branding args let the deploy pick up SITE_TITLE/TAGLINE from .env at build time.
ARG REACT_APP_API_URL=""
ARG REACT_APP_SITE_TITLE="Jyotir AI"
ARG REACT_APP_SITE_TAGLINE=""
ARG REACT_APP_ENABLE_MAP_PICKER="true"
ARG REACT_APP_GOOGLE_CLIENT_ID=""
ENV REACT_APP_API_URL=$REACT_APP_API_URL \
    REACT_APP_SITE_TITLE=$REACT_APP_SITE_TITLE \
    REACT_APP_SITE_TAGLINE=$REACT_APP_SITE_TAGLINE \
    REACT_APP_ENABLE_MAP_PICKER=$REACT_APP_ENABLE_MAP_PICKER \
    REACT_APP_GOOGLE_CLIENT_ID=$REACT_APP_GOOGLE_CLIENT_ID

RUN npm run build

FROM nginx:alpine
# Static bundle. The server block is mounted at /etc/nginx/conf.d/default.conf by compose.
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
