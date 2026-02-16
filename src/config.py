"""
Configuration de l'application RAG
"""
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class Config:
    """Configuration de l'application"""
    
    # Configuration Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 8000))
    
    # URL de base de l'application (pour les liens de téléchargement)
    APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://localhost:8000')
    
    # Configuration Azure Storage
    AZURE_STORAGE_ACCOUNT_NAME = os.getenv('AZURE_STORAGE_ACCOUNT_NAME', 'saconfidentialai')
    AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')  # Optionnel, pour compatibilité
    AZURE_STORAGE_CONTAINER_NAME = os.getenv('AZURE_STORAGE_CONTAINER_NAME', 'encrypted-documents')
    
    # Configuration Azure Key Vault
    AZURE_KEYVAULT_URL = os.getenv('AZURE_KEYVAULT_URL')
    ENCRYPTION_PRIVATE_KEY_NAME = os.getenv('ENCRYPTION_PRIVATE_KEY_NAME', 'encryption-private-key')
    ENCRYPTION_PUBLIC_KEY_NAME = os.getenv('ENCRYPTION_PUBLIC_KEY_NAME', 'encryption-public-key')
    
    # Configuration Azure Authentication
    # Si AZURE_CLIENT_ID est défini, utilise ManagedIdentityCredential avec ce client ID
    # Sinon, utilise DefaultAzureCredential
    AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID')
    
    # Configuration SKR (Secure Key Release) - Mode Confidentiel
    ENABLE_SKR_MODE = os.getenv('ENABLE_SKR_MODE', 'false').lower() == 'true'
    SKR_MAA_ENDPOINT = os.getenv('SKR_MAA_ENDPOINT')  # Microsoft Azure Attestation endpoint
    SKR_KEYVAULT_KEY_URL = os.getenv('SKR_KEYVAULT_KEY_URL')  # URL de la clé Key Vault (format: https://vault.vault.azure.net/keys/key-name)
    IMDS_CLIENT_ID = os.getenv('IMDS_CLIENT_ID')  # Client ID pour l'identité managée IMDS (optionnel)
    
    # Configuration Azure AI Search
    AZURE_SEARCH_SERVICE_NAME = os.getenv('AZURE_SEARCH_SERVICE_NAME')
    AZURE_SEARCH_INDEX_NAME = os.getenv('AZURE_SEARCH_INDEX_NAME', 'documents-index')
    AZURE_SEARCH_API_KEY = os.getenv('AZURE_SEARCH_API_KEY')  # Optionnel - utilise DefaultAzureCredential si non défini
    
    # Configuration du chiffrement pour Azure Search
    ENABLE_SEARCH_ENCRYPTION = os.getenv('ENABLE_SEARCH_ENCRYPTION', 'false').lower() == 'true'
    
    # Configuration IronCore pour le chiffrement
    IRONCORE_PROJECT_ID = os.getenv('IRONCORE_PROJECT_ID')
    IRONCORE_SEGMENT_GROUP_ID = os.getenv('IRONCORE_SEGMENT_GROUP_ID')
    IRONCORE_API_KEY = os.getenv('IRONCORE_API_KEY')
    
    # Noms des clés de chiffrement dans Key Vault
    VECTOR_ENCRYPTION_KEY_NAME = os.getenv('VECTOR_ENCRYPTION_KEY_NAME', 'vector-encryption-key')
    TEXT_ENCRYPTION_KEY_NAME = os.getenv('TEXT_ENCRYPTION_KEY_NAME', 'text-encryption-key')
    SEARCH_CONTEXT_KEY_NAME = os.getenv('SEARCH_CONTEXT_KEY_NAME', 'search-encryption-context')
    
    # Configuration Azure Document Intelligence
    AZURE_DOC_INTELLIGENCE_ENDPOINT = os.getenv('AZURE_DOC_INTELLIGENCE_ENDPOINT')
    AZURE_DOC_INTELLIGENCE_API_KEY = os.getenv('AZURE_DOC_INTELLIGENCE_API_KEY')
    
    # Configuration Embeddings Nomic
    NOMIC_EMBED_ENDPOINT = os.getenv('NOMIC_EMBED_ENDPOINT')
    NOMIC_EMBED_API_KEY = os.getenv('NOMIC_EMBED_API_KEY')
    NOMIC_EMBED_MODEL = os.getenv('NOMIC_EMBED_MODEL', 'nomic-embed-text')
    NOMIC_EMBED_DIMENSION = int(os.getenv('NOMIC_EMBED_DIMENSION', 768))
    
    # Configuration LLM phi-2.7
    PHI_MODEL_ENDPOINT = os.getenv('PHI_MODEL_ENDPOINT')
    PHI_MODEL_API_KEY = os.getenv('PHI_MODEL_API_KEY')
    PHI_MODEL_NAME = os.getenv('PHI_MODEL_NAME', 'phi:2.7')
    
    # Configuration des embeddings
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
    EMBEDDING_DIMENSION = int(os.getenv('EMBEDDING_DIMENSION', 768))  # Dimension pour Nomic Embed
    
    # Configuration du traitement des documents
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', 1000))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', 200))
    UPLOAD_TIMEOUT_SECONDS = int(os.getenv('UPLOAD_TIMEOUT_SECONDS', 120))
    
    # Configuration du chunking intelligent
    USE_SMART_CHUNKING = os.getenv('USE_SMART_CHUNKING', 'true').lower() == 'true'
    SMART_CHUNK_TARGET_SIZE = int(os.getenv('SMART_CHUNK_TARGET_SIZE', 400))
    SMART_CHUNK_MAX_SIZE = int(os.getenv('SMART_CHUNK_MAX_SIZE', 600))
    SMART_CHUNK_OVERLAP = int(os.getenv('SMART_CHUNK_OVERLAP', 80))
    
    # Configuration avancée des tableaux
    TABLE_CHUNKING_STRATEGY = os.getenv('TABLE_CHUNKING_STRATEGY', 'preserve_structure')
    TABLE_MAX_ROWS_PER_CHUNK = int(os.getenv('TABLE_MAX_ROWS_PER_CHUNK', 10))
    TABLE_ALWAYS_INCLUDE_HEADERS = os.getenv('TABLE_ALWAYS_INCLUDE_HEADERS', 'true').lower() == 'true'
    TABLE_SEMANTIC_GROUPING = os.getenv('TABLE_SEMANTIC_GROUPING', 'true').lower() == 'true'
    TABLE_COLUMN_CHUNKING = os.getenv('TABLE_COLUMN_CHUNKING', 'false').lower() == 'true'
    
    # Configuration LLM
    MAX_TOKENS = int(os.getenv('MAX_TOKENS', 1000))
    TEMPERATURE = float(os.getenv('TEMPERATURE', 0.7))
    TOP_P = float(os.getenv('TOP_P', 0.9))
    
    # Taille maximale des fichiers (en bytes)
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 10 * 1024 * 1024))  # 10MB par défaut
    
    # Formats de fichiers supportés
    ALLOWED_EXTENSIONS = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'txt': 'text/plain',
        'json': 'application/json'
    }
    
    @classmethod
    def validate_config(cls):
        """Valide la configuration et vérifie les variables requises"""
        required_vars = [
            # Note: AZURE_STORAGE_CONNECTION_STRING supprimé - utilise DefaultAzureCredential avec AZURE_STORAGE_ACCOUNT_NAME
            'AZURE_STORAGE_ACCOUNT_NAME',
            'AZURE_KEYVAULT_URL',
            'AZURE_SEARCH_SERVICE_NAME',
            # Note: AZURE_SEARCH_API_KEY supprimé - utilise DefaultAzureCredential
            'AZURE_DOC_INTELLIGENCE_ENDPOINT',
            'AZURE_DOC_INTELLIGENCE_API_KEY',
            'NOMIC_EMBED_ENDPOINT',
            'NOMIC_EMBED_API_KEY',
            'PHI_MODEL_ENDPOINT',
            'PHI_MODEL_API_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")
        
        return True
    
    @classmethod
    def get_azure_search_endpoint(cls):
        """Retourne l'endpoint Azure Search complet"""
        return f"https://{cls.AZURE_SEARCH_SERVICE_NAME}.search.windows.net"
