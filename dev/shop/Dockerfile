FROM node:20-alpine

WORKDIR /app
COPY package.json .
RUN npm install
COPY . .

# Serveur de développement Vite (prototype), comme le dashboard. Pour la
# production, préférer `npm run build` puis un serveur statique.
EXPOSE 3002
CMD ["npm", "run", "dev"]
