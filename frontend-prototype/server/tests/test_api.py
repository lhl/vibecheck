from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

import httpx
import pytest
from fastapi.testclient import TestClient

from server.app import UpstreamAPIError, app, describe_image, open_tts_stream, transcribe_audio


class FakeClient:
    async def aclose(self) -> None:
        return None


class FakeUpstreamResponse:
    def __init__(self, chunks: Iterable[bytes]) -> None:
        self._chunks = iter(chunks)

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_get_voices_returns_static_list(client: TestClient) -> None:
    response = client.get('/api/voices')

    assert response.status_code == 200
    payload = response.json()
    assert 'voices' in payload
    assert isinstance(payload['voices'], list)
    assert payload['voices']
    assert all('voice_id' in voice and 'name' in voice for voice in payload['voices'])


def test_get_voices_includes_requested_japanese_names(client: TestClient) -> None:
    response = client.get('/api/voices')

    assert response.status_code == 200
    names = {voice['name'] for voice in response.json()['voices']}
    assert {'Kuon', 'Hinata', 'Otani'}.issubset(names)


def test_get_voices_includes_language_tags(client: TestClient) -> None:
    response = client.get('/api/voices')

    assert response.status_code == 200
    payload = response.json()
    assert all(voice.get('language') in {'EN', 'JP'} for voice in payload['voices'])

    language_by_name = {voice['name']: voice['language'] for voice in payload['voices']}
    assert language_by_name['George'] == 'EN'
    assert language_by_name['Bella'] == 'EN'
    assert language_by_name['Adam'] == 'EN'
    assert language_by_name['Kuon'] == 'JP'
    assert language_by_name['Hinata'] == 'JP'
    assert language_by_name['Otani'] == 'JP'


def test_stt_missing_audio_returns_422(client: TestClient) -> None:
    response = client.post('/api/stt', data={'language': 'en'})

    assert response.status_code == 422


def test_stt_short_audio_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    response = client.post(
        '/api/stt',
        data={'language': 'en'},
        files={'audio': ('sample.webm', b'123', 'audio/webm')},
    )

    assert response.status_code == 400
    assert 'too short' in response.json()['detail'].lower()


def test_stt_oversized_audio_returns_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')
    monkeypatch.setenv('STT_MAX_UPLOAD_BYTES', '8')

    response = client.post(
        '/api/stt',
        data={'language': 'en'},
        files={'audio': ('sample.webm', b'a' * 16, 'audio/webm')},
    )

    assert response.status_code == 413
    assert 'too large' in response.json()['detail'].lower()


