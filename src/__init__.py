from __future__ import annotations

import dataclasses
from dataclasses import dataclass
import datetime
from pathlib import Path
import types
import typing
from typing import Any, Callable, cast, ClassVar, Generic, Iterable, Iterator, Literal, Protocol, Type, TypeAlias, TypeVar


_T = TypeVar("_T")


class _Dataclass(Protocol):

    __dataclass_fields__: ClassVar[dict]


_TDataclass = TypeVar("_TDataclass", bound=_Dataclass)


_Casing: TypeAlias = Literal["upper", "lower", "preserve", "ignore"]


class _Datadotenv:
    error: _Error

    def __call__(
        self,
        datacls: Type[_TDataclass],
        /, *,
        case: _Casing = "upper",
        allow_incomplete: bool = False,
        file_paths_must_exist: bool = True,
        resolve_file_paths: bool = True,
    ) -> _Spec[_TDataclass]:
        var_specs: list[_VarSpec[Any]] = []
        for field in dataclasses.fields(datacls):
            var_specs.append(_VarSpec(
                dataclass_field_name=field.name,
                dataclass_field_type=field.type,
                dotenv_var_name=_transform_case(case, field.name),
                default=field.default,
                target_strategy=_VarSpecTargetByName(
                    name=_transform_case(case, field.name),
                    ignore_case=case == "ignore",
                ),
                file_path_config=_VarSpecFilePathConfig(
                    resolve=resolve_file_paths,
                    must_exist=file_paths_must_exist,
                )
            ))

        return _Spec(
            datacls, 
            var_specs,
            allow_incomplete=allow_incomplete,
        )

    def open_docs(self) -> None:
        """Opens the documentation in your browser."""
        url = "https://github.com/0scarB/datadotenv/tree/main"
        if not _check_system_supports_python_webbrowser():
            raise RuntimeError(
                "Could not open documentation URL in browser. "
                f"Manually visit {url}"
            )
        import webbrowser
        webbrowser.open(url)


@dataclass
class Var:
    name: str
    value: str | None


@dataclass
class _VarSpecTargetByName:
    name: str
    ignore_case: bool 


_VarSpecTargetStrategy: TypeAlias = _VarSpecTargetByName


@dataclass
class _VarSpecFilePathConfig:
    resolve: bool
    must_exist: bool


@dataclass
class _VarSpec(Generic[_T]):
    dataclass_field_name: str
    dataclass_field_type: Any
    dotenv_var_name: str
    default: _T | Literal[dataclasses.MISSING]
    target_strategy: _VarSpecTargetStrategy
    file_path_config: _VarSpecFilePathConfig


class _Spec(Generic[_TDataclass]):
    _datacls: Type[_TDataclass]
    _var_specs: _VarSpecRepository

    _allow_incomplete: bool

    def __init__(
            self,
            datacls: Type[_TDataclass],
            var_specs: list[_VarSpec[Any]],
            allow_incomplete: bool,
    ) -> None:
        self._datacls = datacls
        self._var_specs = _VarSpecRepository(var_specs)

        self._allow_incomplete = allow_incomplete

    def from_chars_iter(
            self,
            chars: Iterable[str],
    ) -> _TDataclass:
        var_spec_resolve_group = _VarSpecResolveGroup(self._var_specs)

        dataclass_kwargs: dict[str, Any] = {}

        for var in parse.dotenv_from_chars_iter(chars):
            try:
                var_spec = (
                    var_spec_resolve_group
                    .find_spec_for_var_and_mark_as_resolved(var)
                )
                validate_and_convert = _choose_validator_and_converter(
                    var_spec,
                    var_spec.dataclass_field_type,
                )
                dataclass_kwargs[var_spec.dataclass_field_name] = \
                    validate_and_convert(var)
            except error.VariableNotSpecified as err:
                if not self._allow_incomplete:
                    raise err

        for unresolved_var_spec \
                in var_spec_resolve_group.get_unresolved_specs():
            if unresolved_var_spec.default != dataclasses.MISSING:
                dataclass_kwargs[unresolved_var_spec.dataclass_field_name] =\
                    unresolved_var_spec.default
                var_spec_resolve_group.mark_as_resolved(
                    unresolved_var_spec
                )

        self._raise_on_missing(
            var_spec_resolve_group.get_unresolved_specs()
        )
        
        return self._datacls(**dataclass_kwargs)

    def from_str(self, s: str) -> _TDataclass:
        return self.from_chars_iter(s)

    def _raise_on_missing(self, missing_var_specs: Iterable[_VarSpec]) -> None:
        missing_var_specs = list(missing_var_specs)
        if len(missing_var_specs) == 0:
            return

        missing_dataclass_field_names: list[str] = []
        missing_var_names: list[str] = []
        for unresolved_spec in missing_var_specs:
            missing_dataclass_field_names\
                .append(unresolved_spec.dataclass_field_name)
            missing_var_names\
                .append(unresolved_spec.dotenv_var_name)
        
        missing_dataclass_field_names_str = ", ".join(
            f"'{name}'" for name in missing_dataclass_field_names
        )
        missing_var_names_str = ", ".join(
            f"'{name}'" for name in missing_var_names
        )

        raise error.VariableMissing(
            f"The dataclass '{self._datacls.__name__}' "
            f"contains the fields {missing_dataclass_field_names_str}, "
            f"but the variables {missing_var_names_str} are not set in the dotenv!"
        )

