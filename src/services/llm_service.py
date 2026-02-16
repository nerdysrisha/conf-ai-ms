"""
Service LLM pour l'interaction avec phi-2.7 via Ollama
"""
import os
import re
from typing import List, Dict, Any, Optional
import requests
import json
import logging

logger = logging.getLogger(__name__)

class LLMService:
    """Service pour l'interaction avec le modèle phi-2.7 via Ollama"""
    
    def __init__(self, endpoint: str, api_key: str, model_name: str = "phi:2.7", encrypted_search_service=None, base_url: str = "http://localhost:8000"):
        """
        Initialise le service LLM Ollama
        
        Args:
            endpoint: Endpoint Ollama (ex: http://4.232.232.104:11434)
            api_key: Clé API (peut être ignorée pour Ollama local)
            model_name: Nom du modèle Ollama (ex: phi:2.7)
            encrypted_search_service: Service de recherche chiffrée (optionnel)
            base_url: URL de base de l'application pour les liens de téléchargement
        """
        # Construire l'endpoint correct pour Ollama
        if not endpoint.endswith('/'):
            endpoint += '/'
        self.chat_endpoint = endpoint + "v1/chat/completions"
        self.generate_endpoint = endpoint + "api/generate"
        
        self.model_name = model_name
        self.api_key = api_key
        self.encrypted_search_service = encrypted_search_service
        self.use_encrypted_search = encrypted_search_service is not None
        self.base_url = base_url  # Stocker l'URL de base
        
        # Headers pour Ollama (généralement pas d'auth requise)
        self.headers = {
            "Content-Type": "application/json"
        }
        
        # Ajouter l'auth seulement si nécessaire
        if api_key and api_key != "test-phi35-key":
            self.headers["Authorization"] = f"Bearer {api_key}"
        
        # Contrôle du debug verbose
        self.debug_verbose = os.getenv('LLM_DEBUG_VERBOSE', 'false').lower() == 'true'
        self.debug_streaming = os.getenv('LLM_DEBUG_STREAMING', 'false').lower() == 'true'
        
        logger.info(f"Service LLM Ollama initialisé - Endpoint: {self.chat_endpoint}, Modèle: {model_name}")
        if self.use_encrypted_search:
            logger.info("Service de recherche chiffrée activé")
        if not self.debug_verbose:
            logger.info("Mode debug verbose désactivé")
        if not self.debug_streaming:
            logger.info("Mode debug streaming désactivé")
        
    def generate_response(self, 
                         messages: List[Dict[str, str]], 
                         max_tokens: int = None,
                         temperature: float = None,
                         top_p: float = None,
                         system_prompt: Optional[str] = None) -> str:
        """
        Génère une réponse à partir des messages via Ollama
        
        Args:
            messages: Liste des messages de conversation
            max_tokens: Nombre maximum de tokens (utilise Config.MAX_TOKENS si None)
            temperature: Température pour la génération (utilise Config.TEMPERATURE si None)
            top_p: Paramètre top_p pour la génération (utilise Config.TOP_P si None)
            system_prompt: Prompt système optionnel
            
        Returns:
            str: Réponse générée par le modèle
        """
        try:
            # Utiliser les valeurs de configuration par défaut si non spécifiées
            from ..config import Config
            if max_tokens is None:
                max_tokens = Config.MAX_TOKENS
            if temperature is None:
                temperature = Config.TEMPERATURE
            if top_p is None:
                top_p = Config.TOP_P
            # Préparer les messages pour Ollama
            formatted_messages = []
            
            if system_prompt:
                formatted_messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            formatted_messages.extend(messages)
            
            # Payload pour l'API OpenAI compatible (vLLM)
            payload = {
                "model": self.model_name,
                "messages": formatted_messages,
                "stream": False,  # Réponse complète (pour éviter erreurs)
                "max_tokens": max_tokens if max_tokens > 0 else None,
                "temperature": temperature,
                "top_p": top_p
            }
            
            # 🔍 LOGGING DÉTAILLÉ DU PROMPT ENVOYÉ À PHI-4 (conditionnel)
            if self.debug_verbose:
                print("\n" + "="*80)
                print("🤖 APPEL À PHI-4 VIA vLLM/OpenAI")
                print("="*80)
                print(f"📡 Endpoint: {self.chat_endpoint}")
                print(f"🔧 Modèle: {self.model_name}")
                print(f"🌡️ Température: {temperature}")
                print(f"📝 Nombre de messages: {len(formatted_messages)}")
                
                # 📋 AFFICHAGE JSON COMPLET DU PAYLOAD
                print("\n📋 PAYLOAD JSON COMPLET ENVOYÉ À PHI-4:")
                print("-" * 60)
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                print("-" * 60)
                
                # 📡 INFORMATIONS DE LA REQUÊTE HTTP
                print(f"\n📡 DÉTAILS DE LA REQUÊTE HTTP:")
                print(f"  - URL: {self.chat_endpoint}")
                print(f"  - Method: POST")
                print(f"  - Headers: {json.dumps(self.headers, indent=2, ensure_ascii=False)}")
                print(f"  - Timeout: 120 secondes")
                print("-" * 60)
                
                print("\n📋 PROMPT COMPLET ENVOYÉ:")
                print("-" * 60)
                for i, msg in enumerate(formatted_messages):
                    role = msg.get('role', 'unknown')
                    content = msg.get('content', '')
                    print(f"[{i+1}] ROLE: {role.upper()}")
                    print(f"CONTENU: {content}")
                    print("-" * 40)
            
            # Debug simple : Payload LLM (conditionnel)
            if self.debug_verbose:
                print(f"🤖 LLM CALL → phi-4 (NON-STREAMING)")
                print(f"📤 INPUT: {json.dumps(payload, ensure_ascii=False)}")
                print(f"❌ ATTENTION: Utilisation de la méthode NON-STREAMING generate_response()")
                print("-" * 80)
            
            # Envoyer la requête à vLLM/OpenAI
            response = requests.post(
                self.chat_endpoint,
                headers=self.headers,
                json=payload,
                timeout=120  # Ollama peut être lent
            )
            
            response.raise_for_status()
            
            # Extraire la réponse Ollama
            response_data = response.json()
            
            # Debug simple : Réponse LLM
            print(f"📥 OUTPUT: {json.dumps(response_data, ensure_ascii=False)}")
            print("-" * 60)
            
            # Format de réponse OpenAI
            if "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    response_content = choice["message"]["content"]
                    print(f"\n✅ CONTENU EXTRAIT: {response_content}")
                    
                    # Statistiques OpenAI/vLLM
                    usage = response_data.get('usage', {})
                    if usage:
                        print(f"\n📊 STATISTIQUES:")
                        print(f"  - Tokens de prompt: {usage.get('prompt_tokens', 'N/A')}")
                        print(f"  - Tokens générés: {usage.get('completion_tokens', 'N/A')}")
                        print(f"  - Total tokens: {usage.get('total_tokens', 'N/A')}")
                    
                    print("="*80 + "\n")
                    return response_content
            
            print(f"❌ FORMAT INATTENDU: {response_data}")
            print("="*80 + "\n")
            raise ValueError(f"Format de réponse OpenAI inattendu: {response_data}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de connexion vLLM/OpenAI: {e}")
            return f"Erreur de connexion au modèle phi-4. Vérifiez que vLLM est démarré et que le modèle {self.model_name} est disponible."
        except Exception as e:
            logger.error(f"Erreur lors de la génération de réponse: {e}")
            return f"Erreur lors de la génération de réponse: {str(e)}"
    
    def generate_response_stream(self, 
                               messages: List[Dict[str, str]], 
                               max_tokens: int = None,
                               temperature: float = None,
                               top_p: float = None,
                               system_prompt: Optional[str] = None):
        """
        Génère une réponse en streaming à partir des messages via Ollama
        
        Args:
            messages: Liste des messages de conversation
            max_tokens: Nombre maximum de tokens (utilise Config.MAX_TOKENS si None)
            temperature: Température pour la génération (utilise Config.TEMPERATURE si None)
            top_p: Paramètre top_p pour la génération (utilise Config.TOP_P si None)
            system_prompt: Prompt système optionnel
            
        Yields:
            str: Fragments de réponse générés par le modèle
        """
        if self.debug_streaming:
            print(f"🌊🌊🌊 ENTRÉE DANS generate_response_stream() - STREAMING ACTIVÉ!")
            print(f"📋 Messages: {len(messages)}")
        
        try:
            # Utiliser les valeurs de configuration par défaut si non spécifiées
            from ..config import Config
            if max_tokens is None:
                max_tokens = Config.MAX_TOKENS
            if temperature is None:
                temperature = Config.TEMPERATURE
            if top_p is None:
                top_p = Config.TOP_P
                
            # Préparer les messages pour Ollama
            formatted_messages = []
            
            if system_prompt:
                formatted_messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            
            formatted_messages.extend(messages)
            
            # Payload pour l'API OpenAI compatible (vLLM) avec streaming activé
            payload = {
                "model": self.model_name,
                "messages": formatted_messages,
                "stream": True,  # Streaming activé
                "max_tokens": max_tokens if max_tokens > 0 else None,
                "temperature": temperature,
                "top_p": top_p
            }
            
            logger.info(f"🌊 Streaming LLM call à {self.chat_endpoint} avec {len(formatted_messages)} messages")
            if self.debug_streaming:
                print(f"🌊 LLM STREAMING CALL → phi-4 (vLLM/OpenAI)")
                print(f"📤 STREAMING INPUT: {json.dumps(payload, ensure_ascii=False)}")
                print(f"✅ STREAMING ACTIVÉ: stream=True")
                print("-" * 80)
            
            # Envoyer la requête à Ollama en streaming
            response = requests.post(
                self.chat_endpoint,
                headers=self.headers,
                json=payload,
                timeout=120,
                stream=True  # Streaming HTTP activé
            )
            
            response.raise_for_status()
            
            # Traiter la réponse en streaming OpenAI (SSE format)
            for line in response.iter_lines():
                if line:
                    try:
                        # Décoder la ligne
                        line_text = line.decode('utf-8')
                        
                        # Ignorer les lignes qui ne sont pas des données SSE
                        if not line_text.startswith('data: '):
                            continue
                            
                        # Extraire le JSON après "data: "
                        json_str = line_text[6:]  # Supprimer "data: "
                        
                        # Ignorer la ligne de fin "[DONE]"
                        if json_str.strip() == '[DONE]':
                            break
                            
                        # Parser le JSON
                        chunk_data = json.loads(json_str)
                        
                        # Extraire le contenu du chunk OpenAI
                        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                            choice = chunk_data["choices"][0]
                            if "delta" in choice and "content" in choice["delta"]:
                                content = choice["delta"]["content"]
                                if content:  # Ne yield que si il y a du contenu
                                    if self.debug_streaming:
                                        logger.debug(f"Chunk envoyé: '{content}'")
                                    yield content
                            
                            # Vérifier si c'est la fin du stream
                            if choice.get("finish_reason") is not None:
                                break
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"Erreur de parsing JSON chunk: {e}")
                        logger.warning(f"Ligne problématique: {line}")
                        continue
                        
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de connexion Ollama streaming: {e}")
            yield f"Erreur de connexion au modèle phi-2.7. Vérifiez que Ollama est démarré et que le modèle {self.model_name} est installé."
        except Exception as e:
            logger.error(f"Erreur lors de la génération de réponse streaming: {e}")
            yield f"Erreur lors de la génération de réponse: {str(e)}"
    
    def generate_rag_response(self, 
                            user_query: str, 
                            context_documents: List[Dict[str, Any]],
                            conversation_history: Optional[List[Dict[str, str]]] = None,
                            query_embedding: Optional[List[float]] = None) -> str:
        """
        Génère une réponse RAG basée sur les documents de contexte
        
        Args:
            user_query: Question de l'utilisateur
            context_documents: Documents de contexte récupérés
            conversation_history: Historique de conversation optionnel
            query_embedding: Embedding de la question (optionnel pour debug)
            
        Returns:
            str: Réponse générée avec contexte
        """
        print(f"❌❌❌ ATTENTION! ENTRÉE DANS generate_rag_response() - MÉTHODE NON-STREAMING!")
        print(f"📋 Question: {user_query[:50]}...")
        print(f"📄 Documents: {len(context_documents)}")
        print(f"🔍 Cette méthode ne devrait PAS être appelée!")
        
        try:
            # Construire le contexte à partir des documents
            context_text = self._build_context(context_documents)
            
            # Créer le prompt système pour RAG optimisé pour phi3.5:3.8b
            system_prompt = f"""You are a professional AI assistant specialized in document analysis and information retrieval. You provide accurate, well-structured answers based on provided documents.

CORE INSTRUCTIONS:
1. **Source-based answers**: Answer ONLY using information from the provided context documents
2. **Document references**: Do not reference documents in your answer
3. **Language consistency**: Always respond in the same language as the user's question
4. **Document list**: Always end with a complete list of referenced documents

CRITICAL LINK FORMAT:
- Each document in context shows: "Source: filename.ext (ID: complete_file_id)"
- Use the COMPLETE ID exactly as provided
- Format: [filename.ext]({self.base_url}/api/files/complete_file_id/decrypt)
- Example: If context shows "Source: role_library.pdf (ID: ebcc2e60-8a86-4b2f-9c7d-1234567890ab)"
  Write: [role_library.pdf]({self.base_url}/api/files/ebcc2e60-8a86-4b2f-9c7d-1234567890ab/decrypt)

RESPONSE STRUCTURE:
1. Provide a clear, comprehensive answer with natural document references
2. End with relevance assessment:

---
### 📊 Évaluation de la réponse
**Note de pertinence** : [Score]/10  
**Sources consultées** : [Number] document(s)

### 📄 Documents consultés
**Complete IDs**: Always use the COMPLETE ID provided in the context (do not truncate)
[List each unique document referenced with download link, no duplicates]
- [filename1.ext]({self.base_url}/api/files/complete_id1/decrypt)
- [filename2.ext]({self.base_url}/api/files/complete_id2/decrypt)

DOCUMENT CONTEXT:
{context_text}

CRITICAL: Use COMPLETE IDs exactly as provided in context - never truncate or modify them!
"""
            
            # Préparer les messages
            messages = []
            
            # Ajouter l'historique de conversation si fourni
            if conversation_history:
                messages.extend(conversation_history[-6:])  # Garder les 6 derniers échanges
            
            # Ajouter la question actuelle
            messages.append({
                "role": "user",
                "content": user_query
            })
            
            print(f"\n📋 HISTORIQUE CONVERSATION: {len(conversation_history) if conversation_history else 0} messages")
            print("🔍" * 40)
            
            # Générer la réponse avec paramètres configurables
            response = self.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=None,  # Utiliser Config.MAX_TOKENS
                temperature=None,  # Utiliser Config.TEMPERATURE
                top_p=None  # Utiliser Config.TOP_P
            )
            
            print("🔍" * 40)
            print("✅ FIN GÉNÉRATION RAG")
            print("🔍" * 40 + "\n")
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de réponse RAG: {e}")
            raise
    
    def generate_rag_response_stream(self, 
                                   user_query: str, 
                                   context_documents: List[Dict[str, Any]],
                                   conversation_history: Optional[List[Dict[str, str]]] = None,
                                   query_embedding: Optional[List[float]] = None):
        """
        Génère une réponse RAG en streaming basée sur les documents de contexte
        
        Args:
            user_query: Question de l'utilisateur
            context_documents: Documents de contexte récupérés
            conversation_history: Historique de conversation optionnel
            query_embedding: Embedding de la question (optionnel pour debug)
            
        Yields:
            str: Fragments de réponse générés avec contexte
        """
        print(f"🌊🌊🌊 ENTRÉE DANS generate_rag_response_stream() - STREAMING ACTIVÉ")
        print(f"📋 Question: {user_query[:50]}...")
        print(f"📄 Documents: {len(context_documents)}")
        
        try:
            # Construire le contexte à partir des documents
            context_text = self._build_context(context_documents)
            
            # Créer le prompt système pour RAG optimisé pour phi3.5:3.8b
            system_prompt = f"""You are a professional AI assistant specialized in document analysis and information retrieval. You provide accurate, well-structured answers based on provided documents.

CORE INSTRUCTIONS:
1. **Source-based answers**: Answer ONLY using information from the provided context documents
2. **Document references**: Do not reference documents in your answer
3. **Language consistency**: Always respond in the same language as the user's question
4. **Document list**: Always end with a complete list of referenced documents

CRITICAL LINK FORMAT:
- Each document in context shows: "Source: filename.ext (ID: complete_file_id)"
- Use the COMPLETE ID exactly as provided
- Format: [filename.ext]({self.base_url}/api/files/complete_file_id/decrypt)
- Example: If context shows "Source: role_library.pdf (ID: ebcc2e60-8a86-4b2f-9c7d-1234567890ab)"
  Write: [role_library.pdf]({self.base_url}/api/files/ebcc2e60-8a86-4b2f-9c7d-1234567890ab/decrypt)

RESPONSE STRUCTURE:
1. Provide a clear, comprehensive answer with natural document references
2. End with relevance assessment:

---
### 📊 Évaluation de la réponse
**Note de pertinence** : [Score]/10  
**Sources consultées** : [Number] document(s)

### 📄 Documents consultés
**Complete IDs**: Always use the COMPLETE ID provided in the context (do not truncate)
[List each unique document referenced with download link, no duplicates]
- [filename1.ext]({self.base_url}/api/files/complete_id1/decrypt)
- [filename2.ext]({self.base_url}/api/files/complete_id2/decrypt)

DOCUMENT CONTEXT:
{context_text}

CRITICAL: Use COMPLETE IDs exactly as provided in context - never truncate or modify them!
"""
            
            # Préparer les messages
            messages = []
            
            # Ajouter l'historique de conversation si fourni
            if conversation_history:
                messages.extend(conversation_history[-6:])  # Garder les 6 derniers échanges
            
            # Ajouter la question actuelle
            messages.append({
                "role": "user",
                "content": user_query
            })
            
            logger.info(f"🌊 Génération RAG streaming pour: {user_query[:100]}...")
            logger.info(f"📋 Historique conversation: {len(conversation_history) if conversation_history else 0} messages")
            
            # Générer la réponse en streaming avec paramètres configurables
            for chunk in self.generate_response_stream(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=None,  # Utiliser Config.MAX_TOKENS
                temperature=None,  # Utiliser Config.TEMPERATURE
                top_p=None  # Utiliser Config.TOP_P
            ):
                yield chunk
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de réponse RAG streaming: {e}")
            yield f"Erreur lors de la génération de réponse: {str(e)}"
    
    def _build_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        Construit le texte de contexte à partir des documents
        
        Args:
            documents: Liste des documents de contexte
            
        Returns:
            str: Contexte formaté
        """
        context_parts = []
        
        for i, doc in enumerate(documents, 1):
            file_name = doc.get("file_name", "Fichier inconnu")
            content = doc.get("content", "")
            file_id = doc.get("file_id", "")
            
            # Utiliser le vrai nom du fichier comme titre principal
            context_part = f"""
