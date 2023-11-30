from typing import Iterable, Iterator


class DatadotenvError(Exception):
    pass


class DatadotenvValueError(DatadotenvError, ValueError):
    pass


class DatadotenvParseError(DatadotenvValueError):
    pass


def iter_key_values_from_chars(
        chars: Iterable[str],
) -> Iterator[tuple[str, str]]:
    """
    Parse character streams in the .env file format
    and yield key/value pairs.

    The format rules try to follow those of `python-dotenv`.
    See: https://pypi.org/project/python-dotenv/ -- Section: File format

    Raises a `DatadotenvParserError` for incorrectly formatted inputs.
    
    Parser implementation is scannerless with low memory overhead.
    """
    return _iter_key_values_from_chars_core(iter(chars))


_PARSER_STATE_BEFORE_NAME = 0
_PARSER_STATE_IN_UNQUOTED_NAME = 1
_PARSER_STATE_IN_QUOTED_NAME = 2
_PARSER_STATE_AFTER_NAME = 3
_PARSER_STATE_BEFORE_VAL = 4
_PARSER_STATE_IN_UNQUOTED_VAL = 5
_PARSER_STATE_IN_DOUBLE_QUOTED_VAL = 6
_PARSER_STATE_IN_SINGLE_QUOTED_VAL = 7
_PARSER_STATE_AFTER_VAL = 8
_PARSER_STATE_IN_COMMENT = 9


