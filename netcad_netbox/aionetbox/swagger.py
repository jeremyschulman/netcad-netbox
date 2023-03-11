from typing import Callable, Optional
import json

import httpx


class SwaggerExecutor:
    def __init__(
        self,
        client: httpx.AsyncClient,
        specfile: Optional[str] = None,
        specdata: Optional[dict] = None,
    ):
        self.client = client
        self.oper_id_specs = dict()
        self.spec_data: dict = specdata or json.load(open(specfile))
        self.load(self.spec_data)

    def load(self, spec_data: dict):
        for api_path, api_body in spec_data["paths"].items():
            for path_op, path_body in api_body.items():
                if not isinstance(path_body, dict):
                    continue

                if not (oper_id := path_body.get("operationId")):
                    continue

                oper_id = oper_id.replace("-", "_")

                self.oper_id_specs[oper_id] = (path_op, api_path)

    def get_oper_spec(self, oper_id):
        if not (oper_data := self.oper_id_specs.get(oper_id)):
            raise ValueError(f"Unkknown operational-id: {oper_id}")

        return oper_data

    def _get_coro(self, oper_id: str) -> Callable:
        """
        Returns a coroutine that performs the function bound to the OpenAPI
        operational-ID name.

        Parameters
        ----------
        oper_id: str
            The API operational-ID name bound to the endpoint.

        Returns
        -------
        The specific AsyncClient command (get, post) coroutine that has been
        formed with calling arguments.  The Caller is responsible for awaiting
        the coroutine to do the actual API execution.
        """

        # oper_cmd is the command string, like "get" or "post"
        # oper_path is the API path endpoint, for example "/devices"

        oper_cmd, oper_path = self.get_oper_spec(oper_id)

        # if the API path contains parameters, then return a decorator so that
        # the URL path parameters can be passed in by the Caller.

        async def call_with_args(**kwargs):
            path_data = self.spec_data["paths"][oper_path]

            oper_params = path_data[oper_cmd].get("parameters", []) + path_data.get(
                "parameters", []
            )

            pathargs = {
                _op["name"]: kwargs.pop(_op["name"])
                for _op in oper_params
                if _op["in"] == "path"
            }

            return await getattr(self.client, oper_cmd)(
                url=oper_path.format(**pathargs), **kwargs
            )

        # return the coroutine (decorator) that will be used to await on
        # the API call.

        return call_with_args

    def __getattr__(self, oper_id):
        """Helper to use API operation by name"""
        return self._get_coro(oper_id)
