# Guide d'implémentation SKR (Secure Key Release)

## 🔐 **Vue d'ensemble**

L'intégration SKR (Secure Key Release) permet à l'application de fonctionner dans un environnement d'informatique confidentielle Azure, où les clés de chiffrement sont protégées par l'attestation de la machine virtuelle.

## 🏗️ **Architecture SKR**

### **Mode Standard (Actuel)**
```
📄 Document → 🔑 Chiffrement AES → 🔐 Clé AES chiffrée avec RSA → 💾 Stockage
                ↓
          🗝️ Clés RSA stockées comme "secrets" dans Key Vault
```

### **Mode SKR (Nouveau)**
```
📄 Document → 🔑 Chiffrement AES → 🔒 Clé AES chiffrée avec SKR → 💾 Stockage
                ↓
          🗝️ Clés RSA stockées comme "clés" dans Key Vault
          🛡️ Attestation VM requise pour décrypter
```

## 🚀 **Fonctionnalités implémentées**

### **1. Configuration SKR**
- `ENABLE_SKR_MODE` : Active/désactive le mode SKR
- `SKR_MAA_ENDPOINT` : Endpoint Microsoft Azure Attestation
- `SKR_KEYVAULT_KEY_URL` : URL de la clé Key Vault pour SKR

### **2. Service de chiffrement dual**
- **Mode standard** : Utilise RSA direct pour les clés AES
- **Mode SKR** : Utilise `skr_client.py` pour wrap/unwrap les clés AES

### **3. Gestion des clés symétriques**
- `_wrap_symmetric_key_with_skr()` : Chiffre les clés AES avec SKR
- `_unwrap_symmetric_key_with_skr()` : Déchiffre les clés AES avec SKR
- Support pour les clés de blob individuelles

## 📁 **Fichiers modifiés**

### **`src/config.py`**
```python
# Nouvelles variables de configuration
ENABLE_SKR_MODE = os.getenv('ENABLE_SKR_MODE', 'false').lower() == 'true'
SKR_MAA_ENDPOINT = os.getenv('SKR_MAA_ENDPOINT')
SKR_KEYVAULT_KEY_URL = os.getenv('SKR_KEYVAULT_KEY_URL')
```

### **`src/services/encryption_service.py`**
**Nouveautés :**
- Constructeur avec paramètres SKR
- Import conditionnel de `SKRClient`
- Méthodes `_wrap_symmetric_key_with_skr()` et `_unwrap_symmetric_key_with_skr()`
- Support des algorithmes `AES-256-CBC+SKR` et `AES-256-CBC+RSA-OAEP`
- Méthodes pour les clés de blob : `generate_and_encrypt_blob_key()` et `decrypt_blob_key()`

### **`app.py`**
```python
# Initialisation avec paramètres SKR
encryption_service = EncryptionService(
    keyvault_url=Config.AZURE_KEYVAULT_URL,
    enable_skr_mode=Config.ENABLE_SKR_MODE,
    skr_maa_endpoint=Config.SKR_MAA_ENDPOINT,
    skr_keyvault_key_url=Config.SKR_KEYVAULT_KEY_URL
)
```

### **`.env`**
```bash
# Configuration SKR (décommentér pour activer)
# ENABLE_SKR_MODE=true
# SKR_MAA_ENDPOINT=https://sharedeus2.eus2.attest.azure.net
# SKR_KEYVAULT_KEY_URL=https://my-vault.vault.azure.net/keys/my-key-name
```

## 🔄 **Flux de chiffrement/déchiffrement**

### **Chiffrement (Mode SKR)**
1. **Document reçu** → Génération clé AES aléatoire
2. **Chiffrement AES** → Document chiffré avec AES-256-CBC
3. **SKR Wrap** → `skr_client.wrap_key()` chiffre la clé AES
4. **Package final** → `{encrypted_key: wrapped_aes_key, iv: iv, encrypted_data: aes_data, algorithm: "AES-256-CBC+SKR"}`

