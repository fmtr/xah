import json
from email.message import Message
from enum import StrEnum, auto
from typing import Annotated
from urllib.parse import urlencode

import httpx
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


class ContentType(StrEnum):
    """Content types with special handling in the request tool."""

    HEADER = "Content-Type"
    HEADER_LOW = HEADER.lower()
    JSON = "application/json"
    FORM_URLENCODED = "application/x-www-form-urlencoded"

    @classmethod
    def parse(cls, header: str | None) -> str:
        if header is None:
            return ""

        message = Message()
        message[cls.HEADER] = header
        return message.get_content_type()


class Response(dm.Base):
    """The useful parts of an HTTP response returned to the model."""

    status_code: int = Field(description="The HTTP response status code.")
    headers: dict[str, str] = Field(description="The HTTP response headers.")
    body: str | dict = Field(description="The response body as text or structured data.")


class RequestBase(WebTool):
    """Shared request fields and execution for HTTP API tools."""

    method: Annotated[
        Method,
        Field(description="The HTTP method to use."),
    ] = Method.GET
    body: Annotated[
        str | dict | None,
        Field(description=f"Optional request body. Structured data is serialized from the {ContentType.HEADER} header."),
    ] = None
    include_headers: Annotated[
        bool,
        Field(description="Whether to include response headers."),
    ] = True
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

    @property
    def serialized_body(self) -> str | None:
        if self.body is None or isinstance(self.body, str):
            return self.body

        if self.request_content_type == ContentType.FORM_URLENCODED:
            return urlencode(self.body)

        return json.dumps(self.body)

    @property
    def request_content_type(self) -> str:
        headers = httpx.Headers(self.request_headers)
        header = headers.get(ContentType.HEADER_LOW)
        if header is None:
            return ContentType.JSON

        return ContentType.parse(header)

    async def run(self) -> Response:
        try:
            async with https.AsyncClient() as client:
                response = await client.request(
                    method=self.method,
                    url=self.request_url,
                    headers=self.request_headers,
                    content=self.serialized_body,
                    params=self.params,
                    timeout=self.timeout,
                    follow_redirects=self.follow_redirects,
                )
        except Exception as error:
            self.fail(error)

        response_headers = httpx.Headers(response.headers)
        response_content_type = response_headers.get(ContentType.HEADER_LOW, "")
        response_media_type = ContentType.parse(response_content_type)

        body: str | dict = response.text
        is_json = response_media_type == ContentType.JSON or response_media_type.endswith("+json")
        if is_json:
            body = json.loads(response.text)

        headers = dict(response_headers)
        if not self.include_headers:
            headers = {}

        return Response(
            status_code=response.status_code,
            headers=headers,
            body=body,
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
