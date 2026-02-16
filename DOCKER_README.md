# 🐋 Déploiement Docker - Application RAG

Ce guide vous aide à déployer l'application RAG Flask dans un conteneur Docker.

## 📋 Prérequis

- Docker et Docker Compose installés
- Fichier `.env` configuré avec vos services Azure

## 🚀 Déploiement rapide

### Option 1 : Script automatique (recommandé)

**Windows :**
```powershell
.\deploy.ps1
```

**Linux/Mac :**
```bash
chmod +x deploy.sh
./deploy.sh
```

### Option 2 : Commandes manuelles

```bash
# Construction de l'image
docker-compose build

# Démarrage de l'application
docker-compose up -d

# Vérification des logs
docker-compose logs -f
```

## 🔧 Configuration

### Variables d'environnement requises

Assurez-vous que votre fichier `.env` contient :

```env
# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=your_connection_string
AZURE_STORAGE_CONTAINER_NAME=encrypted-documents

# Azure Key Vault
AZURE_KEYVAULT_URL=https://your-keyvault.vault.azure.net/

# Azure AI Search
AZURE_SEARCH_SERVICE_NAME=your_search_service
AZURE_SEARCH_INDEX_NAME=documents-index
AZURE_SEARCH_API_KEY=your_search_api_key

# Azure Document Intelligence
AZURE_DOC_INTELLIGENCE_ENDPOINT=your_endpoint
AZURE_DOC_INTELLIGENCE_API_KEY=your_api_key

# LLM phi-3.5
PHI_MODEL_ENDPOINT=your_phi_endpoint
PHI_MODEL_API_KEY=your_phi_api_key
PHI_MODEL_NAME=phi3.5:3.8b

# Nomic Embeddings
NOMIC_EMBED_ENDPOINT=your_nomic_endpoint
NOMIC_EMBED_API_KEY=your_nomic_api_key
NOMIC_EMBED_MODEL=nomic-embed-text
NOMIC_EMBED_DIMENSION=768
```

## 📊 Gestion du conteneur

### Commandes utiles

```bash
# Voir l'état des conteneurs
docker-compose ps

# Voir les logs en temps réel
docker-compose logs -f

# Redémarrer l'application
docker-compose restart

# Arrêter l'application
docker-compose down

# Reconstruire l'image (après modifications du code)
docker-compose build --no-cache
docker-compose up -d
```

### Health Check

L'application inclut un health check automatique qui vérifie :
- Disponibilité de l'endpoint principal
- Intervalle : 30 secondes
- Timeout : 10 secondes
- Nombre d'essais : 3

## 🌐 Accès à l'application

Une fois déployée, l'application est accessible sur :
- **URL locale :** http://localhost:8000
- **Interface chat :** http://localhost:8000
- **API :** http://localhost:8000/api/

## 🔍 Dépannage

### Problèmes courants

1. **L'application ne démarre pas :**
   ```bash
   docker-compose logs
   ```

2. **Erreurs de connexion Azure :**
   - Vérifiez vos variables d'environnement dans `.env`
   - Validez vos clés d'API Azure

3. **Port déjà utilisé :**
   ```bash
   # Modifier le port dans docker-compose.yml
   ports:
     - "8080:8000"  # Changer 8000 en 8080
   ```

4. **Problèmes de permissions :**
   ```bash
   # Linux/Mac : donner les permissions d'exécution
   chmod +x deploy.sh
   ```

### Logs détaillés

Pour voir les logs détaillés de l'application :
```bash
docker-compose logs -f rag-app
```

## 📈 Optimisations de production

### Ajustements pour la production

1. **Modifier les variables d'environnement dans docker-compose.yml :**
   ```yaml
   environment:
     - FLASK_ENV=production
     - GUNICORN_WORKERS=4
     - GUNICORN_TIMEOUT=120
   ```

2. **Configurer un reverse proxy (Nginx) :**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **Monitoring et logs :**
   - Configurer la rotation des logs
   - Utiliser des outils de monitoring comme Prometheus

## 🔐 Sécurité

- L'application s'exécute avec un utilisateur non-root
- Les secrets sont gérés via les variables d'environnement
- Utilisation de HTTPS recommandée en production

## ⚡ Performance

L'image Docker est optimisée avec :
- Mise en cache des layers Docker
- Installation efficace des dépendances Python
- Utilisation de Gunicorn avec 4 workers par défaut
- Configuration de timeout appropriée (120s)

## 📞 Support

En cas de problème :
1. Vérifiez les logs : `docker-compose logs`
2. Validez votre configuration `.env`
3. Testez vos services Azure en dehors du conteneur
