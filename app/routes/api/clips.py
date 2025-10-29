from app import app

from flask import jsonify, request, render_template


CURRENT_ID = 0


@app.route("/api/clips/batch", methods=["GET"])
def batch_get_clips():
    """
    Возвращает батч клипов.
    """

    global CURRENT_ID

    clips_count: int = request.args.get(
        "count", default=app.config.get("DEFAULT_CLIPS_BATCH_SIZE", 1), type=int
    )

    MOCK_CLIPS: list[dict] = [
        # {
        #     "id": 1,
        #     "content": render_template(
        #         "clip.html",
        #         word_parts=['пр', 'ломление'],
        #         answers=["е", "и"],
        #     ),
        # },
        # {
        #     "id": 2,
        #     "content": render_template(
        #         "clip.html",
        #         word_parts=['н', 'важдение'],
        #         answers=["а", "о"],
        #     ),
        # },
        # {
        #     "id": 3,
        #     "content": render_template(
        #         "clip.html",
        #         word_parts=['стел', 'щий'],
        #         answers=["ю", "я"],
        #     ),
        # },
    # ] + [
        {
            "id": i,
            "content": render_template(
                "clip.html",
                word_parts=[str(i), 'нание'],
                answers=["е", "и"],
            ),
        } for i in range(CURRENT_ID, CURRENT_ID + clips_count)
    ]

    # В будущем проверять xss

    CURRENT_ID += clips_count

    return jsonify({"clips": MOCK_CLIPS})
