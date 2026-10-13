from enum import StrEnum,  auto
from typing import Annotated

from pydantic import Field

from corio import dm, https
from xah.toolsets.web.base import WebTool


class Method(StrEnum):
    """HTTP methods supported by the request tool."""

    def _generate_next_value_(name, start, count, last_values):
        return name

    DELETE = auto()
    GET = auto()
    HEAD = auto()
    OPTIONS = auto()
    PATCH = auto()
    POST = auto()
    PUT = auto()


class Response(dm.Base):
    """The useful parts of an HTTP response returned to the model."""

    status_code: int = Field(description="The HTTP response status code.")
    headers: dict[str, str] = Field(description="The HTTP response headers.")
    body: str = Field(description="The response body as text.")


class RequestBase(WebTool):
    """Shared request fields and execution for HTTP API tools."""

    method: Annotated[
        Method,
        Field(description="The HTTP method to use."),
    ] = Method.GET
    body: Annotated[
        str | None,
        Field(description="Optional request body, such as JSON or form data."),
    ] = None
    params: Annotated[
        dict[str, str],
        Field(description="Optional URL query parameters."),
    ] = Field(default_factory=dict)
    timeout: Annotated[
        float,
        Field(description="Request timeout in seconds."),
    ] = 10.0
    follow_redirects: Annotated[
        bool,
        Field(description="Whether to follow HTTP redirects."),
    ] = True

    @property
    def request_url(self) -> str:
        raise NotImplementedError

    @property
    def request_headers(self) -> dict[str, str]:
        raise NotImplementedError

    async def run(self) -> Response:
        try:
            async with https.AsyncClient() as client:
                response = await client.request(
                    method=self.method,
                    url=self.request_url,
                    headers=self.request_headers,
                    content=self.body,
                    params=self.params,
                    timeout=self.timeout,
                    follow_redirects=self.follow_redirects,
                )
        except Exception as error:
            self.fail(error)

        return Response(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.text,
        )


class Request(RequestBase):
    """

    Make an HTTP request for API calls, testing, and basic un-rendered web or
    HTML calls. Do not use this tool for general web browsing, search, or
    research; use the other web tools instead.

    """

    url: Annotated[str, Field(description="The URL to request.")]
    headers: Annotated[
        dict[str, str],
        Field(description="HTTP request headers."),
    ] = Field(default_factory=dict)

    @property
    def request_url(self) -> str:
        return self.url

    @property
    def request_headers(self) -> dict[str, str]:
        return self.headers
