# Imagem de DESENVOLVIMENTO: roda o dev server do Vite com hot reload.
# O deploy de produção é na Vercel, que faz o próprio build a partir do repo,
# então não há estágio de build estático aqui.
FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