Source: {file_name} (ID: {file_id})
Content:
{content}
---
"""
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def process_response_links(self, response: str, base_url: str) -> str:
        """
        Traite les liens dans la réponse pour les convertir en liens de déchiffrement
        
        Args:
            response: Réponse du LLM
            base_url: URL de base de l'application
            
        Returns:
            str: Réponse avec liens traités
        """
        import re
        
        try:
            # Pattern pour détecter les références aux fichiers format [FICHIER:id:nom]
            file_pattern = r'\[FICHIER:([^:]+):([^\]]+)\]'
            
            # Pattern pour détecter les liens markdown existants avec file_id (AVEC /decrypt)
            markdown_pattern = r'\[([^\]]+)\]\(' + re.escape(base_url) + r'/api/files/([^/]+)/decrypt\)'
            
            # Pattern pour détecter les liens markdown SANS /decrypt (à corriger)
            incomplete_pattern = r'\[([^\]]+)\]\(' + re.escape(base_url) + r'/api/files/([^/)]+)\)'
            
            # Chercher tous les matchs
            file_matches = re.findall(file_pattern, response)
            markdown_matches = re.findall(markdown_pattern, response)
            incomplete_matches = re.findall(incomplete_pattern, response)
            
            def replace_file_link(match):
                file_id = match.group(1)
                file_name = match.group(2)
                decrypt_url = f"{base_url}/api/files/{file_id}/decrypt"
                return f'[{file_name}]({decrypt_url})'
                
            def fix_incomplete_link(match):
                file_name = match.group(1)
                file_id = match.group(2)
                decrypt_url = f"{base_url}/api/files/{file_id}/decrypt"
                return f'[{file_name}]({decrypt_url})'
            
            # Remplacer les références [FICHIER:...] par des liens
            processed_response = re.sub(file_pattern, replace_file_link, response)
            
            # Corriger les liens incomplets (sans /decrypt)
            processed_response = re.sub(incomplete_pattern, fix_incomplete_link, processed_response)
            
            return processed_response
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement des liens: {e}")
            return response
    
    def summarize_document(self, content: str, max_length: int = 500) -> str:
        """
        Résume un document
        
        Args:
            content: Contenu du document
            max_length: Longueur maximale du résumé
            
        Returns:
            str: Résumé du document
        """
        try:
            messages = [{
                "role": "user",
                "content": f"Summarize the following document in maximum {max_length} characters:\n\n{content}"
            }]
            
            system_prompt = "You are an expert in document summarization. Produce clear, concise and informative summaries. Respond in the same language as the input text."
            
            summary = self.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=200,
                temperature=0.3
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Erreur lors du résumé: {e}")
            return "Résumé non disponible"
    
    async def generate_rag_response_encrypted(self, 
                                      question: str, 
                                      conversation_history: List[Dict[str, str]] = None,
                                      search_service=None,
                                      embedding_service=None) -> str:
        """
        Génère une réponse RAG avec recherche chiffrée
        
        Args:
            question: Question de l'utilisateur
            conversation_history: Historique de conversation
            search_service: Service de recherche (fallback si pas de recherche chiffrée)
            embedding_service: Service d'embeddings
            
        Returns:
            str: Réponse générée avec contexte déchiffré
        """
        try:
            if not embedding_service:
                raise ValueError("Service d'embeddings requis pour la recherche")
            
            # Initialiser search_results
            search_results = None
            
            # 1. Générer embedding de la question
            question_embedding = embedding_service.generate_embedding(question)
            
            # 2. Recherche chiffrée ou normale
            if self.use_encrypted_search and self.encrypted_search_service:
                try:
                    # Chiffrer l'embedding avec la même clé que les documents indexés
                    encryption_context = self.encrypted_search_service.get_search_context()
                    
                    encrypted_query_vector = await self.encrypted_search_service.encrypt_query_vector(
                        question_embedding, 
                        encryption_context
                    )
                    
                    # Recherche sur données chiffrées
                    search_results = await self.encrypted_search_service.search_documents_encrypted(
                        query=question,
                        vector_query=encrypted_query_vector,
                        top=5
                    )
                    logger.info("🔍 Recherche sur données chiffrées effectuée")
                    
                except Exception as e:
                    logger.error(f"Erreur recherche chiffrée: {e}")
                    
                    if not search_service:
                        raise ValueError("Service de recherche requis en fallback")
                    
                    search_results = search_service.search_documents(
                        query=question, 
                        vector_query=question_embedding,
                        top=5
                    )
                
            else:
                if not search_service:
                    raise ValueError("Service de recherche requis en fallback")
                
                search_results = search_service.search_documents(
                    query=question, 
                    vector_query=question_embedding,
                    top=5
                )
            
            # Vérifier que search_results a été défini
            if search_results is None:
                raise ValueError("Aucun résultat de recherche obtenu")
            
            # 4. Les résultats sont automatiquement déchiffrés
            logger.info(f"📄 NOMBRE DE DOCUMENTS TROUVÉS: {len(search_results.get('results', []))}")
            
            # 5. Construction du contexte et génération de la réponse (inchangée)
            context = self._build_context(search_results["results"])
            
            # Construire l'historique de conversation
            if conversation_history is None:
                conversation_history = []
            
            logger.info(f"📋 HISTORIQUE CONVERSATION: {len(conversation_history)} messages")
            
            # Créer le prompt système pour RAG chiffré optimisé pour phi3.5:3.8b
            system_prompt = f"""You are a professional AI assistant specialized in document analysis and information retrieval. You provide accurate, well-structured answers based on provided documents.

