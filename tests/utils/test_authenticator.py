from __future__ import annotations

import re
import uuid

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

import httpretty
import pytest
import requests

from cleo.io.null_io import NullIO

from poetry.utils.authenticator import Authenticator


if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock import MockerFixture

    from tests.conftest import Config
    from tests.conftest import DummyBackend


@dataclass
class SimpleCredential:
    username: str
    password: str


@pytest.fixture()
def mock_remote(http: type[httpretty.httpretty]) -> None:
    http.register_uri(
        http.GET,
        re.compile("^https?://foo.bar/(.+?)$"),
    )


def test_authenticator_uses_url_provided_credentials(
    config: Config, mock_remote: None, http: type[httpretty.httpretty]
):
    config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar/simple/"}},
            "http-basic": {"foo": {"username": "bar", "password": "baz"}},
        }
    )

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo001:bar002@foo.bar/files/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic Zm9vMDAxOmJhcjAwMg=="


def test_authenticator_uses_credentials_from_config_if_not_provided(
    config: Config, mock_remote: None, http: type[httpretty.httpretty]
):
    config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar/simple/"}},
            "http-basic": {"foo": {"username": "bar", "password": "baz"}},
        }
    )

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo.bar/simple/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic YmFyOmJheg=="


def test_authenticator_uses_credentials_from_config_matched_by_url_path(
    config: Config, mock_remote: None, http: type[httpretty.httpretty]
):
    config.merge(
        {
            "repositories": {
                "foo-alpha": {"url": "https://foo.bar/alpha/files/simple/"},
                "foo-beta": {"url": "https://foo.bar/beta/files/simple/"},
            },
            "http-basic": {
                "foo-alpha": {"username": "bar", "password": "alpha"},
                "foo-beta": {"username": "baz", "password": "beta"},
            },
        }
    )

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo.bar/alpha/files/simple/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic YmFyOmFscGhh"

    # Make request on second repository with the same netloc but different credentials
    authenticator.request("get", "https://foo.bar/beta/files/simple/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic YmF6OmJldGE="


def test_authenticator_uses_credentials_from_config_with_at_sign_in_path(
    config: Config, mock_remote: None, http: type[httpretty.httpretty]
):
    config.merge(
        {
            "repositories": {
                "foo": {"url": "https://foo.bar/beta/files/simple/"},
            },
            "http-basic": {
                "foo": {"username": "bar", "password": "baz"},
            },
        }
    )
    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo.bar/beta/files/simple/f@@-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic YmFyOmJheg=="


def test_authenticator_uses_username_only_credentials(
    config: Config,
    mock_remote: None,
    http: type[httpretty.httpretty],
    with_simple_keyring: None,
):
    config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar/simple/"}},
            "http-basic": {"foo": {"username": "bar", "password": "baz"}},
        }
    )

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo001@foo.bar/files/fo@o-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic Zm9vMDAxOg=="


def test_authenticator_uses_password_only_credentials(
    config: Config, mock_remote: None, http: type[httpretty.httpretty]
):
    config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar/simple/"}},
            "http-basic": {"foo": {"username": "bar", "password": "baz"}},
        }
    )

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://:bar002@foo.bar/files/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic OmJhcjAwMg=="


def test_authenticator_uses_empty_strings_as_default_password(
    config: Config,
    mock_remote: None,
    http: type[httpretty.httpretty],
    with_simple_keyring: None,
):
    config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar/simple/"}},
            "http-basic": {"foo": {"username": "bar"}},
        }
    )

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo.bar/simple/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic YmFyOg=="


def test_authenticator_uses_empty_strings_as_default_username(
    config: Config, mock_remote: None, http: type[httpretty.httpretty]
):
    config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar/simple/"}},
            "http-basic": {"foo": {"username": None, "password": "bar"}},
        }
    )

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo.bar/simple/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic OmJhcg=="


def test_authenticator_falls_back_to_keyring_url(
    config: Config,
    mock_remote: None,
    http: type[httpretty.httpretty],
    with_simple_keyring: None,
    dummy_keyring: DummyBackend,
):
    config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar/simple/"}},
        }
    )

    dummy_keyring.set_password(
        "https://foo.bar/simple/", None, SimpleCredential(None, "bar")
    )

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo.bar/simple/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic OmJhcg=="


