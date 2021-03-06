from decimal import Decimal
from typing import Optional, Union
from datetime import datetime
from urllib3.util import Retry

from requests import Session
from requests.adapters import DEFAULT_POOLSIZE, HTTPAdapter


__all__ = ["CircleClient", "CIRCLE_DATETIME_FORMAT"]

DEFAULT_NUM_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.5
DEFAULT_TIMEOUT = 10
IDENTIFICATION_HEADERS = {
    "User-Agent": "django-polaris-circle/CircleClient",
    "X-Client-Name": "django-polaris-circle",
}
CIRCLE_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class CircleClient:
    def __init__(
        self,
        api_key: str,
        api_url: str,
        wallet_id: str,
        timeout: Optional[float] = DEFAULT_TIMEOUT,
        pool_size: int = DEFAULT_POOLSIZE,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        num_retries: int = DEFAULT_NUM_RETRIES,
        session: Optional[Session] = None,
    ):
        self.api_key = api_key
        self.url = api_url
        self.wallet_id = wallet_id
        self.timeout = timeout
        self.pool_size = pool_size
        self.num_retries = num_retries
        self.backoff_factor = backoff_factor

        retry = Retry(
            total=self.num_retries,
            backoff_factor=self.backoff_factor,
            redirect=0,
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            pool_connections=self.pool_size,
            pool_maxsize=self.pool_size,
            max_retries=retry,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            **IDENTIFICATION_HEADERS,
        }
        if session is None:
            session = Session()
            session.headers.update(headers)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
        self._session: Session = session

    def get_transfers(
        self,
        from_datetime: Optional[datetime] = None,
        to_datetime: Optional[datetime] = None,
        page_size: Optional[int] = None,
        wallet_id: Optional[str] = None,
        destination_wallet_id: Optional[str] = None,
        source_wallet_id: Optional[str] = None,
    ) -> dict:
        request_args = {}
        if from_datetime:
            request_args["from"] = datetime.strftime(
                from_datetime, CIRCLE_DATETIME_FORMAT
            )
        if to_datetime:
            request_args["to"] = datetime.strftime(to_datetime, CIRCLE_DATETIME_FORMAT)
        if wallet_id:
            if destination_wallet_id or source_wallet_id:
                raise ValueError(
                    "'wallet_id' cannot be specified with "
                    "'destination_wallet_id' or 'source_wallet_id'"
                )
            request_args["walletId"] = wallet_id
        if destination_wallet_id:
            request_args["destinationWalletId"] = destination_wallet_id
        if source_wallet_id:
            request_args["sourceWalletId"] = source_wallet_id
        if page_size:
            request_args["pageSize"] = page_size
        return self._session.get(
            f"{self.url}/transfers", params=request_args, timeout=self.timeout
        ).json()

    def get_transfer(self, transfer_id: str):
        return self._session.get(
            f"{self.url}/transfers/{transfer_id}", timeout=self.timeout
        ).json()

    def create_transfer(
        self,
        idempotency_key: str,
        account: str,
        amount: Union[Decimal, str],
        memo: Optional[str] = None,
    ) -> dict:
        return self._session.post(
            f"{self.url}/transfers",
            json={
                "idempotencyKey": idempotency_key,
                "source": {"type": "wallet", "id": self.wallet_id},
                "destination": {
                    "type": "blockchain",
                    "address": account,
                    "chain": "XLM",
                    "addressTag": memo or "",
                },
                "amount": {"amount": str(amount), "currency": "USD"},
            },
            timeout=self.timeout,
        ).json()

    def get_wallet(self) -> dict:
        optional_kwargs = {}
        if self.timeout:
            optional_kwargs["timeout"] = self.timeout
        return self._session.get(
            f"{self.url}/wallets/{self.wallet_id}", timeout=self.timeout
        ).json()

    def create_address(self, idempotency_key: str) -> dict:
        optional_kwargs = {}
        if self.timeout:
            optional_kwargs["timeout"] = self.timeout
        return self._session.post(
            f"{self.url}/wallets/{self.wallet_id}/addresses",
            json={"idempotencyKey": idempotency_key, "currency": "USD", "chain": "XLM"},
            timeout=self.timeout,
        ).json()

    def close(self) -> None:
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __str__(self):
        return (
            "<CircleClient ["
            f"wallet={self.wallet_id}, "
            f"timeout={self.timeout}, "
            f"num_retries={self.num_retries}, "
            f"pool_size={self.pool_size}, "
            f"backoff_factor={self.backoff_factor}, "
            f"session={self._session}, "
            "]>"
        )
