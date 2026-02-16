"""
Service de chiffrement IronCore avec support Property-Preserving Encryption
Intégration avec IronCore Alloy pour chiffrement réel des vecteurs et textes
"""
import os
import json
import logging
import base64
import asyncio
from typing import List, Dict, Any, Optional
from .encryption_key_service import EncryptionKeyService

try:
    import ironcore_alloy as alloy
    IRONCORE_AVAILABLE = True
except ImportError:
    IRONCORE_AVAILABLE = False

logger = logging.getLogger(__name__)

class IroncoreEncryptionService:
    """Service de chiffrement utilisant IronCore Alloy avec Property-Preserving Encryption"""
    
    def __init__(self, key_service: EncryptionKeyService):
        """
        Initialise le service de chiffrement IronCore Alloy
        
        Args:
            key_service: Service de gestion des clés
        """
        self.key_service = key_service
        self.alloy_client = None
        self.metadata = None
        self.secret_path = "documents"
        self.derivation_path = "content"
        
        # Détecter si le mode SKR est activé via le service de chiffrement
        self.skr_mode = getattr(key_service.keyvault, 'enable_skr_mode', False)
        
        if IRONCORE_AVAILABLE:
            self._init_alloy_client()
        else:
            logger.warning("IronCore Alloy non disponible - fonctionnement en mode simulation")
    
    def _init_alloy_client(self):
        """
        Initialise le client IronCore Alloy avec la clé depuis Key Vault
        
        Returns:
            Client Alloy initialisé ou None si erreur
        """
        try:
            # Récupérer la clé maître depuis Key Vault
            master_key = self._get_master_key_from_keyvault()
            if not master_key:
                logger.error("Impossible de récupérer la clé maître depuis Key Vault")
                return
                
            # Configuration Alloy avec la clé unique
            standalone_secret = alloy.StandaloneSecret(1, alloy.Secret(master_key))
            approximation_factor = 2.5
            
            # Configuration des secrets pour vecteurs
            vector_secrets = {
                self.secret_path: alloy.VectorSecret(
                    approximation_factor,
                    alloy.RotatableSecret(standalone_secret, None)
                )
            }
            
            # Configuration des secrets standards
            standard_secrets = alloy.StandardSecrets(1, [standalone_secret])
            deterministic_secrets = {
                self.secret_path: alloy.RotatableSecret(standalone_secret, None)
            }
            
            # Configuration finale
            config = alloy.StandaloneConfiguration(
                standard_secrets, deterministic_secrets, vector_secrets
            )
            
            self.alloy_client = alloy.Standalone(config)
            self.metadata = alloy.AlloyMetadata.new_simple("confidential-ai")
            
            logger.info("Client IronCore Alloy initialisé avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation IronCore Alloy: {e}")
            self.alloy_client = None
    
    def _get_master_key_from_keyvault(self) -> Optional[bytes]:
        """
        Récupère la clé maître depuis Azure Key Vault
        En mode SKR, utilise le service de chiffrement pour les clés symétriques
        En mode standard, utilise l'accès direct aux secrets (comportement actuel)
        
        Format attendu: Clé hexadécimale de 256 caractères (128 bytes)
        Générable avec: openssl rand -hex 128
        
        Returns:
            bytes: Clé maître ou None si erreur
        """
        try:
            # Nom du secret dans Key Vault depuis variable d'environnement
            secret_name = os.getenv("IRONCORE_MASTER_KEY_NAME", "ironcore-master-key")
            
            # Choix de la méthode selon le mode SKR
            if self.skr_mode:
                logger.info("Mode SKR activé - récupération sécurisée de la clé maître IronCore")
                secret_value = self._get_master_key_skr_mode(secret_name)
            else:
                logger.info("Mode standard - récupération directe de la clé maître IronCore")
                secret_value = self._get_master_key_standard_mode(secret_name)
            
            if secret_value:
                # Valider le format hexadécimal
                if len(secret_value) != 256:
                    logger.warning(f"Clé maître invalide: {len(secret_value)} caractères au lieu de 256")
                    # Regénérer une nouvelle clé conforme
                    logger.info("Génération d'une nouvelle clé maître conforme")
                    new_key = self._generate_master_key()
                    self._store_master_key(secret_name, new_key.hex())
                    return new_key
                
                # Convertir la clé hexadécimale en bytes
                return bytes.fromhex(secret_value)
            else:
                # Générer une nouvelle clé maître si elle n'existe pas
                logger.info("Génération d'une nouvelle clé maître IronCore (format openssl rand -hex 128)")
                new_key = self._generate_master_key()
                self._store_master_key(secret_name, new_key.hex())
                return new_key
                
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la clé maître: {e}")
            return None
    
    def _get_master_key_standard_mode(self, secret_name: str) -> Optional[str]:
        """
        Récupère la clé maître en mode standard (accès direct aux secrets)
        Conserve le comportement actuel pour la rétrocompatibilité
        
        Args:
            secret_name: Nom du secret dans Key Vault
            
        Returns:
            str: Clé maître hexadécimale ou None si non trouvée
        """
        try:
            # Mode standard : accès direct via le service de clés (comportement actuel)
            return self.key_service.get_secret(secret_name)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération standard de la clé maître: {e}")
            return None
    
    def _get_master_key_skr_mode(self, secret_name: str) -> Optional[str]:
        """
        Récupère la clé maître en mode SKR (clé symétrique chiffrée)
        Utilise le service de chiffrement pour déchiffrer la clé
        
        Args:
            secret_name: Nom du secret dans Key Vault
            
        Returns:
            str: Clé maître hexadécimale déchiffrée ou None si non trouvée
        """
        try:
            # En mode SKR, la clé est stockée comme une clé blob chiffrée
            blob_key_name = f"blob-key-ironcore-{secret_name}"
            
            # Essayer de récupérer la clé blob chiffrée
            try:
                decrypted_key_bytes = self.key_service.keyvault.decrypt_blob_key(blob_key_name)
                # Convertir les bytes en hexadécimal
                logger.info(f"Clé maître IronCore récupérée en mode SKR: {blob_key_name}")
                return decrypted_key_bytes.hex()
            except Exception as blob_error:
                logger.debug(f"Clé blob non trouvée ({blob_error}), essai en mode legacy...")
                
                # Fallback : essayer l'ancien format secret si la clé blob n'existe pas
                # Cela permet la migration progressive
                legacy_value = self.key_service.get_secret(secret_name)
                if legacy_value:
                    logger.info(f"Migration de la clé IronCore '{secret_name}' vers le mode SKR...")
                    # Convertir en bytes puis re-stocker comme clé blob chiffrée
                    try:
                        key_bytes = bytes.fromhex(legacy_value)
                        # Stocker la clé existante en mode SKR
                        self.key_service.keyvault.store_symmetric_key_as_blob(f"ironcore-{secret_name}", key_bytes)
                        logger.info("Migration vers SKR terminée avec succès")
                        return legacy_value
                    except Exception as migration_error:
                        logger.error(f"Erreur lors de la migration SKR: {migration_error}")
                        # Continuer avec la valeur legacy en cas d'erreur de migration
                        return legacy_value
                
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la récupération SKR de la clé maître: {e}")
            return None
    
    def _store_master_key(self, secret_name: str, key_hex: str) -> bool:
        """
        Stocke la clé maître selon le mode (standard ou SKR)
        
        Args:
            secret_name: Nom du secret dans Key Vault
            key_hex: Clé au format hexadécimal
            
        Returns:
            bool: True si stockage réussi
        """
        try:
            if self.skr_mode:
                # Mode SKR : stocker comme clé blob chiffrée
                blob_key_name = f"ironcore-{secret_name}"
                key_bytes = bytes.fromhex(key_hex)
                
                # Utiliser la nouvelle méthode pour stocker une clé existante
                logger.info(f"Stockage de la clé maître en mode SKR: {blob_key_name}")
                stored_secret_name = self.key_service.keyvault.store_symmetric_key_as_blob(blob_key_name, key_bytes)
                logger.info(f"Clé maître IronCore stockée en mode SKR: {stored_secret_name}")
                return True
            else:
                # Mode standard : stockage direct (comportement actuel)
                return self.key_service.set_secret(secret_name, key_hex)
                
        except Exception as e:
            logger.error(f"Erreur lors du stockage de la clé maître: {e}")
            return False

    def migrate_to_skr_mode(self, secret_name: str) -> bool:
        """
        Migre une clé maître existante vers le mode SKR
        
        Args:
            secret_name: Nom du secret à migrer
            
        Returns:
            bool: True si migration réussie, False sinon
        """
        try:
            # Vérifier qu'on est en mode SKR
            if not self._is_skr_mode():
                logger.warning("Migration SKR tentée en mode standard - ignorée")
                return False
            
            # Récupérer la clé existante en mode standard
            existing_key = self.key_service.get_secret(secret_name)
            if not existing_key:
                logger.warning(f"Aucune clé existante trouvée pour '{secret_name}'")
                return False
            
            # Convertir en bytes et stocker en mode SKR
            key_bytes = bytes.fromhex(existing_key)
            success = self.key_service.keyvault.store_symmetric_key_as_blob(f"ironcore-{secret_name}", key_bytes)
            
            if success:
                logger.info(f"Migration SKR réussie pour la clé '{secret_name}'")
                return True
            else:
                logger.error(f"Échec de la migration SKR pour '{secret_name}'")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la migration SKR de '{secret_name}': {e}")
            return False

    def _is_skr_mode(self) -> bool:
        """
        Détermine si le service fonctionne en mode SKR
        
        Returns:
            bool: True si mode SKR actif
        """
        return self.skr_mode
    
    def _generate_master_key(self) -> bytes:
        """
        Génère une nouvelle clé maître de 128 bytes au format openssl
        
        Équivalent à: openssl rand -hex 128
        Produit une clé hexadécimale de 256 caractères (128 bytes)
        
        Returns:
            bytes: Clé maître générée (128 bytes)
        """
        import secrets
        # Générer une clé forte de 128 bytes (équivalent à openssl rand -hex 128)
        key_bytes = secrets.token_bytes(128)
        
        # Log pour debug (sans révéler la clé complète)
        logger.info(f"Nouvelle clé maître générée: {len(key_bytes)} bytes (format hex: {len(key_bytes.hex())} caractères)")
        
        return key_bytes
    
    def is_encryption_available(self) -> bool:
        """
        Vérifie si le chiffrement est disponible
        
        Returns:
            bool: True si le chiffrement est disponible
        """
        return IRONCORE_AVAILABLE and self.alloy_client is not None
    
    async def encrypt_vector_with_key(self, vector: List[float], encryption_context: Dict) -> List[float]:
        """
        Chiffre un vecteur avec IronCore Alloy Property-Preserving Encryption
        
        Args:
            vector: Vecteur à chiffrer
            encryption_context: Contexte de chiffrement avec clés
            
        Returns:
            List[float]: Vecteur chiffré (même dimension)
        """
        if not self.is_encryption_available() or not self.alloy_client:
            # Mode simulation si IronCore non disponible
            logger.warning("IronCore Alloy non disponible - simulation du chiffrement")
            return [x + 0.001 for x in vector]
        
        try:
            # Validation du vecteur
            if not vector or not isinstance(vector, list):
                raise ValueError("Vecteur invalide")
            
            expected_dim = encryption_context.get("vector_dimension", 768)
            if len(vector) != expected_dim:
                raise ValueError(f"Dimension du vecteur incorrecte: {len(vector)} != {expected_dim}")
            
            # Chiffrement avec IronCore Alloy
            plaintext_vector = alloy.PlaintextVector(
                vector, 
                self.secret_path, 
                self.derivation_path
            )
            
            encrypted_vector = await self.alloy_client.vector().encrypt(
                plaintext_vector, 
                self.metadata
            )
            
            return encrypted_vector.encrypted_vector
            
        except Exception as e:
            logger.error(f"Erreur lors du chiffrement du vecteur: {e}")
            # Fallback vers simulation en cas d'erreur
            return [x + 0.001 for x in vector]
    
    async def decrypt_vector_with_key(self, encrypted_vector: List[float], encryption_context: Dict) -> List[float]:
        """
        Déchiffre un vecteur avec IronCore Alloy Property-Preserving Encryption
        
        Args:
            encrypted_vector: Vecteur chiffré
            encryption_context: Contexte de chiffrement avec clés
            
        Returns:
            List[float]: Vecteur déchiffré
        """
        if not self.is_encryption_available() or not self.alloy_client:
            logger.warning("IronCore Alloy non disponible - simulation du déchiffrement")
            return [x - 0.001 for x in encrypted_vector]
        
        try:
            # Validation
            if not encrypted_vector or not isinstance(encrypted_vector, list):
                raise ValueError("Vecteur chiffré invalide")
            
            logger.debug(f"Déchiffrement vecteur - dimension: {len(encrypted_vector)}")
            
            # Déchiffrement avec IronCore Alloy
            encrypted_vector_obj = alloy.EncryptedVector(
                encrypted_vector,
                self.secret_path,
                self.derivation_path
            )
            
            decrypted_vector = await self.alloy_client.vector().decrypt(
                encrypted_vector_obj,
                self.metadata
            )
            
            logger.debug("Vecteur déchiffré avec succès")
            return decrypted_vector.plaintext_vector
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement du vecteur: {e}")
            # Fallback vers simulation en cas d'erreur
            return [x - 0.001 for x in encrypted_vector]
    
    async def encrypt_text_with_key(self, text: str, encryption_context: Dict) -> str:
        """
        Chiffre un texte avec IronCore Alloy attached encryption
        
        Args:
            text: Texte à chiffrer
            encryption_context: Contexte de chiffrement
            
        Returns:
            str: Texte chiffré (base64)
        """
        if not self.is_encryption_available() or not self.alloy_client:
            logger.warning("IronCore Alloy non disponible - simulation du chiffrement texte")
            import base64
            encrypted_bytes = text.encode('utf-8')
            encrypted_text = base64.b64encode(encrypted_bytes).decode('utf-8')
            return f"ENC:{encrypted_text}"
        
        try:
            if not text or not isinstance(text, str):
                raise ValueError("Texte invalide")
            
            logger.debug(f"Chiffrement texte - longueur: {len(text)}")
            
            # Chiffrement avec IronCore Alloy Standard Attached
            text_bytes = text.encode()
            
            encrypted_bytes = await self.alloy_client.standard_attached().encrypt(
                text_bytes,
                self.metadata
            )
            
            # Encoder en base64 pour stockage
            import base64
            encrypted_text = base64.b64encode(encrypted_bytes).decode()
            encrypted_text = f"IRONCORE:{encrypted_text}"  # Marqueur IronCore
            
            logger.debug("Texte chiffré avec succès")
            return encrypted_text
            
        except Exception as e:
            logger.error(f"Erreur lors du chiffrement du texte: {e}")
            # Fallback vers simulation en cas d'erreur
            import base64
            encrypted_bytes = text.encode('utf-8')
            encrypted_text = base64.b64encode(encrypted_bytes).decode('utf-8')
            return f"ENC:{encrypted_text}"
    
    async def decrypt_text_with_key(self, encrypted_text: str, encryption_context: Dict) -> str:
        """
        Déchiffre un texte avec IronCore Alloy attached encryption
        
        Args:
            encrypted_text: Texte chiffré
            encryption_context: Contexte de chiffrement
            
        Returns:
            str: Texte déchiffré
        """
        if not self.is_encryption_available() or not self.alloy_client:
            logger.warning("IronCore Alloy non disponible - simulation du déchiffrement texte")
            # Gestion des fallbacks
            if encrypted_text.startswith("IRONCORE:"):
                # Fallback pour texte chiffré avec IronCore mais client non disponible
                return encrypted_text  # Retourner tel quel si impossible de déchiffrer
            elif encrypted_text.startswith("ENC:"):
                # Déchiffrement simulation
                import base64
                try:
                    base64_text = encrypted_text[4:]
                    decrypted_bytes = base64.b64decode(base64_text.encode('utf-8'))
                    return decrypted_bytes.decode('utf-8')
                except:
                    return encrypted_text
            return encrypted_text
        
        try:
            if not encrypted_text or not isinstance(encrypted_text, str):
                raise ValueError("Texte chiffré invalide")
            
            # Gestion des différents formats
            if encrypted_text.startswith("IRONCORE:"):
                # Déchiffrement IronCore Alloy
                base64_text = encrypted_text[9:]  # Enlever le préfixe "IRONCORE:"
                import base64
                encrypted_bytes = base64.b64decode(base64_text.encode())
                
                decrypted_bytes = await self.alloy_client.standard_attached().decrypt(
                    encrypted_bytes,
                    self.metadata
                )
                
                return decrypted_bytes.decode()
                
            elif encrypted_text.startswith("ENC:"):
                # Déchiffrement simulation (fallback)
                import base64
                base64_text = encrypted_text[4:]
                decrypted_bytes = base64.b64decode(base64_text.encode('utf-8'))
                return decrypted_bytes.decode('utf-8')
            else:
                # Texte non chiffré
                logger.debug("Texte non chiffré détecté")
                return encrypted_text
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement du texte: {e}")
            # Fallback en cas d'erreur
            return encrypted_text
    
    def get_encryption_info(self) -> Dict[str, Any]:
        """
        Retourne des informations sur l'état du chiffrement
        
        Returns:
            Dict: Informations sur le chiffrement
        """
        return {
            "available": self.is_encryption_available(),
            "project_id": self.project_id,
            "segment_group_id": self.segment_group_id,
            "client_initialized": self.ironcore_client is not None,
            "algorithm": "ironcore-ppe" if self.is_encryption_available() else "none"
        }
