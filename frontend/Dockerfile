# build env
FROM node:21.7.1-alpine
WORKDIR /app
COPY package*.json .npmrc ./
RUN npm install
COPY . ./
RUN npm run build
CMD cp -r build result_build
