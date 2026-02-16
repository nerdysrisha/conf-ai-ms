"""
Service de gestion des clés de chiffrement pour Azure AI Search
Utilise Azure Key Vault pour stocker et gérer les contextes de chiffrement
"""
import os
import json
import uuid
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
from .encryption_service import EncryptionService

logger = logging.getLogger(__name__)

class EncryptionKeyService:
    """Service de gestion des clés pour le chiffrement des données de recherche"""
    
    def __init__(self, keyvault_service: EncryptionService):
        """
        Initialise le service de gestion des clés
        
        Args:
            keyvault_service: Service Azure Key Vault pour stockage des clés
        """
        self.keyvault = keyvault_service
        self.vector_key_name = os.getenv('VECTOR_ENCRYPTION_KEY_NAME', 'vector-encryption-key')
        self.text_key_name = os.getenv('TEXT_ENCRYPTION_KEY_NAME', 'text-encryption-key')
        self.search_context_name = os.getenv('SEARCH_CONTEXT_KEY_NAME', 'search-encryption-context')
        
        # Cache pour éviter les appels répétés au Key Vault
        self._context_cache = {}
        self._cache_expiry = None
        self._cache_ttl = timedelta(hours=1)  # Cache pendant 1 heure
        
    def get_vector_encryption_key(self) -> Optional[str]:
        """
        Récupère la clé pour chiffrement des vecteurs
        
        Returns:
            str: Clé de chiffrement des vecteurs ou None si non trouvée
        """
        try:
            return self.keyvault.get_private_key()  # Réutilise la clé privée existante
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la clé vecteur: {e}")
            return None
    
    def get_text_encryption_key(self) -> Optional[str]:
        """
        Récupère la clé pour chiffrement des textes
        
        Returns:
            str: Clé de chiffrement des textes ou None si non trouvée
        """
        try:
            return self.keyvault.get_public_key()  # Réutilise la clé publique existante
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la clé texte: {e}")
            return None
    
    def get_search_encryption_context(self) -> Dict:
        """
        Récupère ou crée le contexte de chiffrement pour la recherche
        
        Returns:
            Dict: Contexte de chiffrement avec ID, clés et métadonnées
        """
        # Vérifier le cache
        if self._is_cache_valid():
            logger.debug("Utilisation du contexte de chiffrement en cache")
            return self._context_cache
        
        try:
            # Tenter de récupérer le contexte existant
            context_json = self.keyvault.secret_client.get_secret(self.search_context_name).value
            context = json.loads(context_json)
            
            # Valider que le contexte n'est pas expiré
            if self._is_context_valid(context):
                self._update_cache(context)
                logger.info("Contexte de chiffrement récupéré depuis Key Vault")
                return context
            else:
                logger.info("Contexte de chiffrement expiré, création d'un nouveau")
                return self._create_new_context()
                
        except Exception as e:
            logger.warning(f"Contexte de chiffrement non trouvé: {e}, création d'un nouveau")
            return self._create_new_context()
    
    def _create_new_context(self) -> Dict:
        """
        Crée un nouveau contexte de chiffrement
        
        Returns:
            Dict: Nouveau contexte de chiffrement
        """
        context = {
            "context_id": str(uuid.uuid4()),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),  # Expire dans 30 jours
            "vector_key_version": 1,
            "text_key_version": 1,
            "algorithm": "ironcore-ppe",  # Property-Preserving Encryption
            "vector_dimension": int(os.getenv('NOMIC_EMBED_DIMENSION', 768))
        }
        
        try:
            # Stocker le nouveau contexte dans Key Vault
            context_json = json.dumps(context, indent=2)
            self.keyvault.secret_client.set_secret(self.search_context_name, context_json)
            
            # Mettre à jour le cache
            self._update_cache(context)
            
            logger.info(f"Nouveau contexte de chiffrement créé: {context['context_id']}")
            return context
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du contexte: {e}")
            raise
    
    def _is_context_valid(self, context: Dict) -> bool:
        """
        Vérifie si un contexte de chiffrement est encore valide
        
        Args:
            context: Contexte à valider
            
        Returns:
            bool: True si le contexte est valide
        """
        try:
            if 'expires_at' not in context:
                return False
                
            expires_at = datetime.fromisoformat(context['expires_at'])
            return datetime.utcnow() < expires_at
            
        except Exception as e:
            logger.error(f"Erreur lors de la validation du contexte: {e}")
            return False
    
    def _is_cache_valid(self) -> bool:
        """
        Vérifie si le cache est encore valide
        
        Returns:
            bool: True si le cache est valide
        """
        return (
            self._context_cache and 
            self._cache_expiry and 
            datetime.utcnow() < self._cache_expiry
        )
    
    def _update_cache(self, context: Dict):
        """
        Met à jour le cache du contexte
        
        Args:
            context: Contexte à mettre en cache
        """
        self._context_cache = context
        self._cache_expiry = datetime.utcnow() + self._cache_ttl
    
    def rotate_encryption_context(self) -> Dict:
        """
        Force la rotation du contexte de chiffrement
        
        Returns:
            Dict: Nouveau contexte de chiffrement
        """
        logger.info("Rotation forcée du contexte de chiffrement")
        
        # Invalider le cache
        self._context_cache = {}
        self._cache_expiry = None
        
        # Créer un nouveau contexte
        return self._create_new_context()
    
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Récupère un secret depuis Azure Key Vault
        
        Args:
            secret_name: Nom du secret à récupérer
            
        Returns:
            str: Valeur du secret ou None si non trouvé
        """
        try:
            secret = self.keyvault.secret_client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du secret {secret_name}: {e}")
            return None
    
    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Stocke un secret dans Azure Key Vault
        
        Args:
            secret_name: Nom du secret
            secret_value: Valeur du secret
            
        Returns:
            bool: True si stockage réussi, False sinon
        """
        try:
            self.keyvault.secret_client.set_secret(secret_name, secret_value)
            logger.info(f"Secret {secret_name} stocké avec succès dans Key Vault")
            return True
        except Exception as e:
            logger.error(f"Erreur lors du stockage du secret {secret_name}: {e}")
            return False
    
    def get_context_info(self) -> Dict:
        """
        Retourne des informations sur le contexte actuel
        
        Returns:
            Dict: Informations du contexte (sans données sensibles)
        """
        context = self.get_search_encryption_context()
        
        return {
            "context_id": context.get("context_id"),
            "created_at": context.get("created_at"),
            "expires_at": context.get("expires_at"),
            "algorithm": context.get("algorithm"),
            "vector_dimension": context.get("vector_dimension"),
            "is_cached": self._is_cache_valid()
        }
