"""
Service de traitement des documents pour l'indexation RAG
Utilise Azure Document Intelligence pour l'extraction avancée de contenu
"""
import os
import uuid
from typing import List, Dict, Any, Optional
import mimetypes
from datetime import datetime
import logging
from io import BytesIO
import PyPDF2
import docx
from docx import Document
import json
from .azure_doc_intelligence_service import AzureDocIntelligenceService
from .smart_chunker import SmartChunker
from ..config import Config

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Service pour le traitement et la segmentation des documents"""
    
    def __init__(self, 
                 chunk_size: int = 1000, 
                 chunk_overlap: int = 200,
                 doc_intelligence_endpoint: str = None,
                 doc_intelligence_api_key: str = None,
                 use_azure_doc_intelligence: bool = True,
                 use_encryption: bool = False,
                 search_service=None,
                 encrypted_search_service=None,
                 use_smart_chunking: bool = True,
                 smart_chunk_target_size: int = 400,
                 smart_chunk_max_size: int = 600,
                 smart_chunk_overlap: int = 80):
        """
        Initialise le processeur de documents
        
        Args:
            chunk_size: Taille des chunks en caractères (utilisé si smart chunking désactivé)
            chunk_overlap: Chevauchement entre les chunks (utilisé si smart chunking désactivé)
            doc_intelligence_endpoint: Endpoint Azure Document Intelligence
            doc_intelligence_api_key: Clé API Document Intelligence
            use_azure_doc_intelligence: Utiliser Azure Document Intelligence si disponible
            use_encryption: Utiliser le chiffrement pour l'indexation
            search_service: Service de recherche normal
            encrypted_search_service: Service de recherche chiffré
            use_smart_chunking: Activer le chunking intelligent
            smart_chunk_target_size: Taille cible pour le chunking intelligent
            smart_chunk_max_size: Taille maximale pour le chunking intelligent
            smart_chunk_overlap: Chevauchement pour le chunking intelligent
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_azure_doc_intelligence = use_azure_doc_intelligence
        self.use_encryption = use_encryption
        self.use_smart_chunking = use_smart_chunking
        
        # Configuration des services de recherche
        if use_encryption and encrypted_search_service:
            self.search_service = encrypted_search_service
            logger.info("DocumentProcessor configuré avec chiffrement")
        elif search_service:
            self.search_service = search_service
            logger.info("DocumentProcessor configuré sans chiffrement")
        else:
            self.search_service = None
            logger.warning("Aucun service de recherche configuré")
        
        # Debug des paramètres
        logger.info(f"=== INIT DocumentProcessor ===")
        logger.info(f"use_encryption paramètre: {use_encryption}")
        logger.info(f"self.use_encryption: {self.use_encryption}")
        logger.info(f"encrypted_search_service fourni: {encrypted_search_service is not None}")
        logger.info(f"search_service fourni: {search_service is not None}")
        logger.info(f"Type du service final: {type(self.search_service)}")
        
        # Initialiser le Smart Chunker si activé
        if self.use_smart_chunking:
            self.smart_chunker = SmartChunker(
                target_chunk_size=smart_chunk_target_size,
                max_chunk_size=smart_chunk_max_size,
                overlap_size=smart_chunk_overlap,
                strategy="smart",
                table_strategy=getattr(Config, 'TABLE_CHUNKING_STRATEGY', 'preserve_structure'),
                table_max_rows_per_chunk=getattr(Config, 'TABLE_MAX_ROWS_PER_CHUNK', 10),
                table_always_include_headers=getattr(Config, 'TABLE_ALWAYS_INCLUDE_HEADERS', True),
                table_semantic_grouping=getattr(Config, 'TABLE_SEMANTIC_GROUPING', True),
                table_column_chunking=getattr(Config, 'TABLE_COLUMN_CHUNKING', False)
            )
            logger.info(f"Smart Chunker activé - Taille cible: {smart_chunk_target_size}, Max: {smart_chunk_max_size}, Overlap: {smart_chunk_overlap}")
            logger.info(f"Configuration tableaux: stratégie={getattr(Config, 'TABLE_CHUNKING_STRATEGY', 'preserve_structure')}, max_rows={getattr(Config, 'TABLE_MAX_ROWS_PER_CHUNK', 10)}")
        else:
            self.smart_chunker = None
            logger.info(f"Chunking classique activé - Taille: {chunk_size}, Overlap: {chunk_overlap}")
        logger.info(f"=== FIN INIT ===")
        
        # Initialiser Azure Document Intelligence si configuré
        self.doc_intelligence_service = None
        if (use_azure_doc_intelligence and 
            doc_intelligence_endpoint and 
            doc_intelligence_api_key):
            try:
                self.doc_intelligence_service = AzureDocIntelligenceService(
                    doc_intelligence_endpoint,
                    doc_intelligence_api_key
                )
                logger.info("Azure Document Intelligence initialisé avec succès")
            except Exception as e:
                logger.warning(f"Impossible d'initialiser Azure Document Intelligence: {e}")
                logger.info("Utilisation des méthodes d'extraction de fallback")
        
        # Types de fichiers supportés avec méthodes de fallback
        self.supported_types = {
            'application/pdf': self._extract_pdf_text,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': self._extract_docx_text,
            'text/plain': self._extract_txt_text,
            'application/json': self._extract_json_text
        }
    
    def process_file(self, file_content: bytes, filename: str, file_id: str) -> Dict[str, Any]:
        """
        Traite un fichier et extrait son contenu
        
        Args:
            file_content: Contenu du fichier en bytes
            filename: Nom du fichier
            file_id: ID unique du fichier
            
        Returns:
            Dict: Informations sur le fichier traité
        """
        try:
            # Déterminer le type MIME
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            logger.info(f"Traitement du fichier: {filename} (Type: {mime_type})")
            
            # Vérifier si le type est supporté
            if mime_type not in self.supported_types:
                raise ValueError(f"Type de fichier non supporté: {mime_type}")
            
            # Essayer d'abord Azure Document Intelligence si disponible
            text_content = ""
            extraction_method = "fallback"
            additional_metadata = {}
            
            if self.doc_intelligence_service and self._should_use_doc_intelligence(mime_type):
                try:
                    logger.info("Utilisation d'Azure Document Intelligence pour l'extraction")
                    doc_intel_result = self.doc_intelligence_service.extract_structured_data(
                        file_content, filename
                    )
                    text_content = doc_intel_result['content']
                    extraction_method = "Azure Document Intelligence"
                    additional_metadata = doc_intel_result['metadata']
                    
                    logger.info(f"Extraction réussie avec Document Intelligence: {len(text_content)} caractères")
                    
                except Exception as e:
                    logger.warning(f"Erreur avec Document Intelligence, utilisation du fallback: {e}")
                    text_content = self.supported_types[mime_type](file_content)
                    extraction_method = "fallback"
            else:
                # Utiliser les méthodes de fallback
                text_content = self.supported_types[mime_type](file_content)
                extraction_method = "fallback"
            
            # Segmenter le texte en chunks avec chunking intelligent
            chunks = self._create_chunks(text_content, filename)
            
            # Créer les métadonnées
            metadata = {
                'file_id': file_id,
                'filename': filename,
                'mime_type': mime_type,
                'size': len(file_content),
                'text_length': len(text_content),
                'chunks_count': len(chunks),
                'processed_at': datetime.utcnow().isoformat(),
                'extraction_method': extraction_method,
                **additional_metadata
            }
            
            return {
                'metadata': metadata,
                'text_content': text_content,
                'chunks': chunks
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du fichier {filename}: {e}")
            raise
    
    def _should_use_doc_intelligence(self, mime_type: str) -> bool:
        """
        Détermine si Azure Document Intelligence doit être utilisé pour ce type de fichier
        
        Args:
            mime_type: Type MIME du fichier
            
        Returns:
            bool: True si Document Intelligence doit être utilisé
        """
        # Document Intelligence est particulièrement efficace pour ces types
        preferred_types = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg',
            'image/png',
            'image/tiff',
            'image/bmp'
        }
        return mime_type in preferred_types
    
    def _extract_pdf_text(self, file_content: bytes) -> str:
        """Extrait le texte d'un fichier PDF"""
        try:
            # Vérifier que le contenu commence bien par un marqueur PDF
            if not file_content.startswith(b'%PDF'):
                logger.error(f"Le fichier ne semble pas être un PDF valide. Début: {file_content[:20]}")
                raise ValueError("Le fichier ne semble pas être un PDF valide")
            
            pdf_file = BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            logger.info(f"Lecture PDF - Nombre de pages: {len(pdf_reader.pages)}")
            
            text_parts = []
            for i, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    logger.info(f"Page {i+1}: {len(page_text)} caractères extraits")
                    if page_text.strip():  # Seulement ajouter si la page a du contenu
                        text_parts.append(page_text)
                except Exception as e:
                    logger.warning(f"Erreur extraction page {i+1}: {e}")
                    continue
            
            extracted_text = "\n".join(text_parts)
            logger.info(f"Extraction PDF terminée - Total: {len(extracted_text)} caractères")
            
            if not extracted_text.strip():
                logger.warning("Aucun texte extrait du PDF - le fichier pourrait être une image ou protégé")
                return ""
            
            return extracted_text
            
        except PyPDF2.errors.PdfReadError as e:
            logger.error(f"Erreur PDF spécifique: {e}")
            raise ValueError(f"PDF corrompu ou non valide: {e}")
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction PDF: {e}")
            raise
    
    def _extract_docx_text(self, file_content: bytes) -> str:
        """Extrait le texte d'un fichier Word"""
        try:
            docx_file = BytesIO(file_content)
            doc = Document(docx_file)
            
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction DOCX: {e}")
            raise
    
    def _extract_txt_text(self, file_content: bytes) -> str:
        """Extrait le texte d'un fichier texte"""
        try:
            # Essayer différents encodages
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    return file_content.decode(encoding)
                except UnicodeDecodeError:
                    continue
            
            # Si aucun encodage ne fonctionne, utiliser utf-8 avec des erreurs ignorées
            return file_content.decode('utf-8', errors='ignore')
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction TXT: {e}")
            raise
    
    def _extract_json_text(self, file_content: bytes) -> str:
        """Extrait le contenu d'un fichier JSON"""
        try:
            json_content = json.loads(file_content.decode('utf-8'))
            return self._json_to_text(json_content)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction JSON: {e}")
            raise
    
    def _json_to_text(self, json_obj: Any, prefix: str = "") -> str:
        """Convertit un objet JSON en texte lisible"""
        text_parts = []
        
        if isinstance(json_obj, dict):
            for key, value in json_obj.items():
                if isinstance(value, (dict, list)):
                    text_parts.append(f"{prefix}{key}:")
                    text_parts.append(self._json_to_text(value, prefix + "  "))
                else:
                    text_parts.append(f"{prefix}{key}: {value}")
        elif isinstance(json_obj, list):
            for i, item in enumerate(json_obj):
                text_parts.append(f"{prefix}[{i}]:")
                text_parts.append(self._json_to_text(item, prefix + "  "))
        else:
            text_parts.append(f"{prefix}{json_obj}")
        
        return "\n".join(text_parts)
    
    def _create_chunks(self, text: str, filename: str = None) -> List[Dict[str, Any]]:
        """
        Divise le texte en chunks (intelligent ou classique selon la configuration)
        
        Args:
            text: Texte à diviser
            filename: Nom du fichier pour détecter le type (optionnel)
            
        Returns:
            List[Dict]: Liste des chunks avec métadonnées
        """
        if not text or not text.strip():
            return []
        
        # Nettoyer le texte
        text = text.strip()
        
        # Utiliser le chunking intelligent si activé
        if self.use_smart_chunking and self.smart_chunker:
            return self._create_smart_chunks(text, filename)
        else:
            return self._create_simple_chunks(text)
    
    def _create_smart_chunks(self, text: str, filename: str = None) -> List[Dict[str, Any]]:
        """
        Divise le texte en chunks avec chunking intelligent
        
        Args:
            text: Texte à diviser
            filename: Nom du fichier pour détecter le type (optionnel)
            
        Returns:
            List[Dict]: Liste des chunks avec métadonnées enrichies
        """
        logger.info(f"Chunking intelligent du texte ({len(text)} caractères)")
        
        # Détecter le type de document basé sur le nom de fichier
        document_type = self._detect_document_type_from_filename(filename) if filename else "auto"
        
        # Utiliser le smart chunker
        smart_chunks = self.smart_chunker.create_chunks(text, document_type)
        
        # Recalculer les positions dans le texte original pour compatibilité
        search_start = 0
        processed_chunks = []
        
        for i, chunk in enumerate(smart_chunks):
            chunk_text = chunk['text']
            
            # Trouver la position dans le texte original
            position = text.find(chunk_text, search_start)
            
            if position != -1:
                start_pos = position
                end_pos = position + len(chunk_text)
                search_start = position + len(chunk_text)
            else:
                # Si on ne trouve pas exactement, utiliser une approximation
                start_pos = search_start
                end_pos = search_start + len(chunk_text)
                search_start += len(chunk_text)
            
            # Créer le chunk avec métadonnées enrichies
            processed_chunk = {
                'index': i,
                'text': chunk_text,
                'start_pos': start_pos,
                'end_pos': end_pos,
                'length': len(chunk_text),
                'chunk_type': chunk.get('chunk_type', 'unknown'),
                'quality_score': chunk.get('quality_score', 1.0)
            }
            processed_chunks.append(processed_chunk)
        
        # Statistiques de chunking
        stats = self.smart_chunker.get_chunking_stats(smart_chunks)
        logger.info(f"Chunking intelligent terminé: {stats['total_chunks']} chunks, "
                   f"qualité moyenne: {stats['average_quality']:.2f}, "
                   f"types: {stats['chunks_by_type']}")
        
        return processed_chunks
    
    def _create_simple_chunks(self, text: str) -> List[Dict[str, Any]]:
        """
        Divise le texte en chunks classiques (par taille de caractères)
        
        Args:
            text: Texte à diviser
            
        Returns:
            List[Dict]: Liste des chunks
        """
        logger.info(f"Chunking classique du texte ({len(text)} caractères)")
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Fin du chunk
            end = start + self.chunk_size
            
            # Si on n'est pas à la fin du texte, essayer de couper à un espace
            if end < len(text):
                # Chercher le dernier espace avant la limite
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:  # Ignorer les chunks vides
                chunk = {
                    'index': chunk_index,
                    'text': chunk_text,
                    'start_pos': start,
                    'end_pos': end,
                    'length': len(chunk_text),
                    'chunk_type': 'simple',
                    'quality_score': 1.0
                }
                chunks.append(chunk)
                chunk_index += 1
            
            # Déplacer le début avec chevauchement
            start = end - self.chunk_overlap if self.chunk_overlap > 0 else end
        
        logger.info(f"Chunking classique terminé: {len(chunks)} chunks")
        return chunks
    
    def _detect_document_type_from_filename(self, filename: str) -> str:
        """
        Détecte le type de document basé sur le nom de fichier
        
        Args:
            filename: Nom du fichier
            
        Returns:
            str: Type de document détecté
        """
        if not filename:
            return "auto"
        
        filename_lower = filename.lower()
        
        # Mots-clés pour détecter les types de documents
        if any(keyword in filename_lower for keyword in 
               ['contrat', 'contract', 'legal', 'terme', 'condition', 'policy', 'politique', 
                'agreement', 'accord', 'clause', 'article']):
            return "legal"
        elif any(keyword in filename_lower for keyword in 
                 ['manual', 'guide', 'spec', 'specification', 'documentation', 'readme', 
                  'technique', 'technical', 'procedure', 'mode_emploi']):
            return "technical"
        elif any(keyword in filename_lower for keyword in 
                 ['.py', '.js', '.java', '.cpp', '.cs', '.php', '.rb', '.go']):
            return "code"
        elif any(keyword in filename_lower for keyword in 
                 ['handbook', 'manuel', 'employee', 'employe', 'story', 'narrative', 'rapport', 'report']):
            return "narrative"
        else:
            return "auto"
    
    def create_search_documents(self, 
                              processed_file: Dict[str, Any], 
                              embeddings: List[List[float]]) -> List[Dict[str, Any]]:
        """
        Crée les documents pour l'indexation dans Azure Search
        
        Args:
            processed_file: Fichier traité
            embeddings: Embeddings des chunks
            
        Returns:
            List[Dict]: Documents prêts pour l'indexation
        """
        try:
            documents = []
            metadata = processed_file['metadata']
            chunks = processed_file['chunks']
            
            if len(chunks) != len(embeddings):
                raise ValueError("Le nombre de chunks ne correspond pas au nombre d'embeddings")
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                doc_id = f"{metadata['file_id']}_chunk_{i}"
                
                document = {
                    'id': doc_id,
                    'content': chunk['text'],
                    'title': metadata['filename'],
                    'file_id': metadata['file_id'],
                    'file_name': metadata['filename'],
                    'chunk_index': i,
                    'content_vector': embedding,
                    'metadata': json.dumps({
                        'mime_type': metadata['mime_type'],
                        'chunk_start': chunk['start_pos'],
                        'chunk_end': chunk['end_pos'],
                        'processed_at': metadata['processed_at']
                    }),
                    'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                }
                
                documents.append(document)
            
            logger.info(f"Créé {len(documents)} documents pour l'indexation")
            return documents
            
        except Exception as e:
            logger.error(f"Erreur lors de la création des documents de recherche: {e}")
            raise
    
    def get_supported_formats(self) -> List[str]:
        """
        Retourne la liste des formats de fichiers supportés
        
        Returns:
            List[str]: Liste des types MIME supportés
        """
        return list(self.supported_types.keys())
    
    async def process_and_index_document(self, 
                                 file_id: str, 
                                 content: str, 
                                 metadata: Dict[str, Any],
                                 embedding_service) -> Dict[str, Any]:
        """
        Traite et indexe un document avec chiffrement conditionnel
        
        Args:
            file_id: ID du fichier
            content: Contenu du document
            metadata: Métadonnées du document
            embedding_service: Service d'embeddings
            
        Returns:
            Dict: Résultat de l'indexation
        """
        try:
            if not self.search_service:
                raise ValueError("Service de recherche non configuré")
            
            logger.info(f"Traitement et indexation du document {file_id}")
            logger.info(f"Mode chiffrement: {'activé' if self.use_encryption else 'désactivé'}")
            logger.info(f"Contenu du document - Longueur: {len(content)} caractères")
            logger.info(f"Contenu du document - Premiers 200 chars: {content[:200]}")
            
            # Vérifier que le contenu n'est pas vide
            if not content or len(content.strip()) == 0:
                logger.error("Le contenu du document est vide - impossible de créer des chunks")
                return {
                    "success": False,
                    "file_id": file_id,
                    "error": "Le contenu du document est vide - aucun texte extrait",
                    "encryption_used": self.use_encryption
                }
            
            # 1. Segmentation du document avec chunking intelligent
            filename = metadata.get('filename', None)
            chunks = self._create_chunks(content, filename)
            logger.info(f"Document segmenté en {len(chunks)} chunks")
            
            # Vérifier qu'il y a des chunks
            if len(chunks) == 0:
                logger.error("Aucun chunk créé - le texte est probablement trop court ou invalide")
                return {
                    "success": False,
                    "file_id": file_id,
                    "error": "Aucun chunk créé - le texte est trop court ou invalide",
                    "encryption_used": self.use_encryption
                }
            
            # 2. Génération des embeddings et préparation des documents
            documents = []
            for i, chunk in enumerate(chunks):
                # Extraire le texte du chunk
                chunk_text = chunk['text']
                logger.info(f"Chunk {i}: {len(chunk_text)} caractères")
                
                # Générer l'embedding pour ce chunk
                embedding = embedding_service.generate_embedding(chunk_text)
                
                doc = {
                    "id": f"{file_id}_{i}",
                    "content": chunk_text,
                    "title": metadata.get("filename", ""),
                    "file_id": file_id,
                    "file_name": metadata.get("filename", ""),
                    "chunk_index": i,
                    "content_vector": embedding,
                    "metadata": json.dumps(metadata),
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                documents.append(doc)
            
            logger.info(f"Créé {len(documents)} documents pour l'indexation")
            
            # Vérifier qu'il y a des documents à indexer
            if len(documents) == 0:
                logger.error("Aucun document créé pour l'indexation")
                return {
                    "success": False,
                    "file_id": file_id,
                    "error": "Aucun document créé pour l'indexation",
                    "encryption_used": self.use_encryption
                }
            
            # 3. Indexation (chiffrée ou normale selon la configuration)
            if self.use_encryption:
                logger.info("=== DEBUG CHIFFREMENT ===")
                logger.info(f"use_encryption: {self.use_encryption}")
                logger.info(f"Type du service de recherche: {type(self.search_service)}")
                logger.info(f"Service a add_documents_encrypted: {hasattr(self.search_service, 'add_documents_encrypted')}")
                
                # Afficher un échantillon du premier document avant chiffrement
                if documents:
                    sample_doc = documents[0]
                    logger.info(f"=== DOCUMENT AVANT CHIFFREMENT ===")
                    logger.info(f"ID: {sample_doc.get('id', 'N/A')}")
                    logger.info(f"Content (50 premiers chars): {str(sample_doc.get('content', ''))[:50]}...")
                    logger.info(f"Vector (5 premiers éléments): {sample_doc.get('content_vector', [])[:5]}")
                
                # Le service est EncryptedAzureSearchService, utiliser la méthode chiffrée
                if hasattr(self.search_service, 'add_documents_encrypted'):
                    logger.info("Appel de add_documents_encrypted()")
                    await self.search_service.add_documents_encrypted(documents)
                else:
                    logger.error("Service de recherche ne supporte pas le chiffrement")
                    raise Exception("Service de recherche configuré sans support chiffrement")
            else:
                logger.info("Indexation normale")
                self.search_service.add_documents(documents)
            
            result = {
                "success": True,
                "file_id": file_id,
                "chunks_count": len(chunks),
                "encryption_used": self.use_encryption,
                "indexed_documents": len(documents)
            }
            
            logger.info(f"Document {file_id} indexé avec succès - {len(documents)} chunks")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation du document {file_id}: {e}")
            return {
                "success": False,
                "file_id": file_id,
                "error": str(e),
                "encryption_used": self.use_encryption
            }
    
    def is_supported_format(self, filename: str) -> bool:
        """
        Vérifie si un format de fichier est supporté
        
        Args:
            filename: Nom du fichier
            
        Returns:
            bool: True si le format est supporté
        """
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type in self.supported_types if mime_type else False
    
    def get_extraction_capabilities(self) -> Dict[str, Any]:
        """
        Retourne les informations sur les capacités d'extraction
        
        Returns:
            Dict: Informations sur les capacités
        """
        capabilities = {
            'azure_doc_intelligence_available': self.doc_intelligence_service is not None,
            'supported_formats': list(self.supported_types.keys()),
            'fallback_methods': {
                'pdf': 'PyPDF2',
                'docx': 'python-docx',
                'txt': 'native',
                'json': 'native'
            },
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap
        }
        
        if self.doc_intelligence_service:
            doc_intel_info = self.doc_intelligence_service.get_service_info()
            capabilities['azure_doc_intelligence'] = doc_intel_info
        
        return capabilities
