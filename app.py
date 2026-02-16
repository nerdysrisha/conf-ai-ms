"""
Application Flask principale pour le système RAG
"""
import os
import sys
import logging
import uuid
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename
from io import BytesIO

# Ajouter le répertoire src au path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config import Config
from src.services.encryption_service import EncryptionService
from src.services.azure_storage_service import AzureStorageService
from src.services.azure_search_service import AzureSearchService
from src.services.embedding_service import EmbeddingService
from src.services.llm_service import LLMService
from src.services.document_processor import DocumentProcessor

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Factory pour créer l'application Flask"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Configuration CORS
    CORS(app)
    
    # Initialisation des services
    try:
        Config.validate_config()
        
        # Services de base
        encryption_service = EncryptionService(
            keyvault_url=Config.AZURE_KEYVAULT_URL,
            enable_skr_mode=Config.ENABLE_SKR_MODE,
            skr_maa_endpoint=Config.SKR_MAA_ENDPOINT,
            skr_keyvault_key_url=Config.SKR_KEYVAULT_KEY_URL
        )
        storage_service = AzureStorageService(
            account_name=Config.AZURE_STORAGE_ACCOUNT_NAME,
            container_name=Config.AZURE_STORAGE_CONTAINER_NAME,
            connection_string=Config.AZURE_STORAGE_CONNECTION_STRING  # Fallback optionnel
        )
        
        # Services de chiffrement pour la recherche
        use_search_encryption = Config.ENABLE_SEARCH_ENCRYPTION
        logger.info(f"Chiffrement de la recherche: {'activé' if use_search_encryption else 'désactivé'}")
        
        if use_search_encryption:
            # Import conditionnel des services de chiffrement
            from src.services.encryption_key_service import EncryptionKeyService
            from src.services.ironcore_encryption_service import IroncoreEncryptionService
            from src.services.encrypted_azure_search_service import EncryptedAzureSearchService
            
            # Services de chiffrement
            key_service = EncryptionKeyService(encryption_service)
            ironcore_service = IroncoreEncryptionService(key_service)
            
            # Service de recherche chiffré
            search_service = EncryptedAzureSearchService(
                service_name=Config.AZURE_SEARCH_SERVICE_NAME,
                api_key=None,  # Utilise DefaultAzureCredential
                index_name=Config.AZURE_SEARCH_INDEX_NAME,
                vector_dimension=Config.NOMIC_EMBED_DIMENSION,
                encryption_service=ironcore_service,
                key_service=key_service
            )
            
            # Service de recherche normal pour fallback
            normal_search_service = AzureSearchService(
                service_name=Config.AZURE_SEARCH_SERVICE_NAME,
                api_key=None,  # Utilise DefaultAzureCredential
                index_name=Config.AZURE_SEARCH_INDEX_NAME,
                vector_dimension=Config.NOMIC_EMBED_DIMENSION
            )
        else:
            # Service de recherche normal uniquement
            search_service = AzureSearchService(
                service_name=Config.AZURE_SEARCH_SERVICE_NAME,
                api_key=None,  # Utilise DefaultAzureCredential
                index_name=Config.AZURE_SEARCH_INDEX_NAME,
                vector_dimension=Config.NOMIC_EMBED_DIMENSION
            )
            normal_search_service = None
        
        # Services communs
        embedding_service = EmbeddingService(
            Config.NOMIC_EMBED_ENDPOINT,
            Config.NOMIC_EMBED_API_KEY,
            Config.NOMIC_EMBED_MODEL,
            Config.NOMIC_EMBED_DIMENSION
        )
        
        # Service LLM avec support du chiffrement
        if use_search_encryption:
            llm_service = LLMService(
                Config.PHI_MODEL_ENDPOINT, 
                Config.PHI_MODEL_API_KEY, 
                Config.PHI_MODEL_NAME,
                encrypted_search_service=search_service,
                base_url=Config.APP_BASE_URL
            )
        else:
            llm_service = LLMService(
                Config.PHI_MODEL_ENDPOINT, 
                Config.PHI_MODEL_API_KEY, 
                Config.PHI_MODEL_NAME,
                base_url=Config.APP_BASE_URL
            )
        
        # Service de traitement de documents avec support du chiffrement
        document_processor = DocumentProcessor(
            Config.CHUNK_SIZE, 
            Config.CHUNK_OVERLAP,
            Config.AZURE_DOC_INTELLIGENCE_ENDPOINT,
            Config.AZURE_DOC_INTELLIGENCE_API_KEY,
            use_azure_doc_intelligence=True,
            use_encryption=use_search_encryption,
            search_service=normal_search_service,  # Service normal pour fallback
            encrypted_search_service=search_service if use_search_encryption else None,  # Service chiffré si activé
            use_smart_chunking=Config.USE_SMART_CHUNKING,
            smart_chunk_target_size=Config.SMART_CHUNK_TARGET_SIZE,
            smart_chunk_max_size=Config.SMART_CHUNK_MAX_SIZE,
            smart_chunk_overlap=Config.SMART_CHUNK_OVERLAP
        )
        
        # Vérifier que les clés de chiffrement existent
        # encryption_service.ensure_keys_exist()  # Commenté temporairement pour les tests
        
        logger.info("Services initialisés avec succès")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation des services: {e}")
        raise
    
    # Routes de l'API
    
    @app.route('/')
    def index():
        """Page d'accueil avec interface de chat"""
        return render_template('index.html')
    
    @app.route('/upload')
    def upload_page():
        """Page d'upload de fichiers"""
        return render_template('upload.html')
    
    @app.route('/config')
    def config_page():
        """Page de configuration LLM"""
        return render_template('config.html')
    
    @app.route('/api/health')
    def health_check():
        """Endpoint de vérification de santé"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'encryption': encryption_service.get_public_key() is not None,
                'storage': storage_service.blob_service_client is not None,
                'search': search_service.search_client is not None,
                'embeddings': embedding_service.endpoint is not None,
                'llm': llm_service.endpoint is not None,
                'document_processor': document_processor.doc_intelligence_service is not None
            },
            'extraction_capabilities': document_processor.get_extraction_capabilities()
        })
    
    @app.route('/api/extraction-info')
    def extraction_info():
        """Endpoint pour obtenir les informations sur les capacités d'extraction"""
        return jsonify(document_processor.get_extraction_capabilities())
    
    @app.route('/api/config/upload-timeout')
    def get_upload_timeout():
        """Retourne la configuration du timeout d'upload"""
        return jsonify({
            'upload_timeout_seconds': Config.UPLOAD_TIMEOUT_SECONDS,
            'upload_timeout_ms': Config.UPLOAD_TIMEOUT_SECONDS * 1000
        })
    
    @app.route('/api/upload', methods=['POST'])
    def upload_file():
        """Upload et chiffrement d'un fichier"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'Aucun fichier fourni'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'Nom de fichier vide'}), 400
            
            # Vérifier la taille du fichier
            file.seek(0, 2)  # Aller à la fin
            file_size = file.tell()
            file.seek(0)  # Revenir au début
            
            if file_size > Config.MAX_FILE_SIZE:
                return jsonify({'error': f'Fichier trop volumineux (max: {Config.MAX_FILE_SIZE} bytes)'}), 400
            
            # Vérifier le format de fichier
            if not document_processor.is_supported_format(file.filename):
                return jsonify({
                    'error': f'Format de fichier non supporté. Formats acceptés: {list(Config.ALLOWED_EXTENSIONS.keys())}'
                }), 400
            
            # Lire le contenu du fichier
            file.seek(0)  # S'assurer qu'on est au début avant de lire
            file_content = file.read()
            filename = secure_filename(file.filename)
            
            # Diagnostic du contenu du fichier
            logger.info(f"Fichier lu: {filename}, taille: {len(file_content)} bytes")
            logger.info(f"Premiers 50 bytes: {file_content[:50]}")
            
            # Vérifier que le contenu n'est pas vide
            if not file_content:
                return jsonify({'error': 'Le fichier est vide'}), 400
            
            # Traiter et indexer le document avec le DocumentProcessor (gère le chiffrement)
            logger.info(f"Traitement du fichier: {filename}")
            file_id = str(uuid.uuid4())
            
            # 1. Extraire le texte du document avec process_file
            processed_file = document_processor.process_file(file_content, filename, file_id)
            
            # 2. Indexer le contenu extrait avec process_and_index_document pour gérer le chiffrement
            extracted_text = processed_file.get('text_content', '')
            file_metadata = processed_file.get('metadata', {})
            
            metadata = {
                'filename': filename, 
                'uploaded_at': datetime.now().isoformat(),
                'extraction_method': file_metadata.get('extraction_method', 'unknown'),
                'mime_type': file_metadata.get('mime_type', 'unknown'),
                'chunks_count': file_metadata.get('chunks_count', 0)
            }
            
            import asyncio
            result = asyncio.run(document_processor.process_and_index_document(
                file_id=file_id,
                content=extracted_text,
                metadata=metadata,
                embedding_service=embedding_service
            ))
            
            if not result.get('success', False):
                return jsonify({
                    'error': f"Erreur lors du traitement: {result.get('error', 'Erreur inconnue')}"
                }), 500
            
            # Chiffrer et stocker le fichier original avec le même file_id
            encrypted_content = encryption_service.encrypt_data(file_content)
            stored_file_id = storage_service.upload_encrypted_file(
                encrypted_content,
                filename,
                {
                    'text_length': str(result.get('chunks_count', 0) * 500),  # Estimation
                    'chunks_count': str(result.get('chunks_count', 0))
                },
                file_id=file_id  # Utiliser le même ID pour maintenir la cohérence
            )
            
            logger.info(f"Fichier {filename} traité et indexé avec succès (ID: {file_id})")

            return jsonify({
                'success': True,
                'file_id': file_id,  # Utiliser file_id au lieu de stored_file_id pour la cohérence
                'filename': filename,
                'chunks_count': result.get('chunks_count', 0),
                'encryption_used': result.get('encryption_used', False)
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de l'upload: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/chat', methods=['POST'])
    def chat():
        """Endpoint de chat avec le LLM et support du chiffrement"""
        try:
            data = request.get_json()
            
            if not data or 'message' not in data:
                return jsonify({'error': 'Message manquant'}), 400
            
            user_message = data['message']
            conversation_history = data.get('history', [])
            
            # Vérifier si le chiffrement est activé
            if use_search_encryption and hasattr(llm_service, 'encrypted_search_service'):
                logger.info("🔒 MODE CHIFFRÉ ACTIVÉ - Utilisation de la recherche chiffrée pour le chat")
                print(f"🔒🔒🔒 CHEMIN CHIFFRÉ PRIS")
                
                def generate():
                    try:
                        # Utiliser la méthode RAG chiffrée en streaming (synchrone)
                        for chunk in llm_service.generate_rag_response_encrypted_stream(
                            question=user_message,
                            conversation_history=conversation_history,
                            search_service=normal_search_service,  # Fallback
                            embedding_service=embedding_service
                        ):
                            # Traiter les liens dans chaque chunk
                            base_url = Config.APP_BASE_URL
                            processed_chunk = llm_service.process_response_links(chunk, base_url)
                            
                            # S'assurer que le chunk n'est pas vide et est bien formaté
                            if processed_chunk and processed_chunk.strip():
                                chunk_data = {
                                    'chunk': processed_chunk
                                }
                                # Encoder en JSON de manière sûre
                                json_data = json.dumps(chunk_data, ensure_ascii=False)
                                yield f"data: {json_data}\n\n"
                        
                        # Envoyer les métadonnées de fin
                        final_data = {
                            'sources': [], 
                            'total_sources': 0, 
                            'done': True
                        }
                        json_final = json.dumps(final_data, ensure_ascii=False)
                        yield f"data: {json_final}\n\n"
                        
                    except Exception as e:
                        logger.error(f"Erreur lors du streaming chiffré: {e}")
                        error_data = {
                            'error': str(e), 
                            'done': True
                        }
                        json_error = json.dumps(error_data, ensure_ascii=False)
                        yield f"data: {json_error}\n\n"
                
                # Retourner une réponse Server-Sent Events
                return Response(
                    generate(),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type'
                    }
                )
            else:
                logger.info("🔓 MODE NORMAL ACTIVÉ - Utilisation de la recherche normale pour le chat")
                print(f"🔓🔓🔓 CHEMIN NORMAL PRIS")
                
                # Générer l'embedding de la question
                query_embedding = embedding_service.generate_embeddings(user_message)
                
                # Rechercher des documents pertinents
                search_results = search_service.search_documents(
                    query=user_message,
                    vector_query=query_embedding,
                    top=5
                )
                
                # Générer la réponse RAG normale avec streaming
                def generate():
                    print(f"🌊🌊🌊 GÉNÉRATEUR STREAMING NORMAL DÉMARRÉ")
                    try:
                        for chunk in llm_service.generate_rag_response_stream(
                            user_query=user_message,
                            context_documents=search_results['results'],
                            conversation_history=conversation_history,
                            query_embedding=query_embedding
                        ):
                            # Traiter les liens dans chaque chunk
                            base_url = Config.APP_BASE_URL
                            processed_chunk = llm_service.process_response_links(chunk, base_url)
                            
                            # S'assurer que le chunk n'est pas vide et est bien formaté
                            if processed_chunk and processed_chunk.strip():
                                chunk_data = {
                                    'chunk': processed_chunk
                                }
                                # Encoder en JSON de manière sûre
                                json_data = json.dumps(chunk_data, ensure_ascii=False)
                                yield f"data: {json_data}\n\n"
                        
                        # Envoyer les métadonnées de fin avec les sources
                        final_data = {
                            'sources': search_results['results'][:3],
                            'total_sources': search_results['total_count'],
                            'done': True
                        }
                        json_final = json.dumps(final_data, ensure_ascii=False)
                        yield f"data: {json_final}\n\n"
                        
                    except Exception as e:
                        logger.error(f"Erreur lors du streaming: {e}")
                        error_data = {
                            'error': str(e), 
                            'done': True
                        }
                        json_error = json.dumps(error_data, ensure_ascii=False)
                        yield f"data: {json_error}\n\n"
                
                # Retourner une réponse Server-Sent Events
                return Response(
                    generate(),
                    mimetype='text/event-stream',
                    headers={
                        'Cache-Control': 'no-cache',
                        'Connection': 'keep-alive',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': 'Content-Type'
                    }
                )
            
        except Exception as e:
            logger.error(f"Erreur lors du chat: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/chat/stream', methods=['POST'])
    def chat_stream():
        """Endpoint de chat en streaming avec le LLM et support du chiffrement"""
        try:
            data = request.get_json()
            
            if not data or 'message' not in data:
                return jsonify({'error': 'Message manquant'}), 400
            
            user_message = data['message']
            conversation_history = data.get('history', [])
            
            def generate():
                try:
                    # Vérifier si le chiffrement est activé
                    if use_search_encryption and hasattr(llm_service, 'encrypted_search_service'):
                        logger.info("🌊 Utilisation de la recherche chiffrée pour le chat streaming")
                        
                        # Faire d'abord la recherche chiffrée (non-streaming)
                        import asyncio
                        
                        # Générer l'embedding de la question
                        query_embedding = embedding_service.generate_embeddings(user_message)
                        
                        # Recherche chiffrée
                        try:
                            async def do_encrypted_search():
                                # Chiffrer l'embedding avec la même clé que les documents indexés
                                encryption_context = llm_service.encrypted_search_service.get_search_context()
                                
                                encrypted_query_vector = await llm_service.encrypted_search_service.encrypt_query_vector(
                                    query_embedding, 
                                    encryption_context
                                )
                                
                                # Recherche sur données chiffrées
                                return await llm_service.encrypted_search_service.search_documents_encrypted(
                                    query=user_message,
                                    vector_query=encrypted_query_vector,
                                    top=5
                                )
                            
                            search_results = asyncio.run(do_encrypted_search())
                            logger.info("🔍 Recherche sur données chiffrées effectuée")
                            
                        except Exception as e:
                            logger.error(f"Erreur recherche chiffrée: {e}")
                            # Fallback vers recherche normale
                            search_results = search_service.search_documents(
                                query=user_message,
                                vector_query=query_embedding,
                                top=5
                            )
                        
                        # Maintenant utiliser le streaming pour la génération avec les résultats
                        for chunk in llm_service.generate_rag_response_stream(
                            user_query=user_message,
                            context_documents=search_results['results'],
                            conversation_history=conversation_history,
                            query_embedding=query_embedding
                        ):
                            # Traiter les liens dans chaque chunk
                            base_url = Config.APP_BASE_URL
                            processed_chunk = llm_service.process_response_links(chunk, base_url)
                            
                            yield f"data: {json.dumps({'chunk': processed_chunk})}\n\n"
                        
                        # Envoyer les métadonnées de fin avec les sources
                        end_data = {
                            'sources': search_results['results'][:3],
                            'total_sources': search_results['total_count'],
                            'done': True
                        }
                        yield f"data: {json.dumps(end_data)}\n\n"
                        
                    else:
                        logger.info("Utilisation de la recherche normale pour le chat streaming")
                        
                        # Générer l'embedding de la question
                        query_embedding = embedding_service.generate_embeddings(user_message)
                        
                        # Rechercher des documents pertinents
                        search_results = search_service.search_documents(
                            query=user_message,
                            vector_query=query_embedding,
                            top=5
                        )
                        
                        # Générer la réponse RAG en streaming
                        for chunk in llm_service.generate_rag_response_stream(
                            user_query=user_message,
                            context_documents=search_results['results'],
                            conversation_history=conversation_history,
                            query_embedding=query_embedding
                        ):
                            # Traiter les liens dans chaque chunk
                            base_url = Config.APP_BASE_URL
                            processed_chunk = llm_service.process_response_links(chunk, base_url)
                            
                            yield f"data: {json.dumps({'chunk': processed_chunk})}\n\n"
                        
                        # Envoyer les métadonnées de fin avec les sources
                        end_data = {
                            'sources': search_results['results'][:3],
                            'total_sources': search_results['total_count'],
                            'done': True
                        }
                        yield f"data: {json.dumps(end_data)}\n\n"
                        
                except Exception as e:
                    logger.error(f"Erreur lors du streaming: {e}")
                    yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            
            # Retourner une réponse Server-Sent Events
            return Response(
                generate(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type'
                }
            )
            
        except Exception as e:
            logger.error(f"Erreur lors du chat streaming: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/embeddings', methods=['POST'])
    def generate_embeddings():
        """Endpoint pour générer des embeddings"""
        try:
            data = request.get_json()
            
            if not data or 'text' not in data:
                return jsonify({'error': 'Texte manquant'}), 400
            
            text = data['text']
            if isinstance(text, str):
                text = [text]
            
            embeddings = embedding_service.generate_embeddings(text)
            
            return jsonify({
                'success': True,
                'embeddings': embeddings,
                'dimension': embedding_service.dimension
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embeddings: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/files/<file_id>/decrypt')
    def decrypt_file(file_id):
        """Endpoint pour déchiffrer et télécharger un fichier"""
        try:
            logger.info(f"Tentative de téléchargement du fichier: {file_id}")
            
            # Télécharger le fichier chiffré
            encrypted_data, metadata = storage_service.download_encrypted_file(file_id)
            logger.info(f"Fichier chiffré téléchargé, taille: {len(encrypted_data)} caractères")
            
            # Déchiffrer le contenu
            decrypted_content = encryption_service.decrypt_data(encrypted_data)
            logger.info(f"Fichier déchiffré, taille: {len(decrypted_content)} bytes")
            
            # Préparer le téléchargement
            original_filename = metadata.get('original_filename', f'file_{file_id}')
            content_type = metadata.get('content_type', 'application/octet-stream')
            
            logger.info(f"Envoi du fichier: {original_filename} (type: {content_type})")
            
            return send_file(
                BytesIO(decrypted_content),
                download_name=original_filename,
                mimetype=content_type,
                as_attachment=True
            )
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement du fichier {file_id}: {e}")
            logger.error(f"Type d'erreur: {type(e).__name__}")
            return jsonify({'error': f'Erreur de déchiffrement: {str(e)}'}), 500
    
    @app.route('/api/files')
    def list_files():
        """Liste les fichiers stockés"""
        try:
            files = storage_service.list_files()
            return jsonify({
                'success': True,
                'files': files
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la liste des fichiers: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/files/all-links')
    def list_all_files_with_links():
        """Liste tous les fichiers avec leurs liens de téléchargement formatés"""
        try:
            files = storage_service.list_files()
            base_url = Config.APP_BASE_URL  # Utiliser l'URL configurée au lieu de request.url_root
            
            # Générer une réponse avec tous les liens
            response_parts = ["Voici tous les documents disponibles avec leurs liens de téléchargement :\n"]
            
            for i, file_info in enumerate(files, 1):
                file_id = file_info['file_id']
                filename = file_info.get('metadata', {}).get('original_filename', f'Fichier {i}')
                download_url = f"{base_url}/api/files/{file_id}/decrypt"
                
                response_parts.append(f"{i}. [{filename}]({download_url})")
            
            formatted_response = "\n".join(response_parts)
            
            return jsonify({
                'success': True,
                'response': formatted_response,
                'files_count': len(files)
            })
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération des liens: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/files/<file_id>', methods=['DELETE'])
    def delete_file(file_id):
        """Supprime un fichier et ses documents associés"""
        try:
            # Supprimer les documents de l'index de recherche
            search_service.delete_documents_by_file_id(file_id)
            
            # Supprimer le fichier du stockage
            success = storage_service.delete_file(file_id)
            
            if success:
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Échec de la suppression'}), 500
                
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du fichier {file_id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/search')
    def search():
        """Endpoint de recherche dans les documents"""
        try:
            query = request.args.get('q', '')
            top = int(request.args.get('top', 10))
            
            if not query:
                return jsonify({'error': 'Paramètre de requête "q" manquant'}), 400
            
            # Générer l'embedding de la requête
            query_embedding = embedding_service.generate_embeddings(query)
            
            # Rechercher
            results = search_service.search_documents(
                query=query,
                vector_query=query_embedding,
                top=top
            )
            
            return jsonify(results)
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint non trouvé'}), 404
    
    @app.route('/api/test-prompt', methods=['POST'])
    def test_prompt():
        """Endpoint de test pour voir les prompts envoyés à phi"""
        try:
            data = request.get_json()
            query = data.get('query', 'What benefits are available to employees?')
            
            # Générer l'embedding de la question pour la recherche
            query_embedding = embedding_service.generate_embeddings(query)
            
            # Rechercher des documents
            search_results = search_service.search_documents(
                query=query,
                vector_query=query_embedding,
                top=3
            )
            documents = search_results['results']
            
            print(f"\n🧪 ENDPOINT DE TEST - QUESTION: {query}")
            print(f"📄 Documents trouvés: {len(documents)}")
            
            # Utiliser le service RAG streaming pour générer une réponse
            # Cela va déclencher tout le logging détaillé avec streaming
            full_answer = ""
            for chunk in llm_service.generate_rag_response_stream(
                user_query=query, 
                context_documents=documents,
                query_embedding=query_embedding
            ):
                full_answer += chunk
            
            return jsonify({
                'success': True,
                'query': query,
                'documents_found': len(documents),
                'answer': full_answer,
                'documents': [
                    {
                        'title': doc.get('title', ''),
                        'content_preview': doc.get('content', '')[:200] + '...'
                    }
                    for doc in documents
                ]
            })
            
        except Exception as e:
            logger.error(f"Erreur test prompt: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/encryption/status', methods=['GET'])
    def encryption_status():
        """Endpoint pour vérifier le statut du chiffrement"""
        try:
            status = {
                "encryption_enabled": use_search_encryption,
                "services": {
                    "search_encryption": use_search_encryption,
                    "ironcore_available": False,
                    "key_vault_available": True
                }
            }
            
            # Vérifier le statut du service de chiffrement si activé
            if use_search_encryption and hasattr(search_service, 'get_encryption_status'):
                encryption_details = search_service.get_encryption_status()
                status.update(encryption_details)
            
            return jsonify(status)
            
        except Exception as e:
            logger.error(f"Erreur statut chiffrement: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/llm/config', methods=['GET', 'POST'])
    def llm_config():
        """Endpoint pour consulter/modifier la configuration LLM"""
        try:
            if request.method == 'GET':
                # Retourner la configuration actuelle
                return jsonify({
                    'model': Config.PHI_MODEL_NAME,
                    'max_tokens': Config.MAX_TOKENS,
                    'temperature': Config.TEMPERATURE,
                    'top_p': Config.TOP_P,
                    'endpoint': Config.PHI_MODEL_ENDPOINT
                })
            
            elif request.method == 'POST':
                # Modifier la configuration temporairement (en mémoire)
                data = request.get_json()
                
                if 'temperature' in data:
                    temp_val = float(data['temperature'])
                    if 0.0 <= temp_val <= 2.0:
                        Config.TEMPERATURE = temp_val
                        logger.info(f"Temperature mise à jour: {temp_val}")
                    else:
                        return jsonify({'error': 'Temperature doit être entre 0.0 et 2.0'}), 400
                
                if 'top_p' in data:
                    top_p_val = float(data['top_p'])
                    if 0.0 <= top_p_val <= 1.0:
                        Config.TOP_P = top_p_val
                        logger.info(f"Top_p mis à jour: {top_p_val}")
                    else:
                        return jsonify({'error': 'Top_p doit être entre 0.0 et 1.0'}), 400
                
                if 'max_tokens' in data:
                    max_tokens_val = int(data['max_tokens'])
                    if 1 <= max_tokens_val <= 8192:
                        Config.MAX_TOKENS = max_tokens_val
                        logger.info(f"Max_tokens mis à jour: {max_tokens_val}")
                    else:
                        return jsonify({'error': 'Max_tokens doit être entre 1 et 8192'}), 400
                
                return jsonify({
                    'success': True,
                    'message': 'Configuration LLM mise à jour',
                    'config': {
                        'temperature': Config.TEMPERATURE,
                        'top_p': Config.TOP_P,
                        'max_tokens': Config.MAX_TOKENS
                    }
                })
                
        except Exception as e:
            logger.error(f"Erreur configuration LLM: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Erreur interne du serveur'}), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Configuration des timeouts pour éviter les 504 Gateway Timeout
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
        threaded=True,  # Support des requêtes multiples
        request_handler=None  # Utiliser le handler par défaut
    )
