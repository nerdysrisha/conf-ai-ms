# Application RAG avec LLM phi-3.5 et Azure

Une application complète de **Retrieval-Augmented Generation (RAG)** avec interface de chat pour interagir avec un modèle LLM phi-3.5, incluant le chiffrement automatique des fichiers et la recherche vectorielle.

## 🌟 Fonctionnalités

### Core Features
- **Interface de chat** pour interaction avec LLM phi-3.5
- **Upload et chiffrement** automatique des documents
- **Extraction intelligente** avec Azure Document Intelligence
- **Recherche vectorielle** avec Azure AI Search
- **Endpoint d'embeddings** pour génération de vecteurs
- **Déchiffrement automatique** des liens dans les réponses
- **Gestion sécurisée des clés** avec Azure Key Vault

### Sécurité
- 🔐 **Chiffrement RSA** avec clés publique/privée
- 🔑 **Azure Key Vault** pour stockage sécurisé des clés
- 🛡️ **Azure Storage** avec conteneurs chiffrés
- 🔒 **Déchiffrement à la demande** des fichiers

### Formats supportés
- 📄 **PDF** (.pdf)
- 📝 **Word** (.docx)
- 📰 **Texte** (.txt)
- **Extraction intelligente** : Azure Document Intelligence extrait le texte, les tableaux, les structures et les paires clé-valeur
- **Fallback robuste** : Méthodes d'extraction alternatives si Document Intelligence n'est pas disponible
- **Support étendu** : PDF, Word, images (JPEG, PNG, TIFF) avec Azure Document Intelligence

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Interface     │    │   Application    │    │   Azure         │
│   utilisateur   │◄──►│   Flask          │◄──►│   Services      │
│   (HTML/JS)     │    │   (Python)       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────────────────────┐
                       │         Services                │
                       ├─────────────────────────────────┤
                       │ • Encryption (Key Vault)       │
                       │ • Storage (Blob Storage)        │
                       │ • Search (AI Search)           │
                       │ • Embeddings (Sentence Trans.) │
                       │ • LLM (phi-3.5)               │
                       │ • Document Processing          │
                       └─────────────────────────────────┘
```

## 🚀 Installation

### Prérequis
- Python 3.8+
- Compte Azure avec les services suivants configurés :
  - Azure Storage Account
  - Azure Key Vault
  - Azure AI Search
  - Azure Document Intelligence (recommandé pour extraction avancée)
  - Endpoint pour modèle phi-3.5

### 1. Cloner et installer
```bash
cd "c:\Users\sdechoux\OneDrive - Microsoft\Documents\Projects\Confidential AI\apps"
pip install -r requirements.txt
```

### 2. Configuration
Copiez `.env.example` vers `.env` et configurez vos variables :

```bash
cp .env.example .env
```

Editez `.env` avec vos valeurs Azure :
```env
# Configuration Azure Storage
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection_string
AZURE_STORAGE_CONTAINER_NAME=encrypted-documents

# Configuration Azure Key Vault
AZURE_KEYVAULT_URL=https://your-keyvault.vault.azure.net/

# Configuration Azure AI Search
AZURE_SEARCH_SERVICE_NAME=your-search-service
AZURE_SEARCH_INDEX_NAME=documents-index
AZURE_SEARCH_API_KEY=your_search_api_key

# Configuration Azure Document Intelligence
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://your-doc-intelligence.cognitiveservices.azure.com/
AZURE_DOC_INTELLIGENCE_API_KEY=your_doc_intelligence_api_key

# Configuration LLM phi-3.5
PHI_MODEL_ENDPOINT=your_phi35_endpoint
PHI_MODEL_API_KEY=your_phi35_api_key

# Configuration Nomic Embed Text (pour les embeddings)
NOMIC_EMBED_ENDPOINT=https://api-atlas.nomic.ai/v1/embedding/text
NOMIC_EMBED_API_KEY=your_nomic_api_key
NOMIC_EMBED_MODEL=nomic-embed-text-v1.5
NOMIC_EMBED_DIMENSION=768

# Configuration de l'application
SECRET_KEY=your_secret_key_here
DEBUG=True
```

### 3. Lancer l'application
```bash
python app.py
```

L'application sera accessible à `http://localhost:8000`

## 📖 Utilisation

### 1. Upload de documents
- Accédez à `/upload`
- Glissez-déposez vos fichiers ou cliquez pour sélectionner
- Les fichiers sont automatiquement :
  - Chiffrés avec la clé publique
  - Stockés dans Azure Storage
  - Traités et segmentés en chunks
  - Indexés dans Azure AI Search