class _VarSpecRepository:
    _specs: list[_VarSpec]
    _case_sensitive_names_to_spec_indices: dict[str, int]
    _case_insensitive_names_to_spec_indices: dict[str, int]

    def __init__(self, var_specs: list[_VarSpec]) -> None:
        self.update(var_specs)

    def update(self, var_specs: list[_VarSpec]) -> None:
        self._specs = var_specs
        self._case_sensitive_names_to_spec_indices = \
            self._create_case_sensitive_names_to_spec_indices_map(var_specs)
        self._case_insensitive_names_to_spec_indices = \
            self._create_case_insensitive_names_to_spec_indices_map(var_specs)

    def find_spec_idx_for_var(self, var: Var) -> int:
        return self.find_spec_idx_for_var_name(var.name)

    def find_spec_idx_for_var_name(self, name: str) -> int:
        case_sensitive_name = name
        try:
            return self._case_sensitive_names_to_spec_indices[case_sensitive_name]
        except KeyError:
            pass

        case_insensitive_name = case_sensitive_name.lower()
        try:
            return self._case_insensitive_names_to_spec_indices[case_insensitive_name]
        except KeyError:
            pass

        raise error.VariableNotSpecified(
            f"No field for dotenv variable '{name}' is specified in the dataclass!"
        ) 

    def __getitem__(self, idx: int) -> _VarSpec:
        return self._specs[idx]

    def __len__(self) -> int:
        return len(self._specs)
    
    def __iter__(self) -> Iterable[_VarSpec]:
        return iter(self._specs)

    def _create_case_sensitive_names_to_spec_indices_map(
            self,
            specs: list[_VarSpec],
    ) -> dict[str, int]:
        map_: dict[str, int] = {}
        for idx, spec in enumerate(specs):
            if (
                isinstance(spec.target_strategy, _VarSpecTargetByName)
                and not spec.target_strategy.ignore_case
            ):
                map_[spec.dotenv_var_name] = idx

        return map_

    def _create_case_insensitive_names_to_spec_indices_map(
            self,
            specs: list[_VarSpec],
    ) -> dict[str, int]:
        map_: dict[str, int] = {}
        for idx, spec in enumerate(specs):
            if (
                isinstance(spec.target_strategy, _VarSpecTargetByName)
                and spec.target_strategy.ignore_case
            ):
                map_[spec.dotenv_var_name.lower()] = idx

        return map_


