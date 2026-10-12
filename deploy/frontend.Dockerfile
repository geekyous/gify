# ---- 构建前端：VITE_API_BASE_URL 在此注入（生产为 API 对外地址）----
FROM node:22-alpine AS build
ARG VITE_API_BASE_URL
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 运行：纯静态托管，不反代 API（跨域保留，由后端 CORS 白名单放行）----
FROM nginx:alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /fe/dist /usr/share/nginx/html
EXPOSE 80
