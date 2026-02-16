"""
Service Azure AI Search pour la recherche vectorielle et l'indexation
"""
import os
import json
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField
)
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
import logging

logger = logging.getLogger(__name__)

class AzureSearchService:
    """Service pour la recherche vectorielle avec Azure AI Search"""
    
    def __init__(self, service_name: str, api_key: Optional[str] = None, index_name: str = None, vector_dimension: int = 768):
        """
        Initialise le service Azure AI Search
        
        Args:
            service_name: Nom du service Azure Search
            api_key: Clé API pour Azure Search (non utilisée - gardée pour compatibilité)
            index_name: Nom de l'index de recherche
            vector_dimension: Dimension des vecteurs d'embedding
        """
        self.service_name = service_name
        self.endpoint = f"https://{service_name}.search.windows.net"
        self.index_name = index_name
        self.vector_dimension = vector_dimension
        
        # Configuration de l'authentification avec identités managées uniquement
        # Si AZURE_CLIENT_ID est défini, utiliser ManagedIdentityCredential avec ce client ID
        # Sinon, utiliser DefaultAzureCredential
        azure_client_id = os.getenv('AZURE_CLIENT_ID')
        
        if azure_client_id:
            logger.info(f"Utilisation de ManagedIdentityCredential pour Azure AI Search avec client_id: {azure_client_id}")
            self.credential = ManagedIdentityCredential(client_id=azure_client_id)
        else:
            logger.info("Utilisation de DefaultAzureCredential pour Azure AI Search")
            self.credential = DefaultAzureCredential()
        
        # Clients Azure Search
        self.search_client = SearchClient(
            endpoint=self.endpoint,
            index_name=index_name,
            credential=self.credential
        )
        self.index_client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential
        )
        
        self.ensure_index_exists()
    
    def create_search_index(self) -> SearchIndex:
        """
        Crée l'index de recherche avec support vectoriel
        
        Returns:
            SearchIndex: L'index créé
        """
        # Configuration des champs
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SimpleField(name="file_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="file_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.vector_dimension,
                vector_search_profile_name="vector-profile"
            ),
            SimpleField(name="metadata", type=SearchFieldDataType.String),
            SimpleField(name="timestamp", type=SearchFieldDataType.DateTimeOffset)
        ]
        
        # Configuration de la recherche vectorielle
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name="hnsw-algorithm")
            ],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-algorithm"
                )
            ]
        )
        
        # Configuration sémantique
        semantic_config = SemanticConfiguration(
            name="semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")]
            )
        )
        
        semantic_search = SemanticSearch(
            configurations=[semantic_config]
        )
        
        # Créer l'index
        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        return index
    
    def ensure_index_exists(self):
        """Crée l'index s'il n'existe pas"""
        try:
            # Vérifier si l'index existe
            try:
                self.index_client.get_index(self.index_name)
                logger.info(f"Index '{self.index_name}' existe déjà")
            except:
                # L'index n'existe pas, le créer
                index = self.create_search_index()
                self.index_client.create_index(index)
                logger.info(f"Index '{self.index_name}' créé avec succès")
                
        except Exception as e:
            logger.error(f"Erreur lors de la gestion de l'index: {e}")
            raise
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Ajoute des documents à l'index
        
        Args:
            documents: Liste des documents à indexer
        """
        try:
            result = self.search_client.upload_documents(documents)
            
            successful = sum(1 for r in result if r.succeeded)
            failed = len(result) - successful
            
            logger.info(f"Documents indexés: {successful} réussis, {failed} échoués")
            
            if failed > 0:
                for r in result:
                    if not r.succeeded:
                        logger.error(f"Erreur d'indexation pour le document {r.key}: {r.error_message}")
                        
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout des documents: {e}")
            raise
    
    def search_documents(self, 
                        query: str, 
                        vector_query: Optional[List[float]] = None,
                        top: int = 5,
                        include_total_count: bool = True) -> Dict[str, Any]:
        """
        Recherche des documents dans l'index
        
        Args:
            query: Requête de recherche textuelle
            vector_query: Vecteur de requête pour la recherche vectorielle
            top: Nombre de résultats à retourner
            include_total_count: Inclure le nombre total de résultats
            
        Returns:
            Dict: Résultats de la recherche
        """
        try:
            search_params = {
                "search_text": query,
                "top": top,
                "include_total_count": include_total_count,
                "select": ["id", "content", "title", "file_id", "file_name", "chunk_index", "metadata"]
            }
            
            # Ajouter la recherche vectorielle si un vecteur est fourni
            if vector_query:
                vector_queries = [
                    VectorizedQuery(
                        vector=vector_query,
                        k_nearest_neighbors=top,
                        fields="content_vector"
                    )
                ]
                search_params["vector_queries"] = vector_queries
            
            # Debug simple : Payload AI Search
            print(f"🔍 AI SEARCH CALL → Azure")
            print(f"📤 INPUT: {{'query': '{query}', 'top': {top}, 'has_vector': {vector_query is not None}}}")
            
            results = self.search_client.search(**search_params)
            
            # Convertir les résultats en format dict
            search_results = {
                "results": [],
                "total_count": getattr(results, 'get_count', lambda: 0)()
            }
            
            for result in results:
                search_results["results"].append({
                    "id": result.get("id"),
                    "content": result.get("content"),
                    "title": result.get("title"),
                    "file_id": result.get("file_id"),
                    "file_name": result.get("file_name"),
                    "chunk_index": result.get("chunk_index"),
                    "metadata": result.get("metadata"),
                    "score": result.get("@search.score", 0)
                })
            
            # Debug simple : Réponse AI Search
            print(f"📥 OUTPUT: {{'total_count': {search_results['total_count']}, 'results': {len(search_results['results'])}}}")
            
            logger.info(f"Recherche effectuée: {len(search_results['results'])} résultats trouvés")
            return search_results
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            raise
    
    def delete_documents_by_file_id(self, file_id: str):
        """
        Supprime tous les documents associés à un fichier
        
        Args:
            file_id: ID du fichier dont supprimer les documents
        """
        try:
            # Rechercher tous les documents du fichier
            results = self.search_client.search(
                search_text="*",
                filter=f"file_id eq '{file_id}'",
                select=["id"]
            )
            
            # Préparer la liste des documents à supprimer
            documents_to_delete = [{"@search.action": "delete", "id": result["id"]} for result in results]
            
            if documents_to_delete:
                self.search_client.upload_documents(documents_to_delete)
                logger.info(f"Supprimé {len(documents_to_delete)} documents pour le fichier {file_id}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression des documents pour le fichier {file_id}: {e}")
            raise
    
    def get_document_count(self) -> int:
        """
        Retourne le nombre total de documents dans l'index
        
        Returns:
            int: Nombre de documents
        """
        try:
            results = self.search_client.search(
                search_text="*",
                include_total_count=True,
                top=0
            )
            return results.get_count()
            
        except Exception as e:
            logger.error(f"Erreur lors du comptage des documents: {e}")
            return 0