def test_stt_missing_api_key_returns_500(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('MISTRAL_API_KEY', raising=False)

    response = client.post(
        '/api/stt',
        data={'language': 'en'},
        files={'audio': ('sample.webm', b'a' * 4096, 'audio/webm')},
    )

    assert response.status_code == 500
    assert 'MISTRAL_API_KEY' in response.json()['detail']


def test_stt_success_returns_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_transcribe(**_: object) -> str:
        return 'hello world'

    monkeypatch.setattr('server.app.transcribe_audio', fake_transcribe)

    response = client.post(
        '/api/stt',
        data={'language': 'en'},
        files={'audio': ('sample.webm', b'a' * 4096, 'audio/webm')},
    )

    assert response.status_code == 200
    assert response.json() == {'text': 'hello world', 'language': 'en'}


def test_stt_maps_upstream_rate_limit(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_transcribe(**_: object) -> str:
        raise UpstreamAPIError(status_code=429, detail='rate limited')

    monkeypatch.setattr('server.app.transcribe_audio', fake_transcribe)

    response = client.post(
        '/api/stt',
        data={'language': 'en'},
        files={'audio': ('sample.webm', b'a' * 4096, 'audio/webm')},
    )

    assert response.status_code == 429


def test_stt_maps_upstream_auth_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_transcribe(**_: object) -> str:
        raise UpstreamAPIError(status_code=401, detail='invalid key')

    monkeypatch.setattr('server.app.transcribe_audio', fake_transcribe)

    response = client.post(
        '/api/stt',
        data={'language': 'en'},
        files={'audio': ('sample.webm', b'a' * 4096, 'audio/webm')},
    )

    assert response.status_code == 502


def test_tts_missing_api_key_returns_500(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)

    response = client.post('/api/tts', json={'text': 'hello', 'voice_id': 'voice-1'})

    assert response.status_code == 500
    assert 'ELEVENLABS_API_KEY' in response.json()['detail']


def test_tts_empty_text_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-key')

    response = client.post('/api/tts', json={'text': '   ', 'voice_id': 'voice-1'})

    assert response.status_code == 422
    assert 'text' in str(response.json()['detail']).lower()


def test_tts_success_returns_audio(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-key')

    async def fake_open_stream(**_: object) -> tuple[FakeClient, FakeUpstreamResponse]:
        return FakeClient(), FakeUpstreamResponse([b'ID3', b'audio-bytes'])

    monkeypatch.setattr('server.app.open_tts_stream', fake_open_stream)

    response = client.post('/api/tts', json={'text': 'hello', 'voice_id': 'voice-1'})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('audio/mpeg')
    assert response.content.startswith(b'ID3')


def test_tts_reads_upstream_stream_in_single_pass(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-key')

    class SinglePassResponse:
        def __init__(self) -> None:
            self._iterated = False
            self._chunks = [b'ID3', b'audio-bytes']

        async def aiter_bytes(self) -> AsyncIterator[bytes]:
            if self._iterated:
                raise httpx.StreamConsumed()
            self._iterated = True
            for chunk in self._chunks:
                yield chunk

        async def aclose(self) -> None:
            return None

    async def fake_open_stream(**_: object) -> tuple[FakeClient, SinglePassResponse]:
        return FakeClient(), SinglePassResponse()

    monkeypatch.setattr('server.app.open_tts_stream', fake_open_stream)

    response = client.post('/api/tts', json={'text': 'hello', 'voice_id': 'voice-1'})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('audio/mpeg')
    assert response.content == b'ID3audio-bytes'


def test_tts_maps_upstream_errors(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-key')

    async def fake_open_stream(**_: object) -> tuple[FakeClient, FakeUpstreamResponse]:
        raise UpstreamAPIError(status_code=502, detail='upstream failure')

    monkeypatch.setattr('server.app.open_tts_stream', fake_open_stream)

    response = client.post('/api/tts', json={'text': 'hello', 'voice_id': 'voice-1'})

    assert response.status_code == 502


def test_tts_empty_upstream_audio_returns_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-key')

    async def fake_open_stream(**_: object) -> tuple[FakeClient, FakeUpstreamResponse]:
        return FakeClient(), FakeUpstreamResponse([])

    monkeypatch.setattr('server.app.open_tts_stream', fake_open_stream)

    response = client.post('/api/tts', json={'text': 'hello', 'voice_id': 'voice-1'})

    assert response.status_code == 502


def test_vision_success_returns_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_describe_image(**kwargs: object) -> str:
        assert kwargs['api_key'] == 'test-key'
        assert kwargs['image_bytes'] == b'image-bytes'
        assert kwargs['mime_type'] == 'image/jpeg'
        return 'A photo of a city skyline at dusk.'

    monkeypatch.setattr('server.app.describe_image', fake_describe_image)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'image-bytes', 'image/jpeg')},
    )

    assert response.status_code == 200
    assert response.json() == {
        'text': 'A photo of a city skyline at dusk.',
        'prompt': 'Describe this image',
        'model': 'mistral-large-latest',
    }


def test_vision_missing_image_returns_400(client: TestClient) -> None:
    response = client.post('/api/vision')

    assert response.status_code == 400
    assert 'detail' in response.json()


def test_vision_unsupported_mime_returns_415(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fail_if_called(**_: object) -> str:
        raise AssertionError('describe_image should not be called for unsupported MIME types')

    monkeypatch.setattr('server.app.describe_image', fail_if_called)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.gif', b'GIF89a', 'image/gif')},
    )

    assert response.status_code == 415
    payload = response.json()
    assert 'detail' in payload
    assert 'unsupported' in payload['detail'].lower()


def test_vision_oversized_payload_returns_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')
    monkeypatch.setenv('VISION_MAX_UPLOAD_BYTES', '8')

    async def fail_if_called(**_: object) -> str:
        raise AssertionError('describe_image should not be called for oversized images')

    monkeypatch.setattr('server.app.describe_image', fail_if_called)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.png', b'123456789', 'image/png')},
    )

    assert response.status_code == 413
    payload = response.json()
    assert 'detail' in payload
    assert 'too large' in payload['detail'].lower()


def test_vision_empty_image_returns_400(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'', 'image/jpeg')},
    )

    assert response.status_code == 400
    payload = response.json()
    assert 'detail' in payload
    assert 'empty' in payload['detail'].lower()


