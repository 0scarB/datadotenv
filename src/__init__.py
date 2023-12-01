from __future__ import annotations

import dataclasses
from dataclasses import dataclass
import types
import typing
from typing import Any, Callable, ClassVar, Generic, Iterable, Iterator, Protocol, Type, TypeAlias, TypeVar


_T = TypeVar("_T")


class _Dataclass(Protocol):

    __dataclass_fields__: ClassVar[dict]


_TDataclass = TypeVar("_TDataclass", bound=_Dataclass)


def datadotenv(
    datacls: Type[_TDataclass],
) -> _Spec[_TDataclass]:
    _var_specs: list[_VarSpec] = []
    for field in dataclasses.fields(datacls):
        _var_specs.append(_VarSpecSingleton(
            dataclass_field_name=field.name,
            validate_and_convert=_choose_validator_and_converter(
                field.name,
                field.type
            )
        ))

    return _Spec(datacls, _var_specs)


def _choose_validator_and_converter(
        dataclass_field_name: str,
        type_: Any,
) -> Callable[[Var], Any]:
    if type(type_) is str:
        type_ = eval(type_)

    if type_ is str:
        return _validate_and_convert_str
    elif type_ is bool:
        return _validate_and_convert_bool
    elif type_ is int:
        return _validate_and_convert_int
    elif type_ is float:
        return _validate_and_convert_float
    elif isinstance(type_, types.NoneType):
        return _validate_and_convert_unset
    elif getattr(type_, "__name__") == "Literal":
        return _create_validate_and_convert_literal(dataclass_field_name, type_)
    else:
        raise DatadotenvNotImplementedError(
            f"No handling for type of dataclass field '{dataclass_field_name}: {type_.__name__}'!"
        )


def _validate_and_convert_str(env_var: Var) -> str:
    if env_var.value is None:
        raise DatadotenvUnsetError(
            f"Dotenv variable '{env_var.name}' was expected to be set!"
        )

    return env_var.value


def _validate_and_convert_bool(env_var: Var) -> bool:
    str_value = _validate_and_convert_str(env_var)
    if str_value == "true" or str_value == "True":
        return True
    elif str_value == "false" or str_value == "False":
        return False

    raise DatadotenvConversionError(
        f"Failed to convert dotenv variable {env_var.name}='{env_var.value}' to type 'bool'!"
    )


def _validate_and_convert_int(env_var: Var) -> bool:
    str_value = _validate_and_convert_str(env_var)
    try:
        return int(str_value)
    except ValueError:
        raise DatadotenvConversionError(
            f"Failed to convert dotenv variable {env_var.name}='{env_var.value}' to type 'int'!"
        )


def _validate_and_convert_float(env_var: Var) -> bool:
    str_value = _validate_and_convert_str(env_var)
    try:
        return float(str_value)
    except ValueError:
        raise DatadotenvConversionError(
            f"Failed to convert dotenv variable {env_var.name}='{env_var.value}' to type 'float'!"
        )


def _validate_and_convert_unset(env_var: Var) -> None:
    if env_var.value is None:
        return None

    raise DatadotenvConversionError(
        f"Expected dotenv varibale '{env_var.name}' to be unset, not '{env_var.value}'!"
    )


def _create_validate_and_convert_literal(
        dataclass_field_name: str, 
        literal: _T
) -> Callable[[Var], _T]:
    
    def validate_and_convert(env_var: Var) -> _T:
        options = typing.get_args(literal)
        for option in options:
            f = _choose_validator_and_converter(dataclass_field_name, type(option))
            try:
                if option == f(env_var):
                    return option
            except DatadotenvNotImplementedError as err:
                raise err
            except DatadotenvError:
                pass
        
        options_str = ", ".join(f"'{option}'" for option in options)
        raise DatadotenvConversionError(
            f"Expected dotenv variable '{env_var.name}' to be one of {options_str}, not '{env_var.value}'!"
        )

    return validate_and_convert



@dataclass
class Var:
    name: str
    value: str | None


@dataclass
class _VarSpecBase:
    dataclass_field_name: str


@dataclass
class _VarSpecSingleton(Generic[_T], _VarSpecBase):
    validate_and_convert: Callable[[Var], _T]


@dataclass
class _VarSpecAccumulator(Generic[_T], _VarSpecBase):
    accumulator: _T
    validate_and_accumulate: Callable[[_T, Var], _T]


_VarSpec: TypeAlias = _VarSpecSingleton[Any] | _VarSpecAccumulator[Any]