def test_authenticator_falls_back_to_keyring_url_matched_by_path(
    config: Config,
    mock_remote: None,
    http: type[httpretty.httpretty],
    with_simple_keyring: None,
    dummy_keyring: DummyBackend,
):
    config.merge(
        {
            "repositories": {
                "foo-alpha": {"url": "https://foo.bar/alpha/files/simple/"},
                "foo-beta": {"url": "https://foo.bar/beta/files/simple/"},
            }
        }
    )

    dummy_keyring.set_password(
        "https://foo.bar/alpha/files/simple/", None, SimpleCredential(None, "bar")
    )
    dummy_keyring.set_password(
        "https://foo.bar/beta/files/simple/", None, SimpleCredential(None, "baz")
    )

    authenticator = Authenticator(config, NullIO())

    authenticator.request("get", "https://foo.bar/alpha/files/simple/foo-0.1.0.tar.gz")
    request = http.last_request()

    assert request.headers["Authorization"] == "Basic OmJhcg=="

    authenticator.request("get", "https://foo.bar/beta/files/simple/foo-0.1.0.tar.gz")
    request = http.last_request()

    assert request.headers["Authorization"] == "Basic OmJheg=="


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_authenticator_request_retries_on_exception(
    mocker: MockerFixture, config: Config, http: type[httpretty.httpretty]
):
    sleep = mocker.patch("time.sleep")
    sdist_uri = f"https://foo.bar/files/{uuid.uuid4()!s}/foo-0.1.0.tar.gz"
    content = str(uuid.uuid4())
    seen = []

    def callback(
        request: requests.Request, uri: str, response_headers: dict
    ) -> list[int | dict | str]:
        if seen.count(uri) < 2:
            seen.append(uri)
            raise requests.exceptions.ConnectionError("Disconnected")
        return [200, response_headers, content]

    httpretty.register_uri(httpretty.GET, sdist_uri, body=callback)

    authenticator = Authenticator(config, NullIO())
    response = authenticator.request("get", sdist_uri)
    assert response.text == content
    assert sleep.call_count == 2


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_authenticator_request_raises_exception_when_attempts_exhausted(
    mocker: MockerFixture, config: Config, http: type[httpretty.httpretty]
):
    sleep = mocker.patch("time.sleep")
    sdist_uri = f"https://foo.bar/files/{uuid.uuid4()!s}/foo-0.1.0.tar.gz"

    def callback(*_: Any, **___: Any) -> None:
        raise requests.exceptions.ConnectionError(str(uuid.uuid4()))

    httpretty.register_uri(httpretty.GET, sdist_uri, body=callback)
    authenticator = Authenticator(config, NullIO())

    with pytest.raises(requests.exceptions.ConnectionError):
        authenticator.request("get", sdist_uri)

    assert sleep.call_count == 5


@pytest.mark.parametrize(
    ["status", "attempts"],
    [
        (400, 0),
        (401, 0),
        (403, 0),
        (404, 0),
        (500, 0),
        (502, 5),
        (503, 5),
        (504, 5),
    ],
)
def test_authenticator_request_retries_on_status_code(
    mocker: MockerFixture,
    config: Config,
    http: type[httpretty.httpretty],
    status: int,
    attempts: int,
):
    sleep = mocker.patch("time.sleep")
    sdist_uri = f"https://foo.bar/files/{uuid.uuid4()!s}/foo-0.1.0.tar.gz"
    content = str(uuid.uuid4())

    def callback(
        request: requests.Request, uri: str, response_headers: dict
    ) -> list[int | dict | str]:
        return [status, response_headers, content]

    httpretty.register_uri(httpretty.GET, sdist_uri, body=callback)
    authenticator = Authenticator(config, NullIO())

    with pytest.raises(requests.exceptions.HTTPError) as excinfo:
        authenticator.request("get", sdist_uri)

    assert excinfo.value.response.status_code == status
    assert excinfo.value.response.text == content

    assert sleep.call_count == attempts


@pytest.fixture
def environment_repository_credentials(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("POETRY_HTTP_BASIC_FOO_USERNAME", "bar")
    monkeypatch.setenv("POETRY_HTTP_BASIC_FOO_PASSWORD", "baz")


def test_authenticator_uses_env_provided_credentials(
    config: Config,
    environ: None,
    mock_remote: type[httpretty.httpretty],
    http: type[httpretty.httpretty],
    environment_repository_credentials: None,
):
    config.merge({"repositories": {"foo": {"url": "https://foo.bar/simple/"}}})

    authenticator = Authenticator(config, NullIO())
    authenticator.request("get", "https://foo.bar/simple/foo-0.1.0.tar.gz")

    request = http.last_request()

    assert request.headers["Authorization"] == "Basic YmFyOmJheg=="


@pytest.fixture
def environment_repository_credentials_multiple_repositories(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("POETRY_HTTP_BASIC_FOO_ALPHA_USERNAME", "bar")
    monkeypatch.setenv("POETRY_HTTP_BASIC_FOO_ALPHA_PASSWORD", "alpha")
    monkeypatch.setenv("POETRY_HTTP_BASIC_FOO_BETA_USERNAME", "baz")
    monkeypatch.setenv("POETRY_HTTP_BASIC_FOO_BETA_PASSWORD", "beta")


def test_authenticator_uses_env_provided_credentials_matched_by_url_path(
    config: Config,
    environ: None,
    mock_remote: type[httpretty.httpretty],
    http: type[httpretty.httpretty],
    environment_repository_credentials_multiple_repositories: None,
):
    config.merge(
        {
            "repositories": {
                "foo-alpha": {"url": "https://foo.bar/alpha/files/simple/"},
                "foo-beta": {"url": "https://foo.bar/beta/files/simple/"},
            }
        }
    )

    authenticator = Authenticator(config, NullIO())

    authenticator.request("get", "https://foo.bar/alpha/files/simple/foo-0.1.0.tar.gz")
    request = http.last_request()

    assert request.headers["Authorization"] == "Basic YmFyOmFscGhh"

    authenticator.request("get", "https://foo.bar/beta/files/simple/foo-0.1.0.tar.gz")
    request = http.last_request()

    assert request.headers["Authorization"] == "Basic YmF6OmJldGE="
