"""
Service de stockage Azure pour la gestion des fichiers chiffrés
"""
import os
import uuid
from typing import Optional, Dict, Any
from azure.storage.blob import BlobServiceClient, BlobClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import logging
import mimetypes
from datetime import datetime

logger = logging.getLogger(__name__)

class AzureStorageService:
    """Service de gestion des fichiers dans Azure Storage"""
    
    def __init__(self, account_name: str, container_name: str, connection_string: Optional[str] = None):
        """
        Initialise le service de stockage Azure
        
        Args:
            account_name: Nom du compte de stockage Azure
            container_name: Nom du conteneur pour les fichiers chiffrés
            connection_string: Chaîne de connexion (optionnelle, pour compatibilité)
        """
        self.account_name = account_name
        self.container_name = container_name
        
        if not account_name or account_name == "None":
            logger.error(f"ERREUR: account_name invalide: {account_name}")
            raise ValueError("AZURE_STORAGE_ACCOUNT_NAME est requis et ne peut pas être None")
        
        self.account_url = f"https://{account_name}.blob.core.windows.net"
        
        # Configuration de l'authentification avec identités managées
        # Si AZURE_CLIENT_ID est défini, utiliser ManagedIdentityCredential avec ce client ID
        # Sinon, utiliser DefaultAzureCredential
        azure_client_id = os.getenv('AZURE_CLIENT_ID')
        
        if connection_string:
            # Mode compatibilité avec connection string
            logger.info("Utilisation de la connection string pour Azure Storage")
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        elif azure_client_id:
            logger.info(f"Utilisation de ManagedIdentityCredential pour Azure Storage avec client_id: {azure_client_id}")
            self.credential = ManagedIdentityCredential(client_id=azure_client_id)
            self.blob_service_client = BlobServiceClient(account_url=self.account_url, credential=self.credential)
        else:
            logger.info("Utilisation de DefaultAzureCredential pour Azure Storage")
            self.credential = DefaultAzureCredential()
            self.blob_service_client = BlobServiceClient(account_url=self.account_url, credential=self.credential)
        
        self.ensure_container_exists()
    
    def ensure_container_exists(self):
        """Crée le conteneur s'il n'existe pas"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Conteneur '{self.container_name}' créé")
            else:
                logger.info(f"Conteneur '{self.container_name}' existe déjà")
        except Exception as e:
            logger.error(f"Erreur lors de la création du conteneur: {e}")
            raise
    
    def upload_encrypted_file(self, 
                            encrypted_data: str, 
                            original_filename: str,
                            metadata: Optional[Dict[str, str]] = None,
                            file_id: Optional[str] = None) -> str:
        """
        Upload un fichier chiffré dans Azure Storage
        
        Args:
            encrypted_data: Données chiffrées (base64)
            original_filename: Nom de fichier original
            metadata: Métadonnées optionnelles
            file_id: ID unique du fichier (généré automatiquement si non fourni)
            
        Returns:
            str: ID unique du fichier stocké
        """
        try:
            # Utiliser l'ID fourni ou en générer un nouveau
            if file_id is None:
                file_id = str(uuid.uuid4())
            blob_name = f"{file_id}.encrypted"
            
            # Préparer les métadonnées
            blob_metadata = {
                'original_filename': original_filename,
                'upload_timestamp': datetime.utcnow().isoformat(),
                'content_type': mimetypes.guess_type(original_filename)[0] or 'application/octet-stream'
            }
            
            if metadata:
                blob_metadata.update(metadata)
            
            # Upload le fichier chiffré
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            blob_client.upload_blob(
                encrypted_data,
                overwrite=True,
                metadata=blob_metadata
            )
            
            logger.info(f"Fichier '{original_filename}' uploadé avec l'ID: {file_id}")
            return file_id
            
        except Exception as e:
            logger.error(f"Erreur lors de l'upload du fichier: {e}")
            raise
    
    def download_encrypted_file(self, file_id: str) -> tuple[str, Dict[str, str]]:
        """
        Télécharge un fichier chiffré depuis Azure Storage
        
        Args:
            file_id: ID unique du fichier
            
        Returns:
            tuple: (données chiffrées, métadonnées)
        """
        try:
            blob_name = f"{file_id}.encrypted"
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Télécharger les données et métadonnées
            blob_data = blob_client.download_blob()
            # Ne pas décoder en UTF-8 car les données chiffrées sont en base64
            encrypted_data = blob_data.readall().decode('utf-8')
            
            # Récupérer les métadonnées
            blob_properties = blob_client.get_blob_properties()
            metadata = blob_properties.metadata
            
            logger.info(f"Fichier téléchargé avec l'ID: {file_id}")
            return encrypted_data, metadata
            
        except Exception as e:
            logger.error(f"Erreur lors du téléchargement du fichier {file_id}: {e}")
            raise
    
    def delete_file(self, file_id: str) -> bool:
        """
        Supprime un fichier d'Azure Storage
        
        Args:
            file_id: ID unique du fichier
            
        Returns:
            bool: True si la suppression a réussi
        """
        try:
            blob_name = f"{file_id}.encrypted"
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            blob_client.delete_blob()
            logger.info(f"Fichier supprimé avec l'ID: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du fichier {file_id}: {e}")
            return False
    
    def file_exists(self, file_id: str) -> bool:
        """
        Vérifie si un fichier existe dans Azure Storage
        
        Args:
            file_id: ID unique du fichier
            
        Returns:
            bool: True si le fichier existe
        """
        try:
            blob_name = f"{file_id}.encrypted"
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            return blob_client.exists()
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de l'existence du fichier {file_id}: {e}")
            return False
    
    def list_files(self, prefix: Optional[str] = None) -> list[Dict[str, Any]]:
        """
        Liste les fichiers dans le conteneur
        
        Args:
            prefix: Préfixe optionnel pour filtrer les fichiers
            
        Returns:
            list: Liste des informations sur les fichiers
        """
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blobs = container_client.list_blobs(name_starts_with=prefix, include=['metadata'])
            
            files_info = []
            for blob in blobs:
                if blob.name.endswith('.encrypted'):
                    file_id = blob.name.replace('.encrypted', '')
                    file_info = {
                        'file_id': file_id,
                        'name': blob.name,
                        'size': blob.size,
                        'last_modified': blob.last_modified,
                        'metadata': blob.metadata or {}
                    }
                    files_info.append(file_info)
            
            return files_info
            
        except Exception as e:
            logger.error(f"Erreur lors de la liste des fichiers: {e}")
            raise
