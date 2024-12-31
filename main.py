
from app import app, limiter

limiter.init_app(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
