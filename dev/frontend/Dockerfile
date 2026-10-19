FROM node:20-alpine

WORKDIR /app
COPY package.json .
RUN npm install
COPY . .

# Serveur de développement Vite (prototype). Pour la production, préférer
# `npm run build` puis un serveur statique.
EXPOSE 3000
CMD ["npm", "run", "dev"]
