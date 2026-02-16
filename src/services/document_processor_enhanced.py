"""
Extension du DocumentProcessor avec chunking intelligent
Cette version peut remplacer la méthode _create_chunks dans votre DocumentProcessor existant
"""

from .smart_chunker import SmartChunker
import logging

logger = logging.getLogger(__name__)

class DocumentProcessorEnhanced:
    """
    Extension du DocumentProcessor avec chunking intelligent
    """
    
    def __init__(self, document_processor_instance):
        """
        Initialise avec une instance de DocumentProcessor existante
        """
        self.base_processor = document_processor_instance
        
        # Créer le smart chunker avec les paramètres actuels
        self.smart_chunker = SmartChunker(
            target_chunk_size=document_processor_instance.chunk_size,
            max_chunk_size=int(document_processor_instance.chunk_size * 1.5),
            overlap_size=document_processor_instance.chunk_overlap,
            strategy="smart"  # Peut être configuré
        )
        
        logger.info("DocumentProcessor amélioré avec SmartChunker")
    
    def create_chunks_enhanced(self, text: str, filename: str = None) -> List[Dict[str, Any]]:
        """
        Version améliorée de _create_chunks avec chunking intelligent
        
        Args:
            text: Texte à segmenter
            filename: Nom du fichier pour détecter le type
            
        Returns:
            List[Dict]: Chunks améliorés avec métadonnées
        """
        if not text or not text.strip():
            return []
        
        # Détecter le type de document basé sur l'extension
        document_type = self._detect_document_type_from_filename(filename) if filename else "auto"
        
        logger.info(f"Chunking intelligent du texte ({len(text)} caractères) - Type: {document_type}")
        
        # Utiliser le smart chunker
        chunks = self.smart_chunker.create_chunks(text, document_type)
        
        # Recalculer les positions dans le texte original
        chunks_with_positions = self._recalculate_positions(chunks, text)
        
        # Statistiques de chunking
        stats = self.smart_chunker.get_chunking_stats(chunks_with_positions)
        logger.info(f"Chunking terminé: {stats}")
        
        return chunks_with_positions
    
    def _detect_document_type_from_filename(self, filename: str) -> str:
        """
        Détecte le type de document basé sur l'extension
        """
        if not filename:
            return "auto"
        
        filename_lower = filename.lower()
        
        # Mappings d'extensions vers types de documents
        type_mappings = {
            'legal': ['.pdf', '.doc', '.docx'] if any(keyword in filename_lower for keyword in 
                     ['contrat', 'contract', 'legal', 'terme', 'condition', 'policy']) else [],
            'technical': ['.pdf', '.doc', '.docx'] if any(keyword in filename_lower for keyword in 
                         ['manual', 'guide', 'spec', 'documentation', 'readme']) else [],
            'code': ['.py', '.js', '.java', '.cpp', '.cs', '.php', '.rb', '.go'],
            'narrative': ['.txt', '.md', '.rtf']
        }
        
        # Vérifier l'extension
        extension = '.' + filename_lower.split('.')[-1] if '.' in filename else ''
        
        for doc_type, extensions in type_mappings.items():
            if extension in extensions:
                return doc_type
        
        return "auto"
    
    def _recalculate_positions(self, chunks: List[Dict[str, Any]], original_text: str) -> List[Dict[str, Any]]:
        """
        Recalcule les positions des chunks dans le texte original
        """
        updated_chunks = []
        search_start = 0
        
        for chunk in chunks:
            chunk_text = chunk['text']
            
            # Trouver la position dans le texte original
            position = original_text.find(chunk_text, search_start)
            
            if position != -1:
                chunk['start_pos'] = position
                chunk['end_pos'] = position + len(chunk_text)
                search_start = position + len(chunk_text)
            else:
                # Si on ne trouve pas exactement, utiliser une approximation
                chunk['start_pos'] = search_start
                chunk['end_pos'] = search_start + len(chunk_text)
                search_start += len(chunk_text)
            
            updated_chunks.append(chunk)
        
        return updated_chunks
    
    def process_file_enhanced(self, file_content: bytes, filename: str, file_id: str) -> Dict[str, Any]:
        """
        Version améliorée de process_file avec chunking intelligent
        """
        # Utiliser la méthode de base pour l'extraction de texte
        result = self.base_processor.process_file(file_content, filename, file_id)
        
        # Remplacer les chunks par la version améliorée
        if 'text_content' in result:
            enhanced_chunks = self.create_chunks_enhanced(result['text_content'], filename)
            result['chunks'] = enhanced_chunks
            result['chunks_count'] = len(enhanced_chunks)
            
            # Ajouter des métadonnées sur le chunking
            result['chunking_metadata'] = self.smart_chunker.get_chunking_stats(enhanced_chunks)
        
        return result


def enhance_existing_document_processor(document_processor):
    """
    Fonction utilitaire pour améliorer un DocumentProcessor existant
    
    Usage:
        enhanced_processor = enhance_existing_document_processor(your_document_processor)
        # Puis remplacer la méthode _create_chunks
        your_document_processor._create_chunks = enhanced_processor.create_chunks_enhanced
    """
    return DocumentProcessorEnhanced(document_processor)


# Méthode de remplacement direct pour intégration dans DocumentProcessor existant
def create_smart_chunks_method(chunk_size: int = 500, chunk_overlap: int = 100, strategy: str = "smart"):
    """
    Retourne une méthode _create_chunks améliorée pour remplacer l'existante
    
    Usage dans DocumentProcessor:
        self._create_chunks = create_smart_chunks_method(self.chunk_size, self.chunk_overlap)
    """
    
    smart_chunker = SmartChunker(
        target_chunk_size=chunk_size,
        max_chunk_size=int(chunk_size * 1.5),
        overlap_size=chunk_overlap,
        strategy=strategy
    )
    
    def _create_chunks_smart(text: str) -> List[Dict[str, Any]]:
        """
        Version améliorée de _create_chunks
        """
        if not text or not text.strip():
            return []
        
        logger.info(f"Chunking intelligent du texte ({len(text)} caractères)")
        
        # Utiliser le smart chunker
        chunks = smart_chunker.create_chunks(text)
        
        # Recalculer les positions dans le texte original (nécessaire pour compatibilité)
        search_start = 0
        for chunk in chunks:
            chunk_text = chunk['text']
            position = text.find(chunk_text, search_start)
            
            if position != -1:
                chunk['start_pos'] = position
                chunk['end_pos'] = position + len(chunk_text)
                search_start = position + len(chunk_text)
            else:
                chunk['start_pos'] = search_start
                chunk['end_pos'] = search_start + len(chunk_text)
                search_start += len(chunk_text)
        
        # Statistiques
        stats = smart_chunker.get_chunking_stats(chunks)
        logger.info(f"Chunking terminé: {stats['total_chunks']} chunks, qualité moyenne: {stats['average_quality']:.2f}")
        
        return chunks
    
    return _create_chunks_smart