CORE INSTRUCTIONS:
1. **Source-based answers**: Answer ONLY using information from the provided context documents
2. **Document references**: Reference context documents in your answer.
3. **Complete IDs**: Always use the COMPLETE ID provided in the context (do not truncate)
4. **Language consistency**: Always respond in the same language as the user's question
5. **Document list**: Always end with a complete list of referenced documents

CRITICAL LINK FORMAT:
- Each document in context shows: "Source: filename.ext (ID: complete_file_id)"
- Use the COMPLETE ID exactly as provided
- Format: [filename.ext]({self.base_url}/api/files/complete_file_id/decrypt)
- Example: If context shows "Source: role_library.pdf (ID: ebcc2e60-8a86-4b2f-9c7d-1234567890ab)"
  Write: [role_library.pdf]({self.base_url}/api/files/ebcc2e60-8a86-4b2f-9c7d-1234567890ab/decrypt)

RESPONSE STRUCTURE:
1. Provide a clear, comprehensive answer with natural document references
2. End with relevance assessment:

---
### 📊 Évaluation de la réponse
**Note de pertinence** : [Score]/10  

### 📄 Documents consultés
[List each unique document referenced with download link, check the filename.ext in the "Source:" to ensure no duplicate ]
- [filename1.ext]({self.base_url}/api/files/complete_id1/decrypt)
- [filename2.ext]({self.base_url}/api/files/complete_id2/decrypt)

