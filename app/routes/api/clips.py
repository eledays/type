from app import app

from flask import jsonify, request


@app.route('/api/clips/batch', methods=['GET'])
def batch_get_clips():
    """
    Возвращает батч клипов.
    """

    clips_count: int = request.args.get(
        'count', default=app.config.get('DEFAULT_CLIPS_BATCH_SIZE', 1), type=int)
    
    MOCK_CLIPS = [
        {'id': 1, 'content': '<b>Hello</b>, world!'},
        {'id': 2, 'content': 'This is a <i>test</i> clip.'},
        {'id': 3, 'content': 'Flask is <u>awesome</u>!'},
    ]

    return jsonify({'clips': MOCK_CLIPS[:clips_count]})
