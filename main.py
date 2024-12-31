
from app import app

def main():
    """Run the Flask application with debug mode"""
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )

if __name__ == "__main__":
    main()
