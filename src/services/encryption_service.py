"""
Service de chiffrement utilisant Azure Key Vault pour la gestion des clés
Utilise un chiffrement hybride AES+RSA pour les gros fichiers
Supporte le mode SKR (Secure Key Release) pour les environnements confidentiels
"""
import os
import base64
from typing import Tuple, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import logging
import json

logger = logging.getLogger(__name__)

class EncryptionService:
    """Service de chiffrement avec gestion des clés via Azure Key Vault"""
    
    def __init__(self, keyvault_url: str, enable_skr_mode: bool = False, 
                 skr_maa_endpoint: str = None, skr_keyvault_key_url: str = None):
        """
        Initialise le service de chiffrement
        
        Args:
            keyvault_url: URL du Key Vault Azure
            enable_skr_mode: Active le mode SKR (Secure Key Release)
            skr_maa_endpoint: Endpoint Microsoft Azure Attestation pour SKR
            skr_keyvault_key_url: URL de la clé Key Vault pour SKR
        """
        self.keyvault_url = keyvault_url
        self.enable_skr_mode = enable_skr_mode
        
        # Configuration de l'authentification
        # Si AZURE_CLIENT_ID est défini, utiliser ManagedIdentityCredential avec ce client ID
        # Sinon, utiliser DefaultAzureCredential
        azure_client_id = os.getenv('AZURE_CLIENT_ID')
        
        if azure_client_id:
            logger.info(f"Utilisation de ManagedIdentityCredential avec client_id: {azure_client_id}")
            self.credential = ManagedIdentityCredential(client_id=azure_client_id)
        else:
            logger.info("Utilisation de DefaultAzureCredential")
            self.credential = DefaultAzureCredential()
        
        self.secret_client = SecretClient(vault_url=keyvault_url, credential=self.credential)
        self.private_key_name = os.getenv('ENCRYPTION_PRIVATE_KEY_NAME', 'encryption-private-key')
        self.public_key_name = os.getenv('ENCRYPTION_PUBLIC_KEY_NAME', 'encryption-public-key')
        
        # Configuration SKR
        if self.enable_skr_mode:
            if not skr_maa_endpoint or not skr_keyvault_key_url:
                raise ValueError("Mode SKR activé mais endpoints MAA ou Key Vault non configurés")
            
            self.skr_maa_endpoint = skr_maa_endpoint
            self.skr_keyvault_key_url = skr_keyvault_key_url
            self.key_client = KeyClient(vault_url=keyvault_url, credential=self.credential)
            
            # Configurer les variables d'environnement pour SKRClient
            os.environ['MAA_ENDPOINT'] = skr_maa_endpoint
            os.environ['KEYVAULT_KEY'] = skr_keyvault_key_url
            
            # Configurer IMDS_CLIENT_ID si disponible
            imds_client_id = os.getenv('IMDS_CLIENT_ID')
            if imds_client_id:
                os.environ['IMDS_CLIENT_ID'] = imds_client_id
                logger.info(f"Configuration IMDS_CLIENT_ID pour SKR: {imds_client_id}")
            
            # Initialiser le client SKR
            try:
                from .skr_client import SKRClient
                self.skr_client = SKRClient()
                logger.info(f"Mode SKR activé avec succès - MAA: {skr_maa_endpoint}, KeyVault: {skr_keyvault_key_url}")
            except ImportError as e:
                logger.error(f"Impossible d'importer SKRClient: {e}")
                raise ValueError("SKRClient non disponible pour le mode SKR")
        else:
            logger.info("Mode standard (non-SKR) activé")
        
    def generate_key_pair(self) -> Tuple[str, str]:
        """
        Génère une nouvelle paire de clés RSA et les stocke dans Key Vault
        Non disponible en mode SKR (les clés doivent être configurées via Azure Key Vault)
        
        Returns:
            Tuple[str, str]: (clé privée PEM, clé publique PEM)
        """
        try:
            if self.enable_skr_mode:
                raise ValueError("Génération de clés non supportée en mode SKR - utilisez les scripts de configuration Azure Key Vault")
            
            # Générer la paire de clés RSA
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            public_key = private_key.public_key()
            
            # Sérialiser les clés au format PEM
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            # Stocker les clés dans Key Vault
            self.secret_client.set_secret(self.private_key_name, private_pem)
            self.secret_client.set_secret(self.public_key_name, public_pem)
            
            logger.info("Nouvelle paire de clés générée et stockée dans Key Vault")
            return private_pem, public_pem
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération des clés: {e}")
            raise
    
    def get_public_key(self) -> Optional[str]:
        """
        Récupère la clé publique depuis Key Vault
        En mode SKR, l'accès direct aux clés est limité pour des raisons de sécurité
        
        Returns:
            str: Clé publique au format PEM ou None si non trouvée
        """
        try:
            if self.enable_skr_mode:
                # Mode SKR: Limiter l'accès direct aux clés
                # Les opérations de chiffrement doivent utiliser les méthodes SKR appropriées
                logger.warning("Accès direct à la clé publique en mode SKR - considérez utiliser les méthodes SKR")
                raise ValueError("Accès direct aux clés limité en mode SKR - utilisez les méthodes de chiffrement appropriées")
            else:
                # Mode standard: récupérer depuis les secrets
                secret = self.secret_client.get_secret(self.public_key_name)
                return secret.value
        except Exception as e:
            if self.enable_skr_mode:
                logger.error(f"Tentative d'accès à la clé publique en mode SKR: {e}")
                raise
            else:
                logger.warning(f"Clé publique non trouvée dans Key Vault: {e}")
                return None
    
    def get_private_key(self) -> Optional[str]:
        """
        Récupère la clé privée depuis Key Vault
        En mode SKR, l'accès direct à la clé privée est interdit pour des raisons de sécurité
        
        Returns:
            str: Clé privée au format PEM ou None si non trouvée
        """
        try:
            if self.enable_skr_mode:
                # Mode SKR: Interdire l'accès direct à la clé privée
                # Toutes les opérations cryptographiques doivent passer par SKR
                raise ValueError("Accès direct à la clé privée interdit en mode SKR - utilisez les méthodes SKR")
            else:
                # Mode standard: récupérer depuis les secrets
                secret = self.secret_client.get_secret(self.private_key_name)
                return secret.value
        except Exception as e:
            if self.enable_skr_mode:
                logger.error(f"Tentative d'accès à la clé privée en mode SKR: {e}")
                raise
            else:
                logger.warning(f"Clé privée non trouvée dans Key Vault: {e}")
                return None
    
    def _wrap_symmetric_key_with_skr(self, symmetric_key: bytes) -> str:
        """
        Chiffre une clé symétrique avec le client SKR
        
        Args:
            symmetric_key: Clé symétrique à chiffrer
            
        Returns:
            str: Clé symétrique chiffrée (base64)
        """
        try:
            # Utiliser SKR pour chiffrer la clé symétrique
            # Les endpoints sont déjà configurés dans les variables d'environnement
            wrapped_key = self.skr_client.wrap_key(
                key=base64.b64encode(symmetric_key).decode('utf-8')
            )
            return wrapped_key
        except Exception as e:
            logger.error(f"Erreur lors du chiffrement SKR de la clé symétrique: {e}")
            raise
    
    def _unwrap_symmetric_key_with_skr(self, wrapped_key: str) -> bytes:
        """
        Déchiffre une clé symétrique avec le client SKR
        
        Args:
            wrapped_key: Clé symétrique chiffrée
            
        Returns:
            bytes: Clé symétrique déchiffrée
        """
        try:
            # Utiliser SKR pour déchiffrer la clé symétrique
            # Les endpoints sont déjà configurés dans les variables d'environnement
            unwrapped_key = self.skr_client.unwrap_key(
                encrypted_key=wrapped_key
            )
            return base64.b64decode(unwrapped_key.encode('utf-8'))
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement SKR de la clé symétrique: {e}")
            raise
    
    def generate_and_encrypt_blob_key(self, blob_name: str) -> Tuple[str, bytes]:
        """
        Génère une clé symétrique pour un blob et la chiffre selon le mode
        
        Args:
            blob_name: Nom du blob (pour la création d'un nom de secret unique)
            
        Returns:
            Tuple[str, bytes]: (nom du secret pour la clé, clé symétrique en clair)
        """
        try:
            # Générer une clé AES-256 pour le blob
            blob_key = os.urandom(32)  # 256 bits
            
            # Créer un nom unique pour stocker la clé chiffrée
            secret_name = f"blob-key-{blob_name.replace('/', '-').replace('.', '-')}"
            
            if self.enable_skr_mode:
                # Mode SKR: Chiffrer la clé avec SKR et stocker comme secret
                wrapped_key = self._wrap_symmetric_key_with_skr(blob_key)
                self.secret_client.set_secret(secret_name, wrapped_key)
                logger.info(f"Clé blob chiffrée avec SKR et stockée: {secret_name}")
            else:
                # Mode standard: Chiffrer la clé avec RSA et stocker comme secret
                public_key_pem = self.get_public_key()
                if not public_key_pem:
                    raise ValueError("Clé publique non disponible pour chiffrer la clé blob")
                
                public_key = load_pem_public_key(public_key_pem.encode('utf-8'))
                encrypted_blob_key = public_key.encrypt(
                    blob_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                encrypted_blob_key_b64 = base64.b64encode(encrypted_blob_key).decode('utf-8')
                self.secret_client.set_secret(secret_name, encrypted_blob_key_b64)
                logger.info(f"Clé blob chiffrée avec RSA et stockée: {secret_name}")
            
            return secret_name, blob_key
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération/chiffrement de la clé blob: {e}")
            raise
    
    def decrypt_blob_key(self, secret_name: str) -> bytes:
        """
        Récupère et déchiffre une clé symétrique de blob
        
        Args:
            secret_name: Nom du secret contenant la clé chiffrée
            
        Returns:
            bytes: Clé symétrique déchiffrée
        """
        try:
            # Récupérer la clé chiffrée depuis Key Vault
            secret = self.secret_client.get_secret(secret_name)
            encrypted_key = secret.value
            
            if self.enable_skr_mode:
                # Mode SKR: Déchiffrer avec SKR
                blob_key = self._unwrap_symmetric_key_with_skr(encrypted_key)
                logger.info(f"Clé blob déchiffrée avec SKR: {secret_name}")
            else:
                # Mode standard: Déchiffrer avec RSA
                private_key_pem = self.get_private_key()
                if not private_key_pem:
                    raise ValueError("Clé privée non disponible pour déchiffrer la clé blob")
                
                private_key = load_pem_private_key(
                    private_key_pem.encode('utf-8'),
                    password=None
                )
                
                encrypted_blob_key = base64.b64decode(encrypted_key.encode('utf-8'))
                blob_key = private_key.decrypt(
                    encrypted_blob_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                logger.info(f"Clé blob déchiffrée avec RSA: {secret_name}")
            
            return blob_key
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement de la clé blob: {e}")
            raise
    
    def store_symmetric_key_as_blob(self, blob_name: str, symmetric_key: bytes) -> str:
        """
        Stocke une clé symétrique existante en tant que blob chiffré
        (Contrairement à generate_and_encrypt_blob_key qui génère une nouvelle clé)
        
        Args:
            blob_name: Nom du blob (pour la création d'un nom de secret unique)
            symmetric_key: Clé symétrique existante à stocker
            
        Returns:
            str: Nom du secret utilisé pour stocker la clé chiffrée
        """
        try:
            # Créer un nom unique pour stocker la clé chiffrée
            secret_name = f"blob-key-{blob_name.replace('/', '-').replace('.', '-')}"
            
            if self.enable_skr_mode:
                # Mode SKR: Chiffrer la clé avec SKR et stocker comme secret
                wrapped_key = self._wrap_symmetric_key_with_skr(symmetric_key)
                self.secret_client.set_secret(secret_name, wrapped_key)
                logger.info(f"Clé symétrique existante chiffrée avec SKR et stockée: {secret_name}")
            else:
                # Mode standard: Chiffrer la clé avec RSA et stocker comme secret
                public_key_pem = self.get_public_key()
                if not public_key_pem:
                    raise ValueError("Clé publique non disponible pour chiffrer la clé blob")
                
                public_key = load_pem_public_key(public_key_pem.encode('utf-8'))
                encrypted_blob_key = public_key.encrypt(
                    symmetric_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                encrypted_blob_key_b64 = base64.b64encode(encrypted_blob_key).decode('utf-8')
                self.secret_client.set_secret(secret_name, encrypted_blob_key_b64)
                logger.info(f"Clé symétrique existante chiffrée avec RSA et stockée: {secret_name}")
            
            return secret_name
            
        except Exception as e:
            logger.error(f"Erreur lors du stockage de la clé symétrique existante: {e}")
            raise
    
    def encrypt_data(self, data: bytes) -> str:
        """
        Chiffre des données avec un système hybride AES+RSA
        - Génère une clé AES aléatoire pour chiffrer les données
        - Chiffre la clé AES avec RSA  
        - Retourne un package contenant la clé AES chiffrée et les données chiffrées
        
        Args:
            data: Données à chiffrer
            
        Returns:
            str: Package chiffré encodé en base64 (JSON contenant clé AES chiffrée + données AES)
        """
        try:
            # Étape 1: Générer une clé AES-256 aléatoire
            aes_key = os.urandom(32)  # 256 bits
            iv = os.urandom(16)  # 128 bits pour l'IV
            
            # Étape 2: Chiffrer les données avec AES
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            encryptor = cipher.encryptor()
            
            # Padding PKCS7 pour AES
            block_size = 16
            padding_length = block_size - (len(data) % block_size)
            padded_data = data + bytes([padding_length] * padding_length)
            
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # Étape 3: Chiffrer la clé AES 
            if self.enable_skr_mode:
                # Mode SKR: Utiliser SKR pour chiffrer la clé AES
                encrypted_aes_key_b64 = self._wrap_symmetric_key_with_skr(aes_key)
                algorithm = 'AES-256-CBC+SKR'
            else:
                # Mode standard: Chiffrer la clé AES avec RSA
                public_key_pem = self.get_public_key()
                if not public_key_pem:
                    raise ValueError("Clé publique non disponible")
                
                public_key = load_pem_public_key(public_key_pem.encode('utf-8'))
                
                encrypted_aes_key = public_key.encrypt(
                    aes_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                encrypted_aes_key_b64 = base64.b64encode(encrypted_aes_key).decode('utf-8')
                algorithm = 'AES-256-CBC+RSA-OAEP'
            
            # Étape 4: Créer le package final
            package = {
                'encrypted_key': encrypted_aes_key_b64,
                'iv': base64.b64encode(iv).decode('utf-8'),
                'encrypted_data': base64.b64encode(encrypted_data).decode('utf-8'),
                'algorithm': algorithm
            }
            
            # Encoder le package complet en base64
            package_json = json.dumps(package)
            return base64.b64encode(package_json.encode('utf-8')).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Erreur lors du chiffrement hybride: {e}")
            raise
    
    def decrypt_data(self, encrypted_package: str) -> bytes:
        """
        Déchiffre des données avec le système hybride AES+RSA
        
        Args:
            encrypted_package: Package chiffré encodé en base64
            
        Returns:
            bytes: Données déchiffrées
        """
        try:
            # Étape 1: Décoder le package
            package_json = base64.b64decode(encrypted_package.encode('utf-8')).decode('utf-8')
            package = json.loads(package_json)
            
            # Vérifier l'algorithme et déchiffrer la clé AES selon le mode
            algorithm = package.get('algorithm')
            
            if algorithm == 'AES-256-CBC+SKR':
                # Mode SKR: Utiliser SKR pour déchiffrer la clé AES
                wrapped_aes_key = package['encrypted_key']
                aes_key = self._unwrap_symmetric_key_with_skr(wrapped_aes_key)
                
            elif algorithm == 'AES-256-CBC+RSA-OAEP':
                # Mode standard: Déchiffrer la clé AES avec RSA
                if self.enable_skr_mode:
                    raise ValueError("Format RSA-OAEP non supporté en mode SKR - utilisez le format SKR")
                
                private_key_pem = self.get_private_key()
                if not private_key_pem:
                    raise ValueError("Clé privée non disponible")
                
                private_key = load_pem_private_key(
                    private_key_pem.encode('utf-8'),
                    password=None
                )
                
                encrypted_aes_key = base64.b64decode(package['encrypted_key'].encode('utf-8'))
                aes_key = private_key.decrypt(
                    encrypted_aes_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
            else:
                # Fallback pour l'ancien format RSA direct
                if self.enable_skr_mode:
                    raise ValueError("Format de chiffrement legacy non supporté en mode SKR")
                return self._decrypt_legacy_rsa(encrypted_package)
            
            # Étape 4: Déchiffrer les données avec AES
            iv = base64.b64decode(package['iv'].encode('utf-8'))
            encrypted_data = base64.b64decode(package['encrypted_data'].encode('utf-8'))
            
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            
            padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # Étape 5: Supprimer le padding PKCS7
            padding_length = padded_data[-1]
            data = padded_data[:-padding_length]
            
            return data
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement hybride: {e}")
            raise
    
    def decrypt_data_legacy_for_migration(self, encrypted_package: str) -> bytes:
        """
        Déchiffre des données avec les anciens formats (UNIQUEMENT pour la migration)
        Cette méthode ignore temporairement le mode SKR pour permettre la migration des données
        
        Args:
            encrypted_package: Package chiffré encodé en base64
            
        Returns:
            bytes: Données déchiffrées
        """
        try:
            logger.warning("MIGRATION MODE: Déchiffrement legacy activé temporairement")
            
            # Sauvegarder l'état SKR actuel
            original_skr_mode = self.enable_skr_mode
            
            try:
                # Désactiver temporairement le mode SKR pour le déchiffrement
                self.enable_skr_mode = False
                
                # Étape 1: Décoder le package
                try:
                    package_json = base64.b64decode(encrypted_package.encode('utf-8')).decode('utf-8')
                    package = json.loads(package_json)
                    algorithm = package.get('algorithm')
                    
                    if algorithm == 'AES-256-CBC+RSA-OAEP':
                        # Déchiffrer avec format hybride standard
                        private_key_pem = self.get_private_key()
                        if not private_key_pem:
                            raise ValueError("Clé privée non disponible pour migration")
                        
                        private_key = load_pem_private_key(
                            private_key_pem.encode('utf-8'),
                            password=None
                        )
                        
                        encrypted_aes_key = base64.b64decode(package['encrypted_key'].encode('utf-8'))
                        aes_key = private_key.decrypt(
                            encrypted_aes_key,
                            padding.OAEP(
                                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                algorithm=hashes.SHA256(),
                                label=None
                            )
                        )
                        
                        # Déchiffrer les données avec AES
                        iv = base64.b64decode(package['iv'].encode('utf-8'))
                        encrypted_data = base64.b64decode(package['encrypted_data'].encode('utf-8'))
                        
                        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
                        decryptor = cipher.decryptor()
                        
                        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
                        
                        # Supprimer le padding PKCS7
                        padding_length = padded_data[-1]
                        data = padded_data[:-padding_length]
                        
                        logger.info("Migration: Déchiffrement hybride AES+RSA réussi")
                        return data
                    
                    else:
                        # Format non reconnu, essayer legacy RSA direct
                        return self._decrypt_legacy_rsa_for_migration(encrypted_package)
                        
                except (json.JSONDecodeError, KeyError):
                    # Pas un format JSON, essayer legacy RSA direct
                    logger.info("Migration: Format non-JSON détecté, tentative déchiffrement RSA direct")
                    return self._decrypt_legacy_rsa_for_migration(encrypted_package)
                    
            finally:
                # Restaurer l'état SKR original
                self.enable_skr_mode = original_skr_mode
                
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement legacy pour migration: {e}")
            raise
    
    def _decrypt_legacy_rsa_for_migration(self, encrypted_data: str) -> bytes:
        """
        Déchiffre des données avec l'ancien format RSA direct (UNIQUEMENT pour migration)
        
        Args:
            encrypted_data: Données chiffrées encodées en base64 (format RSA direct)
            
        Returns:
            bytes: Données déchiffrées
        """
        try:
            logger.info("Migration: Tentative de déchiffrement RSA direct legacy")
            
            private_key_pem = self.get_private_key()
            if not private_key_pem:
                raise ValueError("Clé privée non disponible pour migration RSA")
            
            private_key = load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None
            )
            
            # Décoder depuis base64
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            
            # Déchiffrer les données
            decrypted_data = private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            logger.info("Migration: Déchiffrement RSA direct réussi")
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement legacy RSA pour migration: {e}")
            raise
    
    def _decrypt_legacy_rsa(self, encrypted_data: str) -> bytes:
        """
        Déchiffre des données avec l'ancien format RSA direct (rétrocompatibilité)
        Non supporté en mode SKR pour des raisons de sécurité
        
        Args:
            encrypted_data: Données chiffrées encodées en base64 (format RSA direct)
            
        Returns:
            bytes: Données déchiffrées
        """
        try:
            if self.enable_skr_mode:
                raise ValueError("Déchiffrement legacy RSA non supporté en mode SKR - les données doivent être rechiffrées avec le format SKR")
            
            private_key_pem = self.get_private_key()
            if not private_key_pem:
                raise ValueError("Clé privée non disponible")
            
            private_key = load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None
            )
            
            # Décoder depuis base64
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            
            # Déchiffrer les données
            decrypted_data = private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return decrypted_data
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement legacy RSA: {e}")
            raise
    
    def ensure_keys_exist(self):
        """
        Vérifie que les clés existent dans Key Vault, les génère si nécessaire
        En mode SKR, seule la vérification est effectuée (pas de génération automatique)
        """
        try:
            if self.enable_skr_mode:
                # Mode SKR: Vérifier que les endpoints SKR sont configurés
                if not hasattr(self, 'skr_client') or not self.skr_client:
                    raise ValueError("Client SKR non configuré")
                
                # Vérifier la configuration SKR
                if not self.skr_maa_endpoint or not self.skr_keyvault_key_url:
                    raise ValueError("Endpoints SKR non configurés")
                
                logger.info("Configuration SKR vérifiée - endpoints MAA et Key Vault configurés")
                return
            
            # Mode standard: Vérifier et générer si nécessaire
            public_key = self.get_public_key()
            private_key = self.get_private_key()
            
            if not public_key or not private_key:
                logger.info("Clés manquantes, génération d'une nouvelle paire")
                self.generate_key_pair()
            else:
                logger.info("Clés de chiffrement disponibles dans Key Vault")
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des clés: {e}")
            raise
