FROM node:22-slim

WORKDIR /app

COPY rules_labeling/frontend/package.json rules_labeling/frontend/package-lock.json ./
RUN npm ci

COPY rules_labeling/frontend/ ./

EXPOSE 5173

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"]
