# Configuration du Chiffrement pour Azure AI Search

Ce guide explique comment configurer et utiliser le chiffrement Property-Preserving Encryption (PPE) avec IronCore CloakedAI dans l'application RAG.

## Vue d'ensemble

L'application supporte maintenant deux modes de fonctionnement :
- **Mode Normal** : Recherche et stockage sans chiffrement (mode par défaut)
- **Mode Chiffré** : Chiffrement des vecteurs et textes avec IronCore CloakedAI

## Architecture du Chiffrement

### Services Impliqués
1. **EncryptionKeyService** : Gestion des clés de chiffrement via Azure Key Vault
2. **IroncoreEncryptionService** : Interface avec IronCore CloakedAI pour PPE
3. **EncryptedAzureSearchService** : Service de recherche avec chiffrement automatique
4. **LLMService** : Support des workflows de recherche chiffrée

### Workflow du Chiffrement
```
Document → Embedding → Chiffrement → Indexation Azure Search
Query → Embedding → Chiffrement → Recherche → Déchiffrement → Réponse
```

## Configuration

### 1. Variables d'Environnement

Ajoutez les variables suivantes à votre fichier `.env` :

```bash
# Activation du chiffrement
ENABLE_SEARCH_ENCRYPTION=true

# Configuration IronCore CloakedAI
IRONCORE_PROJECT_ID=your_ironcore_project_id
IRONCORE_SEGMENT_GROUP_ID=your_segment_group_id
IRONCORE_API_KEY=your_ironcore_api_key

# Noms des clés dans Azure Key Vault
SEARCH_ENCRYPTION_KEY_NAME=search-encryption-key
SEARCH_ENCRYPTION_CONTEXT_NAME=search-context
```

### 2. Installation des Dépendances

```bash
# Si vous avez accès au package IronCore
pip install ironcore-alloy==0.5.0
```

**Note** : Le package `ironcore-alloy` nécessite un accès spécial. En mode développement, l'application utilise un service de simulation.

### 3. Configuration Azure Key Vault

L'application stocke automatiquement :
- **Clés de chiffrement** : Utilisées par IronCore pour le PPE
- **Contexte de chiffrement** : Métadonnées nécessaires pour le déchiffrement

## Utilisation

### Activation du Mode Chiffré

1. Définissez `ENABLE_SEARCH_ENCRYPTION=true` dans votre `.env`
2. Configurez les variables IronCore
3. Redémarrez l'application

### Endpoints API

#### Vérification du Statut
```bash
GET /api/encryption/status
```

Retourne :
```json
{
  "encryption_enabled": true,
  "services": {
    "search_encryption": true,
    "ironcore_available": false,
    "key_vault_available": true
  }
}
```

#### Chat avec Chiffrement
```bash
POST /api/chat
```

L'endpoint utilise automatiquement le mode chiffré si activé.

## Développement et Tests

### Mode Simulation

En l'absence du package IronCore, l'application utilise un mode simulation :
- Chiffrement/déchiffrement simulé avec Base64
- Permet le développement sans credentials IronCore
- Logs détaillés pour le debugging

### Logs de Debug

L'application génère des logs détaillés pour :
- Opérations de chiffrement/déchiffrement
- Gestion des clés
- Recherches chiffrées
- Erreurs et exceptions

## Sécurité

### Bonnes Pratiques
1. **Rotation des clés** : Les clés sont gérées automatiquement
2. **Isolation des contextes** : Chaque environnement a ses propres clés
3. **Logging sécurisé** : Les données sensibles ne sont jamais loggées
4. **Fallback robuste** : L'application fonctionne en mode normal si le chiffrement échoue

### Considerations
- Le chiffrement PPE preserve les propriétés des vecteurs pour la recherche sémantique
- Les performances peuvent être impactées par les opérations de chiffrement
- La compatibilité avec les index existants nécessite une réindexation

## Troubleshooting

### Erreurs Communes

1. **Service IronCore indisponible**
   - Vérifiez la configuration des variables d'environnement
   - L'application continue en mode simulation

2. **Erreurs de clés**
   - Vérifiez l'accès à Azure Key Vault
   - Les clés sont créées automatiquement si absentes

3. **Erreurs de recherche**
   - Vérifiez la cohérence du contexte de chiffrement
   - Assurez-vous que l'index utilise les bons champs chiffrés

### Debug Mode

Pour activer les logs détaillés :
```bash
DEBUG=True
```

## Migration

### Depuis un Index Non-Chiffré

1. Sauvegardez vos données existantes
2. Activez le chiffrement
3. Réindexez tous les documents
4. Testez les recherches

### Retour au Mode Normal

1. Définissez `ENABLE_SEARCH_ENCRYPTION=false`
2. Redémarrez l'application
3. L'application utilisera l'index non-chiffré existant

## Support

Pour des questions spécifiques au chiffrement ou à IronCore CloakedAI, consultez :
- Documentation IronCore CloakedAI
- Logs de l'application (`/logs`)
- Endpoint de statut (`/api/encryption/status`)