### **Déchiffrement (Mode SKR)**
1. **Package reçu** → Extraction des composants
2. **SKR Unwrap** → `skr_client.unwrap_key()` déchiffre la clé AES
3. **Déchiffrement AES** → Récupération du document original

## 🧪 **Tests et validation**

### **Test de configuration**
```bash
python test_skr_mode.py
```

### **Test d'intégration manuel**
```python
# En mode SKR
encryption_service = EncryptionService(
    keyvault_url="https://vault.vault.azure.net",
    enable_skr_mode=True,
    skr_maa_endpoint="https://sharedeus2.eus2.attest.azure.net",
    skr_keyvault_key_url="https://vault.vault.azure.net/keys/enckey"
)

# Chiffrement
test_data = b"Donnees confidentielles"
encrypted = encryption_service.encrypt_data(test_data)

# Déchiffrement
decrypted = encryption_service.decrypt_data(encrypted)
assert decrypted == test_data
```

## ⚠️ **Limitations et considérations**

### **Environnement requis**
- **Linux uniquement** : `skr_client.py` nécessite un environnement Linux
- **Azure Confidential Computing** : VM avec support d'attestation
- **Key Vault configuré** : Clés stockées comme ressources "Key" (pas "Secret")

### **Rétrocompatibilité**
- ✅ **Documents existants** : Continuent de fonctionner en mode standard
- ✅ **Migration progressive** : Basculement par configuration
- ✅ **Fallback** : Détection automatique du format de chiffrement

### **Performance**
- **Coût d'attestation** : Chaque opération SKR nécessite une attestation
- **Latence supplémentaire** : Communication avec MAA endpoint
- **Mise en cache** : Possibilité d'optimiser les appels d'attestation

## 🚀 **Migration vers SKR**

### **Étape 1 : Configuration**
```bash
# Dans .env
ENABLE_SKR_MODE=true
SKR_MAA_ENDPOINT=https://sharedeus2.eus2.attest.azure.net
SKR_KEYVAULT_KEY_URL=https://vault.vault.azure.net/keys/encryption-key
```

### **Étape 2 : Migration des clés**
1. **Exporter** les clés RSA depuis Key Vault Secrets
2. **Importer** comme ressources Key dans Key Vault
3. **Configurer** les permissions d'accès pour la VM confidentielle

### **Étape 3 : Test et validation**
1. **Environnement de test** avec VM confidentielle
2. **Validation** des opérations de chiffrement/déchiffrement
3. **Test de performance** avec charge réelle

### **Étape 4 : Déploiement production**
1. **Sauvegarde** complète de l'environnement actuel
2. **Migration progressive** par composant
3. **Monitoring** des performances et erreurs

## 🔧 **Dépannage**

### **Erreur "SKRClient non disponible"**
- **Cause** : Environnement Windows ou `skr_client.py` manquant
- **Solution** : Vérifier `ENABLE_SKR_MODE=false` ou déployer sur Linux

### **Erreur d'attestation**
- **Cause** : VM non confidentielle ou MAA endpoint incorrect
- **Solution** : Vérifier la configuration de la VM et l'endpoint MAA

### **Erreur de clé Key Vault**
- **Cause** : Clé stockée comme Secret au lieu de Key
- **Solution** : Migrer vers Key Vault Keys avec permissions appropriées

## 📊 **Monitoring recommandé**

### **Métriques clés**
- **Taux de succès** des opérations SKR
- **Latence** des appels d'attestation
- **Erreurs** de chiffrement/déchiffrement
- **Utilisation** Key Vault Keys vs Secrets

### **Alertes**
- **Échec d'attestation** répétés
- **Latence excessive** des opérations SKR
- **Erreurs de configuration** SKR

---

## 📝 **Notes de développement**

Cette implémentation maintient une **compatibilité totale** avec l'architecture existante tout en ajoutant les capacités SKR. Le basculement entre les modes se fait par simple configuration, permettant une migration progressive et sécurisée vers l'informatique confidentielle Azure.