class _Spec(Generic[_TDataclass]):
    _ignore_case: bool
    _ignore_not_in_dataclass: bool

    _datacls: Type[_TDataclass]
    _var_specs: list[_VarSpec]
    _expected_env_var_name_to_var_spec_index: dict[str, int]
    _discover_var_spec: Callable[[list[_VarSpec], str], _VarSpec]

    def __init__(
            self,
            datacls: _TDataclass,
            var_specs: list[_VarSpec],
            ignore_case: bool = True,
            ignore_not_in_dataclass: bool = False,
    ) -> None:
        self._ignore_case = ignore_case
        self._ignore_not_in_dataclass = ignore_not_in_dataclass

        self._datacls = datacls
        self._var_specs = var_specs
        self._expected_env_var_name_to_var_spec_index = {}
        self._repopulate_expected_env_var_name_to_var_spec_index()

        def discover_var_spec(
                var_specs: list[_VarSpec], 
                env_var_name: str,
        ) -> _VarSpec:
            original_env_var_name = env_var_name
            if self._ignore_case:
                env_var_name = env_var_name.lower()
            elif not env_var_name.isupper():
                raise DatadotenvCasingError(
                    "Only uppercase dotenv variable names are supported when `ignore_case=False`. "
                    f"Mixed or lowercase dotenv variable: '{env_var_name}'!"
                )
            try:
                spec_idx = self._expected_env_var_name_to_var_spec_index[env_var_name]
            except KeyError:
                if not self._ignore_not_in_dataclass:
                    raise DatadotenvNotInDataclassError(
                        f"No dataclass attribute '{env_var_name.lower()}' "
                        f"specified for dotenv variable '{original_env_var_name}'!"
                    )
            
            return var_specs[spec_idx]

        self._discover_var_spec = discover_var_spec

    def from_chars(
            self,
            chars: Iterable[str]
    ) -> _TDataclass:
        kwargs: dict[str, Any] = {}
        unhandled_dataclass_fields = {
            var_spec.dataclass_field_name 
            for var_spec in self._var_specs
        }
        for var in iter_vars_from_dotenv_chars(chars):
            var_spec = self._discover_var_spec(self._var_specs, var.name)
            if isinstance(var_spec, _VarSpecSingleton):
                kwargs[var_spec.dataclass_field_name] = var_spec.validate_and_convert(
                    var,
                )
                try:
                    unhandled_dataclass_fields.remove(var_spec.dataclass_field_name)
                except KeyError:
                    raise DatadotenvDuplicateVariableError(
                        f"Dotenv has duplicate variable '{var.name}'!"
                    )
            elif isinstance(var_spec, _VarSpecAccumulator):
                raise DatadotenvNotImplementedError
            else:
                raise RuntimeError(
                    f"Unhandled var_spec type '{type(var_spec).__name__}' with value {var_spec}!"
                )

        if unhandled_dataclass_fields:
            missing_variables = ", ".join(f"'{field.upper()}'" for field in unhandled_dataclass_fields)
            raise DatadotenvMissingVariableError(
                f"Dotenv is missing the variables: {missing_variables}!"
            )
        
        return self._datacls(**kwargs)

    from_str = from_chars

    def _repopulate_expected_env_var_name_to_var_spec_index(self):
        self._expected_env_var_name_to_var_spec_index.clear()
        for idx, spec in enumerate(self._var_specs):
            expected_env_var_name = spec.dataclass_field_name
            if self._ignore_case:
                expected_env_var_name = expected_env_var_name.lower()
            else:
                expected_env_var_name = expected_env_var_name.upper()
            self._expected_env_var_name_to_var_spec_index[expected_env_var_name] = idx


def iter_vars_from_dotenv_chars(
        chars: Iterable[str],
) -> Iterator[Var]:
    """
    Parse an iterator of characters in the .env file format
    and yield `Var` objects containing the dotenv variable 
    names and values.

    The format rules try to follow those of `python-dotenv`.
    See: https://pypi.org/project/python-dotenv/ -- Section: File format

    Raises a `DatadotenvParserError` for incorrectly formatted inputs.
    
    Parser implementation is scannerless with low memory overhead.
    """
    return _iter_name_values_from_chars_core(iter(chars))


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


def _iter_name_values_from_chars_core(
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
                yield Var("".join(name_chars), None)
                name_chars.clear()
                state = _PARSER_STATE_BEFORE_NAME
            elif char == '"':
                state = _PARSER_STATE_IN_DOUBLE_QUOTED_VAL
            elif char == "'":
                state = _PARSER_STATE_IN_SINGLE_QUOTED_VAL
            elif char == "#":
                yield Var("".join(name_chars), "")
                name_chars.clear()
                state = _PARSER_STATE_IN_COMMENT
            elif char != " " and char != "\t" and char != "\v":
                val_chars.append(char)
                state = _PARSER_STATE_IN_UNQUOTED_VAL
        elif state == _PARSER_STATE_IN_UNQUOTED_VAL:
            if char == "\n" or char == "\r" or char == "\f":
                yield Var("".join(name_chars), "".join(val_chars))
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
                yield Var("".join(name_chars), "".join(val_chars))
                name_chars.clear()
                val_chars.clear()
                state = _PARSER_STATE_BEFORE_NAME
            elif char == "#":
                yield Var("".join(name_chars), "".join(val_chars))
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
        yield Var("".join(name_chars), "".join(val_chars))
    # Allow empty values
    elif state == _PARSER_STATE_BEFORE_VAL:
        yield Var("".join(name_chars), None)
    elif state != _PARSER_STATE_BEFORE_NAME:
        raise DatadotenvParseError(
            "Input ended with unterminated name or value!"
        )
                
    # Hopefully help garbage collector
    del name_chars
    del val_chars


class DatadotenvError(Exception):
    pass


class DatadotenvValueError(DatadotenvError, ValueError):
    pass


class DatadotenvParseError(DatadotenvValueError):
    pass


class DatadotenvCasingError(DatadotenvError, ValueError):
    pass


class DatadotenvNotInDataclassError(DatadotenvError, AttributeError):
    pass


class DatadotenvMissingVariableError(DatadotenvError, ValueError):
    pass


class DatadotenvDuplicateVariableError(DatadotenvError, ValueError):
    pass


class DatadotenvUnsetError(DatadotenvError, ValueError):
    pass


class DatadotenvConversionError(DatadotenvError, ValueError):
    pass


class DatadotenvNotImplementedError(NotImplementedError):
    pass
