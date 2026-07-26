import os
import logging
from dotenv import load_dotenv

# Try importing bitwarden-sdk, but handle ImportError gracefully
try:
    from bitwarden_sdk import BitwardenClient
    BITWARDEN_AVAILABLE = True
except ImportError:
    BITWARDEN_AVAILABLE = False

logger = logging.getLogger(__name__)

# Load local environment variables as fallback
load_dotenv()

class AppConfig:
    def __init__(self):
        self.discord_token = os.getenv("DISCORD_TOKEN", "")
        self.pco_app_id = os.getenv("PC_APP_ID", "")
        self.pco_secret = os.getenv("PC_SECRET", "")
        self.pco_form_url = os.getenv("PLANNING_CENTER_FORM_URL", "https://rcpeoria.churchcenter.com/people/forms/1098233")
        
        self.wing_ip = os.getenv("BEHRINGER_WING_IP", "127.0.0.1")
        self.wing_port = int(os.getenv("BEHRINGER_WING_PORT", "2223"))
        self.atem_ip = os.getenv("ATEM_IP", "127.0.0.1")
        self.blackmagic_camera_ip = os.getenv("BLACKMAGIC_CAMERA_IP", "127.0.0.1")
        
        self.bw_access_token = os.getenv("BITWARDEN_ACCESS_TOKEN", "")
        self.bw_org_id = os.getenv("BITWARDEN_ORGANIZATION_ID", "")

        if self.bw_access_token and self.bw_org_id and BITWARDEN_AVAILABLE:
            self._load_from_bitwarden()

    def _load_from_bitwarden(self):
        try:
            logger.info("Initializing Bitwarden Client...")
            client = BitwardenClient()
            
            # The python SDK requires stripping the prefix 'sm.' if present
            token = self.bw_access_token
            if token.startswith("sm."):
                token = token[3:]
                
            client.auth().login_access_token(token)
            
            # List all secret identifiers in the organization
            response = client.secrets().list(self.bw_org_id)
            
            # Iterate through the metadata and query actual values by UUID
            for secret in getattr(response.data, "data", []):
                key = getattr(secret, "key", "")
                secret_id = str(getattr(secret, "id", ""))
                
                if not key or not secret_id:
                    continue
                    
                if key == "Discord Token":
                    secret_val = client.secrets().get(secret_id)
                    self.discord_token = getattr(secret_val.data, "value", "")
                    logger.info("Retrieved Discord Token from Bitwarden.")
                elif key == "Planning Center Client ID":
                    secret_val = client.secrets().get(secret_id)
                    self.pco_app_id = getattr(secret_val.data, "value", "")
                    logger.info("Retrieved Planning Center Client ID from Bitwarden.")
                elif key == "Planning Center Token":
                    secret_val = client.secrets().get(secret_id)
                    self.pco_secret = getattr(secret_val.data, "value", "")
                    logger.info("Retrieved Planning Center Token from Bitwarden.")
                    
            logger.info("Bitwarden Secrets integration completed.")
        except Exception as e:
            logger.error(f"Failed to fetch secrets from Bitwarden: {e}. Using fallback environment variables.")

# Global config instance
config = AppConfig()
