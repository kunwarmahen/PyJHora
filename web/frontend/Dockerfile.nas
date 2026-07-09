# Production frontend image for the NAS deployment: build the React bundle, then
# serve it from nginx. nginx also reverse-proxies /api + /health to the backend
# (config is mounted at runtime — see web/nginx/nginx.conf in docker-compose.nas.yml).
#
# Built locally by dev.sh (`./dev.sh nas deploy`) and loaded onto the NAS; never
# built on the NAS itself.

FROM node:18-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Same-origin relative API paths — one hostname fronts app + API behind Cloudflare.
# The branding args let the deploy pick up SITE_TITLE/TAGLINE from .env at build time.
ARG REACT_APP_API_URL=""
ARG REACT_APP_SITE_TITLE="Jyotir AI"
ARG REACT_APP_SITE_TAGLINE=""
ARG REACT_APP_ENABLE_MAP_PICKER="true"
ENV REACT_APP_API_URL=$REACT_APP_API_URL \
    REACT_APP_SITE_TITLE=$REACT_APP_SITE_TITLE \
    REACT_APP_SITE_TAGLINE=$REACT_APP_SITE_TAGLINE \
    REACT_APP_ENABLE_MAP_PICKER=$REACT_APP_ENABLE_MAP_PICKER

RUN npm run build

FROM nginx:alpine
# Static bundle. The server block is mounted at /etc/nginx/conf.d/default.conf by compose.
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
