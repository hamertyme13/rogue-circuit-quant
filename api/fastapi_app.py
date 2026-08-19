from web_app import WebCommandCenter


def create_app(center: WebCommandCenter | None = None):
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI is not installed. Install fastapi and uvicorn "
            "to run the production API adapter."
        ) from exc

    command_center = center or WebCommandCenter()
    app = FastAPI(title="Rogue Circuit Quant API")

    def require_auth(x_rogue_token: str | None = Header(default=None)):
        if not command_center.auth.verify(x_rogue_token):
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing auth token.",
            )

    @app.get("/api/state")
    def state():
        return command_center.state()

    @app.post("/api/deposits", dependencies=[Depends(require_auth)])
    def add_deposit(payload: dict):
        return command_center.add_deposit(payload)

    @app.post("/api/withdrawals", dependencies=[Depends(require_auth)])
    def add_withdrawal(payload: dict):
        return command_center.add_withdrawal(payload)

    @app.post(
        "/api/snapshots/manual",
        dependencies=[Depends(require_auth)],
    )
    def manual_snapshot(payload: dict):
        return command_center.record_manual_snapshot(payload)

    @app.post(
        "/api/snapshots/kraken",
        dependencies=[Depends(require_auth)],
    )
    def kraken_snapshot():
        return command_center.record_kraken_snapshot()

    @app.post(
        "/api/settings",
        dependencies=[Depends(require_auth)],
    )
    def settings(payload: dict):
        return command_center.apply_settings(payload)

    @app.post(
        "/api/credentials/kraken",
        dependencies=[Depends(require_auth)],
    )
    def credentials(payload: dict):
        return command_center.store_credentials(payload)

    @app.post(
        "/api/kraken/check",
        dependencies=[Depends(require_auth)],
    )
    def kraken_check():
        return command_center.check_kraken_connection()

    @app.post(
        "/api/kraken/use-target",
        dependencies=[Depends(require_auth)],
    )
    def use_target():
        return command_center.use_target_symbol()

    @app.post(
        "/api/trading/run-once",
        dependencies=[Depends(require_auth)],
    )
    def run_once():
        return command_center.run_one_cycle_response()

    @app.post(
        "/api/bot/start",
        dependencies=[Depends(require_auth)],
    )
    def start_bot():
        return command_center.start_service()

    @app.post(
        "/api/bot/stop",
        dependencies=[Depends(require_auth)],
    )
    def stop_bot():
        return command_center.stop_service()

    @app.post(
        "/api/emergency-stop",
        dependencies=[Depends(require_auth)],
    )
    def emergency_stop():
        return command_center.emergency_stop()

    @app.post("/api/resume", dependencies=[Depends(require_auth)])
    def resume():
        return command_center.resume()

    return app
