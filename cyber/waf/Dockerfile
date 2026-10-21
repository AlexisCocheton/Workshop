# Image Caddy avec le module de limite de débit (caddy-ratelimit).
# L'image standard caddy:2.8-alpine n'inclut pas ce module tiers : on le
# compile avec xcaddy. Le rate limit protège /auth et /shop/login du brute force.
FROM caddy:2.8-builder-alpine AS build
RUN xcaddy build v2.8.4 \
    --with github.com/mholt/caddy-ratelimit@v0.1.0

FROM caddy:2.8-alpine
COPY --from=build /usr/bin/caddy /usr/bin/caddy
