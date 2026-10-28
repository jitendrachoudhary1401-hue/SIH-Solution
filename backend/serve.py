import os
from waitress import serve
from app import create_app

def server_options(environment=None):
    settings = os.environ if environment is None else environment
    # Render cannot route to loopback, even if an old local API_HOST was copied
    # into the service environment. Keep local development binding unchanged.
    on_render = settings.get("RENDER", "").lower() == "true"
    host = "0.0.0.0" if on_render else settings.get("API_HOST") or "127.0.0.1"
    port = int(settings.get("PORT") or settings.get("API_PORT") or "5000")
    return {"host": host, "port": port}


def main():
    app = create_app()
    options = server_options()
    print(f"Starting OneCase API on {options['host']}:{options['port']}", flush=True)
    serve(app, **options)


if __name__ == "__main__":
    main()
