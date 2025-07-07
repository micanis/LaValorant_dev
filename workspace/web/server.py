# web/server.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
# from fastapi.staticfiles import StaticFiles

from services.user_service import UserService

# FastAPIアプリケーションのインスタンスを作成
app = FastAPI()


@app.on_event("startup")
async def startup_event():
    # main.pyから渡されたUserServiceインスタンスをここで受け取る想定
    # このようにapp.stateに格納することで、リクエストハンドラ内で利用できる
    app.state.user_service = None  # プレースホルダー


@app.get("/oauth/callback/riot.txt", response_class=FileResponse)
async def get_riot_verification_file():
    """endpoint"""
    return FileResponse("public/riot.txt", media_type="text/plain")


@app.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(request: Request, code: str, state: str):
    """
    RiotからのOAuthコールバックを処理するエンドポイント
    """
    user_service: UserService = request.app.state.user_service
    if not user_service:
        return HTMLResponse(
            "<html><body><h1>エラー</h1><p>サーバー内部でエラーが発生しました。Bot管理者にお問い合わせください。</p></body></html>",
            status_code=500,
        )

    # UserServiceに実際の処理を委譲
    success, message = await user_service.process_oauth_callback(code, state)

    if success:
        return HTMLResponse(f"""
        <html>
            <head><title>連携完了</title></head>
            <body>
                <h1>✅ アカウント連携が完了しました！</h1>
                <p>{message}</p>
                <p>このウィンドウは閉じて、Discordに戻ってください。</p>
            </body>
        </html>
        """)
    else:
        return HTMLResponse(f"""
        <html>
            <head><title>連携失敗</title></head>
            <body>
                <h1>❌ アカウント連携に失敗しました。</h1>
                <p>{message}</p>
                <p>再度/rankコマンドを実行するか、管理者にお問い合わせください。</p>
            </body>
        </html>
        """)
