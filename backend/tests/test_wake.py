from unittest.mock import patch


def test_wake_is_public_and_independent_of_database_or_redis(app, client):
    # Exercise the production proxy boundary without touching real infrastructure.
    app.config.update(APP_ENV='production', FRONTEND_PROXY_SECRET='synthetic-proxy-secret-of-32-characters')
    with patch('app.models.db.session.execute', side_effect=AssertionError('Wake must not query the database')):
        response = client.get('/api/wake')
        assert response.status_code == 200
        assert response.json == {'status': 'awake', 'service': 'onecase'}
        assert 'no-store' in response.headers['Cache-Control']
        assert not response.headers.get('Set-Cookie')
        assert client.head('/api/wake').status_code == 200
        # The liveness exemption never grants access to private API routes.
        assert client.get('/api/account/summary').status_code == 403


def test_wake_does_not_accept_writes(client):
    assert client.post('/api/wake', json={}).status_code == 405
