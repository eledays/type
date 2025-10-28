from app import app

from flask import jsonify, request, render_template


@app.route("/api/clips/batch", methods=["GET"])
def batch_get_clips():
    """
    Возвращает батч клипов.
    """

    clips_count: int = request.args.get(
        "count", default=app.config.get("DEFAULT_CLIPS_BATCH_SIZE", 1), type=int
    )

    MOCK_CLIPS: list[dict] = [
        {
            "id": 1,
            "content": render_template(
                "clip.html",
                word_html='пр<span class="missing-letter"> </span>ломление',
                answers=["е", "и"],
            ),
        },
        {
            "id": 2,
            "content": render_template(
                "clip.html",
                word_html='н<span class="missing-letter"> </span>важдение',
                answers=["а", "о"],
            ),
        },
        {
            "id": 3,
            "content": render_template(
                "clip.html",
                word_html='стел<span class="missing-letter"> </span>щий',
                answers=["ю", "я"],
            ),
        },
    ]

    # В будущем проверять xss

    return jsonify({"clips": MOCK_CLIPS[:clips_count]})
