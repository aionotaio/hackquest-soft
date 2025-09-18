import pyuseragents
import tls_requests
from better_proxy import Proxy


class BaseClient:
    WALLET_TYPES = ['io.metamask', 'io.rabby', 'app.phantom', 'me.rainbow']
    BASE_URL = "https://api.hackquest.io/graphql"

    access_token = ''
    current_phase_id = ''
    
    def __init__(self, proxy: Proxy | None = None) -> None:
        self.user_agent = pyuseragents.random()
        self.proxy = proxy
        self.session = tls_requests.Client(random_tls_extension_order=True, proxy=self.proxy.as_url if self.proxy else None)
        
    def _get_headers(self) -> dict[str, str]:
        return {
            "accept": "application/graphql-response+json",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "origin": "https://www.hackquest.io",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": "https://www.hackquest.io/",
            "sec-ch-ua": r"\"Chromium\";v=\"140\", \"Not=A?Brand\";v=\"24\", \"Google Chrome\";v=\"140\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": r"\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": self.user_agent
        }
