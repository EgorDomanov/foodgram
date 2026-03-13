FROM nginx:1.25.4-alpine

COPY infra/nginx.conf /etc/nginx/templates/default.conf.template

RUN mkdir -p /usr/share/nginx/html/api/docs /usr/share/nginx/html/frontend
COPY docs/ /usr/share/nginx/html/api/docs/