class _VarSpecResolveGroup:
    _specs: _VarSpecRepository
    _resolved: list[bool]

    def __init__(self, specs_repo: _VarSpecRepository) -> None:
        self._specs = specs_repo
        self._resolved = [False] * len(self._specs)

    def mark_as_resolved(self, spec: _VarSpec) -> None:
        idx = self._specs.find_spec_idx_for_var_name(
            spec.dotenv_var_name,
        )
        self._resolved[idx] = True

    def find_spec_for_var_and_mark_as_resolved(
            self,
            var: Var,
    ) -> _VarSpec:
        idx = self._specs.find_spec_idx_for_var(var)
        self._resolved[idx] = True
        return self._specs[idx]

    def get_unresolved_specs(self) -> Iterator[_VarSpec]:
        for spec, is_resolved in zip(cast(Iterable[_VarSpec], self._specs), self._resolved):
            if not is_resolved:
                yield spec


def _choose_validator_and_converter(
        var_spec: _VarSpec[Any],
        type_: Any,
) -> Callable[[Var], Any]:
    if type(type_) is str:
        type_ = eval(type_)

    if type_ is bool:
        return _validate_and_convert_bool
    elif type_ is int:
        return _validate_and_convert_int
    elif type_ is float:
        return _validate_and_convert_float
    elif isinstance(type_, types.NoneType):
        return _validate_and_convert_unset
    elif isinstance(type_, types.UnionType) or getattr(type_, "__name__") == "Union":
        return _create_validate_and_convert_union(var_spec, type_)
    elif getattr(type_, "__name__") == "Optional":
        return _create_validate_and_convert_optional(var_spec, type_)
    elif getattr(type_, "__name__") == "Literal":
        return _create_validate_and_convert_literal(var_spec, type_)
    elif _issubclass_safe(type_, Path):
        return _create_validate_and_convert_file_path(var_spec)
    elif type_ is datetime.datetime:
        return _validate_and_convert_datetime
    elif type_ is datetime.date:
        return _validate_and_convert_date
    elif type_ is datetime.timedelta:
        return _validate_and_convert_timedelta
    elif type_ is str:
        return _validate_and_convert_str
    else:
        raise error.NotImplemented(
            f"No handling for type of dataclass field '{var_spec.dataclass_field_name}: {type_.__name__}'!"
        )


def _validate_and_convert_str(env_var: Var) -> str:
    if env_var.value is None:
        raise error.VariableUnset(
            f"Dotenv variable '{env_var.name}' was expected to be set!"
        )

    return env_var.value


def _validate_and_convert_bool(var: Var) -> bool:
    str_value = _validate_and_convert_str(var)
    if str_value == "true" or str_value == "True":
        return True
    elif str_value == "false" or str_value == "False":
        return False

    raise error.CannotConvertToType(
        f"Failed to convert dotenv variable {var.name}='{var.value}' to type 'bool'!"
    )


def _validate_and_convert_int(var: Var) -> int:
    str_value = _validate_and_convert_str(var)
    try:
        return int(str_value)
    except ValueError:
        raise error.CannotConvertToType(
            f"Failed to convert dotenv variable {var.name}='{var.value}' to type 'int'!"
        )


def _validate_and_convert_float(var: Var) -> float:
    str_value = _validate_and_convert_str(var)
    try:
        return float(str_value)
    except ValueError:
        raise error.CannotConvertToType(
            f"Failed to convert dotenv variable {var.name}='{var.value}' to type 'float'!"
        )


def _validate_and_convert_unset(var: Var) -> None:
    if var.value is None:
        return None

    raise error.CannotConvertToType(
        f"Expected dotenv varibale '{var.name}' to be unset, not '{var.value}'!"
    )


def _create_validate_and_convert_union(
        var_spec: _VarSpec[Any], 
        union: _T
) -> Callable[[Var], _T]:
    
    def validate_and_convert(env_var: Var) -> _T:
        options = typing.get_args(union)
        errs: list[Exception] = []
        for option in options:
            try:
                return _choose_validator_and_converter(var_spec, option)(
                    env_var
                )
            except Exception as err:
                errs.append(err)
        
        options_str = ", ".join(f"'{option.__name__}'" for option in options)
        raise error.CannotConvertToType(
            f"Expected dotenv variable '{env_var.name}' to be one of {options_str}, not '{type(env_var.value).__name__}'!"
        )

    return validate_and_convert


