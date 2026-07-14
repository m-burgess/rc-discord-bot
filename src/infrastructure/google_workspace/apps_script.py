import urllib.parse
from typing import Dict

class GoogleAppsScriptHelper:
    def __init__(self, base_form_url: str = "https://docs.google.com/forms/d/e/1FAIpQLSfXYZ12345/viewform"):
        self.base_url = base_form_url

    def generate_prefilled_link(self, discord_id: str, username: str, entry_id_discord_id: str = "entry.1000001", entry_id_username: str = "entry.1000002") -> str:
        """
        Generates a prefilled Google Form URL containing the user's Discord ID and username
        so it can be linked to their account upon submission.
        """
        params = {
            entry_id_discord_id: discord_id,
            entry_id_username: username
        }
        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}?{query_string}"