### 2. Chat avec l'assistant
- Accédez à `/` 
- Posez vos questions dans l'interface de chat
- L'assistant recherche dans vos documents indexés
- Recevez des réponses avec sources et liens de téléchargement

### 3. Téléchargement sécurisé
- Les liens dans les réponses pointent vers `/api/files/{id}/decrypt`
- Le fichier est automatiquement déchiffré lors du téléchargement
- Nom de fichier original conservé

## 🔧 API Endpoints

### Documents
- `POST /api/upload` - Upload et chiffrement de fichier
- `GET /api/files` - Liste des fichiers
- `GET /api/files/{id}/decrypt` - Téléchargement déchiffré
- `DELETE /api/files/{id}` - Suppression de fichier
- `GET /api/extraction-info` - Informations sur les capacités d'extraction

### Chat et Recherche
- `POST /api/chat` - Chat avec l'assistant RAG
- `GET /api/search?q={query}` - Recherche dans les documents
- `POST /api/embeddings` - Génération d'embeddings (via Nomic API)

### Système
- `GET /api/health` - Vérification de santé des services

## 🤖 Service d'Embeddings

L'application utilise l'API **Nomic Embed Text** pour générer les embeddings vectoriels :

- **Modèle** : `nomic-embed-text-v1.5`
- **Dimension** : 768 dimensions
- **API** : https://api-atlas.nomic.ai/v1/embedding/text
- **Avantages** :
  - Pas d'installation locale de PyTorch
  - Meilleure performance et fiabilité
  - Embeddings de haute qualité

### Test de l'API Nomic
```bash
python test_nomic.py
```

## 📁 Structure du projet

```
apps/
├── app.py                          # Application Flask principale
├── requirements.txt                # Dépendances Python
├── .env.example                   # Variables d'environnement exemple
├── src/
│   ├── config.py                       # Configuration centralisée
│   ├── services/                       # Services métier
│   │   ├── encryption_service.py       # Chiffrement avec Key Vault
│   │   ├── azure_storage_service.py    # Stockage Azure
│   │   ├── azure_search_service.py     # Recherche vectorielle
│   │   ├── azure_doc_intelligence_service.py # Extraction Azure Document Intelligence
│   │   ├── embedding_service.py        # Génération d'embeddings
│   │   ├── llm_service.py              # Interface LLM phi-3.5
│   │   └── document_processor.py       # Traitement de documents
│   ├── models/                         # Modèles de données
│   └── utils/                     # Utilitaires
├── templates/                     # Templates HTML
│   ├── index.html                 # Interface de chat
│   └── upload.html               # Interface d'upload
└── static/                       # Ressources statiques
```

## 🔐 Flux de sécurité

### Upload de fichier
1. **Upload** : Fichier uploadé via l'interface
2. **Extraction intelligente** : Azure Document Intelligence extrait texte, tableaux, structures
3. **Segmentation** : Texte divisé en chunks optimisés
4. **Chiffrement** : Fichier original chiffré avec clé publique
5. **Stockage** : Fichier chiffré stocké dans Azure Storage
6. **Indexation** : Chunks de texte indexés dans Azure AI Search avec embeddings

### Réponse avec fichier
1. **Question** : Utilisateur pose une question
2. **Recherche** : Recherche vectorielle dans l'index
3. **Génération** : LLM génère la réponse avec références
4. **Traitement** : Liens convertis vers endpoints de déchiffrement
5. **Affichage** : Réponse avec liens sécurisés

## 🛠️ Développement

### Tests
```bash
# TODO: Ajouter les tests
pytest tests/
```

### Déploiement
```bash
# Production avec Gunicorn
gunicorn --bind 0.0.0.0:8000 app:app
```

### Variables d'environnement
Toutes les variables sont documentées dans `.env.example`

## 🤝 Contribution

1. Fork le projet
2. Créez une branche feature (`git checkout -b feature/amazing-feature`)
3. Committez vos changements (`git commit -m 'Add amazing feature'`)
4. Push vers la branche (`git push origin feature/amazing-feature`)
5. Ouvrez une Pull Request

## 📝 License

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🆘 Support

Pour toute question ou problème :
- Créez une issue GitHub
- Consultez la documentation Azure
- Vérifiez les logs de l'application

## 🔄 Roadmap

- [ ] Support de plus de formats de fichiers
- [ ] Interface d'administration
- [ ] Analytics et métriques
- [ ] Support multi-langue
- [ ] API REST complète
- [ ] Conteneurisation Docker
- [ ] Tests automatisés
- [ ] Documentation API (Swagger)