DOCUMENT CONTEXT:
{context}

CRITICAL: Use COMPLETE IDs exactly as provided in context - never truncate or modify them!
"""
            
            # Préparer les messages
            messages = []
            
            # Ajouter l'historique de conversation si fourni
            if conversation_history:
                messages.extend(conversation_history[-6:])  # Garder les 6 derniers échanges
            
            # Ajouter la question actuelle
            messages.append({
                "role": "user",
                "content": question
            })
            
            # Générer la réponse avec paramètres configurables EN STREAMING
            full_response = ""
            for chunk in self.generate_response_stream(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=None,  # Utiliser Config.MAX_TOKENS
                temperature=None,  # Utiliser Config.TEMPERATURE
                top_p=None  # Utiliser Config.TOP_P
            ):
                full_response += chunk
            
            response = full_response
            
            logger.info("✅ FIN GÉNÉRATION RAG CHIFFRÉE")
            logger.info("🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍🔍")
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération RAG chiffrée: {e}")
            raise
    
    def generate_rag_response_encrypted_stream(self, 
                                      question: str, 
                                      conversation_history: List[Dict[str, str]] = None,
                                      search_service=None,
                                      embedding_service=None):
        """
        Génère une réponse RAG avec recherche chiffrée en streaming (version synchrone)
        
        Args:
            question: Question de l'utilisateur
            conversation_history: Historique de conversation
            search_service: Service de recherche (fallback si pas de recherche chiffrée)
            embedding_service: Service d'embeddings
            
        Yields:
            str: Fragments de réponse générés avec contexte déchiffré
        """
        try:
            if not embedding_service:
                yield "Erreur: Service d'embeddings requis pour la recherche"
                return
            
            # Initialiser search_results
            search_results = None
            
            # 1. Générer embedding de la question
            question_embedding = embedding_service.generate_embedding(question)
            
            # 2. Recherche chiffrée ou normale
            if self.use_encrypted_search and self.encrypted_search_service:
                try:
                    # Pour le streaming, on doit simuler async en utilisant la recherche normale
                    # car la recherche chiffrée est async mais le streaming est sync
                    logger.info("🔍 Fallback vers recherche normale pour streaming chiffré")
                    
                    if not search_service:
                        yield "Erreur: Service de recherche requis en fallback"
                        return
                    
                    search_results = search_service.search_documents(
                        query=question, 
                        vector_query=question_embedding,
                        top=5
                    )
                    
                except Exception as e:
                    logger.error(f"Erreur recherche fallback: {e}")
                    
                    if not search_service:
                        yield "Erreur: Service de recherche requis en fallback"
                        return
                    
                    search_results = search_service.search_documents(
                        query=question, 
                        vector_query=question_embedding,
                        top=5
                    )
                
            else:
                if not search_service:
                    yield "Erreur: Service de recherche requis en fallback"
                    return
                
                search_results = search_service.search_documents(
                    query=question, 
                    vector_query=question_embedding,
                    top=5
                )
            
            # Vérifier que search_results a été défini
            if search_results is None:
                yield "Erreur: Aucun résultat de recherche obtenu"
                return
            
            # 4. Les résultats sont automatiquement déchiffrés
            logger.info(f"📄 NOMBRE DE DOCUMENTS TROUVÉS: {len(search_results.get('results', []))}")
            
            # 5. Construction du contexte et génération de la réponse
            context = self._build_context(search_results["results"])
            
            # Construire l'historique de conversation
            if conversation_history is None:
                conversation_history = []
            
            logger.info(f"📋 HISTORIQUE CONVERSATION: {len(conversation_history)} messages")
            
            # Créer le prompt système pour RAG chiffré optimisé pour phi3.5:3.8b
            system_prompt = f"""You are a professional AI assistant specialized in document analysis and information retrieval. You provide accurate, well-structured answers based on provided documents.

