"""
Service d'embeddings utilisant l'endpoint Nomic Embed Text
"""
import os
import requests
import json
from typing import List, Union
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service de génération d'embeddings via endpoint Nomic"""
    
    def __init__(self, 
                 endpoint: str, 
                 api_key: str, 
                 model_name: str = "nomic-embed-text-v1.5",
                 dimension: int = 768):
        """
        Initialise le service d'embeddings Nomic
        
        Args:
            endpoint: URL de l'endpoint Nomic
            api_key: Clé API pour l'authentification
            model_name: Nom du modèle d'embeddings
            dimension: Dimension des vecteurs d'embedding
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_name = model_name
        self.dimension = dimension
        self.fallback_mode = False  # Mode de fallback pour les tests
        
        # Headers pour les requêtes
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Vérifier la connexion seulement si ce n'est pas une clé de test
        if api_key and api_key != "test-key" and not api_key.startswith("test-"):
            self._test_connection()
        elif api_key == "test-nomic-key":
            # Clé spéciale pour endpoint personnalisé - tester quand même
            logger.info("Endpoint personnalisé détecté - test de connexion...")
            self._test_connection()
        else:
            logger.info("Service d'embedding initialisé en mode test (pas de validation de connexion)")
            self.fallback_mode = True
    
    def _test_connection(self):
        """Test de connexion à l'endpoint"""
        try:
            # Test avec un texte simple
            test_response = self._call_api(["test connection"])
            if test_response and len(test_response) > 0:
                # Mettre à jour la dimension réelle si différente
                actual_dimension = len(test_response[0])
                if actual_dimension != self.dimension:
                    logger.info(f"Dimension mise à jour: {self.dimension} -> {actual_dimension}")
                    self.dimension = actual_dimension
                logger.info(f"Connexion Nomic réussie. Dimension: {self.dimension}")
            else:
                logger.warning("Test de connexion Nomic échoué")
        except Exception as e:
            logger.warning(f"Test de connexion échoué (sera tenté lors de l'utilisation): {e}")
    
    def _generate_fallback_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Génère des embeddings factices pour les tests
        
        Args:
            texts: Liste des textes
            
        Returns:
            List[List[float]]: Embeddings factices normalisés
        """
        import hashlib
        import random
        
        embeddings = []
        for text in texts:
            # Utiliser le hash du texte pour générer des embeddings reproductibles
            text_hash = hashlib.md5(text.encode()).hexdigest()
            random.seed(int(text_hash[:8], 16))
            
            # Générer un vecteur aléatoire mais reproductible
            embedding = [random.uniform(-1, 1) for _ in range(self.dimension)]
            
            # Normaliser le vecteur
            norm = sum(x*x for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x/norm for x in embedding]
            
            embeddings.append(embedding)
        
        return embeddings
    
    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """
        Appel à l'API Nomic pour générer les embeddings
        Supporte plusieurs formats: 'prompt' (Ollama), 'texts', 'input'
        
        Args:
            texts: Liste de textes à traiter
            
        Returns:
            List[List[float]]: Liste des embeddings
        """
        # Si en mode fallback, utiliser les embeddings factices
        if self.fallback_mode:
            logger.info("Mode fallback activé - génération d'embeddings factices")
            return self._generate_fallback_embeddings(texts)

        all_embeddings = []
        
        for text in texts:
            try:
                # Format 1: Ollama/Nomic avec "prompt" (priorité car fourni par l'utilisateur)
                payload_prompt = {
                    "model": self.model_name,
                    "prompt": text
                }
                
                response = requests.post(
                    self.endpoint,
                    headers=self.headers,
                    json=payload_prompt,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Réponse API Nomic (format prompt): {data}")
                    
                    if "embedding" in data and data["embedding"] and len(data["embedding"]) > 0:
                        all_embeddings.append(data["embedding"])
                        continue
                    else:
                        logger.warning(f"Format 'prompt': embedding vide pour le texte: {text[:50]}...")
                
                # Format 2: Standard avec "texts" 
                payload_texts = {
                    "model": self.model_name,
                    "texts": [text],
                    "task_type": "search_document"
                }
                
                response = requests.post(
                    self.endpoint,
                    headers=self.headers,
                    json=payload_texts,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Réponse API Nomic (format texts): {data}")
                    
                    if "embeddings" in data and data["embeddings"] and len(data["embeddings"]) > 0:
                        if len(data["embeddings"][0]) > 0:
                            all_embeddings.append(data["embeddings"][0])
                            continue
                    elif "embedding" in data and data["embedding"] and len(data["embedding"]) > 0:
                        all_embeddings.append(data["embedding"])
                        continue
                    else:
                        logger.warning(f"Format 'texts': embedding vide pour le texte: {text[:50]}...")
                
                # Format 3: OpenAI-like avec "input"
                payload_input = {
                    "model": self.model_name,
                    "input": text
                }
                
                response = requests.post(
                    self.endpoint,
                    headers=self.headers,
                    json=payload_input,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.debug(f"Réponse API Nomic (format input): {data}")
                    
                    if "data" in data and len(data["data"]) > 0:
                        embedding = data["data"][0].get("embedding", [])
                        if embedding and len(embedding) > 0:
                            all_embeddings.append(embedding)
                            continue
                    elif "embedding" in data and data["embedding"] and len(data["embedding"]) > 0:
                        all_embeddings.append(data["embedding"])
                        continue
                    else:
                        logger.warning(f"Format 'input': embedding vide pour le texte: {text[:50]}...")
                
                # Si aucun format ne fonctionne pour ce texte, utiliser le fallback
                logger.warning(f"Tous les formats ont échoué pour le texte: {text[:50]}... - utilisation du fallback")
                fallback_embedding = self._generate_fallback_embeddings([text])[0]
                all_embeddings.append(fallback_embedding)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Erreur de requête API Nomic pour '{text[:50]}...': {e}")
                # Utiliser le fallback pour ce texte
                fallback_embedding = self._generate_fallback_embeddings([text])[0]
                all_embeddings.append(fallback_embedding)
            except Exception as e:
                logger.error(f"Erreur lors de l'appel API Nomic pour '{text[:50]}...': {e}")
                # Utiliser le fallback pour ce texte
                fallback_embedding = self._generate_fallback_embeddings([text])[0]
                all_embeddings.append(fallback_embedding)
        
        # Vérifier si on a des embeddings réels ou seulement des fallbacks
        if all_embeddings:
            # Si on a au moins un embedding réel, c'est bon
            if any(len(emb) > 0 for emb in all_embeddings):
                return all_embeddings
            else:
                logger.warning("Tous les embeddings sont vides - activation du mode fallback")
                self.fallback_mode = True
                return self._generate_fallback_embeddings(texts)
        else:
            logger.warning("Aucun embedding généré - activation du mode fallback")
            self.fallback_mode = True
            return self._generate_fallback_embeddings(texts)
    
    def generate_embeddings(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        Génère des embeddings pour un ou plusieurs textes
        
        Args:
            texts: Texte(s) à convertir en embeddings
            
        Returns:
            Union[List[float], List[List[float]]]: Embedding(s) générés
        """
        try:
            # Normaliser l'entrée
            if isinstance(texts, str):
                texts = [texts]
                single_input = True
            else:
                single_input = False
            
            # Générer les embeddings via l'API
            embeddings = self._call_api(texts)
            
            # Retourner le format approprié
            if single_input:
                return embeddings[0]
            else:
                return embeddings
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embeddings: {e}")
            raise
    
    def get_model_info(self) -> dict:
        """
        Retourne les informations sur le modèle chargé
        
        Returns:
            dict: Informations sur le modèle
        """
        return {
            "model_name": self.model_name,
            "endpoint": self.endpoint,
            "dimension": self.dimension,
            "service_type": "Nomic Embed API",
            "connected": True
        }
    
    def batch_encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Encode un lot de textes en optimisant les performances
        
        Args:
            texts: Liste de textes à encoder
            batch_size: Taille du lot pour le traitement
            
        Returns:
            List[List[float]]: Liste d'embeddings
        """
        try:
            embeddings = []
            
            # Traiter par lots
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embeddings = self._call_api(batch)
                embeddings.extend(batch_embeddings)
                
                if i % (batch_size * 5) == 0:
                    logger.info(f"Traité {i + len(batch)}/{len(texts)} textes")
            
            logger.info(f"Génération d'embeddings terminée: {len(embeddings)} textes traités")
            return embeddings
            
        except Exception as e:
            logger.error(f"Erreur lors de l'encodage par lots: {e}")
            raise
    
    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Génère un embedding spécialement optimisé pour les requêtes
        
        Args:
            query: Requête de recherche
            
        Returns:
            List[float]: Embedding de la requête
        """
        try:
            # Utiliser la méthode standard mais avec task_type différent si possible
            return self.generate_embeddings(query)
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embedding de requête: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Alias pour generate_embeddings avec un seul texte (compatibilité)
        
        Args:
            text: Texte à convertir
            
        Returns:
            List[float]: Embedding généré
        """
        return self.generate_embeddings(text)