def _create_validate_and_convert_literal(
        var_spec: _VarSpec[Any], 
        literal: _T
) -> Callable[[Var], _T]:
    
    def validate_and_convert(env_var: Var) -> _T:
        options = typing.get_args(literal)
        for option in options:
            try:
                if option == _choose_validator_and_converter(var_spec, type(option))(env_var):
                    return option
            except NotImplemented as err:
                raise err
            except error.Error:
                pass
        
        options_str = ", ".join(f"'{option.__name__}'" for option in options)
        raise error.CannotConvertToType(
            f"Expected dotenv variable '{env_var.name}' to be one of {options_str}, not '{env_var.value}'!"
        )

    return validate_and_convert


def _create_validate_and_convert_optional(
        var_spec: _VarSpec[Any],
        type_: _T,
) -> Callable[[Var], _T | None]:
    
    def validate_and_convert(var: Var) -> _T | None:
        if var.value is None:
            return None
        
        optional_type = typing.get_args(type_)[0]
        return _choose_validator_and_converter(var_spec, optional_type)(var)
    
    return validate_and_convert


def _create_validate_and_convert_file_path(
        var_spec: _VarSpec[Any],
) -> Callable[[Var], Path]:
    
    def validate_and_convert(var: Var) -> Path:
        if var.value is None:
            raise error.VariableUnset(
                f"Expected dotenv variable '{var_spec.dotenv_var_name}' "
                "to be a file path, not unset!"
            )

        file_path = Path(var.value)
        if var_spec.file_path_config.resolve:
            file_path = Path.resolve(file_path)
        if var_spec.file_path_config.must_exist:
            if not file_path.exists():
                raise error.FilePathDoesNotExist(
                    f"Expected path '{file_path}' "
                    f"set by dotenv variable '{var_spec.dotenv_var_name}' to exist!"
                )
        return file_path
    
    return validate_and_convert


def _validate_and_convert_datetime(var: Var) -> datetime.datetime:
    if var.value is None:
        raise error.VariableUnset(
            f"Expected dotenv variable for dataclass field '{var.name}' "
            "to be an ISO-formatted datetime string, not unset!"
        )

    try:
        return datetime.datetime.fromisoformat(var.value)
    except ValueError as err:
        raise error.CannotParse(f"Cannot parse datetime: {str(err).removeprefix('ValueError: ')}")


def _validate_and_convert_date(var: Var) -> datetime.date:
    if var.value is None:
        raise error.VariableUnset(
            f"Expected dotenv variable for dataclass field '{var.name}' "
            "to be an ISO-formatted date string, not unset!"
        )
    try:
        return datetime.date.fromisoformat(var.value)
    except ValueError as err:
        raise error.CannotParse(f"Cannot parse date: {str(err).removeprefix('ValueError: ')}")


def _validate_and_convert_timedelta(var: Var) -> datetime.timedelta:
    if var.value is None:
        raise error.VariableUnset(
            f"Expected dotenv variable for dataclass field '{var.name}' "
            "to be a time duration, e.g. '1s', '1m', '1h', '1d', etc., not unset!"
        )
    return parse.timedelta(var.value)


