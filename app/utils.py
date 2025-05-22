import urllib.parse
import hmac
import hashlib
import time


def verify_telegram_auth(init_data_raw, bot_token):
    """Проверка подлинности initData по алгоритму Telegram"""
    parsed_data = dict(urllib.parse.parse_qsl(init_data_raw, keep_blank_values=True))
    
    received_hash = parsed_data.pop('hash', None)
    if not received_hash:
        return False

    data_check_arr = [f"{k}={v}" for k, v in sorted(parsed_data.items())]
    data_check_string = "\n".join(data_check_arr)

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    auth_date = int(parsed_data.get("auth_date", 0))
    if time.time() - auth_date > 60:
        return False

    return hmac.compare_digest(calculated_hash, received_hash)