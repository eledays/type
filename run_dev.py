from app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(
        debug=app.config.get('DEBUG'), 
        host=app.config.get('FLASK_HOST'), 
        port=app.config.get('FLASK_PORT')
    )
