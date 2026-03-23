def encode_base36(number: int) -> str:
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    if number == 0:
        return '0'

    result = ''
    while number > 0:
        number, remainder = divmod(number, 36)
        result = alphabet[remainder] + result
    return result


def decode_base36(code: str) -> int:
    alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
    normalized_code = code.lower().strip()
    number = 0

    for symbol in normalized_code:
        if symbol not in alphabet:
            raise ValueError('bad base36')
        number = number * 36 + alphabet.index(symbol)

    return number
