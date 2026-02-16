"""
Service de chunking intelligent pour améliorer la qualité du RAG
Implémente plusieurs stratégies de segmentation optimisées
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class SmartChunker:
    """
    Gestionnaire de chunking intelligent avec plusieurs stratégies
    """
    
    def __init__(self, 
                 target_chunk_size: int = 500,
                 max_chunk_size: int = 800,
                 overlap_size: int = 100,
                 strategy: str = "smart",
                 table_strategy: str = "preserve_structure",
                 table_max_rows_per_chunk: int = 10,
                 table_always_include_headers: bool = True,
                 table_semantic_grouping: bool = True,
                 table_column_chunking: bool = False):
        """
        Initialise le chunker intelligent
        
        Args:
            target_chunk_size: Taille cible des chunks
            max_chunk_size: Taille maximale autorisée
            overlap_size: Taille du chevauchement
            strategy: Stratégie de chunking ('simple', 'smart', 'semantic')
            table_strategy: Stratégie pour les tableaux
            table_max_rows_per_chunk: Nombre max de lignes par chunk de tableau
            table_always_include_headers: Toujours inclure les en-têtes
            table_semantic_grouping: Groupement sémantique des lignes
            table_column_chunking: Créer des chunks par colonne
        """
        self.target_size = target_chunk_size
        self.max_size = max_chunk_size
        self.overlap_size = overlap_size
        self.strategy = strategy
        
        # Configuration des tableaux
        self.table_strategy = table_strategy
        self.table_max_rows_per_chunk = table_max_rows_per_chunk
        self.table_always_include_headers = table_always_include_headers
        self.table_semantic_grouping = table_semantic_grouping
        self.table_column_chunking = table_column_chunking
        
        # Patterns pour détecter les structures
        self.paragraph_pattern = r'\n\s*\n'
        self.sentence_pattern = r'[.!?]+\s+'
        self.section_patterns = [
            r'^\s*(?:Section|Article|Chapitre|Chapter)\s+\d+',
            r'^\s*\d+\.\s+[A-Z]',
            r'^\s*[A-Z]+\.\s+',
            r'^\s*#+\s+',  # Markdown headers
        ]
        
        # Patterns pour détecter les tableaux
        self.table_patterns = {
            'markdown': r'\|[^\n]*\|[^\n]*\n\|[-\s|:]+\|[^\n]*\n(\|[^\n]*\|[^\n]*\n)+',
            'ascii_table': r'^[\+\-\|][\-\+\|]*[\+\-\|]$',
            'csv_like': r'^[^,\n]+,[^,\n]+.*\n([^,\n]+,[^,\n]+.*\n){2,}',
            'formatted_rows': r'^[^\n]*\|[^\n]*$',
            'azure_table': r'--- TABLEAU \d+ ---[^-]*?(?=--- |$)'
        }
        
        logger.info(f"SmartChunker initialisé - Stratégie: {strategy}, Taille cible: {target_chunk_size}")
        logger.info(f"Configuration tableaux - Stratégie: {table_strategy}, Max lignes: {table_max_rows_per_chunk}")
    
    def create_chunks(self, text: str, document_type: str = "auto") -> List[Dict[str, Any]]:
        """
        Crée des chunks intelligents basés sur la stratégie choisie
        
        Args:
            text: Texte à segmenter
            document_type: Type de document ('auto', 'narrative', 'technical', 'legal')
            
        Returns:
            List[Dict]: Chunks avec métadonnées
        """
        if not text or not text.strip():
            return []
        
        # Détecter le type de document si auto
        if document_type == "auto":
            document_type = self._detect_document_type(text)
        
        logger.info(f"Chunking avec stratégie '{self.strategy}' pour document type '{document_type}'")
        
        # Appliquer la stratégie appropriée
        if self.strategy == "smart":
            # Détecter les tableaux en premier pour la stratégie smart
            detected_tables = self._detect_table_structures(text)
            if detected_tables and self.table_strategy == "preserve_structure":
                logger.info(f"Utilisation du chunking adapté aux tableaux ({len(detected_tables)} tableaux détectés)")
                chunks = self._table_aware_chunking(text, detected_tables)
            else:
                chunks = self._smart_chunking(text, document_type)
        elif self.strategy == "semantic":
            chunks = self._semantic_chunking(text)
        else:
            chunks = self._simple_chunking(text)
        
        # Ajouter l'overlap intelligent
        overlapped_chunks = self._add_intelligent_overlap(chunks, text)
        
        # Finaliser avec métadonnées
        final_chunks = self._finalize_chunks(overlapped_chunks)
        
        logger.info(f"Créé {len(final_chunks)} chunks (taille moyenne: {self._average_chunk_size(final_chunks):.0f})")
        
        return final_chunks
    
    def _detect_document_type(self, text: str) -> str:
        """
        Détecte automatiquement le type de document
        """
        text_sample = text[:2000].lower()
        
        # Patterns pour différents types
        if any(pattern in text_sample for pattern in ['article', 'section', 'clause', 'whereas']):
            return "legal"
        elif any(pattern in text_sample for pattern in ['function', 'class', 'import', 'def', 'var']):
            return "code"
        elif len(re.findall(r'^\s*\d+\.', text_sample, re.MULTILINE)) > 3:
            return "technical"
        else:
            return "narrative"
    
    def _smart_chunking(self, text: str, document_type: str) -> List[str]:
        """
        Chunking intelligent adapté au type de document avec gestion des tableaux
        """
        # Détecter les tableaux d'abord
        detected_tables = self._detect_table_structures(text)
        
        if detected_tables and self.table_strategy == "preserve_structure":
            return self._table_aware_chunking(text, detected_tables)
        elif document_type == "legal":
            return self._legal_chunking(text)
        elif document_type == "technical":
            return self._technical_chunking(text)
        elif document_type == "code":
            return self._code_chunking(text)
        else:
            return self._narrative_chunking(text)
    
    def _detect_table_structures(self, text: str) -> List[Dict]:
        """Détecte différents types de tableaux dans le texte"""
        
        detected_tables = []
        
        for table_type, pattern in self.table_patterns.items():
            try:
                if table_type == 'azure_table':
                    # Pattern spécial pour tableaux Azure Document Intelligence
                    matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)
                else:
                    matches = re.finditer(pattern, text, re.MULTILINE)
                
                for match in matches:
                    table_content = match.group()
                    table_info = {
                        'type': table_type,
                        'start': match.start(),
                        'end': match.end(),
                        'content': table_content,
                        'row_count': len(table_content.split('\n')),
                        'estimated_columns': self._estimate_columns(table_content),
                        'has_headers': self._has_header_row(table_content, table_type),
                        'table_classification': self._classify_table_type(table_content)
                    }
                    detected_tables.append(table_info)
            except Exception as e:
                logger.warning(f"Erreur détection tableau {table_type}: {e}")
                continue
        
        # Trier par position et fusionner les chevauchements
        detected_tables.sort(key=lambda x: x['start'])
        merged_tables = self._merge_overlapping_tables(detected_tables)
        
        logger.info(f"Détection tableaux: {len(merged_tables)} tableaux trouvés")
        return merged_tables
    
    def _estimate_columns(self, table_content: str) -> int:
        """Estime le nombre de colonnes dans un tableau"""
        
        lines = [line.strip() for line in table_content.split('\n') if line.strip()]
        if not lines:
            return 0
        
        # Compter les séparateurs les plus fréquents
        separators = ['|', ',', '\t', ';']
        max_cols = 0
        
        for separator in separators:
            col_counts = [line.count(separator) + 1 for line in lines if separator in line]
            if col_counts:
                avg_cols = sum(col_counts) / len(col_counts)
                max_cols = max(max_cols, int(avg_cols))
        
        return max_cols
    
    def _has_header_row(self, table_content: str, table_type: str) -> bool:
        """Détecte si le tableau a une ligne d'en-tête"""
        
        lines = [line.strip() for line in table_content.split('\n') if line.strip()]
        if len(lines) < 2:
            return False
        
        if table_type == 'markdown':
            # Vérifier la présence d'une ligne de séparation
            return len(lines) > 1 and bool(re.match(r'^\|[-\s|:]+\|', lines[1]))
        elif table_type == 'azure_table':
            # Les tableaux Azure ont souvent "TABLEAU X" comme indicateur
            return 'TABLEAU' in lines[0]
        else:
            # Heuristique: première ligne contient plus de lettres que de chiffres
            first_line = lines[0]
            letter_count = sum(1 for c in first_line if c.isalpha())
            digit_count = sum(1 for c in first_line if c.isdigit())
            return letter_count > digit_count
    
    def _classify_table_type(self, table_content: str) -> str:
        """Classification automatique du type de tableau"""
        
        content_lower = table_content.lower()
        
        # Mots-clés pour différents types de tableaux
        financial_keywords = ['prix', 'coût', 'montant', '€', '$', 'budget', 'facture']
        temporal_keywords = ['date', 'heure', 'planning', 'délai', 'échéance']
        contact_keywords = ['nom', 'prénom', 'contact', 'email', 'téléphone']
        spec_keywords = ['spécification', 'paramètre', 'config', 'propriété', 'valeur']
        legal_keywords = ['article', 'clause', 'alinéa', 'paragraphe', 'section']
        
        if any(keyword in content_lower for keyword in financial_keywords):
            return 'financial'
        elif any(keyword in content_lower for keyword in temporal_keywords):
            return 'temporal'
        elif any(keyword in content_lower for keyword in contact_keywords):
            return 'contact_list'
        elif any(keyword in content_lower for keyword in spec_keywords):
            return 'specification'
        elif any(keyword in content_lower for keyword in legal_keywords):
            return 'legal'
        else:
            return 'general'
    
    def _merge_overlapping_tables(self, tables: List[Dict]) -> List[Dict]:
        """Fusionne les tableaux qui se chevauchent"""
        
        if not tables:
            return []
        
        merged = []
        current_table = tables[0].copy()
        
        for next_table in tables[1:]:
            # Si les tableaux se chevauchent
            if next_table['start'] <= current_table['end']:
                # Fusionner en prenant les limites externes
                current_table['end'] = max(current_table['end'], next_table['end'])
                current_table['content'] = current_table['content'] + '\n' + next_table['content']
                current_table['row_count'] += next_table['row_count']
                # Garder le type le plus spécifique
                if next_table['type'] != 'formatted_rows':
                    current_table['type'] = next_table['type']
            else:
                merged.append(current_table)
                current_table = next_table.copy()
        
        merged.append(current_table)
        return merged
    
    def _narrative_chunking(self, text: str) -> List[str]:
        """
        Chunking optimisé pour du texte narratif (respecte paragraphes et phrases)
        """
        # 1. Diviser en paragraphes
        paragraphs = re.split(self.paragraph_pattern, text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # Si ajouter ce paragraphe dépasse la taille cible
            if len(current_chunk) + len(paragraph) + 2 > self.target_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = paragraph
                else:
                    # Paragraphe trop long, le diviser par phrases
                    if len(paragraph) > self.max_size:
                        sentence_chunks = self._split_by_sentences(paragraph)
                        chunks.extend(sentence_chunks)
                    else:
                        chunks.append(paragraph)
                    current_chunk = ""
            else:
                current_chunk += ("\\n\\n" + paragraph) if current_chunk else paragraph
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _technical_chunking(self, text: str) -> List[str]:
        """
        Chunking pour documents techniques (respecte sections, listes, numérotation)
        """
        # Détecter les sections
        sections = self._detect_sections(text)
        
        if not sections:
            # Pas de sections détectées, utiliser le chunking narratif
            return self._narrative_chunking(text)
        
        chunks = []
        
        for section_start, section_end in sections:
            section_text = text[section_start:section_end].strip()
            
            if len(section_text) <= self.max_size:
                chunks.append(section_text)
            else:
                # Section trop longue, la diviser intelligemment
                sub_chunks = self._split_large_section(section_text)
                chunks.extend(sub_chunks)
        
        return chunks
    
    def _legal_chunking(self, text: str) -> List[str]:
        """
        Chunking pour documents légaux (respecte articles, clauses)
        """
        # Patterns spécifiques aux documents légaux
        legal_patterns = [
            r'Article\s+\d+',
            r'Section\s+\d+',
            r'Clause\s+\d+',
            r'^\s*\([a-z]\)',  # (a), (b), (c)
            r'^\s*\d+\)',      # 1), 2), 3)
        ]
        
        return self._pattern_based_chunking(text, legal_patterns)
    
    def _code_chunking(self, text: str) -> List[str]:
        """
        Chunking pour code source (respecte fonctions, classes)
        """
        # Patterns pour code
        code_patterns = [
            r'^def\s+\w+',      # Fonctions Python
            r'^class\s+\w+',    # Classes Python
            r'^function\s+\w+', # Fonctions JS
            r'^public\s+class', # Classes Java
        ]
        
        return self._pattern_based_chunking(text, code_patterns)
    
    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Divise un texte long en respectant les limites de phrases
        """
        sentences = re.split(self.sentence_pattern, text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= self.target_size:
                current_chunk += (" " + sentence) if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _detect_sections(self, text: str) -> List[Tuple[int, int]]:
        """
        Détecte les sections dans le texte
        """
        sections = []
        
        for pattern in self.section_patterns:
            matches = list(re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE))
            
            for i, match in enumerate(matches):
                start = match.start()
                # Fin de section = début de la suivante ou fin du texte
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                sections.append((start, end))
        
        # Trier par position et fusionner les chevauchements
        sections.sort()
        merged_sections = []
        
        for start, end in sections:
            if merged_sections and start <= merged_sections[-1][1]:
                # Fusionner avec la section précédente
                merged_sections[-1] = (merged_sections[-1][0], max(end, merged_sections[-1][1]))
            else:
                merged_sections.append((start, end))
        
        return merged_sections
    
    def _table_aware_chunking(self, text: str, detected_tables: List[Dict]) -> List[str]:
        """Chunking qui préserve l'intégrité des tableaux"""
        
        chunks = []
        last_pos = 0
        
        for table in detected_tables:
            # Texte avant le tableau
            if table['start'] > last_pos:
                pre_table_text = text[last_pos:table['start']].strip()
                if pre_table_text:
                    # Chunking normal pour le texte avant le tableau
                    pre_chunks = self._chunk_regular_text(pre_table_text)
                    chunks.extend(pre_chunks)
            
            # Traitement spécialisé du tableau
            table_chunks = self._chunk_table_intelligently(table)
            chunks.extend(table_chunks)
            
            last_pos = table['end']
        
        # Texte après le dernier tableau
        if last_pos < len(text):
            remaining_text = text[last_pos:].strip()
            if remaining_text:
                remaining_chunks = self._chunk_regular_text(remaining_text)
                chunks.extend(remaining_chunks)
        
        return chunks
    
    def _chunk_regular_text(self, text: str) -> List[str]:
        """Chunking standard pour le texte non-tabulaire"""
        return self._narrative_chunking(text)
    
    def _chunk_table_intelligently(self, table: Dict) -> List[str]:
        """Stratégies spécialisées selon le type de tableau"""
        
        logger.info(f"Chunking tableau {table['type']} - {table['row_count']} lignes, {table['estimated_columns']} colonnes")
        
        if table['type'] == 'markdown':
            return self._chunk_markdown_table(table)
        elif table['row_count'] > self.table_max_rows_per_chunk * 2:  # Grand tableau
            return self._chunk_large_table(table)
        elif self._is_reference_table(table):
            return self._chunk_reference_table(table)
        else:
            return self._chunk_small_table(table)
    
    def _chunk_markdown_table(self, table: Dict) -> List[str]:
        """Préserve les en-têtes Markdown et groupe les lignes logiquement"""
        
        lines = [line for line in table['content'].split('\n') if line.strip()]
        if len(lines) < 2:
            return [table['content']]
        
        header_line = lines[0] if lines else ""
        separator_line = lines[1] if len(lines) > 1 and '|' in lines[1] else ""
        data_lines = lines[2:] if len(lines) > 2 else lines[1:] if not separator_line else []
        
        # Toujours inclure en-tête et séparateur si présents
        base_content = header_line
        if separator_line:
            base_content += f"\n{separator_line}"
        base_content += "\n"
        
        chunks = []
        current_chunk = base_content
        rows_in_chunk = 0
        
        for line in data_lines:
            proposed_chunk = current_chunk + line + "\n"
            
            if (len(proposed_chunk) > self.target_size or 
                rows_in_chunk >= self.table_max_rows_per_chunk):
                
                if current_chunk != base_content:
                    chunks.append(current_chunk.strip())
                current_chunk = base_content + line + "\n"
                rows_in_chunk = 1
            else:
                current_chunk = proposed_chunk
                rows_in_chunk += 1
        
        if current_chunk != base_content:
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [table['content']]
    
    def _chunk_large_table(self, table: Dict) -> List[str]:
        """Stratégie pour gros tableaux : chunking par blocs sémantiques"""
        
        lines = [line for line in table['content'].split('\n') if line.strip()]
        
        # Identifier l'en-tête si présent
        header_lines = []
        data_start_index = 0
        
        if table['has_headers']:
            if table['type'] == 'markdown' and len(lines) >= 2:
                header_lines = lines[:2]  # En-tête + séparateur
                data_start_index = 2
            elif table['type'] == 'azure_table':
                # Chercher la fin de l'en-tête Azure
                for i, line in enumerate(lines):
                    if not line.startswith('---') and '|' in line:
                        data_start_index = i
                        break
                header_lines = lines[:data_start_index] if data_start_index > 0 else []
            else:
                header_lines = [lines[0]] if lines else []
                data_start_index = 1
        
        data_lines = lines[data_start_index:]
        
        # Grouper les lignes par blocs sémantiques si activé
        if self.table_semantic_grouping:
            semantic_groups = self._identify_semantic_groups(data_lines, table)
        else:
            # Groupement simple par taille
            semantic_groups = [data_lines[i:i + self.table_max_rows_per_chunk] 
                             for i in range(0, len(data_lines), self.table_max_rows_per_chunk)]
        
        chunks = []
        for group in semantic_groups:
            # Construire le chunk avec en-tête si nécessaire
            chunk_lines = []
            if self.table_always_include_headers and header_lines:
                chunk_lines.extend(header_lines)
            chunk_lines.extend(group)
            
            chunk_content = '\n'.join(chunk_lines)
            
            # Si le chunk est encore trop grand, le subdiviser
            if len(chunk_content) > self.max_size:
                sub_chunks = self._subdivide_table_group(chunk_content, header_lines)
                chunks.extend(sub_chunks)
            else:
                chunks.append(chunk_content)
        
        return chunks
    
    def _chunk_small_table(self, table: Dict) -> List[str]:
        """Traitement pour petits tableaux : garder intact si possible"""
        
        if len(table['content']) <= self.max_size:
            return [table['content']]
        else:
            # Diviser par lignes avec préservation d'en-tête
            return self._chunk_large_table(table)
    
    def _chunk_reference_table(self, table: Dict) -> List[str]:
        """Chunking optimisé pour tableaux de référence"""
        
        lines = [line for line in table['content'].split('\n') if line.strip()]
        
        # Pour les tableaux de référence, grouper par entrées logiques
        # (par exemple, définitions qui vont ensemble)
        logical_groups = self._group_reference_entries(lines, table)
        
        chunks = []
        current_chunk_lines = []
        
        # Inclure l'en-tête si présent
        if table['has_headers'] and lines:
            if table['type'] == 'markdown' and len(lines) >= 2:
                current_chunk_lines.extend(lines[:2])
                logical_groups = logical_groups[2:] if len(logical_groups) > 2 else []
            else:
                current_chunk_lines.append(lines[0])
                logical_groups = logical_groups[1:] if logical_groups else []
        
        for group in logical_groups:
            proposed_lines = current_chunk_lines + [group]
            proposed_content = '\n'.join(proposed_lines)
            
            if len(proposed_content) > self.target_size and current_chunk_lines:
                # Sauvegarder le chunk actuel
                chunks.append('\n'.join(current_chunk_lines))
                
                # Recommencer avec l'en-tête si nécessaire
                current_chunk_lines = []
                if self.table_always_include_headers and table['has_headers']:
                    if table['type'] == 'markdown' and len(lines) >= 2:
                        current_chunk_lines.extend(lines[:2])
                    else:
                        current_chunk_lines.append(lines[0])
                
                current_chunk_lines.append(group)
            else:
                current_chunk_lines.append(group)
        
        if current_chunk_lines:
            chunks.append('\n'.join(current_chunk_lines))
        
        return chunks if chunks else [table['content']]
    
    def _is_reference_table(self, table: Dict) -> bool:
        """Détecte si c'est un tableau de référence (glossaire, index, etc.)"""
        
        content_lower = table['content'].lower()
        reference_indicators = [
            'définition', 'description', 'référence', 'glossaire',
            'index', 'code', 'nom', 'valeur', 'type', 'paramètre'
        ]
        
        return any(indicator in content_lower for indicator in reference_indicators)
    
    def _identify_semantic_groups(self, data_lines: List[str], table: Dict) -> List[List[str]]:
        """Identifie des groupes sémantiques dans les lignes de données"""
        
        if not data_lines:
            return []
        
        groups = []
        current_group = []
        
        # Stratégies de groupement selon le type de tableau
        if table['table_classification'] == 'financial':
            # Grouper par sections financières (même monnaie, même type)
            current_group = [data_lines[0]] if data_lines else []
            for line in data_lines[1:]:
                if self._lines_semantically_related(current_group[-1], line, 'financial'):
                    current_group.append(line)
                else:
                    if current_group:
                        groups.append(current_group)
                    current_group = [line]
        
        elif table['table_classification'] == 'temporal':
            # Grouper par périodes temporelles
            current_group = [data_lines[0]] if data_lines else []
            for line in data_lines[1:]:
                if self._lines_semantically_related(current_group[-1], line, 'temporal'):
                    current_group.append(line)
                else:
                    if current_group:
                        groups.append(current_group)
                    current_group = [line]
        
        else:
            # Groupement par défaut : par taille de chunk
            for i in range(0, len(data_lines), self.table_max_rows_per_chunk):
                group = data_lines[i:i + self.table_max_rows_per_chunk]
                if group:
                    groups.append(group)
        
        # Ajouter le dernier groupe
        if current_group and (not groups or current_group != groups[-1]):
            groups.append(current_group)
        
        return groups if groups else [data_lines]
    
    def _lines_semantically_related(self, line1: str, line2: str, table_type: str) -> bool:
        """Détermine si deux lignes sont sémantiquement liées"""
        
        if table_type == 'financial':
            # Vérifier si même devise ou catégorie financière
            currencies = ['€', '$', '£', 'USD', 'EUR']
            line1_currency = next((c for c in currencies if c in line1), None)
            line2_currency = next((c for c in currencies if c in line2), None)
            return line1_currency == line2_currency
        
        elif table_type == 'temporal':
            # Vérifier si même période (année, mois)
            import re
            date_pattern = r'\b\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b|\b\d{4}\b'
            line1_dates = re.findall(date_pattern, line1)
            line2_dates = re.findall(date_pattern, line2)
            
            if line1_dates and line2_dates:
                # Comparer les années
                line1_year = next((d for d in line1_dates if len(d) == 4), None)
                line2_year = next((d for d in line2_dates if len(d) == 4), None)
                return line1_year == line2_year
        
        # Par défaut, considérer comme liées si longueur similaire
        return abs(len(line1) - len(line2)) < 50
    
    def _group_reference_entries(self, lines: List[str], table: Dict) -> List[str]:
        """Groupe les entrées de référence logiquement"""
        
        # Pour les tableaux de référence, chaque ligne est généralement une entrée
        return lines
    
    def _subdivide_table_group(self, chunk_content: str, header_lines: List[str]) -> List[str]:
        """Subdivise un groupe de tableau trop grand"""
        
        lines = chunk_content.split('\n')
        
        # Retirer l'en-tête pour la subdivision
        header_count = len(header_lines) if header_lines else 0
        data_lines = lines[header_count:]
        
        sub_chunks = []
        current_lines = header_lines.copy() if header_lines else []
        
        for line in data_lines:
            proposed_content = '\n'.join(current_lines + [line])
            
            if len(proposed_content) > self.target_size and len(current_lines) > header_count:
                # Sauvegarder le chunk actuel
                sub_chunks.append('\n'.join(current_lines))
                
                # Recommencer avec l'en-tête
                current_lines = header_lines.copy() if header_lines else []
                current_lines.append(line)
            else:
                current_lines.append(line)
        
        if current_lines and len(current_lines) > header_count:
            sub_chunks.append('\n'.join(current_lines))
        
        return sub_chunks if sub_chunks else [chunk_content]
    
    def _split_large_section(self, section_text: str) -> List[str]:
        """
        Divise une section trop longue en sous-chunks
        """
        # Essayer d'abord par paragraphes
        paragraphs = re.split(self.paragraph_pattern, section_text)
        
        if len(paragraphs) > 1:
            return self._narrative_chunking(section_text)
        else:
            # Pas de paragraphes, diviser par phrases
            return self._split_by_sentences(section_text)
    
    def _pattern_based_chunking(self, text: str, patterns: List[str]) -> List[str]:
        """
        Chunking basé sur des patterns spécifiques
        """
        # Trouver toutes les correspondances
        matches = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                matches.append(match.start())
        
        if not matches:
            return self._narrative_chunking(text)
        
        matches.sort()
        matches.append(len(text))  # Ajouter la fin du texte
        
        chunks = []
        start = 0
        
        for end_pos in matches[1:]:
            chunk_text = text[start:end_pos].strip()
            if chunk_text:
                if len(chunk_text) <= self.max_size:
                    chunks.append(chunk_text)
                else:
                    # Chunk trop long, le diviser
                    sub_chunks = self._split_by_sentences(chunk_text)
                    chunks.extend(sub_chunks)
            start = end_pos
        
        return chunks
    
    def _semantic_chunking(self, text: str) -> List[str]:
        """
        Chunking sémantique (version simplifiée)
        Dans une version complète, on utiliserait des embeddings
        """
        # Pour l'instant, utilise une heuristique basée sur les mots-clés
        topic_change_indicators = [
            "par ailleurs", "d'autre part", "en outre", "cependant", 
            "néanmoins", "toutefois", "en revanche", "de plus",
            "furthermore", "however", "moreover", "nevertheless"
        ]
        
        sentences = re.split(self.sentence_pattern, text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Détecter un changement de sujet
            topic_change = any(indicator in sentence.lower() for indicator in topic_change_indicators)
            
            if (topic_change and current_chunk and len(current_chunk) > self.target_size // 2) or \
               (len(current_chunk) + len(sentence) > self.target_size):
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += (" " + sentence) if current_chunk else sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _simple_chunking(self, text: str) -> List[str]:
        """
        Chunking simple par taille (version améliorée de l'original)
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.target_size, len(text))
            
            # Ajuster pour ne pas couper au milieu d'un mot
            if end < len(text) and not text[end].isspace():
                # Chercher le dernier espace
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
                else:
                    # Chercher le prochain espace
                    next_space = text.find(' ', end)
                    if next_space != -1 and next_space - start <= self.max_size:
                        end = next_space
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)
            
            if end >= len(text):
                break
            
            start = end
        
        return chunks
    
    def _add_intelligent_overlap(self, chunks: List[str], original_text: str) -> List[str]:
        """
        Ajoute un overlap intelligent basé sur le contenu
        """
        if len(chunks) <= 1 or self.overlap_size <= 0:
            return chunks
        
        overlapped_chunks = [chunks[0]]  # Premier chunk sans modification
        
        for i in range(1, len(chunks)):
            current_chunk = chunks[i]
            previous_chunk = chunks[i-1]
            
            # Extraire la fin du chunk précédent pour l'overlap
            overlap_text = self._extract_meaningful_overlap(previous_chunk, self.overlap_size)
            
            if overlap_text:
                overlapped_chunk = overlap_text + "\\n" + current_chunk
                overlapped_chunks.append(overlapped_chunk)
            else:
                overlapped_chunks.append(current_chunk)
        
        return overlapped_chunks
    
    def _extract_meaningful_overlap(self, text: str, max_overlap: int) -> str:
        """
        Extrait un overlap significatif (phrases complètes)
        """
        if len(text) <= max_overlap:
            return text
        
        # Chercher les dernières phrases complètes dans la limite
        sentences = re.split(self.sentence_pattern, text)
        
        overlap = ""
        for sentence in reversed(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(overlap) + len(sentence) + 1 <= max_overlap:
                overlap = (sentence + ". " + overlap) if overlap else sentence
            else:
                break
        
        return overlap.strip()
    
    def _finalize_chunks(self, chunks: List[str]) -> List[Dict[str, Any]]:
        """
        Finalise les chunks avec métadonnées
        """
        finalized_chunks = []
        
        for i, chunk_text in enumerate(chunks):
            chunk = {
                'index': i,
                'text': chunk_text.strip(),
                'length': len(chunk_text),
                'start_pos': 0,  # Sera recalculé si nécessaire
                'end_pos': len(chunk_text),
                'chunk_type': self._classify_chunk(chunk_text),
                'quality_score': self._calculate_quality_score(chunk_text)
            }
            finalized_chunks.append(chunk)
        
        return finalized_chunks
    
    def _classify_chunk(self, text: str) -> str:
        """
        Classifie le type de chunk pour des métadonnées
        """
        # Détecter les chunks de tableau
        if '|' in text and text.count('|') > 4:
            if 'TABLEAU' in text:
                return "azure_table"
            elif re.search(r'\|[-\s|:]+\|', text):
                return "markdown_table"
            else:
                return "formatted_table"
        
        # Détecter les listes
        elif len(re.findall(r'\\d+\\.', text)) > 2:
            return "list"
        elif re.search(r'^(Section|Article|Chapter)', text, re.IGNORECASE):
            return "section_header"
        elif len(text.split('. ')) > 5:
            return "paragraph"
        else:
            return "fragment"
    
    def _calculate_quality_score(self, text: str) -> float:
        """
        Calcule un score de qualité pour le chunk
        """
        score = 1.0
        
        # Pénaliser les chunks très courts ou très longs
        length_ratio = len(text) / self.target_size
        if length_ratio < 0.3 or length_ratio > 2.0:
            score -= 0.3
        
        # Bonifier les chunks qui se terminent par une phrase complète
        if text.rstrip().endswith(('.', '!', '?')):
            score += 0.1
        
        # Pénaliser les chunks qui commencent par une minuscule (probable coupure)
        if text.strip() and text.strip()[0].islower():
            score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def _average_chunk_size(self, chunks: List[Dict[str, Any]]) -> float:
        """
        Calcule la taille moyenne des chunks
        """
        if not chunks:
            return 0.0
        return sum(chunk['length'] for chunk in chunks) / len(chunks)
    
    def get_chunking_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Retourne des statistiques sur le chunking
        """
        if not chunks:
            return {}
        
        lengths = [chunk['length'] for chunk in chunks]
        quality_scores = [chunk.get('quality_score', 0.0) for chunk in chunks]
        
        return {
            'total_chunks': len(chunks),
            'average_length': sum(lengths) / len(lengths),
            'min_length': min(lengths),
            'max_length': max(lengths),
            'average_quality': sum(quality_scores) / len(quality_scores),
            'chunks_by_type': self._count_by_type(chunks),
            'strategy_used': self.strategy
        }
    
    def _count_by_type(self, chunks: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Compte les chunks par type
        """
        counts = {}
        for chunk in chunks:
            chunk_type = chunk.get('chunk_type', 'unknown')
            counts[chunk_type] = counts.get(chunk_type, 0) + 1
        return counts
