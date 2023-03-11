# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Optional, Dict, Callable, Any
import asyncio
from os import environ
from pathlib import Path

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

import httpx
from httpx import AsyncClient
from tenacity import retry, wait_exponential

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netinfra_tools.pager import Pager
from netinfra_tools.swagger import SwaggerExecutor

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["NetboxClient", "Pager"]


# -----------------------------------------------------------------------------
#
#                              CODE BEGINS
#
# -----------------------------------------------------------------------------

_g_module_dir = Path(__file__).parent


class NetboxClient(AsyncClient):
    ENV_VARS = ["NETBOX_ADDR", "NETBOX_TOKEN"]
    DEFAULT_TIMEOUT = 60
    DEFAULT_PAGE_SZ = 1000
    API_RATE_LIMIT = 100

    def __init__(self, base_url=None, token=None, **kwargs):
        try:
            url = base_url or environ["NETBOX_ADDR"]
            token = token or environ["NETBOX_TOKEN"]
        except KeyError as exc:
            raise RuntimeError(f"Missing environment variable: {exc.args[0]}")

        kwargs.setdefault("verify", False)
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)

        super().__init__(
            base_url=f"{url}/api",
            **kwargs,
        )
        self.headers["Authorization"] = f"Token {token}"
        self._api_s4 = asyncio.Semaphore(self.API_RATE_LIMIT)
        swagger_file = _g_module_dir / "openapi_spec3_3.json"
        self.op = SwaggerExecutor(client=self, specfile=str(swagger_file))

    # -------------------------------------------------------------------------
    #
    #                            Utility Functions
    #
    # -------------------------------------------------------------------------

    @staticmethod
    def parse_qfilter(expr: str) -> Dict:
        return dict(item.split(":", maxsplit=1) for item in expr.split(","))  # noqa

    @staticmethod
    def response_items(resp: dict):
        return resp["results"]

    # -------------------------------------------------------------------------
    #
    #                       httpx.AsyncClient Overloads
    #
    # -------------------------------------------------------------------------

    async def request(self, *vargs, **kwargs):
        @retry(wait=wait_exponential(multiplier=1, min=4, max=10))
        async def _do_rqst():
            res = await super(NetboxClient, self).request(*vargs, **kwargs)

            if res.status_code in [500]:
                print(f"Netbox API error: {res.text}, retrying")
                res.raise_for_status()

            return res

        async with self._api_s4:
            return await _do_rqst()

    # -------------------------------------------------------------------------
    #
    #                   pager.Pagable Protocol functions
    #
    # -------------------------------------------------------------------------

    async def pager_setup(
        self,
        pager: Pager,
        call: Callable,
        params: Optional[Dict] = None,
    ) -> "None":
        """
        The Pager setup is responsible for the following actions:
            (1) populate `pager.tasks` list with the coroutine calls required
                to fetch all the data from the Netbox API
            (2) populate `pager.total_items` with the total number of items
                that will be retrieved by the API.

        Parameters
        ----------
        pager: Pager
            The Pager instance that will fetch the pages of data asynchronously.

        call: Callable
            The Netbox API function that is used to fetch the Netbox data.
            This value is provided as the callable function and not the
            coroutine of that call.

        params: dict
            The query-filter parameters
        """
        params = params or {}
        params["limit"] = 1

        res = await call(params=params)
        res.raise_for_status()
        body = res.json()
        pager.total_items = body["count"]

        # create a list of tasks to run concurrently to fetch the data in
        # pages. NOTE: that we _MUST_ do a params.copy() to ensure that each
        # task has a unique offset count.  Observed that if copy not used then
        # all tasks have the same (last) value.

        params["limit"] = pager.page_sz or self.DEFAULT_PAGE_SZ

        for offset in range(0, pager.total_items, params["limit"]):
            params["offset"] = offset
            pager.tasks.append(call(params=params.copy()))

    def pager_page_data(self, pager: Pager, page: httpx.Response) -> Any:  # noqa
        """
        This Pager function is used to extract the page data out of a given
        page job; which was previously awaited for by the pager.  In the case
        of a Netbox client, this page is a httpx.Response instance since that
        is the result of a client "get" call.

        Parameters
        ----------
        pager: Pager
            The pager instance, not-used

        page: httpx.Response
            The result of the latest page fetch, which is a httpx.Response
            instance.

        Returns
        -------
        List[Dict] - the list of the Netbox objects for this API call.
        """
        if page.is_error:
            raise RuntimeError("Failed to execute next page")

        return page.json()["results"]
