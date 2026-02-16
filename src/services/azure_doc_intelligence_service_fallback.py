"""
Service Azure Document Intelligence simplifié - Version de fallback
"""
import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from io import BytesIO
import json

logger = logging.getLogger(__name__)

class AzureDocIntelligenceService:
    """Service pour l'extraction de contenu - Version simplifiée de fallback"""
    
    def __init__(self, endpoint: str, api_key: str):
        """
        Initialise le service (version fallback sans Azure Document Intelligence)
        
        Args:
            endpoint: Endpoint du service (non utilisé en mode fallback)
            api_key: Clé API (non utilisée en mode fallback)
        """
        self.endpoint = endpoint
        self.api_key = api_key
        logger.warning("Azure Document Intelligence désactivé - utilisation du mode fallback")
        
        # Modèles disponibles (pour compatibilité)
        self.available_models = {
            'prebuilt-read': 'Lecture générale de texte (fallback)',
            'prebuilt-layout': 'Extraction de layout et structure (fallback)',
            'prebuilt-document': 'Analyse de documents génériques (fallback)'
        }
    
    def extract_content_from_file(self, 
                                file_content: bytes, 
                                filename: str,
                                model_id: str = 'prebuilt-layout') -> Dict[str, Any]:
        """
        Extrait le contenu d'un fichier (version fallback)
        
        Args:
            file_content: Contenu du fichier en bytes
            filename: Nom du fichier
            model_id: ID du modèle (ignoré en mode fallback)
            
        Returns:
            Dict: Contenu extrait basique
        """
        try:
            logger.info(f"Extraction en mode fallback pour: {filename}")
            
            # Extraction basique - retourne une structure vide mais valide
            extracted_data = {
                'content': f"Contenu extrait en mode fallback pour {filename}\n(Azure Document Intelligence non disponible)",
                'pages': [],
                'tables': [],
                'key_value_pairs': [],
                'entities': [],
                'metadata': {
                    'filename': filename,
                    'page_count': 1,
                    'extraction_method': 'Fallback (Azure Doc Intelligence désactivé)'
                }
            }
            
            logger.info(f"Extraction fallback terminée: {len(extracted_data['content'])} caractères")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction fallback: {e}")
            raise
    
    def get_best_model_for_file(self, filename: str, file_content: bytes = None) -> str:
        """
        Détermine le meilleur modèle (version fallback)
        
        Args:
            filename: Nom du fichier
            file_content: Contenu du fichier (optionnel)
            
        Returns:
            str: ID du modèle (toujours layout en fallback)
        """
        return 'prebuilt-layout'
    
    def extract_structured_data(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extraction spécialisée pour données structurées (version fallback)
        
        Args:
            file_content: Contenu du fichier
            filename: Nom du fichier
            
        Returns:
            Dict: Données structurées basiques
        """
        try:
            result = self.extract_content_from_file(file_content, filename)
            structured_content = self._format_for_rag(result)
            return structured_content
            
        except Exception as e:
            logger.error(f"Erreur extraction données structurées fallback: {e}")
            raise
    
    def _format_for_rag(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formate les données extraites pour une utilisation optimale en RAG
        
        Args:
            extracted_data: Données extraites
            
        Returns:
            Dict: Données formatées pour RAG
        """
        return {
            'content': extracted_data['content'],
            'original_data': extracted_data,
            'metadata': {
                **extracted_data['metadata'],
                'has_tables': False,
                'has_key_value_pairs': False,
                'has_entities': False
            }
        }
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Retourne les informations sur le service (version fallback)
        
        Returns:
            Dict: Informations sur le service
        """
        return {
            'endpoint': self.endpoint,
            'available_models': self.available_models,
            'service_name': 'Azure Document Intelligence (Fallback)',
            'capabilities': [
                'Basic text extraction',
                'Fallback mode active'
            ],
            'status': 'fallback_mode'
        }
