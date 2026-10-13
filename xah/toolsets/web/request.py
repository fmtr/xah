from enum import StrEnum
from typing import Annotated

from pydantic import Field

from corio import dm, https
from xah.toolsets.web.base import WebTool


class Method(StrEnum):
    """HTTP methods supported by the request tool."""

    DELETE = "DELETE"
    GET = "GET"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"
    POST = "POST"
    PUT = "PUT"


class Response(dm.Base):
    """The useful parts of an HTTP response returned to the model."""

    status_code: int = Field(description="The HTTP response status code.")
    headers: dict[str, str] = Field(description="The HTTP response headers.")
    body: str = Field(description="The response body as text.")


class Request(WebTool):
    """

    Make an HTTP request for API calls, testing, and basic un-rendered web or
    HTML calls. Do not use this tool for general web browsing, search, or
    research; use the other web tools instead.

    """

    url: Annotated[str, Field(description="The URL to request.")]
    method: Annotated[
        Method,
        Field(description="The HTTP method to use."),
    ] = Method.GET
    headers: Annotated[
        dict[str, str],
        Field(description="HTTP request headers."),
    ] = Field(default_factory=dict)
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

    async def run(self) -> Response:
        try:
            async with https.AsyncClient() as client:
                response = await client.request(
                    method=self.method,
                    url=self.url,
                    headers=self.headers,
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
