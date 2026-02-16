"""
Service Azure Document Intelligence pour l'extraction avancée de contenu
"""
import os
import base64
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from io import BytesIO
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
import json

logger = logging.getLogger(__name__)

class AzureDocIntelligenceService:
    """Service pour l'extraction de contenu avec Azure Document Intelligence"""
    
    def __init__(self, endpoint: str, api_key: str):
        """
        Initialise le service Azure Document Intelligence
        
        Args:
            endpoint: Endpoint du service Document Intelligence
            api_key: Clé API pour l'authentification
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key)
        )
        
        # Modèles disponibles pour différents types de documents
        self.available_models = {
            'prebuilt-read': 'Lecture générale de texte',
            'prebuilt-layout': 'Extraction de layout et structure',
            'prebuilt-document': 'Analyse de documents génériques',
            'prebuilt-invoice': 'Factures',
            'prebuilt-receipt': 'Reçus',
            'prebuilt-idDocument': 'Documents d\'identité',
            'prebuilt-businessCard': 'Cartes de visite'
        }
    
    def extract_content_from_file(self, 
                                file_content: bytes, 
                                filename: str,
                                model_id: str = 'prebuilt-layout') -> Dict[str, Any]:
        """
        Extrait le contenu d'un fichier en utilisant Azure Document Intelligence
        
        Args:
            file_content: Contenu du fichier en bytes
            filename: Nom du fichier (pour déterminer le type)
            model_id: ID du modèle à utiliser
            
        Returns:
            Dict: Contenu extrait avec métadonnées
        """
        try:
            logger.info(f"Extraction de contenu avec Document Intelligence: {filename}")
            
            # Utilisation de la syntaxe correcte pour azure-ai-documentintelligence 1.0.0
            # L'API attend un dictionnaire avec base64Source
            analyze_request = {
                "base64Source": base64.b64encode(file_content).decode('utf-8')
            }
            
            poller = self.client.begin_analyze_document(
                model_id=model_id,
                body=analyze_request
            )
            
            # Attendre le résultat avec retry et timeout plus long
            max_retries = 10
            retry_delay = 3 # secondes
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Tentative {attempt + 1}/{max_retries} - Attente des résultats...")
                    
                    # Attendre avec un timeout plus long pour les gros fichiers
                    result = poller.result(timeout=600)  # 600 secondes de timeout
                    
                    # Extraire le texte et les métadonnées
                    extracted_data = self._process_analysis_result(result, filename)
                    
                    logger.info(f"Extraction réussie: {len(extracted_data['content'])} caractères extraits")
                    return extracted_data
                    
                except HttpResponseError as e:
                    if "does not exist" in str(e) and attempt < max_retries - 1:
                        logger.warning(f"Résultat pas encore prêt, attente de {retry_delay} secondes... (tentative {attempt + 1})")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Augmenter le délai progressivement
                        continue
                    else:
                        raise
            
            # Si on arrive ici, toutes les tentatives ont échoué
            raise Exception(f"Impossible d'obtenir les résultats après {max_retries} tentatives")
            
        except HttpResponseError as e:
            logger.error(f"Erreur HTTP Document Intelligence: {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction: {e}")
            raise
            
        except HttpResponseError as e:
            logger.error(f"Erreur HTTP Document Intelligence: {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction: {e}")
            raise
    
    def _process_analysis_result(self, result: Any, filename: str) -> Dict[str, Any]:
        """
        Traite les résultats de l'analyse Document Intelligence
        
        Args:
            result: Résultat de l'analyse
            filename: Nom du fichier
            
        Returns:
            Dict: Données structurées extraites
        """
        extracted_data = {
            'content': '',
            'pages': [],
            'tables': [],
            'key_value_pairs': [],
            'entities': [],
            'metadata': {
                'filename': filename,
                'page_count': 0,
                'extraction_method': 'Azure Document Intelligence'
            }
        }
        
        # Extraire le contenu textuel
        if hasattr(result, 'content') and result.content:
            extracted_data['content'] = result.content
        
        # Traiter les pages
        if hasattr(result, 'pages') and result.pages:
            extracted_data['metadata']['page_count'] = len(result.pages)
            
            for page_idx, page in enumerate(result.pages):
                page_data = {
                    'page_number': page_idx + 1,
                    'width': getattr(page, 'width', 0),
                    'height': getattr(page, 'height', 0),
                    'unit': getattr(page, 'unit', 'pixel'),
                    'lines': [],
                    'words': []
                }
                
                # Extraire les lignes de texte
                if hasattr(page, 'lines') and page.lines:
                    for line in page.lines:
                        if hasattr(line, 'content'):
                            page_data['lines'].append({
                                'content': line.content,
                                'bounding_polygon': getattr(line, 'polygon', [])
                            })
                
                # Extraire les mots individuels
                if hasattr(page, 'words') and page.words:
                    for word in page.words:
                        if hasattr(word, 'content'):
                            page_data['words'].append({
                                'content': word.content,
                                'confidence': getattr(word, 'confidence', 0),
                                'bounding_polygon': getattr(word, 'polygon', [])
                            })
                
                extracted_data['pages'].append(page_data)
        
        # Traiter les tableaux
        if hasattr(result, 'tables') and result.tables:
            for table_idx, table in enumerate(result.tables):
                table_data = {
                    'table_id': table_idx,
                    'row_count': getattr(table, 'row_count', 0),
                    'column_count': getattr(table, 'column_count', 0),
                    'cells': []
                }
                
                if hasattr(table, 'cells') and table.cells:
                    for cell in table.cells:
                        cell_data = {
                            'content': getattr(cell, 'content', ''),
                            'row_index': getattr(cell, 'row_index', 0),
                            'column_index': getattr(cell, 'column_index', 0),
                            'row_span': getattr(cell, 'row_span', 1),
                            'column_span': getattr(cell, 'column_span', 1),
                            'kind': getattr(cell, 'kind', 'content')
                        }
                        table_data['cells'].append(cell_data)
                
                extracted_data['tables'].append(table_data)
        
        # Traiter les paires clé-valeur
        if hasattr(result, 'key_value_pairs') and result.key_value_pairs:
            for kvp in result.key_value_pairs:
                kvp_data = {
                    'key': getattr(kvp.key, 'content', '') if hasattr(kvp, 'key') and kvp.key else '',
                    'value': getattr(kvp.value, 'content', '') if hasattr(kvp, 'value') and kvp.value else '',
                    'confidence': getattr(kvp, 'confidence', 0)
                }
                extracted_data['key_value_pairs'].append(kvp_data)
        
        # Traiter les entités (si disponibles)
        if hasattr(result, 'entities') and result.entities:
            for entity in result.entities:
                entity_data = {
                    'content': getattr(entity, 'content', ''),
                    'category': getattr(entity, 'category', ''),
                    'subcategory': getattr(entity, 'subcategory', ''),
                    'confidence': getattr(entity, 'confidence', 0)
                }
                extracted_data['entities'].append(entity_data)
        
        return extracted_data
    
    def get_best_model_for_file(self, filename: str, file_content: bytes = None) -> str:
        """
        Détermine le meilleur modèle à utiliser pour un type de fichier
        
        Args:
            filename: Nom du fichier
            file_content: Contenu du fichier (optionnel, pour analyse plus poussée)
            
        Returns:
            str: ID du modèle recommandé
        """
        filename_lower = filename.lower()
        
        # Logique de sélection du modèle basée sur le nom de fichier et le contenu
        if any(keyword in filename_lower for keyword in ['facture', 'invoice', 'bill']):
            return 'prebuilt-invoice'
        elif any(keyword in filename_lower for keyword in ['recu', 'receipt', 'ticket']):
            return 'prebuilt-receipt'
        elif any(keyword in filename_lower for keyword in ['carte', 'card', 'business']):
            return 'prebuilt-businessCard'
        elif any(keyword in filename_lower for keyword in ['id', 'passport', 'license', 'permis']):
            return 'prebuilt-idDocument'
        else:
            # Modèle par défaut pour documents génériques avec layout
            return 'prebuilt-layout'
    
    def extract_structured_data(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Extraction spécialisée pour données structurées (tableaux, formulaires)
        
        Args:
            file_content: Contenu du fichier
            filename: Nom du fichier
            
        Returns:
            Dict: Données structurées extraites
        """
        try:
            # Utiliser le modèle layout pour une meilleure extraction de structure
            result = self.extract_content_from_file(
                file_content, 
                filename, 
                model_id='prebuilt-layout'
            )
            
            # Formatter les données pour une utilisation optimale en RAG
            structured_content = self._format_for_rag(result)
            
            return structured_content
            
        except Exception as e:
            logger.error(f"Erreur extraction données structurées: {e}")
            raise
    
    def _format_for_rag(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formate les données extraites pour une utilisation optimale en RAG
        
        Args:
            extracted_data: Données extraites brutes
            
        Returns:
            Dict: Données formatées pour RAG
        """
        # Texte principal
        main_content = extracted_data['content']
        
        # Enrichir avec les données structurées
        enriched_sections = []
        
        # Ajouter les tableaux comme sections spéciales
        for table_idx, table in enumerate(extracted_data['tables']):
            table_text = f"\n--- TABLEAU {table_idx + 1} ---\n"
            
            # Organiser les cellules par lignes
            rows = {}
            for cell in table['cells']:
                row_idx = cell['row_index']
                if row_idx not in rows:
                    rows[row_idx] = {}
                rows[row_idx][cell['column_index']] = cell['content']
            
            # Construire le texte du tableau
            for row_idx in sorted(rows.keys()):
                row_cells = []
                for col_idx in sorted(rows[row_idx].keys()):
                    row_cells.append(rows[row_idx][col_idx])
                table_text += " | ".join(row_cells) + "\n"
            
            enriched_sections.append(table_text)
        
        # Ajouter les paires clé-valeur
        if extracted_data['key_value_pairs']:
            kvp_text = "\n--- INFORMATIONS CLÉS ---\n"
            for kvp in extracted_data['key_value_pairs']:
                if kvp['key'] and kvp['value']:
                    kvp_text += f"{kvp['key']}: {kvp['value']}\n"
            enriched_sections.append(kvp_text)
        
        # Ajouter les entités
        if extracted_data['entities']:
            entities_text = "\n--- ENTITÉS DÉTECTÉES ---\n"
            for entity in extracted_data['entities']:
                entities_text += f"{entity['category']}: {entity['content']}\n"
            enriched_sections.append(entities_text)
        
        # Combiner tout le contenu
        final_content = main_content
        if enriched_sections:
            final_content += "\n\n" + "\n".join(enriched_sections)
        
        return {
            'content': final_content,
            'original_data': extracted_data,
            'metadata': {
                **extracted_data['metadata'],
                'has_tables': len(extracted_data['tables']) > 0,
                'has_key_value_pairs': len(extracted_data['key_value_pairs']) > 0,
                'has_entities': len(extracted_data['entities']) > 0
            }
        }
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Retourne les informations sur le service Document Intelligence
        
        Returns:
            Dict: Informations sur le service
        """
        return {
            'endpoint': self.endpoint,
            'available_models': self.available_models,
            'service_name': 'Azure Document Intelligence',
            'capabilities': [
                'Text extraction',
                'Layout analysis', 
                'Table extraction',
                'Key-value pairs',
                'Entity recognition',
                'Form processing'
            ]
        }