def test_vision_invalid_max_upload_env_returns_500_detail(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')
    monkeypatch.setenv('VISION_MAX_UPLOAD_BYTES', 'not-an-int')

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'abc', 'image/jpeg')},
    )

    assert response.status_code == 500
    assert response.headers['content-type'].startswith('application/json')
    payload = response.json()
    assert 'detail' in payload
    assert 'VISION_MAX_UPLOAD_BYTES' in payload['detail']


def test_vision_non_positive_max_upload_env_returns_500_detail(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')
    monkeypatch.setenv('VISION_MAX_UPLOAD_BYTES', '0')

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'abc', 'image/jpeg')},
    )

    assert response.status_code == 500
    assert response.headers['content-type'].startswith('application/json')
    payload = response.json()
    assert payload == {'detail': 'VISION_MAX_UPLOAD_BYTES must be greater than 0'}


def test_vision_missing_api_key_returns_500(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('MISTRAL_API_KEY', raising=False)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'image-bytes', 'image/jpeg')},
    )

    assert response.status_code == 500
    payload = response.json()
    assert 'detail' in payload
    assert 'MISTRAL_API_KEY' in payload['detail']


def test_vision_maps_rate_limit_to_429(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_describe_image(**_: object) -> str:
        raise UpstreamAPIError(status_code=429, detail='rate limited')

    monkeypatch.setattr('server.app.describe_image', fake_describe_image)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'image-bytes', 'image/jpeg')},
    )

    assert response.status_code == 429
    assert 'detail' in response.json()


def test_vision_maps_upstream_auth_failure_to_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_describe_image(**_: object) -> str:
        raise UpstreamAPIError(status_code=401, detail='invalid key')

    monkeypatch.setattr('server.app.describe_image', fake_describe_image)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'image-bytes', 'image/jpeg')},
    )

    assert response.status_code == 502
    assert 'detail' in response.json()


def test_vision_maps_transport_failure_to_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_describe_image(**_: object) -> str:
        raise UpstreamAPIError(status_code=502, detail='transport error')

    monkeypatch.setattr('server.app.describe_image', fake_describe_image)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'image-bytes', 'image/jpeg')},
    )

    assert response.status_code == 502
    assert response.json() == {'detail': 'Vision upstream unavailable'}


def test_vision_maps_empty_upstream_content_to_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_describe_image(**_: object) -> str:
        raise UpstreamAPIError(status_code=502, detail='Vision upstream returned empty content')

    monkeypatch.setattr('server.app.describe_image', fake_describe_image)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'image-bytes', 'image/jpeg')},
    )

    assert response.status_code == 502
    assert response.json() == {'detail': 'Vision upstream unavailable'}


def test_vision_unsupported_mime_checked_before_size_limit(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')
    monkeypatch.setenv('VISION_MAX_UPLOAD_BYTES', '1')

    response = client.post(
        '/api/vision',
        files={'image': ('photo.gif', b'abcdef', 'image/gif')},
    )

    assert response.status_code == 415
    payload = response.json()
    assert 'detail' in payload
    assert 'unsupported' in payload['detail'].lower()


def test_vision_payload_validation_happens_before_api_key_check(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('MISTRAL_API_KEY', raising=False)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.gif', b'abcdef', 'image/gif')},
    )

    assert response.status_code == 415
    payload = response.json()
    assert 'detail' in payload
    assert 'unsupported' in payload['detail'].lower()


def test_vision_upstream_5xx_detail_is_not_leaked(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_describe_image(**_: object) -> str:
        raise UpstreamAPIError(status_code=500, detail='provider stack trace token=abc123')

    monkeypatch.setattr('server.app.describe_image', fake_describe_image)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'image-bytes', 'image/jpeg')},
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload == {'detail': 'Vision upstream unavailable'}
    assert 'abc123' not in payload['detail']


