#!/usr/bin/env python3
"""
Client Python pour AzureAttestSKR - Secure Key Release avec attestation Azure.

Ce module permet d'appeler l'exécutable AzureAttestSKR pour chiffrer/déchiffrer des clés
en utilisant l'attestation Azure Confidential Computing.

Variables d'environnement requises:
- MAA_ENDPOINT: URL du service d'attestation Azure (ex: https://sharedweu.weu.attest.azure.net)
- KEYVAULT_KEY: URL complète de la clé Key Vault (ex: https://mykv.vault.azure.net/keys/mykey/version_GUID)

Variables d'environnement optionnelles:
- IMDS_CLIENT_ID: Client ID de l'identité managée pour IMDS (optionnel)

Usage programmatique:
    client = SKRClient()
    encrypted_key = client.wrap_key("ma_cle_secrete")
    decrypted_key = client.unwrap_key("cle_chiffree_base64")

Usage en ligne de commande (avec variables d'environnement):
- KEY: Clé secrète à chiffrer
- KEY_ENCRYPTED: Clé chiffrée à déchiffrer (base64)
    python skr_client.py wrap    # Chiffre la clé depuis KEY
    python skr_client.py unwrap  # Déchiffre la clé depuis KEY_ENCRYPTED
    
Mode debug:
    DEBUG=1 python skr_client.py wrap
"""

import os
import sys
import subprocess
import platform
import logging
from pathlib import Path
from typing import Optional


class SKRClient:
    """Client pour AzureAttestSKR."""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = self._setup_logging()
        self._validate_environment()
        
        # Variables d'environnement
        self.maa_endpoint = os.environ["MAA_ENDPOINT"]
        self.keyvault_key = os.environ["KEYVAULT_KEY"]
        self.imds_client_id = os.environ.get("IMDS_CLIENT_ID")  # Optionnel
        
        # Chemin vers l'exécutable (même répertoire que ce script)
        self.executable_path = Path(__file__).parent / "AzureAttestSKR"
        
        self.logger.info(f"Initialized SKRClient - MAA: {self.maa_endpoint}")
        self.logger.info(f"KeyVault Key: {self.keyvault_key}")
        if self.imds_client_id:
            self.logger.info(f"IMDS Client ID: {self.imds_client_id}")
        self.logger.info(f"Executable: {self.executable_path}")
    
    def _setup_logging(self) -> logging.Logger:
        """Configure le logging."""
        logger = logging.getLogger(__name__)
        
        if self.debug:
            level = logging.DEBUG
        else:
            level = logging.INFO
            
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[logging.StreamHandler()]
        )
        
        return logger
    
    def _validate_environment(self):
        """Valide l'environnement d'exécution."""
        # Vérifier Linux
        if platform.system() != "Linux":
            raise RuntimeError("Ce programme ne fonctionne que sur Linux")
        
        # Vérifier variables d'environnement requises
        required_vars = ["MAA_ENDPOINT", "KEYVAULT_KEY"]
        missing = [var for var in required_vars if not os.environ.get(var)]
        
        if missing:
            raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing)}")
    
    def _run_command(self, secret: str, operation: str) -> str:
        """Exécute AzureAttestSKR avec les paramètres donnés.
        
        Args:
            secret: La clé secrète ou la clé chiffrée
            operation: 'w' pour wrap, 'u' pour unwrap
            
        Returns:
            La sortie stdout de la commande
            
        Raises:
            FileNotFoundError: Si l'exécutable n'existe pas
            subprocess.CalledProcessError: Si la commande échoue
        """
        # Vérifier que l'exécutable existe
        if not self.executable_path.exists():
            raise FileNotFoundError(f"Exécutable introuvable: {self.executable_path}")
        
        if not os.access(self.executable_path, os.X_OK):
            raise PermissionError(f"Exécutable non exécutable: {self.executable_path}")
        
        # Construire la commande
        cmd = [
            "sudo",
            f"IMDS_CLIENT_ID={self.imds_client_id}",
            str(self.executable_path),
            "-a", self.maa_endpoint,
            "-k", self.keyvault_key,
            "-s", secret,
            f"-{operation}"
        ]
        
        self.logger.debug(f"Commande à exécuter: {' '.join(cmd)}")
        
        try:
            # Préparer l'environnement pour la commande
            env = os.environ.copy()
            if self.imds_client_id:
                env['IMDS_CLIENT_ID'] = self.imds_client_id
                self.logger.debug(f"IMDS_CLIENT_ID configuré dans l'environnement: {self.imds_client_id}")
            
            # Exécuter la commande
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # Timeout de 2 minutes
                check=True,
                env=env
            )
            
            self.logger.debug(f"Code de retour: {result.returncode}")
            self.logger.debug(f"Stdout: {result.stdout}")
            
            if result.stderr:
                self.logger.warning(f"Stderr: {result.stderr}")
            
            return result.stdout.strip()
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Erreur lors de l'exécution: {e}")
            self.logger.error(f"Stdout: {e.stdout}")
            self.logger.error(f"Stderr: {e.stderr}")
            raise
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Timeout lors de l'exécution: {e}")
            raise
    
    def wrap_key(self, key: str) -> str:
        """Chiffre la clé fournie en paramètre.
        
        Args:
            key: La clé secrète à chiffrer
        
        Returns:
            La clé chiffrée en base64
        """
        if not key:
            raise ValueError("La clé à chiffrer ne peut pas être vide")
        
        self.logger.info("=== DÉBUT CHIFFREMENT DE LA CLÉ ===")
        self.logger.info(f"Clé à chiffrer: {key[:10]}... (tronquée)")
        
        result = self._run_command(key, "w")
        
        self.logger.info("=== RÉSULTAT DU CHIFFREMENT ===")
        self.logger.info(f"Clé chiffrée: {result}")
        
        return result
    
    def unwrap_key(self, encrypted_key: str) -> str:
        """Déchiffre la clé chiffrée fournie en paramètre.
        
        Args:
            encrypted_key: La clé chiffrée à déchiffrer (base64)
        
        Returns:
            La clé déchiffrée en clair
        """
        if not encrypted_key:
            raise ValueError("La clé chiffrée à déchiffrer ne peut pas être vide")
        
        self.logger.info("=== DÉBUT DÉCHIFFREMENT DE LA CLÉ ===")
        self.logger.info(f"Clé chiffrée: {encrypted_key[:20]}... (tronquée)")
        
        result = self._run_command(encrypted_key, "u")
        
        self.logger.info("=== RÉSULTAT DU DÉCHIFFREMENT ===")
        self.logger.info(f"Clé déchiffrée: {result}")
        
        return result


