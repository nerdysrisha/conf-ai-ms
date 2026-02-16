FROM python:3.13-slim AS build
RUN apt update -y && apt upgrade -y && apt install -y wget git build-essential libssl-dev libcurl4-openssl-dev libjsoncpp-dev libboost-all-dev nlohmann-json3-dev cmake
RUN mkdir /app
WORKDIR /app
COPY azguestattestation1_1.1.2_amd64.deb .
RUN dpkg -i azguestattestation1_1.1.2_amd64.deb
RUN git clone --recursive https://github.com/Azure/confidential-computing-cvm-guest-attestation
WORKDIR /app/confidential-computing-cvm-guest-attestation/cvm-securekey-release-app
RUN mkdir build
WORKDIR ./build
RUN cmake .. -DCMAKE_BUILD_TYPE=Release  # Debug for more tracing output and define TRACE constant in CMakeLists.txt
RUN make

# Dockerfile pour l'application RAG Flask
# Utilise une image Python officielle optimisée (3.10 pour compatibilité Azure)
FROM python:3.13-slim AS final
RUN mkdir /app
# Définir le répertoire de travail dans le conteneur
WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    libffi-dev \
    libssl-dev \
    ca-certificates \
    sudo \
    && apt clean && rm -rf /var/lib/apt/lists/*
    
# Copier le code source de l'application
COPY . .

# Mettre à jour pip et installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    dpkg -i azguestattestation1_1.1.2_amd64.deb && rm azguestattestation1_1.1.2_amd64.deb

COPY --from=build /app/confidential-computing-cvm-guest-attestation/cvm-securekey-release-app/build/AzureAttestSKR /app/src/services

# Créer un utilisateur non-root pour la sécurité
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app && \
    adduser appuser sudo && \
    echo "appuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
USER appuser

# Exposer le port sur lequel l'application va tourner
EXPOSE 8000

# Variables d'environnement par défaut
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Commande de démarrage avec Gunicorn pour la production
#CMD ["python", "app.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--keep-alive", "2", "app:create_app()"]