def test_vision_upstream_4xx_detail_is_not_leaked(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MISTRAL_API_KEY', 'test-key')

    async def fake_describe_image(**_: object) -> str:
        raise UpstreamAPIError(status_code=400, detail='provider raw body secret')

    monkeypatch.setattr('server.app.describe_image', fake_describe_image)

    response = client.post(
        '/api/vision',
        files={'image': ('photo.jpg', b'image-bytes', 'image/jpeg')},
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload == {'detail': 'Vision upstream request failed'}
    assert 'secret' not in payload['detail']


def test_tts_midstream_failure_aborts_response(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'test-key')

    class MidStreamFailingResponse:
        def __init__(self) -> None:
            self._stream_started = False

        async def aiter_bytes(self) -> AsyncIterator[bytes]:
            if self._stream_started:
                raise httpx.StreamConsumed()
            self._stream_started = True
            yield b'ID3'
            raise httpx.ReadError('stream broke')

        async def aclose(self) -> None:
            return None

    async def fake_open_stream(**_: object) -> tuple[FakeClient, MidStreamFailingResponse]:
        return FakeClient(), MidStreamFailingResponse()

    monkeypatch.setattr('server.app.open_tts_stream', fake_open_stream)

    with pytest.raises(RuntimeError, match='TTS stream interrupted mid-response'):
        client.post('/api/tts', json={'text': 'hello', 'voice_id': 'voice-1'})


@pytest.mark.anyio
async def test_transcribe_audio_transport_error_maps_to_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class TransportFailingClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> TransportFailingClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> object:
            raise httpx.ConnectError('network down')

    monkeypatch.setattr('server.app.httpx.AsyncClient', TransportFailingClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await transcribe_audio(
            api_key='key',
            audio_bytes=b'audio',
            filename='sample.webm',
            content_type='audio/webm',
            language='en',
        )

    assert exc.value.status_code == 502
    assert 'transport error' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_transcribe_audio_invalid_json_maps_to_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class InvalidJsonResponse:
        status_code = 200
        text = ''

        def json(self) -> dict[str, str]:
            raise ValueError('bad json')

    class InvalidJsonClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> InvalidJsonClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> InvalidJsonResponse:
            return InvalidJsonResponse()

    monkeypatch.setattr('server.app.httpx.AsyncClient', InvalidJsonClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await transcribe_audio(
            api_key='key',
            audio_bytes=b'audio',
            filename='sample.webm',
            content_type='audio/webm',
            language='en',
        )

    assert exc.value.status_code == 502
    assert 'invalid json' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_open_tts_stream_transport_error_maps_to_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class TransportFailingClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        def build_request(self, *_: object, **__: object) -> object:
            return object()

        async def send(self, *_: object, **__: object) -> object:
            raise httpx.ConnectError('network down')

        async def aclose(self) -> None:
            return

    monkeypatch.setattr('server.app.httpx.AsyncClient', TransportFailingClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await open_tts_stream(api_key='key', text='hello', voice_id='voice-1')

    assert exc.value.status_code == 502
    assert 'transport error' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_describe_image_normalizes_structured_content(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class VisionResponse:
        status_code = 200
        text = ''

        def json(self) -> dict[str, object]:
            return {
                'choices': [
                    {
                        'message': {
                            'content': [
                                {'type': 'text', 'text': 'A wooden table'},
                                {'type': 'text', 'text': 'with a laptop and coffee mug.'},
                            ]
                        }
                    }
                ]
            }

    class VisionClient:
        def __init__(self, *_: object, **kwargs: object) -> None:
            captured['timeout'] = kwargs.get('timeout')

        async def __aenter__(self) -> VisionClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> VisionResponse:
            captured['url'] = url
            captured['headers'] = headers
            captured['payload'] = json
            return VisionResponse()

    monkeypatch.setattr('server.app.httpx.AsyncClient', VisionClient)

    text = await describe_image(api_key='test-key', image_bytes=b'\x89PNG', mime_type='image/png')

    assert text == 'A wooden table with a laptop and coffee mug.'
    assert captured['timeout'] == 60.0
    assert captured['url'] == 'https://api.mistral.ai/v1/chat/completions'

    payload = captured['payload']
    assert isinstance(payload, dict)
    assert payload['model'] == 'mistral-large-latest'
    assert payload['messages'][0]['content'][0]['image_url'] == 'data:image/png;base64,iVBORw=='
    assert payload['messages'][0]['content'][1] == {'type': 'text', 'text': 'Describe this image'}


@pytest.mark.anyio
async def test_describe_image_empty_content_raises_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyVisionResponse:
        status_code = 200
        text = ''

        def json(self) -> dict[str, object]:
            return {'choices': [{'message': {'content': []}}]}

    class EmptyVisionClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> EmptyVisionClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> EmptyVisionResponse:
            return EmptyVisionResponse()

    monkeypatch.setattr('server.app.httpx.AsyncClient', EmptyVisionClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await describe_image(api_key='test-key', image_bytes=b'image', mime_type='image/jpeg')

    assert exc.value.status_code == 502
    assert 'empty' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_describe_image_invalid_json_raises_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class InvalidJsonResponse:
        status_code = 200
        text = ''

        def json(self) -> dict[str, object]:
            raise ValueError('bad json')

    class InvalidJsonClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> InvalidJsonClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> InvalidJsonResponse:
            return InvalidJsonResponse()

    monkeypatch.setattr('server.app.httpx.AsyncClient', InvalidJsonClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await describe_image(api_key='test-key', image_bytes=b'image', mime_type='image/jpeg')

    assert exc.value.status_code == 502
    assert 'invalid json' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_describe_image_no_choices_raises_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoChoicesResponse:
        status_code = 200
        text = ''

        def json(self) -> dict[str, object]:
            return {'choices': []}

    class NoChoicesClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> NoChoicesClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> NoChoicesResponse:
            return NoChoicesResponse()

    monkeypatch.setattr('server.app.httpx.AsyncClient', NoChoicesClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await describe_image(api_key='test-key', image_bytes=b'image', mime_type='image/jpeg')

    assert exc.value.status_code == 502
    assert 'no choices' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_describe_image_malformed_choice_raises_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class MalformedChoiceResponse:
        status_code = 200
        text = ''

        def json(self) -> dict[str, object]:
            return {'choices': ['not-a-dict']}

    class MalformedChoiceClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> MalformedChoiceClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> MalformedChoiceResponse:
            return MalformedChoiceResponse()

    monkeypatch.setattr('server.app.httpx.AsyncClient', MalformedChoiceClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await describe_image(api_key='test-key', image_bytes=b'image', mime_type='image/jpeg')

    assert exc.value.status_code == 502
    assert 'malformed choices' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_describe_image_malformed_message_raises_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class MalformedMessageResponse:
        status_code = 200
        text = ''

        def json(self) -> dict[str, object]:
            return {'choices': [{'message': 'not-a-dict'}]}

    class MalformedMessageClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> MalformedMessageClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> MalformedMessageResponse:
            return MalformedMessageResponse()

    monkeypatch.setattr('server.app.httpx.AsyncClient', MalformedMessageClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await describe_image(api_key='test-key', image_bytes=b'image', mime_type='image/jpeg')

    assert exc.value.status_code == 502
    assert 'malformed message' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_describe_image_timeout_raises_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class TimeoutVisionClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> TimeoutVisionClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> object:
            raise httpx.ReadTimeout('request timed out')

    monkeypatch.setattr('server.app.httpx.AsyncClient', TimeoutVisionClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await describe_image(api_key='test-key', image_bytes=b'image', mime_type='image/jpeg')

    assert exc.value.status_code == 502
    assert 'transport error' in exc.value.detail.lower()


@pytest.mark.anyio
async def test_describe_image_connect_error_raises_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class ConnectErrorVisionClient:
        def __init__(self, *_: object, **__: object) -> None:
            return

        async def __aenter__(self) -> ConnectErrorVisionClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return

        async def post(self, *_: object, **__: object) -> object:
            raise httpx.ConnectError('network down')

    monkeypatch.setattr('server.app.httpx.AsyncClient', ConnectErrorVisionClient)

    with pytest.raises(UpstreamAPIError) as exc:
        await describe_image(api_key='test-key', image_bytes=b'image', mime_type='image/jpeg')

    assert exc.value.status_code == 502
    assert 'transport error' in exc.value.detail.lower()
