# =============================================================================
# This file contains the definitions to use API paging on any Client API that
# requires a paging like mechanism.  Rather than define the paging routines
# into each client library, the "PagableClient" class is defined as a pythonic
# Protocol (aka "interface").  Any Client API that implements the methods
# defined in PagableClient can then be used to page data out of the Client API.
# =============================================================================

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import (
    Protocol,
    Any,
    Coroutine,
    Callable,
    List,
    Optional,
    Sequence,
    Iterator,
)
import asyncio

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["Pager"]

# -----------------------------------------------------------------------------
#
#                                       Pager
#
# -----------------------------------------------------------------------------


class Pager:
    """
    The Pager class is used to perform Client API "get-paging" functions as a
    consistent API using pythonic protocol types.  The Caller of Pager will
    either use the `all()` method or the `paginate()` method to obtain pages of
    data from Client API.

    For example, the NetboxClient is a PagableClient since that class defines
    the methods defined in the PagableClient class.  As such one could then do
    something like:

    async with NetboxClient() as nb:
        async with Pager(nb).all(
            nb.op.dcim_interfaces_list, params=dict(site="dnvr1")
        ) as pages:
            await pages
            for record in pages.data:
                # do something with each Netbox interface record.

    """

    def __init__(self, paging_client: "PagableClient", page_sz: Optional[int] = None):
        self.page_sz = page_sz
        self.tasks: Optional[List[Coroutine]] = list()
        self._paging_client = paging_client
        self._iter: Optional[Iterator] = None

        self.page_number = 0
        self.total_pages = 0
        self.total_items = 0

        self.data: Optional[Sequence] = None

    async def setup(self, call, params):
        await self._paging_client.pager_setup(self, call, params=params)
        self.total_pages = len(self.tasks)
        return self

    async def paginate(self, call, params):
        """
        Fetches a page of data from the client API call and yields a page of
        data at a time.
        """
        await self.setup(call, params)
        async for page in self:
            yield page

    async def all(
        self, call: Optional[Callable] = None, params: Optional[Any] = None
    ) -> List[Any]:
        """
        Concurrently fetches all pages of data and returns the list of pages.
        """
        if call:
            await self.setup(call, params)
        return await self

    def __await__(self):
        """
        Returns a list of pages-data for each page retrieved from the Client API.
        """

        pager = self

        async def _await_all_pages():
            pages = await asyncio.gather(*self.tasks)
            self.data = list()
            for page in pages:
                self.data.extend(
                    self._paging_client.pager_page_data(pager=self, page=page)
                )
            return pager.data

        return _await_all_pages().__await__()

    async def __anext__(self):
        if not (job := next(self._iter, None)):
            raise StopAsyncIteration

        res = await job
        self.data = self._paging_client.pager_page_data(pager=self, page=res)
        self.page_number += 1
        return self.data

    def __aiter__(self):
        self._iter = asyncio.as_completed(self.tasks)
        return self


# -----------------------------------------------------------------------------
#
#                           Protocol: PagableClient
#
# -----------------------------------------------------------------------------


class PagableClient(Protocol):
    """
    Pythonic type Protocol for any Client that needs a "paging" API to get
    large amounts of data out of the API.
    """

    async def pager_setup(self, pager: "Pager", call: Callable, params: Any):
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

        params: Any
            The query-filter parameters that are passed along to the
            Client implementation.
        """
        ...

    def pager_page_data(self, pager: "Pager", page: Any) -> Any:
        """
        The Client function that extracts the page data, typically a list of
        dicts, from page retreieved via the Client API.  The type of the page
        will be dependent on the Client.  For example a httpx.AsyncClient based
        Client will have page instances of type httpx.Response.

        Parameters
        ----------
        pager: Pager
            The pager instace, should the Client need it

        page: Any
            The Client response instance for which this `pager_page_data`
            function is used to extract the contents.

        Returns
        -------
        The Client method will return the body of the page data, typically a
        list of dict.
        """
        ...