class _Parse:

    def dotenv_from_chars_iter(
            self,
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
        return self._iter_vars_from_dotenv_chars(iter(chars))

    _DOTENV_STATE_BEFORE_NAME = 0
    _DOTENV_STATE_IN_UNQUOTED_NAME = 1
    _DOTENV_STATE_IN_QUOTED_NAME = 2
    _DOTENV_STATE_AFTER_NAME = 3
    _DOTENV_STATE_BEFORE_VAL = 4
    _DOTENV_STATE_IN_UNQUOTED_VAL = 5
    _DOTENV_STATE_IN_DOUBLE_QUOTED_VAL = 6
    _DOTENV_STATE_IN_SINGLE_QUOTED_VAL = 7
    _DOTENV_STATE_AFTER_VAL = 8
    _DOTENV_STATE_IN_COMMENT = 9

    def _iter_vars_from_dotenv_chars(
            self,
            chars: Iterator[str],
    ) -> Iterator[Var]:
        # Parse implementation tries to be compatible with python-dotenv.
        # See: https://pypi.org/project/python-dotenv -- File format

        name_chars: list[str] = []
        val_chars: list[str] = []
        state: int = self._DOTENV_STATE_BEFORE_NAME
        
        while True:
            try:
                char = next(chars)
            except StopIteration:
                break

            if state == self._DOTENV_STATE_BEFORE_NAME:
                # Ignore line-breaks and whitespace
                if char == "\n" or char == "\r" or char == " " or char == "\t" or char == "\v" or char == "\f":
                    continue
                if char == "#":
                    state = self._DOTENV_STATE_IN_COMMENT
                elif char == "'":
                    state = self._DOTENV_STATE_IN_QUOTED_NAME
                elif "A" <= char <= "Z" or "a" <= char <= "z":
                    name_chars.append(char)
                    state = self._DOTENV_STATE_IN_UNQUOTED_NAME
                else:
                    raise error.CannotParse(
                        f"Unquoted dotenv variable names may only start with letters (A-Za-z), found '{char}'!"
                    )
            elif state == self._DOTENV_STATE_IN_UNQUOTED_NAME:
                if char == "=":
                    state = self._DOTENV_STATE_BEFORE_VAL
                # TODO: Check how bash actually handles vertical tabs.
                elif char == " " or char == "\t" or char == "\v":
                    state = self._DOTENV_STATE_AFTER_NAME
                elif char == "_" or "A" <= char <= "Z" or "0" <= char <= "9" or "a" <= char <= "z":
                    name_chars.append(char)
                else:
                    raise error.CannotParse(
                        f"Unquoted dotenv variable names may only contain letters, number and underscores (A-Za-z_), found '{char}'!"
                    )
            elif state == self._DOTENV_STATE_BEFORE_VAL:
                # Allow empty values
                if char == "\n" or char == "\r" or char == "\f":
                    yield Var("".join(name_chars), None)
                    name_chars.clear()
                    state = self._DOTENV_STATE_BEFORE_NAME
                elif char == '"':
                    state = self._DOTENV_STATE_IN_DOUBLE_QUOTED_VAL
                elif char == "'":
                    state = self._DOTENV_STATE_IN_SINGLE_QUOTED_VAL
                elif char == "#":
                    yield Var("".join(name_chars), "")
                    name_chars.clear()
                    state = self._DOTENV_STATE_IN_COMMENT
                elif char != " " and char != "\t" and char != "\v":
                    val_chars.append(char)
                    state = self._DOTENV_STATE_IN_UNQUOTED_VAL
            elif state == self._DOTENV_STATE_IN_UNQUOTED_VAL:
                if char == "\n" or char == "\r" or char == "\f":
                    yield Var("".join(name_chars), "".join(val_chars))
                    name_chars.clear()
                    val_chars.clear()
                    state = self._DOTENV_STATE_BEFORE_NAME
                elif char == " " or char == "\t" or char == "\v":
                    state = self._DOTENV_STATE_AFTER_VAL
                else:
                    val_chars.append(char)
            elif state == self._DOTENV_STATE_IN_DOUBLE_QUOTED_VAL:
                if char == '"':
                    state = self._DOTENV_STATE_AFTER_VAL
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
                        raise error.CannotParse(
                            f"Invalid escape sequence '\\{escaped_char}' inside double-quoted value!"
                        )
                else:
                    val_chars.append(char)
            elif state == self._DOTENV_STATE_IN_SINGLE_QUOTED_VAL:
                if char == "'":
                    state = self._DOTENV_STATE_AFTER_VAL
                elif char == "\\":
                    escaped_char = next(chars)
                    if escaped_char == "'":
                        val_chars.append("'")
                    elif escaped_char == "\\":
                        val_chars.append("\\")
                    else:
                        raise error.CannotParse(
                            f"Invalid escaped sequence '\\{escaped_char}' inside single-quoted value!"
                        )
                else:
                    val_chars.append(char)
            elif state == self._DOTENV_STATE_AFTER_VAL:
                if char == "\n" or char == "\r" or char == "\f":
                    yield Var("".join(name_chars), "".join(val_chars))
                    name_chars.clear()
                    val_chars.clear()
                    state = self._DOTENV_STATE_BEFORE_NAME
                elif char == "#":
                    yield Var("".join(name_chars), "".join(val_chars))
                    name_chars.clear()
                    val_chars.clear()
                    state = self._DOTENV_STATE_IN_COMMENT
                elif char != " " and char != "\t" and char != "\v":
                    raise error.CannotParse(
                        f"Invalid non-whitespace character '{char}' after value ended!"
                    )
            elif state == self._DOTENV_STATE_IN_COMMENT:
                if char == "\n" or char == "\r" or char == "\f":
                    state = self._DOTENV_STATE_BEFORE_NAME
            elif state == self._DOTENV_STATE_AFTER_NAME:
                if char == "=":
                    state = self._DOTENV_STATE_BEFORE_VAL
                elif char != " " and char != "\t" and char != "\v":
                    raise error.CannotParse(
                        f"Invalid non-whitespace character '{char}' after name and before '='!"
                    )
            elif state == self._DOTENV_STATE_IN_QUOTED_NAME:
                if char == "'":
                    state = self._DOTENV_STATE_AFTER_NAME
                elif char == "\\":
                    escaped_char = next(chars)
                    if escaped_char == "'":
                        name_chars.append("'")
                    elif escaped_char == "\\":
                        name_chars.append("\\")
                    else:
                        raise error.CannotParse(
                            f"Invalid escaped sequence '\\{escaped_char}' inside single-quoted name!"
                        )
                else:
                    name_chars.append(char)
            else:
                raise RuntimeError(
                    f"Unhandled parser state={state}"
                )

        if state == self._DOTENV_STATE_IN_UNQUOTED_VAL or state == self._DOTENV_STATE_AFTER_VAL:
            yield Var("".join(name_chars), "".join(val_chars))
        # Allow empty values
        elif state == self._DOTENV_STATE_BEFORE_VAL:
            yield Var("".join(name_chars), None)
        elif state != self._DOTENV_STATE_BEFORE_NAME:
            raise error.CannotParse(
                "Input ended with unterminated name or value!"
            )
                    
        # Hopefully help garbage collector
        del name_chars
        del val_chars

    _TIMEDELTA_ORD_WEEKS = 1
    _TIMEDELTA_ORD_DAYS = 2
    _TIMEDELTA_ORD_HOURS = 3
    _TIMEDELTA_ORD_MINUTES = 4
    _TIMEDELTA_ORD_SECONDS = 5
    _TIMEDELTA_ORD_MILLISECONDS = 6
    _TIMEDELTA_ORD_MICROSECONDS = 7

    def timedelta(self, s: str) -> datetime.timedelta:
        blank_err = error.CannotParse("Got blank input for timedelta!")
        default_err = error.CannotParse(
            f"Invalid timedelta input '{s}'. "
            "Input must contain a sequence of at least one number, "
            "followed by 'w', 'd', 'h', 'm', 's' or 'μs'/'us' "
            "where units cannot duplicate and larger ones must occur before smaller ones, "
            "optionally delimited by whitespaces, tabs or single commas!"
        )

        # Tokenize input
        tokens: list[str] = []
        token_chars: list[str] = []
        chars = iter(s)
        try:
            char = next(chars)
        except StopIteration:
            raise blank_err
        last_was_comma: bool = False
        while True:
            # Skip leading whitespace
            exit_outer_loop = False
            while char == " " or char == "\t" or char == "\v":
                try:
                    char = next(chars)
                except StopIteration:
                    exit_outer_loop = True
                    break
            if exit_outer_loop:
                break

            # Put number in token
            exit_outer_loop = False
            while "0" <= char <= "9" or char == "-" or char == "." or char == "e" or char == "E":
                token_chars.append(char)
                try:
                    char = next(chars)
                except StopIteration:
                    exit_outer_loop = True
                    break
            if not token_chars:
                raise default_err
            tokens.append("".join(token_chars))
            token_chars.clear()
            if exit_outer_loop:
                break
            
            # Put unit in token
            exit_outer_loop = False
            while char == "s" or char == "m" or char == "h" or char == "d" or char == "w" or char == "u" or char == "μ":
                token_chars.append(char)
                try:
                    char = next(chars)
                except StopIteration:
                    exit_outer_loop = True
                    break
            if not token_chars:
                raise default_err
            tokens.append("".join(token_chars))
            token_chars.clear()
            if exit_outer_loop:
                break

            last_was_comma = False
            
            # Skip trailing whitespace
            exit_outer_loop = False
            while char == " " or char == "\t" or char == "\v":
                try:
                    char = next(chars)
                except StopIteration:
                    exit_outer_loop = True
                    break
            if exit_outer_loop:
                break

            # Skip trailing comma
            if char == ",":
                try:
                    char = next(chars)
                except StopIteration:
                    last_was_comma = True
                    break

        if not tokens:
            raise blank_err

        if last_was_comma:
            raise default_err

        # Parse tokens
        weeks = 0
        days = 0
        hours = 0
        minutes = 0
        seconds = 0
        milliseconds = 0
        microseconds = 0
        ord = 0
        num: float | None = None
        for token in tokens:
            if num is None:
                try:
                    num = float(token)
                except ValueError:
                    raise default_err
            else:
                if token == "s":
                    if ord >= self._TIMEDELTA_ORD_SECONDS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_SECONDS
                    seconds = num
                    num = None
                elif token == "m":
                    if ord >= self._TIMEDELTA_ORD_MINUTES:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_MINUTES
                    minutes = num
                    num = None
                elif token == "h":
                    if ord >= self._TIMEDELTA_ORD_HOURS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_HOURS
                    hours = num
                    num = None
                elif token == "d":
                    if ord >= self._TIMEDELTA_ORD_DAYS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_DAYS
                    days = num
                    num = None
                elif token == "w":
                    if ord >= self._TIMEDELTA_ORD_WEEKS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_WEEKS
                    weeks = num
                    num = None
                elif token == "ms":
                    if ord >= self._TIMEDELTA_ORD_MILLISECONDS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_MILLISECONDS
                    milliseconds = num
                    num = None
                elif token == "us" or token == "μs":
                    if ord >= self._TIMEDELTA_ORD_MICROSECONDS:
                        raise default_err
                    ord = self._TIMEDELTA_ORD_MICROSECONDS
                    microseconds = num
                    num = None
                else:
                    raise default_err
        
        return datetime.timedelta(
            weeks=weeks,
            days=days,
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            milliseconds=milliseconds,
            microseconds=microseconds,
        )


def _transform_case(transformation: _Casing, s: str) -> str:
    if transformation == "upper":
        return s.upper()
    elif transformation == "lower":
        return s.lower()
    elif transformation == "preserve":
        return s
    elif transformation == "ignore":
        return s.lower()

    raise ValueError(f"Unknown casing transformation: '{transformation}'!")


def _issubclass_safe(cls: Any, base_cls: Any) -> bool:
    """Like issubclass but does not raise with non-class arguments."""
    try:
        return issubclass(cls, base_cls)
    except TypeError:
        return False


def _check_system_supports_python_webbrowser() -> bool:
    import webbrowser
    webbrowser.open("https://www.youtube.com/watch?v=zL19uMsnpSU")
    return True


class _Error:
    """A namespace for errors thrown by 'datadotenv' and base classes."""

    _GlobalValueError = ValueError

    class Error(Exception):
        pass


    class ValueError(Error, _GlobalValueError):
        pass


    class CannotParse(ValueError):
        pass


    class InvalidLetterCase(ValueError):
        pass


    class VariableNotSpecified(Error, AttributeError):
        pass


    class VariableMissing(ValueError):
        pass


    class VariableDuplicate(ValueError):
        pass


    class VariableUnset(ValueError):
        pass


    class CannotConvertToType(ValueError):
        pass


    class NotImplemented(Error, NotImplementedError):
        pass


    class FilePathDoesNotExist(Error, FileNotFoundError):
        pass


parse = _Parse()
error = _Error()

datadotenv = _Datadotenv()
datadotenv.error = error
