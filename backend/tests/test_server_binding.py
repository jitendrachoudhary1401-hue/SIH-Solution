"""Render must expose the API even when old localhost settings were copied."""
import pytest
import serve


@pytest.mark.parametrize('environment,expected', [
    ({'RENDER':'true','API_HOST':'127.0.0.1','PORT':'10000','API_PORT':'5000'}, {'host':'0.0.0.0','port':10000}),
    ({'RENDER':'true','PORT':'12345'}, {'host':'0.0.0.0','port':12345}),
    ({}, {'host':'127.0.0.1','port':5000}),
    ({'API_HOST':'0.0.0.0','API_PORT':'5050'}, {'host':'0.0.0.0','port':5050}),
])
def test_binding_follows_render_and_local_settings(environment,expected):
    assert serve.server_options(environment) == expected


def test_startup_passes_public_binding_to_waitress(monkeypatch):
    application = object()
    calls = []
    monkeypatch.setenv('RENDER','true')
    monkeypatch.setenv('API_HOST','127.0.0.1')
    monkeypatch.setenv('PORT','10000')
    monkeypatch.setattr(serve,'create_app',lambda:application)
    monkeypatch.setattr(serve,'serve',lambda app,**kwargs:calls.append((app,kwargs)))
    serve.main()
    assert calls == [(application,{'host':'0.0.0.0','port':10000})]