def _iter_key_values_from_chars_core(
        chars: Iterator[str],
) -> Iterator[tuple[str, str]]:
    # Parse implementation tries to be compatible with python-dotenv.
    # See: https://pypi.org/project/python-dotenv -- File format

    name_chars: list[str] = []
    val_chars: list[str] = []
    state: int = _PARSER_STATE_BEFORE_NAME
    
    while True:
        try:
            char = next(chars)
        except StopIteration:
            break

        if state == _PARSER_STATE_BEFORE_NAME:
            # Ignore line-breaks and whitespace
            if char == "\n" or char == "\r" or char == " " or char == "\t" or char == "\v" or char == "\f":
                continue
            if char == "#":
                state = _PARSER_STATE_IN_COMMENT
            elif char == "'":
                state = _PARSER_STATE_IN_QUOTED_NAME
            elif "A" <= char <= "Z" or "a" <= char <= "z":
                name_chars.append(char)
                state = _PARSER_STATE_IN_UNQUOTED_NAME
            else:
                raise DatadotenvParseError(
                    f"Unquoted dotenv variable names may only start with letters (A-Za-z), found '{char}'!"
                )
        elif state == _PARSER_STATE_IN_UNQUOTED_NAME:
            if char == "=":
                state = _PARSER_STATE_BEFORE_VAL
            # TODO: Check how bash actually handles vertical tabs.
            elif char == " " or char == "\t" or char == "\v":
                state = _PARSER_STATE_AFTER_NAME
            elif char == "_" or "A" <= char <= "Z" or "0" <= char <= "9" or "a" <= char <= "z":
                name_chars.append(char)
            else:
                raise DatadotenvParseError(
                    f"Unquoted dotenv variable names may only contain letters, number and underscores (A-Za-z_), found '{char}'!"
                )
        elif state == _PARSER_STATE_BEFORE_VAL:
            # Allow empty values
            if char == "\n" or char == "\r" or char == "\f":
                yield "".join(name_chars), ""
                name_chars.clear()
                state = _PARSER_STATE_BEFORE_NAME
            elif char == '"':
                state = _PARSER_STATE_IN_DOUBLE_QUOTED_VAL
            elif char == "'":
                state = _PARSER_STATE_IN_SINGLE_QUOTED_VAL
            elif char == "#":
                yield "".join(name_chars), ""
                name_chars.clear()
                state = _PARSER_STATE_IN_COMMENT
            elif char != " " and char != "\t" and char != "\v":
                val_chars.append(char)
                state = _PARSER_STATE_IN_UNQUOTED_VAL
        elif state == _PARSER_STATE_IN_UNQUOTED_VAL:
            if char == "\n" or char == "\r" or char == "\f":
                yield "".join(name_chars), "".join(val_chars)
                name_chars.clear()
                val_chars.clear()
                state = _PARSER_STATE_BEFORE_NAME
            elif char == " " or char == "\t" or char == "\v":
                state = _PARSER_STATE_AFTER_VAL
            else:
                val_chars.append(char)
        elif state == _PARSER_STATE_IN_DOUBLE_QUOTED_VAL:
            if char == '"':
                state = _PARSER_STATE_AFTER_VAL
            elif char == "\\":
                escaped_char = next(chars)
                if escaped_char == "\"":
                    val_chars.append('"')
                elif escaped_char == "n":
                    val_chars.append("\n")
                elif escaped_char == "\\":
                    val_chars.append("\\")
                elif escaped_char == "t":
                    val_chars.append("\t")
                elif escaped_char == "'":
                    val_chars.append("'")
                elif escaped_char == "r":
                    val_chars.append("\r")
                elif escaped_char == "v":
                    val_chars.append("\v")
                elif escaped_char == "f":
                    val_chars.append("\f")
                elif escaped_char == "b":
                    val_chars.append("\b")
                elif escaped_char == "a":
                    val_chars.append("\a")
                else:
                    raise DatadotenvParseError(
                        f"Invalid escape sequence '\\{escaped_char}' inside double-quoted value!"
                    )
            else:
                val_chars.append(char)
        elif state == _PARSER_STATE_IN_SINGLE_QUOTED_VAL:
            if char == "'":
                state = _PARSER_STATE_AFTER_VAL
            elif char == "\\":
                escaped_char = next(chars)
                if escaped_char == "'":
                    val_chars.append("'")
                elif escaped_char == "\\":
                    val_chars.append("\\")
                else:
                    raise DatadotenvParseError(
                        f"Invalid escaped sequence '\\{escaped_char}' inside single-quoted value!"
                    )
            else:
                val_chars.append(char)
        elif state == _PARSER_STATE_AFTER_VAL:
            if char == "\n" or char == "\r" or char == "\f":
                yield "".join(name_chars), "".join(val_chars)
                name_chars.clear()
                val_chars.clear()
                state = _PARSER_STATE_BEFORE_NAME
            elif char == "#":
                yield "".join(name_chars), "".join(val_chars)
                name_chars.clear()
                val_chars.clear()
                state = _PARSER_STATE_IN_COMMENT
            elif char != " " and char != "\t" and char != "\v":
                raise DatadotenvParseError(
                    f"Invalid non-whitespace character '{char}' after value ended!"
                )
        elif state == _PARSER_STATE_IN_COMMENT:
            if char == "\n" or char == "\r" or char == "\f":
                state = _PARSER_STATE_BEFORE_NAME
        elif state == _PARSER_STATE_AFTER_NAME:
            if char == "=":
                state = _PARSER_STATE_BEFORE_VAL
            elif char != " " and char != "\t" and char != "\v":
                raise DatadotenvParseError(
                    f"Invalid non-whitespace character '{char}' after name and before '='!"
                )
        elif state == _PARSER_STATE_IN_QUOTED_NAME:
            if char == "'":
                state = _PARSER_STATE_AFTER_NAME
            elif char == "\\":
                escaped_char = next(chars)
                if escaped_char == "'":
                    name_chars.append("'")
                elif escaped_char == "\\":
                    name_chars.append("\\")
                else:
                    raise DatadotenvParseError(
                        f"Invalid escaped sequence '\\{escaped_char}' inside single-quoted name!"
                    )
            else:
                name_chars.append(char)
        else:
            raise RuntimeError(
                f"Unhandled parser state={state}"
            )

    if state == _PARSER_STATE_IN_UNQUOTED_VAL or state == _PARSER_STATE_AFTER_VAL:
        yield "".join(name_chars), "".join(val_chars)
    # Allow empty values
    elif state == _PARSER_STATE_BEFORE_VAL:
        yield "".join(name_chars), ""
    elif state != _PARSER_STATE_BEFORE_NAME:
        raise DatadotenvParseError(
            "Input ended with unterminated name or value!"
        )
                
    # Hopefully help garbage collector
    del name_chars
    del val_chars