def main():
    """Point d'entrée principal."""
    if len(sys.argv) != 2 or sys.argv[1] not in ["wrap", "unwrap"]:
        print("Usage: python skr_client.py [wrap|unwrap]")
        print()
        print("Variables d'environnement requises:")
        print("  MAA_ENDPOINT    - URL du service d'attestation")
        print("  KEYVAULT_KEY    - URL de la clé Key Vault")
        print("  KEY             - Clé à chiffrer (pour wrap)")
        print("  KEY_ENCRYPTED   - Clé chiffrée à déchiffrer (pour unwrap)")
        print()
        print("Variables d'environnement optionnelles:")
        print("  IMDS_CLIENT_ID  - Client ID de l'identité managée")
        print()
        print("Mode debug: DEBUG=1 python skr_client.py wrap")
        sys.exit(1)
    
    operation = sys.argv[1]
    debug = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
    
    try:
        client = SKRClient(debug=debug)
        
        if operation == "wrap":
            # Pour la compatibilité avec l'usage en ligne de commande
            key = os.environ.get("KEY", "")
            if not key:
                raise ValueError("Variable d'environnement KEY manquante pour le chiffrement")
            result = client.wrap_key(key)
            print(f"Clé chiffrée (base64): {result}")
        elif operation == "unwrap":
            # Pour la compatibilité avec l'usage en ligne de commande
            key_encrypted = os.environ.get("KEY_ENCRYPTED", "")
            if not key_encrypted:
                raise ValueError("Variable d'environnement KEY_ENCRYPTED manquante pour le déchiffrement")
            result = client.unwrap_key(key_encrypted)
            print(f"Clé déchiffrée: {result}")
            
    except Exception as e:
        print(f"Erreur: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()