CORE INSTRUCTIONS:
1. **Source-based answers**: Answer ONLY using information from the provided context documents
2. **Document references**: Reference context documents in your answer.
3. **Complete IDs**: Always use the COMPLETE ID provided in the context (do not truncate)
4. **Language consistency**: Always respond in the same language as the user's question
5. **Document list**: Always end with a complete list of referenced documents

CRITICAL LINK FORMAT:
- Each document in context shows: "Source: filename.ext (ID: complete_file_id)"
- Use the COMPLETE ID exactly as provided
- Format: [filename.ext]({self.base_url}/api/files/complete_file_id/decrypt)
- Example: If context shows "Source: role_library.pdf (ID: ebcc2e60-8a86-4b2f-9c7d-1234567890ab)"
  Write: [role_library.pdf]({self.base_url}/api/files/ebcc2e60-8a86-4b2f-9c7d-1234567890ab/decrypt)

RESPONSE STRUCTURE:
1. Provide a clear, comprehensive answer with natural document references
2. End with relevance assessment:

---
### 📊 Évaluation de la réponse
**Note de pertinence** : [Score]/10  

### 📄 Documents consultés
[List each unique document referenced with download link, check the filename.ext in the "Source:" to ensure no duplicate ]
- [filename1.ext]({self.base_url}/api/files/complete_id1/decrypt)
- [filename2.ext]({self.base_url}/api/files/complete_id2/decrypt)

