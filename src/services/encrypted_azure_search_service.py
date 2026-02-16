"""
Service Azure AI Search avec support du chiffrement
Hérite du service de base et ajoute les capacités de chiffrement
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from azure.search.documents.models import VectorizedQuery
from .azure_search_service import AzureSearchService
from .ironcore_encryption_service import IroncoreEncryptionService
from .encryption_key_service import EncryptionKeyService

logger = logging.getLogger(__name__)

class EncryptedAzureSearchService(AzureSearchService):
    """Service Azure AI Search avec chiffrement des données"""
    
    def __init__(self, 
                 service_name: str, 
                 api_key: Optional[str] = None, 
                 index_name: str = None, 
                 vector_dimension: int = 768,
                 encryption_service: IroncoreEncryptionService = None,
                 key_service: EncryptionKeyService = None):
        """
        Initialise le service de recherche avec chiffrement
        
        Args:
            service_name: Nom du service Azure Search
            api_key: Clé API pour Azure Search (optionnel, utilise DefaultAzureCredential si non fourni)
            index_name: Nom de l'index de recherche
            vector_dimension: Dimension des vecteurs d'embedding
            encryption_service: Service de chiffrement IronCore
            key_service: Service de gestion des clés
        """
        # Initialiser le service de base
        super().__init__(service_name, api_key, index_name, vector_dimension)
        
        self.encryption_service = encryption_service
        self.key_service = key_service
        self._encryption_context = None
        
        logger.info("Service Azure Search chiffré initialisé")
        
        # Vérifier la disponibilité du chiffrement
        if not self.encryption_service.is_encryption_available():
            logger.warning("Service de chiffrement non disponible - fonctionnement en mode non-chiffré")
    
    def create_search_index(self):
        """
        Crée l'index de recherche avec support du chiffrement
        Étend l'index de base avec des champs chiffrés
        """
        # Obtenir l'index de base
        index = super().create_search_index()
        
        # Ajouter les champs pour le chiffrement
        from azure.search.documents.indexes.models import (
            SearchField, SearchFieldDataType, SimpleField, SearchableField
        )
        
        encrypted_fields = [
            # Contenu chiffré
            SearchableField(name="content_encrypted", type=SearchFieldDataType.String),
            SearchableField(name="title_encrypted", type=SearchFieldDataType.String),
            
            # Vecteur chiffré (Property-Preserving Encryption)
            SearchField(
                name="content_vector_encrypted",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.vector_dimension,
                vector_search_profile_name="encrypted-vector-profile"
            ),
            
            # Métadonnées de chiffrement
            SimpleField(name="encryption_context_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="encryption_status", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="encrypted_at", type=SearchFieldDataType.DateTimeOffset)
        ]
        
        # Ajouter les nouveaux champs à l'index
        index.fields.extend(encrypted_fields)
        
        # Ajouter un profil vectoriel pour les données chiffrées
        from azure.search.documents.indexes.models import VectorSearchProfile
        
        encrypted_vector_profile = VectorSearchProfile(
            name="encrypted-vector-profile",
            algorithm_configuration_name="hnsw-algorithm"
        )
        
        if hasattr(index.vector_search, 'profiles'):
            index.vector_search.profiles.append(encrypted_vector_profile)
        
        logger.info("Index de recherche configuré avec support du chiffrement")
        return index
    
    def get_search_context(self) -> Dict:
        """
        Retourne le contexte de chiffrement pour la recherche
        
        Returns:
            Dict: Contexte de chiffrement
        """
        if not self._encryption_context:
            self._encryption_context = self.key_service.get_search_encryption_context()
        return self._encryption_context
    
    async def encrypt_query_vector(self, vector: List[float], encryption_context: Dict) -> List[float]:
        """
        Chiffre un vecteur de requête avec le même contexte que les documents
        
        Args:
            vector: Vecteur de requête à chiffrer
            encryption_context: Contexte de chiffrement
            
        Returns:
            List[float]: Vecteur de requête chiffré
        """
        if not self.encryption_service.is_encryption_available():
            logger.debug("Chiffrement non disponible - retour du vecteur original")
            return vector
        
        return await self.encryption_service.encrypt_vector_with_key(vector, encryption_context)
    
    async def add_documents_encrypted(self, documents: List[Dict[str, Any]]):
        """
        Indexe des documents avec chiffrement
        
        Args:
            documents: Liste des documents à indexer avec chiffrement
        """
        if not self.encryption_service.is_encryption_available():
            logger.warning("Chiffrement non disponible - indexation normale")
            return super().add_documents(documents)

        try:
            # Obtenir le contexte de chiffrement pour ce batch
            encryption_context = self.get_search_context()
            
            encrypted_documents = []
            for i, doc in enumerate(documents):
                logger.info(f"Document ID: {doc.get('id', 'N/A')}")
                
                encrypted_doc = doc.copy()
                
                # Chiffrer le contenu textuel
                if "content" in doc:
                    original_content = doc["content"]
                    
                    encrypted_content = await self.encryption_service.encrypt_text_with_key(
                        original_content, encryption_context
                    )
                    encrypted_doc["content_encrypted"] = encrypted_content
                    # Ne pas stocker le contenu original non-chiffré
                    del encrypted_doc["content"]
                    
                if "title" in doc:
                    original_title = doc["title"]
                    
                    encrypted_title = await self.encryption_service.encrypt_text_with_key(
                        original_title, encryption_context
                    )
                    encrypted_doc["title_encrypted"] = encrypted_title
                    # Ne pas stocker le titre original non-chiffré
                    del encrypted_doc["title"]
                
                # Chiffrer le vecteur (Property-Preserving Encryption)
                if "content_vector" in doc:
                    original_vector = doc["content_vector"]
                    
                    encrypted_vector = await self.encryption_service.encrypt_vector_with_key(
                        original_vector, encryption_context
                    )
                    encrypted_doc["content_vector_encrypted"] = encrypted_vector
                    # Ne pas stocker le vecteur original non-chiffré
                    del encrypted_doc["content_vector"]
                
                # Ajouter les métadonnées de chiffrement
                encrypted_doc["encryption_context_id"] = encryption_context["context_id"]
                encrypted_doc["encryption_status"] = "encrypted"
                encrypted_doc["encrypted_at"] = datetime.utcnow().isoformat() + "Z"
                
                encrypted_documents.append(encrypted_doc)
            
            # Indexer les documents chiffrés
            super().add_documents(encrypted_documents)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation chiffrée: {e}")
            raise

    async def search_documents_encrypted(self, 
                                 query: str, 
                                 vector_query: Optional[List[float]] = None,
                                 top: int = 5,
                                 include_total_count: bool = True) -> Dict[str, Any]:
        """
        Recherche avec déchiffrement automatique des résultats
        
        Args:
            query: Requête de recherche textuelle
            vector_query: Vecteur de requête (déjà chiffré)
            top: Nombre de résultats à retourner
            include_total_count: Inclure le nombre total de résultats
            
        Returns:
            Dict: Résultats de recherche avec contenu déchiffré
        """
        if not self.encryption_service.is_encryption_available():
            logger.debug("Chiffrement non disponible - recherche normale")
            return super().search_documents(query, vector_query, top, include_total_count)
        
        try:
            # Paramètres de recherche sur données chiffrées
            search_params = {
                "search_text": query,  # Recherche textuelle sur métadonnées non-chiffrées
                "top": top,
                "include_total_count": include_total_count,
                "select": ["id", "content_encrypted", "title_encrypted", "file_id", 
                          "file_name", "chunk_index", "metadata", "encryption_context_id",
                          "encryption_status"]
            }
            
            # Recherche vectorielle sur données chiffrées
            if vector_query:  # Le vecteur est déjà chiffré par le caller
                vector_queries = [
                    VectorizedQuery(
                        vector=vector_query,  # Vecteur chiffré
                        k_nearest_neighbors=top,
                        fields="content_vector_encrypted"  # Champ vectoriel chiffré
                    )
                ]
                search_params["vector_queries"] = vector_queries
            
            # Debug simple : Payload AI Search Chiffré
            print(f"🔐 AI SEARCH ENCRYPTED CALL → Azure")
            print(f"📤 INPUT: {{'query': '{query}', 'top': {top}, 'has_encrypted_vector': {vector_query is not None}}}")
            
            # Exécuter la recherche
            raw_results = self.search_client.search(**search_params)
            
            # Déchiffrer les résultats pour l'affichage
            encryption_context = self.get_search_context()
            decrypted_results = {
                "results": [],
                "total_count": getattr(raw_results, 'get_count', lambda: 0)()
            }
            
            for result in raw_results:
                decrypted_result = {
                    "id": result.get("id"),
                    "file_id": result.get("file_id"),
                    "file_name": result.get("file_name"),
                    "chunk_index": result.get("chunk_index"),
                    "metadata": result.get("metadata"),
                    "score": result.get("@search.score", 0),
                    "encryption_status": result.get("encryption_status", "unknown")
                }
                
                # Déchiffrer le contenu pour l'affichage
                if result.get("content_encrypted"):
                    try:
                        decrypted_result["content"] = await self.encryption_service.decrypt_text_with_key(
                            result["content_encrypted"], encryption_context
                        )
                    except Exception as e:
                        logger.error(f"Erreur déchiffrement contenu: {e}")
                        decrypted_result["content"] = "[Erreur de déchiffrement]"
                        
                if result.get("title_encrypted"):
                    try:
                        decrypted_result["title"] = await self.encryption_service.decrypt_text_with_key(
                            result["title_encrypted"], encryption_context
                        )
                    except Exception as e:
                        logger.error(f"Erreur déchiffrement titre: {e}")
                        decrypted_result["title"] = "[Erreur de déchiffrement]"
                
                decrypted_results["results"].append(decrypted_result)
            
            # Debug simple : Réponse AI Search Chiffré
            print(f"📥 OUTPUT: {{'total_count': {decrypted_results['total_count']}, 'results': {len(decrypted_results['results'])} (décryptés)}}")
            
            return decrypted_results
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche chiffrée: {e}")
            raise
    
    def delete_documents_by_file_id(self, file_id: str):
        """
        Supprime tous les documents chiffrés associés à un fichier
        
        Args:
            file_id: ID du fichier dont supprimer les documents
        """
        try:
            # Rechercher tous les documents du fichier (chiffrés et non-chiffrés)
            results = self.search_client.search(
                search_text="*",
                filter=f"file_id eq '{file_id}'",
                select=["id"]
            )
            
            # Préparer la liste des documents à supprimer
            documents_to_delete = [{"@search.action": "delete", "id": result["id"]} for result in results]
            
            if documents_to_delete:
                self.search_client.upload_documents(documents_to_delete)
                logger.info(f"Supprimé {len(documents_to_delete)} documents chiffrés pour le fichier {file_id}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression des documents chiffrés pour le fichier {file_id}: {e}")
            raise
    
    def get_encryption_status(self) -> Dict[str, Any]:
        """
        Retourne le statut du chiffrement et des documents
        
        Returns:
            Dict: Informations sur l'état du chiffrement
        """
        try:
            # Compter les documents chiffrés vs non-chiffrés
            encrypted_count = 0
            unencrypted_count = 0
            
            results = self.search_client.search(
                search_text="*",
                select=["encryption_status"],
                top=1000  # Limité pour éviter la surcharge
            )
            
            for result in results:
                status = result.get("encryption_status", "unencrypted")
                if status == "encrypted":
                    encrypted_count += 1
                else:
                    unencrypted_count += 1
            
            return {
                "encryption_available": self.encryption_service.is_encryption_available(),
                "context_info": self.key_service.get_context_info(),
                "encryption_info": self.encryption_service.get_encryption_info(),
                "documents": {
                    "encrypted": encrypted_count,
                    "unencrypted": unencrypted_count,
                    "total": encrypted_count + unencrypted_count
                }
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du statut de chiffrement: {e}")
            return {
                "encryption_available": False,
                "error": str(e)
            }