DOCUMENT CONTEXT:
{context}

CRITICAL: Use COMPLETE IDs exactly as provided in context - never truncate or modify them!
"""
            
            # Préparer les messages
            messages = []
            
            # Ajouter l'historique de conversation si fourni
            if conversation_history:
                messages.extend(conversation_history[-6:])  # Garder les 6 derniers échanges
            
            # Ajouter la question actuelle
            messages.append({
                "role": "user",
                "content": question
            })
            
            logger.info("🌊 Génération RAG chiffrée streaming")
            
            # Générer la réponse en streaming avec paramètres configurables
            for chunk in self.generate_response_stream(
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=None,  # Utiliser Config.MAX_TOKENS
                temperature=None,  # Utiliser Config.TEMPERATURE
                top_p=None  # Utiliser Config.TOP_P
            ):
                yield chunk
            
            logger.info("✅ FIN GÉNÉRATION RAG CHIFFRÉE STREAMING")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération RAG chiffrée streaming: {e}")
            yield f"Erreur lors de la génération de réponse: {str(e)}"
    
    def extract_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """
        Extrait les mots-clés d'un document
        
        Args:
            content: Contenu du document
            max_keywords: Nombre maximum de mots-clés
            
        Returns:
            List[str]: Liste des mots-clés
        """
        try:
            messages = [{
                "role": "user",
                "content": f"Extract {max_keywords} main keywords from the following document. Respond only with the keywords separated by commas:\n\n{content}"
            }]
            
            keywords_response = self.generate_response(
                messages=messages,
                max_tokens=100,
                temperature=0.1
            )
            
            # Parser les mots-clés
            keywords = [kw.strip() for kw in keywords_response.split(",")]
            return keywords[:max_keywords]
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de mots-clés: {e}")
            return []
